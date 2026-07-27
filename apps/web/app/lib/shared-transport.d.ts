export type AlignmentMapping = {
  canonical_time: number[];
  reference_time: number[];
  user_time: number[];
};
export type TransportMode = "raw" | "constant" | "full";
export type TransportMix = "user" | "reference" | "both";
export type TransportOptions = {
  mapping: AlignmentMapping;
  mode: TransportMode;
  automaticLatencySeconds: number;
  manualOffsetSeconds: number;
};
export type SourceReadiness = Record<
  "user" | "reference",
  { status: string; error: string | null }
>;
export type SharedTransportState = {
  playing: boolean;
  cursor: number;
  readiness: SourceReadiness;
  mix: TransportMix;
  mode: TransportMode;
  canPlay: boolean;
  error: string | null;
  diagnostics: {
    referenceTime: number;
    userTime: number;
    localCorrection: number;
    totalEffectiveOffset: number;
  };
};
export type ScheduleSegment = {
  source: "user" | "reference";
  when: number;
  canonicalStart: number;
  canonicalEnd: number;
  sourceStart: number;
  sourceEnd: number;
  playbackRate: number;
};
export function interpolateMapping(
  mapping: AlignmentMapping,
  canonicalSeconds: number,
  sourceKey: "reference_time" | "user_time",
): number;
export function mappedSourceTime(
  mapping: AlignmentMapping,
  canonicalSeconds: number,
  source: "user" | "reference",
  mode: TransportMode,
  automaticLatencySeconds?: number,
  manualOffsetSeconds?: number,
): number;
export function canonicalTimeForSource(
  mapping: AlignmentMapping,
  sourceSeconds: number,
  sourceKey: "reference_time" | "user_time",
): number;
export function mapWaveformToCanonical<T extends {
  time: number[];
  minimum: number[];
  maximum: number[];
  duration: number;
}>(
  waveform: T,
  mapping: AlignmentMapping,
  sourceKey: "reference_time" | "user_time",
): T;
export function mappedWindow(
  options: TransportOptions,
  start: number,
  end: number,
): Record<string, number>;
export function buildSchedule(
  options: TransportOptions,
  start: number,
  end: number,
  startAt: number,
): ScheduleSegment[];
export function loopStartAt(epoch: number, iteration: number, duration: number): number;
export function transportDiagnostics(
  options: TransportOptions,
  canonicalSeconds: number,
): SharedTransportState["diagnostics"];
export function requiredSources(mix: TransportMix): string[];
export function sourcesReady(readiness: SourceReadiness, mix: TransportMix): boolean;
export function safeFullAlignmentRate(rate: number): boolean;
export class SharedAudioTransport {
  constructor(options?: {
    createContext?: () => AudioContext;
    fetcher?: typeof fetch;
    onState?: (state: SharedTransportState) => void;
  });
  load(
    urls: { user: string; reference: string },
    options: TransportOptions,
  ): Promise<void>;
  setMode(mode: TransportMode): void;
  setManualOffset(seconds: number): void;
  setMix(mix: TransportMix): void;
  setVolumes(user: number, reference: number): void;
  setLoop(loop: { start: number; end: number } | null, enabled?: boolean): void;
  setLoopEnabled(enabled: boolean): void;
  play(): Promise<void>;
  pause(): void;
  seek(seconds: number): void;
  currentCanonicalTime(): number;
  dispose(): void;
}
