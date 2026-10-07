# keep-comments

A [pre-commit](https://pre-commit.com) hook that rejects new comments in Python, JavaScript and TypeScript, unless they end with `keep: <CODE>`.

```python
# This comment explains a tricky choice, keep: DH00
# This comment fails
```

```ts
// This comment fails
/* This block comment
passes, keep: DH00 */
```

## Usage

```yaml
- repo: https://github.com/antoinejeannot/keep-comments
  rev: v0.1.0
  hooks:
    - id: keep-comments
      args: [--code, DH00]
```

## Rules

- The hook checks only added or changed lines. Existing comments stay.
- Consecutive full-line `#` or `//` comments are one block. The marker goes on the last line.
- Docstrings, JSDoc (`/** */`) and tool directives are always allowed: shebang, `type:`, `noqa`, `pragma`, `fmt:`, `nosec`, `pyright:`, `mypy:`, `eslint`, `@ts-`, `/// <reference`, `prettier-ignore`. Add more with `--allow <regex>`.

## Diff range

Locally, the hook checks the staged diff. With `--from-ref` and `--to-ref`, it checks `from...to`. In CI, use the pull request target:

```sh
pre-commit run keep-comments --from-ref origin/$GITHUB_BASE_REF --to-ref HEAD
```
