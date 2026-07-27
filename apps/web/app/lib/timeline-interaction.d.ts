export type TimelineGesture =
  | { type: "seek"; time: number }
  | { type: "loop"; start: number; end: number }
  | { type: "none" };

export function resolveTimelineGesture(options: {
  tool: "seek" | "loop";
  startX: number;
  endX: number;
  startTime: number;
  endTime: number;
  handle?: "start" | "end" | null;
  loop?: { start: number; end: number } | null;
  minimumPixels?: number;
  minimumSeconds?: number;
}): TimelineGesture;
