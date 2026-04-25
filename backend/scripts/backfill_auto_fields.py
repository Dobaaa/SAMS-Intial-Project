"""One-shot backfill: populate empty appendix/conditions fields from their
auto_source_field_id sources for every existing agreement.

Existing draft agreements predate the generic cascade fix in
update_agreement_fields. Their AgreementFieldValue rows have entered_value=NULL
for fields like A04 (auto from F06), A06 (auto from F03), A09 (auto from C03),
and so on, so the review step + PDF render them as blank. This script walks all
agreements and writes the cascaded values where the target is currently empty.

It is safe to re-run: only writes if the target row is empty AND a source value
exists. Admin overrides (any non-empty target row) are never touched.

Run from backend/:
    .venv/bin/python -m scripts.backfill_auto_fields
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from database import AsyncSessionLocal
from models.agreement import Agreement, AgreementFieldValue
from models.master import MasterField
from services.agreement_service import _advance_payment_from_price


async def backfill() -> None:
    async with AsyncSessionLocal() as db:
        master_fields = (await db.execute(select(MasterField))).scalars().all()
        cascade_pairs = [
            (mf.field_id, mf.auto_source_field_id) for mf in master_fields if mf.auto_source_field_id
        ]
        # Stable order: F08 -> C03 must run before C03 -> A09 so chains propagate.
        cascade_pairs.sort(key=lambda p: (p[1], p[0]))

        agreements = (await db.execute(select(Agreement))).scalars().all()
        if not agreements:
            print("No agreements found.")
            return

        total_writes = 0
        for agr in agreements:
            rows = (
                await db.execute(
                    select(AgreementFieldValue).where(AgreementFieldValue.agreement_id == agr.id)
                )
            ).scalars().all()
            row_map: dict[str, AgreementFieldValue] = {r.field_id: r for r in rows}
            effective: dict[str, str] = {fid: (r.entered_value or "") for fid, r in row_map.items()}

            # Legacy cleanup: A10 was originally seeded with default_value="10"
            # (a percentage flag) but the field semantically holds the AED
            # amount = 10% of F08, identical to C03/A09. Treat the literal "10"
            # as unset so the F08 cascade can replace it. Force-overwrite is
            # tracked so the write step actually persists the new value.
            force_overwrite: set[str] = set()
            if effective.get("A10") == "10":
                effective["A10"] = ""
                force_overwrite.add("A10")

            f08 = effective.get("F08") or ""
            if f08:
                ten_pct = _advance_payment_from_price(f08)
                if ten_pct is not None:
                    for target in ("C03", "A10"):
                        if not effective.get(target):
                            effective[target] = ten_pct

            # Two passes for chained cascades (F08 -> C03 -> A09).
            for _ in range(2):
                for target, src in cascade_pairs:
                    if effective.get(target):
                        continue
                    src_val = effective.get(src)
                    if src_val:
                        effective[target] = src_val

            writes = 0
            for fid, val in effective.items():
                if not val:
                    continue
                row = row_map.get(fid)
                if row is None:
                    row = AgreementFieldValue(agreement_id=agr.id, field_id=fid, entered_value=val)
                    db.add(row)
                    row_map[fid] = row
                    writes += 1
                elif not (row.entered_value or "").strip() or fid in force_overwrite:
                    row.entered_value = val
                    writes += 1

            if writes:
                total_writes += writes
                print(f"agreement {agr.reference_number}: backfilled {writes} field(s)")
            else:
                print(f"agreement {agr.reference_number}: nothing to backfill")

        await db.commit()
        print(f"Done. Total field writes: {total_writes}")


if __name__ == "__main__":
    asyncio.run(backfill())
