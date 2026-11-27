"""Round-eight combined-market hypotheses and a single gated holdout."""

import argparse
from collections import defaultdict
import itertools
import json
import math
from pathlib import Path
import subprocess

import numpy as np

import inputs as archive

FOLDER = archive.FOLDER
HYPOTHESES = ('H1', 'H2', 'H3')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=archive.REPO).decode().strip()


def registration():
    if git('rev-parse', '--is-shallow-repository') != 'false':
        raise ValueError('Full Git history required')
    commits = git('log', '--diff-filter=A', '--format=%H', '--', 'models/cross_market_macro_search/registration.json').splitlines()
    if len(commits) != 1:
        raise ValueError('Exactly one committed preregistration is required')
    for name in ('registration.json', 'PREREGISTRATION.md'):
        blob = subprocess.check_output(['git', 'show', f'{commits[0]}:models/cross_market_macro_search/{name}'], cwd=archive.REPO)
        if blob.replace(b'\r\n', b'\n') != (FOLDER/name).read_bytes().replace(b'\r\n', b'\n'):
            raise ValueError('Committed preregistration changed')
    spec = json.loads((FOLDER/'registration.json').read_text())
    for path, expected in spec['code_hashes'].items():
        if archive.digest(archive.REPO/path) != expected:
            raise ValueError('Pinned implementation changed: '+path)
    if archive.sources(archive.ROOT) != spec['data_hashes']:
        raise ValueError('Frozen source inputs changed')
    return spec, commits[0]


def logit(value):
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError('Invalid probability')
    value = min(1-1e-6, max(1e-6, value))
    return math.log(value)-math.log1p(-value)


def offset_fit(probabilities, signals, realized, penalty=1.):
    if not probabilities or not math.isfinite(penalty) or penalty <= 0:
        raise ValueError('Nonempty training data and positive L2 required')
    offset = np.array([logit(p) for p in probabilities])
    x, y = np.array(signals, dtype=float), np.array(realized, dtype=float)
    if x.ndim != 2 or x.shape[0] != len(offset) or x.shape[1] == 0 or y.shape != offset.shape or not np.isfinite(x).all() or not np.isin(y, (0, 1)).all():
        raise ValueError('Invalid training dimensions or signal')
    beta = np.zeros(x.shape[1])
    for _ in range(100):
        z = offset+x@beta
        p = np.exp(-np.logaddexp(0, -z))
        gradient = x.T@(p-y)+penalty*beta
        hessian = x.T@((p*(1-p))[:, None]*x)+penalty*np.eye(x.shape[1])
        step = np.linalg.solve(hessian, gradient)
        objective = float(np.sum(np.logaddexp(0, z)-y*z)+penalty*(beta@beta)/2)
        while np.max(np.abs(step)) > 1e-12:
            proposed = offset+x@(beta-step)
            target = float(np.sum(np.logaddexp(0, proposed)-y*proposed)+penalty*((beta-step)@(beta-step))/2)
            if target <= objective:
                break
            step /= 2
        beta -= step
        if np.max(np.abs(step)) < 1e-10:
            return beta
    raise RuntimeError('Offset fit did not converge')


class Model:
    def __init__(self, data, spec, family, asset, placebo=False):
        allowed = set(spec['families'][family]['development'])
        self.daily = [r for r in data['daily'] if r['family'] == family and r['event'] in allowed]
        self.accuracy = [r for r in data['accuracy'] if r['family'] == family]
        self.asset, self.spec = asset, spec
        self.features = spec['groups'][asset]
        self.field = 'placebo' if placebo else 'moves'
        self.sign_cache, self.beta_cache = {}, {}

    def move(self, row):
        return np.array([row[self.field][name]/self.spec['feature_scales'][name] for name in self.features])

    def signs_at(self, cutoff, event):
        key = cutoff, event
        if key not in self.sign_cache:
            grouped = defaultdict(list)
            for row in self.daily:
                if row['event'] != event and row['resolved'] < cutoff and row['next_close'] < cutoff:
                    grouped[row['outcome_key']].append(row)
            result = {}
            for outcome, rows in grouped.items():
                if len({r['event'] for r in rows}) < self.spec['minimum_train_events']:
                    continue
                x = np.array([self.move(r) for r in rows])
                y = np.array([logit(r['p1'])-logit(r['p0']) for r in rows])
                covariance = np.sum((x-x.mean(axis=0))*(y-y.mean())[:, None], axis=0)
                result[outcome] = np.sign(covariance)
            self.sign_cache[key] = result
        return self.sign_cache[key]

    def signal(self, row):
        return float(np.mean(self.vector(row)))

    def vector(self, row):
        return self.signs_at(row['cutoff'], row['event']).get(row['outcome_key'], np.zeros(len(self.features)))*self.move(row)

    def trained(self, row):
        return bool(np.any(self.signs_at(row['cutoff'], row['event']).get(row['outcome_key'], 0)))

    def beta_at(self, row):
        key = row['cutoff'], row['event']
        if key not in self.beta_cache:
            eligible = [(r, self.vector(r)) for r in self.accuracy
                if r['event'] != row['event'] and r['resolved'] < row['cutoff'] and r['cutoff'] < row['cutoff']]
            eligible = [(r, x) for r, x in eligible if np.any(x)]
            if len({r['event'] for r, _ in eligible}) < self.spec['minimum_train_events']:
                beta = np.zeros(len(self.features))
            else:
                beta = offset_fit([r['p0'] for r, _ in eligible], [x for _, x in eligible],
                    [r['realized'] for r, _ in eligible], self.spec['L2'])
            self.beta_cache[key] = beta
        return self.beta_cache[key]


def flip_p(values, spec):
    values = np.array(values, dtype=float)
    n = len(values)
    if n < spec['minimum_test_events']:
        return 1.
    observed = float(values.sum())
    if n <= spec['exact_max_events']:
        signs = np.array(list(itertools.product((-1., 1.), repeat=n)))
        return float(np.mean(signs@values >= observed-1e-12))
    rng = np.random.default_rng(spec['seed'])
    count, remaining = 0, spec['permutations']
    while remaining:
        batch = min(2048, remaining)
        count += int(np.sum(rng.choice((-1., 1.), size=(batch, n))@values >= observed-1e-12))
        remaining -= batch
    return (count+1)/(spec['permutations']+1)


def paired_bootstrap(values, spec):
    values = np.array(values, dtype=float)
    if not len(values):
        return 1., None, None
    rng = np.random.default_rng(spec['seed'])
    means = values[rng.integers(0, len(values), size=(spec['bootstraps'], len(values)))].mean(axis=1)
    observed = float(values.mean())
    p = (1+int(np.sum(means-observed >= observed-1e-12)))/(spec['bootstraps']+1)
    low, high = np.quantile(means, [.025, .975])
    return (float(p) if len(values) >= spec['minimum_test_events'] else 1.), float(low), float(high)


def regression(rows, spec):
    rows = [r for r in rows if r['trained']]
    if not rows:
        return {'metric': None, 'p': 1., 'n_events': 0, 'n_rows': 0, 'cluster_se': None}
    grouped = defaultdict(list)
    for i, row in enumerate(rows):
        grouped[row['outcome_key']].append(i)
    x = np.array([r['signal'] for r in rows], dtype=float)
    y = np.array([logit(r['p1'])-logit(r['p0']) for r in rows])
    for indices in grouped.values():
        x[indices] -= x[indices].mean()
        y[indices] -= y[indices].mean()
    denominator = float(x@x)
    if denominator <= 1e-15:
        return {'metric': None, 'p': 1., 'n_events': len({r['event'] for r in rows}), 'n_rows': len(rows), 'cluster_se': None}
    beta = float(x@y/denominator)
    null_scores, residual_scores = defaultdict(float), defaultdict(float)
    for row, a, b in zip(rows, x, y):
        null_scores[row['event']] += float(a*b)
        residual_scores[row['event']] += float(a*(b-beta*a))
    n, g, k = len(rows), len(null_scores), len(grouped)+1
    se = math.sqrt(g/(g-1)*(n-1)/(n-k)*sum(v*v for v in residual_scores.values()))/denominator if g > 1 and n > k else None
    return {'metric': beta, 'p': flip_p(list(null_scores.values()), spec), 'n_events': g,
        'n_rows': n, 'cluster_se': se}


def evaluate(data, spec, family, asset, hypothesis, phase, placebo=False):
    model = Model(data, spec, family, asset, placebo)
    events = set(spec['families'][family][phase])
    source = {'H1': 'daily', 'H2': 'accuracy', 'H3': 'trading'}[hypothesis]
    rows = [r for r in data[source] if r['family'] == family and r['event'] in events]
    if hypothesis == 'H1':
        return regression([{**r, 'signal': model.signal(r),
            'trained': model.trained(r)} for r in rows], spec)
    values = defaultdict(list)
    for row in rows:
        signal = model.signal(row)
        if hypothesis == 'H2':
            beta = model.beta_at(row)
            vector = model.vector(row)
            adjusted = float(np.exp(-np.logaddexp(0, -(logit(row['p0'])+float(beta@vector))))) if np.any(beta) and np.any(vector) else row['p0']
            market_loss = (row['p0']-row['realized'])**2
            adjusted_loss = (adjusted-row['realized'])**2
            value = market_loss-adjusted_loss
        elif hypothesis == 'H3':
            side = 'YES' if signal > 0 else 'NO'
            entry = row['entries'][side] if signal else None
            value = 0.
            if entry and entry[0] > row['cutoff'] and entry[0] < row['release'] and entry[1]+spec['pm_cost'] < 1:
                payout = row['realized'] if side == 'YES' else 1-row['realized']
                value = payout/(entry[1]+spec['pm_cost'])-1
        else:
            raise ValueError('Unregistered hypothesis')
        values[row['event']].append(value)
    per_event = [float(np.mean(v)) for _, v in sorted(values.items())]
    metric = float(np.mean(per_event)) if per_event else None
    result = {'metric': metric, 'n_events': len(per_event), 'n_rows': len(rows), 'cluster_se': None}
    if hypothesis == 'H2':
        p, low, high = paired_bootstrap(per_event, spec)
        result.update({'p': p, 'brier_delta': -metric if metric is not None else None,
            'improvement_ci_low': low, 'improvement_ci_high': high})
    else:
        result.update({'p': flip_p(per_event, spec), 'roi': metric})
    return result


def holm(pvalues):
    result, previous = {}, 0.
    ordered = sorted(pvalues, key=lambda k: (pvalues[k], k))
    for index, name in enumerate(ordered):
        previous = max(previous, min(1., (len(ordered)-index)*pvalues[name]))
        result[name] = previous
    return result


def names(spec):
    return [(family+'/'+asset+'/'+hypothesis, family, asset, hypothesis)
        for family in spec['families'] for asset in spec['assets'] for hypothesis in spec['hypotheses']]


def advanced(development, spec):
    return sorted(k for k, v in development.items() if v['metric'] is not None and v['metric'] > 0 and v['p'] < spec['development_alpha'])


def develop(spec, commit):
    path = archive.ROOT/'development.json'
    if path.exists() or (FOLDER/'development.json').exists():
        raise ValueError('Development already frozen; no search rerun')
    data = json.loads((archive.ROOT/'panel.json').read_text())
    results, controls = {}, {}
    for name, family, asset, hypothesis in names(spec):
        results[name] = evaluate(data, spec, family, asset, hypothesis, 'development')
        controls[name] = evaluate(data, spec, family, asset, hypothesis, 'development', True)
    frozen = {'preregistration_commit': commit, 'registration_sha256': archive.digest(FOLDER/'registration.json'),
        'code_hashes': spec['code_hashes'], 'data_hashes': spec['data_hashes'], 'development': results,
        'placebo': controls, 'advanced': advanced(results, spec)}
    archive.save(path, frozen)
    archive.save(FOLDER/'development.json', frozen)
    print('Development frozen; advanced: '+(', '.join(frozen['advanced']) or 'none'))


def claim(path, development, spec):
    if development['advanced'] != advanced(development['development'], spec):
        raise ValueError('Frozen advancement set changed')
    with path.open('x') as handle:
        json.dump({'status': 'claimed', 'advanced': development['advanced'],
            'registration_sha256': development['registration_sha256'],
            'development_sha256': archive.digest(archive.ROOT/'development.json')}, handle)


def holdout(spec, commit):
    development = json.loads((archive.ROOT/'development.json').read_text())
    committed = subprocess.check_output(['git', 'show', 'HEAD:models/cross_market_macro_search/development.json'], cwd=archive.REPO)
    if committed.replace(b'\r\n', b'\n') != (archive.ROOT/'development.json').read_bytes().replace(b'\r\n', b'\n'):
        raise ValueError('Development must be committed before holdout')
    if development['registration_sha256'] != archive.digest(FOLDER/'registration.json') or development['data_hashes'] != spec['data_hashes'] or development['code_hashes'] != spec['code_hashes'] or development['preregistration_commit'] != commit:
        raise ValueError('Frozen inputs changed')
    lock = archive.ROOT/'holdout_lock.json'
    claim(lock, development, spec)
    data = json.loads((archive.ROOT/'panel.json').read_text())
    results, controls = {}, {}
    for name in development['advanced']:
        family, asset, hypothesis = name.split('/')
        results[name] = evaluate(data, spec, family, asset, hypothesis, 'holdout')
        controls[name] = evaluate(data, spec, family, asset, hypothesis, 'holdout', True)
    adjusted = holm({k: v['p'] for k, v in results.items()})
    passed = [k for k, v in results.items() if v['metric'] is not None and v['metric'] > 0 and adjusted[k] < spec['holdout_alpha']]
    output = {'status': 'complete', 'results': results, 'placebo': controls, 'holm': adjusted, 'passed': passed}
    archive.save(lock, {**output, 'preregistration_commit': commit,
        'development_sha256': archive.digest(archive.ROOT/'development.json')})
    archive.save(FOLDER/'holdout.json', output)
    report(development, output, spec)
    print('Holdout evaluated once; lock retained. Passes: '+(', '.join(passed) or 'none'))


def number(value):
    return '—' if value is None else f'{value:.6g}'


def report(development, holdout, spec):
    verdict = 'No preregistered cross-market hypothesis established a holdout edge.' if not holdout['passed'] else 'Round-eight holdout passes: '+', '.join(holdout['passed'])+'.'
    lines = ['# '+verdict, '', 'Round 8; 12 hypotheses; dev gate p<.10; one-sided holdout Holm p<.01. These reused historical markets are not fresh independent confirmation.', '',
        '| Hypothesis | Dev events | Dev metric | Dev p | Holdout events | Holdout metric | Raw p | Holm p | Status |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---|']
    records = []
    for name, _, _, hypothesis in names(spec):
        dev = development['development'][name]
        held = holdout['results'].get(name, {})
        status = 'PASS' if name in holdout['passed'] else ('FAIL' if held else 'not advanced')
        records.append({'hypothesis': name, 'dev_events': dev['n_events'], 'dev_metric': dev['metric'],
            'dev_roi': dev.get('roi'), 'dev_brier_delta': dev.get('brier_delta'), 'dev_cluster_se': dev.get('cluster_se'), 'dev_p': dev['p'],
            'dev_improvement_ci_low': dev.get('improvement_ci_low'), 'dev_improvement_ci_high': dev.get('improvement_ci_high'),
            'holdout_events': held.get('n_events'), 'holdout_metric': held.get('metric'),
            'holdout_roi': held.get('roi'), 'holdout_brier_delta': held.get('brier_delta'), 'holdout_cluster_se': held.get('cluster_se'),
            'holdout_p': held.get('p'), 'holm_p': holdout['holm'].get(name), 'status': status,
            'holdout_improvement_ci_low': held.get('improvement_ci_low'), 'holdout_improvement_ci_high': held.get('improvement_ci_high'),
            'placebo_dev_metric': development['placebo'][name]['metric'], 'placebo_dev_p': development['placebo'][name]['p'],
            'placebo_holdout_metric': holdout['placebo'].get(name, {}).get('metric'), 'placebo_holdout_p': holdout['placebo'].get(name, {}).get('p')})
        lines.append(f"| {name} | {dev['n_events']} | {number(dev['metric'])} | {number(dev['p'])} | {held.get('n_events', '—')} | {number(held.get('metric'))} | {number(held.get('p'))} | {number(holdout['holm'].get(name))} | {status} |")
    lines += ['', 'H1 metric is the signed-move slope (outcome fixed effects; event-cluster CR1 SEs in CSV; one-sided cluster wild-score sign-flip p). H2 metric is market-minus-adjusted binary Brier (positive improves); CSV also gives adjusted-minus-market Brier delta. H3 is mean equal-event after-cost ROI, including cash.', '',
        '## Placebo controls (descriptive only; excluded from gate and Holm)', '', '| Pipeline | Dev metric | Dev p | Holdout metric | Holdout p |', '|---|---:|---:|---:|---:|']
    for row in records:
        lines.append(f"| {row['hypothesis']} | {number(row['placebo_dev_metric'])} | {number(row['placebo_dev_p'])} | {number(row['placebo_holdout_metric'])} | {number(row['placebo_holdout_p'])} |")
    lines += ['', '## Limitations', '',
        '- Round 8 of a repeated research sequence; prior study use means the historical holdout is not independent fresh confirmation.',
        '- Only seven held-out releases per family, and sometimes fewer informative H1 events. Exact event sign-flip tests have coarse minimum p-values; Holm further limits power.',
        '- H1 CR1 SEs/wild-score inference and paired Brier bootstrap assume adequate event-level independence. Serial/overlapping exposure and co-released families remain dependent; Holm tolerates dependence but does not repair invalid marginal p-values.',
        '- Fed is change in P(no change) at the nearest future archived meeting, not a complete expected rate path. Missing archived meetings can change its maturity. CPI is change in the highest-threshold upper YoY bucket, whose threshold changes between releases; it is not expected inflation. Sources are selected before checking availability, without replacement.',
        '- USO/GLD/CPER are unadjusted ETF prices, not spot commodity or continuously rolled futures prices. Fees, rolls, carry and distributions affect these proxies. Historical Yahoo vintages and publication latency are not point-in-time verified.',
        '- Signals end at 16:00/13:00 ET; daily PM decisions are 16:05/13:05, with early closes and DST. H2 uses only an earlier completed session. See source_cutoffs.csv for every release-minus-24h availability check.',
        '- Complete-case source coverage: H1/H3 12 development and 7 holdout events per family. H2 only 9/4 payroll and 10/4 unemployment events: below the five-event test minimum in holdout, so any advanced H2 would receive p=1. Causal training further reduces informative observations. The registered H2 is retained rather than silently changing the cutoff or source.',
        '- Missing outcome-class histories cause H1 omissions and market/cash fallbacks for H2/H3. The commodity-only ablation uses the same complete-case opportunities, not a larger standalone commodity population.',
        '- H1 includes the final pre-release forecast interval when next-session prices exist: its target may incorporate release news, using actual trades no later than settlement rather than substituting the realized label. H3 eligibility uses only the current fresh baseline, never future target availability.',
        '- Trades are participant-print execution proxies, not executable quotes. Holding many daily entries to resolution produces overlapping positions; ROI is an equal-event diagnostic, not a deployable compounded portfolio. The flat $0.02 cost proxy ignores changing fees and capacity.',
        '- Historical asset-price revisions and point-in-time archive availability limit real-world replication. No crypto data enters this study.']
    (FOLDER/'RESULTS.md').write_text('\n'.join(lines)+'\n')
    archive.csv_write(FOLDER/'results.csv', records)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('development', 'holdout'))
    arguments = parser.parse_args()
    specification, preregistration_commit = registration()
    (develop if arguments.phase == 'development' else holdout)(specification, preregistration_commit)
