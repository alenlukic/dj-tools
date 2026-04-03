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
