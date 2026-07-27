export function normalizeLoop(
  start: number,
  end: number,
  duration: number,
  minimum?: number,
): { start: number; end: number };
export function stepDiscrepancy(
  current: number,
  count: number,
  direction: number,
): number;
export function loopTarget(
  currentTime: number,
  loop: { start: number; end: number },
  enabled: boolean,
): number | null;
export function acceptsPracticeShortcut(
  tagName: string,
  isContentEditable?: boolean,
): boolean;
export function validStreamRoles(roles: Record<number, string>): boolean;
export function comparisonVerdict(
  before: number,
  after: number,
  confidence: number,
): "insufficient confidence" | "improved" | "worsened" | "unchanged";
export function processingLabel(job: {
  status: string;
  stage?: string;
}): string;
