import json
import sys
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


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DESKTOP_SRC = REPOSITORY_ROOT / "src"


def test_contract_matches_v1_2_desktop_master_data() -> None:
    if str(DESKTOP_SRC) not in sys.path:
        sys.path.insert(0, str(DESKTOP_SRC))

    from services.master_identity import MASTER_IDENTITY_NAMESPACE
    from services.official_canal_management_scope import (
        OFFICIAL_CANAL_MANAGEMENT_SCOPE_SOURCE,
        OFFICIAL_CANAL_MANAGEMENT_SCOPE_VERSION,
        get_confirmed_official_scope_specs,
    )
    from services.official_master_data import (
        OFFICIAL_CANALS,
        OFFICIAL_DEPARTMENTS,
        OFFICIAL_MASTER_DATA_SOURCE,
        OFFICIAL_MASTER_DATA_VERSION,
        OFFICIAL_OFFICES,
    )

    contract, _ = load_contract()
    canal_map = {
        item["master_key"]: item
        for item in OFFICIAL_CANALS
    }
    expected_scopes = []
    for item in get_confirmed_official_scope_specs():
        record = dict(item)
        record["status"] = "active"
        record["description"] = canal_map[
            record["canal_master_key"]
        ].get("description")
        expected_scopes.append(record)

    assert CONTRACT_PATH.exists()
    assert contract["identity_namespace"] == MASTER_IDENTITY_NAMESPACE
    assert contract["master_data_version"] == OFFICIAL_MASTER_DATA_VERSION
    assert contract["master_data_source"] == OFFICIAL_MASTER_DATA_SOURCE
    assert (
        contract["management_scope_version"]
        == OFFICIAL_CANAL_MANAGEMENT_SCOPE_VERSION
    )
    assert (
        contract["management_scope_source"]
        == OFFICIAL_CANAL_MANAGEMENT_SCOPE_SOURCE
    )
    assert contract["departments"] == list(OFFICIAL_DEPARTMENTS)
    assert contract["offices"] == list(OFFICIAL_OFFICES)
    assert contract["canals"] == list(OFFICIAL_CANALS)
    assert contract["management_scopes"] == expected_scopes


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
        assert payload["summary"]["department_count"] == 5
        assert payload["summary"]["office_count"] == 20
        assert payload["summary"]["canal_count"] == 68
        assert payload["summary"]["management_scope_count"] == 63
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
        assert payload["official_canal_count"] == 68
        assert payload["official_scope_count"] == 63
    finally:
        cleanup_test_user(viewer.user_uid)


def test_health_reports_api_generation_for_launcher_compatibility() -> None:
    response = TestClient(app).get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "yinda-web-center-api",
        "api_generation": "2026.09.26-master-data-v1",
    }
