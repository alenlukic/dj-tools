/**
 * Strip metadata prefixes (e.g. `[01B - B - 089.00]`) from track titles for display.
 * Mirrors the Python `extract_unformatted_title()` from `src/data_management/utils.py`.
 */
const MD_COMPOSITE_RE = /\[\d{2}[AB]\s-\s[A-Za-z#]{1,3}\s-\s\d{1,3}\.\d{1,2}]/;

export function cleanTitle(title: string): string {
  if (!MD_COMPOSITE_RE.test(title)) return title;
  const parts = title.split(MD_COMPOSITE_RE);
  const afterPrefix = parts[parts.length - 1].trim();
  const dashParts = afterPrefix.split(' - ');
  return dashParts.length > 1 ? dashParts.slice(1).join(' - ') : afterPrefix;
}

export function formatFloat(value: number | null | undefined): string {
  if (value == null) return '—';
  return parseFloat(value.toFixed(2)).toString();
}

/**
 * Format a 0–1 factor score for display on a 0–100 integer scale.
 * Standard half-up rounding, no decimal places, no percent sign.
 */
export function formatScore(value: number | null | undefined): string {
  if (value == null) return '—';
  return Math.round(value * 100).toString();
}

/**
 * Format an already-0–100 overall score as an integer.
 * Use this for `overall_score` which the API returns pre-scaled.
 */
export function formatOverallScore(value: number | null | undefined): string {
  if (value == null) return '—';
  return Math.round(value).toString();
}

export function displayGenre(genre: string | null | undefined): string | null {
  if (genre == null) return null;
  const idx = genre.lastIndexOf('---');
  return idx >= 0 ? genre.substring(idx + 3) : genre;
}

// Checkpoint table is static — hoisted to avoid re-allocation on every call.
const FILL_PTS: [number, number][] = [
  [0, 0], [5, 25], [10, 45], [15, 60], [20, 70], [25, 75],
];

export function gaugeWeightToFill(weight: number): number {
  /*
   * Piecewise-linear mapping: weight (0–100) → visual fill % (0–100).
   * Low weights are amplified so small values stay visible on the gauge arc.
   * Above 25 the curve flattens to ~0.33 fill-% per weight unit.
   *
   * Checkpoints: 0→0  5→25  10→45  15→60  20→70  25→75
   * Tail:        fill = 75 + (weight − 25) × 25/75, clamped to 100
   */
  if (weight <= 0) return 0;
  if (weight >= 100) return 100;

  if (weight <= 25) {
    for (let i = 1; i < FILL_PTS.length; i++) {
      if (weight <= FILL_PTS[i][0]) {
        const [w0, f0] = FILL_PTS[i - 1];
        const [w1, f1] = FILL_PTS[i];
        return f0 + ((weight - w0) / (w1 - w0)) * (f1 - f0);
      }
    }
  }

  return Math.min(100, 75 + (weight - 25) * (25 / 75));
}

