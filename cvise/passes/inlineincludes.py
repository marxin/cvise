from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

from cvise.passes.hint_based import HintBasedPass
from cvise.utils.hint import Hint, HintBundle, Patch


@dataclass
class _IncludeLoc:
    path: Path
    left: int
    right: int


class InlineIncludesPass(HintBasedPass):
    """Moves header's contents into the file that #include'd it, if it's included only from a single place.

    The reason we don't want to paste a header into multiple places is that this can result in the test case growing
    quickly, but more importantly it can result in the minimization getting stuck later due to the one-definition rule.

    Implementation-wise, relies on ClangIncludeGraphPass to extract the inclusion graph - this information is conveyed
    via the "@c-include" hints.
    """

    def check_prerequisites(self):
        return True

    def supports_dir_test_cases(self):
        return True

    def input_hint_types(self) -> list[bytes]:
        return [b'@c-include']

    def generate_hints(self, test_case: Path, dependee_hints: list[HintBundle], *args, **kwargs):
        path_to_inclusions: dict[Path, list[_IncludeLoc | None]] = {}
        for bundle in dependee_hints:
            for hint in bundle.hints:
                assert hint.extra is not None
                to_path = Path(bundle.vocabulary[hint.extra].decode())
                inclusions = path_to_inclusions.setdefault(to_path, [])
                if hint.patches:
                    for patch in hint.patches:
                        assert patch.path is not None
                        assert patch.left is not None
                        assert patch.right is not None
                        from_path = Path(bundle.vocabulary[patch.path].decode())
                        inclusions.append(_IncludeLoc(from_path, patch.left, patch.right))
                else:
                    inclusions.append(None)

        vocab = [b'paste']
        hints = []
        for to_path, inclusions in sorted(path_to_inclusions.items()):
            if len(inclusions) != 1:
                continue
            loc = inclusions[0]

            vocab.append(str(to_path).encode())
            header_path_id = len(vocab) - 1

            vocab.append(str(loc.path).encode())
            from_path_id = len(vocab) - 1

            size = (test_case / to_path).stat().st_size
            cut_patch = Patch(path=header_path_id, left=0, right=size)
            paste_patch = Patch(
                path=from_path_id,
                left=loc.left,
                right=loc.right,
                operation=0,  # "paste"
                value=header_path_id,
            )
            hints.append(Hint(patches=(cut_patch, paste_patch)))

        return HintBundle(hints=hints, vocabulary=vocab)
