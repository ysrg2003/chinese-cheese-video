# Xiangqi rules research notes

## Sources consulted

The World Xiangqi Federation (WXF) describes its World Xiangqi Rules as the international unified rules based on the Asian Xiangqi Federation revision and provides the English rules PDF. The official page is https://www.wxf-xiangqi.org/index.php?option=com_content&view=article&id=269&Itemid=291&lang=en.

The Xiangqi.com piece guide and Yellow Mountain Imports rule guide were used as accessible explanatory cross-checks. A 2024 paper, *Complete Implementation of WXF Chinese Chess Rules* (arXiv:2412.17334), was used to distinguish basic legal-move validation from the much more complex WXF repetition/chase adjudication.

## Board and starting position

Xiangqi uses 9 files and 10 ranks, with pieces placed on the 90 intersections rather than inside 9×10 squares. The river lies between the fifth and sixth ranks. Each side's palace is a 3×3 region. A normal setup has 32 pieces per side in mirror formation: one general, two advisors, two elephants, two horses, two chariots, two cannons, and five soldiers.

For the repository's top-origin coordinate system, the validator must explicitly define red's home side, black's home side, the river boundary, and the exact FEN orientation instead of relying on a verbal assumption.

## Piece movement constraints

| Piece | Legal movement constraints to encode |
|---|---|
| General | One point orthogonally; remains inside its own 3×3 palace; cannot move into check; the two generals may not face each other on the same file with no intervening piece. |
| Advisor | One point diagonally; remains inside its own palace. Horizontal and vertical moves are illegal. |
| Elephant | Exactly two points diagonally; the midpoint (“elephant eye”) must be empty; cannot cross the river. |
| Horse | One orthogonal step followed by one diagonal step; the adjacent orthogonal “horse leg” square must be empty. It is not an unrestricted Western-chess knight. |
| Chariot | Any number of open points horizontally or vertically; cannot jump over any piece. |
| Cannon | Any number of open points horizontally or vertically for a quiet move; for a capture it must jump over exactly one intervening piece and land on an opposing piece; a quiet cannon move cannot jump. |
| Soldier | One point forward before crossing the river; after crossing, one point forward or horizontally; never backward; no promotion. |

## Global legality constraints

Players alternate one move at a time. A move must use the piece belonging to the side to move, land inside the board, and either move to an empty destination or capture an opposing piece. It must satisfy the piece-specific geometry and blockers. After applying the move, the moving side's general must not be in check. A move that exposes a general to attack is illegal even if its piece geometry is otherwise valid.

The flying-general constraint is not optional teaching detail: if the two generals occupy the same file with no intervening piece, the position is illegal. A proposed move that removes the only intervening piece, or moves a general into such exposure, must be rejected.

The horse-leg, elephant-eye, palace, river, cannon-screen, capture-side, and side-to-move checks must be tested independently and together. The narration must be generated only after the move has been replayed and accepted, and it must use the actual piece and actual from/to squares from the replayed position.

## Scope boundary

Basic legal-move validation is required for every generated teaching line. Full WXF repetition, perpetual-check, and perpetual-chase adjudication is a separate advanced scope. The arXiv implementation documents that repetition outcomes can be win, loss, or draw depending on the chase/check behavior and that a complete WXF implementation covers 110 example cases. The initial publishing gate should reject illegal plies and unsafe positions; it should not claim to adjudicate every tournament repetition outcome until that module is separately implemented and tested.
