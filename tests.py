import re
import subprocess

import pytest

from no_comments import DIRECTIVES, main, strip, violations

ALLOW = re.compile(DIRECTIVES)


def flagged(language: str, source: str) -> list:
    rows = set(range(source.count("\n") + 1))
    return violations(source.encode(), language, rows, "NC00", ALLOW)


def check(language: str, source: str) -> list[int]:
    return [block[-1].start_point.row for block in flagged(language, source)]


@pytest.mark.parametrize(
    ("language", "source", "expected"),
    [
        (
            "python",
            "# This comment makes sense, keep: NC00\n# This comment should raise\nx = 1\n",
            [1],
        ),
        ("python", "x = 1  # raise\n# kept\n# kept, keep: NC00\n", [0]),
        (
            "python",
            '#!/usr/bin/env python\n"""Docstring."""\nx = "# no"  # noqa: E501\n',
            [],
        ),
        (
            "typescript",
            "// this comment makes sense, keep: NC00\n// this comment should raise\n",
            [1],
        ),
        (
            "typescript",
            "/* this multiline comment\nshould not raise, keep: NC00 */\n/* raise\n*/\n",
            [2],
        ),
        (
            "tsx",
            '/** JSDoc */\nconst a = <a href="http://x" />  // @ts-expect-error\n',
            [],
        ),
        ("python", "# -*- coding: utf-8 -*-\nx = 1\n", []),
        ("ruby", "# frozen_string_literal: true\nx = 1\n", []),
        ("python", "# ruff: noqa\nx = 1  # pylint: disable=C0103\n", []),
        (
            "javascript",
            "/* istanbul ignore next */\nf(); // biome-ignore lint: x\n",
            [],
        ),
        ("go", "//go:generate x\nfunc f() {} //nolint:errcheck\n", []),
        ("bash", "# shellcheck disable=SC2086\necho $x\n", []),
        ("javascript", "const r = /\\/\\//; const s = `${1}//no`;\n", []),
        ("python", '"""Doc."""\n# keep-file: NC00\n# x\nimport os  # y\n', []),
        ("python", "import os\n# keep-file: NC00\n", [1]),
        ("typescript", "// keep-file: NC001\n// x\n", [1]),
        ("python", "# keep: this is X & Y\n# more\nx = 1  # keep: z\n", []),
        ("python", "# why, keep: X\n# not keep: first\n", [1]),
        ("typescript", "/* keep: why\n */\n", []),
        ("sql", "-- keep: why\n", []),
        ("xml", "<a>\n<!-- x -->\n<b/>\n<!-- y, keep: NC00 -->\n</a>\n", [1]),
        ("sql", "COMMENT ON TABLE t IS 'x';\n", []),
        ("csv", "a,b\n", []),
        ("rust", "/// Doc\n// x\n// y, keep: NC00\nfn f() {}\n", []),
        ("sql", "-- x\nSELECT 1; -- y, keep: NC00\n", [0]),
        ("html", "<!-- x, keep: NC00 -->\n<!-- y -->\n", [1]),
        ("python", "def f():\n    # a\n    # b, keep: NC00\n    return 1\n" * 300, []),
    ],
)
def test_violations(language: str, source: str, expected: list[int]) -> None:
    assert check(language, source) == expected


def test_main_reads_any_path_and_encoding(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init", "-q"], check=True)
    (tmp_path / "café.py").write_bytes(b"# caf\xe9\nx = 1\n")
    subprocess.run(["git", "add", "."], check=True)

    assert main(["café.py"]) == 1
    assert capsys.readouterr().out.startswith("café.py:1: ")


def test_main_checks_only_staged_lines(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git, "init", "-q"], check=True)
    (tmp_path / "a.py").write_text("# old\nx = 1\n")
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-qm", "init"], check=True)
    (tmp_path / "a.py").write_text("# old\nx = 1\n# new\n")
    subprocess.run([*git, "add", "."], check=True)

    assert main(["a.py", "--message", "no {code}", "--fix"]) == 1
    assert capsys.readouterr().out == "a.py:3: no NC00\n"
    assert (tmp_path / "a.py").read_text() == "# old\nx = 1\n"


@pytest.mark.parametrize(
    ("language", "source", "expected"),
    [
        ("python", "x = 1\n    # a\n    # b\ny = 2  # c\n", "x = 1\ny = 2\n"),
        ("python", "# kept, keep: NC00\nx = 1\n", "# kept, keep: NC00\nx = 1\n"),
        ("typescript", "a(/* x */ 1);\n  /* y */ b();\n", "a( 1);\n  b();\n"),
        ("typescript", "/* a\n b */\nc();\n// d", "c();\n"),
    ],
)
def test_strip(language: str, source: str, expected: str) -> None:
    nodes = [node for block in flagged(language, source) for node in block]
    assert strip(source.encode(), nodes).decode() == expected
