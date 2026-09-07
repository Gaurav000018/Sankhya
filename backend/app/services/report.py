"""Competency Evidence Report.

A signable document an officer can carry to a review, a DPC, or a new posting.
Government runs on documents, and a dashboard that cannot be printed and signed
does not travel.

Two things this is careful not to overclaim:

* **It is not digitally signed.** There is no PKI here. What it carries is a
  verification hash over the underlying figures, so a reviewer can confirm the
  document matches the record, plus a signature block for a human to sign. The
  document says exactly that rather than implying a cryptographic signature.
* **It reproduces the caveats.** The delivery axes are excluded from competency,
  self-assessment carries low weight, evidence decays. A printed extract that
  drops the caveats is how a nuanced number becomes a blunt one in a meeting.
"""

from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Competency, ProficiencyEvidence, User
from app.services.competency import analyse_gaps, role_readiness
from app.services.lift import officer_lift

INK = colors.HexColor("#14181f")
INK_2 = colors.HexColor("#4d5563")
INK_3 = colors.HexColor("#7c8494")
RULE = colors.HexColor("#c8cdd6")
BRASS = colors.HexColor("#8a6614")
CRITICAL = colors.HexColor("#9c3f36")
WARN = colors.HexColor("#a06a2c")
GOOD = colors.HexColor("#2c6b48")

STATUS_COLOUR = {
    "critical": CRITICAL, "at_risk": WARN, "near_target": INK_2, "met": GOOD,
}
STATUS_LABEL = {
    "critical": "Critical gap", "at_risk": "At risk",
    "near_target": "Near target", "met": "Met",
}

SOURCE_LABELS = {
    "simulation": "Simulation", "quiz": "Quiz", "diagnostic": "Diagnostic",
    "interview": "AI interview", "certification": "Certification",
    "supervisor": "Supervisor", "learning_activity": "Course completion",
    "historical": "Service record", "self": "Self-assessment",
}

MAX_EVIDENCE_ROWS = 18


def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"], fontName="Times-Bold", fontSize=17,
            textColor=INK, alignment=TA_LEFT, spaceAfter=2, leading=20,
        ),
        "eyebrow": ParagraphStyle(
            "eyebrow", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=7.5,
            textColor=BRASS, spaceAfter=6, leading=10,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName="Times-Bold", fontSize=11.5,
            textColor=INK, spaceBefore=14, spaceAfter=5, leading=14,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontName="Helvetica", fontSize=8.5,
            textColor=INK_2, leading=12,
        ),
        "small": ParagraphStyle(
            "small", parent=base["Normal"], fontName="Helvetica", fontSize=7,
            textColor=INK_3, leading=9.5,
        ),
        "cell": ParagraphStyle(
            "cell", parent=base["Normal"], fontName="Helvetica", fontSize=8,
            textColor=INK, leading=10,
        ),
    }


def _table(data: list[list], widths: list[float], extra: list | None = None) -> Table:
    table = Table(data, colWidths=widths, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 6.8),
        ("TEXTCOLOR", (0, 0), (-1, 0), INK_3),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("TEXTCOLOR", (0, 1), (-1, -1), INK),
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, INK_3),
        ("LINEBELOW", (0, 1), (-1, -2), 0.25, RULE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
    ] + (extra or [])))
    return table


def collect_report_data(db: Session, user: User, window_days: int = 180) -> dict:
    """Everything the document states, in one structure.

    Kept separate from rendering so the verification hash is taken over the
    figures rather than over PDF bytes, which change with the timestamp.
    """
    gaps = analyse_gaps(db, user=user)
    evidence = db.scalars(
        select(ProficiencyEvidence)
        .where(ProficiencyEvidence.user_id == user.id)
        .order_by(ProficiencyEvidence.created_at.desc())
    ).all()
    competencies = {c.id: c.name for c in db.scalars(select(Competency)).all()}

    return {
        "officer": {
            "name": user.full_name,
            "email": user.email,
            "role": user.frac_role.name if user.frac_role else None,
            "grade": user.frac_role.grade if user.frac_role else None,
            "division": user.division.name if user.division else None,
            "service_years": user.service_years,
        },
        "readiness": role_readiness(db, user=user),
        "competencies": [
            {
                "name": g.competency_name, "code": g.competency_code,
                "current": g.current_level, "required": g.required_level,
                "status": g.status, "evidence_count": g.evidence_count,
                "strongest_source": g.strongest_source,
            }
            for g in gaps
        ],
        "lift": [
            {"name": item.competency_name, "then": item.level_then,
             "now": item.level_now, "change": item.change,
             "direction": item.direction}
            for item in officer_lift(db, user=user, days=window_days)
        ],
        "evidence": [
            {
                "competency": competencies.get(e.competency_id, ""),
                "level": e.level_estimate, "confidence": e.confidence,
                "source": e.source.value,
                "date": e.created_at.strftime("%d %b %Y"),
            }
            for e in evidence[:MAX_EVIDENCE_ROWS]
        ],
        "evidence_total": len(evidence),
        "window_days": window_days,
    }


def verification_hash(data: dict) -> str:
    """SHA-256 over the figures the document states.

    Lets a reviewer confirm a printed copy matches the record. It is not a
    signature and does not prove who produced it — the document says so.
    """
    payload = json.dumps(data, sort_keys=True, default=str).encode()
    return hashlib.sha256(payload).hexdigest()


def render_pdf(db: Session, user: User, window_days: int = 180) -> tuple[bytes, str]:
    """Returns (pdf_bytes, verification_hash)."""
    data = collect_report_data(db, user, window_days=window_days)
    digest = verification_hash(data)
    generated = datetime.now(timezone.utc)
    reference = f"SNK/CER/{user.id:05d}/{generated:%Y%m%d}"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title=f"Competency Evidence Report — {data['officer']['name']}",
        author="SANKHYA",
    )
    s = _styles()
    story: list = []

    story.append(Paragraph(
        "MINISTRY OF STATISTICS AND PROGRAMME IMPLEMENTATION &nbsp;·&nbsp; SANKHYA",
        s["eyebrow"],
    ))
    story.append(Paragraph("Competency Evidence Report", s["title"]))
    story.append(Paragraph(
        f"Reference {reference} &nbsp;·&nbsp; generated {generated:%d %B %Y, %H:%M} UTC",
        s["small"],
    ))
    story.append(Spacer(1, 7))
    story.append(HRFlowable(width="100%", thickness=1.1, color=INK, spaceAfter=10))

    officer = data["officer"]
    story.append(_table(
        [
            ["OFFICER", "ROLE", "DIVISION", "SERVICE", "ROLE READINESS"],
            [
                Paragraph(officer["name"], s["cell"]),
                Paragraph(officer["role"] or "—", s["cell"]),
                Paragraph(officer["division"] or "—", s["cell"]),
                f"{officer['service_years']} yrs",
                f"{data['readiness']}%",
            ],
        ],
        [46 * mm, 40 * mm, 44 * mm, 18 * mm, 26 * mm],
    ))

    # ---------------------------------------------------------------- profile
    story.append(Paragraph("Assessed competency profile", s["h2"]))
    story.append(Paragraph(
        "Levels are derived from recorded evidence, not self-declared. Each is "
        "measured against the requirement of the role this officer holds.",
        s["small"],
    ))
    story.append(Spacer(1, 5))

    rows = [["COMPETENCY", "ASSESSED", "REQUIRED", "STATUS", "RECORDS", "STRONGEST SOURCE"]]
    styling = []
    for index, item in enumerate(data["competencies"], start=1):
        rows.append([
            Paragraph(item["name"], s["cell"]),
            f"L{item['current']:.2f}", f"L{item['required']:.2f}",
            STATUS_LABEL.get(item["status"], item["status"]),
            str(item["evidence_count"]),
            SOURCE_LABELS.get(item["strongest_source"] or "", "—"),
        ])
        styling.append(
            ("TEXTCOLOR", (3, index), (3, index),
             STATUS_COLOUR.get(item["status"], INK_2))
        )
    story.append(_table(
        rows, [58 * mm, 18 * mm, 18 * mm, 24 * mm, 16 * mm, 40 * mm], styling
    ))

    # ------------------------------------------------------------------- lift
    material = [item for item in data["lift"] if abs(item["change"]) >= 0.15]
    if material:
        story.append(Paragraph(
            f"Movement over the last {data['window_days']} days", s["h2"]
        ))
        story.append(Paragraph(
            "Each level is recomputed from the evidence that existed at that date. "
            "A decline generally reflects evidence ageing rather than loss of skill.",
            s["small"],
        ))
        story.append(Spacer(1, 5))

        rows = [["COMPETENCY", "THEN", "NOW", "CHANGE", ""]]
        styling = []
        for index, item in enumerate(material[:8], start=1):
            rows.append([
                Paragraph(item["name"], s["cell"]),
                f"L{item['then']:.2f}", f"L{item['now']:.2f}",
                f"{item['change']:+.2f}", item["direction"],
            ])
            styling.append((
                "TEXTCOLOR", (3, index), (4, index),
                GOOD if item["change"] > 0 else CRITICAL,
            ))
        story.append(_table(
            rows, [58 * mm, 20 * mm, 20 * mm, 22 * mm, 30 * mm], styling
        ))

    # --------------------------------------------------------------- evidence
    story.append(Paragraph("Evidence trail", s["h2"]))
    story.append(Paragraph(
        f"Most recent {len(data['evidence'])} of {data['evidence_total']} records. "
        "The record is append-only: corrections are new entries, never edits.",
        s["small"],
    ))
    story.append(Spacer(1, 5))

    rows = [["DATE", "COMPETENCY", "SOURCE", "LEVEL", "CONFIDENCE"]]
    for item in data["evidence"]:
        rows.append([
            item["date"],
            Paragraph(item["competency"], s["cell"]),
            SOURCE_LABELS.get(item["source"], item["source"]),
            f"L{item['level']:.2f}",
            f"{item['confidence']:.2f}",
        ])
    story.append(_table(
        rows, [24 * mm, 56 * mm, 34 * mm, 18 * mm, 22 * mm]
    ))

    # ------------------------------------------------------- caveats and sign
    story.append(Paragraph("How to read this document", s["h2"]))
    for line in (
        "Competency is derived from multiple sources weighted by reliability. "
        "Demonstrated work on real tasks carries the most weight; course completion "
        "and self-assessment carry the least. Evidence decays with a 365-day "
        "half-life, so a level not refreshed will fall.",
        "The AI interview contributes only its Knowledge axis. Communication "
        "delivery and assurance are recorded as coaching feedback and are "
        "deliberately excluded from competency and from promotion readiness.",
        "This report is indicative and is not by itself a basis for any personnel "
        "decision.",
    ):
        story.append(Paragraph(line, s["body"]))
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 6))
    story.append(KeepTogether([
        HRFlowable(width="100%", thickness=0.6, color=RULE, spaceAfter=8),
        _table(
            [
                ["VERIFICATION HASH (SHA-256)", "COUNTERSIGNED BY"],
                [
                    Paragraph(
                        f"<font face='Courier' size='6.5'>{digest}</font><br/>"
                        "<font size='6.5' color='#7c8494'>Confirms this printout matches "
                        "the record. Not a digital signature.</font>",
                        s["small"],
                    ),
                    Paragraph(
                        "<br/><br/>_______________________________<br/>"
                        "<font size='6.5' color='#7c8494'>Name, designation and date</font>",
                        s["small"],
                    ),
                ],
            ],
            [104 * mm, 70 * mm],
        ),
    ]))

    doc.build(story)
    return buffer.getvalue(), digest
