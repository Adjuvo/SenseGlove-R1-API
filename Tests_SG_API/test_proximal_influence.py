from SG_API.SG_Pro.SG_robot_pinch_mapper import Robot_Pinch_Mapper


def _flexion_at(influence: float) -> float:
    mapper = Robot_Pinch_Mapper()

    def _set(*_args, **_kwargs):
        mapper.state.proximal_influence = influence
        mapper.state.pinch_factor = 0.0

    mapper._calculate_pinch_factor = _set
    flex = [1000, 0, 0, 0, 0]
    proximal = [9000, 0, 0, 0, 0]
    result = mapper.compute_rpm_bents(
        flex, [0, 5000, 5000, 5000, 5000], proximal, [0] * 5,
        [100, 100, 100, 100], [[100] * 4] * 4,
    )
    return result[0][0]


def test_zero_proximal_influence_keeps_original_flexion():
    assert _flexion_at(0.0) == 1000


def test_full_proximal_influence_uses_proximal():
    assert _flexion_at(1.0) == 9000


def test_higher_proximal_influence_moves_closer_to_proximal():
    assert _flexion_at(0.8) > _flexion_at(0.2)
