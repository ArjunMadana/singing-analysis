const LOOKAHEAD_SECONDS = 0.06;
const SEGMENT_SECONDS = 0.5;

export function interpolateMapping(mapping, canonicalSeconds, sourceKey) {
  const canonical = mapping?.canonical_time ?? [];
  const values = mapping?.[sourceKey] ?? [];
  if (!canonical.length || canonical.length !== values.length) return canonicalSeconds;
  if (canonicalSeconds <= canonical[0]) return values[0] + canonicalSeconds - canonical[0];
  const last = canonical.length - 1;
  if (canonicalSeconds >= canonical[last]) {
    return values[last] + canonicalSeconds - canonical[last];
  }
  let low = 0;
  let high = last;
  while (high - low > 1) {
    const middle = Math.floor((low + high) / 2);
    if (canonical[middle] <= canonicalSeconds) low = middle;
    else high = middle;
  }
  const span = canonical[high] - canonical[low];
  const ratio = span ? (canonicalSeconds - canonical[low]) / span : 0;
  return values[low] + ratio * (values[high] - values[low]);
}

export function mappedSourceTime(
  mapping,
  canonicalSeconds,
  source,
  mode,
  automaticLatencySeconds = 0,
  manualOffsetSeconds = 0,
) {
  const reference = interpolateMapping(mapping, canonicalSeconds, "reference_time");
  if (source === "reference") return reference;
  if (mode === "raw") return reference;
  if (mode === "constant") {
    return reference + automaticLatencySeconds + manualOffsetSeconds;
  }
  return (
    interpolateMapping(mapping, canonicalSeconds, "user_time") +
    manualOffsetSeconds
  );
}

export function mappedWindow(options, start, end) {
  const source = (kind, time) =>
    mappedSourceTime(
      options.mapping,
      time,
      kind,
      options.mode,
      options.automaticLatencySeconds,
      options.manualOffsetSeconds,
    );
  return {
    canonicalStart: start,
    canonicalEnd: end,
    referenceStart: source("reference", start),
    referenceEnd: source("reference", end),
    userStart: source("user", start),
    userEnd: source("user", end),
  };
}

export function buildSchedule(options, start, end, startAt) {
  const boundaries = [start];
  for (let cursor = start + SEGMENT_SECONDS; cursor < end; cursor += SEGMENT_SECONDS) {
    boundaries.push(cursor);
  }
  boundaries.push(end);
  const segments = [];
  for (let index = 0; index < boundaries.length - 1; index += 1) {
    const canonicalStart = boundaries[index];
    const canonicalEnd = boundaries[index + 1];
    const window = mappedWindow(options, canonicalStart, canonicalEnd);
    const canonicalDuration = canonicalEnd - canonicalStart;
    for (const source of ["reference", "user"]) {
      const sourceStart = window[`${source}Start`];
      const sourceEnd = window[`${source}End`];
      const sourceDuration = sourceEnd - sourceStart;
      segments.push({
        source,
        when: startAt + canonicalStart - start,
        canonicalStart,
        canonicalEnd,
        sourceStart,
        sourceEnd,
        playbackRate: sourceDuration / canonicalDuration,
      });
    }
  }
  return segments;
}

export function loopStartAt(epoch, iteration, duration) {
  return epoch + iteration * duration;
}

export function transportDiagnostics(options, canonicalSeconds) {
  const reference = mappedSourceTime(
    options.mapping,
    canonicalSeconds,
    "reference",
    options.mode,
    options.automaticLatencySeconds,
    options.manualOffsetSeconds,
  );
  const user = mappedSourceTime(
    options.mapping,
    canonicalSeconds,
    "user",
    options.mode,
    options.automaticLatencySeconds,
    options.manualOffsetSeconds,
  );
  const fullyMappedUser = mappedSourceTime(
    options.mapping,
    canonicalSeconds,
    "user",
    "full",
    options.automaticLatencySeconds,
    options.manualOffsetSeconds,
  );
  return {
    referenceTime: reference,
    userTime: user,
    localCorrection:
      fullyMappedUser - reference - options.automaticLatencySeconds -
      options.manualOffsetSeconds,
    totalEffectiveOffset: user - reference,
  };
}

export function requiredSources(mix) {
  if (mix === "user") return ["user"];
  if (mix === "reference") return ["reference"];
  return ["reference", "user"];
}

export function sourcesReady(readiness, mix) {
  return requiredSources(mix).every((source) => readiness[source]?.status === "ready");
}

export class SharedAudioTransport {
  constructor({ createContext, fetcher, onState } = {}) {
    const Context = globalThis.AudioContext ?? globalThis.webkitAudioContext;
    this.context = createContext ? createContext() : new Context();
    this.fetcher = fetcher ?? globalThis.fetch.bind(globalThis);
    this.onState = onState ?? (() => {});
    this.gains = {
      user: this.context.createGain(),
      reference: this.context.createGain(),
    };
    this.gains.user.connect(this.context.destination);
    this.gains.reference.connect(this.context.destination);
    this.readiness = {
      user: { status: "idle", error: null },
      reference: { status: "idle", error: null },
    };
    this.buffers = {};
    this.nodes = [];
    this.options = {
      mapping: { canonical_time: [], reference_time: [], user_time: [] },
      mode: "full",
      automaticLatencySeconds: 0,
      manualOffsetSeconds: 0,
    };
    this.mix = "both";
    this.volumes = { user: 1, reference: 0.75 };
    this.cursor = 0;
    this.playing = false;
    this.loop = null;
    this.loopEnabled = true;
    this.anchorContext = 0;
    this.anchorCanonical = 0;
    this.loopEpoch = 0;
    this.nextLoopIteration = 0;
    this.loopTimer = null;
    this.endTimer = null;
  }

  async load(urls, options) {
    this.stopNodes();
    this.options = { ...this.options, ...options };
    this.buffers = {};
    for (const source of ["user", "reference"]) {
      this.readiness[source] = { status: "loading", error: null };
    }
    this.emit();
    await Promise.all(
      ["user", "reference"].map(async (source) => {
        try {
          const response = await this.fetcher(urls[source]);
          if (!response.ok) throw new Error(`${source} audio returned HTTP ${response.status}`);
          const bytes = await response.arrayBuffer();
          this.buffers[source] = await this.context.decodeAudioData(bytes);
          this.readiness[source] = { status: "ready", error: null };
        } catch (error) {
          this.readiness[source] = {
            status: "error",
            error: error instanceof Error ? error.message : String(error),
          };
        }
        this.emit();
      }),
    );
  }

  setMode(mode) {
    this.options.mode = mode;
    if (this.playing) this.restart();
    else this.emit();
  }

  setManualOffset(seconds) {
    this.options.manualOffsetSeconds = seconds;
    if (this.playing) this.restart();
    else this.emit();
  }

  setMix(mix) {
    this.mix = mix;
    this.applyGains();
    if (this.playing && !sourcesReady(this.readiness, mix)) this.pause();
    this.emit();
  }

  setVolumes(user, reference) {
    this.volumes = { user, reference };
    this.applyGains();
    this.emit();
  }

  applyGains() {
    this.gains.user.gain.value = this.mix === "reference" ? 0 : this.volumes.user;
    this.gains.reference.gain.value =
      this.mix === "user" ? 0 : this.volumes.reference;
  }

  setLoop(loop, enabled = this.loopEnabled) {
    const wasPlaying = this.playing;
    const priorCursor = this.currentCanonicalTime();
    if (wasPlaying) this.pause();
    this.loop = loop;
    this.loopEnabled = enabled;
    this.cursor = loop ? loop.start : priorCursor;
    if (wasPlaying) this.play().catch((error) => this.fail(error));
    this.emit();
  }

  setLoopEnabled(enabled) {
    this.loopEnabled = enabled;
    if (this.playing) this.restart();
    this.emit();
  }

  async play() {
    if (this.playing) return;
    if (!sourcesReady(this.readiness, this.mix)) {
      const missing = requiredSources(this.mix)
        .filter((source) => this.readiness[source]?.status !== "ready")
        .join(" and ");
      throw new Error(`Playback is waiting for ${missing} audio.`);
    }
    await this.context.resume();
    this.playing = true;
    this.anchorCanonical = this.cursor;
    this.anchorContext = this.context.currentTime + LOOKAHEAD_SECONDS;
    try {
      if (this.loopEnabled && this.loop) {
        if (this.cursor < this.loop.start || this.cursor >= this.loop.end) {
          this.cursor = this.loop.start;
          this.anchorCanonical = this.cursor;
        }
        this.scheduleWindow(this.cursor, this.loop.end, this.anchorContext);
        this.loopEpoch = this.anchorContext + (this.loop.end - this.cursor);
        this.nextLoopIteration = 0;
        this.scheduleLoopLookahead();
      } else {
        const end = this.options.mapping.canonical_time.at(-1) ?? this.cursor;
        this.scheduleWindow(this.cursor, end, this.anchorContext);
        const remaining = Math.max(0, end - this.cursor);
        this.endTimer = globalThis.setTimeout(
          () => {
            this.cursor = end;
            this.playing = false;
            this.stopNodes();
            this.emit();
          },
          (remaining + LOOKAHEAD_SECONDS) * 1000,
        );
      }
    } catch (error) {
      this.fail(error);
      throw error;
    }
    this.emit();
  }

  pause() {
    if (this.playing) this.cursor = this.currentCanonicalTime();
    this.playing = false;
    this.stopNodes();
    this.emit();
  }

  seek(seconds) {
    const wasPlaying = this.playing;
    this.pause();
    this.cursor = Math.max(0, seconds);
    if (wasPlaying) this.play().catch((error) => this.fail(error));
    else this.emit();
  }

  restart() {
    const cursor = this.currentCanonicalTime();
    this.pause();
    this.cursor = cursor;
    this.play().catch((error) => this.fail(error));
  }

  currentCanonicalTime() {
    if (!this.playing) return this.cursor;
    const elapsed = Math.max(0, this.context.currentTime - this.anchorContext);
    if (this.loopEnabled && this.loop) {
      const duration = this.loop.end - this.loop.start;
      return this.loop.start + ((this.anchorCanonical - this.loop.start + elapsed) % duration);
    }
    return this.anchorCanonical + elapsed;
  }

  scheduleLoopLookahead() {
    if (!this.playing || !this.loop || !this.loopEnabled) return;
    const duration = this.loop.end - this.loop.start;
    while (
      loopStartAt(this.loopEpoch, this.nextLoopIteration, duration) <
      this.context.currentTime + duration * 2 + LOOKAHEAD_SECONDS
    ) {
      const when = loopStartAt(this.loopEpoch, this.nextLoopIteration, duration);
      if (when + duration > this.context.currentTime) {
        this.scheduleWindow(this.loop.start, this.loop.end, when);
      }
      this.nextLoopIteration += 1;
    }
    this.loopTimer = globalThis.setTimeout(
      () => this.scheduleLoopLookahead(),
      Math.max(25, duration * 500),
    );
  }

  scheduleWindow(start, end, startAt) {
    const required = new Set(requiredSources(this.mix));
    const schedule = buildSchedule(this.options, start, end, startAt).filter((segment) =>
      required.has(segment.source),
    );
    const pending = [];
    try {
      for (const segment of schedule) {
        const buffer = this.buffers[segment.source];
        const sourceStart = Math.max(0, segment.sourceStart);
        const sourceEnd = Math.min(buffer.duration, segment.sourceEnd);
        if (sourceEnd <= sourceStart || segment.playbackRate <= 0) continue;
        const node = this.context.createBufferSource();
        node.buffer = buffer;
        node.playbackRate.value = segment.playbackRate;
        node.connect(this.gains[segment.source]);
        node.start(segment.when, sourceStart, sourceEnd - sourceStart);
        pending.push(node);
      }
    } catch (error) {
      for (const node of pending) {
        try { node.stop(); } catch {}
      }
      throw error;
    }
    this.nodes.push(...pending);
  }

  stopNodes() {
    if (this.loopTimer !== null) {
      globalThis.clearTimeout(this.loopTimer);
      this.loopTimer = null;
    }
    if (this.endTimer !== null) {
      globalThis.clearTimeout(this.endTimer);
      this.endTimer = null;
    }
    for (const node of this.nodes) {
      try { node.stop(); } catch {}
      try { node.disconnect(); } catch {}
    }
    this.nodes = [];
  }

  fail(error) {
    this.playing = false;
    this.stopNodes();
    this.emit(error instanceof Error ? error.message : String(error));
  }

  state(error = null) {
    return {
      playing: this.playing,
      cursor: this.currentCanonicalTime(),
      readiness: this.readiness,
      mix: this.mix,
      mode: this.options.mode,
      canPlay: sourcesReady(this.readiness, this.mix),
      error,
      diagnostics: transportDiagnostics(this.options, this.currentCanonicalTime()),
    };
  }

  emit(error = null) {
    this.onState(this.state(error));
  }

  dispose() {
    this.pause();
    this.context.close?.();
  }
}
