# Audit of `The General: The Piece You Must Never Expose`

Video: https://www.youtube.com/watch?v=QEdAG1azW2U

The independent audiovisual audit found a critical error in move 3.

The introduction correctly states that the general is restricted to the 3×3 palace. Move 1 is narrated and shown as the red general moving from file 5, rank 10 to file 5, rank 9; this is a legal one-point orthogonal move inside the red palace. Move 2 is narrated and shown as the black general moving from file 5, rank 1 to file 5, rank 2; this is legal in the displayed position because the central soldiers at files/ranks 5/4 and 5/7 still block the line, so the generals are not facing across an empty file.

Move 3 is narrated as the red advisor moving from file 4, rank 10 to file 5, rank 9. The diagonal geometry is advisor-compatible, but file 5, rank 9 is already occupied by the red general after move 1. A Xiangqi piece cannot move onto a square occupied by a friendly piece, and the animation effectively replaces or captures its own general. The move is therefore illegal and the narration falsely presents it as a defensive lesson.

The core failure is not the flying-general rule in moves 1–2; it is the absence of destination occupancy and friendly-collision validation before the move was narrated, rendered, and uploaded. The validator must reject this line before TTS and must generate an alternative legal advisor move or discard the example.

The failed publication record in SQLite is `curriculum-en-010-the-general-en`, with video id `QEdAG1azW2U`. It carries status `failed` despite having a YouTube video id, so the catalog must treat it as a remediation candidate rather than a trusted successful publication.
