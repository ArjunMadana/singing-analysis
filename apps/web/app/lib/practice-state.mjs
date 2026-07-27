/** Clamp and normalize a loop selection. */
export function normalizeLoop(start, end, duration, minimum = 0.08) {
  const low = Math.max(0, Math.min(start, end, duration));
  const high = Math.max(low + minimum, Math.min(Math.max(start, end), duration));
  return { start: low, end: Math.min(duration, high) };
}

/** Select the next discrepancy, wrapping at either edge. */
export function stepDiscrepancy(current, count, direction) {
  if (count <= 0) return -1;
  if (current < 0) return direction > 0 ? 0 : count - 1;
  return (current + direction + count) % count;
}

/** Decide whether playback should wrap during a loop. */
export function loopTarget(currentTime, loop, enabled) {
  return enabled && currentTime >= loop.end ? loop.start : null;
}

/** Keep keyboard shortcuts inert while a user edits a form. */
export function acceptsPracticeShortcut(tagName, isContentEditable = false) {
  return !isContentEditable && !["INPUT", "TEXTAREA", "SELECT", "BUTTON"].includes(tagName);
}

/** Validate the import wizard's one-microphone/one-reference invariant. */
export function validStreamRoles(roles) {
  const values = Object.values(roles);
  return (
    values.filter((role) => role === "microphone").length === 1 &&
    values.filter((role) => role === "reference").length === 1
  );
}

/** Confidence-aware comparison copy. */
export function comparisonVerdict(before, after, confidence) {
  if (confidence < 0.5) return "insufficient confidence";
  if (after < before) return "improved";
  if (after > before) return "worsened";
  return "unchanged";
}

/** Present a stable processing label for every job state. */
export function processingLabel(job) {
  if (job.status === "failed") return "Analysis failed";
  if (job.status === "completed") return "Analysis complete";
  if (!job.stage || job.stage === "queued") return "Waiting to begin";
  return `Processing ${job.stage.replaceAll("_", " ")}`;
}
