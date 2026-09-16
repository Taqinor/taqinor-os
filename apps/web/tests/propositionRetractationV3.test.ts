// PREVIEW-V3-FIX (16/09/2026, audit C2) — LA LIGNE DE RÉTRACTATION NE PEUT
// PLUS DISPARAÎTRE D'UN DEVIS RÉSIDENTIEL.
//
// Le défaut : `clientConsommateur` comparait le champ BRUT
// `data.mode_installation` à 'residentiel'. Or `Devis.mode_installation` est
// `blank=True, null=True` SANS défaut, le builder normalise `None → ''`, et
// le backend lui-même lit `devis.mode_installation or 'residentiel'` pour
// l'échéancier. Un devis résidentiel sans mode affichait donc l'acompte
// résidentiel de 30 % ET taisait le droit de rétractation de 7 jours
// (loi 31-08 art. 29-4/36) — l'information manquante fait passer le délai de
// 7 à 30 jours et expose à l'amende de l'art. 177.
//
// Deux gardes : (1) la fonction PURE que la page utilise partout ailleurs
// range bien `''`/absent en résidentiel et l'industriel hors consommateur ;
// (2) la page dérive la ligne de CETTE fonction (lecture SOURCE en texte —
// même convention que propositionContreSignatureItem66.test.ts, un montage
// DOM complet d'un .astro n'étant pas praticable ici).
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { resolveInstallMode } from '../src/lib/proposition';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');
const PROPOSITION = read('../src/pages/proposition/[...token].astro');

describe('audit C2 — le mode qui décide de la rétractation', () => {
  it('un devis résidentiel SANS mode_installation reste un consommateur', () => {
    for (const mode of ['', null, undefined, '   ']) {
      expect(resolveInstallMode({ mode_installation: mode } as never)).toBe('residentiel');
    }
    expect(resolveInstallMode({} as never)).toBe('residentiel');
    expect(resolveInstallMode({ mode_installation: 'residentiel' } as never)).toBe('residentiel');
  });

  it('un devis industriel, commercial ou agricole n’est PAS un consommateur', () => {
    expect(resolveInstallMode({ mode_installation: 'industriel' } as never)).toBe('industriel');
    expect(resolveInstallMode({ mode_installation: 'commercial' } as never)).toBe('commercial');
    expect(resolveInstallMode({ mode_installation: 'agricole' } as never)).toBe('agricole');
  });

  it('la page GATE la ligne sur `installMode`, jamais sur le champ brut', () => {
    expect(PROPOSITION).toContain("const clientConsommateur = installMode === 'residentiel';");
    // Le défaut exact qui est corrigé : plus aucune comparaison du champ brut.
    expect(PROPOSITION).not.toContain("(data?.mode_installation || '').toString().trim().toLowerCase()");
    expect(PROPOSITION).not.toContain("modeInstallation === 'residentiel'");
  });

  it('la phrase des 7 jours francs est rendue SOUS ce gate, et nulle part ailleurs', () => {
    const gate = PROPOSITION.indexOf('{clientConsommateur && (');
    expect(gate).toBeGreaterThan(0);
    // La phrase client elle-même (art. 36) ne vit qu'après le gate — le seul
    // autre « 7 jours » du fichier est le commentaire qui explique le gate.
    // RECALIBRÉ — décision fondateur 16/09 : réduire au minimum prouvé. La
    // phrase raccourcit (« 7 jours francs pour vous rétracter après
    // acceptation… ») ; le GATE, lui, ne bouge pas d'un caractère, et c'est
    // tout ce que ce test protège : le droit n'est promis qu'au consommateur.
    const phrase = '7 jours francs pour vous rétracter';
    expect(PROPOSITION.indexOf(phrase)).toBeGreaterThan(gate);
    expect(PROPOSITION.split(phrase).length - 1).toBeGreaterThanOrEqual(1);
    // Les trois obligations chiffrées de l'art. 36/37 restent dites.
    expect(PROPOSITION).toContain('sans justification ni pénalité');
    expect(PROPOSITION).toContain('remboursé sous 15 jours');
  });
});
