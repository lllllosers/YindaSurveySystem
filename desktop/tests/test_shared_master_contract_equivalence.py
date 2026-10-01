import json
from pathlib import Path
from shared.master_data.loader import load_official_master_contract
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = PROJECT_ROOT.parent / "shared/master_data/official_master_contract.json"
def load_contract():
    return load_official_master_contract(CONTRACT_PATH), None

def test_contract_matches_v1_2_desktop_master_data() -> None:
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
