export function resolveTimelineGesture({
  tool,
  startX,
  endX,
  startTime,
  endTime,
  handle = null,
  loop = null,
  minimumPixels = 5,
  minimumSeconds = 0.08,
}) {
  if (tool === "seek") {
    return { type: "seek", time: endTime };
  }
  if (handle && loop) {
    if (handle === "start") {
      return {
        type: "loop",
        start: Math.min(endTime, loop.end - minimumSeconds),
        end: loop.end,
      };
    }
    return {
      type: "loop",
      start: loop.start,
      end: Math.max(endTime, loop.start + minimumSeconds),
    };
  }
  if (
    Math.abs(endX - startX) < minimumPixels ||
    Math.abs(endTime - startTime) < minimumSeconds
  ) {
    return { type: "none" };
  }
  return {
    type: "loop",
    start: Math.min(startTime, endTime),
    end: Math.max(startTime, endTime),
  };
}
