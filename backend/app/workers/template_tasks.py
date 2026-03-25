"""
Template synchronization task.
Clones / pulls nuclei-templates from GitHub and indexes them in DB.
"""
import os
import uuid
import yaml
import logging
from pathlib import Path

import git
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.workers.celery_app import celery_app
from app.config import settings
from app.models.template import Template, TemplateSource

logger = logging.getLogger(__name__)

NUCLEI_TEMPLATES_REPO = "https://github.com/projectdiscovery/nuclei-templates.git"

_engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)


def _get_session() -> Session:
    return Session(_engine)


def _parse_template(file_path: str) -> dict | None:
    try:
        with open(file_path, "r", errors="ignore") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return None
        info = data.get("info", {})
        if not info:
            return None

        tags = info.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]
        elif not isinstance(tags, list):
            tags = []

        reference = info.get("reference", [])
        if isinstance(reference, str):
            reference = [reference]
        elif not isinstance(reference, list):
            reference = []

        return {
            "path": file_path,
            "name": info.get("name", os.path.basename(file_path)),
            "author": str(info.get("author", "")),
            "severity": info.get("severity", "unknown"),
            "description": info.get("description"),
            "tags": tags,
            "reference": reference,
        }
    except Exception:
        return None


@celery_app.task(name="app.workers.template_tasks.sync_nuclei_templates",
                 soft_time_limit=600, time_limit=700)
def sync_nuclei_templates():
    """Clone or pull nuclei-templates, then index all YAML files in DB."""
    templates_dir = settings.NUCLEI_TEMPLATES_DIR
    os.makedirs(templates_dir, exist_ok=True)

    try:
        if os.path.exists(os.path.join(templates_dir, ".git")):
            logger.info("Pulling latest nuclei-templates...")
            repo = git.Repo(templates_dir)
            repo.remotes.origin.pull()
        else:
            logger.info("Cloning nuclei-templates...")
            git.Repo.clone_from(NUCLEI_TEMPLATES_REPO, templates_dir, depth=1)
    except Exception as e:
        logger.error(f"Git operation failed: {e}")
        return {"error": str(e)}

    # Walk and index all YAML files
    created = updated = skipped = 0

    with _get_session() as session:
        for yaml_file in Path(templates_dir).rglob("*.yaml"):
            str_path = str(yaml_file)

            # Skip workflow/helper files
            if any(skip in str_path for skip in ["/.github/", "/helpers/", "/.git/"]):
                continue

            parsed = _parse_template(str_path)
            if not parsed:
                skipped += 1
                continue

            existing = session.execute(
                select(Template).where(Template.path == str_path)
            ).scalar_one_or_none()

            if existing:
                existing.name = parsed["name"]
                existing.severity = parsed["severity"]
                existing.tags = parsed["tags"]
                existing.description = parsed["description"]
                updated += 1
            else:
                template = Template(
                    id=str(uuid.uuid4()),
                    path=str_path,
                    name=parsed["name"],
                    author=parsed["author"],
                    severity=parsed["severity"],
                    description=parsed["description"],
                    tags=parsed["tags"],
                    reference=parsed["reference"],
                    source=TemplateSource.OFFICIAL,
                    is_active=True,
                )
                session.add(template)
                created += 1

            # Batch commit every 500
            if (created + updated) % 500 == 0:
                session.commit()

        session.commit()

    result = {"created": created, "updated": updated, "skipped": skipped}
    logger.info(f"Template sync complete: {result}")
    return result
