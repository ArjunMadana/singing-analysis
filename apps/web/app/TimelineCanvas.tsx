"use client";

import { useEffect, useRef } from "react";
import { midiNoteLabel, pitchAxisTicks } from "./lib/music-display.mjs";
import { resolveTimelineGesture } from "./lib/timeline-interaction.mjs";

const PITCH_AXIS_WIDTH = 48;

type Waveform = {
  time: number[];
  minimum: number[];
  maximum: number[];
  duration: number;
};

type Pitch = {
  time: number[];
  reference_midi: (number | null)[];
  shifted_reference_midi?: (number | null)[];
  user_midi: (number | null)[];
  reference_confidence: number[];
  user_confidence: number[];
};

type Note = {
  start_seconds: number;
  end_seconds: number;
  midi_pitch: number;
  scored: boolean;
};

export function TimelineCanvas({
  waveforms,
  pitch,
  notes,
  cursor,
  loop,
  zoom,
  pan,
  tool,
  selectedShift,
  scoringMode,
  showOriginal,
  showShifted,
  showUser,
  onSeek,
  onLoopSelect,
}: {
  waveforms: { user: Waveform; reference: Waveform };
  pitch: Pitch;
  notes: Note[];
  cursor: number;
  loop: { start: number; end: number } | null;
  zoom: number;
  pan: number;
  tool: "seek" | "loop";
  selectedShift: number;
  scoringMode: string;
  showOriginal: boolean;
  showShifted: boolean;
  showUser: boolean;
  onSeek: (time: number) => void;
  onLoopSelect: (start: number, end: number) => void;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const drag = useRef<{
    x: number;
    time: number;
    handle: "start" | "end" | null;
  } | null>(null);
  const duration = Math.max(waveforms.user.duration, waveforms.reference.duration, 0.1);
  const visible = duration / zoom;
  const start = Math.min(Math.max(0, pan), Math.max(0, duration - visible));
  const end = start + visible;

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ratio = window.devicePixelRatio || 1;
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    const context = canvas.getContext("2d");
    if (!context) return;
    context.scale(ratio, ratio);
    context.clearRect(0, 0, width, height);
    context.fillStyle = "#0d151c";
    context.fillRect(0, 0, width, height);

    const shiftedReference = pitch.reference_midi.map((value) =>
      value === null ? null : value + selectedShift
    );
    const visiblePitch = [
      ...(showOriginal ? pitch.reference_midi : []),
      ...(showShifted ? shiftedReference : []),
      ...(showUser ? pitch.user_midi : []),
    ];
    const values = visiblePitch.filter(
      (value): value is number => value !== null,
    );
    const low = values.length ? Math.floor(Math.min(...values) - 2) : 48;
    const high = values.length ? Math.ceil(Math.max(...values) + 2) : 72;
    const pitchHeight = 155;
    const pitchBottom = height - 22;
    const pitchTop = pitchBottom - pitchHeight;
    const pitchY = (midi: number) =>
      pitchBottom - ((midi - low) / (high - low)) * pitchHeight;
    const plotWidth = Math.max(1, width - PITCH_AXIS_WIDTH);
    const x = (time: number) =>
      PITCH_AXIS_WIDTH + ((time - start) / (end - start)) * plotWidth;

    context.fillStyle = "#101b23";
    context.fillRect(0, pitchTop, PITCH_AXIS_WIDTH, pitchHeight);
    context.font = "10px ui-monospace";
    context.textAlign = "right";
    context.textBaseline = "middle";
    pitchAxisTicks(low, high, pitchHeight).forEach((midi) => {
      const y = pitchY(midi);
      context.strokeStyle = midi % 12 === 0 ? "#314652" : "#21333d";
      context.beginPath();
      context.moveTo(PITCH_AXIS_WIDTH, y);
      context.lineTo(width, y);
      context.stroke();
      context.fillStyle = midi % 12 === 0 ? "#adc4cf" : "#728894";
      context.fillText(midiNoteLabel(midi), PITCH_AXIS_WIDTH - 6, y);
    });
    context.textAlign = "left";
    context.textBaseline = "alphabetic";
    context.strokeStyle = "#314652";
    context.beginPath();
    context.moveTo(PITCH_AXIS_WIDTH, pitchTop);
    context.lineTo(PITCH_AXIS_WIDTH, pitchBottom);
    context.stroke();

    for (let second = Math.ceil(start); second <= end; second += 1) {
      context.strokeStyle = second % 5 === 0 ? "#263844" : "#192933";
      context.beginPath();
      context.moveTo(x(second), 0);
      context.lineTo(x(second), height);
      context.stroke();
      if (second % 5 === 0) {
        context.fillStyle = "#728894";
        context.font = "11px ui-monospace";
        context.fillText(`${second}s`, x(second) + 4, 15);
      }
    }

    if (loop) {
      context.fillStyle = "rgba(238, 179, 87, 0.12)";
      context.fillRect(x(loop.start), 0, x(loop.end) - x(loop.start), height);
    }

    const drawWave = (wave: Waveform, y: number, color: string) => {
      context.strokeStyle = color;
      context.globalAlpha = 0.5;
      context.beginPath();
      wave.time.forEach((time, index) => {
        if (time < start || time > end) return;
        context.moveTo(x(time), y + wave.minimum[index] * 34);
        context.lineTo(x(time), y + wave.maximum[index] * 34);
      });
      context.stroke();
      context.globalAlpha = 1;
    };
    drawWave(waveforms.reference, 58, "#63b6d2");
    drawWave(waveforms.user, 125, "#e9a05f");

    notes.forEach((note) => {
      if (note.end_seconds < start || note.start_seconds > end) return;
      context.fillStyle = note.scored ? "rgba(99,182,210,.12)" : "rgba(120,130,136,.08)";
      context.fillRect(
        x(note.start_seconds),
        pitchY(
          note.midi_pitch +
            (scoringMode === "transposition_adjusted" ? selectedShift : 0) +
            0.45,
        ),
        x(note.end_seconds) - x(note.start_seconds),
        Math.max(3, 0.9 * (155 / (high - low))),
      );
    });

    const drawPitch = (
      valuesToDraw: (number | null)[],
      confidence: number[],
      color: string,
      lineWidth = 1.6,
      dash: number[] = [],
    ) => {
      context.strokeStyle = color;
      context.lineWidth = lineWidth;
      context.setLineDash(dash);
      context.beginPath();
      let drawing = false;
      pitch.time.forEach((time, index) => {
        const midi = valuesToDraw[index];
        if (time < start || time > end || midi === null || confidence[index] < 0.35) {
          drawing = false;
          return;
        }
        const px = x(time);
        const py = pitchY(midi);
        if (!drawing) context.moveTo(px, py);
        else context.lineTo(px, py);
        drawing = true;
      });
      context.stroke();
      context.setLineDash([]);
    };
    if (showOriginal) {
      drawPitch(
        pitch.reference_midi,
        pitch.reference_confidence,
        scoringMode === "original_pitch" ? "#68c3df" : "#567988",
        scoringMode === "original_pitch" ? 2.4 : 1.1,
        scoringMode === "original_pitch" ? [] : [5, 4],
      );
    }
    if (showShifted) {
      drawPitch(
        shiftedReference,
        pitch.reference_confidence,
        scoringMode === "transposition_adjusted" ? "#7ce2c7" : "#598d82",
        scoringMode === "transposition_adjusted" ? 2.4 : 1.1,
        scoringMode === "transposition_adjusted" ? [] : [3, 4],
      );
    }
    if (showUser) {
      drawPitch(pitch.user_midi, pitch.user_confidence, "#f1a260", 2);
    }

    context.strokeStyle = "#f4e6c9";
    context.lineWidth = 1;
    context.beginPath();
    context.moveTo(x(cursor), 0);
    context.lineTo(x(cursor), height);
    context.stroke();
    if (loop) {
      context.fillStyle = "#eeb357";
      context.fillRect(x(loop.start) - 2, 0, 4, height);
      context.fillRect(x(loop.end) - 2, 0, 4, height);
    }
  }, [
    cursor,
    end,
    loop,
    notes,
    pitch,
    scoringMode,
    selectedShift,
    showOriginal,
    showShifted,
    showUser,
    start,
    waveforms,
  ]);

  const timeAt = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const plotWidth = Math.max(1, rect.width - PITCH_AXIS_WIDTH);
    const fraction = Math.min(
      1,
      Math.max(0, (event.clientX - rect.left - PITCH_AXIS_WIDTH) / plotWidth),
    );
    return start + fraction * (end - start);
  };

  return (
    <canvas
      ref={ref}
      className="timeline"
      aria-label={`${tool === "seek" ? "Seek" : "Loop selection"} timeline with original, shifted reference, and user pitch`}
      onPointerDown={(event) => {
        const rect = event.currentTarget.getBoundingClientRect();
        const pointerX = event.clientX - rect.left;
        const xForTime = (time: number) =>
          PITCH_AXIS_WIDTH +
          ((time - start) / (end - start)) *
            Math.max(1, rect.width - PITCH_AXIS_WIDTH);
        let handle: "start" | "end" | null = null;
        if (tool === "loop" && loop) {
          if (Math.abs(pointerX - xForTime(loop.start)) <= 10) handle = "start";
          else if (Math.abs(pointerX - xForTime(loop.end)) <= 10) handle = "end";
        }
        drag.current = { x: pointerX, time: timeAt(event), handle };
        event.currentTarget.setPointerCapture(event.pointerId);
      }}
      onPointerUp={(event) => {
        if (drag.current) {
          const rect = event.currentTarget.getBoundingClientRect();
          const gesture = resolveTimelineGesture({
            tool,
            startX: drag.current.x,
            endX: event.clientX - rect.left,
            startTime: drag.current.time,
            endTime: timeAt(event),
            handle: drag.current.handle,
            loop,
          });
          if (gesture.type === "seek") onSeek(gesture.time);
          else if (gesture.type === "loop") {
            onLoopSelect(gesture.start, gesture.end);
          }
        }
        drag.current = null;
      }}
      onPointerCancel={() => { drag.current = null; }}
    />
  );
}
