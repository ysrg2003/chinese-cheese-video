# en-007 Scene Audit and Visual Improvements

## Scope

This audit reviewed the public video [Set Up All 32 Pieces | Xiangqi Rules](https://www.youtube.com/watch?v=m1G38mfiumM) and reconstructed representative frames from the committed en-007 job payload. The audit focused on whether the board, piece setup, narration, overlays, and beginner teaching cues agree.

## Scene findings

| Scene | Spoken teaching | Existing visual result | Finding |
|---|---|---|---|
| 1 | Thirty-two pieces in a mirrored starting arrangement | Full 9×10 board, river, palaces, two-side tint, mirror cue | Correct board state and useful setup overview. |
| 2 | Piece counts for each side | Family rings on all pieces | Structurally correct, but Chinese glyphs were not explicitly mapped to the English names used in narration. |
| 3 | Chariots, Horses, Elephants, Advisors, Cannons, Soldiers, and the river-facing line | Family rings, river band, and mirrored setup | Correct starting homes and river relation. A beginner-oriented English family key was missing. |
| 4 | Open files and routes for future activity | Central files and palace route constraints | Correctly visualized a static constraint; no move was invented. |
| 5 | “In this lesson the army stays still.” | Static board with a generic `NEW IDEA` label | The visual did not state clearly enough that no move was being played. This could confuse a beginner about whether a position change occurred. |
| 6 | Names and starting homes lead into future movement lessons | Family anchors repeated | Correct roadmap bridge; the English mapping should remain available. |

## Root-cause changes

### Branding

The hard-coded renderer header was corrected from `CHINESE CHEESE VIDEO` to `CHINESE CHESS VIDEO` in `src/Composition.tsx`. This applies to future renders and does not modify already-published videos.

### English piece-family mapping

When `piece_family_anchor` is active, the renderer now adds a compact `PIECE KEY · ENGLISH NAMES` legend containing GENERAL, ADVISOR, ELEPHANT, HORSE, CHARIOT, CANNON, and SOLDIER. The colored legend matches the family ring colors while preserving the canonical Chinese piece glyphs and exact board geometry.

### Explicit no-move treatment

The visual director now recognizes sentences such as “the army stays still,” “no move,” and “without moving.” It adds the validated `no_move_notice` primitive and renders `NO MOVE · SETUP ONLY`. The generic `NEW IDEA` badge is suppressed whenever this primitive is active. This is a root-cause change in storyboard planning and rendering, not a post-production edit to one MP4.

## Verification

The updated setup frame was rendered at 1080×1920. It shows the corrected `CHINESE CHESS VIDEO` header and the English family key. The corrected no-move frame shows `NO MOVE · SETUP ONLY` and no generic `NEW IDEA` badge. The board remains a valid 9×10 Xiangqi geometry with the river and both palaces.

The full Python suite passes with **128 tests**, and direct TypeScript compilation passes. The changes are ready to be committed and used by the next GitHub Actions production run. The current public en-007 MP4 was not modified or replaced.

## References

[1]: https://www.youtube.com/watch?v=m1G38mfiumM "Public en-007 video"
[2]: https://github.com/ysrg2003/chinese-cheese-video/blob/master/src/Composition.tsx "Renderer source"
[3]: https://github.com/ysrg2003/chinese-cheese-video/blob/master/python/visual_director.py "Visual director source"
