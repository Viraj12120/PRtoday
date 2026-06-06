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

    url = f"{api_url.rstrip('/')}/analyze"
    payload = {"repo": repo, "pr_number": pr, "user_id": "cli-user"}

    console.print(f"[dim]Delegating to API: {url}[/dim]")

    try:
        with console.status(f"[bold cyan]Analyzing PR #{pr} via API..."):
            response = httpx.post(url, json=payload, timeout=60.0)

        if response.status_code == 200:
            data = response.json()
            # Render a simplified table of results
            table = Table(
                title=f"[bold cyan]PR #{pr} Risk Analysis ({repo})[/bold cyan]",
                show_header=True,
                header_style="bold magenta",
            )
            table.add_column("Metric", style="bold white")
            table.add_column("Value", style="cyan")

            table.add_row("Risk Score", f"{data['risk_score']}/100")
            table.add_row("Blast Radius", ", ".join(data.get("blast_radius", [])))
            table.add_row(
                "Files Changed", str(len(data.get("files_changed", [])))
            )
            table.add_row(
                "AI Summary", data.get("ai_summary", "N/A") or "N/A"
            )

            findings = data.get("security_findings", [])
            if findings:
                table.add_row(
                    "Security Findings",
                    "\n".join(f"⚠ {f}" for f in findings),
                )
            else:
                table.add_row("Security Findings", "[green]None[/green]")

            console.print(table)
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
