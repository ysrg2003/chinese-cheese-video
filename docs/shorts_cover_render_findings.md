# Shorts cover strategy retirement

## Decision

The vertical opening-cover strategy was retired after live production testing. YouTube selected a frame non-deterministically in the Shorts surface, so an opening card inside the MP4 could not guarantee the visible channel cover. The project no longer adds a dedicated `VerticalShortCover` state to new videos.

The standard English `thumbnail_en.jpg` remains generated, validated, and uploaded through `thumbnails.set` for surfaces that support ordinary custom thumbnails. This does not claim control over the Shorts grid cover.

## Live test retained for audit

Production run `31778300228` published `curriculum-en-005-the-9x10-point-board-en` as video `ErLAZQvHUiM`. Its 1.0-second frame showed the temporary vertical cover, while the 3.2-second frame returned to normal teaching cues. The experiment demonstrated that the cover can render correctly inside the MP4 but cannot guarantee the frame that Shorts chooses; therefore the strategy was retired rather than extended.

## Replacement priority

The production effort now prioritizes narration-to-visual alignment. Each narration segment receives a semantic visual plan. Board geometry, files, ranks, intersections, river, palaces, legal destinations, piece paths, cannon screens, and horse-leg constraints use deterministic Remotion overlays. Reference-edit image generation is reserved for non-geometric concepts only, and only when a scene explicitly declares `visualPlan.mode=reference_edit` and supplies a safe masked region preserving the canonical board.
