from __future__ import annotations

import jsonschema

from bite_ingestion.schemas import load_schema


def test_source_unit_schema_accepts_minimal() -> None:
    schema = load_schema("source_unit.schema.json")
    instance = {
        "unit_id": "u-1",
        "media_type": "text/plain",
        "payload_ref": "seeds/example.txt",
        "checksum_sha256": "0" * 64,
        "licence": None,
        "notes": None,
    }
    jsonschema.validate(instance=instance, schema=schema)


def test_evidence_packet_schema_accepts_minimal() -> None:
    schema = load_schema("evidence_packet.schema.json")
    instance = {
        "packet_id": "p-1",
        "visible_evidence": [{"text": "hello", "role": None}],
        "hidden_index_ref": None,
        "provenance": {
            "unit_id": "u-1",
            "source_uri": None,
            "byte_or_token_span": None,
            "renderer_id": None,
        },
        "op_last_touch": "NONE",
        "morphology": None,
    }
    jsonschema.validate(instance=instance, schema=schema)
