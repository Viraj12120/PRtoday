# 1. Use Python (Typer and Rich) for the Terminal CLI

Date: 2026-06-03

## Status

Accepted

## Context

We need to build a highly aesthetic, minimal, dense, and terminal-first Developer CLI for PR Sentinel. The user specifically requested a design that mimics terminal dashboards like `k9s` or `htop` (with Panels, Borders, specific colors, and JetBrains Mono).
Initially, we considered Node.js with `commander`, `chalk`, and `cli-table3`. 

## Decision

We have decided to pivot and build the CLI in **Python 3.10+** using:
1. **Typer**: For modern, type-hinted argument parsing and CLI command orchestration.
2. **Rich**: For rendering advanced terminal UIs, including layout panels, syntax-highlighted tables, loading spinners, and strict hex color palettes.

## Consequences

### Positive
- **Aesthetics**: `Rich` provides unparalleled terminal formatting capabilities out-of-the-box, allowing us to easily meet the strict visual design requirements.
- **AI Integration**: The Python ecosystem has the most robust and mature support for AI integrations (Hugging Face Inference API, `litellm`), which is crucial for the AI Review Engine.
- **Type Safety**: Typer natively leverages Python type hints, matching the requested focus on developer ergonomics.

### Negative
- **Distribution**: Distributing Python CLI apps can be slightly more complex than `npm i -g`, but tools like `pipx` or standard package managers solve this effectively.
