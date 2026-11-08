from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from services.feishu_transfer import server


def test_missing_memoq_denies_group_data():
    assert TestClient(server.app).get("/groups").status_code == 401


@pytest.fixture
def transfer_client(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(server, "groups", lambda: [{"id": "oc_test", "name": "交付群"}])
    server.app.dependency_overrides[server.authenticated] = lambda: None
    try:
        yield TestClient(server.app)
    finally:
        server.app.dependency_overrides.clear()


def test_group_mapping_survives_concurrency_and_replacement(transfer_client):
    path = "/groups/oc_test/document"
    first,second=str(uuid4()),str(uuid4())
    def reserve(key,old="",new=""):
        return transfer_client.post(path,json={"operation":key,"previous":old,"created":new}).json()
    assert reserve(first)["create"]
    assert reserve(second)["wait"]
    assert reserve(first,new="docA")["document"]=="docA"
    assert reserve(second)["document"]=="docA"
    assert reserve(second,"docA")["create"]
    assert reserve(second,"docA","docB")["document"]=="docB"
    assert reserve(first,"docA")["document"]=="docB"
    assert transfer_client.post("/groups/oc_other/document",json={"operation":first}).json()["create"]


def test_invite_and_approval(transfer_client, tmp_path, monkeypatch):
    (tmp_path / "feishu-transfer.json").write_text('{"bot_app_id":"cli_test"}')
    monkeypatch.setattr(server, "bot_present", lambda _: False)

    def invite(*args):
        assert "user" in args and "create" in args and "cli_test" in args[-1]
        return {"pending_approval_id_list": ["cli_test"]}

    monkeypatch.setattr(server, "cli", invite)
    assert transfer_client.post("/groups/oc_test/prepare").json() == {
        "ready": False,
        "pending": True,
    }
    monkeypatch.setattr(server, "bot_present", lambda _: True)
    assert transfer_client.post("/groups/oc_test/prepare").json() == {"ready": True}
