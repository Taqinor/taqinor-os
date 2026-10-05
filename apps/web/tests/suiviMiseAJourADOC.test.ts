// ADOC132 — /suivi : « Mis à jour le » vient de `mis_a_jour_le` (jamais de
// `generated_at`) et l'étape Installation affiche sa vraie date. La donnée est
// l'EXEMPLE du contrat serveur (ADOC112) lu tel quel — aucune forme inventée.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { buildTimeline, libelleMiseAJour, type SuiviResponse } from '../src/lib/suivi';

const lire = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');
const contrat = JSON.parse(
  lire('../../../backend/django_core/apps/ventes/contract_samples/suivi_public.json'),
) as { exemple: SuiviResponse; exemple_aucun_jalon_fait: SuiviResponse };
const PAGE = lire('../src/pages/suivi/[token].astro');

describe('ADOC132 — libelleMiseAJour', () => {
  it('affiche la date de mis_a_jour_le, jamais celle de generated_at', () => {
    const data = contrat.exemple;
    expect(data.generated_at).toBeTruthy();
    expect(data.mis_a_jour_le).toBe('2026-10-02');
    const l = libelleMiseAJour(data);
    expect(l?.fr).toBe('Mis à jour le 02/10/2026');
    expect(l?.ar).toContain('02/10/2026');
    // generated_at ≠ mis_a_jour_le : le libellé ne contient pas la date technique.
    const gen = data.generated_at!.slice(0, 10).split('-').reverse().join('/');
    expect(l?.fr).not.toContain(gen);
  });

  it('une date mis_a_jour_le est rendue telle quelle (26/08/2026)', () => {
    const l = libelleMiseAJour({ mis_a_jour_le: '2026-08-26' });
    expect(l?.fr).toBe('Mis à jour le 26/08/2026');
  });

  it('null / absent / non ISO ⇒ aucune ligne « Mis à jour »', () => {
    expect(libelleMiseAJour(contrat.exemple_aucun_jalon_fait)).toBeNull();
    expect(libelleMiseAJour({ mis_a_jour_le: undefined })).toBeNull();
    expect(libelleMiseAJour({ mis_a_jour_le: 'signe' })).toBeNull();
    expect(libelleMiseAJour(null)).toBeNull();
  });

  it('l’étape Installation de l’exemple affiche le 02/10/2026', () => {
    const inst = buildTimeline(contrat.exemple, 'fr').find((s) => s.key === 'installation');
    expect(inst?.done).toBe(true);
    expect(inst?.dateLabel).toBe('02/10/2026');
  });

  it('la page lit libelleMiseAJour et plus formatSuiviDate(generated_at)', () => {
    expect(PAGE).toContain('libelleMiseAJour(data)');
    expect(PAGE).not.toMatch(/formatSuiviDate\(data\?*\.generated_at/);
  });
});
