"""
Core Nuclei orchestration task.

Flow:
  1. Load scan + targets from DB
  2. Write targets to a temp file
  3. Build nuclei CLI command from scan config (all args as list — never shell=True)
  4. Stream nuclei JSON output line by line
     - stderr drained concurrently in a daemon thread to prevent buffer deadlock
     - Cancellation checked every CANCEL_CHECK_INTERVAL lines (not every line)
     - Findings deduplicated in-memory via (template_id, matched_at) hash set
  5. Parse + insert findings in batches (BATCH_SIZE)
  6. Update scan status + counters atomically per batch
  7. Trigger webhook notifications

Security note: targets are written to a file, never interpolated into shell arguments.
Nuclei is always invoked as a list (subprocess.Popen with shell=False).
"""
import os
import json
import uuid
import shutil
import subprocess
import tempfile
import threading
import logging
from datetime import datetime
from typing import List, Set

from celery import Task
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.workers.celery_app import celery_app
from app.config import settings
from app.models.scan import Scan, ScanStatus, ScanTargetList
from app.models.finding import Finding, FindingSeverity
from app.models.target import TargetList

logger = logging.getLogger(__name__)

# How often (in parsed lines) to check for cancellation
CANCEL_CHECK_INTERVAL = 50
# Batch size for DB inserts
BATCH_SIZE = 50

# Allowed extra flags whitelist (prevent arbitrary CLI injection via config)
ALLOWED_EXTRA_FLAGS: Set[str] = {
    "-headless", "-no-interactsh", "-stats", "-silent", "-debug",
    "-disable-update-check", "-tlsi", "-no-httpx",
    "-follow-redirects", "-follow-host-redirects",
    "-max-redirects", "-disable-redirects",
    "-system-resolvers", "-disable-clustering",
    "-passive", "-et", "-exclude-templates",
    "-include-tags", "-exclude-matchers",
    "-response-size-read", "-response-size-save",
    "-no-color",
}

# Use sync SQLAlchemy for Celery workers (no event loop in worker threads)
_engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=5)


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


def _sanitise_extra_flags(raw_flags: List[str]) -> List[str]:
    """
    Whitelist-filter extra nuclei flags provided by user.
    Rejects any flag not in the approved set to prevent CLI injection.
    """
    clean = []
    for flag in raw_flags:
        flag = flag.strip()
        if not flag:
            continue
        # Accept only flags that start with '-' and appear in the whitelist
        base = flag.split("=")[0] if "=" in flag else flag
        if base in ALLOWED_EXTRA_FLAGS:
            clean.append(flag)
        else:
            logger.warning(f"Rejected disallowed extra_flag: {flag!r}")
    return clean


def _build_nuclei_cmd(scan: Scan, targets_file: str, output_file: str) -> List[str]:
    """
    Build the nuclei CLI command as a list (never as a shell string).
    All arguments are typed — no user strings interpolated directly into the command.
    """
    config = scan.config

    rate_limit = max(1, min(int(config.get("rate_limit", settings.NUCLEI_RATE_LIMIT)), 1000))
    bulk_size = max(1, min(int(config.get("bulk_size", settings.NUCLEI_BULK_SIZE)), 500))
    concurrency = max(1, min(int(config.get("concurrency", settings.NUCLEI_CONCURRENCY)), 500))
    timeout = max(5, min(int(config.get("timeout", 30)), 300))
    retries = max(0, min(int(config.get("retries", 1)), 5))

    cmd: List[str] = [
        settings.NUCLEI_BINARY,
        "-list", targets_file,
        "-json-export", output_file,
        "-json",
        "-silent",
        "-no-color",
        "-disable-update-check",
        "-rate-limit", str(rate_limit),
        "-bulk-size", str(bulk_size),
        "-concurrency", str(concurrency),
        "-timeout", str(timeout),
        "-retries", str(retries),
    ]

    severities = [s for s in config.get("severity", []) if s in ("critical", "high", "medium", "low", "info")]
    if severities:
        cmd += ["-severity", ",".join(severities)]

    # Tags must only contain alphanumeric, hyphens, underscores, commas
    _tag_re = __import__("re").compile(r"^[a-zA-Z0-9_,\-]+$")
    tags = [t for t in config.get("tags", []) if _tag_re.match(t)]
    if tags:
        cmd += ["-tags", ",".join(tags)]

    exclude_tags = [t for t in config.get("exclude_tags", []) if _tag_re.match(t)]
    if exclude_tags:
        cmd += ["-exclude-tags", ",".join(exclude_tags)]

    # Template paths must exist on disk and be within allowed dirs
    allowed_bases = [settings.NUCLEI_TEMPLATES_DIR, settings.NUCLEI_CUSTOM_TEMPLATES_DIR]
    for t in config.get("templates", []):
        real = os.path.realpath(t)
        if any(real.startswith(os.path.realpath(b)) for b in allowed_bases):
            cmd += ["-t", real]
        else:
            logger.warning(f"Rejected template path outside allowed dirs: {t!r}")

    if not config.get("templates"):
        # Default: use official templates dir
        cmd += ["-t", settings.NUCLEI_TEMPLATES_DIR]
        if os.path.isdir(settings.NUCLEI_CUSTOM_TEMPLATES_DIR):
            cmd += ["-t", settings.NUCLEI_CUSTOM_TEMPLATES_DIR]

    # Whitelist-filtered extra flags
    cmd.extend(_sanitise_extra_flags(config.get("extra_flags", [])))

    return cmd


def _collect_targets(scan_id: str, session: Session) -> List[str]:
    stl_result = session.execute(
        select(ScanTargetList).where(ScanTargetList.scan_id == scan_id)
    )
    stls = stl_result.scalars().all()

    targets: set = set()
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
        if isinstance(data, dict) and ("template-id" in data or "matched-at" in data):
            return data
    except (json.JSONDecodeError, ValueError):
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
        extracted_results=data.get("extracted-results", []) or [],
        curl_command=data.get("curl-command"),
        description=info.get("description"),
        reference=info.get("reference", []) if isinstance(info.get("reference"), list) else [],
        tags=info.get("tags", []) if isinstance(info.get("tags"), list) else [],
        raw=data,
    )


def _drain_stderr(proc: subprocess.Popen, buffer: list) -> None:
    """Drain stderr in a daemon thread to prevent stdout/stderr buffer deadlock."""
    try:
        for line in proc.stderr:
            buffer.append(line)
            if len(buffer) > 500:  # Keep last 500 lines max
                buffer.pop(0)
    except Exception:
        pass


class ScanTask(Task):
    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        scan_id = args[0] if args else None
        if scan_id:
            with _get_session() as session:
                scan = session.get(Scan, scan_id)
                if scan and scan.status not in (ScanStatus.DONE, ScanStatus.CANCELLED):
                    scan.status = ScanStatus.FAILED
                    scan.error_message = str(exc)[:4000]
                    scan.completed_at = datetime.utcnow()
                    session.commit()


@celery_app.task(
    bind=True,
    base=ScanTask,
    name="app.workers.scan_tasks.run_nuclei_scan",
    max_retries=0,
    soft_time_limit=settings.SCAN_TIMEOUT_SECONDS + 300,
    time_limit=settings.SCAN_TIMEOUT_SECONDS + 600,
)
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
            scan.error_message = "No targets found in associated target lists"
            scan.completed_at = datetime.utcnow()
            session.commit()
            return

        if len(targets) > settings.MAX_TARGETS_PER_SCAN:
            scan.status = ScanStatus.FAILED
            scan.error_message = f"Too many targets: {len(targets)} exceeds limit {settings.MAX_TARGETS_PER_SCAN}"
            scan.completed_at = datetime.utcnow()
            session.commit()
            return

        scan.status = ScanStatus.RUNNING
        scan.started_at = datetime.utcnow()
        scan.total_targets = len(targets)
        session.commit()

    work_dir = tempfile.mkdtemp(prefix=f"nuclei_{scan_id}_")
    targets_file = os.path.join(work_dir, "targets.txt")
    output_file = os.path.join(work_dir, "results.json")
    stderr_buffer: list = []

    try:
        with open(targets_file, "w") as f:
            f.write("\n".join(targets))

        with _get_session() as session:
            scan = session.get(Scan, scan_id)
            cmd = _build_nuclei_cmd(scan, targets_file, output_file)

        logger.info(f"[scan:{scan_id}] CMD: {' '.join(cmd)}")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            # Never use shell=True — prevents shell injection
        )

        # Drain stderr concurrently to prevent buffer deadlock
        stderr_thread = threading.Thread(
            target=_drain_stderr, args=(proc, stderr_buffer), daemon=True
        )
        stderr_thread.start()

        batch: List[Finding] = []
        # In-memory dedup set: (template_id, matched_at) tuples
        seen_fingerprints: Set[tuple] = set()
        severity_counters = {s: 0 for s in ["critical", "high", "medium", "low", "info", "unknown"]}
        line_count = 0

        for line in proc.stdout:
            line_count += 1

            # Check cancellation every CANCEL_CHECK_INTERVAL lines
            if line_count % CANCEL_CHECK_INTERVAL == 0:
                with _get_session() as session:
                    current = session.get(Scan, scan_id)
                    if current and current.status == ScanStatus.CANCELLED:
                        proc.terminate()
                        logger.info(f"[scan:{scan_id}] Cancelled mid-run at line {line_count}")
                        return

            data = _parse_nuclei_line(line)
            if not data:
                continue

            # Deduplicate findings
            fingerprint = (data.get("template-id"), data.get("matched-at"))
            if fingerprint in seen_fingerprints:
                continue
            seen_fingerprints.add(fingerprint)

            # Enforce max findings limit
            if len(seen_fingerprints) > settings.MAX_FINDINGS_PER_SCAN:
                logger.warning(f"[scan:{scan_id}] Max findings limit reached, stopping early")
                proc.terminate()
                break

            finding = _finding_from_nuclei_output(data, scan_id)
            batch.append(finding)
            sev_key = finding.severity.value
            severity_counters[sev_key] = severity_counters.get(sev_key, 0) + 1

            if len(batch) >= BATCH_SIZE:
                _flush_batch(scan_id, batch, severity_counters)
                batch = []
                severity_counters = {s: 0 for s in severity_counters}

        # Wait for process to finish with hard timeout
        try:
            proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            logger.warning(f"[scan:{scan_id}] Nuclei did not exit cleanly, killing")
            proc.kill()
            proc.wait()

        stderr_thread.join(timeout=5)

        # Flush remaining batch
        if batch:
            _flush_batch(scan_id, batch, severity_counters)

        # Final status
        with _get_session() as session:
            scan = session.get(Scan, scan_id)
            if scan and scan.status not in (ScanStatus.CANCELLED,):
                # nuclei exits 0 (no findings) or 1 (findings found) — both are success
                if proc.returncode not in (0, 1):
                    stderr_text = "".join(stderr_buffer[-50:])  # last 50 lines
                    scan.status = ScanStatus.FAILED
                    scan.error_message = (
                        f"Nuclei exited with code {proc.returncode}. "
                        f"Stderr: {stderr_text[:3000]}"
                    )
                else:
                    scan.status = ScanStatus.DONE
                scan.completed_at = datetime.utcnow()
                session.commit()
                logger.info(
                    f"[scan:{scan_id}] Completed status={scan.status.value} "
                    f"findings={scan.total_findings}"
                )

        # Dispatch notifications
        from app.workers.notification_tasks import notify_scan_completed
        notify_scan_completed.delay(scan_id)

    except Exception as exc:
        logger.exception(f"[scan:{scan_id}] Unexpected error: {exc}")
        with _get_session() as session:
            scan = session.get(Scan, scan_id)
            if scan and scan.status not in (ScanStatus.DONE, ScanStatus.CANCELLED):
                scan.status = ScanStatus.FAILED
                scan.error_message = str(exc)[:4000]
                scan.completed_at = datetime.utcnow()
                session.commit()
        raise

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _flush_batch(
    scan_id: str,
    batch: List[Finding],
    severity_counters: dict,
) -> None:
    """Persist a batch of findings and update scan counters atomically."""
    if not batch:
        return
    with _get_session() as session:
        try:
            session.add_all(batch)
            scan = session.get(Scan, scan_id)
            if scan:
                scan.total_findings += len(batch)
                scan.critical_count += severity_counters.get("critical", 0)
                scan.high_count += severity_counters.get("high", 0)
                scan.medium_count += severity_counters.get("medium", 0)
                scan.low_count += severity_counters.get("low", 0)
                scan.info_count += severity_counters.get("info", 0)
            session.commit()
        except Exception as e:
            logger.error(f"[scan:{scan_id}] Batch flush failed: {e}")
            session.rollback()
            raise
