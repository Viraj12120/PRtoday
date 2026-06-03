# PR SENTINEL

> Predict production risk before merge.

PR Sentinel is a terminal-first, developer-centric CLI tool that automatically analyzes Pull Requests and predicts production risk before merge. It acts as an advanced, AI-assisted review engine that gives you a deterministic risk score and blast radius report natively in your terminal.

## Features

- **Risk Engine:** Deterministically calculates a risk score (0-100) based on files changed, database migrations, configuration updates, and dependency shifts.
- **Blast Radius Detection:** Determines which modules, services, and shared libraries are impacted by the PR.
- **Missing Test Detection:** Analyzes the diff against existing test coverage to flag missing unit or integration tests.
- **AI Review Engine:** Uses Qwen/DeepSeek (via Hugging Face) to generate an intelligent change summary, predict potential failure scenarios, and suggest reviewer focus areas.
- **Terminal Dashboard:** A gorgeous, dense, and fast UI built with `Rich` that feels like an engineering tool (inspired by k9s, LazyGit, and htop).
- **Analysis History:** Tracks and stores previous PR analyses in a local SQLite database for historical auditing.

## Architecture

![Architecture](docs/architecture.md)

PR Sentinel is built as a pure Python CLI application.
- **Language**: Python 3.10+
- **CLI Framework**: Typer
- **Terminal UI**: Rich
- **GitHub Integration**: PyGithub / httpx
- **Database**: Local SQLite via SQLAlchemy
- **AI Engine**: Hugging Face Inference API / litellm

## Installation

You will need Python 3.10+ installed.

```bash
# Clone the repository
git clone https://github.com/your-org/pr-sentinel.git
cd pr-sentinel

# Create and activate virtual environment
python -m venv .venv
# On Windows (PowerShell/CMD)
.venv\Scripts\activate
# On macOS/Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -m pr_sentinel.cli --help
```

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

## Usage

```bash
# Analyze a specific PR
python -m pr_sentinel.cli analyze --repo org/repo-name --pr 123

# View analysis history
python -m pr_sentinel.cli history

# Authenticate / Setup
python -m pr_sentinel.cli auth
```

## Running Tests

We use `pytest` for end-to-end and unit testing.

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=pr_sentinel
```

## Roadmap

- [x] Sprint 0: Project Setup & Documentation
- [x] Sprint 1: CLI Foundation & GitHub Integration
- [x] Sprint 2: Risk Engine (Deterministic)
- [x] Sprint 3: AI Review Engine
- [x] Sprint 4: Terminal Dashboard
- [x] Sprint 5: Polish & Production Readiness

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
