"""Assign material controls from captured values despite RNA side effects."""
INPLANE_FIELDS = ('tension_stiffness', 'compression_stiffness', 'shear_stiffness',
                  'tension_stiffness_max', 'compression_stiffness_max', 'shear_stiffness_max')

def scale_inplane_stiffness(settings, inherited, factor):
    assert factor > 0
    expected = {name: inherited[name] * factor for name in INPLANE_FIELDS}
    for name, value in expected.items():
        setattr(settings, name, value)
    actual = {name: getattr(settings, name) for name in INPLANE_FIELDS}
    for name in INPLANE_FIELDS:
        assert abs(actual[name] - expected[name]) <= max(1e-6, abs(expected[name]) * 1e-6), (name, expected[name], actual[name])
    return actual
