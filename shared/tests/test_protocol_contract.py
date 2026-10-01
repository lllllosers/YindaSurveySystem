from shared.protocol.business_code import build_business_code
from shared.protocol.identity import deterministic_master_uid
from shared.protocol.revision import classify_revision_values
from shared.protocol.stake import parse_stake


def test_shared_identity_and_code_examples_remain_stable() -> None:
    assert deterministic_master_uid("organization", "ORG-D01") == (
        "d3f2f31e9c37ede995b19ab5a821792e"
    )
    assert build_business_code("1", "01", "03", "02", 1) == "1-01-03-02-001"
    assert parse_stake("K12+350") == ("CH12+350", 12350.0)

def test_shared_revision_contract_covers_idempotency_and_divergence() -> None:
    assert classify_revision_values(
        same_identity=True,
        same_content=True,
        incoming_revision=1,
        local_revision=3,
        source_revision=1,
    )[0] == "existing"
    assert classify_revision_values(
        same_identity=True,
        same_content=False,
        incoming_revision=1,
        local_revision=1,
        source_revision=2,
    )[0] == "stale"
    assert classify_revision_values(
        same_identity=True,
        same_content=False,
        incoming_revision=2,
        local_revision=2,
        source_revision=1,
    )[0] == "diverged"
    assert classify_revision_values(
        same_identity=False,
        same_content=True,
        incoming_revision=2,
        local_revision=1,
        source_revision=1,
    )[0] == "identity_conflict"
