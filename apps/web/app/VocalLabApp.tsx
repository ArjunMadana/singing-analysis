"use client";

/* API payloads retain forward-compatible measurement fields at this UI boundary. */
/* eslint-disable @typescript-eslint/no-explicit-any */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { TimelineCanvas } from "./TimelineCanvas";
import {
  acceptsPracticeShortcut,
  comparisonVerdict,
  normalizeLoop,
  processingLabel,
  stepDiscrepancy,
  validStreamRoles,
} from "./lib/practice-state.mjs";
import {
  SharedAudioTransport,
  mapWaveformToCanonical,
  mappedSourceTime,
  transportDiagnostics,
} from "./lib/shared-transport.mjs";
import {
  createImportDraft,
  createInspectedImportDraft,
  importDraftForProject,
  type ImportDraft,
} from "./lib/import-draft.mjs";

const API = process.env.NEXT_PUBLIC_VOCALLAB_API ?? "http://127.0.0.1:8000";
const STAGES = [
  "extraction",
  "reference_preparation",
  "pitch_tracking",
  "note_generation",
  "synchronization",
  "alignment",
  "transposition",
  "scoring",
  "visualization",
];

type Project = {
  id: string;
  title: string;
  artist: string;
  take_count: number;
  active_baseline_version: number | null;
  last_analyzed_at: string | null;
  detected_transposition: number | null;
  transposition_reliable: boolean;
  latest_scoring_mode: string | null;
  warnings: string[];
  latest_metrics?: Record<string, number>;
};
type Take = { id: string; status: string; imported_at: string; analysis: any };
type Stream = {
  index: number;
  codec: string;
  channels: number;
  sample_rate: number;
  duration_seconds: number;
  title?: string;
  statistics: { rms: number; peak: number; silence_ratio: number };
  suggested_role: string;
  preview_url: string;
};
type Inspection = { token: string; filename: string; streams: Stream[] };
type TransportState = {
  playing: boolean;
  canPlay: boolean;
  readiness: Record<string, { status: string; error: string | null }>;
  error: string | null;
};
type Note = {
  start_seconds: number;
  end_seconds: number;
  attack_end_seconds: number;
  release_start_seconds: number;
  midi_pitch: number;
  cents_offset: number;
  confidence: number;
  phrase_id: string;
  ornamental: boolean;
  scored: boolean;
  source: string;
};
type ScoringMode =
  | "original_pitch"
  | "transposition_adjusted"
  | "octave_invariant"
  | "interval_contour";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail ?? "VocalLab request failed.");
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export function VocalLabApp() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [takes, setTakes] = useState<Take[]>([]);
  const [take, setTake] = useState<Take | null>(null);
  const [importDraft, setImportDraft] = useState<ImportDraft<Inspection>>(
    () => createImportDraft<Inspection>(),
  );
  const [job, setJob] = useState<any>(null);
  const [visualization, setVisualization] = useState<any>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [filter, setFilter] = useState("all");
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [loop, setLoop] = useState<{ start: number; end: number } | null>(null);
  const [loopEnabled, setLoopEnabled] = useState(true);
  const [userVolume, setUserVolume] = useState(1);
  const [referenceVolume, setReferenceVolume] = useState(0.75);
  const [cursor, setCursor] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState(0);
  const [notes, setNotes] = useState<Note[]>([]);
  const [noteHistory, setNoteHistory] = useState<Note[][]>([]);
  const [redoHistory, setRedoHistory] = useState<Note[][]>([]);
  const [selectedNote, setSelectedNote] = useState(0);
  const [baselineVersions, setBaselineVersions] = useState<any[]>([]);
  const [preRoll, setPreRoll] = useState(0.75);
  const [postRoll, setPostRoll] = useState(0.75);
  const [comparison, setComparison] = useState<any>(null);
  const [loopPreset, setLoopPreset] = useState("note_context");
  const [playbackMode, setPlaybackMode] = useState<"raw" | "constant">("constant");
  const [mix, setMix] = useState<"user" | "reference" | "both">("both");
  const [manualOffset, setManualOffset] = useState(0);
  const [separatorMode, setSeparatorMode] = useState<"fallback" | "demucs">("fallback");
  const [scoringMode, setScoringMode] = useState<ScoringMode>("original_pitch");
  const [scoringView, setScoringView] = useState<any>(null);
  const [selectedShift, setSelectedShift] = useState(0);
  const [manualShift, setManualShift] = useState(0);
  const [timelineTool, setTimelineTool] = useState<"seek" | "loop">("seek");
  const [showOriginal, setShowOriginal] = useState(true);
  const [showShifted, setShowShifted] = useState(true);
  const [showUser, setShowUser] = useState(true);
  const [capabilities, setCapabilities] = useState<any>(null);
  const [transportState, setTransportState] = useState<TransportState>({
    playing: false,
    canPlay: false,
    readiness: {
      user: { status: "idle", error: null },
      reference: { status: "idle", error: null },
    },
    error: null,
  });
  const transport = useRef<SharedAudioTransport | null>(null);

  const loadProjects = useCallback(async () => {
    setProjects(await request<Project[]>("/api/projects"));
  }, []);

  const loadProject = useCallback(async (id: string, preferredTake?: string) => {
    transport.current?.pause();
    setImportOpen(false);
    setImportDraft(createImportDraft<Inspection>(id));
    setVisualization(null);
    setSelectedIndex(-1);
    setLoop(null);
    setCursor(0);
    const data = await request<Project & { takes: Take[] }>(`/api/projects/${id}`);
    setProject(data);
    setTakes(data.takes);
    const next =
      data.takes.find((item) => item.id === preferredTake) ??
      [...data.takes].reverse().find((item) => item.analysis) ??
      data.takes.at(-1) ??
      null;
    setTake(next);
  }, []);

  const openImportDialog = useCallback(() => {
    if (!project) return;
    setImportDraft(createImportDraft<Inspection>(project.id));
    setImportOpen(true);
  }, [project]);

  useEffect(() => {
    // Initial data synchronization with the local service.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadProjects().catch((reason) => setError(reason.message));
    request("/api/capabilities").then(setCapabilities).catch((reason) => setError(reason.message));
  }, [loadProjects]);

  useEffect(() => {
    if (!project || !take?.analysis) {
      return;
    }
    Promise.all([
      request(`/api/projects/${project.id}/takes/${take.id}/visualization`),
      request<{ notes: Note[]; versions: any[] }>(`/api/projects/${project.id}/baseline`),
    ])
      .then(([view, baseline]) => {
        setVisualization(view);
        const nextScoring = take.analysis.scoring ?? null;
        setScoringView(nextScoring);
        setScoringMode(nextScoring?.default_mode ?? "original_pitch");
        setSelectedShift(
          nextScoring?.selected_shift ??
            take.analysis.transposition?.best_shift ??
            0,
        );
        setManualShift(
          nextScoring?.selected_shift ??
            take.analysis.transposition?.best_shift ??
            0,
        );
        setNotes(baseline.notes);
        setBaselineVersions(baseline.versions);
        setNoteHistory([]);
        setRedoHistory([]);
      })
      .catch((reason) => setError(reason.message));
  }, [project, take]);

  useEffect(() => {
    const current = transport.current;
    current?.dispose();
    transport.current = null;
    if (!project || !take?.analysis || !visualization?.transport) return;
    const next = new SharedAudioTransport({
      onState: (state: TransportState) => {
        setTransportState(state);
        if (state.error) setError(state.error);
      },
    });
    transport.current = next;
    const savedOffset = visualization.transport.manual_offset_seconds ?? 0;
    next.setMix(mix);
    next.setVolumes(userVolume, referenceVolume);
    next.load(
      {
        user: `${API}/api/projects/${project.id}/takes/${take.id}/audio/user`,
        reference: `${API}/api/projects/${project.id}/takes/${take.id}/audio/reference`,
      },
      {
        mapping: visualization.transport.mapping,
        mode: playbackMode,
        systemOffsetSeconds:
          visualization.transport.diagnostics.system_reference_offset_seconds ?? 0,
        automaticLatencySeconds:
          visualization.transport.diagnostics.microphone_latency_seconds ?? 0,
        manualOffsetSeconds: savedOffset,
      },
    ).then(() => setManualOffset(savedOffset));
    return () => {
      next.dispose();
      if (transport.current === next) transport.current = null;
    };
    // Transport is intentionally recreated only when the analyzed take changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project?.id, take?.id, visualization]);

  useEffect(() => {
    if (!transportState.playing) return;
    let animation = 0;
    const updateCursor = () => {
      if (transport.current) setCursor(transport.current.currentCanonicalTime());
      animation = window.requestAnimationFrame(updateCursor);
    };
    animation = window.requestAnimationFrame(updateCursor);
    return () => window.cancelAnimationFrame(animation);
  }, [transportState.playing]);

  useEffect(() => {
    if (!job || ["completed", "failed", "cancelled"].includes(job.status)) return;
    const timer = window.setInterval(async () => {
      const current = await request<any>(`/api/jobs/${job.id}`);
      setJob(current);
      if (current.status === "completed" && project) {
        await loadProject(project.id, current.take_id);
        await loadProjects();
      }
      if (current.status === "failed") setError(current.error);
    }, 500);
    return () => window.clearInterval(timer);
  }, [job, loadProject, loadProjects, project]);

  const practiceTargets = useMemo(() => {
    const items = visualization?.practice_targets ?? [];
    if (filter === "all") return items;
    const groups: Record<string, string[]> = {
      center: ["flat", "sharp"],
      attack: ["began", "settled"],
      drift: ["drift", "unstable"],
      timing: ["early", "late", "release"],
      mismatch: ["wrong", "octave", "missing", "extra"],
      confidence: ["confidence", "contaminated"],
    };
    return items.filter((target: any) =>
      target.measurements.some((item: any) =>
        (groups[filter] ?? []).some((term) => item.kind.includes(term)),
      ),
    );
  }, [filter, visualization]);

  const displayWaveforms = useMemo(() => {
    if (!visualization?.waveforms || !visualization?.transport?.mapping) {
      return visualization?.waveforms;
    }
    return {
      reference: mapWaveformToCanonical(
        visualization.waveforms.reference,
        visualization.transport.mapping,
        "reference_time",
        playbackMode,
        visualization.transport.diagnostics.system_reference_offset_seconds ?? 0,
      ),
      user: mapWaveformToCanonical(
        visualization.waveforms.user,
        visualization.transport.mapping,
        "user_time",
        playbackMode,
        visualization.transport.diagnostics.system_reference_offset_seconds ?? 0,
        visualization.transport.diagnostics.microphone_latency_seconds ?? 0,
        manualOffset,
      ),
    };
  }, [manualOffset, playbackMode, visualization]);
  const duration = displayWaveforms?.reference?.duration ?? 0;

  const selectDiscrepancy = useCallback(
    (
      index: number,
      selectedPreset = loopPreset,
      selectedPreRoll = preRoll,
      selectedPostRoll = postRoll,
    ) => {
      const target = practiceTargets[index];
      if (!target) return;
      const preset = target.loop_presets?.[selectedPreset] ?? {
        start: target.loop_start_seconds,
        end: target.loop_end_seconds,
      };
      const range = normalizeLoop(
        preset.start - Math.max(0, selectedPreRoll - 0.75),
        preset.end + Math.max(0, selectedPostRoll - 0.75),
        duration,
      );
      setSelectedIndex(index);
      setLoop(range);
      setCursor(range.start);
      setZoom(Math.max(1, duration / Math.max(2.5, range.end - range.start + 1)));
      setPan(Math.max(0, range.start - 0.5));
      transport.current?.setLoop(range, true);
    },
    [duration, loopPreset, postRoll, practiceTargets, preRoll],
  );

  const togglePlay = useCallback(async () => {
    if (!transport.current) return;
    if (transportState.playing) transport.current.pause();
    else await transport.current.play();
  }, [transportState.playing]);

  useEffect(() => {
    const keyboard = (event: KeyboardEvent) => {
      if (!acceptsPracticeShortcut((event.target as HTMLElement)?.tagName ?? "")) return;
      if (event.code === "Space") {
        event.preventDefault();
        togglePlay();
      } else if (event.key.toLowerCase() === "l") setLoopEnabled((value) => !value);
      else if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        const direction = event.key === "ArrowRight" ? 1 : -1;
        if (event.shiftKey) transport.current?.seek(Math.max(0, cursor + direction));
        else selectDiscrepancy(stepDiscrepancy(selectedIndex, practiceTargets.length, direction));
      } else if (event.key.toLowerCase() === "r" && loop) {
        transport.current?.seek(loop.start);
      } else if (event.key === "Escape") {
        setLoop(null);
        setSelectedIndex(-1);
        transport.current?.setLoop(null);
      }
    };
    window.addEventListener("keydown", keyboard);
    return () => window.removeEventListener("keydown", keyboard);
  }, [cursor, loop, practiceTargets.length, selectDiscrepancy, selectedIndex, togglePlay]);

  const runAnalysis = async (
    takeId: string,
    selectedSeparator = separatorMode,
    refreshReference = false,
  ) => {
    if (!project) return;
    setError("");
    const response = await request<{ job_id: string }>(
      `/api/projects/${project.id}/takes/${takeId}/analyze`,
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          separator: selectedSeparator,
          refresh_reference: refreshReference,
        }),
      },
    );
    setJob({ id: response.job_id, status: "queued", stages: {}, take_id: takeId });
  };

  const mutateNotes = (next: Note[]) => {
    setNoteHistory((history) => [...history, notes]);
    setRedoHistory([]);
    setNotes(next);
  };

  const selectedTarget =
    selectedIndex >= 0 ? practiceTargets[selectedIndex] ?? null : null;
  const modes = scoringView?.modes ?? {};
  const selectedScoring = modes[scoringMode] ?? null;
  const scoringReferenceLabel = ({
    original_artist_pitch: "the original artist contour",
    transposition_shifted_reference: "the shifted reference contour",
    octave_equivalent_reference: "the nearest octave-equivalent reference",
    relative_contour: "relative interval and contour movement",
  } as Record<string, string>)[selectedScoring?.scoring_reference] ?? "an unavailable legacy view";
  const detectedReliable =
    take?.analysis?.transposition?.reliable ??
    scoringView?.transposition_reliable ??
    false;
  const applyScoringShift = async (shift?: number) => {
    if (!project || !take) return;
    const query = shift === undefined ? "" : `?shift=${shift}`;
    const result = await request<any>(
      `/api/projects/${project.id}/takes/${take.id}/scoring${query}`,
    );
    setScoringView(result.scoring);
    setScoringMode(result.scoring.default_mode);
    setSelectedShift(result.scoring.selected_shift);
    setManualShift(result.scoring.selected_shift);
    setVisualization((current: any) => ({
      ...current,
      discrepancies: result.discrepancies,
      practice_targets: result.practice_targets,
    }));
    setSelectedIndex(-1);
    setLoop(null);
    transport.current?.setLoop(null);
  };
  const playbackDiagnostics = visualization?.transport
    ? transportDiagnostics(
        {
          mapping: visualization.transport.mapping,
          mode: playbackMode,
          systemOffsetSeconds:
            visualization.transport.diagnostics.system_reference_offset_seconds ?? 0,
          automaticLatencySeconds:
            visualization.transport.diagnostics.microphone_latency_seconds ?? 0,
          manualOffsetSeconds: manualOffset,
        },
        cursor,
      )
    : null;

  return (
    <main className="app-shell">
      <aside className="library">
        <header className="brand">
          <div className="brand-mark">VL</div>
          <div><strong>VocalLab</strong><small>Private practice analysis</small></div>
        </header>
        <button className="primary wide" onClick={() => setCreateOpen(true)}>＋ New song project</button>
        <nav className="project-list" aria-label="Song projects">
          {projects.map((item) => (
            <button
              key={item.id}
              className={`project-card ${project?.id === item.id ? "active" : ""}`}
              onClick={() => loadProject(item.id).catch((reason) => setError(reason.message))}
            >
              <span><strong>{item.title}</strong><small>{item.artist}</small></span>
              <span className="project-meta">{item.take_count} takes</span>
              <span className="project-meta">
                {item.last_analyzed_at
                  ? `Analyzed ${new Date(item.last_analyzed_at).toLocaleDateString()}`
                  : "Not analyzed"}
                {item.detected_transposition !== null
                  ? item.transposition_reliable
                    ? ` · ${item.detected_transposition >= 0 ? "+" : ""}${item.detected_transposition} st`
                    : " · key uncertain"
                  : ""}
              </span>
              <span className="project-meta">
                {item.active_baseline_version
                  ? `Baseline v${item.active_baseline_version}`
                  : "No baseline"}
                {item.latest_metrics?.median_absolute_cents !== undefined
                  ? ` · ${item.latest_metrics.median_absolute_cents.toFixed(1)}¢ ${
                      item.latest_scoring_mode === "transposition_adjusted"
                        ? "key-adjusted error"
                        : "original-pitch frame error"
                    }`
                  : ""}
              </span>
              {item.warnings.length > 0 && <span className="warning-dot" title="Quality warning" />}
            </button>
          ))}
        </nav>
        <footer>Local only · no uploads to cloud</footer>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <span className="eyebrow">ANALYSIS WORKSPACE</span>
            <h1>{project ? project.title : "Choose a song project"}</h1>
            <p>{project?.artist ?? "Create a project to begin a private practice session."}</p>
          </div>
          {project && (
            <div className="top-actions">
              <select
                aria-label="Selected take"
                value={take?.id ?? ""}
                onChange={(event) => {
                  transport.current?.pause();
                  setVisualization(null);
                  setSelectedIndex(-1);
                  setLoop(null);
                  setCursor(0);
                  setTake(takes.find((item) => item.id === event.target.value) ?? null);
                }}
              >
                {takes.map((item, index) => <option key={item.id} value={item.id}>Take {index + 1} · {item.status}</option>)}
              </select>
              <button className="secondary danger" onClick={async () => {
                const confirmation = window.prompt(`Type "${project.title}" to delete this project.`);
                if (confirmation !== project.title) return;
                await request(`/api/projects/${project.id}`, {
                  method: "DELETE",
                  headers: { "content-type": "application/json" },
                  body: JSON.stringify({ confirmation }),
                });
                setProject(null);
                setTake(null);
                await loadProjects();
              }}>Delete</button>
              <button className="primary" onClick={openImportDialog}>Import take</button>
            </div>
          )}
        </header>

        {error && <div className="error-banner"><strong>Couldn’t complete that action.</strong> {error}<button onClick={() => setError("")}>Dismiss</button></div>}

        {!project && <EmptyState onCreate={() => setCreateOpen(true)} />}

        {project && takes.length === 0 && (
          <EmptyState onCreate={openImportDialog} importMode />
        )}

        {project && take && !take.analysis && !job && (
          <section className="panel centered">
            <span className="eyebrow">TAKE READY</span>
            <h2>Build the first analysis</h2>
            <p>VocalLab will prepare the reference, align your microphone track, and preserve every artifact locally.</p>
            <button className="primary" onClick={() => runAnalysis(take.id).catch((reason) => setError(reason.message))}>Analyze this take</button>
          </section>
        )}

        {job && !["completed", "failed"].includes(job.status) && (
          <Processing job={job} onCancel={async () => {
            const result = await request<{ cancelled: boolean; message: string }>(
              `/api/jobs/${job.id}/cancel`,
              { method: "POST" },
            );
            if (!result.cancelled) setError(result.message);
          }} />
        )}

        {project && take?.analysis && visualization && (
          <>
            <section className="summary-strip">
              <Metric label="Original-pitch frame error" value={`${modes.original_pitch?.metrics?.median_absolute_cents?.toFixed(1) ?? "—"}¢`} />
              <Metric
                label="Detected key difference"
                value={detectedReliable
                  ? `${take.analysis.transposition.best_shift >= 0 ? "+" : ""}${take.analysis.transposition.best_shift} st`
                  : "uncertain"}
              />
              <Metric
                label="Key-adjusted residual"
                value={scoringView?.transposition_reliable
                  ? `${modes.transposition_adjusted?.metrics?.median_absolute_cents?.toFixed(1) ?? "—"}¢`
                  : "choose key"}
              />
              <Metric label="Alignment confidence" value={`${(take.analysis.alignment.confidence * 100).toFixed(0)}%`} />
              <Metric label="Baseline" value={`v${take.analysis.baseline_version}${take.analysis.baseline_reused ? " reused" : " new"}`} />
            </section>

            {take.analysis.warnings?.map((warning: string) => <div className="warning-banner" key={warning}>⚠ {warning}</div>)}

            <section className="reference-mode panel">
              <div className="active-reference">
                <span className="eyebrow">ACTIVE REFERENCE · BASELINE v{take.analysis.baseline_version}</span>
                <strong>
                  {take.analysis.reference_processing?.engine ?? "Unknown engine"}
                  {take.analysis.reference_processing?.provisional ? " · provisional scoring" : ""}
                </strong>
                <small>
                  This provenance describes the reference currently used for scoring.
                </small>
              </div>
              <div className="next-reference">
                <label>Next rebuild method
                  <select
                    aria-label="Next reference rebuild method"
                    value={separatorMode}
                    onChange={(event) => setSeparatorMode(event.target.value as "fallback" | "demucs")}
                  >
                    <option value="fallback">Full mix fallback</option>
                    <option value="demucs" disabled={!capabilities?.demucs?.compatible}>
                      Demucs htdemucs
                    </option>
                  </select>
                </label>
                <small>This choice does not change the active baseline until you rebuild.</small>
                <button
                  className="secondary"
                  disabled={separatorMode === "demucs" && !capabilities?.demucs?.compatible}
                  onClick={() => runAnalysis(take.id, separatorMode, true).catch((reason) => setError(reason.message))}
                >
                  Rebuild as new baseline
                </button>
              </div>
              {!capabilities?.demucs?.installed && (
                <code>{capabilities?.demucs?.install_command}</code>
              )}
            </section>

            <section className="panel scoring-panel">
              <div>
                <span className="eyebrow">SCORING VIEW</span>
                <h2>{selectedScoring?.title ?? "Reanalyze for explicit scoring"}</h2>
                <p>
                  {scoringMode === "original_pitch"
                    ? "Frame-by-frame distance from the artist pitch contour; this is not a detected key difference."
                    : selectedScoring?.description ?? "This stored analysis predates the explicit scoring model."}
                </p>
                <small>Scoring against {scoringReferenceLabel}.</small>
                {selectedScoring?.available === false && (
                  <small className="confidence">Unavailable until a coherent key is detected or you apply a manual global shift.</small>
                )}
                {selectedScoring?.metrics?.median_absolute_cents !== undefined && (
                  <strong>{selectedScoring.metrics.median_absolute_cents.toFixed(1)}¢ median absolute difference</strong>
                )}
                {selectedScoring?.metrics?.within_25_cents_percentage !== undefined && (
                  <small>{selectedScoring.metrics.within_25_cents_percentage.toFixed(1)}% within ±25¢ across {selectedScoring.metrics.voiced_frame_count} voiced frames</small>
                )}
                {scoringMode === "original_pitch" && !detectedReliable && (
                  <small className="confidence">
                    No coherent global pitch shift was found. This median can hide
                    incompatible pitch and octave clusters and should not rank takes
                    by itself.
                  </small>
                )}
                {scoringMode === "interval_contour" &&
                  selectedScoring?.metrics?.contour_direction_agreement_percentage !== undefined && (
                    <>
                      <strong>{selectedScoring.metrics.median_absolute_interval_error_cents.toFixed(1)}¢ median interval error</strong>
                      <small>{selectedScoring.metrics.contour_direction_agreement_percentage.toFixed(0)}% contour-direction agreement across {selectedScoring.metrics.transition_count} transitions</small>
                    </>
                  )}
                {scoringMode === "octave_invariant" &&
                  selectedScoring?.metrics?.median_octave_displacement !== undefined && (
                    <small>Median octave placement: {selectedScoring.metrics.median_octave_displacement >= 0 ? "+" : ""}{selectedScoring.metrics.median_octave_displacement.toFixed(1)} octaves</small>
                  )}
              </div>
              <div className="scoring-controls">
                <label>Compare as
                  <select value={scoringMode} onChange={(event) => setScoringMode(event.target.value as ScoringMode)}>
                    <option value="original_pitch">Original absolute pitch</option>
                    <option value="transposition_adjusted">Key-adjusted melody</option>
                    <option value="octave_invariant">Octave-invariant melody</option>
                    <option value="interval_contour">Interval and contour</option>
                  </select>
                </label>
                <label>Global shift
                  <input
                    className="small-number"
                    type="number"
                    min="-12"
                    max="12"
                    step="1"
                    value={manualShift}
                    onChange={(event) => setManualShift(Number(event.target.value))}
                  />
                </label>
                <button className="secondary" onClick={() => applyScoringShift(manualShift).catch((reason) => setError(reason.message))}>Apply manual key</button>
                <button className="secondary" onClick={() => applyScoringShift().catch((reason) => setError(reason.message))}>Use detection</button>
                <small>
                  Detection: {take.analysis.transposition.support_percentage.toFixed(1)}% support
                  · {take.analysis.transposition.support_margin_percentage?.toFixed(1) ?? "0.0"} point margin
                  · runner-up {take.analysis.transposition.second_best_shift >= 0 ? "+" : ""}{take.analysis.transposition.second_best_shift} st
                </small>
                {!detectedReliable && <small className="confidence">No coherent global key was detected. Manual key selection enables note-level adjusted feedback without rerunning audio analysis.</small>}
                <small>Practice targets use the active key-adjusted scoring reference, not the currently selected summary view.</small>
              </div>
            </section>

            <section className="panel timeline-panel">
              <div className="panel-heading">
                <div><span className="eyebrow">PITCH & TIMING</span><h2>Performance timeline</h2></div>
                <div className="legend"><span className="reference">Original artist</span><span className="shifted-reference">Shifted reference</span><span className="user">Your take</span></div>
              </div>
              <div className="timeline-tools">
                <div className="mix-presets" aria-label="Timeline interaction">
                  <button className={timelineTool === "seek" ? "active" : ""} onClick={() => setTimelineTool("seek")}>Seek / listen</button>
                  <button className={timelineTool === "loop" ? "active" : ""} onClick={() => setTimelineTool("loop")}>Create / resize loop</button>
                  <button onClick={() => {
                    setLoop(null);
                    setSelectedIndex(-1);
                    transport.current?.setLoop(null);
                  }}>Clear loop</button>
                </div>
                <div className="contour-toggles">
                  <label><input type="checkbox" checked={showOriginal} onChange={(event) => setShowOriginal(event.target.checked)} /> Original</label>
                  <label><input type="checkbox" checked={showShifted} onChange={(event) => setShowShifted(event.target.checked)} /> Shifted</label>
                  <label><input type="checkbox" checked={showUser} onChange={(event) => setShowUser(event.target.checked)} /> User</label>
                </div>
                <small>{timelineTool === "seek" ? "Click to move playback. This mode never creates a loop." : "Drag empty space to create a loop; drag either gold edge to resize it. A click does nothing."}</small>
              </div>
              <TimelineCanvas
                waveforms={displayWaveforms}
                pitch={visualization.pitch}
                notes={visualization.notes ?? notes}
                cursor={cursor}
                loop={loop}
                zoom={zoom}
                pan={pan}
                tool={timelineTool}
                selectedShift={selectedShift}
                scoringMode={scoringMode}
                showOriginal={showOriginal}
                showShifted={showShifted}
                showUser={showUser}
                onSeek={(time) => {
                  const target = Math.min(Math.max(0, time), duration);
                  setCursor(target);
                  transport.current?.seek(target);
                }}
                onLoopSelect={(start, end) => {
                  const range = normalizeLoop(start, end, duration);
                  setSelectedIndex(-1);
                  setLoopPreset("custom");
                  setLoop(range);
                  setCursor(range.start);
                  transport.current?.setLoop(range, true);
                }}
              />
              <div className="source-readiness" aria-live="polite">
                {(["user", "reference"] as const).map((source) => (
                  <span
                    key={source}
                    className={transportState.readiness[source]?.status ?? "idle"}
                  >
                    {source}: {transportState.readiness[source]?.status ?? "idle"}
                    {transportState.readiness[source]?.error
                      ? ` · ${transportState.readiness[source].error}`
                      : ""}
                  </span>
                ))}
              </div>
              <div className="transport">
                <button
                  className="transport-button"
                  disabled={!transportState.canPlay}
                  onClick={() => togglePlay().catch((reason) => setError(reason.message))}
                >
                  {transportState.playing ? "Ⅱ" : "▶"}
                </button>
                <button
                  className={loopEnabled ? "toggle active" : "toggle"}
                  onClick={() => {
                    const enabled = !loopEnabled;
                    setLoopEnabled(enabled);
                    transport.current?.setLoopEnabled(enabled);
                  }}
                >
                  Loop
                </button>
                <span className="time">{cursor.toFixed(2)} / {duration.toFixed(2)}s</span>
                <div className="mix-presets" aria-label="Playback mix">
                  {(["user", "reference", "both"] as const).map((value) => (
                    <button
                      key={value}
                      className={mix === value ? "active" : ""}
                      onClick={() => {
                        setMix(value);
                        transport.current?.setMix(value);
                      }}
                    >
                      {value === "user" ? "User only" : value === "reference" ? "Reference only" : "Both"}
                    </button>
                  ))}
                </div>
                <label>User volume/mix <input type="range" min="0" max="1" step=".05" value={userVolume} onChange={(event) => { const value = Number(event.target.value); setUserVolume(value); transport.current?.setVolumes(value, referenceVolume); }} /></label>
                <label>Reference volume/mix <input type="range" min="0" max="1" step=".05" value={referenceVolume} onChange={(event) => { const value = Number(event.target.value); setReferenceVolume(value); transport.current?.setVolumes(userVolume, value); }} /></label>
                <label>Pre-roll <input className="small-number" type="number" min="0" max="2" step=".05" value={preRoll} onChange={(event) => {
                  const value = Number(event.target.value);
                  setPreRoll(value);
                  if (selectedIndex >= 0 && loopPreset !== "custom") {
                    selectDiscrepancy(selectedIndex, loopPreset, value, postRoll);
                  }
                }} /></label>
                <label>Post-roll <input className="small-number" type="number" min="0" max="2" step=".05" value={postRoll} onChange={(event) => {
                  const value = Number(event.target.value);
                  setPostRoll(value);
                  if (selectedIndex >= 0 && loopPreset !== "custom") {
                    selectDiscrepancy(selectedIndex, loopPreset, preRoll, value);
                  }
                }} /></label>
                <label>Loop size
                  <select value={loopPreset} onChange={(event) => {
                    const value = event.target.value;
                    setLoopPreset(value);
                    if (selectedIndex >= 0 && value !== "custom") {
                      selectDiscrepancy(selectedIndex, value, preRoll, postRoll);
                    }
                  }}>
                    <option value="note_context">Note context</option>
                    <option value="short_phrase">Short phrase</option>
                    <option value="full_phrase">Full phrase</option>
                    <option value="custom">Custom</option>
                  </select>
                </label>
                <label>Zoom <input type="range" min="1" max="12" step=".25" value={zoom} onChange={(event) => setZoom(Number(event.target.value))} /></label>
                <label>Pan <input type="range" min="0" max={Math.max(0, duration - duration / zoom)} step=".1" value={pan} onChange={(event) => setPan(Number(event.target.value))} /></label>
              </div>
              <div className="diagnostic-controls">
                <label>Playback correction
                  <select
                    value={playbackMode}
                    onChange={(event) => {
                      const mode = event.target.value as "raw" | "constant";
                      setPlaybackMode(mode);
                      transport.current?.setMode(mode);
                    }}
                  >
                    <option value="raw">Raw simultaneous</option>
                    <option value="constant">Constant offset corrected</option>
                  </select>
                </label>
                <span className="confidence">
                  Playback uses timestamp shifts only. Both recordings remain at
                  1.0× speed.
                </span>
                <label className="manual-offset">
                  Diagnostic microphone offset {manualOffset >= 0 ? "+" : ""}{manualOffset.toFixed(2)}s
                  <input
                    type="range"
                    min="-2"
                    max="2"
                    step=".01"
                    value={manualOffset}
                    onChange={(event) => {
                      const value = Number(event.target.value);
                      setManualOffset(value);
                      transport.current?.setManualOffset(value);
                    }}
                  />
                </label>
                <button
                  className="secondary"
                  onClick={() => request(
                    `/api/projects/${project.id}/takes/${take.id}/playback-offset`,
                    {
                      method: "PUT",
                      headers: { "content-type": "application/json" },
                      body: JSON.stringify({ offset_seconds: manualOffset }),
                    },
                  ).catch((reason) => setError(reason.message))}
                >
                  Save for this take
                </button>
              </div>
              <details className="diagnostics">
                <summary>Advanced synchronization diagnostics</summary>
                <dl>
                  <dt>System-reference offset</dt><dd>{visualization.transport.diagnostics.system_reference_offset_seconds.toFixed(3)}s</dd>
                  <dt>Estimated microphone-device latency</dt><dd>{visualization.transport.diagnostics.microphone_latency_seconds.toFixed(3)}s</dd>
                  <dt>Selected latency evidence</dt><dd>{visualization.transport.diagnostics.microphone_latency_method}</dd>
                  <dt>Pitch latency candidate</dt><dd>{visualization.transport.diagnostics.pitch_latency_seconds.toFixed(3)}s · {(visualization.transport.diagnostics.pitch_latency_confidence * 100).toFixed(0)}%</dd>
                  <dt>Energy latency candidate</dt><dd>{visualization.transport.diagnostics.energy_latency_seconds.toFixed(3)}s · {(visualization.transport.diagnostics.energy_latency_confidence * 100).toFixed(0)}%</dd>
                  <dt>Candidate disagreement</dt><dd>{visualization.transport.diagnostics.latency_candidate_disagreement_seconds.toFixed(3)}s</dd>
                  <dt>Mapped user time at cursor</dt><dd>{playbackDiagnostics?.userTime.toFixed(3)}s</dd>
                  <dt>Mapped reference time at cursor</dt><dd>{playbackDiagnostics?.referenceTime.toFixed(3)}s</dd>
                  <dt>Total effective playback offset</dt><dd>{playbackDiagnostics?.totalEffectiveOffset.toFixed(3)}s</dd>
                  <dt>Matched coverage</dt><dd>{(visualization.transport.diagnostics.matched_coverage * 100).toFixed(0)}%</dd>
                  <dt>Calibrated confidence</dt><dd>{(visualization.transport.diagnostics.alignment_confidence * 100).toFixed(0)}%</dd>
                  {loop && <>
                    <dt>Mapped user loop start</dt><dd>{mappedSourceTime(visualization.transport.mapping, loop.start, "user", playbackMode, visualization.transport.diagnostics.microphone_latency_seconds, manualOffset, visualization.transport.diagnostics.system_reference_offset_seconds).toFixed(3)}s</dd>
                    <dt>Mapped user loop end</dt><dd>{mappedSourceTime(visualization.transport.mapping, loop.end, "user", playbackMode, visualization.transport.diagnostics.microphone_latency_seconds, manualOffset, visualization.transport.diagnostics.system_reference_offset_seconds).toFixed(3)}s</dd>
                  </>}
                </dl>
              </details>
            </section>

            <div className="analysis-grid">
              <section className="panel discrepancies">
                <div className="panel-heading"><div><span className="eyebrow">PRACTICE TARGETS</span><h2>Actionable regions</h2></div><strong>{practiceTargets.length}</strong></div>
                <div className="filters">
                  {["all", "center", "attack", "drift", "timing", "mismatch", "confidence"].map((item) => <button className={filter === item ? "active" : ""} key={item} onClick={() => {
                    setFilter(item);
                    setSelectedIndex(-1);
                    setLoop(null);
                    transport.current?.setLoop(null);
                  }}>{item}</button>)}
                </div>
                <ol>
                  {practiceTargets.map((target: any, index: number) => {
                    const item = target.measurements[0];
                    return (
                    <li key={target.id} className={selectedIndex === index ? "selected" : ""}>
                      <button onClick={() => selectDiscrepancy(index)}>
                        <span className="discrepancy-time">Error measured {target.measurement_start_seconds.toFixed(2)}–{target.measurement_end_seconds.toFixed(2)}s</span>
                        <strong>{item.kind}</strong>
                        <p>{item.explanation}</p>
                        <span className="confidence">Practice loop {target.loop_start_seconds.toFixed(2)}–{target.loop_end_seconds.toFixed(2)}s · {target.measurements.length} measurement{target.measurements.length === 1 ? "" : "s"}</span>
                        {item.target_midi !== null && item.target_midi !== undefined && (
                          <span className="confidence">
                            Target MIDI {item.target_midi.toFixed(2)} · user {item.user_midi.toFixed(2)}
                          </span>
                        )}
                        <span className="confidence">{target.provisional ? "Provisional · " : ""}{item.magnitude.toFixed(0)}¢ · {Math.round(target.confidence * 100)}% confidence</span>
                      </button>
                    </li>
                  )})}
                  {practiceTargets.length === 0 && <li className="empty-list">No sufficiently reliable practice target crossed the current threshold.</li>}
                </ol>
              </section>

              <section className="panel detail">
                <span className="eyebrow">SELECTED REGION</span>
                <h2>{selectedTarget ? selectedTarget.measurements[0].kind : "Choose a practice target"}</h2>
                <p>{selectedTarget ? selectedTarget.measurements[0].explanation : "Select a practice target to set its musical loop and inspect the underlying measurement."}</p>
                {selectedTarget && loop && <>
                  <div className="loop-readout"><span>Error measured</span><strong>{selectedTarget.measurement_start_seconds.toFixed(2)}–{selectedTarget.measurement_end_seconds.toFixed(2)}s</strong></div>
                  <div className="loop-readout"><span>Practice loop</span><strong>{loop.start.toFixed(2)}–{loop.end.toFixed(2)}s</strong></div>
                </>}
                <div className="provenance">
                  <span>Device latency</span>
                  <strong>{take.analysis.alignment.microphone_latency_seconds?.toFixed(3) ?? "0.000"}s</strong>
                  <span>Octave displacement</span>
                  <strong>{take.analysis.transposition.octave_shift >= 0 ? "+" : ""}{take.analysis.transposition.octave_shift} st</strong>
                </div>
                <div className="cache-list">{take.analysis.cache_events?.map((item: any) => <span key={`${item.stage}-${item.status}`}>{item.stage}: {item.status}</span>)}</div>
                <div className="shortcut-list"><kbd>Space</kbd> play/pause <kbd>L</kbd> loop <kbd>←</kbd><kbd>→</kbd> targets <kbd>R</kbd> replay</div>
              </section>
            </div>

            <section className="panel tools-panel">
              <details>
                <summary>Compare takes</summary>
                <Comparison project={project} takes={takes} onResult={setComparison} />
                {comparison && <ComparisonResult data={comparison} />}
              </details>
              <details>
                <summary>Review baseline notes · version {take.analysis.baseline_version}</summary>
                <BaselineEditor
                  notes={notes}
                  selected={selectedNote}
                  setSelected={setSelectedNote}
                  onChange={mutateNotes}
                  undo={() => {
                    const prior = noteHistory.at(-1);
                    if (prior) { setRedoHistory((history) => [...history, notes]); setNotes(prior); setNoteHistory((history) => history.slice(0, -1)); }
                  }}
                  redo={() => {
                    const next = redoHistory.at(-1);
                    if (next) { setNoteHistory((history) => [...history, notes]); setNotes(next); setRedoHistory((history) => history.slice(0, -1)); }
                  }}
                  canUndo={noteHistory.length > 0}
                  canRedo={redoHistory.length > 0}
                  versions={baselineVersions}
                  activate={async (baselineId: string) => {
                    await request(`/api/projects/${project.id}/baseline/${baselineId}/activate`, { method: "POST" });
                    await runAnalysis(take.id);
                  }}
                  save={async () => {
                    await request(`/api/projects/${project.id}/baseline/versions`, {
                      method: "POST",
                      headers: { "content-type": "application/json" },
                      body: JSON.stringify({ take_id: take.id, notes }),
                    });
                    await runAnalysis(take.id);
                  }}
                />
              </details>
              <details>
                <summary>Compare reference-pitch versions</summary>
                <ReferenceVersionComparison
                  key={baselineVersions.map((item) => item.id).join("-")}
                  versions={baselineVersions}
                />
              </details>
            </section>
          </>
        )}
      </section>

      {createOpen && <CreateProject close={() => setCreateOpen(false)} created={async (created) => { await loadProjects(); await loadProject(created.id); setCreateOpen(false); }} />}
      {importOpen && project && <ImportDialog
        project={project}
        draft={importDraftForProject(importDraft, project.id)}
        setDraft={setImportDraft}
        close={() => {
          setImportOpen(false);
          setImportDraft(createImportDraft<Inspection>(project.id));
        }}
        imported={async (takeId) => {
          await loadProject(project.id, takeId);
          setImportOpen(false);
          setImportDraft(createImportDraft<Inspection>(project.id));
          setJob(null);
        }}
        runAnalysis={runAnalysis}
        setError={setError}
        busy={busy}
        setBusy={setBusy}
        separatorMode={separatorMode}
        setSeparatorMode={setSeparatorMode}
        capabilities={capabilities}
      />}
    </main>
  );
}

function EmptyState({ onCreate, importMode = false }: { onCreate: () => void; importMode?: boolean }) {
  return <section className="empty-state"><div className="empty-visual"><span>REF</span><i /><span>TAKE</span></div><span className="eyebrow">READY WHEN YOU ARE</span><h2>{importMode ? "Import your first take" : "Turn a take into a practice target"}</h2><p>{importMode ? "Choose an OBS recording with separate microphone and system-audio tracks." : "VocalLab identifies specific pitch differences, lets you loop them, and tracks whether the next attempt improved."}</p><button className="primary" onClick={onCreate}>{importMode ? "Choose recording" : "Create song project"}</button></section>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div><span>{label}</span><strong>{value}</strong></div>;
}

function Processing({ job, onCancel }: { job: any; onCancel: () => void }) {
  return <section className="panel processing"><span className="eyebrow">LOCAL ANALYSIS</span><h2>{processingLabel(job)}</h2><div className="stage-list"><div className="completed"><i /><span>inspection</span><small>completed</small></div>{STAGES.map((stage) => <div key={stage} className={job.stages?.[stage] ?? ""}><i /> <span>{stage.replaceAll("_", " ")}</span><small>{job.stages?.[stage] ?? "waiting"}</small></div>)}</div><button className="secondary" onClick={onCancel}>Request cancel</button></section>;
}

function CreateProject({ close, created }: { close: () => void; created: (project: Project) => void }) {
  const [title, setTitle] = useState("");
  const [artist, setArtist] = useState("");
  return <div className="modal-backdrop"><form className="modal" onSubmit={async (event) => { event.preventDefault(); created(await request<Project>("/api/projects", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ title, artist }) })); }}><span className="eyebrow">NEW SONG PROJECT</span><h2>What are you practicing?</h2><label>Song title<input autoFocus required value={title} onChange={(event) => setTitle(event.target.value)} /></label><label>Artist<input required value={artist} onChange={(event) => setArtist(event.target.value)} /></label><div className="modal-actions"><button type="button" className="secondary" onClick={close}>Cancel</button><button className="primary">Create project</button></div></form></div>;
}

function ImportDialog({ project, draft, setDraft, close, imported, runAnalysis, setError, busy, setBusy, separatorMode, setSeparatorMode, capabilities }: any) {
  const inspection: Inspection | null = draft.inspection;
  const roles: Record<number, string> = draft.roles;
  const inspect = async (file: File) => {
    setBusy(true);
    try {
      const data = await request<Inspection>(`/api/recordings/inspect?filename=${encodeURIComponent(file.name)}`, { method: "POST", headers: { "content-type": file.type || "application/octet-stream" }, body: file });
      setDraft(createInspectedImportDraft(project.id, data));
    } catch (reason: any) { setError(reason.message); } finally { setBusy(false); }
  };
  const mic = inspection?.streams.find((stream: Stream) => roles[stream.index] === "microphone");
  const reference = inspection?.streams.find((stream: Stream) => roles[stream.index] === "reference");
  return <div className="modal-backdrop"><div className="modal import-modal"><span className="eyebrow">IMPORT OBS RECORDING</span><h2>{inspection ? "Confirm stream roles" : "Choose a recording"}</h2>{!inspection ? <label className="dropzone"><input type="file" accept=".mkv,.mp4,.mov,.wav,.flac,.mp3,.m4a" onChange={(event) => event.target.files?.[0] && inspect(event.target.files[0])} /><strong>{busy ? "Inspecting locally…" : "Drop or choose a multistream recording"}</strong><small>The source file is never modified.</small></label> : <><div className="stream-list">{inspection.streams.map((stream) => <article key={stream.index}><div><strong>Stream {stream.index}</strong><small>{stream.title || "Untitled"} · {stream.codec} · {stream.channels}ch · {stream.sample_rate} Hz · {stream.duration_seconds?.toFixed(1)}s</small><small>RMS {(20 * Math.log10(Math.max(stream.statistics.rms, 1e-8))).toFixed(1)} dBFS · peak {(stream.statistics.peak * 100).toFixed(0)}%</small></div><audio controls preload="none" src={`${API}${stream.preview_url}`} /><select value={roles[stream.index]} onChange={(event) => setDraft({ ...draft, roles: { ...roles, [stream.index]: event.target.value } })}><option value="microphone">Microphone</option><option value="reference">Reference/system</option><option value="mixed">Mixed</option><option value="ignore">Ignore</option></select></article>)}</div><div className="reference-choice"><label>Reference processing<select value={separatorMode} onChange={(event) => setSeparatorMode(event.target.value)}><option value="fallback">Full mix fallback</option><option value="demucs" disabled={!capabilities?.demucs?.compatible}>Demucs htdemucs</option></select></label><small>{capabilities?.demucs?.installed ? `Installed: Demucs ${capabilities.demucs.version} · ${capabilities.demucs.model}` : "Demucs unavailable; full-mix results will be labeled provisional."}</small>{!capabilities?.demucs?.installed && <code>{capabilities?.demucs?.install_command}</code>}</div></>}<div className="modal-actions">{inspection && <button className="secondary" onClick={() => setDraft(createImportDraft(project.id))}>Choose different recording</button>}<button className="secondary" onClick={close}>Cancel</button>{inspection && <button className="primary" disabled={!validStreamRoles(roles) || (separatorMode === "demucs" && !capabilities?.demucs?.compatible)} onClick={async () => { try { const result = await request<{ take_id: string }>(`/api/projects/${project.id}/takes`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ recording_token: inspection.token, microphone_stream: mic.index, reference_stream: reference.index }) }); await imported(result.take_id); await runAnalysis(result.take_id, separatorMode); } catch (reason: any) { setError(reason.message); } }}>Import & analyze</button>}</div></div></div>;
}

function Comparison({ project, takes, onResult }: any) {
  const analyzed = takes.filter((item: Take) => item.analysis);
  const [first, setFirst] = useState(analyzed.at(-2)?.id ?? analyzed[0]?.id ?? "");
  const [second, setSecond] = useState(analyzed.at(-1)?.id ?? "");
  return <div className="comparison-controls"><select value={first} onChange={(event) => setFirst(event.target.value)}>{analyzed.map((item: Take, index: number) => <option value={item.id} key={item.id}>Take {index + 1}</option>)}</select><span>versus</span><select value={second} onChange={(event) => setSecond(event.target.value)}>{analyzed.map((item: Take, index: number) => <option value={item.id} key={item.id}>Take {index + 1}</option>)}</select><button className="secondary" disabled={!first || !second || first === second} onClick={async () => onResult(await request(`/api/projects/${project.id}/compare?first=${first}&second=${second}`))}>Compare</button></div>;
}

function ComparisonResult({ data }: any) {
  const first = data.metrics.first.median_absolute_cents;
  const second = data.metrics.second.median_absolute_cents;
  const verdict = comparisonVerdict(first, second, 1);
  const label = data.metrics_mode === "transposition_adjusted"
    ? "Key-adjusted median error"
    : data.metrics_mode === "original_pitch"
      ? "Original-pitch median frame error"
      : "Legacy median pitch metric";
  return <div className="comparison-result"><div><span>{label}</span><strong>{first.toFixed(1)}¢ → {second.toFixed(1)}¢</strong><small className={verdict}>{verdict === "improved" ? `${(first - second).toFixed(1)}¢ improvement` : verdict === "worsened" ? `${(second - first).toFixed(1)}¢ worse` : verdict}</small></div><div><span>Practice targets</span><strong>{data.improved.length} improved · {data.resolved.length} resolved</strong><small>{data.worsened.length} worsened · {data.introduced.length} new</small></div><ComparisonContours contours={data.contours} />{data.improved.slice(0, 4).map((item: any) => <p key={`${item.before.kind}-${item.before.start_seconds}`}>{item.before.kind}: {item.before.magnitude.toFixed(0)}¢ → {item.after.magnitude.toFixed(0)}¢ at {item.before.start_seconds.toFixed(2)}s.</p>)}</div>;
}

function ComparisonContours({ contours }: any) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const element = canvas.current;
    if (!element || !contours) return;
    const context = element.getContext("2d");
    if (!context) return;
    const width = element.width;
    const height = element.height;
    context.clearRect(0, 0, width, height);
    const all = [...contours.first.user_midi, ...contours.second.user_midi].filter((value): value is number => value !== null);
    if (!all.length) return;
    const low = Math.min(...all) - 1;
    const high = Math.max(...all) + 1;
    const duration = Math.max(...contours.first.time, ...contours.second.time, 1);
    const draw = (series: any, color: string) => {
      context.strokeStyle = color;
      context.beginPath();
      let started = false;
      series.time.forEach((time: number, index: number) => {
        const value = series.user_midi[index];
        if (value === null) { started = false; return; }
        const x = time / duration * width;
        const y = height - (value - low) / (high - low) * height;
        if (started) context.lineTo(x, y); else context.moveTo(x, y);
        started = true;
      });
      context.stroke();
    };
    draw(contours.first, "#68c3df");
    draw(contours.second, "#f1a260");
  }, [contours]);
  return <canvas className="comparison-canvas" ref={canvas} width="700" height="130" aria-label="Overlaid take pitch contours" />;
}

function ReferenceVersionComparison({ versions }: { versions: any[] }) {
  const available = versions.filter((item) => item.pitch_preview);
  const [firstId, setFirstId] = useState(available[0]?.id ?? "");
  const [secondId, setSecondId] = useState(available.at(-1)?.id ?? "");
  const canvas = useRef<HTMLCanvasElement>(null);
  const first = available.find((item) => item.id === firstId);
  const second = available.find((item) => item.id === secondId);
  useEffect(() => {
    const element = canvas.current;
    if (!element || !first?.pitch_preview || !second?.pitch_preview) return;
    const context = element.getContext("2d");
    if (!context) return;
    const values = [
      ...first.pitch_preview.midi,
      ...second.pitch_preview.midi,
    ].filter((value): value is number => value !== null);
    context.clearRect(0, 0, element.width, element.height);
    if (!values.length) return;
    const low = Math.min(...values) - 1;
    const high = Math.max(...values) + 1;
    const duration = Math.max(
      ...first.pitch_preview.time,
      ...second.pitch_preview.time,
      1,
    );
    const draw = (preview: any, color: string) => {
      context.strokeStyle = color;
      context.beginPath();
      let started = false;
      preview.time.forEach((time: number, index: number) => {
        const value = preview.midi[index];
        if (value === null) { started = false; return; }
        const x = time / duration * element.width;
        const y = element.height - (value - low) / (high - low) * element.height;
        if (started) context.lineTo(x, y); else context.moveTo(x, y);
        started = true;
      });
      context.stroke();
    };
    draw(first.pitch_preview, "#69bdd6");
    draw(second.pitch_preview, "#eba05f");
  }, [first, second]);
  if (!available.length) return <p>No reference-pitch versions are available.</p>;
  return <div className="reference-comparison"><div className="comparison-controls"><label>First<select value={firstId} onChange={(event) => setFirstId(event.target.value)}>{available.map((item) => <option key={item.id} value={item.id}>v{item.version} · {item.engine}</option>)}</select></label><label>Second<select value={secondId} onChange={(event) => setSecondId(event.target.value)}>{available.map((item) => <option key={item.id} value={item.id}>v{item.version} · {item.engine}</option>)}</select></label></div><canvas ref={canvas} className="comparison-canvas" width="700" height="130" aria-label="Reference pitch version comparison" /><small className="confidence">Blue: v{first?.version} ({first?.engine}) · orange: v{second?.version} ({second?.engine})</small></div>;
}

function BaselineEditor({ notes, selected, setSelected, onChange, undo, redo, canUndo, canRedo, save, versions, activate }: any) {
  const note: Note | undefined = notes[selected];
  const update = (patch: Partial<Note>) => onChange(notes.map((item: Note, index: number) => index === selected ? { ...item, ...patch, source: "manual" } : item));
  return <div className="baseline-editor"><div className="version-row"><label>Active version <select value={versions.find((item: any) => item.active)?.id ?? ""} onChange={(event) => activate(event.target.value)}>{versions.map((item: any) => <option key={item.id} value={item.id}>Version {item.version} · {item.engine}</option>)}</select></label></div><div className="note-list">{notes.map((item: Note, index: number) => <button key={`${item.start_seconds}-${index}`} className={selected === index ? "active" : ""} onClick={() => setSelected(index)}>{item.start_seconds.toFixed(2)}s · MIDI {item.midi_pitch} {item.scored ? "" : "· unscored"}</button>)}</div>{note && <div className="note-form"><label>Start<input type="number" step=".01" value={note.start_seconds} onChange={(event) => update({ start_seconds: Number(event.target.value) })} /></label><label>End<input type="number" step=".01" value={note.end_seconds} onChange={(event) => update({ end_seconds: Number(event.target.value) })} /></label><label>Target MIDI<input type="number" step="1" min="0" max="127" value={note.midi_pitch} onChange={(event) => update({ midi_pitch: Number(event.target.value) })} /></label><label className="check"><input type="checkbox" checked={note.scored} onChange={(event) => update({ scored: event.target.checked })} /> Include in scoring</label></div>}<div className="baseline-actions"><button className="secondary" disabled={!canUndo} onClick={undo}>Undo</button><button className="secondary" disabled={!canRedo} onClick={redo}>Redo</button><button className="secondary" onClick={() => onChange([...notes, { start_seconds: 0, end_seconds: .5, attack_end_seconds: .08, release_start_seconds: .42, midi_pitch: 60, cents_offset: 0, confidence: 1, phrase_id: "manual", ornamental: false, scored: true, source: "manual" }])}>Add note</button><button className="secondary danger" disabled={!note} onClick={() => { onChange(notes.filter((_: Note, index: number) => index !== selected)); setSelected(Math.max(0, selected - 1)); }}>Delete</button><button className="primary" onClick={save}>Save new baseline version</button></div></div>;
}
