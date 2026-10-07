import argparse
import os
import re
import subprocess
import sys
from collections import defaultdict
from functools import cache
from pathlib import Path

from tree_sitter import Node, Query, QueryCursor, Tree
from tree_sitter_language_pack import (
    PackConfig,
    configure,
    detect_language_from_path,
    get_language,
    get_parser,
)

DOCS = ("/**", "///", "//!")
DIRECTIVES = (
    r"!|type:|noqa\b|pragma\b|fmt:|nosec\b|pyright:|mypy:|ruff:|pylint:|flake8:"
    r"|isort:|pyre-ignore|eslint|@ts-|/ <reference|prettier-ignore|biome-ignore"
    r"|deno-lint-ignore|(istanbul|c8|v8) ignore|nolint\b|go:|NOLINT|clang-format"
    r"|shellcheck\b|hadolint\b|yamllint\b|tfsec:|checkov:|trivy:|tflint-ignore"
    r"|rubocop:|noinspection\b|checkstyle:|-\*-|(en)?coding[:=]|frozen_string_literal:"
)
PREFIX = re.compile(r"^(#|//|/\*)\s*")
KEEP = re.compile(r"^\W*keep:")
HUNK = re.compile(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@")


@cache
def query(language: str) -> Query | None:
    grammar = get_language(language)
    kinds = {
        grammar.node_kind_for_id(i)
        for i in range(grammar.node_kind_count)
        if grammar.node_kind_is_named(i) and grammar.node_kind_is_visible(i)
    }
    # Grammars name them `comment`, `line_comment`, `block_comment`...
    patterns = [
        f"({kind})"
        for kind in sorted(kinds)
        if kind.lower().endswith("comment") and not kind.startswith("keyword")
    ]
    return Query(grammar, f"[{' '.join(patterns)}] @comment") if patterns else None


def comments(tree: Tree, language: str) -> list[Node]:
    if not (comment_query := query(language)):
        return []
    nodes = QueryCursor(comment_query).captures(tree.root_node).get("comment", [])
    return sorted(
        (node for node in nodes if "comment" not in node.parent.type),
        key=lambda node: node.start_byte,
    )


def blocks(
    source: bytes, nodes: list[Node], allow: re.Pattern[str]
) -> list[list[Node]]:
    lines = source.splitlines()
    result: list[list[Node]] = []
    previous = None
    for node in nodes:
        text = node.text.decode(errors="replace")
        if text.startswith(DOCS) or allow.match(PREFIX.sub("", text)):
            previous = None
            continue
        row, column = node.start_point
        alone = "\n" not in text.rstrip() and not lines[row][:column].strip()
        if alone and previous and row == previous.start_point.row + 1:
            result[-1].append(node)
        else:
            result.append([node])
        previous = node if alone else None
    return result


def violations(
    source: bytes, language: str, rows: set[int], code: str, allow: re.Pattern[str]
) -> list[list[Node]]:
    marker = re.compile(rf"keep: {re.escape(code)}\W*$")
    tree = get_parser(language).parse(source)
    nodes = comments(tree, language)
    code_start = next(
        (
            node.start_byte
            for node in tree.root_node.named_children
            if "comment" not in node.type and node.type != "string"
        ),
        len(source),
    )
    file_marker = re.compile(rf"^\W*keep: {re.escape(code)}\W*$")
    if any(
        file_marker.match(node.text.decode(errors="replace"))
        for node in nodes
        if node.start_byte < code_start
    ):
        return []
    return [
        block
        for block in blocks(source, nodes, allow)
        if rows.intersection(
            range(block[0].start_point.row, block[-1].end_point.row + 1)
        )
        and not KEEP.match(block[0].text.decode(errors="replace"))
        and not marker.search(block[-1].text.decode(errors="replace"))
    ]


def strip(source: bytes, nodes: list[Node]) -> bytes:
    for node in sorted(nodes, key=lambda node: node.start_byte, reverse=True):
        start, end = node.start_byte, node.end_byte
        while start and source[start - 1] in b" \t":
            start -= 1
        while end < len(source) and source[end] in b" \t\r":
            end += 1
        if start and source[start - 1] != ord("\n"):
            end = node.end_byte
        elif end == len(source) or source[end] == ord("\n"):
            end += 1
        else:
            start = node.start_byte
        source = source[:start] + source[end:]
    return source


def added_rows(filenames: list[str]) -> dict[str, set[int]]:
    source = os.environ.get("PRE_COMMIT_FROM_REF")
    target = os.environ.get("PRE_COMMIT_TO_REF")
    revisions = [f"{source}...{target}"] if source and target else ["--cached"]
    diff = subprocess.run(
        [
            "git",
            "-c",
            "core.quotePath=false",
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
        errors="replace",
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
    parser.add_argument("--code", default="NC00")
    parser.add_argument(
        "--message",
        default="comment not allowed, start it with 'keep:' or end it with 'keep: {code}'",
    )
    parser.add_argument("--fix", action="store_true", help="drop flagged comments")
    parser.add_argument(
        "--allow", action="append", default=[DIRECTIVES], help="extra directive regex"
    )
    parser.add_argument("filenames", nargs="*")
    args = parser.parse_args(argv)
    allow = re.compile("|".join(f"(?:{pattern})" for pattern in args.allow))
    # Grammars live and get cached with the pre-commit environment.
    configure(PackConfig(cache_dir=sys.prefix))
    added = added_rows(args.filenames)
    failed = 0
    for filename in args.filenames:
        language = detect_language_from_path(filename)
        if language and (rows := added.get(filename)):
            path = Path(filename)
            source = path.read_bytes()
            flagged = violations(source, language, rows, args.code, allow)
            for block in flagged:
                row = block[-1].start_point.row + 1
                print(f"{filename}:{row}: {args.message.format(code=args.code)}")
                failed = 1
            if args.fix and flagged:
                path.write_bytes(
                    strip(source, [node for block in flagged for node in block])
                )
    return failed
