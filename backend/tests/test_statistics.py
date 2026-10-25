import pytest
from app.metrics.statistics import welch, power_plan


def test_welch_known_reference():
    result = welch([1, 2, 3], [1.1, 2.9, 4.2])
    assert result['p_value'] == pytest.approx(.5361949075)
    assert result['interval'][0] < result['effect'] < result['interval'][1]


def test_constant_or_sparse_welch_withholds_inference():
    assert welch([1, 1], [2, 2])['p_value'] is None
    assert welch([1], [2, 3])['effect'] is None


def test_planning_sample_and_power_are_consistent():
    plan = power_plan(.2, .03, 1000)
    assert 2700 < plan['required_users_per_arm'] < 3200
    achieved = power_plan(.2, .03, plan['required_users_per_arm'])
    assert achieved['power_at_planned_sample'] == pytest.approx(.8, abs=.005)
    assert achieved['minimum_detectable_absolute_effect'] == pytest.approx(.03, abs=.001)
    assert power_plan(.2, .03, 10000)['power_at_planned_sample'] > plan['power_at_planned_sample']


def test_planner_rejects_impossible_effect():
    with pytest.raises(ValueError):
        power_plan(.9, .2, 1000)
