from math import ceil, isfinite, sqrt
from statistics import NormalDist, mean, variance

from scipy.stats import t as student_t


def welch(control: list[float], treatment: list[float]) -> dict:
    result = {'effect': None, 'interval': None, 'p_value': None, 'status': 'insufficient_data'}
    if min(len(control), len(treatment)) < 2:
        return result
    delta = mean(treatment) - mean(control)
    a, b = variance(control)/len(control), variance(treatment)/len(treatment)
    result['effect'] = delta
    if a+b == 0:
        return result
    df = (a+b)**2 / (a*a/(len(control)-1) + b*b/(len(treatment)-1))
    se = sqrt(a+b)
    p = float(2*student_t.sf(abs(delta/se), df))
    margin = float(student_t.ppf(.975, df))*se
    if all(isfinite(x) for x in (p, margin)):
        result.update(interval=[delta-margin, delta+margin], p_value=p, status='difference_detected' if p < .05 else 'inconclusive')
    return result


def power_plan(baseline: float, effect: float, per_arm: int, target: float = .8) -> dict:
    """Normal approximation for a two-sided, equal-allocation binary experiment."""
    if not 0 < baseline < 1 or not 0 < effect < 1 or baseline+effect >= 1 or per_arm < 2 or not .5 < target < 1:
        raise ValueError('Use a baseline in (0,1), a positive effect with baseline + effect < 1, at least two users per arm, and target power in (0.5,1)')
    normal = NormalDist()
    z = normal.inv_cdf(.975)
    def required(delta):
        p2 = baseline + delta
        pooled = (baseline+p2)/2
        return (z*sqrt(2*pooled*(1-pooled)) + normal.inv_cdf(target)*sqrt(baseline*(1-baseline)+p2*(1-p2)))**2/delta**2
    p2 = baseline+effect
    se = sqrt((baseline*(1-baseline)+p2*(1-p2))/per_arm)
    null_se = sqrt(2*((baseline+p2)/2)*(1-(baseline+p2)/2)/per_arm)
    power = 1-normal.cdf((z*null_se-effect)/se)+normal.cdf((-z*null_se-effect)/se)
    lo, hi = 1e-8, 1-baseline-1e-8
    mde = None
    if required(hi) <= per_arm:
        for _ in range(70):
            mid = (lo+hi)/2
            if required(mid) > per_arm:
                lo = mid
            else:
                hi = mid
        mde = hi
    return {'required_users_per_arm': ceil(required(effect)), 'power_at_planned_sample': power, 'minimum_detectable_absolute_effect': mde, 'target_power': target, 'alpha': .05, 'method': 'Approximate two-sided binary comparison, equal allocation; positive absolute lift'}
