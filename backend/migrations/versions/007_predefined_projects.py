"""Add projects.reference + seed BGCC predefined projects.

BGCC supplied a fixed list of projects (Project Details.xlsx). They should be
pre-saved so the agreement wizard can offer them in a dropdown and autofill
name / site no / location / employer / engineer / reference. "Others" in the
dropdown is a UI-only manual-entry option and is NOT seeded here.

Adds a nullable ``reference`` column to ``projects`` and inserts the seed rows
(idempotent via NOT EXISTS on project_code).

Revision ID: 007_predefined_projects
Revises: 006_add_c15_optional_terms
Create Date: 2026-05-20
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "007_predefined_projects"
down_revision: str | None = "006_add_c15_optional_terms"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PROJECTS = [
    {'employer_name': 'M/s. Bhatia General Contracting Co. (L.L.C.)',
 'engineer_name': 'M/s. Golden Cube Architectural  & Interior Design Consultancy',
 'project_code': 'PJ-98',
 'project_location': 'Ras Al Khor Industrial Second Dubai-UAE',
 'project_name': 'Proposed G+M Office and Service Block Plot No. 6131211 at Ras Al Khor Industrial Second Dubai-UAE',
 'reference': 'SAG-BGCC-QS-2026-098-SXX'},
    {'employer_name': 'M/s. Palm NorthAcre Holding Limited',
 'engineer_name': 'M/s. Lacasa Architechs & Engineering Consultants',
 'project_code': 'PJ-313',
 'project_location': 'Ocean House, Palm Jumeirah Dubai UAE',
 'project_name': 'Main Works – B+G+9+R Residential Building Project – Ocean House, Palm Jumeirah Dubai UAE',
 'reference': 'SAG-BGCC-QS-2026-313-SXX'},
    {'employer_name': 'M/s. Sol Properties Development',
 'engineer_name': 'M/s. Group Consultant International',
 'project_code': 'PJ-315',
 'project_location': 'Downtown Burj Khalifa District-Dubai-UAE',
 'project_name': 'Solara Tower Dubai (Residential Tower 4B+G+M+3P+51 Floors on Plot No 3450811) at Burj Khalifa Downtown Dubai-UAE',
 'reference': 'SAG-BGCC-QS-2026-315-SXX'},
    {'employer_name': 'Mohammed Bin Rashid Al Maktoum City District One Dubai-UAE',
 'engineer_name': 'M/s. Conin International Consultants',
 'project_code': 'PJ-317',
 'project_location': 'Mohammed Bin Rashid Al Maktoum City District One Dubai-UAE',
 'project_name': 'Naya Cluster-1 Mohammed Bin Rashid Al Maktoum City District One, Phase 3A.2 South (Naya-1 G+20+Roof, Naya-2 G+12+Roof, Naya-3 G+16+Roof)',
 'reference': 'SAG-BGCC-QS-2026-317-SXX'},
    {'employer_name': 'M/s. NAS Estates LLC',
 'engineer_name': 'M/s. Conin International Consultants',
 'project_code': 'PJ-318',
 'project_location': 'Nad Al Sheba Gardens E-Phase 4 Dubai, UAE',
 'project_name': 'SH-0003-04-Nad Al Sheba Gardens E-Phase 4 Dubai, UAE',
 'reference': 'SAG-BGCC-QS-2026-318-SXX'},
    {'employer_name': 'M/s. Sol Properties Development',
 'engineer_name': 'M/s. Federal Engineering Consultant',
 'project_code': 'PJ-319',
 'project_location': 'Al Barsha South Fifth, Jumeirah Village Triangle Dubai-UAE',
 'project_name': 'SOL LEVANTE Mixed-Use Residential Building G+4P+20F+R) Plot No: JVT 01G HRA 100 Al Barsha South Fifth, Jumeirah Village Triangle Dubai-UAE',
 'reference': 'SAG-BGCC-QS-2026-319-SXX'},
    {'employer_name': 'M/s. Sol Properties Development',
 'engineer_name': 'M/s. Federal Engineering Consultant',
 'project_code': 'PJ-320',
 'project_location': 'Trade Centre First, Dubai-UAE',
 'project_name': 'SOL LUXE Mixed-Use Residential Building (B+G+59F+R) On Plot No:3350144, at Trade Centre First, Dubai-UAE',
 'reference': 'SAG-BGCC-QS-2026-320-SXX'},
    {'employer_name': 'M/s. Sahel Al Akhdar Building Materials Trading',
 'engineer_name': 'M/s. Nad Al Sheba Engineering Consultants (NASEC)',
 'project_code': 'PJ-321',
 'project_location': 'AL TTAY, Dubai-UAE',
 'project_name': 'Proposed Warehouse Ground + Mezzanine and Compound Wall at Plot No. 2840411 at AL TTAY, Dubai-UAE for M/s. Synergy Properties',
 'reference': 'SAG-BGCC-QS-2026-321-SXX'},
]



_INSERT = sa.text(
    """
    INSERT INTO projects
        (id, project_name, project_code, project_location, employer_name,
         engineer_name, reference, created_at)
    VALUES
        (gen_random_uuid(), :project_name, :project_code, :project_location,
         :employer_name, :engineer_name, :reference, now())
    ON CONFLICT (project_code) DO NOTHING
    """
)


def upgrade() -> None:
    op.add_column("projects", sa.Column("reference", sa.String(length=255), nullable=True))
    bind = op.get_bind()
    for proj in PROJECTS:
        bind.execute(_INSERT, proj)


def downgrade() -> None:
    bind = op.get_bind()
    codes = [p["project_code"] for p in PROJECTS]
    if codes:
        bind.execute(
            sa.text("DELETE FROM projects WHERE project_code = ANY(:codes)"),
            {"codes": codes},
        )
    op.drop_column("projects", "reference")
