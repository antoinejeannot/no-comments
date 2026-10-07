import argparse
import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path

import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_typescript
from tree_sitter import Language, Node, Parser, Query, QueryCursor

LANGUAGES = {
    ".py": tree_sitter_python.language(),
    ".js": tree_sitter_javascript.language(),
    ".jsx": tree_sitter_javascript.language(),
    ".ts": tree_sitter_typescript.language_typescript(),
    ".tsx": tree_sitter_typescript.language_tsx(),
}
DIRECTIVES = (
    r"!|type:|noqa\b|pragma\b|fmt:|nosec\b|pyright:|mypy:"
    r"|eslint|@ts-|/ <reference|prettier-ignore"
)
PREFIX = re.compile(r"^(#|//|/\*)\s*")
HUNK = re.compile(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@")


def blocks(
    source: bytes, nodes: list[Node], allow: re.Pattern[str]
) -> list[list[Node]]:
    lines = source.splitlines()
    result: list[list[Node]] = []
    previous = None
    for node in nodes:
        text = node.text.decode()
        if text.startswith("/**") or allow.match(PREFIX.sub("", text)):
            previous = None
            continue
        row, column = node.start_point
        alone = text.startswith(("#", "//")) and not lines[row][:column].strip()
        if alone and previous and row == previous.end_point.row + 1:
            result[-1].append(node)
        else:
            result.append([node])
        previous = node if alone else None
    return result


def violations(
    source: bytes, suffix: str, rows: set[int], code: str, allow: re.Pattern[str]
) -> list[int]:
    marker = re.compile(rf"keep: {re.escape(code)}\s*(\*/)?$")
    language = Language(LANGUAGES[suffix])
    tree = Parser(language).parse(source)
    query = QueryCursor(Query(language, "(comment) @comment"))
    nodes = sorted(
        query.captures(tree.root_node).get("comment", []),
        key=lambda node: node.start_byte,
    )
    return [
        block[-1].start_point.row
        for block in blocks(source, nodes, allow)
        if rows.intersection(
            range(block[0].start_point.row, block[-1].end_point.row + 1)
        )
        and not marker.search(block[-1].text.decode())
    ]


def added_rows(filenames: list[str]) -> dict[str, set[int]]:
    source = os.environ.get("PRE_COMMIT_FROM_REF")
    target = os.environ.get("PRE_COMMIT_TO_REF")
    revisions = [f"{source}...{target}"] if source and target else ["--cached"]
    diff = subprocess.run(
        [
            "git",
            "diff",
            "-U0",
            "--no-color",
            "--no-ext-diff",
            "--no-prefix",
            *revisions,
            "--",
            *filenames,
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    added: dict[str, set[int]] = defaultdict(set)
    path = ""
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[4:]
        elif match := HUNK.match(line):
            start = int(match[1]) - 1
            added[path].update(range(start, start + int(match[2] or 1)))
    return added


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reject new comments unless they end with `keep: <CODE>`."
    )
    parser.add_argument("--code", required=True)
    parser.add_argument(
        "--allow", action="append", default=[DIRECTIVES], help="extra directive regex"
    )
    parser.add_argument("filenames", nargs="*")
    args = parser.parse_args(argv)
    allow = re.compile("|".join(f"(?:{pattern})" for pattern in args.allow))
    added = added_rows(args.filenames)
    failed = 0
    for filename in args.filenames:
        if rows := added.get(filename):
            path = Path(filename)
            for row in violations(
                path.read_bytes(), path.suffix, rows, args.code, allow
            ):
                print(
                    f"{filename}:{row + 1}: comment must end with 'keep: {args.code}'"
                )
                failed = 1
    return failed
