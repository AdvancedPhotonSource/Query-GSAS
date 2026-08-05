"""
RAG pipeline architecture diagram for Query-GSAS manuscript.
Two-column layout: Ingestion (left, blue) | Query (right, orange).
Outputs: fig_architecture.svg (Inkscape-editable), fig_architecture.png (300 dpi)
"""
import matplotlib
matplotlib.rcParams['svg.fonttype'] = 'none'
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import os

ARGBLUE  = '#1a4f8a'
APORANGE = '#e87722'
GRAY     = '#555555'
BG_BLUE  = '#dce8f5'
BG_ORA   = '#fde8d0'
BG_GRAY  = '#e8e8e8'
OUT_DIR  = os.path.dirname(os.path.abspath(__file__))

fig, ax = plt.subplots(figsize=(11, 7))
ax.set_xlim(0, 11)
ax.set_ylim(0, 7)
ax.axis('off')

# ─── helper ───────────────────────────────────────────────────────────────────
def box(ax, x, y, w, h, label, sub=None, fc=BG_BLUE, ec=ARGBLUE, lw=1.8):
    rect = FancyBboxPatch((x - w/2, y - h/2), w, h,
                          boxstyle='round,pad=0.08',
                          facecolor=fc, edgecolor=ec, linewidth=lw)
    ax.add_patch(rect)
    yt = y + 0.10 if sub else y
    ax.text(x, yt, label, ha='center', va='center',
            fontsize=10, fontfamily='sans-serif', fontweight='bold', color='#111111')
    if sub:
        ax.text(x, y - 0.22, sub, ha='center', va='center',
                fontsize=8.5, fontfamily='monospace', color='#444444')

def arrow(ax, x1, y1, x2, y2, color=ARGBLUE):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=color, lw=2.0,
                                connectionstyle='arc3,rad=0.0'))

# ─── Column headers ───────────────────────────────────────────────────────────
ax.text(2.75, 6.65, 'Ingestion  (one-time)', ha='center', va='center',
        fontsize=11, style='italic', color=ARGBLUE)
ax.text(8.25, 6.65, 'Query  (real-time)', ha='center', va='center',
        fontsize=11, style='italic', color=APORANGE)

# ─── Ingestion column (left) ──────────────────────────────────────────────────
bw, bh = 3.2, 0.80
lx = 2.75
ys = [6.10, 5.05, 4.00, 2.95, 1.75]

box(ax, lx, ys[0], bw, bh, 'GSAS-II Docs',
    sub='152 HTML sources  +  179 book pages (opt.)',
    fc=BG_BLUE, ec=ARGBLUE)
box(ax, lx, ys[1], bw, bh, 'Fetch & Parse',
    sub='requests  +  BeautifulSoup4',
    fc=BG_BLUE, ec=ARGBLUE)
box(ax, lx, ys[2], bw, bh, 'Chunk',
    sub='≤ 1200 chars, sentence-boundary',
    fc=BG_BLUE, ec=ARGBLUE)
box(ax, lx, ys[3], bw, bh, 'Embed',
    sub='bge-base-en-v1.5  (ONNX)',
    fc=BG_BLUE, ec=ARGBLUE)
box(ax, lx, ys[4], bw + 0.4, bh + 0.15, 'ChromaDB  (5,838 vectors)',
    sub='~/.GSASII/gsas_query/chroma_db',
    fc=BG_GRAY, ec=GRAY)

for i in range(len(ys) - 1):
    arrow(ax, lx, ys[i] - bh/2, lx, ys[i+1] + bh/2, color=ARGBLUE)

# ─── Query column (right) ─────────────────────────────────────────────────────
rx = 8.25
ys_r = [6.10, 5.05, 4.00, 2.95, 1.80]

box(ax, rx, ys_r[0], bw, bh, 'User Question',
    fc=BG_ORA, ec=APORANGE)
box(ax, rx, ys_r[1], bw, bh, 'Embed Query',
    sub='bge-base-en-v1.5  (ONNX)',
    fc=BG_ORA, ec=APORANGE)
box(ax, rx, ys_r[2], bw, bh, 'Retrieve top-6',
    sub='cosine sim + URL dedup (top-30 over-fetch)',
    fc=BG_ORA, ec=APORANGE)
box(ax, rx, ys_r[3], bw, bh, 'LLM Generation',
    sub='Ollama / llama-cpp-python / Anthropic',
    fc=BG_ORA, ec=APORANGE)
box(ax, rx, ys_r[4], bw + 0.4, bh + 0.10, 'Cited Answer',
    sub='inline [1]–[6]  +  journal bibliography',
    fc=BG_ORA, ec=APORANGE)

for i in range(len(ys_r) - 1):
    arrow(ax, rx, ys_r[i] - bh/2, rx, ys_r[i+1] + bh/2, color=APORANGE)

# ─── Cross arrow: ChromaDB → Retrieve ─────────────────────────────────────────
db_x = lx + (bw + 0.4)/2
ret_x = rx - bw/2
db_y = ys[4]
ret_y = ys_r[2]
ax.annotate('', xy=(ret_x, ret_y), xytext=(db_x, db_y),
            arrowprops=dict(arrowstyle='->', color=GRAY, lw=1.8,
                            linestyle='dashed',
                            connectionstyle='arc3,rad=-0.35'))

plt.tight_layout(pad=0.3)
plt.savefig(os.path.join(OUT_DIR, 'fig_architecture.svg'), format='svg', dpi=150,
            bbox_inches='tight')
plt.savefig(os.path.join(OUT_DIR, 'fig_architecture.png'), format='png', dpi=300,
            bbox_inches='tight')
plt.close()
print('Saved fig_architecture.svg and fig_architecture.png')
