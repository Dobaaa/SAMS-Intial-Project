"""Seed a fully populated demo agreement for the Rev 02 review round.

Inserts (or finds) the BGCC ↔ Microfab warehouse scenario from the Rev 02
reference screenshots — same dataset we use for local PDF previews — so
the alpha environment carries a live agreement that exercises every Rev
02 fix (Comms Address, Time-for-Completion, Milestones, F02 bold + date
superscript, running reference stamp).

Idempotent: if an agreement already exists whose reference matches
``SAG-{YEAR}-319-002``, the script reports it and exits without changing
anything. Otherwise it creates a fresh draft via the same
``agreement_service`` codepath the API uses, so the appendix-config and
cascade rules apply exactly as they would in production.

Run on the VPS::

    cd /var/www/sams/backend
    source venv/bin/activate
    python -m scripts.seed_rev02_demo
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from models.agreement import Agreement
from models.user import RoleEnum, User
from services.agreement_service import (
    create_draft_agreement,
    update_agreement_fields,
)


PROJECT_PAYLOAD: dict[str, str] = {
    "project_name": "Proposed Warehouse Ground + Mezzanine and Compound Wall at Plot No. 2840411 at AL TTAY",
    "project_code": "319",
    "project_location": "Plot No. 2840411, AL TTAY, Dubai, U.A.E.",
    "employer_name": "M/s. Synergy Properties LLC",
    "engineer_name": "M/s. Khatib & Alami Consulting Engineers",
}

SUBCONTRACTOR_PAYLOAD: dict[str, str] = {
    "company_name": "M/s. Microfab Structural Steel Manufacturing LLC",
    "po_box": "3695",
    "trade_licence_no": "1536579",
    "contact_person": "Mr. Ahmed Hassan",
    "email": "ahmed@microfab.ae",
    "phone": "+971 4 765 4321",
    "address": "Al Quoz Industrial Area 3, Dubai, U.A.E.",
}

# F/C/A values matching the Rev 02 preview scenario. A-field cascades
# (F02→A01, F05→A02, F06→A04, F08→A07, F03→A06 etc.) are handled by
# update_agreement_fields, so we only need to set the leaves and the
# manually-entered appendix rows (A03, A05 multifield, A11, A15, A16,
# A17, A18 — A06 is auto-cascaded from F03 but we override with a richer
# multifield value for the demo).
FIELD_VALUES: dict[str, str] = {
    "F01": "2026-05-05",
    "F02": "M/s. Microfab Structural Steel Manufacturing LLC",
    "F03": "3695",
    "F04": "1536579",
    "F05": "M/s. Synergy Properties LLC",
    "F06": "Proposed Warehouse Ground + Mezzanine and Compound Wall at Plot No. 2840411 at AL TTAY, Dubai-UAE",
    "F07": "Plot No. 2840411, AL TTAY, Dubai, U.A.E.",
    "F08": "8500000",
    "F09": (
        "Design, Engineering, Preparation of the Fabrication Drawings, Material "
        "Procurement, Fabrication, Painting, Packing, Loading and Delivery of the "
        "Fabricated Steel Structure Roof, Wall Cladding and Erection works"
    ),
    "A03": "M/s. Khatib & Alami Consulting Engineers",
    "A05": (
        "Attention: Mr. Sanjeev Bhatia\n"
        "Position Title: General Manager\n"
        "Address: P.O. Box 6007, Dubai, U.A.E.\n"
        "Facsimile Number: +971 4 123 4567\n"
        "Email Address: sanjeev@bgcc.ae"
    ),
    "A06": (
        "Attention: Mr. Ahmed Hassan\n"
        "Position Title: Operations Director\n"
        "Address: P.O. Box 3695, Al Quoz Industrial Area 3, Dubai, U.A.E.\n"
        "Facsimile Number: +971 4 765 4321\n"
        "Email Address: ahmed@microfab.ae"
    ),
    "A11": "within 14 days of receipt of unconditional advance payment guarantee",
    "A15": "2026-06-01",
    "A16": "24 months",
    "A17": "01st June 2028",
    "A18": (
        "MS1: Material Submission complete — 2026-07-15\n"
        "MS2: Shop drawing approval — 2026-08-30\n"
        "MS3: First steel delivery — 2026-10-15\n"
        "MS4: Erection 50% complete — 2027-04-30"
    ),
    "A19": "365",
    "A22": "14",
    "C02": "Lump Sum",
    "C04": "within 7 days from receipt of bank guarantee",
    "C05": "30",
    "C06": "50% on Substantial Completion certificate",
    "C07": "50% on expiry of Defects Liability Period",
    "C08": "24 months",
    "C09": "See milestone schedule in Appendix item A18",
    "C10": "12 months",
    "C11": "2000",
    "C12": "14",
    "C13": "Dubai Courts",
    "C14": "Bank Guarantee",
}

TARGET_REFERENCE = f"SAG-{datetime.now(UTC).year}-319-002"


async def _find_admin(db: AsyncSession) -> User:
    res = await db.execute(select(User).where(User.role == RoleEnum.admin).limit(1))
    admin = res.scalar_one_or_none()
    if admin is None:
        raise SystemExit(
            "No admin user found in the database. Create one before seeding."
        )
    return admin


async def main() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(Agreement).where(Agreement.reference_number == TARGET_REFERENCE)
        )
        prior = existing.scalar_one_or_none()
        if prior is not None:
            print(
                f"[skip] agreement {TARGET_REFERENCE} already exists "
                f"(id={prior.id}); not touching it"
            )
            return

        admin = await _find_admin(db)

        agreement = await create_draft_agreement(
            db,
            user=admin,
            project_payload=PROJECT_PAYLOAD,
            subcontractor_payload=SUBCONTRACTOR_PAYLOAD,
            reference_number=TARGET_REFERENCE,
        )

        # Re-fetch in a fresh transaction-aware state before applying values
        # (create_draft_agreement commits, so `agreement` is detached).
        fetched = await db.execute(
            select(Agreement).where(Agreement.id == agreement.id)
        )
        agreement = fetched.scalar_one()

        await update_agreement_fields(
            db,
            agreement=agreement,
            user=admin,
            values=FIELD_VALUES,
        )
        await db.commit()

        print(
            f"[ok] created agreement {agreement.reference_number} "
            f"(id={agreement.id})"
        )


if __name__ == "__main__":
    asyncio.run(main())
