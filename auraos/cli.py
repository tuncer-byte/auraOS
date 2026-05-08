"""auraOS komut satırı arayüzü."""
from __future__ import annotations
import os
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from auraos import AutonomousAgent, Agent, Task
from auraos.fintech import OnboardingAgent

app = typer.Typer(help="auraOS - Kurumsal sınıf finansal AI Agent Framework")
console = Console()


def _check_api_key():
    """API key kontrolü — yoksa kullanıcıya bilgi ver."""
    if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or
            os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")):
        console.print(
            "[bold red]HATA:[/] Hiçbir LLM provider API anahtarı bulunamadı.\n"
            "Lütfen şunlardan birini tanımlayın:\n"
            "  • GEMINI_API_KEY (önerilen)\n"
            "  • OPENAI_API_KEY\n"
            "  • ANTHROPIC_API_KEY\n\n"
            "Örnek:\n"
            "  export GEMINI_API_KEY='your-key-here'\n"
            "  auraos run \"5 ile 7'yi topla\"",
            style="yellow",
        )
        sys.exit(1)


@app.command()
def version():
    """Sürüm bilgisi."""
    from auraos import __version__
    console.print(f"[bold cyan]auraOS[/] v{__version__}")


@app.command()
def run(
    prompt: str = typer.Argument(..., help="Çalıştırılacak prompt/görev"),
    model: str = typer.Option("gemini/gemini-2.5-flash", "--model", "-m", help="LLM model (provider/model)"),
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Autonomous mod workspace yolu"),
    autonomous: bool = typer.Option(False, "--autonomous", "-a", help="AutonomousAgent kullan (dosya okuma/yazma)"),
    max_iterations: int = typer.Option(10, "--max-iter", help="Maksimum iteration"),
):
    """Hızlı bir agent çalıştır.

    Örnekler:
      auraos run "Merhaba dünya"
      auraos run "5 ile 7'yi topla" -m anthropic/claude-sonnet-4-6
      auraos run "Rapor yaz" --autonomous -w ./workspace
    """
    _check_api_key()

    if autonomous:
        if workspace is None:
            workspace = Path("./workspace")
        console.print(f"[dim]AutonomousAgent başlatılıyor: {workspace}[/]")
        agent = AutonomousAgent(model=model, workspace=workspace, max_iterations=max_iterations)
    else:
        console.print(f"[dim]Agent başlatılıyor: {model}[/]")
        agent = Agent(model=model, max_iterations=max_iterations)

    console.print(f"[bold cyan]Görev:[/] {prompt}\n")
    resp = agent.run(Task(description=prompt))

    if resp.success:
        console.print(f"[bold green]✓ Tamamlandı ({resp.iterations} iter, {resp.duration_ms:.0f}ms)[/]\n")
        console.print(resp.output)
        if resp.tool_calls:
            console.print(f"\n[dim]Tool çağrıları: {', '.join(tc.name for tc in resp.tool_calls)}[/]")
    else:
        console.print(f"[bold red]✗ Hata:[/] {resp.error}")


@app.command()
def onboard(
    name: str = typer.Option(..., "--name", help="Müşteri adı"),
    tc: str = typer.Option(..., "--tc", help="TC kimlik no"),
    birth: str = typer.Option(..., "--birth", help="Doğum tarihi (YYYY-MM-DD)"),
    address: str = typer.Option(..., "--address", help="Adres"),
    model: str = typer.Option("gemini/gemini-2.5-flash", "--model"),
):
    """Onboarding ajanını çalıştır.

    Örnek:
      auraos onboard --name "Mehmet Yılmaz" --tc 12345678901 \\
        --birth 1990-01-15 --address "İstanbul/Kadıköy"
    """
    _check_api_key()
    console.print("[bold cyan]Onboarding Agent[/]")
    agent = OnboardingAgent(model=model)
    task = Task(
        description=(
            f"Şu müşteriyi onboard et:\n"
            f"Ad: {name}\nTC: {tc}\nDoğum: {birth}\nAdres: {address}"
        )
    )
    resp = agent.run(task)
    console.print(resp.output)


@app.command()
def info():
    """auraOS v0.2 bileşenlerini listele."""
    table = Table(title="auraOS v0.2 - Kurumsal Modüller", show_lines=True)
    table.add_column("Kategori", style="cyan")
    table.add_column("Bileşenler", style="white")

    table.add_row(
        "Çekirdek",
        "Agent, AutonomousAgent, Task, AgentResponse, ToolRegistry, @tool"
    )
    table.add_row(
        "LLM",
        "Gemini, OpenAI (GPT), Anthropic (Claude), Ollama\n"
        "[dim]Factory:[/] get_llm(\"gemini/gemini-2.5-flash\")"
    )
    table.add_row(
        "Hafıza",
        "SessionManager (InMemory/Redis), ConversationMemory"
    )
    table.add_row(
        "Bilgi Tabanı",
        "KnowledgeBase + 4 embedding provider:\n"
        "Hash, OpenAI, Gemini, SentenceTransformer"
    )
    table.add_row(
        "Güvenlik",
        "Guardrails (PII redact, prompt injection)\n"
        "RBACGuard (rol bazlı tool erişim)\n"
        "Principal, AuthorizationError"
    )
    table.add_row(
        "Observability",
        "AuditLog (hash zinciri)\n"
        "CostTracker (token + USD)\n"
        "MetricsRegistry (Prometheus)\n"
        "JsonFormatter + correlation_id"
    )
    table.add_row(
        "Güvenilirlik",
        "CircuitBreaker (closed→open→half_open)\n"
        "RateLimiter (token bucket)\n"
        "IdempotencyStore\n"
        "RetryPolicy (exponential backoff)"
    )
    table.add_row(
        "Cache",
        "InMemoryCache, RedisCache"
    )
    table.add_row(
        "Fintech",
        "kyc, aml, risk, katilim, fx, settlement, market\n"
        "Özel agent'lar: OnboardingAgent, AMLAgent"
    )
    table.add_row(
        "Team",
        "Team (Sequential, Coordinate, Route)"
    )

    console.print(table)
    console.print("\n[bold]Kurulum:[/]")
    console.print("  pip install auraos[google]      # Gemini")
    console.print("  pip install auraos[all]         # Tüm provider'lar")


@app.command()
def test():
    """Framework sağlık kontrolü (API key + import testi)."""
    console.print("[bold]auraOS Sağlık Kontrolü[/]\n")

    # Versiyon
    from auraos import __version__
    console.print(f"✓ Versiyon: [cyan]{__version__}[/]")

    # API key
    has_key = False
    for k in ["GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"]:
        if os.getenv(k):
            console.print(f"✓ API key: [green]{k} tanımlı[/]")
            has_key = True
            break
    if not has_key:
        console.print("✗ API key: [red]Hiçbiri tanımlı değil[/]")

    # Import testi
    try:
        from auraos import (
            Agent, AuditLog, CostTracker, Guardrails,
            MetricsRegistry, RateLimiter, SessionManager,
        )
        console.print("✓ Import: [green]Tüm modüller yüklü[/]")
    except ImportError as e:
        console.print(f"✗ Import hatası: [red]{e}[/]")
        sys.exit(1)

    console.print("\n[bold green]Framework hazır.[/]")


if __name__ == "__main__":
    app()
