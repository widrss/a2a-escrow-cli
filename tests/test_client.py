"""Tests for the EscrowClient SDK."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from a2a_escrow.client import EscrowClient, EscrowClientError, Escrow


# ── Fixtures ────────────────────────────────────────────────────


@pytest.fixture
def creds_file(tmp_path):
    """Create a temporary credentials file."""
    creds = {
        "account_id": "test-agent",
        "api_key": "ask_test_key_123",
        "exchange_url": "http://localhost:8000",
    }
    path = tmp_path / ".a2a-escrow" / "credentials.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(creds))
    return path


@pytest.fixture
def client(creds_file):
    """Create a client with test credentials."""
    return EscrowClient(credentials_path=creds_file)


# ── Escrow Dataclass ────────────────────────────────────────────


class TestEscrow:
    def test_from_api_nested(self):
        data = {
            "escrow": {
                "id": "esc-123",
                "requester_id": "agent-a",
                "provider_id": "agent-b",
                "amount": 10,
                "status": "held",
                "task_id": "summarize",
                "created_at": "2026-03-22T12:00:00Z",
            }
        }
        esc = Escrow.from_api(data)
        assert esc.id == "esc-123"
        assert esc.requester_id == "agent-a"
        assert esc.provider_id == "agent-b"
        assert esc.amount == 10
        assert esc.status == "held"
        assert esc.task_id == "summarize"

    def test_from_api_flat(self):
        data = {
            "id": "esc-456",
            "requester_id": "agent-x",
            "provider_id": "agent-y",
            "amount": 5,
            "status": "released",
        }
        esc = Escrow.from_api(data)
        assert esc.id == "esc-456"
        assert esc.status == "released"


# ── Client Init ─────────────────────────────────────────────────


class TestClientInit:
    def test_loads_from_file(self, creds_file):
        client = EscrowClient(credentials_path=creds_file)
        assert client.account_id == "test-agent"
        assert client.api_key == "ask_test_key_123"
        assert client.exchange_url == "http://localhost:8000"

    def test_explicit_credentials(self, tmp_path):
        client = EscrowClient(
            account_id="explicit-agent",
            api_key="explicit-key",
            exchange_url="http://example.com",
        )
        assert client.account_id == "explicit-agent"
        assert client.api_key == "explicit-key"

    def test_missing_credentials_raises(self, tmp_path):
        fake_path = tmp_path / "nonexistent" / "creds.json"
        with pytest.raises(EscrowClientError, match="No credentials found"):
            EscrowClient(credentials_path=fake_path)

    def test_env_override(self, creds_file, monkeypatch):
        monkeypatch.setenv("A2A_EXCHANGE_URL", "http://custom:9000")
        client = EscrowClient(credentials_path=creds_file)
        assert client.exchange_url == "http://custom:9000"


# ── API Methods (mocked) ───────────────────────────────────────


class TestClientMethods:
    @patch("a2a_escrow.client.requests.Session")
    def test_get_balance(self, mock_session_cls, creds_file):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "balance": {"available": 100, "held": 10, "total": 110}
        }
        mock_session = MagicMock()
        mock_session.request.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        client = EscrowClient(credentials_path=creds_file)
        client.session = mock_session

        result = client.get_balance()
        assert result["balance"]["available"] == 100
        mock_session.request.assert_called_once()

    @patch("a2a_escrow.client.requests.Session")
    def test_create_escrow(self, mock_session_cls, creds_file):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "escrow": {
                "id": "esc-new",
                "requester_id": "test-agent",
                "provider_id": "provider-1",
                "amount": 15,
                "status": "held",
            }
        }
        mock_session = MagicMock()
        mock_session.request.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        client = EscrowClient(credentials_path=creds_file)
        client.session = mock_session

        escrow = client.create_escrow(provider_id="provider-1", amount=15, task="test-task")
        assert isinstance(escrow, Escrow)
        assert escrow.id == "esc-new"
        assert escrow.status == "held"
        assert escrow.amount == 15

    @patch("a2a_escrow.client.requests.Session")
    def test_release_escrow(self, mock_session_cls, creds_file):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "released"}
        mock_session = MagicMock()
        mock_session.request.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        client = EscrowClient(credentials_path=creds_file)
        client.session = mock_session

        result = client.release_escrow("esc-123")
        assert result["status"] == "released"

    @patch("a2a_escrow.client.requests.Session")
    def test_api_error_handling(self, mock_session_cls, creds_file):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.json.return_value = {"error": "Insufficient balance"}
        mock_resp.text = "Insufficient balance"
        mock_session = MagicMock()
        mock_session.request.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        client = EscrowClient(credentials_path=creds_file)
        client.session = mock_session

        with pytest.raises(EscrowClientError, match="Insufficient balance"):
            client.create_escrow(provider_id="p1", amount=9999)

    @patch("a2a_escrow.client.requests.Session")
    def test_directory(self, mock_session_cls, creds_file):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "providers": [
                {"id": "p1", "name": "Agent Alpha", "skills": ["research"]},
                {"id": "p2", "name": "Agent Beta", "skills": ["analysis"]},
            ]
        }
        mock_session = MagicMock()
        mock_session.request.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        client = EscrowClient(credentials_path=creds_file)
        client.session = mock_session

        providers = client.directory()
        assert len(providers) == 2
        assert providers[0]["name"] == "Agent Alpha"

    @patch("a2a_escrow.client.requests.Session")
    def test_deliver(self, mock_session_cls, creds_file):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "delivered"}
        mock_session = MagicMock()
        mock_session.request.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        client = EscrowClient(credentials_path=creds_file)
        client.session = mock_session

        result = client.deliver("esc-123", content="Here is the analysis...")
        assert result["status"] == "delivered"

    @patch("a2a_escrow.client.requests.Session")
    def test_transactions(self, mock_session_cls, creds_file):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "transactions": [
                {"id": "tx-1", "type": "escrow_create", "amount": 10, "status": "held"},
            ]
        }
        mock_session = MagicMock()
        mock_session.request.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        client = EscrowClient(credentials_path=creds_file)
        client.session = mock_session

        txns = client.transactions(limit=5)
        assert len(txns) == 1
        assert txns[0]["type"] == "escrow_create"


# ── Registration ────────────────────────────────────────────────


class TestRegistration:
    @patch("a2a_escrow.client.requests.post")
    def test_register_success(self, mock_post, tmp_path):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "account_id": "new-agent",
            "api_key": "ask_new_key",
        }
        mock_post.return_value = mock_resp

        creds_path = tmp_path / ".a2a-escrow" / "credentials.json"
        result = EscrowClient.register(
            name="new-agent",
            email="new@example.com",
            credentials_path=creds_path,
        )

        assert result["registered"] is True
        assert result["account_id"] == "new-agent"
        assert creds_path.exists()

        saved = json.loads(creds_path.read_text())
        assert saved["account_id"] == "new-agent"
        assert saved["api_key"] == "ask_new_key"

    @patch("a2a_escrow.client.requests.post")
    def test_register_failure(self, mock_post, tmp_path):
        mock_resp = MagicMock()
        mock_resp.status_code = 409
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {"error": "Account already exists"}
        mock_post.return_value = mock_resp

        with pytest.raises(EscrowClientError, match="Account already exists"):
            EscrowClient.register(
                name="existing",
                email="existing@example.com",
                credentials_path=tmp_path / "creds.json",
            )
