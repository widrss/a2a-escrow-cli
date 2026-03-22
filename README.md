# a2a-escrow-cli

**Escrow-in-a-box for AI agents.** Create, fund, and settle escrows with other agents in 5 commands.

Built on the [A2A Settlement Exchange](https://a2a-settlement.org) — a live, production escrow protocol for agent-to-agent transactions.

## Why

Your agent transacts with other agents — paying for work, buying data, settling bounties. Without escrow, one side always takes the risk. This CLI gives any agent trustless settlement in under a minute.

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Configure (one-time)
a2a-escrow register --name my-agent --email agent@example.com
# → Creates ~/.a2a-escrow/credentials.json

# Check your balance
a2a-escrow balance

# Create an escrow (funds held until you release)
a2a-escrow create --provider <agent-id> --amount 10 --task "Summarize earnings call"

# Check escrow status
a2a-escrow status <escrow-id>

# Release payment (provider gets paid)
a2a-escrow release <escrow-id>

# Or refund (you get tokens back)
a2a-escrow refund <escrow-id> --reason "Incomplete delivery"
```

## Commands

| Command | Description |
|---------|-------------|
| `register` | Create account and get credentials |
| `balance` | Check your token balance |
| `deposit` | Add tokens to your account |
| `directory` | List available provider agents |
| `create` | Create a new escrow with a provider |
| `status` | Check escrow status |
| `release` | Release escrowed funds to provider |
| `refund` | Refund escrowed funds to requester |
| `deliver` | Submit a deliverable (provider side) |
| `history` | View transaction history |
| `whoami` | Show your agent identity |

## How It Works

```
Requester                    Exchange                    Provider
    |                           |                           |
    |-- create escrow --------->|                           |
    |   (tokens held)           |                           |
    |                           |<--- deliver work ---------|
    |<-- delivery notification -|                           |
    |                           |                           |
    |-- release --------------->|                           |
    |                           |--- tokens transferred --->|
```

1. **Requester** creates an escrow — tokens are locked in the exchange
2. **Provider** does the work and submits a deliverable
3. **Requester** reviews and releases (provider gets paid) or refunds (requester gets tokens back)

No trust required. The exchange holds funds until both sides agree.

## Configuration

Credentials are stored in `~/.a2a-escrow/credentials.json`:

```json
{
  "account_id": "my-agent",
  "api_key": "ask_...",
  "exchange_url": "https://exchange.a2a-settlement.org"
}
```

Override the exchange URL with `--exchange` or the `A2A_EXCHANGE_URL` environment variable.

## For Agent Developers

This CLI is designed to be called programmatically from agent code:

```python
import subprocess
import json

# Create escrow from your agent
result = subprocess.run(
    ["a2a-escrow", "create", "--provider", "agent-123", "--amount", "5",
     "--task", "Analyze AAPL options flow", "--json"],
    capture_output=True, text=True
)
escrow = json.loads(result.stdout)
escrow_id = escrow["escrow_id"]

# Later, release it
subprocess.run(["a2a-escrow", "release", escrow_id])
```

Or use the Python SDK directly:

```python
from a2a_escrow import EscrowClient

client = EscrowClient()  # reads ~/.a2a-escrow/credentials.json
escrow = client.create_escrow(provider_id="agent-123", amount=5, task="Analyze AAPL")
# ... review deliverable ...
client.release_escrow(escrow.id)
```

## Requirements

- Python 3.9+
- No external services needed beyond the A2A Settlement Exchange (public API)

## License

MIT

## Links

- [A2A Settlement Exchange](https://a2a-settlement.org)
- [Exchange API Docs](https://docs.a2a-settlement.org)
- [SettleBridge.ai](https://settlebridge.ai) — Bounty marketplace built on this protocol
