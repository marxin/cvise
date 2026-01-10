import os
import shutil
import signal
import stat
import subprocess
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

import pytest


def get_source_path(testcase: str) -> Path:
    return Path(__file__).parent / 'sources' / testcase


@pytest.fixture
def overridden_subprocess_tmpdir() -> Iterator[Path]:
    """Used to point the child process to a fake tmpdir, so that we can assert that it doesn't leave leftover files."""
    with tempfile.TemporaryDirectory(prefix='cvise-') as tmp_dir:
        yield Path(tmp_dir)


def start_cvise(arguments: list[str], tmp_path: Path, overridden_subprocess_tmpdir: Path) -> subprocess.Popen:
    binary = Path(__file__).parent.parent / 'cvise-cli.py'
    cmd = [str(binary)] + arguments

    new_env = os.environ.copy()
    new_env['TMPDIR'] = str(overridden_subprocess_tmpdir)

    return subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf8', env=new_env, cwd=tmp_path
    )


def check_cvise(
    testcase: str, arguments: list[str], expected: list[str], tmp_path: Path, overridden_subprocess_tmpdir: Path
) -> None:
    work_path = tmp_path / testcase
    shutil.copy(get_source_path(testcase), work_path)
    work_path.chmod(0o644)

    proc = start_cvise([testcase] + arguments, tmp_path, overridden_subprocess_tmpdir)
    stdout, stderr = proc.communicate()
    assert proc.returncode == 0, (
        f'Process failed with exit code {proc.returncode}; stderr:\n{stderr}\nstdout:\n{stdout}'
    )

    content = work_path.read_text()
    assert content in expected
    assert stat.filemode(work_path.stat().st_mode) == '-rw-r--r--'
    assert_subprocess_tmpdir_empty(overridden_subprocess_tmpdir)


def wait_until_file_created(path: Path):
    while not path.exists():
        time.sleep(0.1)


def assert_subprocess_tmpdir_empty(overridden_subprocess_tmpdir: Path) -> None:
    assert list(overridden_subprocess_tmpdir.iterdir()) == []


def test_simple_reduction(tmp_path: Path, overridden_subprocess_tmpdir: Path):
    check_cvise(
        'blocksort-part.c',
        ['-c', r"gcc -c blocksort-part.c && grep '\<nextHi\>' blocksort-part.c"],
        ['#define nextHi', '#define nextHi\n', '#undef nextHi', '#undef nextHi\n'],
        tmp_path,
        overridden_subprocess_tmpdir,
    )


def test_simple_reduction_no_interleaving_config(tmp_path: Path, overridden_subprocess_tmpdir: Path):
    check_cvise(
        'blocksort-part.c',
        ['-c', r"gcc -c blocksort-part.c && grep '\<nextHi\>' blocksort-part.c", '--pass-group', 'no-interleaving'],
        ['#define nextHi', '#define nextHi\n', '#undef nextHi', '#undef nextHi\n'],
        tmp_path,
        overridden_subprocess_tmpdir,
    )


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
@pytest.mark.parametrize('signum', [signal.SIGINT, signal.SIGTERM], ids=['sigint', 'sigterm'])
@pytest.mark.parametrize('additional_delay', [0, 1, 10])
def test_kill(tmp_path: Path, overridden_subprocess_tmpdir: Path, signum: int, additional_delay: int):
    """Test that Control-C is handled quickly, without waiting for jobs to finish."""
    MAX_SHUTDOWN = 60  # in seconds; tolerance to prevent flakiness (normally it's a fraction of a second)
    JOB_SLOWNESS = MAX_SHUTDOWN * 2  # make a single job slower than the thresholds
    N = 5  # don't use very high parallelism since it'd skew timings

    shutil.copy(get_source_path('blocksort-part.c'), tmp_path)
    flag_file = tmp_path / 'flag'

    proc = start_cvise(
        [
            'blocksort-part.c',
            '-c',
            f'gcc -c blocksort-part.c && touch {flag_file} && sleep {JOB_SLOWNESS}',
            '--skip-interestingness-test-check',
            '-n',
            str(N),
        ],
        tmp_path,
        overridden_subprocess_tmpdir,
    )
    # to make the test cover the interesting scenario, we wait until C-Vise starts at least one job
    wait_until_file_created(flag_file)
    # extra wait for more variance in test scenarios
    time.sleep(additional_delay)

    proc.send_signal(signum)
    try:
        proc.communicate(timeout=MAX_SHUTDOWN)
    except TimeoutError:
        # C-Vise has not quit on time - kill it and fail the test
        proc.kill()
        raise
    assert_subprocess_tmpdir_empty(overridden_subprocess_tmpdir)


def test_interleaving_lines_passes(tmp_path: Path, overridden_subprocess_tmpdir: Path):
    """Test a pass group config with an interleaving category."""
    config_path = tmp_path / 'config.json'
    config_path.write_text("""
        {"interleaving": [
            {"pass": "lines", "arg": "0"},
            {"pass": "lines", "arg": "1"},
            {"pass": "lines", "arg": "2"}
         ]
        }""")

    testcase_path = tmp_path / 'test.c'
    testcase_path.write_text("""
        int bar() {
          return 42;
        }
        int foo() {
          return bar();
        }
        int main() {
          return foo();
        }
        """)

    proc = start_cvise(
        ['-c', 'gcc -c test.c && grep foo test.c', '--pass-group-file', str(config_path), testcase_path.name],
        tmp_path,
        overridden_subprocess_tmpdir,
    )
    stdout, stderr = proc.communicate()
    assert proc.returncode == 0, (
        f'Process failed with exit code {proc.returncode}; stderr:\n{stderr}\nstdout:\n{stdout}'
    )
    assert (
        testcase_path.read_text()
        == """
        int foo() {
        }
        """
    )
    assert_subprocess_tmpdir_empty(overridden_subprocess_tmpdir)


def test_apply_hints(tmp_path: Path, overridden_subprocess_tmpdir: Path):
    """Test the application of hints via the --action=apply-hints mode."""
    hints_path = tmp_path / 'hints.jsonl'
    hints_path.write_text(
        """{"format": "cvise_hints_v0"}
        []
        {"p": [{"l": 0, "r": 1}]}
        {"p": [{"l": 1, "r": 2}]}
        {"p": [{"l": 2, "r": 3}]}
        """
    )

    input_path = tmp_path / 'input.txt'
    input_path.write_text('abcd')

    proc = start_cvise(
        [
            '--action=apply-hints',
            '--hints-file',
            str(hints_path),
            '--hint-begin-index=1',
            '--hint-end-index=3',
            str(input_path),
        ],
        tmp_path,
        overridden_subprocess_tmpdir,
    )
    stdout, stderr = proc.communicate()
    assert proc.returncode == 0, (
        f'Process failed with exit code {proc.returncode}; stderr:\n{stderr}\nstdout:\n{stdout}'
    )
    assert stdout == 'ad'
    assert_subprocess_tmpdir_empty(overridden_subprocess_tmpdir)


def test_non_ascii(tmp_path: Path, overridden_subprocess_tmpdir: Path):
    testcase_path = tmp_path / 'test.c'
    testcase_path.write_bytes(b"""
        // nonutf\xff
        int foo;
        char *s = "Streichholzsch\xc3\xa4chtelchen";
        """)

    # Also enable diff logging to check it doesn't break on non-unicode.
    proc = start_cvise(
        ['-c', 'gcc -c -Wall -Werror test.c && grep foo test.c', testcase_path.name, '--print-diff'],
        tmp_path,
        overridden_subprocess_tmpdir,
    )
    stdout, stderr = proc.communicate()

    assert proc.returncode == 0, (
        f'Process failed with exit code {proc.returncode}; stderr:\n{stderr}\nstdout:\n{stdout}'
    )
    # The reduced result may or may not include the trailing line break - this depends on random ordering factors.
    assert testcase_path.read_text() in ('int foo;', 'int foo;\n')
    assert_subprocess_tmpdir_empty(overridden_subprocess_tmpdir)
    assert 'Streichholz' in stderr


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_non_ascii_interestingness_test(tmp_path: Path, overridden_subprocess_tmpdir: Path):
    """Test no breakage caused by non-UTF-8 characters printed by the interestingness test"""
    shutil.copy(get_source_path('blocksort-part.c'), tmp_path)
    check_cvise(
        'blocksort-part.c',
        ['-c', r"printf '\xc3\xa4\xff'; gcc -c blocksort-part.c && grep '\<nextHi\>' blocksort-part.c"],
        ['#define nextHi', '#define nextHi\n', '#undef nextHi', '#undef nextHi\n'],
        tmp_path,
        overridden_subprocess_tmpdir,
    )


def test_dir_test_case(tmp_path: Path, overridden_subprocess_tmpdir: Path):
    test_case = tmp_path / 'repro'
    test_case.mkdir()
    (test_case / 'a.h').write_text('// comment\nint x = 1;\n')
    (test_case / 'a.cc').write_text('#include "a.h"\nint nextHi = x;\n')

    proc = start_cvise(
        [
            '-c',
            'gcc -c repro/a.cc && grep "nextHi = x" repro/a.cc',
            'repro',
        ],
        tmp_path,
        overridden_subprocess_tmpdir,
    )
    stdout, stderr = proc.communicate()

    assert proc.returncode == 0, (
        f'Process failed with exit code {proc.returncode}; stderr:\n{stderr}\nstdout:\n{stdout}'
    )
    assert (test_case / 'a.h').read_text() == 'int x ;\n'
    assert (test_case / 'a.cc').read_text() == '#include "a.h"\nint nextHi = x;\n'


def test_dir_linker_duplicate_var_error(tmp_path: Path, overridden_subprocess_tmpdir: Path):
    """Test reducing headers and a makefile for a link-time error due to duplicate variables.

    Here we had to hardcode particular error messages from real linkers.
    """
    ERROR_REGEX = 'multiple|duplicate'

    test_case = tmp_path / 'repro'
    test_case.mkdir()
    (test_case / 'h1.h').write_text('int x;\n')
    (test_case / 'h2.h').write_text('#include "h1.h"\n')
    (test_case / 'src1.c').write_text('#include "h2.h"\n')
    (test_case / 'src2.c').write_text('// duplicate!\nint x;\n')
    (test_case / 'src3.c').write_text('int main() {\n}\n')
    (test_case / 'Makefile').write_text(
        """.PHONY: all clean
all: prog
src1.o:
\tgcc -Werror -c src1.c
src2.o:
\tgcc -Werror -c src2.c
src3.o:
\tgcc -Werror -c src3.c
prog: src1.o src2.o src3.o
\tgcc -o prog src1.o src2.o src3.o
clean:
\trm -f src1.o src2.o src3.o prog
"""
    )

    # Use awk instead of grep to easily see the whole build log if the test fails.
    proc = start_cvise(
        [
            '-c',
            f"(make -C repro 2>&1 || true) | awk '{{ print }} /{ERROR_REGEX}/ {{ y=1 }} END {{ exit !y }}'",
            'repro',
            '--tidy',
        ],
        tmp_path,
        overridden_subprocess_tmpdir,
    )
    stdout, stderr = proc.communicate()

    assert proc.returncode == 0, (
        f'Process failed with exit code {proc.returncode}; stderr:\n{stderr}\nstdout:\n{stdout}'
    )
    assert _read_files_in_dir(test_case) == {
        'Makefile': """.PHONY: all clean
all: prog
src1.o:
\tgcc -Werror -c src1.c
src2.o:
\tgcc -Werror -c src2.c
prog: src1.o src2.o
\tgcc -o prog src1.o src2.o
clean:
\trm -f src1.o src2.o prog
""",
        'src1.c': 'int x;\n',
        'src2.c': 'int x;\n',
    }


def test_dir_fibonacci_test_case(tmp_path: Path, overridden_subprocess_tmpdir: Path):
    """Test reducing headers for a compile-time Fibonacci sequence evaluation.

    To prevent C-Vise from deleting compile-time calculations, our makefile checks that the compilation fails iff a
    preprocessor definition (used in a compile-time assert) is nonzero.
    """
    test_case = tmp_path / 'repro'
    test_case.mkdir()
    (test_case / 'head1.h').write_text(
        """
#ifndef HEAD1_H_
#define HEAD1_H_

// Fibonacci sequence, induction step.
template <int N>
struct Fib {
  static constexpr int value = Fib<N - 1>::value + Fib<N - 2>::value;
};

#endif  // HEAD1_H_
"""
    )
    (test_case / 'head2.h').write_text(
        """
#ifndef HEAD2_H_
#define HEAD2_H_

#include "head1.h"

// Fibonacci sequence, base steps.
template <>
struct Fib<0> {
    static constexpr int value = 0;
};
template <>
struct Fib<1> {
    static constexpr int value = 1;
};

#endif  // HEAD2_H_
"""
    )
    (test_case / 'head3.h').write_text(
        """
#ifndef HEAD3_H_
#define HEAD3_H_

#include <vector>

std::vector<int> Foo() {
    return {1, 2, 3};
}

#endif  // HEAD3_H_
"""
    )
    (test_case / 'src1.cc').write_text(
        """
#include "head2.h"
#include "head3.h"
static_assert(Fib<6>::value == 8 + DISTURB, "unexpected Fibonacci value #6");
"""
    )
    (test_case / 'src2.cc').write_text('// unrelated\nint x;\n')
    (test_case / 'src3.cc').write_text('int main() {\n}\n')
    (test_case / 'Makefile').write_text(
        """.PHONY: all sanity
all: prog sanity
prog: src1.o src2.o src3.o
\tg++ -o prog -lstdc++ src1.o src2.o src3.o
src1.o:
\tg++ -c -DDISTURB=0 src1.cc
src2.o:
\tg++ -c src2.cc
src3.o:
\tg++ -c src3.cc
sanity:
\tg++ -c -DDISTURB=0 src1.cc
\t! g++ -c -DDISTURB=1 src1.cc
"""
    )

    # Use awk instead of grep to easily see the whole build log if the test fails.
    proc = start_cvise(
        [
            '-c',
            'make -C repro',
            'repro',
        ],
        tmp_path,
        overridden_subprocess_tmpdir,
    )
    stdout, stderr = proc.communicate()

    assert proc.returncode == 0, (
        f'Process failed with exit code {proc.returncode}; stderr:\n{stderr}\nstdout:\n{stdout}'
    )
    assert _read_files_in_dir(test_case) == {
        'Makefile': """.PHONY: all sanity
all: sanity
sanity:
\tg++ -c -DDISTURB=0 src1.cc
\t! g++ -c -DDISTURB=1 src1.cc
""",
        'src1.cc': """template <int N>
struct Fib {
  static constexpr int value = Fib<N - 1>::value + Fib<N - 2>::value;
};
template <>
struct Fib<0> {
    static constexpr int value = 0;
};
template <>
struct Fib<1> {
    static constexpr int value = 1;
};
static_assert(Fib<6>::value == 8 + DISTURB);
""",
    }


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_script_inside_test_case_error(tmp_path: Path, overridden_subprocess_tmpdir: Path):
    test_case = tmp_path / 'repro'
    test_case.mkdir()
    (test_case / 'foo.txt').touch()
    interestingness_test = test_case / 'check.sh'
    interestingness_test.write_text('#!/bin/sh\ntrue\n')
    interestingness_test.chmod(interestingness_test.stat().st_mode | stat.S_IEXEC)

    proc = start_cvise(
        [
            str(interestingness_test),
            'repro',
            '--tidy',
            '--no-cache',
        ],
        tmp_path,
        overridden_subprocess_tmpdir,
    )
    stdout, stderr = proc.communicate()

    assert proc.returncode != 0, f'Process succeeded unexpectedly; stderr:\n{stderr}\nstdout:\n{stdout}'
    assert 'is inside test case directory' in stderr


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_non_ascii_dir_test_case(tmp_path: Path, overridden_subprocess_tmpdir: Path):
    test_case = tmp_path / 'repro'
    test_case.mkdir()
    a_path = test_case / 'a.c'
    b_path = test_case / 'b.c'
    a_path.write_bytes(b"""
        // nonutf\xff
        int foo;
        char *s = "Streichholzsch\xc3\xa4chtelchen";
        """)
    b_path.write_bytes(b"""
        int main() {}
        """)

    # Also enable diff logging to check it doesn't break on non-unicode.
    proc = start_cvise(
        [
            '-c',
            'gcc -c -Wall -Werror repro/*.c && grep foo repro/*.c',
            'repro',
            '--print-diff',
        ],
        tmp_path,
        overridden_subprocess_tmpdir,
    )
    stdout, stderr = proc.communicate()

    assert proc.returncode == 0, (
        f'Process failed with exit code {proc.returncode}; stderr:\n{stderr}\nstdout:\n{stdout}'
    )
    assert a_path.read_text() in ('int foo;', 'int foo;\n')
    assert not b_path.exists() or b_path.read_text() == ''
    assert 'Streichholz' in stderr


def test_failing_interestingness_test(tmp_path: Path, overridden_subprocess_tmpdir: Path):
    testcase_path = tmp_path / 'test.c'
    testcase_path.write_text('foo')

    proc = start_cvise(
        ['test.c', '-c', 'gcc test.c'],
        tmp_path,
        overridden_subprocess_tmpdir,
    )
    stdout, stderr = proc.communicate()

    assert proc.returncode != 0, f'Process succeeded unexpectedly; stderr:\n{stderr}\nstdout:\n{stdout}'
    assert 'interestingness test does not return' in stdout


def _read_files_in_dir(dir: Path) -> dict[str, str]:
    return {str(p.relative_to(dir)): p.read_text() for p in dir.rglob('*') if not p.is_dir()}
