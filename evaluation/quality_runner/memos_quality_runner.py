"""Run the MemOS Quality Pack through the common EvaluationRun contract.

This adapter deliberately implements fixture validation only.  It does not call
an LLM, a MemOS service, or a network endpoint.  ``shadow`` and ``mock`` runs
therefore report ``not_available`` for model outcomes while still producing
auditable dataset hashes and per-sample fixture coverage.  A live model
adapter can be added later without changing the report shape.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import time

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    import os

    from collections.abc import Iterable, Mapping


RUNNER_ID = "memos-eval-runner"
RUNNER_VERSION = "0.1.0"
REPORT_SCHEMA_VERSION = "evaluation-run.v1"
SUPPORTED_MODES = ("shadow", "mock")
MAX_MANIFEST_DEPTH = 8


class QualityPackError(ValueError):
    """Raised when a Quality Pack cannot be safely and deterministically read."""


@dataclass(frozen=True)
class LoadedDataset:
    """Validated immutable input used to construct an EvaluationRun."""

    dataset_id: str
    product_id: str
    version: str
    status: str
    manifest_path: Path
    manifest_sha256: str
    dataset_content_hash: str
    files: tuple[Mapping[str, Any], ...]
    samples: tuple[Mapping[str, Any], ...]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: Any) -> bytes:
    """Encode JSON deterministically for report and content hashes."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _read_json(path: Path, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QualityPackError(f"{label} 不是有效 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise QualityPackError(f"{label} 必须是 JSON 对象。")
    return value


def _safe_relative_path(value: Any) -> str:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise QualityPackError("manifest 文件路径必须是非空相对路径。")
    path = Path(value)
    if any(part in ("", ".", "..") for part in path.parts):
        raise QualityPackError(f"manifest 文件路径不安全: {value}")
    return path.as_posix()


def _inside(root: Path, candidate: Path) -> Path:
    root_resolved = root.resolve()
    candidate_resolved = candidate.resolve()
    try:
        candidate_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise QualityPackError("质量包文件路径越界，拒绝读取。") from exc
    return candidate_resolved


def _iter_manifests(root: Path) -> Iterable[Path]:
    for path in root.rglob("manifest.json"):
        if ".git" in path.parts:
            continue
        try:
            depth = len(path.relative_to(root).parts)
        except ValueError:
            continue
        if depth <= MAX_MANIFEST_DEPTH:
            yield path


def _validate_sample(
    sample: Mapping[str, Any],
    *,
    dataset_id: str,
    product_id: str,
) -> None:
    required = ("id", "productId", "datasetId", "query", "memories", "goldenAnswer", "evidenceRefs")
    missing = [field for field in required if field not in sample]
    if missing:
        raise QualityPackError(f"样本缺少字段: {', '.join(missing)}")
    if not isinstance(sample["id"], str) or not sample["id"].strip():
        raise QualityPackError("样本 id 必须是非空字符串。")
    if sample["productId"] != product_id or sample["datasetId"] != dataset_id:
        raise QualityPackError(f"样本 {sample['id']} 的 productId/datasetId 与 manifest 不一致。")
    if not isinstance(sample["query"], str) or not sample["query"].strip():
        raise QualityPackError(f"样本 {sample['id']} 的 query 必须是非空字符串。")
    if not isinstance(sample["goldenAnswer"], str) or not sample["goldenAnswer"].strip():
        raise QualityPackError(f"样本 {sample['id']} 的 goldenAnswer 必须是非空字符串。")
    if not isinstance(sample["memories"], list) or not sample["memories"]:
        raise QualityPackError(f"样本 {sample['id']} 的 memories 必须是非空数组。")
    for memory in sample["memories"]:
        if not isinstance(memory, dict) or not isinstance(memory.get("content"), str):
            raise QualityPackError(f"样本 {sample['id']} 的 memory 结构无效。")
        if not isinstance(memory.get("sourceRef"), str) or not memory["sourceRef"].strip():
            raise QualityPackError(f"样本 {sample['id']} 的 memory 缺少 sourceRef。")
    if not isinstance(sample["evidenceRefs"], list) or not all(
        isinstance(ref, str) and ref.strip() for ref in sample["evidenceRefs"]
    ):
        raise QualityPackError(f"样本 {sample['id']} 的 evidenceRefs 结构无效。")
    acceptable = sample.get("acceptableAnswers", [])
    if not isinstance(acceptable, list) or not all(
        isinstance(answer, str) for answer in acceptable
    ):
        raise QualityPackError(f"样本 {sample['id']} 的 acceptableAnswers 结构无效。")


def load_quality_dataset(
    quality_packs_root: str | os.PathLike[str], dataset_id: str
) -> LoadedDataset:
    """Load and hash exactly one Quality Pack dataset.

    The declared file SHA-256, line count, sample count, IDs, and sample
    bindings are all checked before the runner can produce a report.
    """

    if not isinstance(dataset_id, str) or not dataset_id.strip():
        raise QualityPackError("dataset_id 必须是非空字符串。")
    root = Path(quality_packs_root).expanduser().resolve()
    if not root.is_dir():
        raise QualityPackError(f"QUALITY_PACKS_ROOT 不存在或不可读取: {root}")
    matches: list[tuple[Path, Mapping[str, Any]]] = []
    for manifest_path in _iter_manifests(root):
        manifest = _read_json(manifest_path, str(manifest_path))
        if manifest.get("datasetId") == dataset_id:
            matches.append((_inside(root, manifest_path), manifest))
    if len(matches) != 1:
        if not matches:
            raise QualityPackError(f"未找到 datasetId: {dataset_id}")
        raise QualityPackError(f"datasetId 对应多个 manifest: {dataset_id}")

    manifest_path, manifest = matches[0]
    product_id = manifest.get("productId")
    version = manifest.get("version")
    status = manifest.get("status")
    if not isinstance(product_id, str) or not product_id:
        raise QualityPackError("manifest.productId 缺失。")
    if not isinstance(version, str) or not version:
        raise QualityPackError("manifest.version 缺失。")
    if status not in ("draft", "frozen", "retired"):
        raise QualityPackError("manifest.status 无效。")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise QualityPackError("manifest.files 必须是非空数组。")

    samples: list[Mapping[str, Any]] = []
    file_records: list[Mapping[str, Any]] = []
    seen_ids: set[str] = set()
    dataset_dir = manifest_path.parent
    for file_record in files:
        if not isinstance(file_record, dict):
            raise QualityPackError("manifest.files 中存在无效条目。")
        relative_path = _safe_relative_path(file_record.get("path"))
        file_path = _inside(dataset_dir, dataset_dir / relative_path)
        try:
            raw = file_path.read_bytes()
        except OSError as exc:
            raise QualityPackError(f"质量包文件读取失败: {relative_path}") from exc
        expected_sha = file_record.get("sha256")
        actual_sha = _sha256(raw)
        if expected_sha != actual_sha:
            raise QualityPackError(f"质量包文件 SHA-256 不匹配: {relative_path}")
        lines = raw.decode("utf-8").splitlines()
        if file_record.get("lineCount") != len(lines):
            raise QualityPackError(f"质量包文件 lineCount 不匹配: {relative_path}")
        if file_record.get("format") != "jsonl":
            continue
        for line_number, line in enumerate(lines, start=1):
            try:
                sample = json.loads(line)
            except json.JSONDecodeError as exc:
                raise QualityPackError(f"质量包 JSONL 无效: {relative_path}:{line_number}") from exc
            if not isinstance(sample, dict):
                raise QualityPackError(f"质量包样本必须是对象: {relative_path}:{line_number}")
            _validate_sample(sample, dataset_id=dataset_id, product_id=product_id)
            sample_id = sample["id"]
            if sample_id in seen_ids:
                raise QualityPackError(f"质量包样本 ID 重复: {sample_id}")
            seen_ids.add(sample_id)
            samples.append(sample)
        file_records.append({"path": relative_path, "sha256": actual_sha, "lineCount": len(lines)})

    sample_count = manifest.get("sampleCount")
    if sample_count != len(samples):
        raise QualityPackError("manifest.sampleCount 与实际样本数不一致。")
    file_digests = "\n".join(f"{item['path']}:{item['sha256']}" for item in file_records)
    content_input = f"{dataset_id}\n{file_digests}\n{len(samples)}".encode()
    return LoadedDataset(
        dataset_id=dataset_id,
        product_id=product_id,
        version=version,
        status=status,
        manifest_path=manifest_path,
        manifest_sha256=_sha256(manifest_path.read_bytes()),
        dataset_content_hash=_sha256(content_input),
        files=tuple(file_records),
        samples=tuple(samples),
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _item(sample: Mapping[str, Any], mode: str) -> dict[str, Any]:
    """Build a no-model result; null observability fields are intentional."""

    return {
        "id": sample["id"],
        "status": "not_available",
        "outcome": "inconclusive",
        "fixtureMatch": "pass",
        "evidenceRefCount": len(sample["evidenceRefs"]),
        "targetOutput": None,
        "targetLatencyMs": None,
        "inputTokens": None,
        "outputTokens": None,
        "costMicros": None,
        "error": f"mode={mode}: model execution intentionally skipped; no quality score produced",
    }


def run_fixture_validation(
    dataset: LoadedDataset,
    *,
    mode: str = "shadow",
    run_id: str | None = None,
    target_revision: str | None = None,
    model_version: str | None = None,
    prompt_version: str | None = None,
    rag_version: str | None = None,
    quality_profile_sha: str | None = None,
) -> dict[str, Any]:
    """Create a shadow/mock EvaluationRun without invoking a target model."""

    if mode not in SUPPORTED_MODES:
        raise QualityPackError(f"mode 只能是: {', '.join(SUPPORTED_MODES)}")
    started_at = _utc_now()
    started_clock = time.perf_counter()
    run_id = run_id or f"eval-{dataset.dataset_id}-{dataset.dataset_content_hash[:12]}"
    items = [_item(sample, mode) for sample in dataset.samples]
    execution_duration_ms = round((time.perf_counter() - started_clock) * 1000, 3)
    count = len(items)
    scorecard = {
        "status": "not_available",
        "metrics": {
            "fixtureSampleCount": count,
            "fixtureValidCount": count,
            "fixtureCoverage": 1.0 if count else 0.0,
            "fixtureMatchCount": count,
            "fixtureMatchRate": 1.0 if count else 0.0,
            "evaluatedItemCount": 0,
            "notAvailableItemCount": count,
            "targetLatencyP50Ms": None,
            "targetLatencyP95Ms": None,
            "inputTokensTotal": None,
            "outputTokensTotal": None,
            "costMicrosTotal": None,
        },
        "notes": [
            "fixtureCoverage/fixtureMatchRate only validate the Quality Pack; they are not model quality scores.",
            "target latency, token usage and cost are null because this run intentionally did not invoke a model.",
            "A live runner must submit complete per-sample outputs before recall accuracy can be computed.",
        ],
    }
    run = {
        "id": run_id,
        "status": "completed",
        "result": "not_available",
        "mode": mode,
        "productId": dataset.product_id,
        "datasetId": dataset.dataset_id,
        "datasetVersion": dataset.version,
        "datasetStatus": dataset.status,
        "datasetContentHash": dataset.dataset_content_hash,
        "qualityProfileSha": quality_profile_sha,
        "target": {
            "revision": target_revision,
            "modelVersion": model_version,
            "promptVersion": prompt_version,
            "ragVersion": rag_version,
        },
        "runner": {"id": RUNNER_ID, "version": RUNNER_VERSION},
        "startedAt": started_at,
        "completedAt": _utc_now(),
        "executionDurationMs": execution_duration_ms,
        "itemCount": count,
        "completedItemCount": 0,
        "failedItemCount": 0,
    }
    body = {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "run": run,
        "qualityPack": {
            "manifestPath": dataset.manifest_path.as_posix(),
            "manifestSha256": dataset.manifest_sha256,
            "files": list(dataset.files),
        },
        "items": items,
        "scorecard": scorecard,
    }
    report_sha = _sha256(_canonical_json(body))
    body["report"] = {
        "format": "json",
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "sha256": report_sha,
    }
    body["reportSha256"] = report_sha
    return body


def write_report(report: Mapping[str, Any], output_path: str | os.PathLike[str]) -> Path:
    """Write a report atomically and return the final path."""

    destination = Path(output_path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_json(report) + b"\n"
    with tempfile.NamedTemporaryFile("wb", dir=destination.parent, delete=False) as temp:
        temp.write(payload)
        temp_path = Path(temp.name)
    temp_path.replace(destination)
    return destination


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="MemOS Quality Pack shadow/mock EvaluationRun runner"
    )
    parser.add_argument("--quality-packs-root", required=True, type=Path)
    parser.add_argument("--dataset-id", default="memos-golden-recall-v0")
    parser.add_argument("--mode", choices=SUPPORTED_MODES, default="shadow")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--target-revision")
    parser.add_argument("--model-version")
    parser.add_argument("--prompt-version")
    parser.add_argument("--rag-version")
    parser.add_argument("--quality-profile-sha")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = run_fixture_validation(
        load_quality_dataset(args.quality_packs_root, args.dataset_id),
        mode=args.mode,
        run_id=args.run_id,
        target_revision=args.target_revision,
        model_version=args.model_version,
        prompt_version=args.prompt_version,
        rag_version=args.rag_version,
        quality_profile_sha=args.quality_profile_sha,
    )
    if args.output:
        write_report(report, args.output)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through CLI smoke tests.
    raise SystemExit(main())
