"""Tests for the deterministic Quality Pack shadow runner."""

from __future__ import annotations

import hashlib
import json

from typing import TYPE_CHECKING

import pytest


if TYPE_CHECKING:
    from pathlib import Path

from evaluation.quality_runner.memos_quality_runner import (
    QualityPackError,
    _canonical_json,
    load_quality_dataset,
    run_fixture_validation,
    write_report,
)


def _fixture(tmp_path: Path, *, sample_count: int = 2) -> Path:
    dataset_dir = tmp_path / "datasets" / "memos" / "memos-golden-recall-v0"
    dataset_dir.mkdir(parents=True)
    rows = []
    for index in range(sample_count):
        rows.append(
            {
                "id": f"memos-fixture-{index + 1}",
                "productId": "memos",
                "datasetId": "memos-golden-recall-v0",
                "query": f"What is remembered {index + 1}?",
                "memories": [
                    {"id": "m1", "content": "A redacted memory", "sourceRef": "fixture:D1:1"}
                ],
                "goldenAnswer": "A redacted memory",
                "acceptableAnswers": ["A redacted memory"],
                "evidenceRefs": ["D1:1"],
            }
        )
    encoded = "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows
    ).encode("utf-8")
    samples_path = dataset_dir / "samples.jsonl"
    samples_path.write_bytes(encoded)
    manifest = {
        "schemaVersion": "1.0",
        "datasetId": "memos-golden-recall-v0",
        "productId": "memos",
        "displayName": "fixture",
        "version": "0.1.0",
        "status": "draft",
        "sampleCount": sample_count,
        "splitCounts": {"smoke": sample_count},
        "task": "memory_recall",
        "ownerConfirmation": {"status": "pending", "required": True, "scope": ["test"]},
        "source": {
            "kind": "synthetic",
            "dataset": "fixture",
            "repository": "fixture",
            "path": "fixture",
            "sourceCommit": "0" * 40,
            "sourceLicenseReview": "not_required",
            "transformations": ["fixture"],
        },
        "files": [
            {
                "path": "samples.jsonl",
                "format": "jsonl",
                "sha256": hashlib.sha256(encoded).hexdigest(),
                "lineCount": sample_count,
            }
        ],
        "execution": {
            "runnerInput": "memories + query",
            "expectedOutput": "answer + evidenceRefs",
            "scoring": "outside fixture runner",
            "networkRequired": False,
        },
    }
    (dataset_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path


def test_loads_and_hashes_quality_pack(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    dataset = load_quality_dataset(root, "memos-golden-recall-v0")
    assert len(dataset.samples) == 2
    assert len(dataset.dataset_content_hash) == 64
    assert dataset.files[0]["lineCount"] == 2


def test_shadow_report_is_explicitly_not_available_and_has_no_model_metrics(tmp_path: Path) -> None:
    dataset = load_quality_dataset(_fixture(tmp_path), "memos-golden-recall-v0")
    report = run_fixture_validation(dataset, mode="shadow", run_id="eval-test")
    assert report["run"]["mode"] == "shadow"
    assert report["run"]["result"] == "not_available"
    assert report["scorecard"]["status"] == "not_available"
    assert report["scorecard"]["metrics"]["fixtureCoverage"] == 1.0
    assert report["scorecard"]["metrics"]["targetLatencyP95Ms"] is None
    assert report["scorecard"]["metrics"]["inputTokensTotal"] is None
    assert report["scorecard"]["metrics"]["costMicrosTotal"] is None
    assert all(item["status"] == "not_available" for item in report["items"])
    assert all(item["targetOutput"] is None for item in report["items"])
    body = {key: value for key, value in report.items() if key not in ("report", "reportSha256")}
    expected_hash = hashlib.sha256(_canonical_json(body)).hexdigest()
    assert report["reportSha256"] == expected_hash
    assert report["report"]["sha256"] == expected_hash


def test_write_report_is_parseable(tmp_path: Path) -> None:
    dataset = load_quality_dataset(_fixture(tmp_path), "memos-golden-recall-v0")
    destination = tmp_path / "out" / "run.json"
    report = run_fixture_validation(dataset, mode="mock")
    assert write_report(report, destination) == destination
    assert json.loads(destination.read_text(encoding="utf-8"))["run"]["mode"] == "mock"


def test_rejects_hash_mismatch_and_unsafe_path(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    manifest_path = next(root.rglob("manifest.json"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][0]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(QualityPackError, match="SHA-256"):
        load_quality_dataset(root, "memos-golden-recall-v0")
