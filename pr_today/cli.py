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
from rich.text import Text
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


def version_callback(value: bool) -> None:
    """Print the version and exit."""
    if value:
        console.print("[bold cyan]PRtoday v0.1.0[/bold cyan]")
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
    console.print(Panel.fit("[bold cyan]PRtoday GitHub Token Authentication Verification[/bold cyan]"))
    
    if not settings.GITHUB_PAT:
        console.print("[bold red]Error:[/bold red] GITHUB_PAT is not set. Configure it in environment or .env file.")
        raise typer.Exit(1)
        
    try:
        with console.status("[bold cyan]Verifying token with GitHub API..."):
            g = Github(settings.GITHUB_PAT)
            user = g.get_user()
            username = user.login
            # PyGithub headers will contain OAuth scopes info
            scopes = user.raw_headers.get("x-oauth-scopes", "no scopes listed")
            
        console.print(f"[bold green]✓ Authentication Successful![/bold green]")
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
) -> None:
    """Analyze a Pull Request risk scoring and blast radius."""
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


@app.command()
def history(
    limit: int = typer.Option(
        10,
        "--limit",
        "-l",
        help="Number of historical analyses to display.",
    )
) -> None:
    """View database history of previous PR analyses."""
    async def _fetch_history() -> list[AnalysisResult]:
        await init_db()
        async with get_session() as session:
            stmt = select(AnalysisResult).order_by(AnalysisResult.created_at.desc()).limit(limit)
            res = await session.execute(stmt)
            return list(res.scalars().all())

    try:
        records = asyncio.run(_fetch_history())
        if not records:
            console.print("[bold yellow]No PR risk history found in database.[/bold yellow]")
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

            migrations_indicator = "[red]Yes[/red]" if r.db_migrations_detected else "[green]No[/green]"

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


if __name__ == "__main__":
    app()
