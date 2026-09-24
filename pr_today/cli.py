"""Typer command-line interface entry point for PRtoday."""

import asyncio
import logging
import sys
from typing import Optional

import typer
from github import Github
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlalchemy import select

from pr_today.config import settings, setup_logging
from pr_today.dashboard import Dashboard
from pr_today.database import get_session, init_db
from pr_today.models import AnalysisResult
from pr_today.orchestrator import Orchestrator, OrchestratorError

app = typer.Typer(
    help="PRtoday: A terminal-first, AI-assisted PR risk engine.",
    no_args_is_help=True,
)
console = Console()
logger = logging.getLogger("pr_today.cli")

# Default API URL for the --api-url flag
DEFAULT_API_URL = "http://localhost:8000"


def version_callback(value: bool) -> None:
    """Print the version and exit."""
    if value:
        console.print("[bold cyan]PRtoday v2.0.0[/bold cyan]")
        raise typer.Exit()


@app.callback()
def main(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output (DEBUG logging).",
    ),
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show PRtoday version.",
    ),
) -> None:
    """PRtoday CLI global configurations."""
    if verbose:
        settings.LOG_LEVEL = "DEBUG"
    setup_logging()


@app.command()
def auth() -> None:
    """Check validity and scope of configured GitHub PAT token."""
    console.print(
        Panel.fit(
            "[bold cyan]PRtoday GitHub Token Authentication Verification[/bold cyan]"
        )
    )

    if not settings.GITHUB_PAT:
        console.print(
            "[bold red]Error:[/bold red] GITHUB_PAT is not set. Configure it in environment or .env file."
        )
        raise typer.Exit(1)

    try:
        with console.status("[bold cyan]Verifying token with GitHub API..."):
            g = Github(settings.GITHUB_PAT)
            user = g.get_user()
            username = user.login
            # PyGithub headers will contain OAuth scopes info
            scopes = user.raw_headers.get("x-oauth-scopes", "no scopes listed")

        console.print("[bold green]✓ Authentication Successful![/bold green]")
        console.print(f"Logged in as: [bold cyan]@{username}[/bold cyan]")
        console.print(f"Token Scopes: [dim]{scopes}[/dim]")
    except Exception as e:
        console.print(f"[bold red]Authentication Failed:[/bold red] {str(e)}")
        raise typer.Exit(1)


@app.command()
def analyze(
    repo: str = typer.Option(
        ...,
        "--repo",
        "-r",
        help="Repository in format 'owner/name' (e.g. Viraj12120/PRtoday).",
    ),
    pr: int = typer.Option(
        ...,
        "--pr",
        "-p",
        help="Pull Request number to analyze.",
    ),
    no_ai: bool = typer.Option(
        False,
        "--no-ai",
        help="Disable the litellm AI review analysis.",
    ),
    api_url: Optional[str] = typer.Option(
        None,
        "--api-url",
        help=f"Delegate analysis to a running API server instead of local execution. Default: {DEFAULT_API_URL}",
    ),
) -> None:
    """Analyze a Pull Request risk scoring and blast radius."""

    # ── Remote API mode ──────────────────────────────────────────────────
    if api_url is not None:
        _analyze_via_api(api_url, repo, pr)
        return

    # ── Local execution mode (original behavior) ─────────────────────────
    orchestrator = Orchestrator()
    dashboard = Dashboard()

    async def _async_run() -> None:
        await init_db()

        # Display spinner while Orchestrator is running
        with console.status(f"[bold cyan]Analyzing PR #{pr} in {repo}..."):
            result = await orchestrator.run(repo, pr, no_ai=no_ai)

        # Determine author by reading from GitHub
        author = "Unknown"
        try:
            g = Github(settings.GITHUB_PAT)
            # Use cached call to get user login if available, otherwise fetch
            author = g.get_repo(repo).get_pull(pr).user.login
        except Exception:
            pass

        dashboard.render(result, author=author)

    try:
        asyncio.run(_async_run())
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Analysis aborted by user.[/bold yellow]")
        sys.exit(130)
    except OrchestratorError as oe:
        console.print(f"[bold red]Analysis Error:[/bold red] {str(oe)}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {str(e)}")
        if settings.LOG_LEVEL == "DEBUG":
            import traceback

            traceback.print_exc()
        sys.exit(1)


def _analyze_via_api(api_url: str, repo: str, pr: int) -> None:
    """Delegate analysis to a remote API server via HTTP POST."""
    import httpx
    import time
    from concurrent.futures import ThreadPoolExecutor
    from rich.progress import Progress, SpinnerColumn, TextColumn

    url = f"{api_url.rstrip('/')}/analyze"
    payload = {"repo": repo, "pr_number": pr, "user_id": "cli-user"}

    console.print(f"[dim]Delegating to API: {url}[/dim]")

    def make_request():
        # Large repositories like Ladybird/FastAPI take time to clone and analyze.
        return httpx.post(url, json=payload, timeout=600.0)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task("[cyan]Initializing Request...", total=None)
            
            with ThreadPoolExecutor() as executor:
                future = executor.submit(make_request)
                
                stages = [
                    (0, "[cyan]Fetching PR metadata from GitHub..."),
                    (2, "[blue]Running Deterministic Risk Engine..."),
                    (4, "[magenta]Streaming AI Code Review Analysis..."),
                    (10, "[green]Persisting results to database...")
                ]
                
                start_time = time.time()
                current_stage = -1
                
                while not future.done():
                    elapsed = time.time() - start_time
                    if current_stage < len(stages) - 1 and elapsed >= stages[current_stage + 1][0]:
                        current_stage += 1
                        progress.update(task, description=stages[current_stage][1])
                    time.sleep(0.1)
                
                response = future.result()

        if response.status_code == 200:
            data = response.json()
            _render_rich_dashboard(data, repo, pr)
        else:
            console.print(
                f"[bold red]API Error ({response.status_code}):[/bold red] {response.text}"
            )
            sys.exit(1)

    except httpx.ConnectError:
        console.print(
            f"[bold red]Connection Error:[/bold red] Could not reach API at {api_url}. "
            "Is the server running?"
        )
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]API Error:[/bold red] {str(e)}")
        sys.exit(1)


def _render_rich_dashboard(data: dict, repo: str, pr: int) -> None:
    """Render a comprehensive multi-panel dashboard from API response data."""
    from rich.columns import Columns
    from rich.markdown import Markdown
    from rich.markup import escape
    from rich.text import Text
    from rich.tree import Tree

    score = data.get("risk_score", 0)
    level = data.get("risk_level", "UNKNOWN").upper()
    classification = data.get("change_classification", "UNKNOWN")

    # Color mapping
    color_map = {"LOW": "green", "MEDIUM": "yellow", "HIGH": "red", "CRITICAL": "bold red"}
    accent = color_map.get(level, "white")

    # ── 1. Header ─────────────────────────────────────────────────────
    header = Text()
    header.append("PR TODAY ", style="bold magenta")
    header.append("— AI-Assisted PR Risk Assessment\n", style="bold white")
    header.append(
        f"Repository: {repo}  │  PR: #{pr}  │  Type: {classification}",
        style="dim white",
    )
    console.print(Panel(header, border_style="cyan", padding=(1, 2)))

    # ── 2. Risk Score & Confidence ────────────────────────────────────
    bar_len = 40
    filled = int(score / 100 * bar_len)
    bar = f"[{accent}]{'█' * filled}[/{accent}][dim]{'░' * (bar_len - filled)}[/dim]"

    score_text = Text()
    score_text.append(f"\n  {score}/100 ", style=f"bold {accent}")
    score_text.append(f"[{level}]\n", style=f"{accent}")

    confidence = data.get("confidence_score", 100)
    conf_filled = int(confidence / 100 * 20)
    conf_color = "green" if confidence >= 90 else ("yellow" if confidence >= 70 else "red")
    conf_bar = f"[{conf_color}]{'█' * conf_filled}[/{conf_color}][dim]{'░' * (20 - conf_filled)}[/dim]"
    score_text.append(f"  Confidence: {confidence}% {conf_bar}\n", style="dim white")

    files_changed = data.get("files_changed", [])
    blast_radius = data.get("blast_radius", [])

    details_table = Table(show_header=False, box=None, padding=(0, 2))
    details_table.add_column("Label", style="bold white", min_width=18)
    details_table.add_column("Value", style="cyan")
    details_table.add_row("Files Changed", str(len(files_changed)))
    details_table.add_row("Blast Radius", ", ".join(blast_radius) if blast_radius else "None")
    details_table.add_row(
        "DB Migrations",
        "[red]DETECTED[/red]" if data.get("db_migrations_detected") else "[green]None[/green]",
    )
    details_table.add_row(
        "Config Changes",
        "[red]DETECTED[/red]" if data.get("config_changes_detected") else "[green]None[/green]",
    )
    details_table.add_row(
        "Dependency Changes",
        "[yellow]DETECTED[/yellow]" if data.get("dependency_changes_detected") else "[green]None[/green]",
    )

    score_grid = Table.grid(expand=True, padding=1)
    score_grid.add_column(ratio=1)
    score_grid.add_column(ratio=2)
    score_grid.add_row(
        Panel(f"  {bar}\n{score_text.plain}", border_style=accent),
        details_table,
    )
    console.print(Panel(score_grid, title="[bold]Risk Assessment[/bold]", border_style=accent, padding=(1, 2)))

    # ── 3. AI Summary ─────────────────────────────────────────────────
    summary = data.get("ai_summary") or "AI review not available."
    console.print(
        Panel(
            Markdown(summary),
            title="[bold]AI Executive Summary[/bold]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    # ── 4. Architectural Impact ───────────────────────────────────────
    arch_impact = data.get("architectural_impact", "Not assessed.")
    if arch_impact and arch_impact != "Not assessed.":
        console.print(
            Panel(
                Markdown(arch_impact),
                title="[bold]Architectural Impact[/bold]",
                border_style="blue",
                padding=(1, 2),
            )
        )

    # ── 5. Failure Scenarios ──────────────────────────────────────────
    failures = data.get("ai_failures", [])
    if failures:
        fail_md = "\n\n".join(f"{i}. {scenario}" for i, scenario in enumerate(failures, 1))
        console.print(
            Panel(
                Markdown(fail_md),
                title=f"[bold]Potential Failure Scenarios ({len(failures)})[/bold]",
                border_style="red",
                padding=(1, 2),
            )
        )

    # ── 6. Reviewer Focus Areas ───────────────────────────────────────
    focus = data.get("ai_focus_areas", [])
    if focus:
        focus_md = "\n\n".join(f"{i}. {area}" for i, area in enumerate(focus, 1))
        console.print(
            Panel(
                Markdown(focus_md),
                title=f"[bold]Reviewer Focus Areas ({len(focus)})[/bold]",
                border_style="yellow",
                padding=(1, 2),
            )
        )

    # ── 7. SAST Findings ──────────────────────────────────────────────
    sast = data.get("security_findings", [])
    if sast:
        sast_md = "\n".join(
            f"- **{f.get('rule_id', 'Vulnerability')}** in `{f.get('file', 'Unknown')}:{f.get('line', '?')}` ({f.get('severity', 'WARNING')})\n  {f.get('message', '')}"
            if isinstance(f, dict) else f"- {f}"
            for f in sast
        )
        console.print(
            Panel(
                Markdown(sast_md),
                title=f"[bold]SAST Findings ({len(sast)})[/bold]",
                border_style="red",
                padding=(1, 2),
            )
        )
    else:
        console.print(
            Panel(
                "[green]✓ No SAST vulnerabilities detected by Semgrep.[/green]",
                title="[bold]SAST Findings (0)[/bold]",
                border_style="green",
                padding=(1, 2),
            )
        )

    # ── 8. Security & Testing (side-by-side) ──────────────────────────
    security = data.get("security_notes", "Not assessed.")
    testing = data.get("testing_gaps", "Not assessed.")

    sec_border = "green" if security == "No security concerns identified." else "red"
    test_border = "green" if testing == "Test coverage appears adequate." else "yellow"

    bottom_grid = Table.grid(expand=True, padding=1)
    bottom_grid.add_column(ratio=1)
    bottom_grid.add_column(ratio=1)
    bottom_grid.add_row(
        Panel(
            Markdown(security),
            title="[bold]Security Notes[/bold]",
            border_style=sec_border,
            padding=(1, 2),
        ),
        Panel(
            Markdown(testing),
            title="[bold]Testing Gaps[/bold]",
            border_style=test_border,
            padding=(1, 2),
        ),
    )
    console.print(bottom_grid)

    # ── 8. AI Metrics Footer ──────────────────────────────────────────
    model = data.get("ai_model_used", "unknown")
    tokens_p = data.get("ai_tokens_prompt")
    tokens_c = data.get("ai_tokens_completion")
    cost = data.get("ai_cost_usd")
    latency = data.get("ai_latency_ms")

    metrics_parts = [f"[dim]Model: {model}[/dim]"]
    if tokens_p is not None:
        metrics_parts.append(f"[dim]Tokens: {tokens_p:,}→{tokens_c:,}[/dim]")
    if cost is not None:
        metrics_parts.append(f"[dim]Cost: ${cost:.4f}[/dim]")
    if latency is not None:
        metrics_parts.append(f"[dim]Latency: {latency / 1000:.1f}s[/dim]")
    console.print(f"\n  {'  │  '.join(metrics_parts)}\n")

    # ── Legend ────────────────────────────────────────────────────────
    legend_text = Text()
    legend_text.append("Legend:\n", style="bold white")
    legend_text.append(" • Blast Radius: ", style="bold cyan")
    legend_text.append("How widely the code changes affect the rest of the project.\n", style="dim")
    legend_text.append(" • Config Changes: ", style="bold cyan")
    legend_text.append("Changes to settings or environment files that might break deployments.\n", style="dim")
    legend_text.append(" • SAST Findings: ", style="bold cyan")
    legend_text.append("Security risks and vulnerabilities found in the code.\n", style="dim")
    legend_text.append(" • Confidence: ", style="bold cyan")
    legend_text.append("How sure the AI is about its review (lower if the PR is too large or complex).", style="dim")
    
    legend_panel = Panel(
        legend_text,
        title="Terminology",
        title_align="center",
        border_style="dim white",
        padding=(0, 2)
    )
    console.print(legend_panel)


@app.command()
def history(
    limit: int = typer.Option(
        10,
        "--limit",
        "-l",
        help="Number of historical analyses to display.",
    ),
    api_url: Optional[str] = typer.Option(
        None,
        "--api-url",
        help=f"Fetch history from a running API server. Default: {DEFAULT_API_URL}",
    ),
) -> None:
    """View database history of previous PR analyses."""

    # ── Remote API mode ──────────────────────────────────────────────────
    if api_url is not None:
        _history_via_api(api_url, limit)
        return

    # ── Local execution mode (original behavior) ─────────────────────────
    async def _fetch_history() -> list[AnalysisResult]:
        await init_db()
        async with get_session() as session:
            stmt = (
                select(AnalysisResult)
                .order_by(AnalysisResult.created_at.desc())
                .limit(limit)
            )
            res = await session.execute(stmt)
            return list(res.scalars().all())

    try:
        records = asyncio.run(_fetch_history())
        if not records:
            console.print(
                "[bold yellow]No PR risk history found in database.[/bold yellow]"
            )
            return

        table = Table(
            title="[bold cyan]PRtoday Analysis History[/bold cyan]",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Date", style="dim")
        table.add_column("Repository")
        table.add_column("PR #", justify="right")
        table.add_column("Risk Score", justify="right")
        table.add_column("Level")
        table.add_column("Files Changed", justify="right")
        table.add_column("Migrations", justify="center")

        for r in records:
            level_upper = r.risk_level.upper()
            if level_upper == "LOW":
                level_style = "green"
            elif level_upper == "MEDIUM":
                level_style = "yellow"
            else:
                level_style = "red"

            migrations_indicator = (
                "[red]Yes[/red]" if r.db_migrations_detected else "[green]No[/green]"
            )

            table.add_row(
                r.created_at.strftime("%Y-%m-%d %H:%M"),
                r.repo,
                f"#{r.pr_number}",
                f"[{level_style}]{r.risk_score}/100[/{level_style}]",
                f"[{level_style}]{level_upper}[/{level_style}]",
                str(len(r.files_changed)),
                migrations_indicator,
            )

        console.print(table)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]History retrieval aborted by user.[/bold yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[bold red]Error fetching history:[/bold red] {str(e)}")
        sys.exit(1)


def _history_via_api(api_url: str, limit: int) -> None:
    """Fetch analysis history from a remote API server."""
    import httpx

    url = f"{api_url.rstrip('/')}/history"
    params = {"limit": limit}

    console.print(f"[dim]Fetching history from API: {url}[/dim]")

    try:
        with console.status("[bold cyan]Fetching history via API..."):
            response = httpx.get(url, params=params, timeout=30.0)

        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])

            if not results:
                console.print(
                    "[bold yellow]No PR risk history found.[/bold yellow]"
                )
                return

            table = Table(
                title="[bold cyan]PRtoday Analysis History (API)[/bold cyan]",
                show_header=True,
                header_style="bold magenta",
            )
            table.add_column("Date", style="dim")
            table.add_column("Repository")
            table.add_column("PR #", justify="right")
            table.add_column("Risk Score", justify="right")
            table.add_column("Level")

            for item in results:
                level = item.get("risk_level", "UNKNOWN").upper()
                if level == "LOW":
                    style = "green"
                elif level == "MEDIUM":
                    style = "yellow"
                else:
                    style = "red"

                table.add_row(
                    item.get("created_at", "")[:16],
                    item.get("repo", ""),
                    f"#{item.get('pr_number', '?')}",
                    f"[{style}]{item.get('risk_score', '?')}/100[/{style}]",
                    f"[{style}]{level}[/{style}]",
                )

            console.print(table)
        else:
            console.print(
                f"[bold red]API Error ({response.status_code}):[/bold red] {response.text}"
            )
            sys.exit(1)

    except httpx.ConnectError:
        console.print(
            f"[bold red]Connection Error:[/bold red] Could not reach API at {api_url}."
        )
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]API Error:[/bold red] {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    app()
