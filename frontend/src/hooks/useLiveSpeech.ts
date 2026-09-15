import { useCallback, useRef, useState } from "react";

import type { LiveSpeech } from "../types";

/**
 * Live speech analysis, in the browser, while the officer answers.
 *
 * Runs the same Vosk recogniser the worker uses — the Indian English model, not
 * a US one, because a US model reads ordinary Indian pronunciation as
 * hesitation and this is the one platform that must not make that mistake. The
 * model is packaged by `scripts/prepare_live_speech.py`.
 *
 * **Nothing is streamed anywhere.** Recognition happens on this machine, and
 * only the recorded answer goes to the server, exactly as before. Live analysis
 * adds no new path for audio to leave the browser.
 *
 * ## What this deliberately does not do
 *
 * It does not put a filler counter in front of someone mid-answer. Watching a
 * number climb while you explain stratified sampling consumes the working
 * memory the explanation needs, and this platform's own model says disfluency
 * tracks cognitive load rather than competence — so a live counter would punish
 * exactly the hard thinking the question is trying to provoke. What the officer
 * sees while speaking is calm: that they are being heard, and whether their
 * pace is in a comfortable band.
 *
 * The filler analysis lands the moment they stop, which is when it can be acted
 * on rather than fought.
 *
 * The figures here are indicative. The recorded answer is measured again
 * server-side under better conditions, and that pass is what the report and the
 * evidence are built from.
 */

const MODEL_URL = "/vosk/model.tar.gz";
const SAMPLE_RATE = 16000;

// Matches the server-side list in `services/interview_scoring.py`. Two lists
// that drift apart give an officer a live figure and a recorded figure that
// disagree for no reason they can see.
const FILLERS = new Set([
  "um", "uh", "erm", "hmm", "mmm", "eh", "ah", "er",
  "like", "basically", "actually", "literally", "sort", "kind",
  "yeah", "okay", "right",
]);

// Comfortable speaking range. Wide on purpose: outside it is worth mentioning
// afterwards, never worth flashing a warning about mid-sentence.
const PACE_LOW = 100;
const PACE_HIGH = 175;

// A gap this long reads as searching for the next thing rather than phrasing.
const LONG_PAUSE_SECONDS = 2.0;

interface Tracker {
  words: string[];
  fillerTimes: number[];
  lastWordAt: number;
  longPauses: number;
  startedAt: number;
}

function emptyTracker(): Tracker {
  return { words: [], fillerTimes: [], lastWordAt: 0, longPauses: 0, startedAt: 0 };
}

export function useLiveSpeech() {
  const [available, setAvailable] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);
  const [listening, setListening] = useState(false);
  const [live, setLive] = useState<LiveSpeech | null>(null);
  const [error, setError] = useState<string | null>(null);

  const modelRef = useRef<unknown>(null);
  const recognizerRef = useRef<unknown>(null);
  const contextRef = useRef<AudioContext | null>(null);
  const nodeRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const trackerRef = useRef<Tracker>(emptyTracker());

  const snapshot = useCallback((): LiveSpeech => {
    const tracker = trackerRef.current;
    const elapsed = tracker.startedAt
      ? (performance.now() - tracker.startedAt) / 1000
      : 0;
    const words = tracker.words.length;
    const wpm = elapsed > 3 ? Math.round((words / elapsed) * 60) : null;

    return {
      words,
      seconds: Number(elapsed.toFixed(1)),
      wpm,
      filler_count: tracker.fillerTimes.length,
      filler_rate: words >= 15
        ? Number(((tracker.fillerTimes.length / words) * 100).toFixed(1))
        : null,
      long_pauses: tracker.longPauses,
      pace: wpm === null ? "unknown" : wpm > PACE_HIGH ? "fast"
        : wpm < PACE_LOW ? "slow" : "steady",
      filler_times: [...tracker.fillerTimes],
    };
  }, []);

  /** Load the model. Large and slow, so this is called once, up front. */
  const load = useCallback(async () => {
    if (modelRef.current) {
      setAvailable(true);
      return true;
    }
    setLoading(true);
    try {
      const head = await fetch(MODEL_URL, { method: "HEAD" });
      if (!head.ok) throw new Error("model not packaged");

      const vosk = await import("vosk-browser");
      modelRef.current = await vosk.createModel(MODEL_URL);
      setAvailable(true);
      return true;
    } catch {
      // Not an error worth showing loudly: the interview is complete without
      // this, and the setup step that produces the model is optional.
      setAvailable(false);
      setError(
        "Live analysis is not set up on this machine. Run "
        + "`python scripts/prepare_live_speech.py` to enable it. Your answer is "
        + "still recorded and analysed exactly as normal.",
      );
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  const start = useCallback((stream: MediaStream) => {
    const model = modelRef.current as {
      KaldiRecognizer: new (rate: number) => {
        on: (event: string, handler: (message: unknown) => void) => void;
        acceptWaveform: (buffer: AudioBuffer) => void;
        remove?: () => void;
      };
    } | null;
    if (!model || stream.getAudioTracks().length === 0) return;

    trackerRef.current = emptyTracker();
    trackerRef.current.startedAt = performance.now();
    trackerRef.current.lastWordAt = performance.now();

    let recognizer;
    try {
      recognizer = new model.KaldiRecognizer(SAMPLE_RATE);
    } catch {
      return;
    }
    recognizerRef.current = recognizer;

    const ingest = (text: string) => {
      if (!text.trim()) return;
      const tracker = trackerRef.current;
      const now = performance.now();

      const gap = (now - tracker.lastWordAt) / 1000;
      if (gap >= LONG_PAUSE_SECONDS) tracker.longPauses += 1;
      tracker.lastWordAt = now;

      for (const raw of text.split(/\s+/)) {
        const word = raw.toLowerCase().replace(/[^a-z']/g, "");
        if (!word) continue;
        tracker.words.push(word);
        if (FILLERS.has(word)) {
          tracker.fillerTimes.push(
            Number(((now - tracker.startedAt) / 1000).toFixed(1)),
          );
        }
      }
      setLive(snapshot());
    };

    recognizer.on("result", (message: unknown) => {
      const text = (message as { result?: { text?: string } })?.result?.text;
      if (text) ingest(text);
    });

    // Partials keep the display alive between finalised phrases, but are not
    // counted — a partial is revised as it goes, so counting it double-counts.
    recognizer.on("partialresult", () => setLive(snapshot()));

    try {
      const context = new AudioContext({ sampleRate: SAMPLE_RATE });
      contextRef.current = context;
      const source = context.createMediaStreamSource(stream);
      sourceRef.current = source;

      // ScriptProcessor rather than an AudioWorklet: vosk-browser accepts an
      // AudioBuffer directly, and this path avoids shipping a worklet file for
      // a node that runs for ninety seconds at a time.
      const node = context.createScriptProcessor(4096, 1, 1);
      nodeRef.current = node;
      node.onaudioprocess = (event) => {
        try {
          recognizer.acceptWaveform(event.inputBuffer);
        } catch {
          /* a dropped buffer is not worth interrupting the interview for */
        }
      };
      source.connect(node);
      // Connected to the destination with no gain, because a ScriptProcessor
      // that is not connected downstream is not scheduled by the browser.
      const silence = context.createGain();
      silence.gain.value = 0;
      node.connect(silence);
      silence.connect(context.destination);

      setListening(true);
      setLive(snapshot());
    } catch {
      setError("Live analysis could not start. The interview is unaffected.");
    }
  }, [snapshot]);

  const stop = useCallback((): LiveSpeech | null => {
    const final = trackerRef.current.startedAt ? snapshot() : null;

    nodeRef.current?.disconnect();
    sourceRef.current?.disconnect();
    void contextRef.current?.close().catch(() => {});
    nodeRef.current = null;
    sourceRef.current = null;
    contextRef.current = null;

    const recognizer = recognizerRef.current as { remove?: () => void } | null;
    try {
      recognizer?.remove?.();
    } catch {
      /* nothing depends on tearing this down cleanly */
    }
    recognizerRef.current = null;

    setListening(false);
    return final;
  }, [snapshot]);

  const reset = useCallback(() => {
    trackerRef.current = emptyTracker();
    setLive(null);
  }, []);

  return { available, loading, listening, live, error, load, start, stop, reset };
}
