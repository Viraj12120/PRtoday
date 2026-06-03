# User Flow

## 1. Initial Setup
1. Developer installs PR Today (`pipx install pr-today` or `poetry install`).
2. Developer runs `pr-today auth`.
3. CLI prompts for GitHub PAT and Hugging Face API Token.
4. CLI verifies credentials and stores them securely in `~/.pr_today/config.json` or system keyring.

## 2. Analyzing a Pull Request
1. Developer runs `pr-today analyze --repo <org/repo> --pr <id>`.
2. A loading spinner (Rich console status) indicates:
   - "Fetching PR data from GitHub..."
   - "Calculating deterministic risk..."
   - "Generating AI failure predictions..."
3. The Terminal Dashboard is rendered immediately showing:
   - PR Metadata
   - Overall Risk Score & Level
   - Discrete Risk Factors
   - Blast Radius
   - AI Review Summary & Missing Tests

## 3. Viewing History
1. Developer runs `pr-today history`.
2. CLI queries the local SQLite database.
3. A Rich Table is printed to the terminal showing a paginated list of previous scans with:
   - Date
   - Risk Score
   - Level
   - Repository
   - PR ID
