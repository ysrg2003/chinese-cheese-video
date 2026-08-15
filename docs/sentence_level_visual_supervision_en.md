# Sentence-Level Visual Supervision

## Purpose

The production pipeline now plans visuals at sentence level for every non-foundation lesson. A narration segment is no longer treated as one undifferentiated visual window when it contains several meaningful sentences. Each sentence receives a stable `sentenceId`, a semantic `visualIntent`, a renderer-safe visual treatment, and a storyboard scene that can be checked before rendering.

The design has two goals. First, a spoken idea must have a visible counterpart: a board region, a legal path, a before/after state, a rule boundary, a piece spotlight, a question reveal, or another intentional treatment. Second, the system must remain useful when the director encounters a concept that was not included in a fixed keyword dictionary. Unknown concepts are preserved and receive a safe `concept_focus` treatment instead of being silently discarded or forcing the AI to invent a move.

## Production flow

The supervision layer runs inside `add_visual_storyboard()` in `python/visual_director.py` before the AI storyboard request and before deterministic fallback construction. Foundation lessons retain their dedicated storyboard contract because their scene order is intentionally fixed. All other storyboard lessons follow this sequence:

| Stage | Operation | Blocking condition |
| --- | --- | --- |
| 1 | Split each narration segment into meaningful sentences with `split_sentences()` | Empty narration produces no usable segments |
| 2 | Preserve the original beat metadata, including `kind`, `movePhase`, `movePly`, and move data | Metadata cannot be lost during expansion |
| 3 | Assign a `sentenceId` and an intent to every sentence | Missing ID or intent fails coverage validation |
| 4 | Map known concepts to verified visual treatments | Unsupported primitives are rejected |
| 5 | Map new concepts to `concept_focus` with `confidence: inferred` | The fallback must not invent a move or an unverified piece state |
| 6 | Send `sentenceVisualIntents` and the expanded segments to the AI visual director | The AI receives explicit supervision rather than only raw prose |
| 7 | Normalize the AI storyboard against the deterministic contract | Invalid scene counts, text, plans, or primitives fall back safely |
| 8 | Attach scenes back to the sentence segments | Scene count must equal narration segment count |
| 9 | Run `validate_visual_storyboard()` before rendering | Any missing sentence coverage blocks production |

The TTS stage later replaces the proportional timing estimates with actual word-aligned timing. Therefore, the supervision layer does not treat its initial timing estimates as final audio timing.

## Data contract

A sentence segment contains the original narration metadata plus the supervision fields:

```json
{
  "kind": "intro",
  "text": "The first exchange changes the rhythm of the position.",
  "captionText": "The first exchange changes the rhythm of the position.",
  "sentenceId": "seg-001-sent-01",
  "visualIntent": {
    "concept": "The first exchange changes the rhythm of the position",
    "semanticRole": "concept_explanation",
    "visualTreatment": "concept_focus",
    "evidenceMode": "board_state",
    "coverage": "covered",
    "confidence": "inferred"
  }
}
```

The job also records an aggregate audit object and a flat intent list:

```json
{
  "sentenceVisualSupervision": {
    "version": "sentence_visual_supervision_v1",
    "status": "planned",
    "sourceSegmentCount": 1,
    "sentenceCount": 1,
    "unresolvedCount": 0
  },
  "sentenceVisualIntents": [
    {
      "sentenceId": "seg-001-sent-01",
      "visualTreatment": "concept_focus",
      "visualKind": "board_overview",
      "primitives": ["concept_focus"],
      "confidence": "inferred"
    }
  ]
}
```

`sentenceVisualIntents` is sent explicitly in the AI storyboard request. The same intent is also present on the corresponding segment so the deterministic normalizer can enforce the contract even if the AI returns incomplete or overly broad scene instructions.

## Known concept treatments

Known concepts are mapped to board-safe treatments. The mapping is intentionally conservative: it selects primitives that already have a deterministic Remotion renderer and does not authorize arbitrary geometry.

| Meaning in narration | Treatment | Main primitives | Evidence mode |
| --- | --- | --- | --- |
| River, territory, or palace regions | `region_split` | `river_band`, `territory_split`, `palace_x` | `board_state` |
| Files, ranks, intersections, or notation | `coordinate_map` | `files`, `ranks`, `coordinate_endpoints` | `board_state` |
| Horse Leg blocking mechanic | `horse_leg` | `piece_anchor`, `horse_leg`, `legal_destinations` | `claim_proof` |
| Elephant Eye blocking mechanic | `elephant_eye` | `piece_anchor`, `elephant_eye`, `river_limit` | `claim_proof` |
| Cannon Screen mechanic | `cannon_screen` | `piece_anchor`, `cannon_screen`, `cannon_target` | `claim_proof` |
| General, check, or checkmate goal | `goal_focus` | `palace_piece_anchor`, `pressure_marker` | `board_state` |
| Named piece or piece movement | `piece_spotlight` | `piece_anchor`, `legal_destinations` | `board_state` |
| History, origin, or cultural context | `history_context` | `board_overview` | `research_bundle` |
| Comparison language | `comparison` | `before_after` | `editorial_bridge` |
| Tempo, initiative, momentum, or strategic balance without a supplied legal position | `strategic_bridge` | `concept_bridge` with labeled editorial states | `editorial_bridge` |
| Question or viewer challenge | `question_reveal` | `legal_destinations` | `board_state` |

The known mapping does not replace the deeper semantic contract in `visual_director.py`. For example, a sentence about the Elephant Eye can still receive the specialized deterministic `elephant_eye` contract, while a sentence about the river and palaces can receive the canonical `river_palaces` board plan.

## Flexible handling of new concepts

A new concept is not an error merely because it is absent from `KNOWN_TREATMENTS`. The planner preserves the sentence text in the intent, marks the intent as `inferred`, and assigns `concept_focus`. The renderer then keeps the canonical 9×10 Xiangqi board visible, adds a gold focus frame and focus ring, and shows a `NEW IDEA` marker. It does not invent a move, alter the FEN, fabricate a piece, or claim that an unverified board relation exists.

The semantic director may refine an unknown concept if it can produce an allowed, evidence-backed plan. If it cannot, the deterministic fallback remains renderable. This makes the system extensible without requiring a code change for every new editorial phrase.

The fallback also preserves specialized existing visual kinds. For example, a history lesson that already selected `history_timeline`, `two_armies`, or `learning_roadmap` is not downgraded to `concept_focus`; those progression scenes remain protected for history, board, setup, and related curriculum profiles. The generic treatment is used for genuinely unseen concepts where no protected progression contract applies. If two inferred concepts are adjacent, their focus signatures must differ so the fallback cannot silently render the same generic scene twice.

## Idempotence and timing

`expand_narration_segments()` is idempotent. If the job already contains `sentenceVisualSupervision`, a second call returns the job unchanged. This prevents repeated workflow stages, retries, and remediation runs from multiplying narration segments.

When a source segment has no final audio timing, the planner estimates each sentence window proportionally to word count and carries a cumulative cursor across all source segments. This cumulative cursor is important for the four move beats: action, reply, effect, and constraint must not all start at zero, otherwise Remotion would keep selecting the first overlapping scene and the rendered MP4 could show the wrong visual treatment. If a source segment already has timing, the estimate is distributed across its sentences. TTS word alignment remains authoritative later in the pipeline, so these estimates are only planning values.

## Validation rules

`validate_sentence_visual_coverage()` blocks the following conditions:

| Failure | Result |
| --- | --- |
| No intent list | Production stops before rendering |
| Intent count differs from expanded segment count | Production stops |
| Intent has no `sentenceId` | Production stops |
| Intent has no `visualTreatment` | Production stops |
| Intent is marked `unresolved` | Production stops |
| Intent has an invalid coverage state | Production stops |
| Segment has no `sentenceId` or `visualIntent` | `validate_visual_storyboard()` blocks the storyboard |
| Scene count differs from sentence segment count | `validate_visual_storyboard()` blocks the storyboard |
| Scene contains an unsupported primitive | `validate_visual_storyboard()` blocks the storyboard |

Foundation storyboard modes are excluded from the new sentence expansion because those lessons use a fixed, audited visual sequence. They remain protected by their existing foundation validation.

## Remotion implementation

The renderer now has two safe paths for abstract ideas. `concept_focus` provides focus and hierarchy without asserting a move. `concept_bridge` is a controlled editorial model for language such as tempo or initiative: it shows two labeled states, such as `QUIET TEMPO` and `FORCING TEMPO`, plus `EDITORIAL MODEL · NOT A MOVE`. It never changes the FEN or claims that either state was played. Both primitives are declared in the Python supported primitive set and rendered in `src/Composition.tsx`. All legal move demonstrations continue to use the existing FEN-derived board state, verified move geometry, and dedicated primitives such as `horse_leg`, `cannon_screen`, `elephant_eye`, `legal_path`, and `played_destination`.

The TypeScript types now carry `VisualIntent`, `sentenceId`, `visualIntent`, `sentenceVisualIntents`, and `sentenceVisualSupervision`. This keeps the sentence-level audit data available through storyboard normalization and rendering without weakening the existing board-state types.

## Tests

The dedicated test file is `python/test_sentence_visual_supervision.py`. It verifies that:

1. An unseen concept receives `concept_focus` with `confidence: inferred`.
2. Multiple sentences receive distinct stable IDs and distinct treatments where appropriate.
3. Expansion is idempotent.
4. An unknown concept can produce a renderable fallback with no fake move.
5. The resulting storyboard passes the pre-render validation gate.

Existing visual-director tests also cover the intentional change that one move beat containing several sentences becomes several sentence-scoped scenes while preserving the original `movePhase` and legal move contract.

Run focused tests with:

```bash
env PYTHONPATH=python \
  XIANGQI_RESEARCH_REQUIRED=0 \
  GOOGLE_GROUNDING_ENABLED=0 \
  GOOGLE_GROUNDING_REQUIRED=0 \
  AI_ROUTER_REQUIRE_KEYS=0 \
  PREPUBLISH_CRITIC_REQUIRED=0 \
  python3 -m unittest python/test_sentence_visual_supervision.py python/test_visual_director.py
```

A non-publishing experiment fixture is available at `python/run_sentence_supervision_experiment.py`. It uses two unseen concepts, disables publication in the job payload, runs the deterministic storyboard path, and writes its artifacts under `experiment-output/`.

```bash
env PYTHONPATH=python AI_ROUTER_REQUIRE_KEYS=0 \
  XIANGQI_RESEARCH_REQUIRED=0 GOOGLE_GROUNDING_ENABLED=0 \
  GOOGLE_GROUNDING_REQUIRED=0 PREPUBLISH_CRITIC_REQUIRED=0 \
  python3 python/run_sentence_supervision_experiment.py
```

Run the complete Python suite with:

```bash
env XIANGQI_RESEARCH_REQUIRED=0 \
  GOOGLE_GROUNDING_ENABLED=0 \
  GOOGLE_GROUNDING_REQUIRED=0 \
  AI_ROUTER_REQUIRE_KEYS=0 \
  PREPUBLISH_CRITIC_REQUIRED=0 \
  PYTHONPATH=python \
  python3 -m unittest discover -s python -p 'test_*.py'
```

The production workflow still keeps research grounding, claim proof, creative review, visual validation, and publication reconciliation as separate gates. Sentence-level supervision adds another deterministic pre-render check; it does not replace those gates.
