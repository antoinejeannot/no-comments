# no-comments

A [pre-commit](https://pre-commit.com) hook that rejects new comments, unless they end with `keep: NC00`. It supports every language of [tree-sitter-language-pack](https://github.com/xberg-io/tree-sitter-language-pack) and skips other files.

```python
# This comment explains a tricky choice, keep: NC00
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
  rev: v0.5.0
  hooks:
    - id: no-comments
      files: \.(py|jsx?|tsx?)$
```

Without `files:`, the hook checks every supported language, YAML and shell included. On its first run, the hook downloads the grammars (about 25 MB) into its pre-commit environment, so a cache of `~/.cache/pre-commit` keeps them.

## Rules

- `args: [--code, XY00]` replaces the default code `NC00`.
- The hook checks only added or changed lines. Existing comments stay.
- Consecutive full-line comments are one block. The marker goes on the last line.
- `keep-file: <CODE>` in a comment before the first line of code skips the whole file.
- Docstrings, doc comments (`/** */`, `///`, `//!`) and tool directives are always allowed: shebang, `type:`, `noqa`, `pragma`, `fmt:`, `nosec`, `pyright:`, `mypy:`, `eslint`, `@ts-`, `/// <reference`, `prettier-ignore`. Add more with `--allow <regex>`.

## Diff range

Locally, the hook checks the staged diff. With `--from-ref` and `--to-ref`, it checks `from...to`. In CI, use the pull request target:

```sh
pre-commit run no-comments --from-ref origin/$GITHUB_BASE_REF --to-ref HEAD
```
