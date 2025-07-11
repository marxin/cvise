import pytest

from cvise.passes.line_markers import LineMarkersPass
from cvise.tests.testabstract import collect_all_transforms, validate_stored_hints


@pytest.fixture
def input_path(tmp_path):
    return tmp_path / 'input.cc'


def init_pass(tmp_path, input_path):
    pass_ = LineMarkersPass()
    state = pass_.new(input_path, tmp_dir=tmp_path)
    validate_stored_hints(state)
    return pass_, state


def test_all(tmp_path, input_path):
    input_path.write_text("# 1 'foo.h'\n# 2 'bar.h'\n#4   'x.h'")
    pass_, state = init_pass(tmp_path, input_path)

    (_, state) = pass_.transform(input_path, state, None)

    assert input_path.read_text() == ''


def test_only_last(tmp_path, input_path):
    input_path.write_text("# 1 'foo.h'\n# 2 'bar.h'\n#4   'x.h\nint x = 2;")
    pass_, state = init_pass(tmp_path, input_path)

    (_, state) = pass_.transform(input_path, state, None)

    assert input_path.read_text() == 'int x = 2;'


def test_all_iteration(tmp_path, input_path):
    input_path.write_text("# 1 'foo.h'\n# 2 'bar.h'\nint x = 2;\n# 4 'x.h'")
    pass_, state = init_pass(tmp_path, input_path)

    all_transforms = collect_all_transforms(pass_, state, input_path)

    assert "# 2 'bar.h'\nint x = 2;\n# 4 'x.h'" in all_transforms
    assert "# 1 'foo.h'\nint x = 2;\n# 4 'x.h'" in all_transforms
    assert "# 1 'foo.h'\n# 2 'bar.h'\nint x = 2;\n" in all_transforms
