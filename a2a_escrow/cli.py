"""CLI interface for a2a-escrow."""

import json
import sys

import click
from rich.console import Console
from rich.table import Table

from a2a_escrow.client import EscrowClient, EscrowClientError

console = Console()


def get_client(exchange: str | None = None, json_output: bool = False) -> EscrowClient:
    """Get an authenticated client, handling errors gracefully."""
    try:
        return EscrowClient(exchange_url=exchange)
    except EscrowClientError as e:
        if json_output:
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


def output(data, as_json: bool = False):
    """Output data as JSON or pretty-print."""
    if as_json:
        click.echo(json.dumps(data, indent=2, default=str))
    return data


@click.group()
@click.version_option(version="1.0.0", prog_name="a2a-escrow")
def cli():
    """a2a-escrow: Trustless escrow for AI agents.

    Create, fund, and settle escrows with other agents in 5 commands.
    Built on the A2A Settlement Exchange (https://a2a-settlement.org).
    """
    pass


# ── Register ────────────────────────────────────────────────────


@cli.command()
@click.option("--name", required=True, help="Agent name / account ID")
@click.option("--email", required=True, help="Contact email")
@click.option("--exchange", default=None, help="Exchange URL (default: production)")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def register(name: str, email: str, exchange: str | None, json_output: bool):
    """Register a new agent on the exchange."""
    try:
        result = EscrowClient.register(name=name, email=email, exchange_url=exchange)
    except EscrowClientError as e:
        if json_output:
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Registration failed:[/red] {e}")
        sys.exit(1)

    if json_output:
        output(result, as_json=True)
    else:
        console.print(f"[green]✓[/green] Registered as [bold]{result['account_id']}[/bold]")
        console.print(f"  Credentials saved to ~/.a2a-escrow/credentials.json")
        console.print(f"  Exchange: {result['exchange_url']}")


# ── Balance ─────────────────────────────────────────────────────


@cli.command()
@click.option("--exchange", default=None, help="Exchange URL")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def balance(exchange: str | None, json_output: bool):
    """Check your token balance."""
    client = get_client(exchange, json_output)
    try:
        data = client.get_balance()
    except EscrowClientError as e:
        if json_output:
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    if json_output:
        output(data, as_json=True)
    else:
        bal = data.get("balance", data)
        if isinstance(bal, dict):
            available = bal.get("available", "?")
            held = bal.get("held", 0)
            total = bal.get("total", available)
            console.print(f"  Available: [green]{available}[/green] tokens")
            if held:
                console.print(f"  Held in escrow: [yellow]{held}[/yellow] tokens")
            console.print(f"  Total: [bold]{total}[/bold] tokens")
        else:
            console.print(f"  Balance: [green]{bal}[/green] tokens")


# ── Deposit ─────────────────────────────────────────────────────


@cli.command()
@click.argument("amount", type=float)
@click.option("--exchange", default=None, help="Exchange URL")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def deposit(amount: float, exchange: str | None, json_output: bool):
    """Add tokens to your account."""
    client = get_client(exchange, json_output)
    try:
        data = client.deposit(amount)
    except EscrowClientError as e:
        if json_output:
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    if json_output:
        output(data, as_json=True)
    else:
        console.print(f"[green]✓[/green] Deposited {amount} tokens")


# ── Directory ───────────────────────────────────────────────────


@cli.command()
@click.option("--exchange", default=None, help="Exchange URL")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def directory(exchange: str | None, json_output: bool):
    """List available provider agents."""
    client = get_client(exchange, json_output)
    try:
        providers = client.directory()
    except EscrowClientError as e:
        if json_output:
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    if json_output:
        output(providers, as_json=True)
        return

    if not providers:
        console.print("No providers registered.")
        return

    table = Table(title="Available Providers")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="bold")
    table.add_column("Skills")
    table.add_column("Reputation", justify="right")

    for p in providers:
        table.add_row(
            p.get("id", p.get("account_id", "?"))[:16] + "...",
            p.get("name", "Unknown"),
            ", ".join(p.get("skills", [])) if isinstance(p.get("skills"), list) else str(p.get("skills", "")),
            str(p.get("reputation", p.get("score", "-"))),
        )

    console.print(table)


# ── Create Escrow ───────────────────────────────────────────────


@cli.command()
@click.option("--provider", required=True, help="Provider agent ID")
@click.option("--amount", required=True, type=float, help="Token amount to escrow")
@click.option("--task", default=None, help="Task description / ID")
@click.option("--group", default=None, help="Group ID for multi-escrow pipelines")
@click.option("--depends-on", default=None, help="Comma-separated escrow IDs this depends on")
@click.option("--exchange", default=None, help="Exchange URL")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def create(
    provider: str,
    amount: float,
    task: str | None,
    group: str | None,
    depends_on: str | None,
    exchange: str | None,
    json_output: bool,
):
    """Create a new escrow with a provider agent."""
    client = get_client(exchange, json_output)
    deps = [d.strip() for d in depends_on.split(",")] if depends_on else None

    try:
        escrow = client.create_escrow(
            provider_id=provider,
            amount=amount,
            task=task,
            group_id=group,
            depends_on=deps,
        )
    except EscrowClientError as e:
        if json_output:
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    if json_output:
        output(escrow.raw, as_json=True)
    else:
        console.print(f"[green]✓[/green] Escrow created: [bold cyan]{escrow.id}[/bold cyan]")
        console.print(f"  Provider: {escrow.provider_id}")
        console.print(f"  Amount: [yellow]{escrow.amount}[/yellow] tokens (held)")
        console.print(f"  Status: {escrow.status}")
        if task:
            console.print(f"  Task: {task}")


# ── Status ──────────────────────────────────────────────────────


@cli.command()
@click.argument("escrow_id")
@click.option("--exchange", default=None, help="Exchange URL")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def status(escrow_id: str, exchange: str | None, json_output: bool):
    """Check escrow status."""
    client = get_client(exchange, json_output)
    try:
        escrow = client.get_escrow(escrow_id)
    except EscrowClientError as e:
        if json_output:
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    if json_output:
        output(escrow.raw, as_json=True)
    else:
        status_color = {
            "held": "yellow",
            "released": "green",
            "refunded": "red",
            "expired": "dim",
        }.get(escrow.status, "white")

        console.print(f"  Escrow: [bold cyan]{escrow.id}[/bold cyan]")
        console.print(f"  Status: [{status_color}]{escrow.status}[/{status_color}]")
        console.print(f"  Amount: {escrow.amount} tokens")
        console.print(f"  Requester: {escrow.requester_id}")
        console.print(f"  Provider: {escrow.provider_id}")
        if escrow.task_id:
            console.print(f"  Task: {escrow.task_id}")
        if escrow.created_at:
            console.print(f"  Created: {escrow.created_at}")


# ── Release ─────────────────────────────────────────────────────


@cli.command()
@click.argument("escrow_id")
@click.option("--exchange", default=None, help="Exchange URL")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def release(escrow_id: str, exchange: str | None, json_output: bool):
    """Release escrowed funds to the provider."""
    client = get_client(exchange, json_output)
    try:
        data = client.release_escrow(escrow_id)
    except EscrowClientError as e:
        if json_output:
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    if json_output:
        output(data, as_json=True)
    else:
        console.print(f"[green]✓[/green] Escrow [bold]{escrow_id}[/bold] released — provider paid")


# ── Refund ──────────────────────────────────────────────────────


@cli.command()
@click.argument("escrow_id")
@click.option("--reason", default=None, help="Reason for refund")
@click.option("--exchange", default=None, help="Exchange URL")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def refund(escrow_id: str, reason: str | None, exchange: str | None, json_output: bool):
    """Refund escrowed funds to the requester."""
    client = get_client(exchange, json_output)
    try:
        data = client.refund_escrow(escrow_id, reason=reason)
    except EscrowClientError as e:
        if json_output:
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    if json_output:
        output(data, as_json=True)
    else:
        console.print(f"[green]✓[/green] Escrow [bold]{escrow_id}[/bold] refunded")
        if reason:
            console.print(f"  Reason: {reason}")


# ── Deliver ─────────────────────────────────────────────────────


@cli.command()
@click.argument("escrow_id")
@click.argument("content")
@click.option("--exchange", default=None, help="Exchange URL")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def deliver(escrow_id: str, content: str, exchange: str | None, json_output: bool):
    """Submit a deliverable for an escrow (provider side)."""
    client = get_client(exchange, json_output)
    try:
        data = client.deliver(escrow_id, content=content)
    except EscrowClientError as e:
        if json_output:
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    if json_output:
        output(data, as_json=True)
    else:
        console.print(f"[green]✓[/green] Deliverable submitted for escrow [bold]{escrow_id}[/bold]")


# ── History ─────────────────────────────────────────────────────


@cli.command()
@click.option("--limit", default=20, type=int, help="Number of transactions")
@click.option("--exchange", default=None, help="Exchange URL")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def history(limit: int, exchange: str | None, json_output: bool):
    """View transaction history."""
    client = get_client(exchange, json_output)
    try:
        txns = client.transactions(limit=limit)
    except EscrowClientError as e:
        if json_output:
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    if json_output:
        output(txns, as_json=True)
        return

    if not txns:
        console.print("No transactions yet.")
        return

    table = Table(title="Transaction History")
    table.add_column("ID", style="cyan", max_width=16)
    table.add_column("Type")
    table.add_column("Amount", justify="right")
    table.add_column("Status")
    table.add_column("Date")

    for t in txns:
        table.add_row(
            str(t.get("id", ""))[:16],
            t.get("type", t.get("transaction_type", "?")),
            str(t.get("amount", "")),
            t.get("status", ""),
            str(t.get("created_at", t.get("timestamp", "")))[:19],
        )

    console.print(table)


# ── Whoami ──────────────────────────────────────────────────────


@cli.command()
@click.option("--exchange", default=None, help="Exchange URL")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def whoami(exchange: str | None, json_output: bool):
    """Show your agent identity."""
    client = get_client(exchange, json_output)
    try:
        data = client.whoami()
    except EscrowClientError as e:
        if json_output:
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    if json_output:
        output(data, as_json=True)
    else:
        acct = data.get("account", data)
        console.print(f"  Account: [bold]{acct.get('id', acct.get('account_id', '?'))}[/bold]")
        console.print(f"  Name: {acct.get('name', '?')}")
        if acct.get("email"):
            console.print(f"  Email: {acct['email']}")
        console.print(f"  Exchange: {client.exchange_url}")


if __name__ == "__main__":
    cli()
