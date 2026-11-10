"""
Interactive CLI for E-Commerce AI Data Analytics Agent
Run autonomous ReAct analysis directly from your terminal with rich formatting.
"""

import sys
import json

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.syntax import Syntax

from src.config import Config
from src.database import DatabaseConnection
from src.agent import DatabaseAgent, AgentStep

console = Console(force_terminal=True)

def print_welcome_banner(db_status: str, has_api_key: bool):
    if Config.LLM_PROVIDER == "ollama":
        mode_text = f"[green]Local Ollama ({Config.OLLAMA_MODEL})[/green]"
    elif Config.LLM_PROVIDER == "gemini" and has_api_key:
        mode_text = f"[green]Google Gemini ({Config.GEMINI_MODEL})[/green]"
    else:
        mode_text = "[yellow]Mock / Simulation Mode (Offline Demo)[/yellow]"

    banner = f"""[bold magenta]🚀 AI Data Analytics & Database Agent (ReAct Loop)[/bold magenta]
[dim]Based on AGENTS.md Specification for ecommerce_db[/dim]

• Database: {db_status}
• Engine: {mode_text}
• AST Safety: [bold green]sqlglot MySQL 8.x Validator (Read-Only)[/bold green]
"""
    console.print(Panel(banner, border_style="cyan"))

def render_step_callback(step: AgentStep):
    """Callback to render ReAct steps in real time."""
    step_header = f"[bold cyan]Step {step.step_number}[/bold cyan]"
    
    if step.thought:
        console.print(f"\n🧠 {step_header} [bold]Thought:[/bold] {step.thought}")

    if step.tool_name:
        console.print(f"⚡ [bold yellow]Action:[/bold yellow] [bold]{step.tool_name}[/bold]({json.dumps(step.parameters, ensure_ascii=False)})")

    if step.is_error:
        console.print(f"❌ [bold red]Observation (Error):[/bold red] {step.observation}")
        console.print("🔄 [dim yellow]-> Triggering Self-Correction / Self-Healing Loop...[/dim yellow]")
    elif step.observation is not None:
        if step.tool_name == "execute_sql" and isinstance(step.observation, list):
            row_count = len(step.observation)
            console.print(f"👁️ [bold green]Observation:[/bold green] Retrieved {row_count} row(s)")
            if row_count > 0:
                table = Table(title=f"Query Result Preview (Top {min(row_count, 5)})", show_lines=True)
                sample = step.observation[0]
                for col in sample.keys():
                    table.add_column(str(col), style="cyan")
                for row in step.observation[:5]:
                    table.add_row(*[str(v) for v in row.values()])
                console.print(table)
        else:
            obs_str = str(step.observation)
            if len(obs_str) > 400:
                obs_str = obs_str[:400] + "... [truncated]"
            console.print(f"👁️ [bold green]Observation:[/bold green] {obs_str}")

def main():
    db = DatabaseConnection()
    is_connected, db_msg = db.test_connection()
    has_api_key = Config.is_api_key_set()

    print_welcome_banner(
        f"[green]{db_msg}[/green]" if is_connected else f"[red]{db_msg}[/red]",
        has_api_key
    )

    if not is_connected and Config.DB_TYPE == "mysql":
        console.print("[yellow]Tip: If your MySQL is running, check DB_HOST, DB_USER, DB_PASSWORD in .env[/yellow]")

    agent = DatabaseAgent(db=db)

    # Check if question passed as CLI argument
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        run_question(agent, question)
        return

    # Interactive prompt loop
    while True:
        try:
            console.print("\n[bold green]?[/bold green] [bold]พิมพ์คำถามธุรกิจเป็นภาษาไทย (หรือ 'exit' เพื่อออก):[/bold]")
            question = input("> ").strip()
            if not question:
                continue
            if question.lower() in ("exit", "quit", "q"):
                console.print("[yellow]ขอบคุณสำหรับการใช้งาน AI Data Agent สวัสดีครับ![/yellow]")
                break

            run_question(agent, question)

        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Exiting...[/yellow]")
            break

def run_question(agent: DatabaseAgent, question: str):
    console.print(Panel(f"[bold white]{question}[/bold white]", title="[bold]Business Question[/bold]", border_style="blue"))
    
    with console.status("[bold green]Agent is reasoning...[/bold green]", spinner="dots"):
        result = agent.run(question, step_callback=render_step_callback)

    if result.last_executed_sql:
        console.print("\n[bold]Executed SQL Statement:[/bold]")
        syntax = Syntax(result.last_executed_sql, "sql", theme="monokai", line_numbers=True)
        console.print(syntax)

    console.print("\n" + "=" * 60)
    console.print(Panel(Markdown(result.final_answer), title="[bold green]📊 Final Executive Business Report[/bold green]", border_style="green"))
    console.print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
