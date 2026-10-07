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
  rev: v0.8.0
  hooks:
    - id: no-comments
      files: \.(py|jsx?|tsx?)$
```

Without `files:`, the hook checks every supported language, YAML and shell included. On its first run, the hook downloads the grammars (about 25 MB) into its pre-commit environment, so a cache of `~/.cache/pre-commit` keeps them.

## Rules

- `args: [--code, XY00]` replaces the default code `NC00`.
- `args: [--message, "..."]` replaces the error message. `{code}` is replaced by the code.
- `args: [--fix]` deletes the flagged comments. The hook still fails, so you can review the change.
- The hook checks only added or changed lines. Existing comments stay.
- Consecutive full-line comments are one block. `keep:` goes at the start of its first line, or `keep: <CODE>` at the end of its last line.
- `keep-file: <CODE>` in a comment before the first line of code skips the whole file.
- Docstrings, doc comments (`/** */`, `///`, `//!`) and tool directives are always allowed, for example `noqa`, `type:`, `ruff:`, `eslint`, `@ts-`, `istanbul ignore`, `nolint`, `shellcheck` or `rubocop:` (see `DIRECTIVES` in `no_comments.py`).

## Allow more comments

`--allow <regex>` adds a pattern to the allowlist. The pattern must match the start of the comment text, after `#`, `//` or `/*`. Use it for TODO, FIXME or other tool directives:

```yaml
    - id: no-comments
      args: [--allow, "TODO|FIXME"]
```

`# TODO: retry later` and `// FIXME: race` pass, but `# a TODO later` fails. An allowed comment ends its block, so the next comment line needs its own marker.

## Diff range

Locally, the hook checks the staged diff. With `--from-ref` and `--to-ref`, it checks `from...to`. In CI, use the pull request target:

```sh
pre-commit run no-comments --from-ref origin/$GITHUB_BASE_REF --to-ref HEAD
```
