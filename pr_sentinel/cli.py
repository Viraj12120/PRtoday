import typer
import sys
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text
from pr_sentinel.auth import set_token, get_github_token
from pr_sentinel.github import GithubClient, GithubClientError
from pr_sentinel.risk import calculate_risk, analyze_blast_radius, detect_missing_tests, RiskLevel
from pr_sentinel.ai import AiClient

app = typer.Typer(help="PR Sentinel - Predict production risk before merge.")
console = Console()

def _can_encode(char: str) -> bool:
    try:
        char.encode(sys.stdout.encoding or 'ascii')
        return True
    except Exception:
        return False

# Unicode/ASCII fallbacks for compatibility
SYM_WARN = "⚠" if _can_encode("⚠") else "!"
SYM_CHECK = "✓" if _can_encode("✓") else "+"
SYM_BULLET = "☉" if _can_encode("☉") else "*"


# Design system colors
COLOR_BG = "#0D1117"
COLOR_PANEL = "#161B22"
COLOR_BORDER = "#30363D"
COLOR_TEXT = "#C9D1D9"
COLOR_SUCCESS = "#238636"
COLOR_WARNING = "#D29922"
COLOR_DANGER = "#DA3633"


def _risk_color(level: RiskLevel) -> str:
    """Map risk level to design system color."""
    return {
        RiskLevel.LOW: COLOR_SUCCESS,
        RiskLevel.MEDIUM: COLOR_WARNING,
        RiskLevel.HIGH: COLOR_DANGER,
        RiskLevel.CRITICAL: COLOR_DANGER,
    }[level]


@app.command()
def auth():
    """Authenticate with GitHub and AI Providers."""
    console.print(Panel.fit("PR Sentinel Authentication", style="bold blue"))

    gh_token = Prompt.ask("Enter GitHub Personal Access Token", password=True)
    if gh_token:
        set_token("github", gh_token)
        console.print(f"[green]{SYM_CHECK} GitHub token saved successfully.[/green]")

    hf_token = Prompt.ask("Enter Hugging Face API Token (optional)", password=True, default="")
    if hf_token:
        set_token("hf", hf_token)
        console.print(f"[green]{SYM_CHECK} Hugging Face token saved successfully.[/green]")


@app.command()
def analyze(repo: str = typer.Option(..., help="Repository name in format org/repo"),
            pr: int = typer.Option(..., help="Pull Request number")):
    """Analyze a Pull Request for production risk."""
    try:
        client = GithubClient()

        with console.status("[bold cyan]Fetching PR data from GitHub..."):
            pr_data = client.get_pull_request(repo, pr)
            files = client.get_pr_files(repo, pr)

        # --- Risk Engine ---
        with console.status("[bold cyan]Calculating deterministic risk score..."):
            risk_report = calculate_risk(files)
            blast_report = analyze_blast_radius(files)
            test_report = detect_missing_tests(files)

        # --- AI Review Engine ---
        with console.status("[bold cyan]Generating AI failure predictions..."):
            ai_client = AiClient()
            ai_report = ai_client.generate_review(files)

        # --- Save to local SQLite database ---
        try:
            from pr_sentinel.db import save_analysis
            save_analysis(repo, pr, pr_data.title, risk_report, ai_report)
        except Exception as db_err:
            console.print(f"[dim yellow]{SYM_WARN} Could not save analysis to history: {str(db_err)}[/dim yellow]")

        # --- Render Terminal Dashboard ---
        risk_color = _risk_color(risk_report.level)

        # 1. Header Panel
        console.print(Panel(
            f"[bold {COLOR_TEXT}]PR SENTINEL[/bold {COLOR_TEXT}]",
            border_style=COLOR_BORDER,
        ))

        # 2. Top Row: PR Information (Left) & Risk Score (Right)
        meta_table = Table(show_header=False, box=None, padding=(0, 1))
        meta_table.add_column("Key", style=f"bold {COLOR_TEXT}")
        meta_table.add_column("Value", style=COLOR_TEXT)
        meta_table.add_row("Repository", repo)
        meta_table.add_row("PR", f"#{pr} - {pr_data.title}")
        meta_table.add_row("Files Changed", str(risk_report.total_files_changed))
        meta_table.add_row("Lines", f"+{risk_report.total_additions} / -{risk_report.total_deletions}")

        score_text = Text(f"\n {risk_report.score}/100 [{risk_report.level.value}] \n", style=f"bold {risk_color}")

        top_row = Table.grid(expand=True, padding=1)
        top_row.add_column(ratio=2)
        top_row.add_column(ratio=1)
        top_row.add_row(
            Panel(meta_table, title="[bold]PR Information[/bold]", border_style=COLOR_BORDER),
            Panel(score_text, title="[bold]Risk Score[/bold]", border_style=risk_color)
        )
        console.print(top_row)

        # 3. Middle Row: Risk Factors (Left) & Blast Radius (Right)
        factors_text = ""
        if risk_report.triggered_factors:
            for f in risk_report.triggered_factors:
                factors_text += f"[{risk_color}][+] {f.name}[/{risk_color}]\n"
                factors_text += f"    [dim]{f.description}[/dim]\n"
        else:
            factors_text = "[dim]No critical risk factors triggered.[/dim]"

        blast_text = ""
        if blast_report.affected_modules:
            for mod in blast_report.affected_modules:
                blast_text += f"  {mod}/*\n"
            if blast_report.shared_libraries_impacted:
                blast_text += "\n[bold]Shared Libraries:[/bold]\n"
                for lib in blast_report.shared_libraries_impacted:
                    blast_text += f"  {SYM_WARN} {lib}\n"
            if blast_report.cross_cutting_concerns:
                blast_text += "\n[bold]Cross-Cutting Concerns:[/bold]\n"
                for cc in blast_report.cross_cutting_concerns:
                    blast_text += f"  {SYM_WARN} {cc}\n"
        else:
            blast_text = "[dim]Changes are localized. No external modules impacted.[/dim]"

        mid_row = Table.grid(expand=True, padding=1)
        mid_row.add_column(ratio=1)
        mid_row.add_column(ratio=1)
        mid_row.add_row(
            Panel(factors_text.strip(), title="[bold]Risk Factors[/bold]", border_style=COLOR_BORDER),
            Panel(blast_text.strip(), title="[bold]Blast Radius[/bold]", border_style=COLOR_BORDER)
        )
        console.print(mid_row)

        # 4. Bottom Row: Test Coverage (Left) & AI Review & Predictions (Right)
        test_text = ""
        if test_report.missing_unit_tests or test_report.missing_integration_tests:
            if test_report.files_without_tests:
                test_text += f"[{COLOR_WARNING}]Missing Unit Tests:[/{COLOR_WARNING}]\n"
                for tf in test_report.files_without_tests:
                    test_text += f"  [-] {tf}\n"
            if test_report.missing_integration_tests:
                test_text += f"\n[{COLOR_DANGER}][!] Missing Integration Tests[/{COLOR_DANGER}]\n"
            test_text += f"\nTest Coverage: {test_report.coverage_ratio:.0%}"
        else:
            test_text = f"[{COLOR_SUCCESS}]{SYM_CHECK} All changed files have corresponding tests.[/{COLOR_SUCCESS}]\n\nTest Coverage: {test_report.coverage_ratio:.0%}"

        ai_text = ""
        if ai_report.error:
            ai_text += f"[dim]AI Engine offline: {ai_report.error}[/dim]\n\n"
        
        ai_text += f"[bold {COLOR_TEXT}]Summary:[/bold {COLOR_TEXT}]\n{ai_report.summary}\n\n"
        
        if ai_report.failure_scenarios:
            ai_text += f"[bold {COLOR_DANGER}]Potential Failure Scenarios:[/bold {COLOR_DANGER}]\n"
            for scenario in ai_report.failure_scenarios:
                ai_text += f"  {SYM_WARN} {scenario}\n"
            ai_text += "\n"
            
        if ai_report.reviewer_focus:
            ai_text += f"[bold {COLOR_WARNING}]Reviewer Focus Areas:[/bold {COLOR_WARNING}]\n"
            for focus in ai_report.reviewer_focus:
                ai_text += f"  {SYM_BULLET} {focus}\n"
            ai_text += "\n"

        if ai_report.suggested_tests:
            ai_text += f"[bold {COLOR_SUCCESS}]Suggested Tests:[/bold {COLOR_SUCCESS}]\n"
            for test in ai_report.suggested_tests:
                ai_text += f"  {SYM_CHECK} {test}\n"

        bottom_row = Table.grid(expand=True, padding=1)
        bottom_row.add_column(ratio=1)
        bottom_row.add_column(ratio=1)
        bottom_row.add_row(
            Panel(
                test_text.strip(),
                title="[bold]Test Coverage[/bold]",
                border_style=COLOR_WARNING if (test_report.missing_unit_tests or test_report.missing_integration_tests) else COLOR_SUCCESS
            ),
            Panel(ai_text.strip(), title="[bold]AI Review & Predictions[/bold]", border_style=COLOR_BORDER)
        )
        console.print(bottom_row)

    except GithubClientError as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise typer.Exit(code=1)


@app.command()
def history():
    """View analysis history."""
    try:
        from pr_sentinel.db import get_history
        records = get_history()

        if not records:
            console.print("[yellow]No analysis history found.[/yellow]")
            return

        table = Table(title="[bold]Analysis History[/bold]", border_style=COLOR_BORDER, expand=True)
        table.add_column("Date", style="dim")
        table.add_column("Repository", style="bold")
        table.add_column("PR", style="cyan")
        table.add_column("Risk Score", justify="right")
        table.add_column("Level")
        table.add_column("Changes", justify="right")

        for r in records:
            # Map string risk level back to RiskLevel enum for color mapping
            try:
                enum_level = RiskLevel(r.risk_level)
            except ValueError:
                enum_level = RiskLevel.LOW
            
            risk_color = _risk_color(enum_level)
            level_text = f"[{risk_color}]{r.risk_level}[/{risk_color}]"
            score_text = f"[{risk_color}]{r.risk_score}/100[/{risk_color}]"
            
            date_str = r.timestamp.strftime("%Y-%m-%d %H:%M")
            
            table.add_row(
                date_str,
                r.repo,
                f"#{r.pr_number} - {r.title}",
                score_text,
                level_text,
                f"+{r.additions}/-{r.deletions}"
            )

        console.print(table)
    except Exception as e:
        console.print(f"[bold red]Error loading history:[/bold red] {str(e)}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
