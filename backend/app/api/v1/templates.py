import uuid
import os
import yaml
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from typing import List, Optional
from app.database import get_db
from app.models.user import User
from app.models.template import Template, TemplateSource
from app.core.rbac import require_admin, can_write
from app.api.deps import get_current_user
from app.config import settings

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=List[dict])
async def list_templates(
    search: Optional[str] = None,
    severity: Optional[str] = None,
    source: Optional[TemplateSource] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Template).where(Template.is_active == True)

    if search:
        query = query.where(
            or_(
                Template.name.ilike(f"%{search}%"),
                Template.description.ilike(f"%{search}%"),
            )
        )
    if severity:
        query = query.where(Template.severity == severity)
    if source:
        query = query.where(Template.source == source)

    result = await db.execute(query.offset(skip).limit(limit))
    templates = result.scalars().all()
    return [
        {
            "id": t.id, "path": t.path, "name": t.name,
            "author": t.author, "severity": t.severity,
            "description": t.description, "tags": t.tags,
            "source": t.source, "is_active": t.is_active,
        }
        for t in templates
    ]


@router.post("/sync", response_model=dict)
async def sync_templates(
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_admin),
):
    """Trigger background sync of official nuclei-templates."""
    from app.workers.template_tasks import sync_nuclei_templates
    task = sync_nuclei_templates.delay()
    return {"task_id": task.id, "message": "Template sync started"}


@router.post("/custom", response_model=dict, status_code=201)
async def upload_custom_template(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(can_write),
):
    """Upload a custom YAML template."""
    if not file.filename.endswith((".yaml", ".yml")):
        raise HTTPException(status_code=400, detail="Only YAML files accepted")

    content = await file.read()
    try:
        parsed = yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}")

    # Basic validation
    if not isinstance(parsed, dict) or "id" not in parsed:
        raise HTTPException(status_code=400, detail="Template must have an 'id' field")

    template_id = parsed.get("id", str(uuid.uuid4()))
    info = parsed.get("info", {})
    name = info.get("name", template_id)
    severity = info.get("severity", "unknown")

    # Save to disk
    os.makedirs(settings.NUCLEI_CUSTOM_TEMPLATES_DIR, exist_ok=True)
    file_path = os.path.join(settings.NUCLEI_CUSTOM_TEMPLATES_DIR, file.filename)
    with open(file_path, "wb") as f:
        f.write(content)

    # Upsert in DB
    result = await db.execute(select(Template).where(Template.path == file_path))
    template = result.scalar_one_or_none()
    if not template:
        template = Template(
            id=str(uuid.uuid4()),
            path=file_path,
            name=name,
            severity=severity,
            source=TemplateSource.CUSTOM,
            content=content.decode("utf-8"),
            tags=info.get("tags", []) if isinstance(info.get("tags"), list) else [],
        )
        db.add(template)
    else:
        template.name = name
        template.content = content.decode("utf-8")

    await db.commit()
    return {"id": template.id, "name": name, "path": file_path}


@router.get("/{template_id}/content", response_model=dict)
async def get_template_content(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    content = template.content
    if not content and template.path and os.path.exists(template.path):
        with open(template.path) as f:
            content = f.read()

    return {"id": template.id, "name": template.name, "content": content}


@router.put("/{template_id}/content", response_model=dict)
async def update_template_content(
    template_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(can_write),
):
    result = await db.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if template.source != TemplateSource.CUSTOM:
        raise HTTPException(status_code=400, detail="Can only edit custom templates")

    content = payload.get("content", "")
    try:
        yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}")

    template.content = content
    if template.path and os.path.exists(template.path):
        with open(template.path, "w") as f:
            f.write(content)

    await db.commit()
    return {"id": template.id, "message": "Template updated"}
