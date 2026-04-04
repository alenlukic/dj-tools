import { describe, it, expect } from 'vitest';
import { formatFloat, formatScore, displayGenre } from './utils';

describe('formatFloat', () => {
  it('returns em-dash for null', () => {
    expect(formatFloat(null)).toBe('—');
  });

  it('returns em-dash for undefined', () => {
    expect(formatFloat(undefined)).toBe('—');
  });

  it('suppresses trailing zeroes', () => {
    expect(formatFloat(1.0)).toBe('1');
    expect(formatFloat(1.1)).toBe('1.1');
    expect(formatFloat(1.10)).toBe('1.1');
  });

  it('rounds to 2 decimal places', () => {
    expect(formatFloat(1.126)).toBe('1.13');
    expect(formatFloat(1.124)).toBe('1.12');
  });

  it('handles zero', () => {
    expect(formatFloat(0)).toBe('0');
  });
});

describe('formatScore', () => {
  it('returns em-dash for null', () => {
    expect(formatScore(null)).toBe('—');
  });

  it('scales to 100 and suppresses trailing zeroes', () => {
    expect(formatScore(1.0)).toBe('100');
    expect(formatScore(0.9)).toBe('90');
    expect(formatScore(0.612)).toBe('61.2');
    expect(formatScore(0.6124)).toBe('61.24');
  });

  it('does not include percent sign', () => {
    expect(formatScore(0.5)).not.toContain('%');
  });

  it('handles zero', () => {
    expect(formatScore(0)).toBe('0');
  });
});

describe('displayGenre', () => {
  it('returns null for null input', () => {
    expect(displayGenre(null)).toBeNull();
  });

  it('returns null for undefined input', () => {
    expect(displayGenre(undefined)).toBeNull();
  });

  it('strips family prefix with ---', () => {
    expect(displayGenre('Rock---Grindcore')).toBe('Grindcore');
  });

  it('strips nested prefixes using last ---', () => {
    expect(displayGenre('Electronic---House---Deep House')).toBe('Deep House');
  });

  it('returns genre as-is when no --- present', () => {
    expect(displayGenre('Techno')).toBe('Techno');
  });

  it('handles empty string', () => {
    expect(displayGenre('')).toBe('');
  });
});
