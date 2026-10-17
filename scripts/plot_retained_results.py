"""Render committed result summaries only. No model, native runner or raw-log reads.

The canvases show only the stored values. Everything in words is written by
the caption functions to ``<stem>.caption.md`` beside each image and copied
into the result guides under it.
"""
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

import figure_style as style

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/figures'
DOMAIN = ROOT / 'evidence/task-domain-2026-10-03/results.json'
RUNTIME = ROOT / 'evidence/task-observation-qualification-2026-10-04/results.json'
LETTERS = 'abc'
# 183 mm wide, the two-column width used across the sibling repositories.
WIDTH = 7.2
BAR = {'height': .5, 'edgecolor': style.INK, 'lw': .8}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load():
    return json.loads(DOMAIN.read_text()), json.loads(RUNTIME.read_text())


def phases(domain):
    """(cohort, [(phase, record), ...]) per panel; agree + disagree must equal executed."""
    result = [('Directed development', [('Before fixes', domain['before']['directed']['all']),
              ('Replayed', domain['development_replay_after_fixes']['directed']['all'])]),
              ('Random development', [('Before fixes', domain['before']['development']['all']),
              ('Replayed', domain['development_replay_after_fixes']['development']['all'])]),
              ('Fresh reserved corpus', [('After fixes', domain['reserved']['all'])])]
    for _, records in result:
        for _, r in records:
            assert r['agree'] + r['disagree'] == r['executed']
    return result


def events(runtime):
    """Origin and (stage, vehicle HRT us, observation) rows on the instrumented run's clock."""
    run = runtime['runs']['clean-instrumented']
    timing = run['timing']; segments = timing['native_segments']
    origin = segments['last_observed_qualifying_receive']['t']
    # Squares mean equal entry/end stamps; the caption says so, so the data must agree.
    for key in ('first_lost_detector_bracket', 'first_navigator_rtl_execution_bracket'):
        assert segments[key]['t'] == segments[key]['end'], key
    return origin, [
        ('Last qualifying receive', origin, 'receiver marker'),
        ('Last true telemetry publication', segments['publications_matching_detector_anchor'][-1]['t'], 'detector anchor'),
        ('First observed aged-false heartbeat', segments['first_observed_aged_false']['t'], 'aging marker'),
        ('First false telemetry publication', segments['first_false_telemetry_publication']['t'], 'publication marker'),
        ('GCS-loss detector', segments['first_lost_detector_bracket']['t'], 'entry/end bracket'),
        ('Consumed GCS-loss input', run['native']['first_consumed_armed_gcs_loss_us'], 'class update marker'),
        ('Selected Hold', segments['first_selected_hold']['t'], 'selector marker'),
        ('Selected RTL', segments['first_selected_rtl']['t'], 'selector marker'),
        ('Committed RTL nav_state', timing['rtl_mode_change']['commit_us'], 'ULog nav_state_timestamp'),
        ('Navigator RTL execution', segments['first_navigator_rtl_execution_bracket']['t'], 'entry/end bracket')]


def tick_label(name):
    # cmr10 has no underscore glyph; mathtext draws a real one.
    return name.replace('_', r'$\_$')


def bracket(kind):
    return 'bracket' in kind


def component_caption(domain):
    p = {cohort: dict(records) for cohort, records in phases(domain)}
    rows = [r for records in p.values() for r in records.values()]
    probe = domain['admission_probes']
    assert probe['executed'] == 0 == probe['invalid'] and probe['excluded'] == probe['attempted']
    def count(r):
        text = f"{r['agree']:,} of {r['executed']:,} agreed"
        return text + (f" and {r['disagree']:,} disagreed" if r['disagree'] else '')
    return (
        'Sequence-level agreement between the Python model and the native PX4 failsafe '
        'class. Panels: (a) directed development, (b) random development, (c) fresh '
        'reserved corpus; each panel has its own count axis. A filled bar counts '
        'sequences on which the two agree; a hollow bar counts disagreements. Before the '
        f"fixes: directed, {count(p['Directed development']['Before fixes'])}; random, "
        f"{count(p['Random development']['Before fixes'])}. Replayed after the fixes: "
        f"directed, {count(p['Directed development']['Replayed'])}; random, "
        f"{count(p['Random development']['Replayed'])}. Fresh reserved corpus after the "
        f"fixes: {count(p['Fresh reserved corpus']['After fixes'])}. Unit: one complete sequence. "
        'Development replays reuse inputs; the fresh corpus is separate from Study A '
        f"confirmation. The generated cohorts had {sum(r['invalid'] for r in rows)} invalid "
        f"and {sum(r['excluded'] for r in rows)} excluded sequences; {probe['excluded']} "
        'separate unsupported-input probes were rejected before either adapter. Corpus '
        'agreement only: RC loss, mode switching, pilot takeover and integrated behavior '
        'are excluded. Source: evidence/task-domain-2026-10-03/results.json. Values: '
        'tables.md and component-agreement.csv.')


def component_figure(domain):
    style.apply()
    fig, axes = plt.subplots(1, 3, figsize=(WIDTH, 2.2))
    fig.subplots_adjust(left=.105, right=.975, bottom=.2, top=.76, wspace=.62)
    for i, (ax, (_, records)) in enumerate(zip(axes, phases(domain))):
        for y, (_, r) in enumerate(records):
            ax.barh(y, r['agree'], facecolor=style.FILL[True], **BAR)
            ax.barh(y, r['disagree'], left=r['agree'], facecolor=style.FILL[False], **BAR)
        n = max(r['executed'] for _, r in records)
        ax.set(xlim=(0, n), ylim=(1.7, -.7), yticks=range(len(records)),
               yticklabels=[x for x, _ in records], xlabel='Executed sequences [count]')
        ax.set_xticks([0, n / 2, n], labels=[f'{x:,.0f}' for x in [0, n / 2, n]])
        ax.tick_params(axis='x', length=3)
        ax.tick_params(axis='y', length=0)
        ax.text(0, 1.06, f'({LETTERS[i]})', transform=ax.transAxes, ha='left', va='bottom',
                size=style.LETTER_SIZE)
    handles = [Patch(facecolor=style.FILL[True], edgecolor=style.INK, lw=.8, label='Agree'),
               Patch(facecolor=style.FILL[False], edgecolor=style.INK, lw=.8, label='Disagree')]
    fig.legend(handles=handles, loc='upper center', bbox_to_anchor=(.5, .995), ncol=2,
               columnspacing=1.4, handletextpad=.5, borderaxespad=0)
    return fig


def datalink_caption(runtime):
    origin, rows = events(runtime)
    brackets = [name for name, _, kind in rows if bracket(kind)]
    elapsed = '; '.join(f'{name}, {(t - origin) / 1e6:.3f} s' for name, t, _ in rows[1:])
    return (
        'Datalink stages from one instrumented SIH development run, on one vehicle HRT '
        'clock. Each row is one stage; the axis is time since the last observed '
        'qualifying heartbeat receive. Circles mark recorded stamps; squares mark the '
        f'{brackets[0]} and {brackets[1]} brackets, whose entry and end stamps are '
        f'equal. Time after the last qualifying receive: {elapsed}. The host cut has no '
        'upper bound and is omitted from the axis. Lockstep quantization does not '
        'measure host execution time. Navigator execution is not actuator response. '
        'Timing is descriptive and outside pass/fail. Source: '
        'evidence/task-observation-qualification-2026-10-04/results.json. Exact '
        'microseconds: datalink-observations.csv.')


def datalink_figure(runtime):
    origin, rows = events(runtime)
    style.apply()
    fig, ax = plt.subplots(figsize=(WIDTH, 3.0))
    fig.subplots_adjust(left=.27, right=.97, top=.97, bottom=.15)
    ax.axvline(0, color=style.INK, lw=.6)
    for i, (_, t, kind) in enumerate(rows):
        seconds = (t - origin) / 1e6
        ax.plot([0, seconds], [i, i], color=style.INK, lw=.5, ls=(0, (1, 2)))
        ax.plot(seconds, i, marker='s' if bracket(kind) else 'o', mfc=style.FILL[True], **style.MARKER)
    ax.set(yticks=range(len(rows)), yticklabels=[tick_label(name) for name, _, _ in rows],
           ylim=(len(rows) - .5, -.5), xlim=(-.4, 18), xticks=[0, 5, 10, 15],
           xlabel='Time since last observed qualifying receive [s]')
    ax.tick_params(axis='y', length=0, pad=6)
    ax.tick_params(axis='x', length=3)
    ax.spines['left'].set_visible(False)
    handles = [Line2D([], [], marker='o', mfc=style.FILL[True], label='Recorded stamp', **style.MARKER),
               Line2D([], [], marker='s', mfc=style.FILL[True], label='Equal entry/end bracket', **style.MARKER)]
    ax.legend(handles=handles, loc='upper right', borderaxespad=.6)
    return fig


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    domain, runtime = load()
    table = [{'cohort': phase, 'phase': label, **r}
             for phase, records in phases(domain) for label, r in records]
    origin, rows = events(runtime)
    for stem, figure, caption, data in (('component-agreement', component_figure, component_caption, domain),
                                        ('datalink-observations', datalink_figure, datalink_caption, runtime)):
        fig = figure(data)
        style.save(fig, OUT / stem)
        plt.close(fig)
        (OUT / f'{stem}.caption.md').write_text(caption(data) + '\n')
    with (OUT/'component-agreement.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(table[0]),lineterminator="\n");w.writeheader();w.writerows(table)
    with (OUT/'datalink-observations.csv').open('w') as f:
        w=csv.writer(f,lineterminator="\n");w.writerow(['stage','vehicle_hrt_us','since_last_receive_us','observation'])
        w.writerows((name,t,t-origin,kind) for name,t,kind in rows)

    lines=['# Retained result tables','',
           'Generated from committed results by `python scripts/plot_retained_results.py`.',
           'These are existing observations. Study A remains paused.','',
           '## Component comparison','',
           '| Cohort / phase | Executed [count] | Agree [count] | Disagree [count] |',
           '| --- | ---: | ---: | ---: |']
    for r in table:
        lines.append('| '+ ' | '.join([r['cohort']+' / '+r['phase']]+[f"{r[k]:,}" for k in ['executed','agree','disagree']])+' |')
    lines += ['', 'Admission counts, with unsupported-input probes kept separate:', '',
              '| Cohort / phase | Attempted [count] | Excluded [count] | Invalid [count] |',
              '| --- | ---: | ---: | ---: |']
    for r in table:
        lines.append('| '+ ' | '.join([r['cohort']+' / '+r['phase']]+[f"{r[k]:,}" for k in ['attempted','excluded','invalid']])+' |')
    probe=domain['admission_probes']
    lines.append(f"| Separate admission probes | {probe['attempted']} | {probe['excluded']} | {probe['invalid']} |")
    lines += ['',f"Separate admission probes: {probe['attempted']} attempted, {probe['excluded']} excluded, {probe['executed']} executed. They are outside the generated cohorts.",
              'Unit: one sequence. Replayed development sequences are reused inputs. The fresh corpus is separate from Study A confirmation.',
              '', '[Source, mechanism breakdown and exclusions](../../evidence/task-domain-2026-10-03/README.md) · [Source JSON](../../evidence/task-domain-2026-10-03/results.json) · [Download CSV](component-agreement.csv)',
              '', '## Instrumented datalink observations','',
              '| Stage | Vehicle HRT [s] | Since last observed receive [s] | Observation |',
              '| --- | ---: | ---: | --- |']
    lines += [f'| {name} | {t/1e6:.3f} | {(t-origin)/1e6:.3f} | {kind} |' for name,t,kind in rows]
    lines += ['', 'Decimal display follows this run\'s HRT granularity; it is not an accuracy claim. The detector and navigator brackets have equal entry/end stamps. No host-time duration follows from that equality.',
              '', 'Host-cut upper bound and actuator response: unavailable. Sampled flag brackets, cadence/gaps, binary and typed-parameter identities remain in the source packet.',
              '', '[Source and clock limits](../../evidence/task-observation-qualification-2026-10-04/README.md) · [Source JSON](../../evidence/task-observation-qualification-2026-10-04/results.json) · [Download exact microsecond CSV](datalink-observations.csv)','']
    (OUT/'tables.md').write_text('\n'.join(lines))
    manifest={'generator':'scripts/plot_retained_results.py','command':'python scripts/plot_retained_results.py',
              'matplotlib':matplotlib.__version__,'generator_sha256':digest(Path(__file__)),
              'style_sha256':digest(Path(style.__file__)),
              'inputs':{str(p.relative_to(ROOT)):digest(p) for p in [DOMAIN,RUNTIME]},
              'outputs':{p.name:digest(p) for p in sorted(OUT.iterdir()) if p.suffix in ['.png','.svg','.csv','.md']},
              'evidence':'existing component comparisons and instrumented runtime development observations',
              'style_reference':'https://github.com/500ft/evidence-sufficiency-benchmark/pull/26'}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')


if __name__ == '__main__':
    main()
