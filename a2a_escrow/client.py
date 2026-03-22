"""A2A Settlement Exchange client SDK."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

DEFAULT_EXCHANGE_URL = "https://exchange.a2a-settlement.org"
CREDENTIALS_PATH = Path.home() / ".a2a-escrow" / "credentials.json"


@dataclass
class Escrow:
    """Represents an escrow transaction."""

    id: str
    requester_id: str
    provider_id: str
    amount: float
    status: str
    task_id: Optional[str] = None
    group_id: Optional[str] = None
    created_at: Optional[str] = None
    deliverable: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "Escrow":
        esc = data.get("escrow", data)
        return cls(
            id=esc.get("id", ""),
            requester_id=esc.get("requester_id", ""),
            provider_id=esc.get("provider_id", ""),
            amount=esc.get("amount", 0),
            status=esc.get("status", "unknown"),
            task_id=esc.get("task_id"),
            group_id=esc.get("group_id"),
            created_at=esc.get("created_at"),
            deliverable=esc.get("deliverable"),
            raw=data,
        )


class EscrowClientError(Exception):
    """Raised when the exchange returns an error."""

    def __init__(self, message: str, status_code: int = 0, response: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response or {}


class EscrowClient:
    """Client for the A2A Settlement Exchange.

    Usage:
        client = EscrowClient()  # reads ~/.a2a-escrow/credentials.json
        escrow = client.create_escrow(provider_id="agent-123", amount=5)
        client.release_escrow(escrow.id)
    """

    def __init__(
        self,
        account_id: Optional[str] = None,
        api_key: Optional[str] = None,
        exchange_url: Optional[str] = None,
        credentials_path: Optional[Path] = None,
    ):
        self._creds_path = credentials_path or CREDENTIALS_PATH

        if account_id and api_key:
            self.account_id = account_id
            self.api_key = api_key
        else:
            creds = self._load_credentials()
            self.account_id = account_id or creds["account_id"]
            self.api_key = api_key or creds["api_key"]

        self.exchange_url = (
            exchange_url
            or os.environ.get("A2A_EXCHANGE_URL")
            or self._load_credentials().get("exchange_url", DEFAULT_EXCHANGE_URL)
        ).rstrip("/")

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "X-Account-ID": self.account_id,
                "X-API-Key": self.api_key,
            }
        )

    def _load_credentials(self) -> Dict[str, str]:
        """Load credentials from disk."""
        if not self._creds_path.exists():
            raise EscrowClientError(
                f"No credentials found at {self._creds_path}. "
                f"Run 'a2a-escrow register' first."
            )
        with open(self._creds_path) as f:
            return json.load(f)

    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Make an authenticated request to the exchange."""
        url = f"{self.exchange_url}{path}"
        try:
            resp = self.session.request(method, url, timeout=30, **kwargs)
        except requests.ConnectionError:
            raise EscrowClientError(
                f"Cannot connect to exchange at {self.exchange_url}. "
                f"Is the exchange running?"
            )
        except requests.Timeout:
            raise EscrowClientError("Request timed out.")

        try:
            data = resp.json()
        except ValueError:
            data = {"raw": resp.text}

        if resp.status_code >= 400:
            msg = data.get("error", data.get("detail", data.get("message", resp.text)))
            raise EscrowClientError(
                f"Exchange error ({resp.status_code}): {msg}",
                status_code=resp.status_code,
                response=data,
            )
        return data

    # ── Identity & Balance ──────────────────────────────────────

    def whoami(self) -> Dict[str, Any]:
        """Get current account info."""
        return self._request("GET", f"/accounts/{self.account_id}")

    def get_balance(self) -> Dict[str, Any]:
        """Get account balance."""
        return self._request("GET", f"/accounts/{self.account_id}/balance")

    def deposit(self, amount: float) -> Dict[str, Any]:
        """Deposit tokens into account."""
        return self._request(
            "POST",
            f"/accounts/{self.account_id}/deposit",
            json={"amount": amount},
        )

    # ── Directory ───────────────────────────────────────────────

    def directory(self) -> List[Dict[str, Any]]:
        """List available provider agents."""
        data = self._request("GET", "/directory")
        return data.get("providers", data.get("agents", []))

    # ── Escrow Operations ───────────────────────────────────────

    def create_escrow(
        self,
        provider_id: str,
        amount: float,
        task: Optional[str] = None,
        group_id: Optional[str] = None,
        depends_on: Optional[List[str]] = None,
    ) -> Escrow:
        """Create a new escrow. Tokens are held until released or refunded."""
        payload: Dict[str, Any] = {
            "provider_id": provider_id,
            "amount": amount,
        }
        if task:
            payload["task_id"] = task
        if group_id:
            payload["group_id"] = group_id
        if depends_on:
            payload["depends_on"] = depends_on

        data = self._request("POST", "/escrow", json=payload)
        return Escrow.from_api(data)

    def get_escrow(self, escrow_id: str) -> Escrow:
        """Get escrow details."""
        data = self._request("GET", f"/escrow/{escrow_id}")
        return Escrow.from_api(data)

    def release_escrow(self, escrow_id: str) -> Dict[str, Any]:
        """Release escrowed funds to the provider."""
        return self._request("POST", f"/escrow/{escrow_id}/release")

    def refund_escrow(self, escrow_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """Refund escrowed funds to the requester."""
        payload = {}
        if reason:
            payload["reason"] = reason
        return self._request("POST", f"/escrow/{escrow_id}/refund", json=payload)

    def deliver(self, escrow_id: str, content: str, provenance: Optional[Dict] = None) -> Dict[str, Any]:
        """Submit a deliverable for an escrow (provider side)."""
        payload: Dict[str, Any] = {"content": content}
        if provenance:
            payload["provenance"] = provenance
        return self._request("POST", f"/escrow/{escrow_id}/deliver", json=payload)

    # ── History ─────────────────────────────────────────────────

    def transactions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get transaction history."""
        data = self._request("GET", f"/accounts/{self.account_id}/transactions?limit={limit}")
        return data.get("transactions", [])

    # ── Registration ────────────────────────────────────────────

    @staticmethod
    def register(
        name: str,
        email: str,
        exchange_url: Optional[str] = None,
        credentials_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Register a new agent account on the exchange."""
        url = (exchange_url or DEFAULT_EXCHANGE_URL).rstrip("/")
        creds_path = credentials_path or CREDENTIALS_PATH

        try:
            resp = requests.post(
                f"{url}/accounts/register",
                json={"name": name, "email": email},
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
        except requests.ConnectionError:
            raise EscrowClientError(f"Cannot connect to exchange at {url}")

        if resp.status_code >= 400:
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            raise EscrowClientError(
                f"Registration failed ({resp.status_code}): {data.get('error', resp.text)}",
                status_code=resp.status_code,
                response=data,
            )

        data = resp.json()

        # Save credentials
        creds_path.parent.mkdir(parents=True, exist_ok=True)
        creds = {
            "account_id": data.get("account_id", data.get("id", name)),
            "api_key": data.get("api_key", data.get("key", "")),
            "exchange_url": url,
        }
        with open(creds_path, "w") as f:
            json.dump(creds, f, indent=2)

        return {**creds, "registered": True}
