# PR TODAY

> Predict production risk before merge.

PR Today is a terminal-first, developer-centric CLI tool that automatically analyzes Pull Requests and predicts production risk before merge. It acts as an advanced, AI-assisted review engine that gives you a deterministic risk score and blast radius report natively in your terminal.

---

## Features

- **Risk Engine:** Deterministically calculates a risk score (0-100) based on files changed, database migrations, configuration updates, and dependency shifts.
- **Blast Radius Detection:** Determines which modules, services, and shared libraries are impacted by the PR.
- **Missing Test Detection:** Analyzes the diff against existing test coverage to flag missing unit or integration tests.
- **AI Review Engine:** Uses Qwen/DeepSeek (via Hugging Face) to generate an intelligent change summary, predict potential failure scenarios, and suggest reviewer focus areas.
- **Terminal Dashboard:** A gorgeous, dense, and fast UI built with `Rich` that feels like an engineering tool (inspired by k9s, LazyGit, and htop).
- **Analysis History:** Tracks and stores previous PR analyses in a local SQLite database for historical auditing.

---

## Architecture

PR Today is built as a pure Python CLI application with three core subsystems: the **Risk Engine**, **AI Review Engine**, and **Terminal Dashboard** — all orchestrated through a Typer-based CLI.

```mermaid
graph TB
    subgraph User["👤 Developer"]
        CLI["CLI Command\npr_today.cli analyze"]
    end

    subgraph Core["🧠 PR Today Core"]
        direction TB
        ORCH["Orchestrator\norchestrator.py"]

        subgraph Risk["Risk Engine"]
            RE["Risk Calculator\nrisk_engine.py"]
            BRD["Blast Radius\nDetector"]
            MTD["Missing Test\nDetector"]
        end

        subgraph AI["AI Review Engine"]
            AIR["AI Reviewer\nai_engine.py"]
            SUM["Change Summarizer"]
            FAIL["Failure Predictor"]
        end

        subgraph UI["Terminal Dashboard"]
            RICH["Rich Renderer\ndashboard.py"]
            REPORT["Report Builder"]
        end

        DB["SQLite Store\nSQLAlchemy\nhistory.db"]
    end

    subgraph External["🌐 External Services"]
        GH["GitHub API\nPyGithub / httpx"]
        HF["Hugging Face\nInference API"]
        GEMINI["Google Gemini API"]
        OAI["OpenAI API"]
    end

    CLI --> ORCH
    ORCH --> RE
    ORCH --> AIR
    ORCH --> RICH

    RE --> BRD
    RE --> MTD

    AIR --> SUM
    AIR --> FAIL

    RICH --> REPORT

    ORCH --> DB
    ORCH --> GH

    AIR -->|litellm router| HF
    AIR -->|litellm router| GEMINI
    AIR -->|litellm router| OAI

    GH -->|PR diff + metadata| ORCH

    style Core fill:#1a1a2e,stroke:#4a9eff,color:#fff
    style Risk fill:#0f3460,stroke:#4a9eff,color:#fff
    style AI fill:#0f3460,stroke:#a855f7,color:#fff
    style UI fill:#0f3460,stroke:#22c55e,color:#fff
    style External fill:#1a1a1a,stroke:#666,color:#fff
    style User fill:#111,stroke:#888,color:#fff
```

### Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| CLI Framework | Typer |
| Terminal UI | Rich |
| GitHub Integration | PyGithub / httpx |
| Database | Local SQLite via SQLAlchemy |
| AI Engine | Hugging Face Inference API / litellm |

---

## PR Analysis Flow

The end-to-end flow when you run `pr_today analyze`:

```mermaid
sequenceDiagram
    actor Dev as Developer
    participant CLI as CLI (Typer)
    participant GH as GitHub API
    participant RE as Risk Engine
    participant AI as AI Engine
    participant DB as SQLite DB
    participant UI as Terminal UI

    Dev->>CLI: pr_today analyze --repo org/repo --pr 123
    CLI->>GH: Fetch PR metadata + diff
    GH-->>CLI: Files changed, commits, author info

    CLI->>RE: Run deterministic analysis
    activate RE
    RE->>RE: Score file changes (0-100)
    RE->>RE: Detect DB migrations
    RE->>RE: Check config & dep changes
    RE->>RE: Map blast radius
    RE->>RE: Flag missing tests
    RE-->>CLI: Risk score + blast radius report
    deactivate RE

    CLI->>AI: Run AI review on diff
    activate AI
    AI->>AI: Generate change summary
    AI->>AI: Predict failure scenarios
    AI->>AI: Suggest reviewer focus areas
    AI-->>CLI: AI review report
    deactivate AI

    CLI->>DB: Persist analysis result
    CLI->>UI: Render terminal dashboard
    UI-->>Dev: Risk score panel + blast radius + AI insights
```

---

## Risk Score Breakdown

The deterministic risk score is calculated across four weighted dimensions:

```mermaid
graph LR
    PR["Pull Request\nDiff"] --> FC
    PR --> DBM
    PR --> CFG
    PR --> DEP

    FC["📄 Files Changed\nvolume + criticality"]
    DBM["🗄️ DB Migrations\nschema changes"]
    CFG["⚙️ Config Changes\nenv / secrets / flags"]
    DEP["📦 Dependency Shifts\nadditions / removals"]

    FC --> SCORE
    DBM --> SCORE
    CFG --> SCORE
    DEP --> SCORE

    SCORE["🎯 Risk Score\n0 – 100"]

    SCORE --> LOW["🟢 Low Risk\n0–33\nSafe to merge"]
    SCORE --> MED["🟡 Medium Risk\n34–66\nReview carefully"]
    SCORE --> HIGH["🔴 High Risk\n67–100\nBlock & escalate"]

    style SCORE fill:#1e3a5f,stroke:#4a9eff,color:#fff
    style LOW fill:#14532d,stroke:#22c55e,color:#fff
    style MED fill:#713f12,stroke:#eab308,color:#fff
    style HIGH fill:#450a0a,stroke:#ef4444,color:#fff
```

---

## Module Structure

```mermaid
graph TD
    ROOT["PRtoday/"]

    ROOT --> CLI_MOD["pr_today/\n── cli.py\n── orchestrator.py\n── risk_engine.py\n── ai_engine.py\n── dashboard.py\n── database.py\n── models.py\n── config.py"]

    ROOT --> TESTS["tests/\n── test_risk_engine.py\n── test_ai_engine.py\n── test_cli.py"]

    ROOT --> DOCS["docs/\n── architecture.md"]

    ROOT --> CFG["Config\n── pyproject.toml\n── .env\n── .gitignore"]

    style ROOT fill:#1a1a2e,stroke:#4a9eff,color:#fff
    style CLI_MOD fill:#0f3460,stroke:#4a9eff,color:#fff
    style TESTS fill:#0f3460,stroke:#a855f7,color:#fff
    style DOCS fill:#0f3460,stroke:#22c55e,color:#fff
    style CFG fill:#1a1a1a,stroke:#666,color:#fff
```

---

## Installation

You will need Python 3.10+ installed.

```bash
# Clone the repository
git clone https://github.com/your-org/pr-today.git
cd pr-today

# Create and activate virtual environment
python -m venv .venv
# On Windows (PowerShell/CMD)
.venv\Scripts\activate
# On macOS/Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -m pr_today.cli --help
```

---

## Environment Variables

Create a `.env` file in the root directory:

```env
GITHUB_PAT=your_github_personal_access_token
LOG_LEVEL=INFO

# Choose and configure your AI Provider:

# Option A: Hugging Face (Default)
HF_TOKEN=your_hugging_face_api_token
AI_MODEL=huggingface/Qwen/Qwen2.5-Coder-32B-Instruct

# Option B: Google Gemini
GEMINI_API_KEY=your_gemini_api_key
AI_MODEL=gemini/gemini-2.5-flash

# Option C: OpenAI
OPENAI_API_KEY=your_openai_api_key
AI_MODEL=openai/gpt-4o-mini
```

---

## Usage

```bash
# Analyze a specific PR
python -m pr_today.cli analyze --repo org/repo-name --pr 123

# View analysis history
python -m pr_today.cli history

# Authenticate / Setup
python -m pr_today.cli auth
```

---

## Running Tests

We use `pytest` for end-to-end and unit testing.

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=pr_today
```

---

## Example Output

Here is an example of the terminal dashboard rendered when analyzing a PR:

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ PR TODAY                                                                                                       │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
┌───────────────────────────────── PR Information ─────────────────────────────────┐ ┌────────── Risk Score ──────────┐
│ Repository      refinedev/refine                                                 │ │                                │
│ PR              #7440 - feat(core): add updateIdentity method to auth provider   │ │         43/100 [MEDIUM]        │
│ Files Changed   10                                                               │ │                                │
│ Lines           +927 / -1                                                        │ │                                │
└──────────────────────────────────────────────────────────────────────────────────┘ └────────────────────────────────┘
┌────────────────────────────────── Risk Factors ──────────────────────────────────┐ ┌────────── Blast Radius ─────────┐
│ [+] Moderate Change Set                                                          │ │ auth-provider-update-identity/ │
│     10 files changed                                                             │ │   core/*                       │
│ [+] Large Diff                                                                   │ │   documentation/*              │
│     928 lines changed                                                            │ │                                │
│ [+] Critical Path Modified: authentication/                                      │ │ Shared Libraries:              │
│     Changes detected in 'authentication/' directory                              │ │   ⚠️ definitions/helpers        │
│ [+] Critical Path Modified: auth/                                                │ │   ⚠️ packages/core             │
│     Changes detected in 'auth/' directory                                        │ │                                │
│                                                                                  │ │ Cross-Cutting Concerns:        │
│                                                                                  │ │   ⚠️ Authentication            │
└──────────────────────────────────────────────────────────────────────────────────┘ └────────────────────────────────┘
┌────────────────────────────────── Test Coverage ─────────────────────────────────┐ ┌───── AI Review & Predictions ──┐
│ Missing Unit Tests:                                                              │ │ Summary:                       │
│   [-] packages/core/src/contexts/auth/types.ts                                   │ │ This PR introduces a new       │
│                                                                                  │ │ `updateIdentity` method to     │
│ Test Coverage: 80%                                                               │ │ the `AuthProvider` interface   │
│                                                                                  │ │ and a corresponding            │
│                                                                                  │ │ `useUpdateIdentity` hook...    │
└──────────────────────────────────────────────────────────────────────────────────┘ └────────────────────────────────┘
```

### Detailed AI Review & Predictions for the above PR:

* **Summary:**
  This PR introduces a new `updateIdentity` method to the `AuthProvider` interface and a corresponding `useUpdateIdentity` hook, allowing applications to update the current user's identity (e.g., username, email) with built-in handling for redirects and notifications.

* **Potential Failure Scenarios:**
  * ⚠️ If an `authProvider` implements `updateIdentity` incorrectly (e.g., fails to return `success: true` on success, or returns malformed `AuthActionResponse`), it could lead to silent failures, incorrect redirects, or misleading user notifications.
  * ⚠️ Improper backend implementation or misconfiguration of the `updateIdentity` method in the `authProvider` could introduce security vulnerabilities, allowing unauthorized identity changes or exposing sensitive user data if not properly validated and secured.
  * ⚠️ Existing applications that upgrade might encounter issues if their custom `authProvider` is not updated to gracefully handle the optional `updateIdentity` method, potentially leading to runtime errors if the hook is used without the method being defined.

* **Reviewer Focus Areas:**
  * ☉ `packages/core/src/contexts/auth/index.tsx` and `packages/core/src/contexts/auth/types.ts`: Verify that the `updateIdentity` method is correctly added as an optional property to the `AuthProvider` interface and that its type signature is consistent with other auth actions.
  * ☉ `packages/core/src/hooks/auth/useUpdateIdentity/index.ts`: Scrutinize the implementation of the `useUpdateIdentity` hook, ensuring it correctly calls the `authProvider`'s `updateIdentity` method, handles loading/error states, and processes `AuthActionResponse` (especially `redirectTo` and `notifications`) as expected.
  * ☉ `documentation/docs/authentication/auth-provider/index.md` and `documentation/docs/authentication/hooks/use-update-identity/index.md`: Ensure the new method and hook are thoroughly documented with clear examples, expected return types, and explanations of error handling and redirection behavior.

* **Suggested Tests:**
  * ✓ Create an integration test that uses `useUpdateIdentity` with a mock `authProvider` implementation. Test successful updates (with and without `redirectTo`, with and without `successNotification`), failed updates (with and without `error` object), and verify correct UI feedback (notifications, redirects) is triggered.
  * ✓ Add edge case tests for the `AuthActionResponse` returned by `updateIdentity`. Specifically, test scenarios where `success` is `false` but no `error` object is provided (should show generic error), and ensure `redirectTo` and `successNotification` are correctly processed when present.
  * ✓ Implement a test case for an `authProvider` that *does not* implement the `updateIdentity` method. Verify that calling `useUpdateIdentity` in such a scenario either gracefully handles the missing method (e.g., returns an error or a no-op) without crashing the application.

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.