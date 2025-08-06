import pytest

from cvise.passes.abstract import SubsegmentState
from cvise.passes.clexhints import ClexHintsPass
from cvise.tests.testabstract import collect_all_transforms, validate_stored_hints
from cvise.utils.externalprograms import find_external_programs


# How many times to repeat each test that involves randomness (for extra reassurance).
RANDOM_TEST_REPETITIONS = 10

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


def collect_all_advances(s):
    observed = []
    while s is not None:
        observed.append((s.index, s.end()))
        s = s.advance()
    return sorted(observed)


@pytest.mark.parametrize('test_instance', range(RANDOM_TEST_REPETITIONS))
def test_state_iteration_chunk_1(test_instance):
    N = 10
    s = SubsegmentState.create(instances=N, min_chunk=1, max_chunk=1)
    assert collect_all_advances(s) == [(i, i + 1) for i in range(N)]


@pytest.mark.parametrize('test_instance', range(RANDOM_TEST_REPETITIONS))
def test_state_iteration_chunk_1_with_success(test_instance):
    INITIAL_N = 10
    NEW_N = 5
    s = SubsegmentState.create(instances=INITIAL_N, min_chunk=1, max_chunk=1)
    assert s is not None
    s = s.advance_on_success(NEW_N)
    assert collect_all_advances(s) == [(i, i + 1) for i in range(NEW_N)]


@pytest.mark.parametrize('test_instance', range(RANDOM_TEST_REPETITIONS))
def test_state_iteration_chunk_2(test_instance):
    N = 10
    s = SubsegmentState.create(instances=N, min_chunk=2, max_chunk=2)
    assert collect_all_advances(s) == [(i, i + 2) for i in range(N - 1)]


@pytest.mark.parametrize('test_instance', range(RANDOM_TEST_REPETITIONS))
def test_state_iteration_chunk_2_with_successes(test_instance):
    INITIAL_N = 10
    SECOND_N = 10
    FINAL_N = 1
    s = SubsegmentState.create(instances=INITIAL_N, min_chunk=2, max_chunk=2)
    assert s is not None
    s = s.advance_on_success(SECOND_N)
    assert s is not None
    assert collect_all_advances(s) == [(i, i + 2) for i in range(SECOND_N - 1)]
    s = s.advance_on_success(FINAL_N)
    assert s is None


@pytest.mark.parametrize('test_instance', range(RANDOM_TEST_REPETITIONS))
def test_state_iteration_chunks_1_to_2(test_instance):
    N = 10
    s = SubsegmentState.create(instances=N, min_chunk=1, max_chunk=2)
    assert collect_all_advances(s) == [(i, j) for i in range(N) for j in range(i + 1, 1 + min(N, i + 2))]


@pytest.mark.parametrize('test_instance', range(RANDOM_TEST_REPETITIONS))
def test_state_iteration_chunks_1_to_2_with_success(test_instance):
    INITIAL_N = 10
    FINAL_N = 3
    s = SubsegmentState.create(instances=INITIAL_N, min_chunk=1, max_chunk=2)
    assert s is not None
    s = s.advance_on_success(FINAL_N)
    assert collect_all_advances(s) == [(0, 1), (0, 2), (1, 2), (1, 3), (2, 3)]
