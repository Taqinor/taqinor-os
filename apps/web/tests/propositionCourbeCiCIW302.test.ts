// CIW302 — Courbe du jour d'un devis C&I : celle du moteur C&I quand elle est servie, sinon
// aucune ; plus de forme générique 9 h-19 h ni de poste « 1x8 » par défaut.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolveCiCurve, consumptionProfile } from '../src/lib/proposalCurve';

const FORME_PROD = [0, 0, 0, 0, 0, 0.001, 0.02, 0.05, 0.07, 0.09, 0.1, 0.11, 0.12, 0.11, 0.1, 0.09, 0.07, 0.05, 0.02, 0.001, 0, 0, 0, 0].map(
  (v, _i, a) => v / a.reduce((x, y) => x + y, 0),
);
const FORME_CONS = Array.from({ length: 24 }, (_, h) => (h >= 7 && h < 21 ? 3 : 1)).map((v, _i, a) => v / a.reduce((x, y) => x + y, 0));

function payload(mode: string, courbes?: unknown) {
  return { mode_installation: mode, quote: {}, ...(courbes === undefined ? {} : { courbes_journalieres: courbes }) };
}

const SERVIE = {
  source: 'moteur_ci',
  note_horaire: 'heure civile marocaine',
  production: { ete: { forme: FORME_PROD, kwh_jour: 322.7, pic_kw: 36.73, source: 'moteur_ci' } },
  consommation: { ete: { forme: FORME_CONS, kwh_jour: 539.1, source: 'moteur_ci' } },
};

describe('CIW302 — resolveCiCurve', () => {
  it('commercial sans courbes_journalieres → null (jamais une forme générique)', () => {
    expect(resolveCiCurve(payload('commercial'))).toBeNull();
    expect(resolveCiCurve(payload('commercial', {}))).toBeNull();
  });

  it('industriel sans régime servi (profil seul, ni production ni consommation) → null, jamais 1x8', () => {
    const r = resolveCiCurve(
      payload('industriel', { source: 'moteur_ci', profil_suppose: true, etiquette_profil: 'profil type — estimation' }),
    );
    expect(r).toBeNull();
  });

  it('une courbe qui n\'est pas du moteur C&I est ignorée', () => {
    expect(resolveCiCurve(payload('commercial', { ...SERVIE, source: 'pvgis' }))).toBeNull();
    const { source: _s, ...sansSource } = SERVIE;
    expect(resolveCiCurve(payload('commercial', sansSource))).toBeNull();
  });

  it('courbe servie → séries reprises telles quelles', () => {
    const r = resolveCiCurve(payload('commercial', SERVIE))!;
    expect(r).not.toBeNull();
    expect(r.curves.production.ete?.forme).toEqual(FORME_PROD);
    expect(r.curves.production.ete?.kwhJour).toBe(322.7);
    expect(r.curves.production.ete?.picKw).toBe(36.73);
    expect(r.curves.consommation.ete?.forme).toEqual(FORME_CONS);
    expect(r.curves.consommation.ete?.kwhJour).toBe(539.1);
    expect(r.etiquette).toBeNull();
    expect(r.profilSuppose).toBe(false);
  });

  it('étiquette SERVIE « profil type — estimation » reprise telle quelle', () => {
    const r = resolveCiCurve(
      payload('industriel', { ...SERVIE, profil_suppose: true, etiquette_profil: 'profil type — estimation' }),
    )!;
    expect(r.etiquette).toBe('profil type — estimation');
    expect(r.profilSuppose).toBe(true);
  });

  it('une saison sans forme de consommation n\'est pas dessinée (aucune moitié de courbe)', () => {
    const r = resolveCiCurve(
      payload('commercial', {
        ...SERVIE,
        consommation: { ete: { kwh_jour: 539.1 } },
      }),
    );
    expect(r).toBeNull();
  });

  it('hors C&I → null (le résidentiel garde sa voie)', () => {
    for (const m of ['residentiel', 'agricole', '']) expect(resolveCiCurve(payload(m, SERVIE))).toBeNull();
  });
});

describe('CIW302 — les formes génériques C&I sont supprimées', () => {
  it('consumptionProfile industriel/commercial sans forme servie vaut 0 partout', () => {
    for (const mode of ['industriel', 'commercial'] as const) {
      for (let h = 0; h < 24; h++) expect(consumptionProfile(h, { mode })).toBe(0);
    }
  });

  const lib = readFileSync(fileURLToPath(new URL('../src/lib/proposalCurve.ts', import.meta.url)), 'utf-8');
  const page = readFileSync(fileURLToPath(new URL('../src/pages/proposition/[...token].astro', import.meta.url)), 'utf-8');
  it('plus de industrialShape / commercialShape / régime 1x8 dans la lib', () => {
    expect(lib).not.toMatch(/function industrialShape|function commercialShape|INDUSTRIAL_STANDBY|COMMERCIAL_OPEN_HOUR/);
    expect(lib).not.toMatch(/IndustrialShift|industrialShift/);
  });
  it('la page ne dessine la courbe C&I que si le moteur la sert', () => {
    expect(page).toContain('const dessineCourbeJour = ok && (!isAutoconso || !!ciCurve);');
    expect(page).toContain("const curveVariantToggle = curveMode === 'residentiel';");
  });
});
