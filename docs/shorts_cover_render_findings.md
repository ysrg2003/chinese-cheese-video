# Vertical Shorts cover render findings

A four-second Remotion sample was rendered from `python/shorts_cover_sample_job.json` at 1080×1920.

At approximately 1.0 second, the frame is a clean vertical cover: a dark navy-to-red header, `XIANGQI LAB`, the English title `The General: Palace Rules`, `CHINESE CHESS • BOARD • HISTORY • STRATEGY`, `ENGLISH PRIMARY`, and `SHORT LESSON`, with the clean corrected Xiangqi board below. No spoken caption, MoveCard, or animated overlay obscures the frame.

At approximately 3.2 seconds, the cover has fully faded out and the normal video returns: the regular English title, corrected board, and synchronized spoken-sentence cue are visible. This confirms that the cover is a short opening visual state rather than a permanent replacement for the educational content.

The production policy keeps the 16:9 `thumbnail_en.jpg` upload for non-Short surfaces, while the vertical MP4 opening frame is the automated cover strategy for Shorts surfaces where YouTube Help documents frame selection through the YouTube app rather than Studio.

## Live production proof

Production run `31778300228` published `curriculum-en-005-the-9x10-point-board-en` as video `ErLAZQvHUiM`. The extracted 1.0-second frame from the published MP4 shows the vertical English cover with `XIANGQI LAB`, `The 9×10 Point Board`, `CHINESE CHESS • BOARD • HISTORY • STRATEGY`, `ENGLISH PRIMARY`, `SHORT LESSON`, and the corrected board. The extracted 3.2-second frame shows the cover gone and the normal `Board Basics First` / `BOARD MAP` teaching cues plus the synchronized spoken-sentence cue. This proves the new behavior survived the real GitHub Actions production render and was not limited to the local sample.
