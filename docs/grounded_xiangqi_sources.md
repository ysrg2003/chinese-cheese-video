# Grounded Xiangqi Sources

This file records the external references used by the autonomous director and claim verifier. Source retrieval is evidence only; deterministic board-state calculations remain authoritative for move legality and causal claims.

## Source hierarchy

### 1. World Xiangqi Federation — World Xiangqi Rules

URL: https://www.wxf-xiangqi.org/index.php?option=com_content&view=article&id=269&Itemid=291&lang=en

The World Xiangqi Federation describes the World Xiangqi Rules as a unified international rules publication based on the Asian Xiangqi Federation rules. The page links the English rules PDF:
https://www.wxf-xiangqi.org/images/wxf-rules/2018_World_XiangQi_Rules_English2018.pdf

Use: primary rules provenance and terminology authority. The PDF is the preferred source for future rule-specific retrieval when available.

### 2. Xiangqi.com — Learning the Xiangqi Pieces and Moves

URL: https://www.xiangqi.com/help/pieces-and-moves

Retrieved facts:

- Xiangqi has seven piece families: General, Chariot, Horse, Cannon, Soldier, Advisor, and Elephant.
- Pieces stand on board intersections rather than inside squares.
- A Horse moves one orthogonal point and then one diagonal point; an intervening piece blocks that direction. The source calls this blocking the Horse's leg.
- A Cannon moves along ranks/files and captures by jumping over exactly one intervening piece, the screen or mount, to land on an opposing piece.
- An Elephant moves two points diagonally, cannot move through a blocking piece, and cannot cross the river.
- An Advisor moves one point diagonally and remains inside the palace.
- A General moves one point orthogonally and remains inside the palace; the two Generals cannot face one another on an empty file.
- Soldiers move forward before crossing the river and gain sideways movement after crossing it.
- The palace is a 3x3 zone containing nine points.

### 3. Chess.com — How To Play Chinese Chess (Xiangqi)

URL: https://www.chess.com/blog/SamCopeland/how-to-play-chinese-chess

Retrieved facts:

- Xiangqi pieces are placed on intersections, not inside squares.
- The board is divided by a river; the river affects piece restrictions and soldier mobility.
- Cannons capture only after jumping over one piece, commonly called a gun mount or screen.
- Horses move one orthogonal point and one diagonal point and cannot jump; an intervening piece blocks the horse in that direction.
- Elephants move two diagonal points, cannot cross the river, and are blocked by a piece in their path.
- Advisors move diagonally within the palace.
- Generals move orthogonally within the palace and may not face one another directly.

## Operational grounding contract

1. Research must be retrieved and saved before AI script generation for any lesson whose claims depend on rules, history, terminology, or current external facts.
2. The AI director receives source URLs, retrieved excerpts, retrieval timestamp, source hierarchy, and an explicit instruction to distinguish sourced facts from its own proposed teaching language.
3. The director may not invent a rule claim that is absent from the evidence bundle unless the deterministic Xiangqi verifier proves it from the supplied board state.
4. External prose is not treated as proof of a specific position. For claims such as blocked Horse leg, blocked Elephant eye, Cannon screen, Flying General, legal destinations, pressure, or changed attack/defense relationship, the deterministic verifier is authoritative.
5. A stale, missing, contradictory, or failed retrieval produces `research_grounding_failed` and blocks script generation for that lesson. It must not silently fall back to an ungrounded AI script.
6. The final review stores the evidence bundle hash and the claim-proof hash in the job artifact so the published video can be traced to the research and board-state facts used before rendering.

## Known terminology correction

Use **Horse Leg** for the Xiangqi Horse's intervening orthogonal blocking point. Use **Elephant Eye** for the intervening point that blocks an Elephant's two-point diagonal move. Do not use `Horse Eye`, `Blocked Eye`, or `Horse's Eye` as the primary English teaching term for the Horse rule.

## References

[1] World Xiangqi Federation, World Xiangqi Rules: https://www.wxf-xiangqi.org/index.php?option=com_content&view=article&id=269&Itemid=291&lang=en

[2] World Xiangqi Federation, World Xiangqi Rules English PDF: https://www.wxf-xiangqi.org/images/wxf-rules/2018_World_XiangQi_Rules_English2018.pdf

[3] Xiangqi.com, Learning the Xiangqi Pieces and Moves: https://www.xiangqi.com/help/pieces-and-moves

[4] Chess.com, How To Play Chinese Chess (Xiangqi): https://www.chess.com/blog/SamCopeland/how-to-play-chinese-chess

Retrieved during the root-cause grounding work on 2026-08-15 UTC.

> Source text is evidence for research grounding. Deterministic board-state verification remains the final authority for position-specific claims.

Copyright and use note: The system stores URLs, short factual notes, and hashes rather than copying entire source documents into generated videos.


## Versioned fallback cache

The repository also contains `data/grounding_source_cache.json`, populated from the sources above and versioned with the project. For stable Xiangqi rules, a temporary HTTPS failure may use this cache while recording `status: cached` and the live-fetch error in the research bundle. This does not apply to current/trending topics or any topic whose required evidence is absent. Such topics remain fail-closed until live retrieval or required Google Search grounding succeeds.

The cache is not a substitute for board-state proof: Horse Leg, Elephant Eye, Cannon Screen, river restrictions, legal destinations, and flying-general relations are still calculated mechanically from the exact FEN and move trace.
