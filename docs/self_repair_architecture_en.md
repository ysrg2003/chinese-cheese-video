# Self-Repair Architecture for Xiangqi Lab

## Purpose

The self-repair lane sits beside the production pipeline. It does not replace legal validation, research grounding, visual QA, creative criticism, or YouTube publication reconciliation. Its responsibility is to diagnose a failed production attempt, request a structured repair plan from the AI router, apply only an allowlisted content or visual patch, rerun the smallest safe production boundary, and return control to the original pipeline.

The key rule is:

> The repair lane may repair the candidate artifact, but it may never weaken a gate, invent claim proof, publish directly, or modify production code through an untrusted free-form AI response.

## State machine

| State | Meaning | Allowed next states |
|---|---|---|
| `production_failed` | The original pipeline stopped before completion | `diagnosing`, `retry_candidate`, `quarantined` |
| `diagnosing` | Failure evidence is being collected and classified | `repair_planned`, `retry_stage`, `quarantined` |
| `repair_planned` | A strict JSON repair plan was returned and validated | `applying_patch`, `retry_stage`, `quarantined` |
| `applying_patch` | An allowlisted patch is being applied to a temporary candidate artifact | `verification`, `quarantined` |
| `verification` | The patched artifact is rechecked by deterministic gates and, where required, AI review | `resuming`, `quarantined` |
| `resuming` | The original pipeline is rerun from the earliest affected stage | `completed`, `production_failed` |
| `completed` | The repaired artifact passed all gates and reached the existing publication path | terminal |
| `quarantined` | No safe automatic repair exists within the bounded budget | terminal for this attempt; candidate remains retryable or blocked according to the existing policy |

## Failure evidence package

Every repair request receives a bounded evidence package containing the stable job ID, candidate ID, current stage, exception text, command return code, input payload, latest job JSON if available, research bundle status, claim proof, storyboard validation errors, visual QA report, creative critic report, and the list of files written for the attempt. Large media files are represented by paths, dimensions, hashes, and selected frame evidence rather than being copied into the prompt without a size limit.

The package is stored with a SHA-256 fingerprint. A repair attempt cannot be applied if its evidence fingerprint no longer matches the checkpoint that produced the plan.

## Strict repair-plan contract

The AI router must return JSON matching the following conceptual contract:

```json
{
  "schema": "xiangqi_self_repair_v1",
  "disposition": "apply_patch",
  "failure_class": "content_claim",
  "root_cause": "The narration claims a cannon controls a file after a pawn move, but the claim proof does not establish that relation.",
  "diagnosis": "The move is legal; the causal sentence is unsupported.",
  "patch_type": "content_patch",
  "patch": {
    "replace_move_fields": {
      "3": {
        "purpose": "Describe only the pawn's legal move.",
        "effect": "The position changes without claiming a cannon effect.",
        "opponentReply": "Describe a legal reply or use a neutral response.",
        "claims": [{"claimType": "legal_move", "ply": 3, "position": "after", "statement": "The supplied move is legal."}]
      }
    }
  },
  "resume_stage": "director",
  "required_gates": ["research_grounding", "legal_moves", "claim_proof", "visual_storyboard", "visual_qa", "creative_critic"]
}
```

The actual implementation validates all fields, limits string sizes, rejects unknown patch keys, rejects Arabic in English content, rejects changes to publication metadata, and rejects any plan that asks to disable or bypass a gate.

## Allowlisted repair types

Content repairs may replace title, narration, move purpose, reply, effect, constraint focus, claims, or a complete move sequence only when the repaired payload passes the existing Xiangqi validator and claim-proof validator. A complete move-sequence replacement is allowed only for supplementary dynamic candidates; fixed curriculum payloads remain hard failures when their source definition is invalid.

Visual repairs reuse the existing protected scene-repair contract. They may change a scene headline, visual instruction, visual kind, semantic tags, visual plan, or validated generated-asset reference. They may not change `fen`, `moves`, `from`, `to`, `piece`, `side`, narration, captions, move phase, or generated asset paths outside the approved asset contract.

Stage retries cover transient TTS, image-service, network, browser, or Remotion failures. They reuse the same stable job ID and checkpoint, and they never create a new candidate or a second publication identity.

Source-code or workflow repairs are not applied directly to production by an unconstrained model response. The repair lane records a structured maintenance proposal, runs isolated tests when a matching allowlisted transformation exists, and quarantines the proposal for controlled integration when arbitrary source changes would be required.

## Checkpoint and resume rules

A repair checkpoint is written before every AI request and after every patch. It records the original input hash, the evidence hash, the plan hash, the patch hash, attempt number, current stage, and verification result. The checkpoint is stored in a dedicated SQLite table and in the job's output artifact directory. The original candidate input is immutable; every repair operates on a copied candidate input under the job's repair directory.

The maximum automatic repair budget is bounded per job and per workflow run. A job may receive a small number of repair attempts, and a failed repair cannot recursively create unlimited AI calls. When the budget is exhausted, the candidate is returned to the existing retry or quarantine policy with a complete diagnostic report.

## Publication boundary

The repair lane ends before YouTube publication. Only the original publisher may create or update a YouTube publication record. The candidate is marked published only after the existing public-upload, localization, playlist, and reconciliation contracts succeed. Review-only runs can produce and inspect repaired MP4 artifacts but cannot advance curriculum state or create public publication records.

## Expected behavior

A malformed model field, unsupported causal sentence, illegal dynamic move declaration, or visual mismatch should now cause a diagnose-plan-apply-verify-resume cycle. A legal curriculum defect, missing credentials, exhausted daily quota, authentication failure, or unsafe repair proposal should not be hidden by a fallback. It should be reported with evidence and left for the existing retry, cooldown, or quarantine behavior.
