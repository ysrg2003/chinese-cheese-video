# Thumbnail smoke findings

The local smoke test generated English and Simplified Chinese thumbnails from a clean Remotion board frame rather than an arbitrary video frame. Both files are 1280×720 JPEGs under YouTube's 2MB API limit.

The English version keeps `XIANGQI LAB` branding, the complete headline `THE QUIET TRAP / ON THE LEFT WING`, a `CHINESE CHESS` label, and a crisp board focal point. The Chinese version keeps the same board and layout with the exact test headline `中国象棋：三十二个棋子的摆法` and label `中国象棋`. The headline-fit correction prevents clipping at the right edge. Neither version contains the Arabic title/caption that appeared in the earlier frame-extraction prototype.
