# Xiangqi Visual Reference Research

**Date:** 2026-08-14

## User-supplied video references

1. https://www.youtube.com/watch?v=nApZihrdQGo
2. https://www.youtube.com/watch?v=vklqOLf6mtU

The browser player was blocked by an automated-traffic interstitial, so both public videos were analyzed with the local video-analysis utility. The analysis is visual reference data, not a substitute for formal rules verification.

### Video 1: nApZihrdQGo

The analyzed frames show a real Xiangqi board with pieces placed on line intersections, not in square centers. The board has nine vertical lines and ten horizontal lines. The river is a broad horizontal empty band in the center; the inner vertical grid lines stop at the river edges while the outside frame remains continuous. Each side has a 3x3 palace in the central rear area with two diagonal lines forming an X. The initial back rank is chariot, horse, elephant, advisor, general, advisor, elephant, horse, chariot. Two cannons are placed on the third rank in front of the horses, and five soldiers are placed on the fourth rank at alternating files. The analyzed set uses dark wood with light/golden lines and round colored discs.

### Video 2: vklqOLf6mtU

The analyzed frames confirm the same intersection-based 9x10 point grid and a visible river between the fifth and sixth ranks. The eight inner vertical lines are interrupted at the river while the outside border lines continue. Each palace covers three files by three ranks and has crossed diagonals. The initial cannon points are the second and eighth files; soldier points are the first, third, fifth, seventh, and ninth files. The pieces are flat circular discs, with red and black armies. Traditional Chinese glyph pairs are visually important: red general 帥 versus black general 將; red advisor 仕 versus black advisor 士; red elephant 相 versus black elephant 象; red soldier 兵 versus black soldier 卒. The board is mirror-symmetric around the central file.

## Independent web references to verify next

- Xiangqi.com board and setup guide: https://www.xiangqi.com/help/board-and-set-up
- Yellow Mountain Imports rules guide: https://www.ymimports.com/pages/how-to-play-xiangqi-chinese-chess
- Wikipedia overview: https://en.wikipedia.org/wiki/Xiangqi

## Non-negotiable visual acceptance facts

The production renderer must use a 9x10 intersection grid, not a Western chess 8x8 square grid. The river must be visible as a central horizontal gap or clearly labeled band, with inner vertical lines not drawn continuously through it. The two palaces must be visible with crossed diagonals. Pieces must be centered on intersections. Initial setup must place 32 pieces at the standard points and use red/black glyph variants where applicable. A generated decorative image is not an acceptable substitute for this deterministic board geometry.

## Current incident to investigate

The user reports that generated scene images appeared in the ChatGPT image-generation history but were not visible in the final videos. The next phase must trace whether the assets were rejected by validation, stored outside the Remotion asset path, omitted from the job storyboard, or never referenced by the React composition. The final system must record an asset-to-scene mapping and fail the non-publishing visual acceptance test if an approved asset is not present in the rendered frame.

## Verified independent source findings

### Xiangqi.com

The [Xiangqi.com board and setup guide](https://www.xiangqi.com/help/board-and-set-up) states that the board has nine vertical lines and ten horizontal lines, that all pieces sit on intersections rather than inside squares, that each side has a palace shaped like an X in a box, and that a river divides the two sides in the middle. It places the general at the center of the back rank, chariots at the edges, horses next to chariots, elephants next to horses, advisors between elephants and the general, cannons on the rank aligned with the top of the palace and on the second outermost files, and soldiers on every other intersection. It also states that generals cannot face each other.

### Yellow Mountain Imports

The [Yellow Mountain Imports Xiangqi guide](https://www.ymimports.com/pages/how-to-play-xiangqi-chinese-chess) independently confirms the 9x10 intersection board. It describes each palace as 3 by 3 points with diagonal lines forming an X, places the river between the fifth and sixth ranks, and notes that the river is often marked with 楚河 (Chu River) and 漢界 (Han Border). It confirms the standard arrangement, the red/black glyph variants, and the movement restrictions that depend on the river and palace. Its displayed board reference visibly shows a physical wooden board with a distinct river band and pieces centered on intersections.

These two independent guides agree with both supplied-video analyses. The existing renderer must therefore be treated as visually wrong if it presents a continuous 9x10 square grid without an unmistakable river gap/band, omits the palace X diagonals, places discs in square centers, or uses an abstract/generated board that does not preserve these geometrical landmarks.

### Wikipedia cross-check

The [Wikipedia Xiangqi article](https://en.wikipedia.org/wiki/Xiangqi) independently describes a board nine lines wide and ten lines long, with pieces placed on intersections called points. It locates the two palaces at ranks 1–3 and 8–10, each three points by three points with two crossing diagonals. It places the river between the fifth and sixth ranks and notes that it is usually marked with 楚河 and 漢界. It also notes that soldier starting points and cannon starting points are usually, but not always, marked with small crosses. This supports using a configurable but unmistakable river band and palace X markings rather than a continuous square grid.

## Local reference assets selected

The project now contains two local reference assets under `assets/xiangqi_reference/`:

- `physical_board_reference.jpeg`: a photographed wooden Xiangqi board with circular pieces centered on intersections, a clearly separated river band, visible palace diagonals, and the standard initial arrangement.
- `ymimports_setup_reference.gif`: a setup diagram from Yellow Mountain Imports showing the 9x10 line geometry, palace X diagonals, the river gap, and standard piece positions.

The physical photo is suitable as a visual reference for material, disc scale, glyph placement, and river appearance. The diagram is suitable as a geometry reference. Neither should be published as a channel asset without confirming usage rights; the production board should be recreated deterministically from the verified geometry or used only under an appropriate license.

## ChatGPT image URLs supplied by the user

Both supplied `chatgpt.com/backend-api/estuary/content` links were tested. The first returned an access-denied/captcha response, and the second returned `Invalid signature or expired URL`. The images therefore cannot currently be inspected or reliably referenced by the build. This also explains why an image visible in a ChatGPT generation history may not appear in a GitHub Actions video: a signed session URL is not a durable project asset, and the production job may have no readable local copy or stable manifest entry.

The corrected asset pipeline must require a durable local/project path, a content hash, dimensions, scene ID, and an explicit inclusion record before a generated image can be considered part of a render. A ChatGPT history item alone is not evidence that the asset was downloaded, validated, copied into the job output, or referenced by the Remotion composition.

## Current renderer diagnosis

The current `src/Composition.tsx` confirms two structural defects. The base `Board` draws all nine vertical lines continuously across all ten ranks, so the river is not a real visual gap. Its palace diagonals are drawn from columns 0–2 at the top and bottom, while the actual palaces must occupy the central columns 3–5. Some later overlays use central palace coordinates, so the base board and overlays disagree.

The current `GeneratedVisualAsset` component is intentionally an ephemeral backdrop: it appears only when the active narration segment has a matching `sceneId` and the storyboard scene has a `generatedAsset.src`, fades in and out within that segment, and sits underneath deterministic board/overlay layers. The current production artifact for the corrected en-010 job recorded `visualAssets.assets=[]` with `reason=ai_planner_selected_no_asset`, so the images observed in a separate ChatGPT history were not part of that video. The asset service writes files correctly when selected, but the planner may select none, the scene may be ineligible, or the output may be too transient to be perceived. The fix must make asset presence, scene mapping, and frame visibility explicit acceptance criteria.

## Corrected acceptance frame

A non-publishing Remotion still rendered after the geometry patch. Visual inspection confirms that the two palace X marks are centered in files 4–6, the river is a distinct horizontal band between the fifth and sixth ranks with the inner vertical lines interrupted, and the 32 pieces are centered on the 9x10 intersections in standard setup. The Chinese river labels are visible as 楚河 and 漢界. The board now matches the physical and diagram references materially better than the previous continuous-grid/left-palace renderer.

The render emitted a warning that installed Remotion packages are split between 4.0.508 and 4.0.509. This must be pinned to one version before the final CI acceptance render, even though the local still completed successfully.

## Pinned Remotion acceptance render

After pinning `remotion`, `@remotion/cli`, and `@remotion/media-utils` to `4.0.509` and installing the matching Chrome Headless Shell, the corrected acceptance still rendered successfully at 1080x1920. Visual inspection shows the same correct river gap, central palaces, intersection placement, standard pieces, and river labels. The earlier 4.0.508/4.0.509 warning is resolved in the clean install path.

## Thumbnail acceptance

The thumbnail policy now produces only `thumbnail_en.jpg` at 1280x720 and below the 2MB limit. Visual inspection confirms that the clean board card uses the corrected 9x10 board with the visible river and centered palaces. The English file is the sole default YouTube thumbnail and is uploaded automatically through the YouTube Data API; no `thumbnail_zh.jpg` is generated or required.

## GitHub Actions acceptance artifact

Run `31769123910` succeeded on commit `1c3420a`. Its downloaded `clean-board.png` is 1080x1920 and visually matches the local acceptance frame: standard 32-piece placement on intersections, central palace diagonals, and a full-width river band separating the armies. The smoke workflow produces and validates the single 1280x720 English thumbnail. The artifact contains `no-publish.txt`, confirming that this run performs no YouTube mutation.

## Public YouTube proof

The successful production run uploaded `D-o77HngwOU`. A public YouTube navigation to `https://www.youtube.com/watch?v=D-o77HngwOU` returned the title `What Is Xiangqi?`, channel `Xiangqi Lab | 中国象棋实验室`, the English description, and public watch-page metadata. The sandbox player itself showed YouTube's sign-in/anti-bot interstitial, so visual frame verification remains based on the downloaded GitHub artifact rather than assuming the browser player rendered.

### Artifact visual inspection — production proof 31769865009

The downloaded `prepublish_thumbnails/clean_board.png` is 1080x1920 and visibly shows all pieces centered on grid intersections, a full-width river gap between the fifth and sixth ranks, and palace X diagonals in the central three files for both sides. The clean-board frame is the source for the validated 1280x720 English and Chinese thumbnails; explanatory labels/highlights are layered by the video scenes rather than baked into this clean source frame.
