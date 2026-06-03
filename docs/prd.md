# PR Today - Product Requirements Document (PRD)

## 1. Product Vision
Software teams merge risky Pull Requests every day. Existing tools show lines changed but fail to answer:
- Will this break production?
- What systems are affected?
- What is the blast radius?
- Which reviewers should focus where?
- Are tests missing?

**PR Today** solves this by predicting production risk before merge via a dense, terminal-first developer tool.

## 2. Target Users
- Software Engineers
- Senior & Staff Engineers
- Engineering Managers & Tech Leads
- Startup Founders & Open Source Maintainers

## 3. Core Features

### 3.1. CLI Authentication
- Authenticate with GitHub via Personal Access Token (PAT).
- Authenticate with AI providers (Hugging Face) via API tokens.

### 3.2. PR Analysis Engine
- Analyze files changed, lines modified, dependency updates, and configuration updates.
- Detect authentication changes, database migrations, and infrastructure modifications.

### 3.3. Risk Engine (Deterministic)
- Calculate a deterministic Risk Score (0-100).
- Classify into Risk Levels: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.
- Weighted scoring system based on the severity of modified files.

### 3.4. Blast Radius Detection
- Determine affected modules, services, shared libraries, and dependency chains.

### 3.5. Missing Test Detection
- Correlate changed source files against existing test coverage to flag missing unit/integration tests.

### 3.6. AI Review Engine
- Generate intelligent change summaries.
- Predict potential failure scenarios.
- Suggest missing tests and areas for reviewer focus.
- Note: AI must *explain* the risk, not *calculate* the score.

### 3.7. Terminal Dashboard & History
- Render dense, fast, keyboard-friendly terminal panels.
- Display a historical table of previously analyzed PRs stored in a local SQLite database.

## 4. Design Philosophy
- **Minimal, Terminal-First, Developer-Centric.**
- Information-rich, fast, and keyboard-driven.
- Color Palette: Background `#0D1117`, Panels `#161B22`, Borders `#30363D`, Primary Text `#C9D1D9`, Success `#238636`, Warning `#D29922`, Danger `#DA3633`.
- Font: JetBrains Mono (Terminal Default).
