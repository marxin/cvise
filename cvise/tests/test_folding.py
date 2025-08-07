from pathlib import Path

from cvise.passes.hint_based import HintState, PerTypeHintState
from cvise.utils.folding import FoldingManager


def create_stub_hint_state(type: str) -> HintState:
    fake_path = Path()
    return HintState(
        tmp_dir=fake_path, per_type_states=[PerTypeHintState(type=type, hints_file_name=fake_path, underlying_state=0)]
    )


def test_folding_two():
    state1 = create_stub_hint_state('type1')
    state2 = create_stub_hint_state('type2')
    mgr = FoldingManager()
    mgr.on_transform_job_success(state1)
    mgr.on_transform_job_success(state2)

    fold = mgr.maybe_prepare_folding_job(job_order=100)
    assert fold is not None
    assert fold.sub_states == [state1, state2]


def test_folding_many():
    N = 10
    states = [create_stub_hint_state(f'type{i}') for i in range(N)]
    mgr = FoldingManager()
    for s in states:
        mgr.on_transform_job_success(s)

    fold = mgr.maybe_prepare_folding_job(job_order=N + 1)
    assert fold is not None
    assert fold.sub_states == states


def test_no_folding_zero_candidates():
    mgr = FoldingManager()
    fold = mgr.maybe_prepare_folding_job(job_order=100)
    assert fold is None


def test_no_folding_one_candidate():
    state = create_stub_hint_state('type')
    mgr = FoldingManager()
    mgr.on_transform_job_success(state)

    fold = mgr.maybe_prepare_folding_job(job_order=100) is None
    assert fold


def test_dont_fold_same_twice():
    state1 = create_stub_hint_state('type1')
    state2 = create_stub_hint_state('type2')
    mgr = FoldingManager()
    mgr.on_transform_job_success(state1)
    mgr.on_transform_job_success(state2)

    fold1 = mgr.maybe_prepare_folding_job(job_order=100)
    assert fold1 is not None
    fold2 = mgr.maybe_prepare_folding_job(job_order=200)
    assert fold2 is None


def test_folding_continues_with_new_candidates():
    state1 = create_stub_hint_state('type1')
    state2 = create_stub_hint_state('type2')
    state3 = create_stub_hint_state('type3')
    mgr = FoldingManager()
    mgr.on_transform_job_success(state1)
    mgr.on_transform_job_success(state2)
    fold1 = mgr.maybe_prepare_folding_job(job_order=100)
    assert fold1 is not None
    fold2 = mgr.maybe_prepare_folding_job(job_order=200)
    assert fold2 is None

    mgr.on_transform_job_success(state3)
    fold3 = mgr.maybe_prepare_folding_job(job_order=300)
    assert fold3 is not None


def test_only_fold_hints():
    state1 = create_stub_hint_state('type')
    state2 = 'some-non-hint-state'
    mgr = FoldingManager()
    mgr.on_transform_job_success(state1)
    mgr.on_transform_job_success(state2)

    fold = mgr.maybe_prepare_folding_job(job_order=100)
    assert fold is None


def test_dont_nest_fold_into_fold():
    state1 = create_stub_hint_state('type1')
    state2 = create_stub_hint_state('type2')
    mgr = FoldingManager()
    mgr.on_transform_job_success(state1)
    mgr.on_transform_job_success(state2)
    fold1 = mgr.maybe_prepare_folding_job(job_order=100)
    assert fold1 is not None
    mgr.on_transform_job_success(fold1)

    fold2 = mgr.maybe_prepare_folding_job(job_order=1000)
    assert fold2 is None


def test_dont_fold_too_often():
    N = 10
    MAX_FOLDS = N // 2  # a reasonable upper boundary, without hardcoding specific implementation choices here
    mgr = FoldingManager()

    folds = []
    for i in range(N):
        mgr.on_transform_job_success(create_stub_hint_state(f'type{i}'))
        folds.append(mgr.maybe_prepare_folding_job(job_order=N + i))
    assert sum(f is not None for f in folds) < MAX_FOLDS


def test_continue_attempting_folds_initially():
    PARALLEL_TESTS = 10
    PASS_COUNT = 10
    mgr = FoldingManager()
    assert mgr.continue_attempting_folds(job_order=1, parallel_tests=PARALLEL_TESTS, pass_count=PASS_COUNT)
    mgr.on_transform_job_success(create_stub_hint_state('type1'))
    assert mgr.continue_attempting_folds(job_order=2, parallel_tests=PARALLEL_TESTS, pass_count=PASS_COUNT)
    mgr.on_transform_job_success(create_stub_hint_state('type2'))
    assert mgr.continue_attempting_folds(job_order=3, parallel_tests=PARALLEL_TESTS, pass_count=PASS_COUNT)


def test_stop_attempting_folds():
    PARALLEL_TESTS = 10
    PASS_COUNT = 10
    BIG_NUMBER = 10000
    mgr = FoldingManager()
    assert not mgr.continue_attempting_folds(job_order=BIG_NUMBER, parallel_tests=PARALLEL_TESTS, pass_count=PASS_COUNT)
