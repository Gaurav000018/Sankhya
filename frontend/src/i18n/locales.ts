/**
 * Interface strings, English and Hindi.
 *
 * Hand-written rather than machine-translated, using the vocabulary the Official
 * Statistical System actually uses (सांख्यिकी, अभिलेख, दक्षता). **Every Hindi
 * string here still needs review by a Hindi-speaking officer before this goes
 * anywhere near a real deployment** — a government interface that reads as
 * translated is worse than one that stays in English, and `scripts/check_i18n.py`
 * reports coverage so the gap is visible rather than assumed closed.
 *
 * Missing keys fall back to English rather than rendering the key itself. A
 * user seeing `nav.dashboard` learns nothing; seeing "Dashboard" at least works.
 */

export const LOCALES = ["en", "hi"] as const;
export type Locale = (typeof LOCALES)[number];

export const LOCALE_NAMES: Record<Locale, string> = {
  en: "English",
  hi: "हिन्दी",
};

const en = {
  // Navigation and chrome
  "nav.dashboard": "Dashboard",
  "nav.learning": "Learning",
  "nav.promotion": "Promotion",
  "nav.team": "Team",
  "nav.review": "Review queue",
  "nav.workforce": "Workforce",
  "nav.capacityPlan": "Capacity plan",
  "nav.quiz": "Assessment",
  "nav.interview": "Interview",
  "nav.settings": "Settings",
  "nav.primary": "Primary",
  "nav.signOut": "Sign out",
  "nav.skipToContent": "Skip to main content",
  "nav.language": "Language",

  "role.learner": "Officer",
  "role.supervisor": "Supervisor",
  "role.sme": "Subject expert",
  "role.admin": "Administrator",

  // Document titles (WCAG 2.4.2) — translated too, or a Hindi speaker gets a
  // Hindi page in an English tab.
  "title.dashboard": "Dashboard",
  "title.learning": "Development plan",
  "title.promotion": "Promotion outlook",
  "title.team": "Team readiness",
  "title.review": "Review queue",
  "title.workforce": "Workforce intelligence",
  "title.capacityPlan": "Capacity building plan",
  "title.quiz": "Assessment",
  "title.interview": "AI interview",
  "title.settings": "Settings",
  "title.signIn": "Sign in",
  "title.noAccess": "No access",

  // Shared states
  "common.loading": "Loading",
  "common.records": "records",
  "common.of": "of",
  "common.assessed": "Assessed level",
  "common.roleRequirement": "Role requirement",
  "common.thinEvidence": "Thin evidence",
  "common.noAccessTitle": "No access",
  "common.noAccessSubtitle": "Your role does not have permission to open this page",
  "common.noAccessBody": "If you believe you should have access, ask your division administrator.",

  // Gap status
  "status.critical": "Critical gap",
  "status.at_risk": "At risk",
  "status.near_target": "Near target",
  "status.met": "Met",

  // Sign in
  "login.heading": "Workforce competency intelligence",
  "login.intro":
    "For officers of India's Official Statistical System. Competency here is derived from evidence, not declared.",
  "login.method.password": "Password",
  "login.method.otp": "Email code",
  "login.method.totp": "Authenticator",
  "login.email": "Official email",
  "login.password": "Password",
  "login.submit": "Sign in",
  "login.submitting": "Signing in…",
  "login.sendCode": "Send a code",
  "login.sending": "Sending…",
  "login.code": "Six-digit code",
  "login.codeFromApp": "Code from your authenticator app",
  "login.verify": "Verify and sign in",
  "login.methodNote.otp": "A code is sent to your official address.",
  "login.methodNote.totp":
    "Generated on your device. Works with no network connection.",
  "login.parichay":
    "In production this authenticates against Parichay, the Government of India single sign-on. These methods are the interim path.",

  // Officer dashboard
  "dashboard.roleReadiness": "Role readiness",
  "dashboard.roleReadinessNote":
    "Weighted by how critical each competency is to your role",
  "dashboard.atTarget": "At target level",
  "dashboard.competencies": "competencies",
  "dashboard.noCriticalGaps": "No critical gaps",
  "dashboard.criticalGapsCount": "{count} critical",
  "dashboard.evidenceRecords": "Evidence records",
  "dashboard.evidenceNote": "Every level traces back to these",
  "dashboard.strongestArea": "Strongest area",
  "dashboard.competencyProfile": "Competency profile",
  "dashboard.frcScale": "FRAC proficiency L1–L5",
  "dashboard.gaps": "Competency gaps",
  "dashboard.gapsHint": "Ranked by size, then by criticality to your role",
  "dashboard.allMet": "Every competency meets its requirement for this role.",
  "dashboard.promotionReadiness": "Promotion readiness",
  "dashboard.promotionHint":
    "The same gap engine, run against a role you are aiming for",
  "dashboard.evidenceTimeline": "Evidence timeline",
  "dashboard.evidenceTimelineHint": "Append-only — nothing here is ever overwritten",
  "dashboard.serviceRequirement": "Service requirement",
  "dashboard.eligibility": "Eligibility",
  "dashboard.eligible": "Service requirement met",
  "dashboard.notEligible": "Service requirement not yet met",
  "dashboard.report": "Evidence report (PDF)",
  "dashboard.reportGenerating": "Generating…",
  "dashboard.years": "years of service",

  // Evidence sources
  "source.simulation": "Simulation on live data",
  "source.quiz": "Quiz",
  "source.diagnostic": "Adaptive diagnostic",
  "source.interview": "AI interview",
  "source.certification": "Certification",
  "source.supervisor": "Supervisor rating",
  "source.learning_activity": "Course completion",
  "source.historical": "Service record",
  "source.self": "Self-assessment",
} as const;

export type MessageKey = keyof typeof en;

/**
 * Hindi. Deliberately incomplete where a confident translation was not
 * available — a wrong term in a statistical context is worse than the English
 * one, and the coverage report makes the gap visible.
 */
const hi: Partial<Record<MessageKey, string>> = {
  "nav.dashboard": "डैशबोर्ड",
  "nav.learning": "अधिगम",
  "nav.promotion": "पदोन्नति",
  "nav.team": "दल",
  "nav.review": "समीक्षा सूची",
  "nav.workforce": "कार्यबल",
  "nav.capacityPlan": "क्षमता योजना",
  "nav.quiz": "मूल्यांकन",
  "nav.interview": "साक्षात्कार",
  "nav.settings": "सेटिंग्स",
  "nav.primary": "मुख्य",
  "nav.signOut": "साइन आउट",
  "nav.skipToContent": "मुख्य सामग्री पर जाएँ",
  "nav.language": "भाषा",

  "role.learner": "अधिकारी",
  "role.supervisor": "पर्यवेक्षक",
  "role.sme": "विषय विशेषज्ञ",
  "role.admin": "प्रशासक",

  "title.dashboard": "डैशबोर्ड",
  "title.learning": "विकास योजना",
  "title.promotion": "पदोन्नति संभावना",
  "title.team": "दल की तत्परता",
  "title.review": "समीक्षा सूची",
  "title.workforce": "कार्यबल आसूचना",
  "title.capacityPlan": "क्षमता निर्माण योजना",
  "title.quiz": "मूल्यांकन",
  "title.interview": "एआई साक्षात्कार",
  "title.settings": "सेटिंग्स",
  "title.signIn": "साइन इन",
  "title.noAccess": "पहुँच नहीं",

  "common.loading": "लोड हो रहा है",
  "common.records": "अभिलेख",
  "common.of": "में से",
  "common.assessed": "आकलित स्तर",
  "common.roleRequirement": "पद की अपेक्षा",
  "common.thinEvidence": "अपर्याप्त साक्ष्य",
  "common.noAccessTitle": "पहुँच नहीं",
  "common.noAccessSubtitle": "आपकी भूमिका को यह पृष्ठ खोलने की अनुमति नहीं है",
  "common.noAccessBody":
    "यदि आपको पहुँच मिलनी चाहिए, तो अपने प्रभाग प्रशासक से संपर्क करें।",

  "status.critical": "गंभीर अंतर",
  "status.at_risk": "जोखिम में",
  "status.near_target": "लक्ष्य के निकट",
  "status.met": "पूर्ण",

  "login.heading": "कार्यबल दक्षता आसूचना",
  "login.intro":
    "भारत की राष्ट्रीय सांख्यिकी प्रणाली के अधिकारियों के लिए। यहाँ दक्षता साक्ष्य से निकाली जाती है, घोषित नहीं की जाती।",
  "login.method.password": "पासवर्ड",
  "login.method.otp": "ईमेल कोड",
  "login.method.totp": "प्रमाणक ऐप",
  "login.email": "कार्यालयी ईमेल",
  "login.password": "पासवर्ड",
  "login.submit": "साइन इन करें",
  "login.submitting": "साइन इन हो रहा है…",
  "login.sendCode": "कोड भेजें",
  "login.sending": "भेजा जा रहा है…",
  "login.code": "छह अंकों का कोड",
  "login.codeFromApp": "अपने प्रमाणक ऐप से कोड",
  "login.verify": "सत्यापित कर साइन इन करें",
  "login.methodNote.otp": "आपके कार्यालयी पते पर एक कोड भेजा जाता है।",
  "login.methodNote.totp":
    "आपके उपकरण पर बनता है। बिना नेटवर्क के भी काम करता है।",
  "login.parichay":
    "उत्पादन परिवेश में प्रमाणीकरण परिचय (भारत सरकार सिंगल साइन-ऑन) से होगा। ये विधियाँ अंतरिम व्यवस्था हैं।",

  "dashboard.roleReadiness": "पद हेतु तत्परता",
  "dashboard.roleReadinessNote":
    "आपके पद के लिए प्रत्येक दक्षता की महत्ता के अनुसार भारित",
  "dashboard.atTarget": "लक्ष्य स्तर पर",
  "dashboard.competencies": "दक्षताएँ",
  "dashboard.noCriticalGaps": "कोई गंभीर अंतर नहीं",
  "dashboard.criticalGapsCount": "{count} गंभीर",
  "dashboard.evidenceRecords": "साक्ष्य अभिलेख",
  "dashboard.evidenceNote": "प्रत्येक स्तर इन्हीं से निकाला गया है",
  "dashboard.strongestArea": "सबसे सशक्त क्षेत्र",
  "dashboard.competencyProfile": "दक्षता प्रोफ़ाइल",
  "dashboard.frcScale": "FRAC प्रवीणता स्तर L1–L5",
  "dashboard.gaps": "दक्षता अंतर",
  "dashboard.gapsHint": "अंतर के आकार और पद के लिए महत्ता के क्रम में",
  "dashboard.allMet": "इस पद की सभी दक्षता अपेक्षाएँ पूरी हैं।",
  "dashboard.promotionReadiness": "पदोन्नति तत्परता",
  "dashboard.promotionHint":
    "वही अंतर विश्लेषण, आपके लक्षित पद के विरुद्ध",
  "dashboard.evidenceTimeline": "साक्ष्य कालक्रम",
  "dashboard.evidenceTimelineHint":
    "केवल जोड़ा जाता है — यहाँ कुछ भी अधिलेखित नहीं होता",
  "dashboard.serviceRequirement": "सेवा अपेक्षा",
  "dashboard.eligibility": "पात्रता",
  "dashboard.eligible": "सेवा अपेक्षा पूर्ण",
  "dashboard.notEligible": "सेवा अपेक्षा अभी पूर्ण नहीं",
  "dashboard.report": "साक्ष्य रिपोर्ट (PDF)",
  "dashboard.reportGenerating": "तैयार हो रही है…",
  "dashboard.years": "वर्ष की सेवा",

  "source.simulation": "वास्तविक आँकड़ों पर अनुरूपण",
  "source.quiz": "प्रश्नोत्तरी",
  "source.diagnostic": "अनुकूली निदान",
  "source.interview": "एआई साक्षात्कार",
  "source.certification": "प्रमाणन",
  "source.supervisor": "पर्यवेक्षक आकलन",
  "source.learning_activity": "पाठ्यक्रम पूर्णता",
  "source.historical": "सेवा अभिलेख",
  "source.self": "स्व-आकलन",
};

export const MESSAGES: Record<Locale, Partial<Record<MessageKey, string>>> = {
  en,
  hi,
};

export const FALLBACK_LOCALE: Locale = "en";
