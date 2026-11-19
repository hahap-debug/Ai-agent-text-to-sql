"""
Standalone Test Script for AI Data Agent with Benchmark Test Set
Run queries directly against MySQL ecommerce_db and view real-time LLM ReAct steps.

Usage:
    python test_query.py                  # Show list of tests and run test #1
    python test_query.py 1                # Run test question #1 (1 to 10)
    python test_query.py 5                # Run test question #5
    python test_query.py --list           # Display all 10 benchmark questions
    python test_query.py --all            # Run all 10 tests in sequence and show summary report
    python test_query.py "คำถามเอง"       # Run any custom question
    python test_query.py 1 --gemini       # Run test #1 using Gemini
    python test_query.py 1 --model qwen2.5-coder:3b  # Run test #1 using specific Ollama model
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import json
import time
import argparse

# Ensure UTF-8 output on Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich.markdown import Markdown

from src.config import Config
from src.database import DatabaseConnection
from src.agent import DatabaseAgent, AgentStep
from src.test_sets import TEST_SET

console = Console(force_terminal=True)

def step_callback(step: AgentStep):
    step_box = f"[bold cyan]─── Step {step.step_number} ───[/bold cyan]"
    console.print(f"\n{step_box}")
    if step.thought:
        console.print(f"🧠 [bold]Thought:[/bold] {step.thought}")
    if step.tool_name:
        console.print(f"⚡ [bold yellow]Action:[/bold yellow] [bold]{step.tool_name}[/bold]({json.dumps(step.parameters, ensure_ascii=False)})")
    if step.is_error:
        console.print(f"❌ [bold red]Error:[/bold red] {step.observation}")
        console.print("🔄 [yellow]Triggering Self-Healing Loop...[/yellow]")
    else:
        if step.tool_name == "execute_sql" and isinstance(step.observation, list):
            console.print(f"👁️ [bold green]Observation:[/bold green] ได้รับข้อมูล {len(step.observation)} รายการ")
            if step.observation:
                table = Table(title="Preview Results", show_lines=True)
                for col in step.observation[0].keys():
                    table.add_column(str(col), style="cyan")
                for row in step.observation[:5]:
                    table.add_row(*[str(v) for v in row.values()])
                console.print(table)
        else:
            obs_str = str(step.observation)
            if len(obs_str) > 250:
                obs_str = obs_str[:250] + "... [truncated]"
            console.print(f"👁️ [bold green]Observation:[/bold green] {obs_str}")

def print_test_list():
    table = Table(title="📋 Benchmark Test Set (10 Questions)", show_lines=True)
    table.add_column("#", style="bold yellow", width=4)
    table.add_column("Question (คำถามทดสอบ)", style="white")
    for idx, q in enumerate(TEST_SET, 1):
        table.add_row(str(idx), q)
    console.print(table)

def run_single_query(agent: DatabaseAgent, question: str, test_idx: int = None):
    label = f"Test #{test_idx}: " if test_idx else ""
    console.print(f"\n[bold magenta]══════════════════════════════════════════════════[/bold magenta]")
    console.print(f"[bold cyan]🎯 {label}[/bold cyan][bold white]{question}[/bold white]")
    console.print(f"[bold magenta]══════════════════════════════════════════════════[/bold magenta]")

    start_time = time.time()
    with console.status(f"[bold green]🤖 LLM กำลังคิดและประมวลผล... ({agent.provider}: {agent.model_name})[/bold green]", spinner="dots"):
        result = agent.run(question, step_callback=step_callback)
    duration = time.time() - start_time

    if result.last_executed_sql:
        console.print("\n[bold]📄 Executed SQL Query:[/bold]")
        syntax = Syntax(result.last_executed_sql, "sql", theme="monokai", line_numbers=True)
        console.print(syntax)

    console.print(f"\n[dim]⏱️ ใช้เวลาประมวลผลทั้งหมด: {duration:.2f} วินาที[/dim]")
    console.print(Panel(Markdown(result.final_answer), title="[bold green]📊 Final Executive Business Report[/bold green]", border_style="green"))
    return result, duration

def run_batch_test(agent: DatabaseAgent):
    console.print(Panel(f"[bold magenta]🚀 Running Full Benchmark Test Set (10 Questions)[/bold magenta]\nProvider: [cyan]{agent.provider}[/cyan] | Model: [cyan]{agent.model_name}[/cyan]", border_style="magenta"))
    
    results = []
    total_start = time.time()

    for idx, q in enumerate(TEST_SET, 1):
        console.print(f"\n[bold yellow]▶ Running [{idx}/{len(TEST_SET)}]:[/bold yellow] {q}")
        t0 = time.time()
        res = agent.run(q)
        dt = time.time() - t0
        rows_count = len(res.last_query_result) if res.last_query_result else 0
        success = res.success and res.last_executed_sql is not None
        results.append({
            "idx": idx,
            "question": q,
            "success": success,
            "rows": rows_count,
            "time": dt,
            "sql": (res.last_executed_sql or "N/A").strip().replace("\n", " ")[:60] + "..."
        })
        status_icon = "✅" if success else "❌"
        console.print(f"  {status_icon} Rows: {rows_count} | Time: {dt:.2f}s | Steps: {len(res.steps)}")

    total_time = time.time() - total_start

    # Summary Scorecard
    summary_table = Table(title=f"📊 Benchmark Scorecard ({agent.model_name})", show_lines=True)
    summary_table.add_column("#", width=3, style="bold")
    summary_table.add_column("Status", width=8)
    summary_table.add_column("Question", width=40)
    summary_table.add_column("Rows", width=6)
    summary_table.add_column("Time (s)", width=8)
    summary_table.add_column("SQL Preview", width=45)

    passed = 0
    for r in results:
        status_str = "[bold green]PASS[/bold green]" if r["success"] else "[bold red]FAIL[/bold red]"
        if r["success"]: passed += 1
        summary_table.add_row(
            str(r["idx"]),
            status_str,
            r["question"],
            str(r["rows"]),
            f"{r['time']:.2f}",
            r["sql"]
        )

    console.print("\n")
    console.print(summary_table)
    score_pct = (passed / len(TEST_SET)) * 100
    color = "green" if score_pct >= 80 else ("yellow" if score_pct >= 50 else "red")
    console.print(Panel(f"Passed: [bold {color}]{passed}/{len(TEST_SET)} ({score_pct:.1f}%)[/bold {color}] | Total Time: [bold]{total_time:.2f}s[/bold]", title="Final Result", border_style=color))

def main():
    args = sys.argv[1:]

    # Parse special flags
    if "--gemini" in args:
        provider = "gemini"
        args.remove("--gemini")
    elif "--ollama" in args:
        provider = "ollama"
        args.remove("--ollama")
    elif "--mock" in args:
        provider = "mock"
        args.remove("--mock")
    else:
        provider = Config.LLM_PROVIDER

    custom_model = None
    if "--model" in args:
        m_idx = args.index("--model")
        if m_idx + 1 < len(args):
            custom_model = args[m_idx + 1]
            args.pop(m_idx + 1)
            args.pop(m_idx)

    # Initialize DB & Agent
    db = DatabaseConnection()
    success, db_msg = db.test_connection()

    model_name = custom_model or (Config.GEMINI_MODEL if provider == "gemini" else Config.OLLAMA_MODEL)
    agent = DatabaseAgent(db=db, provider=provider, model_name=model_name)

    if "--list" in args:
        print_test_list()
        return

    if "--all" in args:
        run_batch_test(agent)
        return

    # Check if user passed an index number (1-10)
    if len(args) == 1 and args[0].isdigit():
        idx = int(args[0])
        if 1 <= idx <= len(TEST_SET):
            question = TEST_SET[idx - 1]
            run_single_query(agent, question, test_idx=idx)
            return
        else:
            console.print(f"[bold red]❌ Index {idx} out of range (1 - {len(TEST_SET)})[/bold red]")
            return

    # Check if freeform question
    if args:
        question = " ".join(args)
        run_single_query(agent, question)
        return

    # If no argument passed, show list and run Test #1 with instruction
    print_test_list()
    console.print("\n[dim]💡 Tip: ระบุเลขข้อเพื่อรันข้อนั้นได้เลย เช่น [bold cyan]python test_query.py 2[/bold cyan] หรือ [bold cyan]python test_query.py --all[/bold cyan][/dim]")
    console.print("[yellow]กำลังรันข้อที่ 1 เป็นตัวอย่างเริ่มต้น...[/yellow]\n")
    run_single_query(agent, TEST_SET[0], test_idx=1)

if __name__ == "__main__":
    main()
