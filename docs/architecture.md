# Architecture

PR Sentinel is a pure Python Terminal CLI application built for performance, aesthetics, and deterministic analysis.

## Core Components

### 1. CLI Layer (`pr_sentinel.cli`)
- Built using **Typer**.
- Handles argument parsing, routing to subcommands (`analyze`, `history`, `auth`), and orchestration.

### 2. UI Layer (`pr_sentinel.ui`)
- Built using **Rich**.
- Responsible for rendering Panels, Tables, and formatted text directly to stdout.
- Implements the strict color palette and layout constraints.

### 3. GitHub Client (`pr_sentinel.github`)
- Wraps `PyGithub` and `httpx`.
- Fetches PR metadata, diffs, commits, and repository structure.

### 4. Risk Engine (`pr_sentinel.risk`)
- **Deterministic scoring algorithm.**
- Analyzes diffs using AST parsing or regex to identify DB migrations, config changes, and test coverage gaps.
- Outputs a normalized score (0-100) and discrete risk factors.

### 5. AI Engine (`pr_sentinel.ai`)
- Integrates with Hugging Face Inference API via `huggingface_hub` or `litellm`.
- Uses Qwen/DeepSeek models for summarization and failure prediction.
- Implements strict prompting strategies and cost-optimization caching.

### 6. Database Layer (`pr_sentinel.db`)
- Uses **SQLAlchemy** over a local SQLite database (`~/.pr_sentinel/history.db`).
- Stores historical analysis runs for the `history` command.

## Data Flow (Analyze Command)
1. User invokes `pr-sentinel analyze --repo X --pr Y`.
2. CLI Layer parses arguments.
3. GitHub Client fetches PR data (Diff, Commits, Files).
4. Risk Engine calculates deterministic score & blast radius.
5. AI Engine generates summary and predictions based on the diff.
6. DB Layer persists the result.
7. UI Layer renders the final Dashboard to the terminal.
