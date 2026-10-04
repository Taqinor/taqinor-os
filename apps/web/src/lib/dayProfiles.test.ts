import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { decalageMarocH, noteHoraire } from './dayProfiles';

describe('WJ117 — heure légale marocaine (décret 2.26.530)', () => {
  it('décalage 0 h le 21/09/2026 et +1 h le 19/09/2026', () => {
    expect(decalageMarocH(new Date('2026-09-21T12:00:00Z'))).toBe(0);
    expect(decalageMarocH(new Date('2026-09-19T12:00:00Z'))).toBe(1);
    expect(decalageMarocH(new Date('2027-07-01T12:00:00Z'))).toBe(0);
  });
  it('la note affichée suit le décalage', () => {
    expect(noteHoraire(new Date('2026-09-21T12:00:00Z'))).toContain('UTC+0');
    expect(noteHoraire(new Date('2026-09-19T12:00:00Z'))).toContain('UTC+1');
  });
  it('aucun « UTC+1 sauf Ramadan » servi', () => {
    const src = readFileSync(new URL('./dayProfiles.ts', import.meta.url), 'utf8');
    expect(src).not.toMatch(/RAMADAN_TZ_OFFSET_HOURS/);
    expect(src).not.toMatch(/SAUF pendant le Ramadan/);
    const page = readFileSync(new URL('../pages/proposition/[...token].astro', import.meta.url), 'utf8');
    expect(page).not.toMatch(/Morocco reverts to UTC\+0/);
  });
});
