import { useEffect, useRef, useState } from "react";
import type { RefObject } from "react";

/**
 * Whether an element has scrolled into view, as a boolean.
 *
 * For components that run something once they are on screen — an animated
 * demo, a chart that draws itself — rather than just fading in. Same dead-man
 * switch as the reveal below: if the observer exists but never reports, the
 * answer becomes "yes" so the thing runs anyway.
 */
export function useInView<T extends HTMLElement>(
  threshold = 0.3,
): [RefObject<T>, boolean] {
  const ref = useRef<T>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }
    let delivered = false;
    const observer = new IntersectionObserver(
      ([entry]) => {
        delivered = true;
        if (entry?.isIntersecting) {
          setInView(true);
          observer.disconnect();
        }
      },
      { threshold },
    );
    observer.observe(el);
    const failsafe = window.setTimeout(() => {
      if (delivered) return;
      observer.disconnect();
      setInView(true);
    }, 2000);
    return () => {
      window.clearTimeout(failsafe);
      observer.disconnect();
    };
  }, [threshold]);

  return [ref, inView];
}

export function prefersReducedMotionNow(): boolean {
  return prefersReducedMotion();
}

/**
 * Scroll-triggered reveal and count-up.
 *
 * Both hooks below share one rule: **the end state is the default**. An element
 * is only moved to its "before" state once the observer is attached and has
 * confirmed it will fire. If IntersectionObserver is missing, JS throws, or the
 * user has asked for reduced motion, the content is simply already there.
 *
 * The alternative — animating from `opacity: 0` in CSS and relying on JS to
 * remove it — turns any failure into a blank page.
 */

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true
  );
}

/**
 * Reveals every `.reveal` descendant of `root` as it scrolls into view.
 *
 * One observer for the whole page rather than one per element: a landing page
 * has 40-odd revealed nodes and 40 observers is 40 sets of callbacks competing
 * on the same scroll.
 */
export function useRevealOnScroll(root: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const host = root.current;
    if (!host) return;
    if (prefersReducedMotion() || typeof IntersectionObserver === "undefined") return;

    const nodes = Array.from(host.querySelectorAll<HTMLElement>(".reveal"));
    if (nodes.length === 0) return;

    let delivered = false;

    const observer = new IntersectionObserver(
      (entries) => {
        delivered = true;
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          const el = entry.target as HTMLElement;
          // Stagger within a row so a grid resolves left-to-right instead of
          // all six cards snapping at once.
          const delay = Number(el.dataset.revealDelay ?? 0);
          window.setTimeout(() => el.classList.add("is-visible"), delay);
          observer.unobserve(el);
        }
      },
      // Fire a little before the element reaches the fold, so the transition is
      // finishing as it arrives rather than starting.
      { rootMargin: "0px 0px -12% 0px", threshold: 0.08 },
    );

    // Arm only now that the observer exists and is about to watch them.
    for (const node of nodes) {
      node.dataset.armed = "1";
      observer.observe(node);
    }

    /* Dead-man switch.
     *
     * `IntersectionObserver` existing is not the same as it working. In a
     * renderer that never composites — a hidden webview, an embedded preview,
     * some headless capture paths — the constructor succeeds and the callback
     * is simply never invoked, which would leave the whole page at opacity 0
     * with no error anywhere.
     *
     * On any working page at least the above-the-fold elements report
     * immediately, so *zero* deliveries after a beat means the observer is not
     * going to fire at all. Give up on it and show everything. */
    const failsafe = window.setTimeout(() => {
      if (delivered) return;
      observer.disconnect();
      for (const node of nodes) node.classList.add("is-visible");
    }, 2000);

    return () => {
      window.clearTimeout(failsafe);
      observer.disconnect();
    };
  }, [root]);
}

/**
 * Counts a number up once it is on screen.
 *
 * Returns a ref to attach to the element that should hold the number. The
 * element's text is set imperatively rather than through state: a dozen
 * counters each re-rendering 60 times a second would re-render the page 720
 * times a second for a decorative effect.
 */
export function useCountUp(
  target: number,
  { decimals = 0, durationMs = 1400 }: { decimals?: number; durationMs?: number } = {},
) {
  const ref = useRef<HTMLSpanElement | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const format = (value: number) =>
      value.toLocaleString("en-IN", {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      });

    if (prefersReducedMotion() || typeof IntersectionObserver === "undefined") {
      el.textContent = format(target);
      return;
    }

    // Reserve the final width before counting, or every tile jitters as the
    // digit count grows. Monospace figures plus this makes the row still.
    el.textContent = format(target);
    let frame = 0;
    let settle = 0;
    let started = false;

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries[0]?.isIntersecting || started) return;
        started = true;
        observer.disconnect();

        const startedAt = performance.now();
        const step = (now: number) => {
          const progress = Math.min(1, (now - startedAt) / durationMs);
          // Ease-out quint: fast enough to read as instant, slow enough at the
          // end that the final value feels settled rather than cut off.
          const eased = 1 - Math.pow(1 - progress, 5);
          el.textContent = format(target * eased);
          if (progress < 1) frame = requestAnimationFrame(step);
        };
        el.textContent = format(0);
        frame = requestAnimationFrame(step);

        /* Guarantee the true value lands.
         *
         * `requestAnimationFrame` stops being serviced whenever the renderer
         * stops producing frames — the tab is backgrounded, the window is
         * occluded, the page is being captured. An interrupted count-up does
         * not just look unfinished, it leaves a *wrong number* on screen: the
         * officer count would read 41 instead of 204. A timer keeps running
         * when rAF does not, so it is what the final value is written from. */
        settle = window.setTimeout(() => {
          cancelAnimationFrame(frame);
          el.textContent = format(target);
        }, durationMs + 150);
      },
      { threshold: 0.4 },
    );

    observer.observe(el);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
      window.clearTimeout(settle);
    };
  }, [target, decimals, durationMs]);

  return ref;
}
