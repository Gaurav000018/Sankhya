import { useEffect, useState } from "react";

import { ApiError, api } from "../api";
import { PageHeader } from "../components/Layout";
import { Card, Empty, ErrorNote, Note, Spinner, StatTile } from "../components/ui";
import type { Competency, Question, QuestionSource } from "../types";
import { usePageTitle } from "../hooks/usePageTitle";

/**
 * SME review queue.
 *
 * Nothing generated reaches an officer until a subject expert approves it here.
 * The cited passage is shown beside every question, and the citation is
 * re-verified live rather than trusted from generation time — so a reviewer can
 * see the evidence rather than take the model's word for it.
 */

export function ReviewQueue() {
  usePageTitle("title.review");

  const [questions, setQuestions] = useState<Question[]>([]);
  const [stats, setStats] = useState<Record<string, number>>({});
  const [selected, setSelected] = useState<Question | null>(null);
  const [source, setSource] = useState<QuestionSource | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [competencies, setCompetencies] = useState<Competency[]>([]);
  const [uploadCompetency, setUploadCompetency] = useState<number | "">("");
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadNote, setUploadNote] = useState<string | null>(null);

  async function load() {
    const [queue, s] = await Promise.all([
      api.get<Question[]>("/questions/review-queue"),
      api.get<{ by_status: Record<string, number> }>("/questions"),
    ]);
    setQuestions(queue);
    setStats(s.by_status);
    setSelected((current) => queue.find((q) => q.id === current?.id) ?? queue[0] ?? null);
  }

  useEffect(() => {
    api.get<Competency[]>("/frac/competencies").then(setCompetencies).catch(() => {});
  }, []);

  useEffect(() => {
    load()
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load the queue."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selected) {
      setSource(null);
      return;
    }
    setSource(null);
    api
      .get<QuestionSource>(`/questions/${selected.id}/source`)
      .then(setSource)
      .catch(() => setSource(null));
  }, [selected]);

  async function upload() {
    if (!uploadFile || !uploadTitle.trim() || uploadCompetency === "") return;
    setBusy(true);
    setError(null);
    try {
      const material = await api.uploadMaterial(
        uploadFile,
        uploadTitle.trim(),
        Number(uploadCompetency),
      );
      await api.post(`/materials/${material.id}/generate`, {
        per_chunk: 2,
        bloom_level: "apply",
      });
      setUploadNote(
        `"${material.title}" split into ${material.chunk_count} passages. ` +
          "Questions are being generated and will appear below for review. " +
          "Anything whose citation does not verify is discarded before it reaches you.",
      );
      setUploadTitle("");
      setUploadFile(null);
      setTimeout(() => void load(), 4000);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not upload that file.");
    } finally {
      setBusy(false);
    }
  }

  async function decide(action: "approve" | "reject") {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      await api.post(`/questions/${selected.id}/${action}`, { note: note || null });
      setNote("");
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not record that decision.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <Spinner label="Loading the review queue" />;

  return (
    <>
      <PageHeader
        title="Review queue"
        subtitle="Generated questions awaiting subject-expert approval"
        meta="Nothing here has been seen by an officer"
      />

      <div className="mb-4 grid gap-3.5 sm:grid-cols-4">
        <StatTile label="Awaiting review" value={stats.draft ?? 0} />
        <StatTile label="Approved" value={stats.approved ?? 0} note="In use with officers" />
        <StatTile label="Rejected" value={stats.rejected ?? 0} />
        <StatTile label="Retired" value={stats.retired ?? 0} note="Withdrawn on psychometric grounds" />
      </div>

      {error && (
        <div className="mb-4">
          <ErrorNote message={error} />
        </div>
      )}

      <div className="mb-4">
        <Card
          title="Add learning material"
          hint="Questions are generated from its passages and queued below for your review"
        >
          {uploadNote && (
            <div className="mb-3">
              <Note>{uploadNote}</Note>
            </div>
          )}
          <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_220px_auto] sm:items-end">
            <div>
              <label
                htmlFor="material-title"
                className="block text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3"
              >
                Title
              </label>
              <input
                id="material-title"
                value={uploadTitle}
                onChange={(e) => setUploadTitle(e.target.value)}
                placeholder="Weighting and non-response, NSS training note"
                className="mt-1.5 w-full border border-rule-strong bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
              />
            </div>
            <div>
              <label
                htmlFor="material-competency"
                className="block text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3"
              >
                Competency
              </label>
              <select
                id="material-competency"
                value={uploadCompetency}
                onChange={(e) =>
                  setUploadCompetency(e.target.value ? Number(e.target.value) : "")
                }
                className="mt-1.5 w-full border border-rule-strong bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
              >
                <option value="">Choose...</option>
                {competencies.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label
                htmlFor="material-file"
                className="block text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3"
              >
                File
              </label>
              <input
                id="material-file"
                type="file"
                accept=".pdf,.docx,.pptx,.txt,.md"
                onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
                className="mt-1.5 w-full text-[12px] text-ink-2 file:mr-2 file:border file:border-rule-strong file:bg-surface file:px-2.5 file:py-1 file:text-[12px] file:text-ink-2"
              />
            </div>
          </div>
          <button
            disabled={busy || !uploadFile || !uploadTitle.trim() || uploadCompetency === ""}
            onClick={upload}
            className="mt-3 bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "Uploading..." : "Upload and generate"}
          </button>
          <p className="mt-2.5 text-[11.5px] leading-relaxed text-ink-3">
            A competency is required: questions inherit it, and one without a
            competency could never become evidence. PDF, DOCX, PPTX, TXT and MD.
          </p>
        </Card>
      </div>

      {questions.length === 0 ? (
        <Empty>
          Nothing awaiting review. Upload learning material and generate questions to fill
          the queue.
        </Empty>
      ) : (
        <div className="grid gap-3.5 lg:grid-cols-[320px_minmax(0,1fr)]">
          <Card title={`Queue (${questions.length})`} hint="Flagged items first">
            <div className="-mx-5 -my-5 divide-y divide-rule">
              {questions.map((q) => (
                <button
                  key={q.id}
                  onClick={() => setSelected(q)}
                  className={`block w-full px-5 py-3 text-left transition-colors hover:bg-surface-2 ${
                    selected?.id === q.id ? "bg-surface-2 shadow-[inset_2px_0_0_var(--color-accent)]" : ""
                  }`}
                >
                  <div className="line-clamp-2 text-[12.5px] leading-snug">{q.stem}</div>
                  <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[11px] text-ink-3">
                    <span className="font-mono">#{q.id}</span>
                    <span>{q.bloom_level}</span>
                    {q.quality_flags.length > 0 && (
                      <span className="font-semibold text-warn">
                        {q.quality_flags.length} flag{q.quality_flags.length > 1 ? "s" : ""}
                      </span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </Card>

          {selected && (
            <div className="grid gap-3.5">
              <Card
                title="Question"
                hint={`Generated by ${selected.generated_by_model ?? "unknown model"} · Bloom level: ${selected.bloom_level}`}
              >
                <p className="text-[15px] leading-relaxed">{selected.stem}</p>

                <ul className="mt-4 space-y-1.5">
                  {selected.options.map((option, index) => (
                    <li
                      key={index}
                      className={`flex gap-3 border px-3 py-2 text-[13.5px] ${
                        index === selected.correct_index
                          ? "border-good bg-[#f2f7f4]"
                          : "border-rule"
                      }`}
                    >
                      <span className="font-mono text-[11.5px] text-ink-3">
                        {String.fromCharCode(65 + index)}
                      </span>
                      <span className="flex-1">{option}</span>
                      {index === selected.correct_index && (
                        <span className="text-[10.5px] font-semibold uppercase tracking-[0.05em] text-good">
                          Correct
                        </span>
                      )}
                    </li>
                  ))}
                </ul>

                {selected.explanation && (
                  <div className="mt-4">
                    <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3">
                      Explanation
                    </div>
                    <p className="text-[13px] leading-relaxed text-ink-2">{selected.explanation}</p>
                  </div>
                )}

                {selected.quality_flags.length > 0 && (
                  <div className="mt-4">
                    <Note tone="brass">
                      <strong className="font-semibold text-ink">
                        Automated checks flagged this item.
                      </strong>
                      <ul className="mt-1.5 list-disc space-y-0.5 pl-5">
                        {selected.quality_flags.map((flag) => (
                          <li key={flag}>{flag}</li>
                        ))}
                      </ul>
                    </Note>
                  </div>
                )}
              </Card>

              <Card
                title="Citation"
                hint="Re-verified against the source now, not trusted from generation time"
              >
                {!source ? (
                  <Spinner label="Checking the source passage" />
                ) : (
                  <>
                    <div className="mb-3 flex flex-wrap items-center gap-3 text-[12px]">
                      <span
                        className={`font-semibold ${
                          source.citation_verified ? "text-good" : "text-critical"
                        }`}
                      >
                        {source.citation_verified ? "Citation verified" : "Citation does NOT verify"}
                      </span>
                      <span className="text-ink-3">{source.verification_detail}</span>
                      {source.page && (
                        <span className="font-mono text-[11.5px] text-ink-3">
                          {source.material_title} · page {source.page}
                        </span>
                      )}
                    </div>

                    <blockquote className="border-l-2 border-brass bg-[#f6f4ee] px-4 py-3 text-[13px] italic leading-relaxed text-ink-2">
                      “{source.quote}”
                    </blockquote>

                    <details className="mt-3">
                      <summary className="cursor-pointer text-[12.5px] text-accent">
                        Show the full passage
                      </summary>
                      <p className="mt-2 max-h-56 overflow-y-auto whitespace-pre-wrap border border-rule bg-surface-2 p-3 text-[12.5px] leading-relaxed text-ink-2">
                        {source.passage}
                      </p>
                    </details>
                  </>
                )}
              </Card>

              <Card title="Decision">
                <label
                  htmlFor="review-note"
                  className="block text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3"
                >
                  Reviewer note (recorded in the audit log)
                </label>
                <textarea
                  id="review-note"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={2}
                  placeholder="Checked against the source; terminology matches the manual."
                  className="mt-1.5 w-full border border-rule-strong bg-surface px-3 py-2 text-[13px] outline-none focus:border-accent"
                />
                <div className="mt-3 flex flex-wrap gap-2.5">
                  <button
                    disabled={busy || (source ? !source.citation_verified : false)}
                    onClick={() => decide("approve")}
                    className="bg-good px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40"
                  >
                    Approve for use
                  </button>
                  <button
                    disabled={busy}
                    onClick={() => decide("reject")}
                    className="border border-rule-strong px-4 py-2 text-sm text-ink-2 transition-colors hover:border-critical hover:text-critical disabled:opacity-40"
                  >
                    Reject
                  </button>
                  {source && !source.citation_verified && (
                    <span className="self-center text-[12px] text-critical">
                      Approval is blocked while the citation does not verify.
                    </span>
                  )}
                </div>
              </Card>
            </div>
          )}
        </div>
      )}
    </>
  );
}
