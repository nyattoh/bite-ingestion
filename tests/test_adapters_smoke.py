from __future__ import annotations

from pathlib import Path

from bite_bench.adapters import available_adapters, get_adapter
from bite_bench.adapters.registry import assert_no_network_adapters_enabled


def test_four_synthetic_domains_registered() -> None:
    ids = available_adapters()
    assert len(ids) >= 4
    for adapter_id in ids:
        assert adapter_id.startswith("synthetic_")


def test_adapters_yield_records_offline() -> None:
    assert_no_network_adapters_enabled()
    for adapter_id in available_adapters():
        adapter = get_adapter(adapter_id)
        assert adapter.allow_network_fetch() is False
        records = list(adapter.iter_records())
        assert len(records) >= 1
        assert adapter.manifest.dataset_name.startswith("synthetic-")
        assert adapter.manifest.human_approval == "not_required_for_synthetic"
        assert "TBD" in str(records[0].meta.get("real_dataset", "TBD"))


def test_ledger_marks_real_rows_pending() -> None:
    text = Path("research/dataset-ledger.csv").read_text(encoding="utf-8")
    assert "blocked_pending_human" in text
    assert "pending_human" in text
    assert "synthetic_observability_logs" in text


def test_privacy_and_licence_docs_exist() -> None:
    assert Path("research/licence-review.md").is_file()
    assert Path("research/privacy-review.md").is_file()
    assert "pending_human" in Path("research/licence-review.md").read_text(encoding="utf-8")
