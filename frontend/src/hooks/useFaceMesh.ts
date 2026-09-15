import { useCallback, useRef, useState } from "react";

import type { AttentionSummary } from "../types";

/**
 * Camera engagement, measured entirely in this browser.
 *
 * MediaPipe Face Mesh runs on the live preview and produces landmarks per
 * frame. Those landmarks never leave this function: they are folded into
 * running counters and discarded, and what `summary()` returns is a handful of
 * numbers. There is no code path here that retains a frame, an image or a
 * landmark, and no upload of any kind.
 *
 * That is deliberate rather than incidental. Facial geometry is biometric
 * personal data under the DPDP Act 2023, and the cheapest way to be sure a
 * government database never holds an officer's face is for it never to be sent.
 *
 * The model and its wasm runtime are served from `public/mediapipe/`, not a
 * CDN, so an air-gapped deployment works the same as this laptop does.
 *
 * What these numbers are for: the officer watches their own recording
 * afterwards and sees what a listener would see. They are not scored, they do
 * not reach a supervisor, and nothing here touches a competency level.
 */

const WASM_PATH = "/mediapipe/wasm";
const MODEL_PATH = "/mediapipe/models/face_landmarker.task";

// Roughly 10 fps. Face Mesh at full frame rate buys precision nobody needs here
// and competes with the recording for the same CPU.
const SAMPLE_INTERVAL_MS = 100;

// How far off-centre the gaze may drift and still count as looking at the
// screen. Generous on purpose: this is a coaching hint, and a tight threshold
// would punish anyone sitting slightly off-axis from their webcam.
const GAZE_TOLERANCE = 0.22;

// Looking away for less than this is reading, thinking or glancing at notes.
const LOOK_AWAY_SECONDS = 1.5;

const BLINK_THRESHOLD = 0.5;

const HAND_MODEL_PATH = "/mediapipe/models/hand_landmarker.task";

// Hands are checked on every other tick, about five times a second. Gestures
// change slowly compared with gaze, and two landmarkers at full rate on a
// laptop CPU compete with the recording itself.
const HAND_EVERY_N_TICKS = 2;

// Wrist travel, in normalised frame units per hand sample, that counts as
// fully animated. Calibrated so ordinary explanatory gesturing lands mid-scale.
const ANIMATED_WRIST_TRAVEL = 0.05;

// MediaPipe hand landmark indices: wrist, then thumb, index and middle tips.
const WRIST = 0;
const FINGERTIPS = [4, 8, 12];

interface Accumulator {
  frames: number;
  facePresent: number;
  onScreen: number;
  blinks: number;
  wasBlinking: boolean;
  lookAwayRuns: number[];
  currentRun: number;
  headPositions: { x: number; y: number }[];
  // Gestures
  handTicks: number;
  handsVisible: number;
  lastWrists: { x: number; y: number }[];
  wristTravel: number;
  wristSamples: number;
  faceTouches: number;
  wasTouching: boolean;
  faceBox: { minX: number; maxX: number; minY: number; maxY: number } | null;
}

function emptyAccumulator(): Accumulator {
  return {
    frames: 0, facePresent: 0, onScreen: 0, blinks: 0, wasBlinking: false,
    lookAwayRuns: [], currentRun: 0, headPositions: [],
    handTicks: 0, handsVisible: 0, lastWrists: [], wristTravel: 0, wristSamples: 0,
    faceTouches: 0, wasTouching: false, faceBox: null,
  };
}

function score(blendshapes: unknown, name: string): number {
  const categories = (blendshapes as { categories?: { categoryName: string; score: number }[] })
    ?.categories;
  return categories?.find((c) => c.categoryName === name)?.score ?? 0;
}

export function useFaceMesh() {
  const [ready, setReady] = useState(false);
  const [supported, setSupported] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [livePresent, setLivePresent] = useState<boolean | null>(null);

  const landmarkerRef = useRef<unknown>(null);
  // Optional. If the hand model fails to load, gaze tracking carries on alone.
  const handLandmarkerRef = useRef<unknown>(null);
  const tickRef = useRef(0);
  const timerRef = useRef<number | null>(null);
  const accRef = useRef<Accumulator>(emptyAccumulator());

  /** Load the model. Safe to call repeatedly; only the first load does work. */
  const load = useCallback(async () => {
    if (landmarkerRef.current) {
      setReady(true);
      return true;
    }
    try {
      const vision = await import("@mediapipe/tasks-vision");
      const fileset = await vision.FilesetResolver.forVisionTasks(WASM_PATH);
      landmarkerRef.current = await vision.FaceLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: MODEL_PATH, delegate: "GPU" },
        outputFaceBlendshapes: true,
        outputFacialTransformationMatrixes: false,
        runningMode: "VIDEO",
        numFaces: 1,
      });
      try {
        handLandmarkerRef.current = await vision.HandLandmarker.createFromOptions(fileset, {
          baseOptions: { modelAssetPath: HAND_MODEL_PATH, delegate: "GPU" },
          runningMode: "VIDEO",
          numHands: 2,
        });
      } catch {
        // Gestures are the least important signal here; losing them must not
        // take gaze tracking down too.
        handLandmarkerRef.current = null;
      }
      setReady(true);
      setSupported(true);
      return true;
    } catch (e) {
      // A machine without WebGL, or a browser that blocks wasm, simply does not
      // get this feature. The interview itself is unaffected — attention is
      // coaching, and the answer is still recorded, transcribed and scored.
      setSupported(false);
      setError(
        e instanceof Error
          ? `Camera analysis is unavailable on this machine (${e.message}). The interview will run without it.`
          : "Camera analysis is unavailable on this machine. The interview will run without it.",
      );
      return false;
    }
  }, []);

  /** One hand sample. Called from the tick, every HAND_EVERY_N_TICKS. */
  const sampleHands = useCallback(
    (
      hands: { detectForVideo: (v: HTMLVideoElement, t: number) => { landmarks: { x: number; y: number }[][] } },
      video: HTMLVideoElement,
    ) => {
      const acc = accRef.current;
      acc.handTicks += 1;
      let result;
      try {
        result = hands.detectForVideo(video, performance.now());
      } catch {
        return;
      }
      const found = result.landmarks ?? [];
      if (found.length === 0) {
        acc.lastWrists = [];
        acc.wasTouching = false;
        return;
      }
      acc.handsVisible += 1;

      // Movement: how far each wrist travelled since the last sample. Matched
      // by order, which is stable enough over two hundred milliseconds.
      const wrists = found.map((hand) => hand[WRIST]).filter(Boolean);
      wrists.forEach((wrist, i) => {
        const previous = acc.lastWrists[i];
        if (previous) {
          acc.wristTravel += Math.hypot(wrist.x - previous.x, wrist.y - previous.y);
          acc.wristSamples += 1;
        }
      });
      acc.lastWrists = wrists;

      // A fingertip inside the face box, padded a little. Counted on the way
      // in, so a hand resting on the chin is one touch, not twenty.
      const box = acc.faceBox;
      let touching = false;
      if (box) {
        const padX = (box.maxX - box.minX) * 0.1;
        const padY = (box.maxY - box.minY) * 0.1;
        touching = found.some((hand) =>
          FINGERTIPS.some((index) => {
            const tip = hand[index];
            return tip && tip.x >= box.minX - padX && tip.x <= box.maxX + padX &&
              tip.y >= box.minY - padY && tip.y <= box.maxY + padY;
          }),
        );
      }
      if (touching && !acc.wasTouching) acc.faceTouches += 1;
      acc.wasTouching = touching;
    },
    [],
  );

  const start = useCallback((video: HTMLVideoElement) => {
    const landmarker = landmarkerRef.current as {
      detectForVideo: (v: HTMLVideoElement, t: number) => {
        faceLandmarks: { x: number; y: number }[][];
        faceBlendshapes: unknown[];
      };
    } | null;
    if (!landmarker) return;

    accRef.current = emptyAccumulator();
    tickRef.current = 0;
    const hands = handLandmarkerRef.current as {
      detectForVideo: (v: HTMLVideoElement, t: number) => {
        landmarks: { x: number; y: number }[][];
      };
    } | null;

    timerRef.current = window.setInterval(() => {
      if (video.readyState < 2) return;
      const acc = accRef.current;
      acc.frames += 1;
      tickRef.current += 1;
      if (hands && tickRef.current % HAND_EVERY_N_TICKS === 0) sampleHands(hands, video);

      let result;
      try {
        result = landmarker.detectForVideo(video, performance.now());
      } catch {
        return; // a dropped frame is not worth reporting
      }

      const landmarks = result.faceLandmarks?.[0];
      if (!landmarks || landmarks.length === 0) {
        acc.currentRun += SAMPLE_INTERVAL_MS / 1000;
        setLivePresent(false);
        return;
      }

      acc.facePresent += 1;
      setLivePresent(true);

      const shapes = result.faceBlendshapes?.[0];
      const blinking =
        score(shapes, "eyeBlinkLeft") > BLINK_THRESHOLD &&
        score(shapes, "eyeBlinkRight") > BLINK_THRESHOLD;
      if (blinking && !acc.wasBlinking) acc.blinks += 1;
      acc.wasBlinking = blinking;

      // Gaze from the blendshape pairs rather than raw iris geometry: the
      // in/out/up/down scores are already normalised for head pose, which is
      // what makes this usable when someone is not squared up to the camera.
      const horizontal =
        score(shapes, "eyeLookOutLeft") + score(shapes, "eyeLookInRight") -
        score(shapes, "eyeLookInLeft") - score(shapes, "eyeLookOutRight");
      const vertical =
        score(shapes, "eyeLookUpLeft") + score(shapes, "eyeLookUpRight") -
        score(shapes, "eyeLookDownLeft") - score(shapes, "eyeLookDownRight");

      const offAxis = Math.hypot(horizontal / 2, vertical / 2);
      if (offAxis <= GAZE_TOLERANCE) {
        acc.onScreen += 1;
        if (acc.currentRun >= LOOK_AWAY_SECONDS) acc.lookAwayRuns.push(acc.currentRun);
        acc.currentRun = 0;
      } else {
        acc.currentRun += SAMPLE_INTERVAL_MS / 1000;
      }

      // Nose tip, for how much the head moved overall.
      const nose = landmarks[1];
      if (nose) acc.headPositions.push({ x: nose.x, y: nose.y });

      let minX = 1, maxX = 0, minY = 1, maxY = 0;
      for (const point of landmarks) {
        if (point.x < minX) minX = point.x;
        if (point.x > maxX) maxX = point.x;
        if (point.y < minY) minY = point.y;
        if (point.y > maxY) maxY = point.y;
      }
      acc.faceBox = { minX, maxX, minY, maxY };
    }, SAMPLE_INTERVAL_MS);
  }, [sampleHands]);

  const stop = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
    setLivePresent(null);
  }, []);

  /**
   * Fold the run into the numbers that get sent.
   *
   * This is the only thing that leaves: eight aggregates. Returns null when too
   * little was tracked to say anything, which is reported as "unusable" rather
   * than dressed up as a low score.
   */
  const summary = useCallback((durationSeconds: number): AttentionSummary | null => {
    const acc = accRef.current;
    if (acc.frames < 30) return null;

    if (acc.currentRun >= LOOK_AWAY_SECONDS) acc.lookAwayRuns.push(acc.currentRun);

    const facePresentRatio = acc.facePresent / acc.frames;
    const gazeRatio = acc.facePresent > 0 ? acc.onScreen / acc.facePresent : null;

    // Spread of head position, inverted so 1 is perfectly steady.
    let stability: number | null = null;
    if (acc.headPositions.length > 5) {
      const meanX = acc.headPositions.reduce((s, p) => s + p.x, 0) / acc.headPositions.length;
      const meanY = acc.headPositions.reduce((s, p) => s + p.y, 0) / acc.headPositions.length;
      const spread = Math.sqrt(
        acc.headPositions.reduce(
          (s, p) => s + (p.x - meanX) ** 2 + (p.y - meanY) ** 2, 0,
        ) / acc.headPositions.length,
      );
      stability = Math.max(0, Math.min(1, 1 - spread * 8));
    }

    return {
      screen_gaze_ratio: gazeRatio === null ? null : Number(gazeRatio.toFixed(3)),
      longest_look_away_seconds: acc.lookAwayRuns.length
        ? Number(Math.max(...acc.lookAwayRuns).toFixed(1))
        : 0,
      look_away_count: acc.lookAwayRuns.length,
      blink_rate_per_minute: durationSeconds > 0
        ? Number(((acc.blinks / durationSeconds) * 60).toFixed(1))
        : null,
      head_stability: stability === null ? null : Number(stability.toFixed(3)),
      face_present_ratio: Number(facePresentRatio.toFixed(3)),
      frames_analysed: acc.frames,
      // Null when hand tracking never ran, so "no gesture data" is never
      // reported as "kept perfectly still".
      hands_visible_ratio: acc.handTicks > 0
        ? Number((acc.handsVisible / acc.handTicks).toFixed(3))
        : null,
      hand_movement: acc.wristSamples > 0
        ? Number(Math.min(1, acc.wristTravel / acc.wristSamples / ANIMATED_WRIST_TRAVEL).toFixed(3))
        : null,
      face_touch_count: acc.handTicks > 0 ? acc.faceTouches : null,
    };
  }, []);

  return { ready, supported, error, livePresent, load, start, stop, summary };
}
