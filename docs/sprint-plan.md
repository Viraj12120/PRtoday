# Sprint Plan

We strictly follow an Agile/Scrum execution model.

## Sprint 0: Project Setup
- **Goal:** Establish monorepo structure, stack validation, and core documentation.
- **Deliverables:** `pyproject.toml`, `README.md`, `prd.md`, `architecture.md`, `user-flow.md`, `sprint-plan.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, initial ADR.

## Sprint 1: CLI Foundation & GitHub Integration
- **Goal:** Build the CLI skeleton and connect to GitHub.
- **Tasks:**
  - Implement Typer CLI entrypoint.
  - Implement `auth` command.
  - Implement GitHub client to fetch PR data, diffs, and files changed.
  - Write unit tests for GitHub client.

## Sprint 2: Risk Engine (Deterministic)
- **Goal:** Implement the deterministic scoring logic.
- **Tasks:**
  - Build scoring formula based on file extensions, directories (e.g., `/db/migrations`), and diff size.
  - Implement Blast Radius detection logic.
  - Implement missing test detection algorithm.
  - Write comprehensive unit tests for the risk engine.

## Sprint 3: AI Review Engine
- **Goal:** Integrate AI for summarization and failure prediction.
- **Tasks:**
  - Implement Hugging Face Inference API client.
  - Design optimized prompts for Qwen/DeepSeek.
  - Generate Change Summary, Suggested Tests, and Reviewer Focus Areas.
  - Ensure deterministic fallback if AI fails.

## Sprint 4: Terminal Dashboard & Database
- **Goal:** Build the final UI and persistence layer.
- **Tasks:**
  - Build the complex Rich Layouts and Panels for the `analyze` output.
  - Setup local SQLite via SQLAlchemy.
  - Implement the `history` command and table output.

## Sprint 5: Polish & Production Readiness
- **Goal:** Prepare the tool for open-source release and recruiter review.
- **Tasks:**
  - End-to-end integration tests using `pytest`.
  - Refactor for maximum clean architecture adherence.
  - Finalize documentation and deployment steps.
