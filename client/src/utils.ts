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
