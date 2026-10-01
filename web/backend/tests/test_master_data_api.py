import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.master_data_service import (
    CONTRACT_PATH,
    deterministic_master_uid,
    load_contract,
)
from tests.auth_helpers import (
    cleanup_test_user,
    create_test_user,
    login_client,
)




def test_contract_matches_shared_master_contract() -> None:
    from shared.master_data.loader import load_official_master_contract
    contract, _ = load_contract()
    assert CONTRACT_PATH.exists()
    assert contract == load_official_master_contract()
    assert len(contract["departments"]) == 5
    assert len(contract["offices"]) == 20
    assert len(contract["canals"]) == 68
    assert len(contract["management_scopes"]) == 63



def test_master_data_snapshot_permissions_and_content() -> None:
    viewer = create_test_user("viewer")
    try:
        anonymous = TestClient(app)
        assert anonymous.get("/api/v1/master-data/snapshot").status_code == 401

        client = TestClient(app)
        login_client(client, viewer.username)
        response = client.get("/api/v1/master-data/snapshot")
        assert response.status_code == 200, response.text

        payload = response.json()
        # 正式库允许在甲方初始基线上继续补充单位、渠道和分段范围。
        assert payload["summary"]["department_count"] >= 5
        assert payload["summary"]["office_count"] >= 20
        assert payload["summary"]["canal_count"] >= 68
        assert payload["summary"]["management_scope_count"] >= 63
        assert len(payload["summary"]["contract_sha256"]) == 64

        department = payload["departments"][0]
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        assert department["stable_uid"] == deterministic_master_uid(
            contract["identity_namespace"],
            "organization",
            department["master_key"],
        )
    finally:
        cleanup_test_user(viewer.user_uid)


def test_overview_reports_web_and_master_data_status() -> None:
    viewer = create_test_user("viewer")
    try:
        client = TestClient(app)
        login_client(client, viewer.username)
        response = client.get("/api/v1/overview")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["product_version"] == "V1.2.0"
        assert payload["task_protocol"] == ".ydtask V3"
        assert payload["result_protocol"] == ".ydresult 2.2"
        assert payload["official_canal_count"] >= 68
        assert payload["official_scope_count"] >= 63
        assert payload["unassigned_backbone_canal_count"] >= 0
    finally:
        cleanup_test_user(viewer.user_uid)


def test_health_reports_api_generation_for_launcher_compatibility() -> None:
    response = TestClient(app).get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "yinda-web-center-api",
        "api_generation": "2026.09.27-deployment-cleanup-v6",
    }
