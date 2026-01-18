"""
CLI commands for Memory Palace.

This module provides a rich command-line interface for:
- Ingesting documents
- Querying memories
- Managing the database
- Running the API server
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from config.schema import SourceType

console = Console()


@click.group()
@click.version_option(version="1.0.0", prog_name="Memory Palace")
def cli():
    """
    Memory Palace - Personal AI Knowledge Management System

    A RAG-based system for storing and querying your personal memories
    from conversation transcripts and notes.
    """
    pass


@cli.command()
@click.argument("query")
@click.option("--top-k", "-k", default=10, help="Number of results to return")
@click.option("--synthesize/--no-synthesize", default=True, help="Generate AI synthesis")
@click.option("--export", "-e", type=click.Choice(["json", "markdown"]), help="Export format")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
def query(
    query: str,
    top_k: int,
    synthesize: bool,
    export: Optional[str],
    output: Optional[str],
):
    """
    Query your memory database.

    Examples:
        memory-palace query "What did I discuss about AI safety?"
        memory-palace query "conversations with John last month" -k 20
        memory-palace query "project planning" --export markdown -o results.md
    """
    from query.query_engine import get_query_engine
    from query.result_synthesizer import get_result_synthesizer

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Searching memories...", total=None)

        engine = get_query_engine(settings.anthropic_api_key)
        response = engine.query(
            query_text=query,
            top_k=top_k,
            synthesize_results=synthesize,
        )

    if not response.results:
        console.print("[yellow]No memories found matching your query.[/yellow]")
        return

    # Display results
    console.print(f"\n[bold green]Found {response.total_results} memories[/bold green]")
    console.print(f"[dim]Query time: {response.processing_time_ms:.0f}ms[/dim]\n")

    # Show synthesis if available
    if response.synthesis:
        console.print(Panel(
            Markdown(response.synthesis),
            title="[bold]AI Summary[/bold]",
            border_style="blue",
        ))
        console.print()

    # Show individual results
    for i, result in enumerate(response.results[:10], 1):
        timestamp = result.metadata.timestamp.strftime("%Y-%m-%d %H:%M")
        participants = ", ".join(result.metadata.participants) if result.metadata.participants else "Unknown"
        score = f"{result.score:.2f}"

        console.print(f"[bold cyan]{i}. [{timestamp}][/bold cyan] ({participants}) [dim]score: {score}[/dim]")

        # Truncate long text
        preview = result.text[:300] + "..." if len(result.text) > 300 else result.text
        console.print(f"   {preview}\n")

    # Export if requested
    if export:
        synthesizer = get_result_synthesizer(settings.anthropic_api_key)

        if export == "json":
            content = synthesizer.export_json(query, response.results)
            ext = ".json"
        else:
            content = synthesizer.export_markdown(query, response.results)
            ext = ".md"

        if output:
            output_path = Path(output)
        else:
            output_path = Path(f"memory_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}")

        output_path.write_text(content)
        console.print(f"\n[green]Exported to: {output_path}[/green]")


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--tags", "-t", multiple=True, help="Custom tags to apply")
@click.option("--recursive/--no-recursive", default=True, help="Search subdirectories")
@click.option("--pattern", "-p", multiple=True, help="File patterns (e.g., *.txt)")
def ingest(
    path: str,
    tags: tuple,
    recursive: bool,
    pattern: tuple,
):
    """
    Ingest documents into the memory database.

    Examples:
        memory-palace ingest ./transcripts/
        memory-palace ingest meeting.txt -t work -t important
        memory-palace ingest ./notes/ --pattern "*.md" --pattern "*.txt"
    """
    from ingestion.batch_importer import get_batch_importer

    path = Path(path)
    custom_tags = list(tags) if tags else None
    patterns = list(pattern) if pattern else None

    importer = get_batch_importer()

    if path.is_file():
        # Single file
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(f"Ingesting {path.name}...", total=None)

            result = importer.import_file(
                path,
                custom_tags=custom_tags,
            )

        if result.success:
            console.print(f"[green]✓ Ingested {path.name}: {result.chunks_created} chunks created[/green]")
        else:
            console.print(f"[red]✗ Failed: {result.error_message}[/red]")

    else:
        # Directory
        def progress_callback(current, total, filename):
            console.print(f"  [{current}/{total}] {filename}", end="\r")

        console.print(f"[bold]Ingesting from {path}...[/bold]\n")

        results = importer.import_directory(
            directory=path,
            patterns=patterns,
            recursive=recursive,
            custom_tags=custom_tags,
            progress_callback=progress_callback,
        )

        # Summary
        successful = sum(1 for r in results.values() if r.success and not r.duplicate)
        duplicates = sum(1 for r in results.values() if r.duplicate)
        failed = sum(1 for r in results.values() if not r.success)

        console.print("\n")
        table = Table(title="Ingestion Summary")
        table.add_column("Status", style="bold")
        table.add_column("Count")
        table.add_row("[green]Successful[/green]", str(successful))
        table.add_row("[yellow]Duplicates[/yellow]", str(duplicates))
        table.add_row("[red]Failed[/red]", str(failed))
        console.print(table)


@cli.command()
@click.argument("text")
@click.option("--tags", "-t", multiple=True, help="Custom tags")
@click.option("--participants", "-p", multiple=True, help="Participants")
def add(text: str, tags: tuple, participants: tuple):
    """
    Add a quick note or memory.

    Examples:
        memory-palace add "Discussed project timeline with team"
        memory-palace add "AI model training ideas" -t ai -t research
    """
    from ingestion.batch_importer import get_batch_importer

    importer = get_batch_importer()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Adding memory...", total=None)

        result = importer.import_text(
            text=text,
            custom_tags=list(tags) if tags else None,
            participants=list(participants) if participants else None,
        )

    if result.success:
        console.print(f"[green]✓ Memory added (ID: {result.doc_id})[/green]")
    else:
        console.print(f"[red]✗ Failed: {result.error_message}[/red]")


@cli.command()
@click.argument("topic")
@click.option("--top-k", "-k", default=50, help="Maximum entries")
def timeline(topic: str, top_k: int):
    """
    Generate a chronological timeline for a topic.

    Examples:
        memory-palace timeline "AI safety"
        memory-palace timeline "project updates" -k 100
    """
    from query.query_engine import get_query_engine

    engine = get_query_engine(settings.anthropic_api_key)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Building timeline...", total=None)

        results = engine.get_timeline(topic, top_k=top_k)

    if not results:
        console.print("[yellow]No memories found for timeline.[/yellow]")
        return

    console.print(f"\n[bold]Timeline: {topic}[/bold]")
    console.print(f"[dim]{len(results)} entries[/dim]\n")

    current_date = None
    for result in results:
        date_str = result.metadata.timestamp.strftime("%Y-%m-%d")
        time_str = result.metadata.timestamp.strftime("%H:%M")

        if date_str != current_date:
            current_date = date_str
            console.print(f"\n[bold cyan]═══ {date_str} ═══[/bold cyan]")

        participants = ", ".join(result.metadata.participants) if result.metadata.participants else ""
        preview = result.text[:200] + "..." if len(result.text) > 200 else result.text

        if participants:
            console.print(f"[dim]{time_str}[/dim] ({participants})")
        else:
            console.print(f"[dim]{time_str}[/dim]")
        console.print(f"  {preview}\n")


@cli.command()
def stats():
    """Show database statistics."""
    from storage.vector_db import get_vector_db
    from storage.embedding_service import get_embedding_service
    from query.query_engine import get_query_engine

    db = get_vector_db()
    embedding = get_embedding_service()
    engine = get_query_engine(settings.anthropic_api_key)

    db_stats = db.get_stats()

    table = Table(title="Memory Palace Statistics")
    table.add_column("Metric", style="bold")
    table.add_column("Value")

    table.add_row("Total Chunks", str(db_stats.get("total_chunks", 0)))
    table.add_row("Total Documents", str(db_stats.get("total_documents", 0)))
    table.add_row("Collection Name", db_stats.get("collection_name", "N/A"))
    table.add_row("Embedding Model", embedding.model_name)
    table.add_row("Embedding Dimension", str(embedding.embedding_dimension))
    table.add_row("Database Available", "✓" if db.is_available else "✗")
    table.add_row("LLM Available", "✓" if engine.planner.is_available else "✗")

    console.print(table)


@cli.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option("--port", default=8000, help="Port to listen on")
@click.option("--reload", is_flag=True, help="Enable auto-reload")
def serve(host: str, port: int, reload: bool):
    """
    Start the REST API server.

    Examples:
        memory-palace serve
        memory-palace serve --host 0.0.0.0 --port 8080
        memory-palace serve --reload  # for development
    """
    console.print(f"[bold green]Starting Memory Palace API server...[/bold green]")
    console.print(f"[dim]Host: {host}, Port: {port}[/dim]")
    console.print(f"[dim]API docs: http://{host}:{port}/docs[/dim]\n")

    from api.rest_api import run_server
    run_server(host=host, port=port, reload=reload)


@cli.command()
@click.option("--directory", "-d", type=click.Path(exists=True), help="Directory to watch")
@click.option("--interval", default=30, help="Check interval in seconds")
def watch(directory: Optional[str], interval: int):
    """
    Watch a directory for new files and auto-ingest.

    Examples:
        memory-palace watch -d ./incoming/
        memory-palace watch -d ./transcripts/ --interval 60
    """
    from ingestion.batch_importer import get_batch_importer

    watch_dir = directory or settings.get("ingestion", "watch_folder", default="./data/raw")
    watch_path = Path(watch_dir)

    if not watch_path.exists():
        watch_path.mkdir(parents=True)
        console.print(f"[dim]Created watch directory: {watch_path}[/dim]")

    importer = get_batch_importer()

    console.print(f"[bold green]Watching {watch_path} for new files...[/bold green]")
    console.print(f"[dim]Check interval: {interval}s. Press Ctrl+C to stop.[/dim]\n")

    def on_file_processed(result):
        if result.success:
            console.print(f"[green]✓ {result.doc_id}: {result.chunks_created} chunks[/green]")
        else:
            console.print(f"[red]✗ {result.doc_id}: {result.error_message}[/red]")

    try:
        asyncio.run(
            importer.watch_directory(
                directory=watch_path,
                interval_seconds=interval,
                callback=on_file_processed,
            )
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Watch stopped.[/yellow]")


@cli.command()
@click.option("--all", "sync_all", is_flag=True, help="Sync all transcripts")
@click.option("--since-days", default=7, help="Sync transcripts from last N days")
def fireflies(sync_all: bool, since_days: int):
    """
    Sync transcripts from Fireflies.ai.

    Examples:
        memory-palace fireflies
        memory-palace fireflies --all
        memory-palace fireflies --since-days 30
    """
    from api.fireflies_sync import get_fireflies_sync
    from datetime import timedelta

    fireflies_sync = get_fireflies_sync(settings.fireflies_api_key)

    if not fireflies_sync.is_configured:
        console.print("[red]Fireflies API key not configured.[/red]")
        console.print("[dim]Set FIREFLIES_API_KEY or add to config/settings.local.yaml[/dim]")
        return

    since_date = None if sync_all else datetime.now() - timedelta(days=since_days)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Syncing Fireflies transcripts...", total=None)

        result = asyncio.run(
            fireflies_sync.sync_transcripts(
                sync_all=sync_all,
                since_date=since_date,
            )
        )

    if result["success"]:
        console.print(f"[green]✓ {result['message']}[/green]")
        if result.get("errors"):
            console.print("[yellow]Some errors occurred:[/yellow]")
            for error in result["errors"][:5]:
                console.print(f"  - {error}")
    else:
        console.print(f"[red]✗ Sync failed: {result['message']}[/red]")


@cli.command()
@click.confirmation_option(prompt="Are you sure you want to clear all memories?")
def clear():
    """Clear all memories from the database."""
    from storage.vector_db import get_vector_db

    db = get_vector_db()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Clearing database...", total=None)
        db.clear()

    console.print("[yellow]All memories have been cleared.[/yellow]")


@cli.command()
def interactive():
    """
    Start an interactive query session.

    Provides a REPL-style interface for querying memories.
    """
    from query.query_engine import get_query_engine

    engine = get_query_engine(settings.anthropic_api_key)

    console.print("[bold]Memory Palace Interactive Mode[/bold]")
    console.print("[dim]Type your queries, or 'quit' to exit.[/dim]\n")

    while True:
        try:
            query_text = console.input("[bold cyan]Query>[/bold cyan] ")

            if query_text.lower() in ("quit", "exit", "q"):
                break

            if not query_text.strip():
                continue

            response = engine.query(query_text, top_k=5)

            if response.synthesis:
                console.print(Panel(
                    Markdown(response.synthesis),
                    title="Answer",
                    border_style="green",
                ))
            elif response.results:
                for result in response.results[:3]:
                    timestamp = result.metadata.timestamp.strftime("%Y-%m-%d")
                    preview = result.text[:200] + "..."
                    console.print(f"[dim]{timestamp}[/dim]: {preview}\n")
            else:
                console.print("[yellow]No relevant memories found.[/yellow]")

            console.print()

        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    console.print("\n[dim]Goodbye![/dim]")


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
