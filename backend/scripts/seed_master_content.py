"""Seed verbatim PDF prose into the latest active MasterTemplate rows.

Idempotent: finds the most recent active template per type and overwrites its
content_html with the file under backend/seeds/. If no active template exists,
the script exits with a clear instruction (templates must be created via the
API first; this script only refreshes their content).

Form + Conditions content is read from:
  backend/seeds/form_master.html
  backend/seeds/conditions_master.html
The Appendix template is rendered entirely by Jinja (templates/appendix.html)
so it does not need a content_html row -- this script leaves Appendix alone.

Run after seed_fields.py:
    python -m scripts.seed_master_content
"""
from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

from sqlalchemy import select

from database import AsyncSessionLocal
from models.master import MasterTemplate, TemplateTypeEnum


SEEDS_DIR = Path(__file__).resolve().parents[1] / "seeds"

CONTENT_BY_TYPE: dict[TemplateTypeEnum, Path] = {
    TemplateTypeEnum.form: SEEDS_DIR / "form_master.html",
    TemplateTypeEnum.conditions: SEEDS_DIR / "conditions_master.html",
}


async def seed_master_content() -> None:
    async with AsyncSessionLocal() as session:
        for template_type, source_path in CONTENT_BY_TYPE.items():
            if not source_path.exists():
                raise FileNotFoundError(f"Missing seed source: {source_path}")
            html = source_path.read_text(encoding="utf-8")

            stmt = (
                select(MasterTemplate)
                .where(
                    MasterTemplate.type == template_type,
                    MasterTemplate.is_active.is_(True),
                )
                .order_by(MasterTemplate.created_at.desc())
                .limit(1)
            )
            template = (await session.execute(stmt)).scalar_one_or_none()
            if template is None:
                raise RuntimeError(
                    f"No active MasterTemplate row for '{template_type.value}'. "
                    "Create it via POST /api/masters/ first, then re-run this script."
                )

            if template.content_html == html:
                print(f"[skip] {template_type.value} v{template.version_number} already up to date")
                continue

            template.content_html = html
            template.version_date = date.today()
            print(f"[update] {template_type.value} v{template.version_number} content refreshed")

        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed_master_content())
