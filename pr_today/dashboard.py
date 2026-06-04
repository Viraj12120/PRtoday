"""Terminal UI dashboard for rendering PRtoday analysis results."""

import logging
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from pr_today.models import AnalysisResult

logger = logging.getLogger("pr_today.dashboard")


def _can_encode(char: str) -> bool:
    """Check if stdout can encode the specified character."""
    try:
        char.encode(sys.stdout.encoding or "ascii")
        return True
    except Exception:
        return False


class Dashboard:
    """Renders a dense, aesthetic terminal dashboard of the analysis results."""

    def __init__(self) -> None:
        self.console = Console()

    def render(self, result: AnalysisResult, author: str = "Unknown") -> None:
        """Render the full PR today dashboard using Rich components.

        Args:
            result: The populated AnalysisResult database model.
            author: The login name of the PR author.
        """
        # Determine color scheme based on risk level
        level = result.risk_level.upper()
        if level == "LOW":
            accent_color = "green"
        elif level == "MEDIUM":
            accent_color = "yellow"
        else:
            accent_color = "red"

        # Safe character encodings
        sym_dash = "—" if _can_encode("—") else "-"
        sym_folder = "📁 " if _can_encode("📁") else "[Dir] "
        sym_warn = "⚠️ " if _can_encode("⚠️") else "[!] "
        sym_cross = "❌ " if _can_encode("❌") else "[-] "
        sym_check = "✅ " if _can_encode("✅") else "[+] "
        sym_bullet = "• " if _can_encode("•") else "- "

        # 1. Header Panel
        header_text = Text()
        header_text.append("PR TODAY ", style="bold magenta")
        header_text.append(
            f"{sym_dash} AI-Assisted PR Risk Assessment\n", style="bold white"
        )
        header_text.append(
            f"Repository: {result.repo}  |  PR: #{result.pr_number}  |  Author: @{author}  |  Date: {result.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            style="dim white",
        )

        header_panel = Panel(
            header_text,
            border_style="cyan",
            padding=(1, 2),
        )

        # 2. Risk Score Panel
        # Large ASCII risk score representation dynamically rendered per PR score
        score_val = result.risk_score

        digits_unicode = {
            "0": ["  ████  ", " ██  ██ ", " ██  ██ ", " ██  ██ ", "  ████  "],
            "1": ["   ██   ", "  ███   ", "   ██   ", "   ██   ", "  ████  "],
            "2": ["  ████  ", "     ██ ", "   ███  ", "  ██    ", " ██████ "],
            "3": ["  ████  ", "     ██ ", "   ███  ", "     ██ ", "  ████  "],
            "4": [" ██  ██ ", " ██  ██ ", " ██████ ", "     ██ ", "     ██ "],
            "5": [" ██████ ", " ██     ", " █████  ", "     ██ ", " ██████ "],
            "6": ["  ████  ", " ██     ", " █████  ", " ██  ██ ", "  ████  "],
            "7": [" ██████ ", "     ██ ", "    ██  ", "   ██   ", "   ██   "],
            "8": ["  ████  ", " ██  ██ ", "  ████  ", " ██  ██ ", "  ████  "],
            "9": ["  ████  ", " ██  ██ ", "  █████ ", "     ██ ", "  ████  "],
        }

        digits_ascii = {
            "0": ["  ---   ", " |   |  ", " |   |  ", " |   |  ", "  ---   "],
            "1": ["   /|   ", "  / |   ", "    |   ", "    |   ", "  ----- "],
            "2": ["  ---   ", "     |  ", "  ---   ", " |      ", "  ----- "],
            "3": ["  ---   ", "     |  ", "  ---   ", "     |  ", "  ---   "],
            "4": [" |   |  ", " |   |  ", "  ---   ", "     |  ", "     |  "],
            "5": ["  ---   ", " |      ", "  ---   ", "     |  ", "  ---   "],
            "6": ["  ---   ", " |      ", "  ---   ", " |   |  ", "  ---   "],
            "7": ["  ---   ", "     |  ", "    /   ", "   /    ", "  /     "],
            "8": ["  ---   ", " |   |  ", "  ---   ", " |   |  ", "  ---   "],
            "9": ["  ---   ", " |   |  ", "  ---   ", "     |  ", "  ---   "],
        }

        score_str = str(score_val)
        digits_dict = digits_unicode if _can_encode("█") else digits_ascii

        ascii_lines = []
        for i in range(5):
            line_parts = []
            for digit in score_str:
                line_parts.append(digits_dict[digit][i])
            ascii_lines.append(" ".join(line_parts))

        ascii_score = (
            "\n"
            + "\n".join(ascii_lines)
            + f"\n\n     PR Score: {score_val}/100 [{level}]\n"
        )

        # A breakdown table of deterministic components
        breakdown_table = Table(show_header=True, box=None, padding=(0, 2))
        breakdown_table.add_column("Risk Dimension", style="bold white")
        breakdown_table.add_column("Severity Score", justify="right", style="cyan")

        breakdown_table.add_row(
            "Volume & Criticality (30%)",
            f"{'Yes' if len(result.files_changed) > 0 else 'No'}",
        )
        breakdown_table.add_row(
            "Database Migrations (30%)",
            f"{'DETECTED' if result.db_migrations_detected else 'None'}",
            style="red" if result.db_migrations_detected else "green",
        )
        breakdown_table.add_row(
            "Config/Secret Changes (25%)",
            f"{'DETECTED' if result.config_changes_detected else 'None'}",
            style="red" if result.config_changes_detected else "green",
        )
        breakdown_table.add_row(
            "Dependency Shifts (15%)",
            f"{'DETECTED' if result.dependency_changes_detected else 'None'}",
            style="yellow" if result.dependency_changes_detected else "green",
        )

        score_content = Table.grid(expand=True, padding=1)
        score_content.add_column(ratio=1)
        score_content.add_column(ratio=2)
        score_content.add_row(
            Text(ascii_score, style=f"bold {accent_color}"),
            Panel(breakdown_table, title="Score Breakdown", border_style="dim white"),
        )

        score_panel = Panel(
            score_content,
            title="[bold]Risk Assessment[/bold]",
            border_style=accent_color,
            padding=(1, 2),
        )

        # 3. Blast Radius Tree View Panel
        # Create tree representation of affected packages/directories
        blast_tree = Tree("Impacted Packages")
        if result.blast_radius:
            for mod in result.blast_radius:
                blast_tree.add(f"[cyan]{sym_folder}{mod}[/cyan]")
        else:
            blast_tree.add("[dim]No modules affected (empty change list).[/dim]")

        blast_panel = Panel(
            blast_tree,
            title="[bold]Blast Radius[/bold]",
            border_style="blue",
            padding=(1, 2),
        )

        # 4. Missing Tests Panel
        missing_tests_text = Text()
        if result.missing_tests:
            missing_tests_text.append(
                f"{sym_warn}Missing tests for files:\n", style="bold yellow"
            )
            for f in result.missing_tests:
                missing_tests_text.append(f"  {sym_cross}{f}\n", style="red")
        else:
            missing_tests_text.append(
                f"{sym_check}All changed source files have corresponding tests.",
                style="bold green",
            )

        tests_panel = Panel(
            missing_tests_text,
            title="[bold]Missing Test Coverage[/bold]",
            border_style="yellow" if result.missing_tests else "green",
            padding=(1, 2),
        )

        # 5. AI Review Panel
        ai_text = Text()
        if result.ai_summary is None:
            ai_text.append("AI review disabled.\n", style="dim italic white")
        else:
            ai_text.append("Summary:\n", style="bold cyan")
            ai_text.append(f"{result.ai_summary}\n\n", style="white")

            if result.ai_failures:
                ai_text.append("Potential Failure Scenarios:\n", style="bold red")
                for scenario in result.ai_failures:
                    ai_text.append(f"  {sym_bullet}{scenario}\n", style="red")
                ai_text.append("\n")

            if result.ai_focus_areas:
                ai_text.append("Reviewer Focus Areas:\n", style="bold yellow")
                for area in result.ai_focus_areas:
                    ai_text.append(f"  {sym_bullet}{area}\n", style="yellow")

        ai_panel = Panel(
            ai_text,
            title="[bold]AI Predictions & Code Review[/bold]",
            border_style="magenta",
            padding=(1, 2),
        )

        # Build UI layout
        self.console.print(header_panel)

        # Risk score panel takes full width
        self.console.print(score_panel)

        # Next layer: Blast Radius and Missing Tests side-by-side
        middle_table = Table.grid(expand=True, padding=1)
        middle_table.add_column(ratio=1)
        middle_table.add_column(ratio=1)
        middle_table.add_row(blast_panel, tests_panel)
        self.console.print(middle_table)

        # Bottom layer: AI Review taking full width
        self.console.print(ai_panel)
