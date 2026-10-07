import re
import subprocess

import pytest

from keep_comments import DIRECTIVES, main, violations

ALLOW = re.compile(DIRECTIVES)


def check(suffix: str, source: str) -> list[int]:
    return violations(
        source.encode(), suffix, set(range(source.count("\n") + 1)), "DH00", ALLOW
    )


@pytest.mark.parametrize(
    ("suffix", "source", "expected"),
    [
        (
            ".py",
            "# This comment makes sense, keep: DH00\n# This comment should raise\nx = 1\n",
            [1],
        ),
        (".py", "x = 1  # raise\n# kept\n# kept, keep: DH00\n", [0]),
        (
            ".py",
            '#!/usr/bin/env python\n"""Docstring."""\nx = "# no"  # noqa: E501\n',
            [],
        ),
        (
            ".ts",
            "// this comment makes sense, keep: DH00\n// this comment should raise\n",
            [1],
        ),
        (
            ".ts",
            "/* this multiline comment\nshould not raise, keep: DH00 */\n/* raise\n*/\n",
            [2],
        ),
        (
            ".tsx",
            '/** JSDoc */\nconst a = <a href="http://x" />  // @ts-expect-error\n',
            [],
        ),
        (".js", "const r = /\\/\\//; const s = `${1}//no`;\n", []),
        (".py", "def f():\n    # a\n    # b, keep: DH00\n    return 1\n" * 300, []),
    ],
)
def test_violations(suffix: str, source: str, expected: list[int]) -> None:
    assert check(suffix, source) == expected


def test_main_checks_only_staged_lines(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git, "init", "-q"], check=True)
    (tmp_path / "a.py").write_text("# old\nx = 1\n")
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-qm", "init"], check=True)
    (tmp_path / "a.py").write_text("# old\nx = 1\n# new\n")
    subprocess.run([*git, "add", "."], check=True)

    assert main(["--code", "DH00", "a.py"]) == 1
    assert capsys.readouterr().out == "a.py:3: comment must end with 'keep: DH00'\n"
