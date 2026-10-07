import re
import subprocess

import pytest

from keep_comments import DIRECTIVES, main, violations

ALLOW = re.compile(DIRECTIVES)


def check(language: str, source: str) -> list[int]:
    return violations(
        source.encode(), language, set(range(source.count("\n") + 1)), "KC00", ALLOW
    )


@pytest.mark.parametrize(
    ("language", "source", "expected"),
    [
        (
            "python",
            "# This comment makes sense, keep: KC00\n# This comment should raise\nx = 1\n",
            [1],
        ),
        ("python", "x = 1  # raise\n# kept\n# kept, keep: KC00\n", [0]),
        (
            "python",
            '#!/usr/bin/env python\n"""Docstring."""\nx = "# no"  # noqa: E501\n',
            [],
        ),
        (
            "typescript",
            "// this comment makes sense, keep: KC00\n// this comment should raise\n",
            [1],
        ),
        (
            "typescript",
            "/* this multiline comment\nshould not raise, keep: KC00 */\n/* raise\n*/\n",
            [2],
        ),
        (
            "tsx",
            '/** JSDoc */\nconst a = <a href="http://x" />  // @ts-expect-error\n',
            [],
        ),
        ("javascript", "const r = /\\/\\//; const s = `${1}//no`;\n", []),
        ("python", '"""Doc."""\n# keep-file: KC00\n# x\nimport os  # y\n', []),
        ("python", "import os\n# keep-file: KC00\n", [1]),
        ("typescript", "// keep-file: KC001\n// x\n", [1]),
        ("rust", "/// Doc\n// x\n// y, keep: KC00\nfn f() {}\n", []),
        ("sql", "-- x\nSELECT 1; -- y, keep: KC00\n", [0]),
        ("html", "<!-- x, keep: KC00 -->\n<!-- y -->\n", [1]),
        ("python", "def f():\n    # a\n    # b, keep: KC00\n    return 1\n" * 300, []),
    ],
)
def test_violations(language: str, source: str, expected: list[int]) -> None:
    assert check(language, source) == expected


def test_main_checks_only_staged_lines(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git, "init", "-q"], check=True)
    (tmp_path / "a.py").write_text("# old\nx = 1\n")
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-qm", "init"], check=True)
    (tmp_path / "a.py").write_text("# old\nx = 1\n# new\n")
    subprocess.run([*git, "add", "."], check=True)

    assert main(["a.py"]) == 1
    assert capsys.readouterr().out == "a.py:3: comment must end with 'keep: KC00'\n"
