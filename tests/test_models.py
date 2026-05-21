import json
import pytest
from custom_components.missioncontrol.models import HaTaskPayload


def test_parse_standard_payload():
    raw = json.dumps({
        "domain": "light",
        "service": "turn_on",
        "target": {"entity_id": "light.office"},
        "data": {"brightness": 200},
    })
    payload = HaTaskPayload.from_json(raw)
    assert payload.domain == "light"
    assert payload.service == "turn_on"
    assert payload.target == {"entity_id": "light.office"}
    assert payload.data == {"brightness": 200}


def test_parse_payload_no_data():
    raw = json.dumps({"domain": "light", "service": "turn_off", "target": {"entity_id": "light.hall"}})
    payload = HaTaskPayload.from_json(raw)
    assert payload.data == {}
    assert payload.target == {"entity_id": "light.hall"}


def test_parse_notify_payload():
    raw = json.dumps({
        "domain": "notify",
        "service": "mobile_app",
        "data": {
            "message": "Approve?",
            "actions": [
                {"action": "APPROVE", "title": "✓ Approve"},
                {"action": "REJECT", "title": "✗ Reject"},
            ],
        },
    })
    payload = HaTaskPayload.from_json(raw)
    assert payload.is_approval_gate is True
    assert len(payload.data["actions"]) == 2


def test_parse_payload_invalid_json():
    with pytest.raises(ValueError, match="invalid payload"):
        HaTaskPayload.from_json("not json")


def test_parse_payload_missing_domain():
    with pytest.raises(ValueError, match="domain"):
        HaTaskPayload.from_json(json.dumps({"service": "turn_on"}))
