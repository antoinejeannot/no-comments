# no-comments

A [pre-commit](https://pre-commit.com) hook that rejects new comments, unless they start with `keep:` or end with `keep: NC00`. It supports every language of [tree-sitter-language-pack](https://github.com/xberg-io/tree-sitter-language-pack) and skips other files.

```python
# This comment explains a tricky choice, keep: NC00
# keep: this comment passes too
# This comment fails
```

```ts
// This comment fails
/* This block comment
passes, keep: NC00 */
```

## Usage

```yaml
- repo: https://github.com/antoinejeannot/no-comments
  rev: v0.10.1
  hooks:
    - id: no-comments
      files: \.(py|jsx?|tsx?)$
```

Without `files:`, the hook checks every supported language, YAML and shell included. On its first run, the hook downloads the grammars (about 25 MB) into its pre-commit environment, so a cache of `~/.cache/pre-commit` keeps them.

For a fixed, verifiable install, pin a commit instead of a tag: `pre-commit autoupdate --freeze` writes `rev: <sha>  # frozen: v0.10.1`. The dependencies have exact versions, and `tree-sitter-language-pack` checks the SHA-256 of the grammars it downloads.

## Rules

- `args: [--code, XY00]` replaces the default code `NC00`.
- `args: [--message, "..."]` replaces the error message. `{code}` is replaced by the code.
- `args: [--fix]` deletes the flagged comments. The hook still fails, so you can review the change.
- The hook checks only added or changed lines. Existing comments stay.
- Consecutive full-line comments are one block. `keep:` goes at the start of its first line, or `keep: <CODE>` at the end of its last line.
- A comment with only `keep: <CODE>`, for example `# keep: NC00`, before the first line of code skips the whole file.
- Docstrings, doc comments (`/** */`, `///`, `//!`) and tool directives are always allowed, for example `noqa`, `type:`, `ruff:`, `eslint`, `@ts-`, `istanbul ignore`, `nolint`, `shellcheck` or `rubocop:`, encoding or magic comments like `# -*- coding: utf-8 -*-`, and version pins like `# v1.2.3` or `# frozen: v1.2.3` (see `DIRECTIVES` in `no_comments.py`).

## Allow more comments

`--allow <regex>` adds a pattern to the allowlist. The pattern must match the start of the comment text, after `#`, `//` or `/*`. Use it for TODO, FIXME or other tool directives:

```yaml
    - id: no-comments
      args: [--allow, "TODO|FIXME"]
```

`# TODO: retry later` and `// FIXME: race` pass, but `# a TODO later` fails. An allowed comment ends its block, so the next comment line needs its own marker.

## GitHub CI

Locally, the hook checks the staged diff. In a pull request, the `no-comments check` action checks the pull request diff. It uses the hook settings in your `.pre-commit-config.yaml`, and it caches the hook and its grammars.

```yaml
on:
  pull_request:

jobs:
  no-comments:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: antoinejeannot/no-comments@v0.10.1
```

Without the action, run `pre-commit run no-comments --from-ref HEAD^1 --to-ref HEAD` after a checkout with `fetch-depth: 2`. A `pre-commit run --all-files` step passes this hook, because nothing is staged in CI.
