import tempfile
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

from cvise.passes.abstract import AbstractPass
from cvise.utils import fileutil
from cvise.utils.cache import Cache


@pytest.fixture(autouse=True)
def cd_to_tmp_path(tmp_path: Path) -> Iterator[None]:
    with fileutil.chdir(tmp_path):
        yield


@pytest.fixture
def cache_tmp_prefix() -> str:
    return f'cvisecachetest{uuid.uuid4()}'


@pytest.fixture
def cache(cache_tmp_prefix: str) -> Iterator[Cache]:
    with Cache(tmp_prefix=cache_tmp_prefix) as cache:
        yield cache
    assert _get_cache_storage_dirs(cache_tmp_prefix) == []  # no leftover temp files


class FakePass(AbstractPass):
    pass


def test_cache_add_lookup(cache: Cache, cache_tmp_prefix: str):
    PASSES = []
    FAKE_HASH = b'42'
    FAKE_HASH_OTHER = b'123'
    test_case = Path('foo.txt')
    test_case.write_text('foo')
    assert cache.lookup(PASSES, FAKE_HASH) is None
    cache.add(PASSES, FAKE_HASH, test_case)

    assert _get_cache_storage_dirs(cache_tmp_prefix) != []
    for _ in range(2):  # test two times to verify the cached file isn't moved away
        cached_path = cache.lookup(PASSES, FAKE_HASH)
        assert cached_path is not None
        assert cached_path.read_text() == 'foo'
    assert cache.lookup(PASSES, FAKE_HASH_OTHER) is None


def test_cache_add_same_hash_different_result(cache: Cache):
    PASSES = []
    FAKE_HASH = b'42'
    test_case = Path('foo.txt')
    test_case.write_text('x')
    cache.add(PASSES, FAKE_HASH, test_case)
    test_case.write_text('y')
    cache.add(PASSES, FAKE_HASH, test_case)

    cached_path = cache.lookup(PASSES, FAKE_HASH)
    assert cached_path is not None
    assert cached_path.read_text() == 'y'


def test_cache_lookup_per_pass(cache: Cache):
    FAKE_HASH = b'42'
    first_passes = [FakePass(arg='a')]
    second_passes = [FakePass(arg='b'), FakePass(arg='c')]
    test_case = Path('foo.txt')
    test_case.write_text('foo')
    cache.add(first_passes, FAKE_HASH, test_case)
    test_case.write_text('bar')
    cache.add(second_passes, FAKE_HASH, test_case)

    first_lookup = cache.lookup(first_passes, FAKE_HASH)
    assert first_lookup is not None
    assert first_lookup.read_text() == 'foo'
    second_lookup = cache.lookup(second_passes, FAKE_HASH)
    assert second_lookup is not None
    assert second_lookup.read_text() == 'bar'


def test_cache_eviction(cache: Cache, cache_tmp_prefix: str):
    PASSES = []
    ADD_CALLS = Cache.MAX_ITEMS_PER_PASS_GROUP + 1
    test_case = Path('foo.txt')
    test_case.write_text('foo')

    for i in range(ADD_CALLS):
        fake_hash = bytes(i)
        cache.add(PASSES, fake_hash, test_case)
        assert cache.lookup(PASSES, fake_hash) is not None
    assert len(_get_cache_storage_dirs(cache_tmp_prefix)) <= Cache.MAX_ITEMS_PER_PASS_GROUP


def _get_cache_storage_dirs(cache_tmp_prefix: str) -> list[Path]:
    tmp_dir = Path(tempfile.gettempdir())
    return list(tmp_dir.glob(f'{cache_tmp_prefix}*'))
