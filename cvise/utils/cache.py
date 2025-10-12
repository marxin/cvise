from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Optional

from cvise.passes.abstract import AbstractPass
from cvise.utils import fileutil


@dataclass
class _Item:
    tmp_dir: Path
    path: Path


class Cache:
    MAX_ITEMS_PER_PASS_GROUP = 3

    def __init__(self, tmp_prefix: str):
        self._tmp_prefix: str = tmp_prefix
        self._items: dict[str, dict[bytes, _Item]] = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for mapping in self._items.values():
            for item in mapping.values():
                fileutil.rmfolder(item.tmp_dir)
        self._items = {}

    def lookup(self, passes: Sequence[AbstractPass], hash_before: bytes) -> Optional[Path]:
        key = self._key(passes)
        item = self._items.get(key, {}).get(hash_before)
        return item.path if item else None

    def add(self, passes: Sequence[AbstractPass], hash_before: bytes, path_after: Path) -> None:
        key = self._key(passes)
        mapping = self._items.setdefault(key, {})

        evict_hash = None
        if hash_before in mapping:
            evict_hash = hash_before
        elif len(mapping) >= self.MAX_ITEMS_PER_PASS_GROUP:
            evict_hash = next(iter(mapping.keys()))

        if evict_hash is not None:
            fileutil.rmfolder(mapping[evict_hash].tmp_dir)
            del mapping[evict_hash]

        tmp_dir = Path(tempfile.mkdtemp(prefix=self._tmp_prefix))
        mapping[hash_before] = _Item(tmp_dir, tmp_dir / path_after)
        fileutil.copy_test_case(path_after, tmp_dir)

    def _key(self, passes: Sequence[AbstractPass]) -> str:
        return repr([passes])
