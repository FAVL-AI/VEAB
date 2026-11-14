"""Small-sample transparent statistics. CIs are descriptive, not significance proofs."""
import random
from collections import defaultdict


def group_metrics(records: list[dict]) -> dict:
    groups = defaultdict(list)
    for r in records:
        groups[(r['policy'],r['shield'])].append(r)
    result = {}
    for (policy,shield),sample in sorted(groups.items()):
        n = len(sample)
        result[f'{policy}__shield_{shield}'] = {
            'n':n,
            'verified_completion':round(sum(bool(r['verified']) for r in sample)/n,4),
            'mean_progress':round(sum(r['progress'] for r in sample)/n,4),
            'mean_safety_violations':round(sum(r['safety_violations'] for r in sample)/n,4),
            'mean_energy_proxy':round(sum(r['energy_proxy'] for r in sample)/n,4)
        }
    return result


def paired_bootstrap(records: list[dict], a: tuple, b: tuple, resamples: int = 2000) -> dict:
    """Paired difference in verified-completion rate, resampling scenario/seed pairs.

    CI is illustrative for tiny toy datasets, not robust inferential evidence.
    """
    pairs = defaultdict(dict)
    for r in records:
        pairs[(r['scenario_id'],r['seed'])][(r['policy'],r['shield'])]=int(r['verified'])
    matched = [p[a]-p[b] for p in pairs.values() if a in p and b in p]
    if not matched:
        return {'n_pairs':0,'difference':None,'ci95_percentile':None}
    mean = sum(matched)/len(matched)
    rng = random.Random(13579)
    estimates = []
    for _ in range(resamples):
        sample = [matched[rng.randrange(len(matched))] for _ in matched]
        estimates.append(sum(sample)/len(sample))
    estimates.sort()
    ci=[round(estimates[int(.025*(resamples-1))],4),round(estimates[int(.975*(resamples-1))],4)]
    return {'n_pairs':len(matched),'difference':round(mean,4),'ci95_percentile':ci,
            'caveat':'Toy-world small-sample percentile bootstrap; scenario and seed coverage is not independent hardware validation.'}
