"""
Source-count horizontal bar chart for Query-GSAS manuscript.
Outputs: fig_sources.svg (Inkscape-editable), fig_sources.png (300 dpi)
"""
import matplotlib
matplotlib.rcParams['svg.fonttype'] = 'none'   # editable text in Inkscape
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os

ARGBLUE   = '#1a4f8a'
APORANGE  = '#e87722'
OUT_DIR   = os.path.dirname(os.path.abspath(__file__))

# ── Data (sources counts, not chunks) ────────────────────────────────────────
labels   = ['Tutorials\n(dynamic)', 'Help manual', 'Home / Install / Dev',
            "Programmer's Guide\n(ReadTheDocs)", 'Powder Cryst.\nBook (opt.)']
counts   = [65, 42, 22, 23, 179]
colors   = [ARGBLUE, ARGBLUE, ARGBLUE, ARGBLUE, APORANGE]
alphas   = [0.85, 0.65, 0.50, 0.70, 0.80]

fig, ax = plt.subplots(figsize=(8, 4.2))

y = np.arange(len(labels))
bars = ax.barh(y, counts, height=0.55, color=colors,
               edgecolor='#111111', linewidth=1.2)

# Value labels
for bar, val in zip(bars, counts):
    ax.text(bar.get_width() + 2.5, bar.get_y() + bar.get_height() / 2,
            str(val), va='center', ha='left', fontsize=10, fontfamily='sans-serif')

ax.set_yticks(y)
ax.set_yticklabels(labels, fontsize=10)
ax.set_xlabel('Number of HTML pages / sources', fontsize=10)
ax.set_xlim(0, 210)
ax.set_title('Documentation sources indexed by Query-GSAS', fontsize=11, pad=10)

# Legend
patch_req = mpatches.Patch(facecolor=ARGBLUE, edgecolor='#111111', linewidth=1.2,
                            label='Default (indexed automatically)')
patch_opt = mpatches.Patch(facecolor=APORANGE, edgecolor='#111111', linewidth=1.2,
                            label='Optional (--book flag)')
ax.legend(handles=[patch_req, patch_opt], fontsize=9, loc='lower right')

# Dark-bordered spines
for spine in ax.spines.values():
    spine.set_linewidth(1.4)
    spine.set_edgecolor('#111111')
ax.tick_params(axis='both', which='both', length=4, color='#111111', labelsize=9)

plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, 'fig_sources.svg'), format='svg', dpi=150,
            bbox_inches='tight')
plt.savefig(os.path.join(OUT_DIR, 'fig_sources.png'), format='png', dpi=300,
            bbox_inches='tight')
plt.close()
print('Saved fig_sources.svg and fig_sources.png')