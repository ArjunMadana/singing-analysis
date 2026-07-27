const NOTE_NAMES = [
  "C",
  "C♯",
  "D",
  "D♯",
  "E",
  "F",
  "F♯",
  "G",
  "G♯",
  "A",
  "A♯",
  "B",
];

export function midiNoteLabel(midi) {
  const rounded = Math.round(midi);
  const pitchClass = ((rounded % 12) + 12) % 12;
  const octave = Math.floor(rounded / 12) - 1;
  return `${NOTE_NAMES[pitchClass]}${octave}`;
}

export function pitchAxisTicks(low, high, pixelHeight, minimumSpacing = 13) {
  const span = Math.max(1, high - low);
  const pixelsPerSemitone = pixelHeight / span;
  const step = Math.max(1, Math.ceil(minimumSpacing / pixelsPerSemitone));
  const first = Math.ceil(low / step) * step;
  const ticks = [];
  for (let midi = first; midi <= high; midi += step) ticks.push(midi);
  return ticks;
}
