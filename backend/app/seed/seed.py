"""Seed a realistic Official Statistical System.

Run with:  python -m app.seed.seed

Generates 8 MoSPI divisions across 5 states, 6 FRAC roles, 12 competencies over
the four domains named in the problem statement, ~200 officers, and 12 months of
evidence history. All data is SYNTHETIC — no real officer names or records.

Deterministic: the same seed produces the same population every run, so the demo
never shifts under you.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db import SessionLocal, reset_schema
from app.models import (
    AuditLog,
    Competency,
    CompetencyDomain,
    CompetencyProfile,
    Criticality,
    Division,
    EvidenceSource,
    FracRole,
    ProficiencyEvidence,
    RoleCompetencyRequirement,
    User,
    UserRole,
)
from app.models_learning import Course, CourseCompletion
from app.seed.questions import seed_questions
from app.services.competency import recompute_profile
from app.services.igot import sync_catalogue
from app.services.recommender import embed_catalogue

RNG = random.Random(26101)
NOW = datetime.now(timezone.utc)

DEMO_PASSWORD = "Sankhya@2026"

DIVISIONS = [
    ("NAD", "National Accounts Division", "Delhi"),
    ("ESD", "Economic Statistics Division", "Delhi"),
    ("SSD", "Social Statistics Division", "Delhi"),
    ("DIID", "Data Informatics & Innovation Division", "Delhi"),
    ("SDRD", "Survey Design & Research Division", "West Bengal"),
    ("DPD", "Data Processing Division", "West Bengal"),
    ("FOD", "Field Operations Division", "Maharashtra"),
    ("NSSTA", "National Statistical Systems Training Academy", "Uttar Pradesh"),
]

# Ascending seniority. The Promotion Readiness Engine walks this ordering.
FRAC_ROLES = [
    ("JSO", "Junior Statistical Officer", "Level 6", 1, 0.0),
    ("SSO", "Senior Statistical Officer", "Level 7", 2, 4.0),
    ("AD", "Assistant Director", "Level 10", 3, 8.0),
    ("DD", "Deputy Director", "Level 11", 4, 13.0),
    ("JD", "Joint Director", "Level 12", 5, 18.0),
    ("DIR", "Director", "Level 13", 6, 24.0),
]

COMPETENCIES = [
    ("STAT-SAMP", "Sampling & Survey Design", CompetencyDomain.STATISTICAL),
    ("STAT-EST", "Estimation & Weighting", CompetencyDomain.STATISTICAL),
    ("STAT-NAS", "National Accounts Methodology", CompetencyDomain.STATISTICAL),
    ("STAT-INDEX", "Index Number Construction", CompetencyDomain.STATISTICAL),
    ("TECH-ANL", "Data Analytics & Machine Learning", CompetencyDomain.TECHNICAL),
    ("TECH-GIS", "GIS & Spatial Analysis", CompetencyDomain.TECHNICAL),
    ("TECH-BIG", "Big Data & Cloud Platforms", CompetencyDomain.TECHNICAL),
    ("TECH-VIZ", "Data Visualisation & Dissemination", CompetencyDomain.TECHNICAL),
    ("DG-QUAL", "Data Governance & Quality Assurance", CompetencyDomain.DIGITAL_GOVERNANCE),
    ("DG-PRIV", "Data Privacy & Confidentiality", CompetencyDomain.DIGITAL_GOVERNANCE),
    ("BEH-COMM", "Communication & Statistical Reporting", CompetencyDomain.BEHAVIOURAL),
    ("BEH-LEAD", "Team Leadership & Coordination", CompetencyDomain.BEHAVIOURAL),
]

# Requirement by role seniority (level_order 1..6), before per-competency tuning.
BASE_REQUIREMENT = {1: 2.0, 2: 2.5, 3: 3.0, 4: 3.5, 5: 4.0, 6: 4.5}

# Competencies that matter more as you go up, and those that matter less.
SENIORITY_WEIGHTED = {"BEH-LEAD": 0.8, "BEH-COMM": 0.5, "DG-QUAL": 0.3}
CRITICAL_FOR_ROLE = {
    "JSO": {"STAT-SAMP", "TECH-VIZ"},
    "SSO": {"STAT-SAMP", "STAT-EST"},
    "AD": {"STAT-EST", "DG-QUAL"},
    "DD": {"STAT-NAS", "TECH-GIS", "BEH-LEAD"},
    "JD": {"BEH-LEAD", "DG-QUAL", "STAT-NAS"},
    "DIR": {"BEH-LEAD", "BEH-COMM", "DG-QUAL"},
}

FIRST_NAMES = [
    "Aarav", "Ananya", "Rohan", "Priya", "Vikram", "Meera", "Arjun", "Kavita",
    "Sanjay", "Divya", "Rahul", "Sunita", "Karthik", "Neha", "Manish", "Lakshmi",
    "Imran", "Fatima", "Joseph", "Grace", "Tenzin", "Deepa", "Suresh", "Anjali",
    "Nikhil", "Pooja", "Ravi", "Shalini", "Amit", "Rekha", "Gopal", "Ritu",
]
LAST_NAMES = [
    "Sharma", "Iyer", "Banerjee", "Reddy", "Nair", "Patel", "Khan", "Das",
    "Chauhan", "Menon", "Joshi", "Mukherjee", "Rao", "Verma", "Pillai", "Ghosh",
    "Kulkarni", "Bhatt", "Sinha", "Naidu", "Thomas", "Mishra", "Gowda", "Saxena",
]

# Evidence sources weighted by how often they realistically occur.
SOURCE_POOL = [
    (EvidenceSource.QUIZ, 30),
    (EvidenceSource.LEARNING_ACTIVITY, 22),
    (EvidenceSource.DIAGNOSTIC, 12),
    (EvidenceSource.SUPERVISOR, 12),
    (EvidenceSource.INTERVIEW, 8),
    (EvidenceSource.SIMULATION, 7),
    (EvidenceSource.CERTIFICATION, 5),
    (EvidenceSource.HISTORICAL, 4),
]

SOURCE_NOISE = {
    EvidenceSource.SIMULATION: 0.25,
    EvidenceSource.QUIZ: 0.40,
    EvidenceSource.DIAGNOSTIC: 0.45,
    EvidenceSource.INTERVIEW: 0.50,
    EvidenceSource.CERTIFICATION: 0.55,
    EvidenceSource.SUPERVISOR: 0.65,
    EvidenceSource.LEARNING_ACTIVITY: 0.70,
    EvidenceSource.HISTORICAL: 0.80,
}


def _pick_source() -> EvidenceSource:
    total = sum(w for _, w in SOURCE_POOL)
    roll = RNG.uniform(0, total)
    upto = 0.0
    for source, weight in SOURCE_POOL:
        upto += weight
        if roll <= upto:
            return source
    return EvidenceSource.QUIZ


def _clamp(value: float) -> float:
    return round(max(1.0, min(5.0, value)), 2)


def build_framework(db: Session) -> tuple[dict, dict, dict]:
    divisions = {}
    for code, name, state in DIVISIONS:
        d = Division(code=code, name=name, state=state)
        db.add(d)
        divisions[code] = d

    roles = {}
    for code, name, grade, order, min_years in FRAC_ROLES:
        r = FracRole(
            code=code, name=name, grade=grade,
            level_order=order, min_service_years=min_years,
        )
        db.add(r)
        roles[code] = r

    competencies = {}
    for code, name, domain in COMPETENCIES:
        c = Competency(code=code, name=name, domain=domain)
        db.add(c)
        competencies[code] = c

    db.flush()

    for role_code, role in roles.items():
        critical = CRITICAL_FOR_ROLE.get(role_code, set())
        for comp_code, comp in competencies.items():
            required = BASE_REQUIREMENT[role.level_order]
            required += SENIORITY_WEIGHTED.get(comp_code, 0.0) * (role.level_order / 6.0)
            if comp_code in critical:
                criticality = Criticality.CRITICAL
                required += 0.5
            elif comp.domain == CompetencyDomain.STATISTICAL:
                criticality = Criticality.HIGH
            elif comp.domain == CompetencyDomain.BEHAVIOURAL and role.level_order >= 4:
                criticality = Criticality.HIGH
            else:
                criticality = Criticality.MEDIUM

            db.add(
                RoleCompetencyRequirement(
                    frac_role_id=role.id,
                    competency_id=comp.id,
                    required_level=_clamp(required),
                    criticality=criticality,
                )
            )

    db.flush()
    return divisions, roles, competencies


def _latent_ability(role_order: int) -> float:
    """An officer's underlying skill, loosely tracking seniority."""
    return _clamp(RNG.gauss(1.4 + role_order * 0.5, 0.55))


def generate_evidence(
    db: Session, user: User, latent: dict[int, float], months: int = 12
) -> int:
    """Twelve months of observations, drifting slowly upward as people learn."""
    count = RNG.randint(9, 26)
    written = 0

    for _ in range(count):
        comp_id = RNG.choice(list(latent.keys()))
        source = _pick_source()
        days_ago = RNG.randint(0, months * 30)
        created = NOW - timedelta(days=days_ago, hours=RNG.randint(0, 23))

        # Skill grows over the year, so older evidence sits slightly lower.
        growth = 0.35 * (1 - days_ago / (months * 30))
        observed = RNG.gauss(latent[comp_id] + growth, SOURCE_NOISE[source])

        ev = ProficiencyEvidence(
            user_id=user.id,
            competency_id=comp_id,
            level_estimate=_clamp(observed),
            confidence=round(RNG.uniform(0.65, 1.0), 2),
            source=source,
            source_ref=f"{source.value}:{RNG.randint(1000, 9999)}",
            created_at=created,
        )
        db.add(ev)
        written += 1

    # ~1 in 4 officers self-rates optimistically. This is what makes the
    # confidence-competence divergence check fire on real data rather than a
    # hand-placed demo row.
    if RNG.random() < 0.25:
        comp_id = RNG.choice(list(latent.keys()))
        db.add(
            ProficiencyEvidence(
                user_id=user.id,
                competency_id=comp_id,
                level_estimate=_clamp(latent[comp_id] + RNG.uniform(1.2, 2.2)),
                confidence=1.0,
                source=EvidenceSource.SELF,
                source_ref="onboarding-self-assessment",
                created_at=NOW - timedelta(days=RNG.randint(20, 300)),
            )
        )
        written += 1

    return written


def generate_scripted_evidence(
    db: Session, user: User, latent: dict[int, float], months: int = 12
) -> int:
    """Evidence across EVERY competency, for the demo officer.

    The random generator above leaves some competencies unmeasured, which is
    realistic for the population but useless for a demo: the radar chart loses
    axes, and a single low-weight observation sits below the confidence floor
    that divergence detection requires. Here every competency gets 3-4
    observations from reliable sources, so the narrative is stable across reseeds.
    """
    written = 0
    for comp_id, true_level in latent.items():
        for _ in range(RNG.randint(3, 4)):
            source = RNG.choice([
                EvidenceSource.QUIZ,
                EvidenceSource.SIMULATION,
                EvidenceSource.DIAGNOSTIC,
                EvidenceSource.INTERVIEW,
            ])
            days_ago = RNG.randint(0, months * 30)
            growth = 0.3 * (1 - days_ago / (months * 30))
            db.add(
                ProficiencyEvidence(
                    user_id=user.id,
                    competency_id=comp_id,
                    level_estimate=_clamp(
                        RNG.gauss(true_level + growth, SOURCE_NOISE[source] * 0.6)
                    ),
                    confidence=round(RNG.uniform(0.8, 1.0), 2),
                    source=source,
                    source_ref=f"{source.value}:{RNG.randint(1000, 9999)}",
                    created_at=NOW - timedelta(days=days_ago, hours=RNG.randint(0, 23)),
                )
            )
            written += 1
    return written


def make_user(
    email: str, name: str, role: UserRole, division: Division,
    frac_role: FracRole, service_years: float,
) -> User:
    return User(
        email=email,
        full_name=name,
        role=role,
        password_hash=hash_password(DEMO_PASSWORD),
        division_id=division.id,
        frac_role_id=frac_role.id,
        service_years=service_years,
        baseline_wpm=round(RNG.uniform(118, 165), 1),
        baseline_filler_rate=round(RNG.uniform(1.4, 4.8), 2),
    )


def seed(total_officers: int = 200) -> None:
    print("Resetting schema...")
    reset_schema()
    db: Session = SessionLocal()

    try:

        print("Building FRAC framework...")
        divisions, roles, competencies = build_framework(db)
        comp_ids = [c.id for c in competencies.values()]

        print("Loading interview question bank...")
        question_count = seed_questions(db, competencies)

        print("Importing the course catalogue...")
        catalogue = sync_catalogue(db)
        embedded = embed_catalogue(db)
        db.commit()

        # ------------------------------------------------------------------ #
        # Named demo accounts. The learner is the officer in the mockups: a
        # Deputy Director in ESD with a critical GIS gap, which is what the
        # end-to-end demo narrative hangs on.
        # ------------------------------------------------------------------ #
        print("Creating demo accounts...")
        demo_users = [
            make_user("venkatesan@sankhya.gov.in", "A. Venkatesan", UserRole.LEARNER,
                      divisions["ESD"], roles["DD"], 14.5),
            make_user("director.esd@sankhya.gov.in", "S. Raghavan", UserRole.SUPERVISOR,
                      divisions["ESD"], roles["DIR"], 26.0),
            make_user("sme@sankhya.gov.in", "P. Lakshmi", UserRole.SME,
                      divisions["NSSTA"], roles["JD"], 20.0),
            make_user("admin@sankhya.gov.in", "MoSPI Administrator", UserRole.ADMIN,
                      divisions["DIID"], roles["DIR"], 22.0),
        ]
        for u in demo_users:
            db.add(u)
        db.flush()

        venkatesan = demo_users[0]

        # Hand-set latent abilities so the demo story is stable: strong on
        # statistical method, weak on GIS and on the behavioural domain.
        scripted = {
            "STAT-SAMP": 4.2, "STAT-EST": 4.0, "STAT-NAS": 3.6, "STAT-INDEX": 3.7,
            "TECH-ANL": 2.6, "TECH-GIS": 1.8, "TECH-BIG": 2.9, "TECH-VIZ": 3.4,
            "DG-QUAL": 3.1, "DG-PRIV": 3.3,
            "BEH-COMM": 3.0, "BEH-LEAD": 2.4,
        }
        venkatesan_latent = {
            competencies[code].id: level for code, level in scripted.items()
        }
        generate_scripted_evidence(db, venkatesan, venkatesan_latent)

        # An inflated self-rating on exactly the weakest competency, so the
        # divergence flag has something real to find.
        db.add(
            ProficiencyEvidence(
                user_id=venkatesan.id,
                competency_id=competencies["TECH-GIS"].id,
                level_estimate=4.0,
                confidence=1.0,
                source=EvidenceSource.SELF,
                source_ref="onboarding-self-assessment",
                created_at=NOW - timedelta(days=45),
            )
        )

        for u in demo_users[1:]:
            latent = {cid: _latent_ability(u.frac_role.level_order) for cid in comp_ids}
            generate_evidence(db, u, latent)

        db.flush()

        # ------------------------------------------------------------------ #
        # Population
        # ------------------------------------------------------------------ #
        print(f"Generating {total_officers} officers...")
        division_list = list(divisions.values())
        role_list = list(roles.values())
        role_distribution = [
            roles["JSO"], roles["JSO"], roles["JSO"],
            roles["SSO"], roles["SSO"],
            roles["AD"], roles["AD"],
            roles["DD"],
            roles["JD"],
            roles["DIR"],
        ]

        used_emails = {u.email for u in demo_users}
        total_evidence = 0

        for i in range(total_officers):
            first = RNG.choice(FIRST_NAMES)
            last = RNG.choice(LAST_NAMES)
            name = f"{first} {last}"
            email = f"{first.lower()}.{last.lower()}{i}@sankhya.gov.in"
            if email in used_emails:
                continue
            used_emails.add(email)

            frac_role = RNG.choice(role_distribution)
            division = RNG.choice(division_list)
            service = round(
                frac_role.min_service_years + RNG.uniform(0.5, 6.0), 1
            )

            # Roughly one supervisor per twelve officers.
            user_role = UserRole.SUPERVISOR if (
                frac_role.level_order >= 5 and RNG.random() < 0.4
            ) else UserRole.LEARNER

            u = make_user(email, name, user_role, division, frac_role, service)
            # A small share of officers have fluency scoring switched off. This is
            # a first-class accommodation, not an edge case.
            if RNG.random() < 0.04:
                u.fluency_scoring_enabled = False

            db.add(u)
            db.flush()

            latent = {cid: _latent_ability(frac_role.level_order) for cid in comp_ids}
            total_evidence += generate_evidence(db, u, latent)

            if (i + 1) % 50 == 0:
                db.commit()
                print(f"  ...{i + 1} officers")

        db.commit()

        # ------------------------------------------------------------------ #
        # Course history. Without it the peer signal is always zero and every
        # recommendation looks identical, which hides half the ranking model.
        print("Generating course completion history...")
        courses = list(db.scalars(select(Course)).all())
        completions = 0
        for user in db.scalars(select(User)).all():
            for course in RNG.sample(courses, RNG.randint(1, 6)):
                db.add(CourseCompletion(
                    user_id=user.id,
                    course_id=course.id,
                    level_at_completion=round(RNG.uniform(1.5, 4.0), 2),
                    # Kept inside the evidence history so both the before and
                    # after windows have something in them. A completion older
                    # than the evidence itself is unmeasurable, and a catalogue
                    # where nothing is measurable makes course efficacy look
                    # broken rather than unpopulated.
                    completed_at=NOW - timedelta(days=RNG.randint(100, 260)),
                ))
                completions += 1
        db.commit()

        print("Deriving Digital Skill Twins from evidence...")
        all_user_ids = [u.id for u in db.scalars(select(User)).all()]
        for idx, uid in enumerate(all_user_ids, 1):
            recompute_profile(db, user_id=uid)
            if idx % 50 == 0:
                db.commit()
        db.commit()

        evidence_total = db.scalar(
            select(ProficiencyEvidence.id).order_by(ProficiencyEvidence.id.desc()).limit(1)
        )

        print("\n" + "=" * 62)
        print("  Seed complete")
        print("=" * 62)
        print(f"  Officers          {len(all_user_ids)}")
        print(f"  Divisions         {len(DIVISIONS)} across 5 states")
        print(f"  FRAC roles        {len(FRAC_ROLES)}")
        print(f"  Competencies      {len(COMPETENCIES)} over 4 domains")
        print(f"  Interview bank    {question_count} questions + 1 calibration")
        print(f"  Course catalogue  {catalogue['total']} courses, {embedded} embedded")
        print(f"  Completions       {completions}")
        print(f"  Evidence rows     ~{evidence_total}")
        print("\n  Demo accounts — password for all: " + DEMO_PASSWORD)
        for u in demo_users:
            print(f"    {u.role.value:<11} {u.email}")
        print("\n  Start here: venkatesan@sankhya.gov.in has a critical GIS gap")
        print("  and an inflated self-rating on the same competency.")
        print("=" * 62)

    finally:
        db.close()


if __name__ == "__main__":
    seed()
