import assert from "node:assert/strict";
import test from "node:test";
import {
  acceptsPracticeShortcut,
  comparisonVerdict,
  loopTarget,
  normalizeLoop,
  processingLabel,
  stepDiscrepancy,
  validStreamRoles,
} from "../app/lib/practice-state.mjs";
import {
  SharedAudioTransport,
  buildSchedule,
  loopStartAt,
  mapWaveformToCanonical,
  mappedSourceTime,
  safeFullAlignmentRate,
  sourcesReady,
} from "../app/lib/shared-transport.mjs";
import { resolveTimelineGesture } from "../app/lib/timeline-interaction.mjs";
import {
  createImportDraft,
  createInspectedImportDraft,
  importDraftForProject,
} from "../app/lib/import-draft.mjs";

test("normalizes loop selection and keeps a useful minimum", () => {
  assert.deepEqual(normalizeLoop(4, 2, 10), { start: 2, end: 4 });
  assert.deepEqual(normalizeLoop(-2, 0.01, 10), { start: 0, end: 0.08 });
});

test("a new project cannot inherit a previously inspected recording", () => {
  const inspected = createInspectedImportDraft("project-one", {
    token: "old-recording",
    streams: [
      { index: 0, suggested_role: "microphone" },
      { index: 1, suggested_role: "reference" },
    ],
  });
  const next = importDraftForProject(inspected, "project-two");
  assert.deepEqual(next, createImportDraft("project-two"));
});

test("choosing another recording clears inspection and stream roles", () => {
  const reset = createImportDraft("project-one");
  assert.equal(reset.inspection, null);
  assert.deepEqual(reset.roles, {});
});

test("timeline click seeks without creating a loop", () => {
  assert.deepEqual(
    resolveTimelineGesture({
      tool: "seek",
      startX: 100,
      endX: 101,
      startTime: 4,
      endTime: 4.01,
    }),
    { type: "seek", time: 4.01 },
  );
});

test("loop tool ignores clicks and tiny drags", () => {
  assert.deepEqual(
    resolveTimelineGesture({
      tool: "loop",
      startX: 100,
      endX: 102,
      startTime: 4,
      endTime: 4.01,
    }),
    { type: "none" },
  );
});

test("loop tool creates intentional ranges and adjusts handles", () => {
  assert.deepEqual(
    resolveTimelineGesture({
      tool: "loop",
      startX: 100,
      endX: 180,
      startTime: 4,
      endTime: 6,
    }),
    { type: "loop", start: 4, end: 6 },
  );
  assert.deepEqual(
    resolveTimelineGesture({
      tool: "loop",
      startX: 100,
      endX: 140,
      startTime: 4,
      endTime: 5,
      handle: "start",
      loop: { start: 4, end: 8 },
    }),
    { type: "loop", start: 5, end: 8 },
  );
});

test("steps discrepancies with wraparound", () => {
  assert.equal(stepDiscrepancy(-1, 3, 1), 0);
  assert.equal(stepDiscrepancy(2, 3, 1), 0);
  assert.equal(stepDiscrepancy(0, 3, -1), 2);
});

test("loop state wraps only at the configured end", () => {
  assert.equal(loopTarget(3.9, { start: 2, end: 4 }, true), null);
  assert.equal(loopTarget(4, { start: 2, end: 4 }, true), 2);
  assert.equal(loopTarget(4, { start: 2, end: 4 }, false), null);
});

test("shortcuts stay inert in forms", () => {
  assert.equal(acceptsPracticeShortcut("DIV"), true);
  assert.equal(acceptsPracticeShortcut("INPUT"), false);
  assert.equal(acceptsPracticeShortcut("DIV", true), false);
});

test("stream assignment requires exactly one mic and reference", () => {
  assert.equal(validStreamRoles({ 0: "microphone", 1: "reference" }), true);
  assert.equal(validStreamRoles({ 0: "microphone", 1: "microphone" }), false);
  assert.equal(
    validStreamRoles({ 0: "microphone", 1: "reference", 2: "reference" }),
    false,
  );
});

test("comparison never declares low-confidence improvement", () => {
  assert.equal(comparisonVerdict(60, 20, 0.3), "insufficient confidence");
  assert.equal(comparisonVerdict(60, 20, 0.9), "improved");
  assert.equal(comparisonVerdict(20, 60, 0.9), "worsened");
});

test("processing labels expose waiting, failure, and active stage", () => {
  assert.equal(processingLabel({ status: "queued", stage: "queued" }), "Waiting to begin");
  assert.equal(
    processingLabel({ status: "running", stage: "pitch_tracking" }),
    "Processing pitch tracking",
  );
  assert.equal(processingLabel({ status: "failed" }), "Analysis failed");
});

const mapping = {
  canonical_time: [0, 1, 2, 3],
  reference_time: [0.1, 1.1, 2.1, 3.1],
  user_time: [1, 2.05, 3.2, 4.25],
};

test("shared schedule starts enabled sources on the same audio clock", () => {
  const schedule = buildSchedule(
    {
      mapping,
      mode: "full",
      automaticLatencySeconds: 1,
      manualOffsetSeconds: 0,
    },
    1,
    2,
    10,
  );
  assert.equal(schedule[0].when, schedule[1].when);
  assert.equal(schedule[0].canonicalStart, schedule[1].canonicalStart);
});

test("source readiness follows the selected mix", () => {
  const readiness = {
    user: { status: "ready" },
    reference: { status: "error" },
  };
  assert.equal(sourcesReady(readiness, "user"), true);
  assert.equal(sourcesReady(readiness, "both"), false);
  assert.equal(sourcesReady(readiness, "reference"), false);
});

test("mapped seek applies constant latency and nonlinear local alignment", () => {
  assert.equal(mappedSourceTime(mapping, 1.5, "reference", "full"), 1.6);
  assert.ok(
    Math.abs(mappedSourceTime(mapping, 1.5, "user", "constant", 1, 0.2) - 2.8) <
      1e-12,
  );
  assert.ok(
    Math.abs(mappedSourceTime(mapping, 1.5, "user", "full", 1, 0.2) - 2.825) <
      1e-12,
  );
});

test("partial-take waveforms are cropped and mapped to canonical time", () => {
  const partialMapping = {
    canonical_time: [0, 1, 2],
    reference_time: [3, 4, 5],
    user_time: [3.3, 4.3, 5.3],
  };
  const waveform = {
    time: [0, 1, 2, 3, 4, 5, 6],
    minimum: [-1, -2, -3, -4, -5, -6, -7],
    maximum: [1, 2, 3, 4, 5, 6, 7],
    duration: 7,
  };
  assert.deepEqual(
    mapWaveformToCanonical(waveform, partialMapping, "reference_time"),
    {
      time: [0, 1, 2],
      minimum: [-4, -5, -6],
      maximum: [4, 5, 6],
      duration: 2,
    },
  );
});

test("full alignment rejects audio-mangling playback rates", () => {
  assert.equal(safeFullAlignmentRate(1), true);
  assert.equal(safeFullAlignmentRate(0.72), true);
  assert.equal(safeFullAlignmentRate(1.22), true);
  assert.equal(safeFullAlignmentRate(0), false);
  assert.equal(safeFullAlignmentRate(2.2), false);
  assert.equal(safeFullAlignmentRate(90.5), false);
});

test("twenty loop starts remain anchored without accumulated drift", () => {
  const starts = Array.from({ length: 20 }, (_, index) =>
    loopStartAt(5.25, index, 2.5),
  );
  starts.forEach((value, index) => {
    assert.ok(Math.abs(value - (5.25 + index * 2.5)) < 1e-12);
  });
});

class FakeAudioContext {
  constructor() {
    this.currentTime = 4;
    this.destination = {};
    this.starts = [];
  }
  createGain() {
    return { gain: { value: 1 }, connect() {} };
  }
  createBufferSource() {
    return {
      playbackRate: { value: 1 },
      connect() {},
      disconnect() {},
      stop() {},
      start: (...args) => { this.starts.push(args); },
    };
  }
  async decodeAudioData() {
    return { duration: 30 };
  }
  async resume() {}
  async close() {}
}

test("failed reference never enables Both but User-only remains available", async () => {
  const context = new FakeAudioContext();
  const transport = new SharedAudioTransport({
    createContext: () => context,
    fetcher: async (url) => ({
      ok: url.includes("user"),
      status: 500,
      async arrayBuffer() { return new ArrayBuffer(8); },
    }),
  });
  await transport.load(
    { user: "/user.wav", reference: "/reference.wav" },
    { mapping, mode: "full", automaticLatencySeconds: 1, manualOffsetSeconds: 0 },
  );
  assert.equal(transport.state().canPlay, false);
  transport.setMix("user");
  assert.equal(transport.state().canPlay, true);
  await transport.play();
  assert.equal(transport.state().playing, true);
  transport.pause();
  assert.equal(transport.state().playing, false);
  transport.dispose();
});

test("mix presets and gains mute only the intended source", () => {
  const context = new FakeAudioContext();
  const transport = new SharedAudioTransport({ createContext: () => context });
  transport.setVolumes(0.4, 0.6);
  transport.setMix("user");
  assert.equal(transport.gains.user.gain.value, 0.4);
  assert.equal(transport.gains.reference.gain.value, 0);
  transport.setMix("reference");
  assert.equal(transport.gains.user.gain.value, 0);
  assert.equal(transport.gains.reference.gain.value, 0.6);
  transport.dispose();
});

test("pause and resume recreate sources from one canonical cursor", async () => {
  const context = new FakeAudioContext();
  const transport = new SharedAudioTransport({
    createContext: () => context,
    fetcher: async () => ({
      ok: true,
      status: 200,
      async arrayBuffer() { return new ArrayBuffer(8); },
    }),
  });
  await transport.load(
    { user: "/user.wav", reference: "/reference.wav" },
    { mapping, mode: "full", automaticLatencySeconds: 1, manualOffsetSeconds: 0 },
  );
  await transport.play();
  const firstSourceCount = context.starts.length;
  context.currentTime += 0.4;
  transport.pause();
  const pausedAt = transport.cursor;
  await transport.play();
  assert.ok(context.starts.length > firstSourceCount);
  assert.ok(Math.abs(transport.anchorCanonical - pausedAt) < 1e-12);
  transport.pause();
  transport.dispose();
});

test("gain changes do not reschedule or desynchronize active sources", async () => {
  const context = new FakeAudioContext();
  const transport = new SharedAudioTransport({
    createContext: () => context,
    fetcher: async () => ({
      ok: true,
      status: 200,
      async arrayBuffer() { return new ArrayBuffer(8); },
    }),
  });
  await transport.load(
    { user: "/user.wav", reference: "/reference.wav" },
    { mapping, mode: "full", automaticLatencySeconds: 1, manualOffsetSeconds: 0 },
  );
  await transport.play();
  const starts = context.starts.map((entry) => entry[0]);
  transport.setVolumes(0.2, 0.9);
  assert.deepEqual(context.starts.map((entry) => entry[0]), starts);
  assert.equal(transport.state().playing, true);
  transport.pause();
  transport.dispose();
});

test("rapid practice-target switching replaces the active loop atomically", () => {
  const context = new FakeAudioContext();
  const transport = new SharedAudioTransport({ createContext: () => context });
  transport.setLoop({ start: 2, end: 4 });
  transport.setLoop({ start: 8, end: 11 });
  assert.deepEqual(transport.loop, { start: 8, end: 11 });
  assert.equal(transport.cursor, 8);
  transport.dispose();
});

test("disposed transports cannot overwrite readiness after a project switch", async () => {
  const context = new FakeAudioContext();
  const responses = [];
  const emitted = [];
  const transport = new SharedAudioTransport({
    createContext: () => context,
    onState: (state) => emitted.push(state),
    fetcher: () => new Promise((resolve) => responses.push(resolve)),
  });
  const loading = transport.load(
    { user: "/user.wav", reference: "/reference.wav" },
    { mapping, mode: "full", automaticLatencySeconds: 1, manualOffsetSeconds: 0 },
  );
  await Promise.resolve();
  const emissionCount = emitted.length;
  transport.dispose();
  responses.forEach((resolve) => resolve({
    ok: true,
    status: 200,
    async arrayBuffer() { return new ArrayBuffer(8); },
  }));
  await loading;
  assert.equal(emitted.length, emissionCount);
});

test("play at the canonical end restarts instead of scheduling silence", async () => {
  const context = new FakeAudioContext();
  const transport = new SharedAudioTransport({
    createContext: () => context,
    fetcher: async () => ({
      ok: true,
      status: 200,
      async arrayBuffer() { return new ArrayBuffer(8); },
    }),
  });
  await transport.load(
    { user: "/user.wav", reference: "/reference.wav" },
    { mapping, mode: "full", automaticLatencySeconds: 1, manualOffsetSeconds: 0 },
  );
  transport.cursor = mapping.canonical_time.at(-1);
  await transport.play();
  assert.equal(transport.anchorCanonical, 0);
  assert.ok(context.starts.length > 0);
  transport.pause();
  transport.dispose();
});
