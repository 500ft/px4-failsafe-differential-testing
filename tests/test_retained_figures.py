"""The retained-result figures show only stored values; their words live in the captions.

These checks need matplotlib, which CI does not install; they skip there and
run wherever the figures can be generated.
"""
import csv
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/figures'
HAS_MPL = importlib.util.find_spec('matplotlib') is not None
squash = lambda s: ' '.join(s.split())


@unittest.skipUnless(HAS_MPL, 'matplotlib is not installed')
class RetainedFigureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / 'scripts'))
        import matplotlib.pyplot as plt
        import figure_style
        import plot_retained_results as plot
        cls.plt, cls.style, cls.plot = plt, figure_style, plot
        cls.domain, cls.runtime = plot.load()
        cls.figures = {'component-agreement': plot.component_figure(cls.domain),
                       'datalink-observations': plot.datalink_figure(cls.runtime)}
        cls.captions = {'component-agreement': plot.component_caption(cls.domain),
                        'datalink-observations': plot.datalink_caption(cls.runtime)}

    @classmethod
    def tearDownClass(cls):
        for fig in cls.figures.values():
            cls.plt.close(fig)
        sys.path.remove(str(ROOT / 'scripts'))

    def test_bars_carry_committed_counts(self):
        with (OUT / 'component-agreement.csv').open() as f:
            rows = list(csv.DictReader(f))
        cohorts = list(dict.fromkeys(r['cohort'] for r in rows))
        for ax, cohort in zip(self.figures['component-agreement'].axes, cohorts):
            expected = [r for r in rows if r['cohort'] == cohort]
            bars = ax.patches
            self.assertEqual(len(bars), 2 * len(expected))
            for y, row in enumerate(expected):
                agree, disagree = bars[2 * y], bars[2 * y + 1]
                self.assertEqual((agree.get_x(), agree.get_width()), (0, int(row['agree'])))
                self.assertEqual((disagree.get_x(), disagree.get_width()),
                                 (int(row['agree']), int(row['disagree'])))
                self.assertEqual(agree.get_facecolor(), (0, 0, 0, 1))
                self.assertEqual(disagree.get_facecolor(), (1, 1, 1, 1))
            self.assertEqual([t.get_text() for t in ax.get_yticklabels()], [r['phase'] for r in expected])

    def test_markers_carry_committed_stamps(self):
        with (OUT / 'datalink-observations.csv').open() as f:
            rows = list(csv.DictReader(f))
        ax = self.figures['datalink-observations'].axes[0]
        markers = [line for line in ax.lines if len(line.get_xdata()) == 1]
        self.assertEqual(len(markers), len(rows))
        for y, (line, row) in enumerate(zip(markers, rows)):
            self.assertEqual(line.get_xdata()[0], int(row['since_last_receive_us']) / 1e6)
            self.assertEqual(line.get_ydata()[0], y)
            self.assertEqual(line.get_marker(), 's' if 'bracket' in row['observation'] else 'o')
        self.assertEqual([t.get_text() for t in ax.get_yticklabels()],
                         [self.plot.tick_label(r['stage']) for r in rows])

    def test_canvas_holds_only_axes_text_panel_letters_and_legend(self):
        from matplotlib.text import Text
        for name, fig in self.figures.items():
            printed = {t.get_text() for t in fig.findobj(Text) if t.get_visible() and t.get_text().strip()}
            allowed = {f'({c})' for c in self.plot.LETTERS}
            allowed |= {ax.get_xlabel() for ax in fig.axes}
            legends = list(fig.legends) + [ax.get_legend() for ax in fig.axes if ax.get_legend()]
            allowed |= {t.get_text() for legend in legends for t in legend.get_texts()}
            allowed |= {t.get_text() for ax in fig.axes for t in ax.get_xticklabels() + ax.get_yticklabels()}
            self.assertLessEqual(printed, allowed, name)
            self.assertEqual(len(legends), 1, name)

    def test_nothing_printed_touches_anything(self):
        for name, fig in self.figures.items():
            self.assertEqual(self.style.audit(fig), [], name)

    def test_captions_match_files_and_docs(self):
        docs = {'component-agreement': ['README.md', 'results/README.md'],
                'datalink-observations': ['results/README.md']}
        for stem, text in self.captions.items():
            self.assertEqual(text, (OUT / f'{stem}.caption.md').read_text().strip())
            for doc in docs[stem]:
                body = (ROOT / doc).read_text()
                self.assertIn(squash(text), squash(body), doc)
                self.assertIn(f'figures/{stem}.caption.md', body, doc)
        self.assertIn('25 of 36 agreed and 11 disagreed', self.captions['component-agreement'])
        self.assertIn('Navigator RTL execution, 17.284 s', self.captions['datalink-observations'])

    def test_manifest_records_committed_outputs(self):
        manifest = json.loads((OUT / 'manifest.json').read_text())
        for name, sha in manifest['outputs'].items():
            self.assertEqual(self.plot.digest(OUT / name), sha, name)
        self.assertEqual(self.plot.digest(ROOT / 'scripts/figure_style.py'), manifest['style_sha256'])


if __name__ == '__main__':
    unittest.main()
