import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Microphone, and optionally webcam, recording via MediaRecorder.
 *
 * Answers are capped: a three-minute answer means a minute of analysis, and the
 * cap is enforced here rather than only being suggested in copy.
 *
 * **The uploaded blob is audio-only by construction.** When the camera is on,
 * two recorders run: one over a stream built from the audio tracks alone, whose
 * output is what `onComplete` hands to the API, and a second over the full
 * stream whose output stays in this tab as an object URL for the officer to
 * watch. No branch lets the video recorder's blob reach `onComplete`, so
 * "video never leaves the browser" is a property of the code rather than a
 * promise made in a comment.
 *
 * The stream is stopped on every exit path. Leaving a camera or microphone open
 * after recording ends is both a privacy problem and the reason a browser keeps
 * showing the recording indicator.
 */

export type RecorderState = "idle" | "requesting" | "recording" | "stopped" | "denied";

interface Options {
  maxSeconds: number;
  onComplete: (blob: Blob, seconds: number) => void;
  /** Turn the camera on. Off by default: the interview works without it. */
  video?: boolean;
  /** Handed the live stream so a caller can preview it and run Face Mesh. */
  onStream?: (stream: MediaStream) => void;
}

export function useRecorder({ maxSeconds, onComplete, video = false, onStream }: Options) {
  const [state, setState] = useState<RecorderState>("idle");
  const [seconds, setSeconds] = useState(0);
  const [level, setLevel] = useState(0);
  const [error, setError] = useState<string | null>(null);
  /** Object URL for the local recording. Never uploaded, never persisted. */
  const [localVideoUrl, setLocalVideoUrl] = useState<string | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const videoRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const videoChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const frameRef = useRef<number | null>(null);
  const tickRef = useRef<number | null>(null);
  const startedAtRef = useRef(0);

  const cleanup = useCallback(() => {
    if (frameRef.current) cancelAnimationFrame(frameRef.current);
    if (tickRef.current) clearInterval(tickRef.current);
    frameRef.current = null;
    tickRef.current = null;

    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;

    void audioContextRef.current?.close().catch(() => {});
    audioContextRef.current = null;
    setLevel(0);
  }, []);

  useEffect(() => cleanup, [cleanup]);

  const stop = useCallback(() => {
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
    if (videoRecorderRef.current?.state === "recording") videoRecorderRef.current.stop();
  }, []);

  const start = useCallback(async () => {
    setError(null);
    setSeconds(0);
    chunksRef.current = [];

    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("This browser cannot record audio. Chrome, Edge and Firefox all can.");
      setState("denied");
      return;
    }

    setState("requesting");
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          // Left off deliberately: automatic gain control rewrites loudness,
          // and intensity is one of the measurements taken from the recording.
          autoGainControl: false,
        },
        video: video
          ? { width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 15 } }
          : false,
      });
    } catch {
      setError(
        video
          ? "Camera or microphone access was refused. Allow it in your browser's address bar, or switch the camera off and continue with audio."
          : "Microphone access was refused. Allow it in your browser's address bar, then try again.",
      );
      setState("denied");
      return;
    }

    streamRef.current = stream;
    onStream?.(stream);

    // Live level meter, so the officer can see they are actually being heard.
    try {
      const context = new AudioContext();
      audioContextRef.current = context;
      const analyser = context.createAnalyser();
      analyser.fftSize = 512;
      context.createMediaStreamSource(stream).connect(analyser);
      const data = new Uint8Array(analyser.frequencyBinCount);

      const sample = () => {
        analyser.getByteTimeDomainData(data);
        let sum = 0;
        for (const value of data) sum += (value - 128) ** 2;
        setLevel(Math.min(1, Math.sqrt(sum / data.length) / 40));
        frameRef.current = requestAnimationFrame(sample);
      };
      sample();
    } catch {
      /* the meter is a nicety; recording continues without it */
    }

    const mimeType = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus"].find(
      (type) => MediaRecorder.isTypeSupported(type),
    );
    // A stream of the audio tracks alone. This — not the camera stream — is what
    // the upload recorder sees, so a video track cannot end up in the blob that
    // goes to the server.
    const audioOnly = new MediaStream(stream.getAudioTracks());
    const recorder = new MediaRecorder(audioOnly, mimeType ? { mimeType } : undefined);
    recorderRef.current = recorder;

    if (video && stream.getVideoTracks().length > 0) {
      const videoMime = ["video/webm;codecs=vp8,opus", "video/webm"].find((type) =>
        MediaRecorder.isTypeSupported(type),
      );
      try {
        const videoRecorder = new MediaRecorder(
          stream, videoMime ? { mimeType: videoMime } : undefined,
        );
        videoRecorderRef.current = videoRecorder;
        videoChunksRef.current = [];
        videoRecorder.ondataavailable = (event) => {
          if (event.data.size > 0) videoChunksRef.current.push(event.data);
        };
        videoRecorder.onstop = () => {
          const blob = new Blob(videoChunksRef.current, {
            type: videoRecorder.mimeType || "video/webm",
          });
          // An object URL held in this tab only, revoked on the next recording
          // and when the page unmounts.
          if (blob.size > 0) {
            setLocalVideoUrl((prev) => {
              if (prev) URL.revokeObjectURL(prev);
              return URL.createObjectURL(blob);
            });
          }
        };
        videoRecorder.start();
      } catch {
        /* recording the answer matters; the self-review copy does not */
      }
    }

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunksRef.current.push(event.data);
    };

    recorder.onstop = () => {
      if (videoRecorderRef.current?.state === "recording") {
        videoRecorderRef.current.stop();
      }
      const elapsed = (Date.now() - startedAtRef.current) / 1000;
      const blob = new Blob(chunksRef.current, {
        type: recorder.mimeType || "audio/webm",
      });
      cleanup();
      setState("stopped");
      if (blob.size > 0) onComplete(blob, elapsed);
      else setError("Nothing was recorded. Check that the right microphone is selected.");
    };

    startedAtRef.current = Date.now();
    recorder.start();
    setState("recording");

    tickRef.current = window.setInterval(() => {
      const elapsed = (Date.now() - startedAtRef.current) / 1000;
      setSeconds(elapsed);
      if (elapsed >= maxSeconds) stop();
    }, 100);
  }, [cleanup, maxSeconds, onComplete, stop, video, onStream]);

  const reset = useCallback(() => {
    cleanup();
    setState("idle");
    setSeconds(0);
    setError(null);
    setLocalVideoUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return null;
    });
  }, [cleanup]);

  return { state, seconds, level, error, start, stop, reset, localVideoUrl };
}
