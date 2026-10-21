"""The Edwisely look shared by every figure module: palette, fonts, saving, legends, and the record of labels that still
collide in the figure being drawn (read by figures.render)."""
import os, tempfile
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, 'assets', 'fonts')
PURPLE, LAV, YEL, INK, GREY, LINE = '#4D2A87', '#F0EBFA', '#FFE100', '#1F1A2E', '#6B6480', '#D9D0EE'
# series palette sampled from the reference PDF: purple, mid-purple, gold, teal, then extras
PALETTE = ['#4D2A87', '#7B5CB8', '#D9A400', '#2E8B87', '#B5487A', '#5A7FBF', '#8C6D1F', '#3F7F4F']
ACCENTS = {'purple': PURPLE, 'lav': LAV, 'yellow': YEL, 'accent': YEL, 'gold': '#D9A400', 'teal': '#2E8B87',
           'mid': '#7B5CB8', 'red': '#C0392B', 'green': '#3F7F4F', 'grey': '#BDB6CC', 'white': '#FFFFFF'}
DPI = 300
CACHE = os.path.join(tempfile.gettempdir(), 'topicpdf_fig')


def col(c, default=PURPLE):
    if c is None: return default
    return ACCENTS.get(c, c)


_branded = False


def brand():
    """Apply Edwisely matplotlib style (Poppins labels, DejaVu for maths-friendly text)."""
    global _branded
    if _branded: return
    for f in os.listdir(FONTS):
        if f.endswith('.ttf'): font_manager.fontManager.addfont(os.path.join(FONTS, f))
    plt.rcParams.update({
        'font.family': ['Poppins', 'DejaVu Sans'], 'font.size': 9, 'mathtext.fontset': 'dejavusans',
        'axes.edgecolor': GREY, 'axes.labelcolor': INK, 'axes.titlecolor': PURPLE, 'axes.titleweight': 'bold',
        'axes.titlesize': 10, 'axes.titlelocation': 'left', 'xtick.color': INK, 'ytick.color': INK,
        'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': False, 'grid.color': LINE,
        'axes.prop_cycle': matplotlib.cycler(color=PALETTE), 'legend.frameon': False, 'savefig.dpi': DPI,
        'axes.unicode_minus': True})
    _branded = True


def save(fig, path):
    fig.savefig(path, dpi=DPI, bbox_inches='tight', pad_inches=0.06, transparent=True)  # blends into lavender boxes
    plt.close(fig)
    return path


def _fmt(v):
    if not isinstance(v, (int, float)): return str(v)
    return f'{v:,.0f}' if 1e5 <= abs(v) < 1e15 else f'{v:g}'      # 12,345,679 rather than 1.23457e+07


def _size(spec):
    """The figure size asked for, kept between a stamp and a page (a huge figure would be shrunk until its text is unreadable)."""
    w, h = spec.get('size') or (6.4, 3.0)
    return min(max(float(w), 1.5), 7.5), min(max(float(h), 1.0), 5.0)


ISSUES = []         # labels that still collide after placement, one count per axes of the figure being drawn


def legend(ax, n, inside=False):
    """Above the plot, right-aligned, in one or two rows: clear of the curves, bars and tick labels.
    Returns its height in points, so a title can sit above it. inside: right of the plot, for stacked panels (the band
    above belongs to the panel above, and a dense waveform leaves no free corner)."""
    if not ax.get_legend_handles_labels()[0]: return 0
    if inside:
        ax.legend(fontsize=7.5, loc='center left', bbox_to_anchor=(1.01, 0.5), frameon=False, handlelength=1.6)
        return 0
    leg = ax.legend(fontsize=8, loc='lower right', bbox_to_anchor=(1, 1.01), ncol=min(max(n, 1), 4), frameon=False, borderaxespad=0,
                    handlelength=1.6, columnspacing=1.2)
    return leg.get_window_extent(ax.figure.canvas.get_renderer()).height * 72 / ax.figure.dpi + 4
