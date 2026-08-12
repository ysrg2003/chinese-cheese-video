from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests


class ProviderExhausted(RuntimeError):
    pass


class ProviderFailure(RuntimeError):
    def __init__(self, message: str, *, retryable: bool, cooldown_seconds: int = 0, status_code: int | None = None) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.cooldown_seconds = cooldown_seconds
        self.status_code = status_code


@dataclass(frozen=True)
class GeminiSlot:
    slot_id: str
    api_key: str
    project: str


class ProviderRouter:
    """Ordered, stateful provider failover for unattended GitHub Actions runs."""

    def __init__(self, store: Any | None = None) -> None:
        self.store = store
        self.gemini_models = [
            os.getenv("GEMINI_PRIMARY_MODEL", "gemini-2.5-flash"),
            os.getenv("GEMINI_SECONDARY_MODEL", "gemini-2.5-flash-lite"),
        ]
        self.gemini_slots = self._load_gemini_slots()
        self.hf_models = self._csv(os.getenv("HF_MODELS", "openai/gpt-oss-120b:fastest"))
        self.max_attempts = max(1, int(os.getenv("AI_MAX_ATTEMPTS", "24")))
        self.timeout = max(15, int(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "90")))

    @staticmethod
    def _csv(raw: str) -> list[str]:
        return [item.strip() for item in re.split(r"[,\n]+", raw or "") if item.strip()]

    def _load_gemini_slots(self) -> list[GeminiSlot]:
        slots: list[GeminiSlot] = []
        raw_json = os.getenv("GEMINI_KEYS_JSON", "").strip()
        if raw_json:
            try:
                values = json.loads(raw_json)
                for index, value in enumerate(values):
                    if isinstance(value, str):
                        slots.append(GeminiSlot(f"gemini-{index + 1}", value.strip(), "default"))
                    elif isinstance(value, dict) and value.get("key"):
                        slots.append(
                            GeminiSlot(
                                str(value.get("id") or f"gemini-{index + 1}"),
                                str(value["key"]).strip(),
                                str(value.get("project") or "default"),
                            )
                        )
            except json.JSONDecodeError:
                print("GEMINI_KEYS_JSON is invalid JSON; falling back to GEMINI_API_KEYS")
        if not slots:
            raw = os.getenv("GEMINI_API_KEYS", "") or os.getenv("GOOGLE_API_KEYS", "")
            values = self._csv(raw)
            if not values and os.getenv("GOOGLE_API_KEY"):
                values = [os.environ["GOOGLE_API_KEY"]]
            if not values and os.getenv("GEMINI_API_KEY"):
                values = [os.environ["GEMINI_API_KEY"]]
            slots = [GeminiSlot(f"gemini-{index + 1}", value, "default") for index, value in enumerate(values)]
        return slots

    def available(self) -> bool:
        return bool(self.gemini_slots or (os.getenv("HF_TOKEN") and self.hf_models) or os.getenv("OLLAMA_BASE_URL"))

    def generate_json(self, *, system_prompt: str, user_prompt: str, operation: str) -> dict[str, Any]:
        attempts = 0
        errors: list[str] = []
        for model in self.gemini_models:
            for slot in self.gemini_slots:
                if attempts >= self.max_attempts:
                    break
                attempts += 1
                if self._is_cooling("gemini", model, slot.slot_id):
                    continue
                try:
                    result, usage = self._call_gemini(slot, model, system_prompt, user_prompt)
                    self._record("gemini", model, slot.slot_id, slot.project, operation, "success", usage=usage)
                    return result
                except ProviderFailure as exc:
                    errors.append(f"gemini/{model}/{slot.slot_id}: {exc}")
                    self._record_failure("gemini", model, slot.slot_id, slot.project, operation, exc)

        if os.getenv("HF_TOKEN"):
            for model in self.hf_models:
                if attempts >= self.max_attempts:
                    break
                attempts += 1
                if self._is_cooling("huggingface", model, model):
                    continue
                try:
                    result, usage = self._call_huggingface(model, system_prompt, user_prompt)
                    self._record("huggingface", model, model, "router", operation, "success", usage=usage)
                    return result
                except ProviderFailure as exc:
                    errors.append(f"huggingface/{model}: {exc}")
                    self._record_failure("huggingface", model, model, "router", operation, exc)

        raise ProviderExhausted("All configured AI providers failed or are cooling down: " + " | ".join(errors[-8:]))

    def _call_gemini(
        self,
        slot: GeminiSlot,
        model: str,
        system_prompt: str,
        user_prompt: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        try:
            response = requests.post(endpoint, params={"key": slot.api_key}, json=payload, timeout=self.timeout)
        except requests.RequestException as exc:
            raise ProviderFailure(str(exc), retryable=True, cooldown_seconds=30) from exc
        body = self._json_response(response)
        if response.status_code >= 400:
            raise self._classify_http_failure(response.status_code, body)
        try:
            text = body["candidates"][0]["content"]["parts"][0]["text"]
            return self._parse_json(text), body.get("usageMetadata", {})
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderFailure(f"Gemini returned an invalid JSON response: {body}", retryable=False, status_code=response.status_code) from exc

    def _call_huggingface(self, model: str, system_prompt: str, user_prompt: str) -> tuple[dict[str, Any], dict[str, Any]]:
        endpoint = os.getenv("HF_BASE_URL", "https://router.huggingface.co/v1").rstrip("/") + "/chat/completions"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        try:
            response = requests.post(
                endpoint,
                headers={"Authorization": f"Bearer {os.environ['HF_TOKEN']}", "Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise ProviderFailure(str(exc), retryable=True, cooldown_seconds=30) from exc
        body = self._json_response(response)
        if response.status_code >= 400:
            raise self._classify_http_failure(response.status_code, body)
        try:
            text = body["choices"][0]["message"]["content"]
            return self._parse_json(text), body.get("usage", {})
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderFailure(f"Hugging Face returned an invalid JSON response: {body}", retryable=False, status_code=response.status_code) from exc

    @staticmethod
    def _json_response(response: requests.Response) -> dict[str, Any]:
        try:
            data = response.json()
            return data if isinstance(data, dict) else {"data": data}
        except ValueError:
            return {"raw": response.text[:2000]}

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        clean = str(text or "").strip()
        clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\s*```$", "", clean).strip()
        parsed = json.loads(clean)
        if not isinstance(parsed, dict):
            raise ValueError("Model output is not a JSON object")
        return parsed

    @staticmethod
    def _classify_http_failure(status_code: int, body: dict[str, Any]) -> ProviderFailure:
        message = json.dumps(body, ensure_ascii=False)[:1000]
        if status_code in {401, 403}:
            return ProviderFailure(f"authentication or permission failure: {message}", retryable=False, cooldown_seconds=86_400, status_code=status_code)
        if status_code == 429:
            return ProviderFailure(f"rate limit or quota exhausted: {message}", retryable=True, cooldown_seconds=900, status_code=status_code)
        if status_code in {408, 409, 425, 500, 502, 503, 504}:
            return ProviderFailure(f"transient provider failure: {message}", retryable=True, cooldown_seconds=120, status_code=status_code)
        return ProviderFailure(f"provider rejected request: {message}", retryable=False, cooldown_seconds=300, status_code=status_code)

    def _is_cooling(self, provider: str, model: str, slot_id: str) -> bool:
        if not self.store or not hasattr(self.store, "get_provider_state"):
            return False
        state = self.store.get_provider_state(provider, model, slot_id)
        if not state or not state.get("cooldown_until"):
            return False
        try:
            return datetime.fromisoformat(state["cooldown_until"]) > datetime.now(timezone.utc)
        except ValueError:
            return False

    def _record_failure(self, provider: str, model: str, slot_id: str, project: str, operation: str, exc: ProviderFailure) -> None:
        cooldown = max(0, exc.cooldown_seconds)
        if self.store and hasattr(self.store, "record_provider_failure"):
            self.store.record_provider_failure(
                provider=provider,
                model=model,
                slot_id=slot_id,
                project=project,
                operation=operation,
                error_class=self._error_class(exc),
                error_message=str(exc),
                cooldown_seconds=cooldown,
                status_code=exc.status_code,
            )
        if cooldown:
            time.sleep(min(2.0, cooldown / 1000.0))

    def _record(self, provider: str, model: str, slot_id: str, project: str, operation: str, status: str, usage: dict[str, Any] | None = None) -> None:
        if self.store and hasattr(self.store, "record_provider_call"):
            self.store.record_provider_call(
                provider=provider,
                model=model,
                slot_id=slot_id,
                project=project,
                operation=operation,
                status=status,
                usage=usage or {},
            )

    @staticmethod
    def _error_class(exc: ProviderFailure) -> str:
        if exc.status_code in {401, 403}:
            return "auth"
        if exc.status_code == 429:
            return "quota"
        if exc.status_code and exc.status_code >= 500:
            return "transient"
        return "invalid_or_unknown"
