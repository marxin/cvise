import pytest

from cvise.passes.clexhints import ClexHintsPass
from cvise.tests.testabstract import collect_all_transforms, validate_stored_hints
from cvise.utils.externalprograms import find_external_programs


INPUT = """
void f() {
    char x;
}
"""

TOKENS_REMOVED_1 = [
    b"""
f() {
    char x;
}
""",
    b"""
void () {
    char x;
}
""",
    b"""
void f) {
    char x;
}
""",
    b"""
void f({
    char x;
}
""",
    b"""
void f() char x;
}
""",
    b"""
void f() {
    x;
}
""",
    b"""
void f() {
    char ;
}
""",
    b"""
void f() {
    char x}
""",
    b"""
void f() {
    char x;
""",
]

TOKENS_REMOVED_2 = [
    b"""
() {
    char x;
}
""",
    b"""
void ) {
    char x;
}
""",
    b"""
void f{
    char x;
}
""",
    b"""
void f(char x;
}
""",
    b"""
void f() x;
}
""",
    b"""
void f() {
    ;
}
""",
    b"""
void f() {
    char }
""",
    b"""
void f() {
    char x""",
]

TOKENS_REMOVED_8 = [
    b'\n',
]


@pytest.fixture
def input_path(tmp_path):
    return tmp_path / 'input.cc'


def init_pass(arg, tmp_dir, input_path):
    pass_ = ClexHintsPass(arg, find_external_programs())
    state = pass_.new(input_path, tmp_dir=tmp_dir)
    validate_stored_hints(state)
    return pass_, state


def test_rm_toks_1(tmp_path, input_path):
    """Test that the "rm-toks" pass with parameter "1" deletes individual tokens."""
    input_path.write_text(INPUT)
    p, state = init_pass('rm-toks-1-to-1', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert set(TOKENS_REMOVED_1) <= all_transforms


def test_rm_toks_2(tmp_path, input_path):
    """Test that the "rm-toks" pass with parameter "2" additionally deletes pairs of consecutive tokens."""
    input_path.write_text(INPUT)
    p, state = init_pass('rm-toks-2-to-2', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert set(TOKENS_REMOVED_2) <= all_transforms
    assert all_transforms.isdisjoint(set(TOKENS_REMOVED_1))


def test_rm_toks_1_to_2(tmp_path, input_path):
    """Test that the "rm-toks" pass with parameter "1 to 2" additionally deletes pairs of consecutive tokens."""
    input_path.write_text(INPUT)
    p, state = init_pass('rm-toks-1-to-2', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert set(TOKENS_REMOVED_2) <= all_transforms
    assert set(TOKENS_REMOVED_1) <= all_transforms


def test_rm_toks_16_shorter(tmp_path, input_path):
    """Test that the "rm-toks" pass with parameter "1 to 16" removes all tokens when there's less than 16 of them."""
    input_path.write_text(INPUT)
    p, state = init_pass('rm-toks-1-to-16', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert set(TOKENS_REMOVED_8) <= all_transforms
    assert set(TOKENS_REMOVED_2) <= all_transforms
    assert set(TOKENS_REMOVED_1) <= all_transforms
