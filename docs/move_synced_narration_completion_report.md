# Move-Synchronized Narration and Caption Completion Report

## User-facing problem

The previous renderer created a long transcript caption that could remain visible across the entire video. At the same time, a separate MoveCard displayed the current move. The voice often explained a general concept instead of explicitly naming the move that the board was showing. This made the viewer choose between three different signals: voice, transcript, and board animation.

## New narration contract

Every generated job now contains `narrationSegments`. The first segment is an introduction. Each following segment belongs to exactly one `movePly` and contains a short spoken sentence that names the move, the side, the piece, the source square, the destination square, and the purpose of the move. The full TTS input is the introduction followed by these move sentences in order.

For English, a move sentence follows this form:

> Move 1: red pawn, from file 1, rank 7 to file 1, rank 6. Focus: opening pressure.

The purpose phrase is selected from the content type, such as opening pressure, the forcing threat, the conversion, the forcing idea, the game plan, the different geometry, the skill test, or the viewer challenge. The Chinese voice uses the equivalent concise Chinese sentence and continues to use the male `zh-CN-YunjianNeural` voice.

## Audio-derived timing

After Edge-TTS returns WordBoundary cues, the pipeline counts the spoken units belonging to each narration segment and assigns that segment the exact start and end range of the corresponding audio cues. The same range is then applied to the associated move. The caption is created from the narration segment itself, not from an independently invented summary.

If WordBoundary data is unavailable, the same segment order is distributed proportionally across the estimated duration. This fallback still keeps one caption per introduction or move and does not stretch one full transcript across all later moves. A compatibility guard preserves the old retiming behavior for jobs that have narration segments without audio-derived timestamps, including `skip_tts` previews.

## Visual layout

The Remotion composition now renders only the active caption and returns no caption element when the current time is outside a cue. Captions are positioned above the board, with a bounded two-line area and smaller text. The MoveCard is positioned above the caption and shows the move number, piece, source/destination coordinate labels, and the short move label. Neither layer covers the board or persists into the next move window.

## Validation

The local suite passed 13 tests, including the new test that creates two move narration segments, aligns them to audio cues, and confirms that the move captions do not overlap. Python compilation, TypeScript typechecking, workflow validation, and a local Remotion render all passed.

Workflow `31658898459` completed successfully from commit `4ada3ed`. It ran English only and published:

| Item | Result |
| --- | --- |
| Public video | [One Cannon Pattern Every New Xiangqi Player Should Know — Series 33.2](https://www.youtube.com/watch?v=gSgVXtG9Snw) |
| Duration | 0:38 on YouTube; 37.894 seconds in the job record |
| Content type | `tactics` |
| Caption source | `move_narration_audio` |
| Move 1 window | 12.939–21.258 seconds |
| Move 2 window | 21.258–29.576 seconds |
| Move 3 window | 29.576–37.894 seconds |

The artifact contains the same windows in `narrationSegments`, `moves`, and `captions`. A local visual preview showed Move 1 and Move 2 changing together, with the caption above the board and the MoveCard above the caption.

Future English videos will therefore say the move they show, display only the active spoken sentence, move the board at the same audio-derived time, and hide the caption before the next narration segment begins.
