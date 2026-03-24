"""
Core Nuclei orchestration task.

Flow:
  1. Load scan + targets from DB
  2. Write targets to a temp file
  3. Build nuclei CLI command from scan config
  4. Stream nuclei JSON output line by line
  5. Parse + insert findings in batches
  6. Update scan status + counters
  7. Trigger webhook notifications
"""
import os
import json
import uuid
import shutil
import subprocess
import tempfile
import logging
from datetime import datetime
from typing import List

from celery import Task
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.workers.celery_app import celery_app
from app.config import settings
from app.models.scan import Scan, ScanStatus, ScanTargetList
from app.models.finding import Finding, FindingSeverity
from app.models.target import TargetList

logger = logging.getLogger(__name__)

# Use sync SQLAlchemy for Celery workers
_engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)


def _get_session() -> Session:
    return Session(_engine)


def _severity_from_str(s: str) -> FindingSeverity:
    mapping = {
        "critical": FindingSeverity.CRITICAL,
        "high": FindingSeverity.HIGH,
        "medium": FindingSeverity.MEDIUM,
        "low": FindingSeverity.LOW,
        "info": FindingSeverity.INFO,
    }
    return mapping.get(s.lower(), FindingSeverity.UNKNOWN)


def _build_nuclei_cmd(scan: Scan, targets_file: str, output_file: str) -> List[str]:
    config = scan.config
    cmd = [
        settings.NUCLEI_BINARY,
        "-list", targets_file,
        "-json-export", output_file,
        "-json",
        "-silent",
        "-no-color",
        "-rate-limit", str(config.get("rate_limit", settings.NUCLEI_RATE_LIMIT)),
        "-bulk-size", str(config.get("bulk_size", settings.NUCLEI_BULK_SIZE)),
        "-concurrency", str(config.get("concurrency", settings.NUCLEI_CONCURRENCY)),
        "-timeout", str(config.get("timeout", 30)),
        "-retries", str(config.get("retries", 1)),
    ]

    severities = config.get("severity", [])
    if severities:
        cmd += ["-severity", ",".join(severities)]

    tags = config.get("tags", [])
    if tags:
        cmd += ["-tags", ",".join(tags)]

    exclude_tags = config.get("exclude_tags", [])
    if exclude_tags:
        cmd += ["-exclude-tags", ",".join(exclude_tags)]

    templates = config.get("templates", [])
    if templates:
        for t in templates:
            cmd += ["-t", t]
    else:
        # Default: use official templates dir
        cmd += ["-t", settings.NUCLEI_TEMPLATES_DIR]
        # Also add custom templates if they exist
        if os.path.isdir(settings.NUCLEI_CUSTOM_TEMPLATES_DIR):
            cmd += ["-t", settings.NUCLEI_CUSTOM_TEMPLATES_DIR]

    extra = config.get("extra_flags", [])
    cmd.extend(extra)

    return cmd


def _collect_targets(scan_id: str, session: Session) -> List[str]:
    stl_result = session.execute(
        select(ScanTargetList).where(ScanTargetList.scan_id == scan_id)
    )
    stls = stl_result.scalars().all()

    targets = set()
    for stl in stls:
        tl = session.execute(
            select(TargetList).where(TargetList.id == stl.target_list_id)
        ).scalar_one_or_none()
        if tl:
            for target in tl.targets:
                targets.add(target.value)
    return list(targets)


def _parse_nuclei_line(line: str) -> dict | None:
    line = line.strip()
    if not line:
        return None
    try:
        data = json.loads(line)
        if "template-id" in data or "matched-at" in data:
            return data
    except json.JSONDecodeError:
        pass
    return None


def _finding_from_nuclei_output(data: dict, scan_id: str) -> Finding:
    info = data.get("info", {})
    severity_str = info.get("severity", "unknown")

    return Finding(
        id=str(uuid.uuid4()),
        scan_id=scan_id,
        template_id=data.get("template-id"),
        template_name=info.get("name", data.get("template-id")),
        template_path=data.get("template-path"),
        severity=_severity_from_str(severity_str),
        matched_at=data.get("matched-at", ""),
        target=data.get("host", data.get("matched-at", "")),
        host=data.get("host"),
        matched_line=data.get("matched-line"),
        extracted_results=data.get("extracted-results", []),
        curl_command=data.get("curl-command"),
        description=info.get("description"),
        reference=info.get("reference", []) if isinstance(info.get("reference"), list) else [],
        tags=info.get("tags", []) if isinstance(info.get("tags"), list) else [],
        raw=data,
    )


class ScanTask(Task):
    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        scan_id = args[0] if args else None
        if scan_id:
            with _get_session() as session:
                scan = session.get(Scan, scan_id)
                if scan:
                    scan.status = ScanStatus.FAILED
                    scan.error_message = str(exc)[:2000]
                    scan.completed_at = datetime.utcnow()
                    session.commit()


@celery_app.task(bind=True, base=ScanTask, name="app.workers.scan_tasks.run_nuclei_scan",
                 max_retries=1, soft_time_limit=3600, time_limit=3900)
def run_nuclei_scan(self, scan_id: str):
    """Execute a Nuclei scan and persist findings to DB."""
    logger.info(f"[scan:{scan_id}] Starting Nuclei scan")

    with _get_session() as session:
        scan = session.get(Scan, scan_id)
        if not scan:
            logger.error(f"[scan:{scan_id}] Scan not found")
            return

        if scan.status == ScanStatus.CANCELLED:
            logger.info(f"[scan:{scan_id}] Scan was cancelled before starting")
            return

        targets = _collect_targets(scan_id, session)
        if not targets:
            scan.status = ScanStatus.FAILED
            scan.error_message = "No targets found"
            scan.completed_at = datetime.utcnow()
            session.commit()
            return

        scan.status = ScanStatus.RUNNING
        scan.started_at = datetime.utcnow()
        scan.total_targets = len(targets)
        session.commit()

    # Work in a temp dir
    work_dir = tempfile.mkdtemp(prefix=f"nuclei_{scan_id}_")
    targets_file = os.path.join(work_dir, "targets.txt")
    output_file = os.path.join(work_dir, "results.json")

    try:
        with open(targets_file, "w") as f:
            f.write("\n".join(targets))

        with _get_session() as session:
            scan = session.get(Scan, scan_id)
            cmd = _build_nuclei_cmd(scan, targets_file, output_file)

        logger.info(f"[scan:{scan_id}] CMD: {' '.join(cmd)}")

        # Run nuclei and stream stdout
        batch: List[Finding] = []
        severity_counters = {s: 0 for s in ["critical", "high", "medium", "low", "info", "unknown"]}

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        for line in proc.stdout:
            # Check cancellation every line
            with _get_session() as session:
                current = session.get(Scan, scan_id)
                if current and current.status == ScanStatus.CANCELLED:
                    proc.terminate()
                    logger.info(f"[scan:{scan_id}] Cancelled mid-run")
                    return

            data = _parse_nuclei_line(line)
            if data:
                finding = _finding_from_nuclei_output(data, scan_id)
                batch.append(finding)
                severity_counters[finding.severity.value] = severity_counters.get(finding.severity.value, 0) + 1

                # Flush batch every 50 findings
                if len(batch) >= 50:
                    with _get_session() as session:
                        session.add_all(batch)
                        scan = session.get(Scan, scan_id)
                        scan.total_findings += len(batch)
                        scan.critical_count += severity_counters.get("critical", 0)
                        scan.high_count += severity_counters.get("high", 0)
                        scan.medium_count += severity_counters.get("medium", 0)
                        scan.low_count += severity_counters.get("low", 0)
                        scan.info_count += severity_counters.get("info", 0)
                        session.commit()
                    batch = []
                    severity_counters = {s: 0 for s in severity_counters}

        proc.wait()

        # Flush remaining
        if batch:
            with _get_session() as session:
                session.add_all(batch)
                scan = session.get(Scan, scan_id)
                scan.total_findings += len(batch)
                scan.critical_count += severity_counters.get("critical", 0)
                scan.high_count += severity_counters.get("high", 0)
                scan.medium_count += severity_counters.get("medium", 0)
                scan.low_count += severity_counters.get("low", 0)
                scan.info_count += severity_counters.get("info", 0)
                session.commit()

        # Final status update
        with _get_session() as session:
            scan = session.get(Scan, scan_id)
            if scan.status != ScanStatus.CANCELLED:
                if proc.returncode not in (0, 1):  # nuclei returns 1 when findings exist
                    stderr = proc.stderr.read() if proc.stderr else ""
                    scan.status = ScanStatus.FAILED
                    scan.error_message = stderr[:2000] if stderr else f"Exit code {proc.returncode}"
                else:
                    scan.status = ScanStatus.DONE
                scan.completed_at = datetime.utcnow()
                session.commit()

        logger.info(f"[scan:{scan_id}] Completed. Total findings: {scan.total_findings}")

        # Dispatch notifications
        from app.workers.notification_tasks import notify_scan_completed
        notify_scan_completed.delay(scan_id)

    except Exception as exc:
        logger.exception(f"[scan:{scan_id}] Unexpected error: {exc}")
        with _get_session() as session:
            scan = session.get(Scan, scan_id)
            if scan:
                scan.status = ScanStatus.FAILED
                scan.error_message = str(exc)[:2000]
                scan.completed_at = datetime.utcnow()
                session.commit()
        raise

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
