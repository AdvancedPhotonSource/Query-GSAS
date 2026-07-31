"""
Recall@k grouped bar chart for Query-GSAS manuscript.
Outputs: fig_recall.svg (Inkscape-editable), fig_recall.png (300 dpi)
"""
import matplotlib
matplotlib.rcParams['svg.fonttype'] = 'none'
import matplotlib.pyplot as plt
import numpy as np
import os

ARGBLUE  = '#1a4f8a'
APORANGE = '#e87722'
OUT_DIR  = os.path.dirname(os.path.abspath(__file__))

categories = ['All\n(n=40)', 'Rietveld\n(n=10)', 'Sequential\n(n=8)',
              'Structure\n(n=6)', 'Calibration\n(n=6)', 'Scripting\n(n=5)',
              'Export\n(n=5)']

recall1 = [0.50, 0.40, 0.38, 0.33, 1.00, 0.40, 0.60]
recall3 = [0.83, 0.70, 0.75, 1.00, 1.00, 0.80, 0.80]
recall6 = [0.98, 1.00, 1.00, 1.00, 1.00, 0.80, 1.00]

x = np.arange(len(categories))
w = 0.25

fig, ax = plt.subplots(figsize=(10, 5.2))

b1 = ax.bar(x - w, recall1, width=w, label='Recall@1',
            facecolor=ARGBLUE, alpha=0.45, edgecolor='#111111', linewidth=1.1)
b3 = ax.bar(x,     recall3, width=w, label='Recall@3',
            facecolor=ARGBLUE, alpha=0.70, edgecolor='#111111', linewidth=1.1)
b6 = ax.bar(x + w, recall6, width=w, label='Recall@6',
            facecolor=APORANGE, alpha=0.85, edgecolor='#111111', linewidth=1.1)

ax.set_ylabel('Recall@$k$', fontsize=11)
ax.set_ylim(0, 1.13)
ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
ax.set_xticks(x)
ax.set_xticklabels(categories, fontsize=9.5)
ax.set_title('Retrieval performance by query category — bge-base-en-v1.5, 40-question evaluation set',
             fontsize=10, pad=10)
ax.axhline(1.0, color='#888888', linewidth=0.8, linestyle='--')

ax.legend(fontsize=10, loc='lower left')

# Grid
ax.yaxis.grid(True, linestyle='--', alpha=0.4, color='#444444')
ax.set_axisbelow(True)

# Dark-bordered spines
for spine in ax.spines.values():
    spine.set_linewidth(1.4)
    spine.set_edgecolor('#111111')
ax.tick_params(axis='both', which='both', length=4, color='#111111')

plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, 'fig_recall.svg'), format='svg', dpi=150,
            bbox_inches='tight')
plt.savefig(os.path.join(OUT_DIR, 'fig_recall.png'), format='png', dpi=300,
            bbox_inches='tight')
plt.close()
print('Saved fig_recall.svg and fig_recall.png')
