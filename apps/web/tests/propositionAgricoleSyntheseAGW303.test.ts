// AGW303 — jumeau web du document agricole (1/2) : l'eau, le besoin de la culture, le
// schéma et le point de fonctionnement sont LUS dans `synthese_agricole` (contrat partagé
// `proposal_data.json` › `exemple_agricole`), sans aucun calcul dans la page.
//
//  - extracteur pur `syntheseAgricole(p)` à lecture défensive : clé absente → `null`,
//    série partielle → `null`, jamais un 0 fabriqué ;
//  - `agricoleMonthlyDelivery` (livraison d'eau dérivée de m3_jour × 365 dans le
//    navigateur) a DISPARU, avec son usage ;
//  - la page insère `schema_svg` tel que servi et omet graphe / schéma sans synthèse.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  courbeGeometrie,
  dateJjMmAaaa,
  omissionSynthese,
  phraseProvenance,
  provenanceKind,
  syntheseAgricole,
  type ProposalResponse,
} from '../src/lib/proposition';

const lire = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');
const contrat = JSON.parse(lire('../src/contract_samples/proposal_data.json')) as {
  exemple_agricole: { synthese_agricole: Record<string, unknown> };
};
const SERVIE = contrat.exemple_agricole.synthese_agricole;

function payload(synthese?: unknown, mode = 'agricole'): ProposalResponse {
  return {
    reference: 'DEV-2026-0001',
    mode_installation: mode,
    quote: { ref: 'DEV-2026-0001', mode_installation: mode },
    ...(synthese === undefined ? {} : { synthese_agricole: synthese }),
  } as unknown as ProposalResponse;
}

describe('AGW303 — syntheseAgricole : lecture défensive', () => {
  it('lit l’exemple agricole du contrat partagé', () => {
    const s = syntheseAgricole(payload(SERVIE))!;
    expect(s).not.toBeNull();
    expect(s.modePompe).toBe('neuve');
    expect(s.eau).toEqual({ m3Jour: 134.2, heuresPompage: 4.4, hmtM: 58.7, debitHmtM3h: 30.5, estimation: false });
    expect(s.besoinVsLivre!.mois).toHaveLength(12);
    expect(s.besoinVsLivre!.moisLePlusSerre).toBe(12);
    expect(s.besoinVsLivre!.hectaresIrrigables).toBeNull();
    expect(s.pointFonctionnement!.point).toEqual({ debitM3h: 30.5, hmtM: 58.7 });
    expect(s.pointFonctionnement!.courbe[0]).toEqual([0, 91]);
    expect(s.schemaSvg!.startsWith('<svg')).toBe(true);
    expect(s.champ).toEqual({ kwc: 9.94, nbPanneaux: 14 });
    expect(s.aConfirmerParVisite).toEqual(['profondeur_forage_m']);
    expect(s.provenance.map((e) => e.cle)).toContain('niveau_statique_m');
  });

  it('clé absente, vide ou non-objet → null (jamais une synthèse fabriquée)', () => {
    expect(syntheseAgricole(payload(undefined))).toBeNull();
    expect(syntheseAgricole(payload({}))).toBeNull();
    expect(syntheseAgricole(payload(null))).toBeNull();
    expect(syntheseAgricole(payload([]))).toBeNull();
    expect(syntheseAgricole(payload('x'))).toBeNull();
  });

  it('hors mode agricole → null, même si la clé est présente (zéro fuite inter-mode)', () => {
    expect(syntheseAgricole(payload(SERVIE, 'residentiel'))).toBeNull();
    expect(syntheseAgricole(payload(SERVIE, 'industriel'))).toBeNull();
    expect(syntheseAgricole(null)).toBeNull();
  });

  it('besoin_vs_livre : série partielle ou mal formée → null, jamais complétée de zéros', () => {
    const mois = (SERVIE.besoin_vs_livre as { mois: unknown[] }).mois;
    const avec = (m: unknown[]) => syntheseAgricole(payload({ ...SERVIE, besoin_vs_livre: { ...(SERVIE.besoin_vs_livre as object), mois: m } }))!;
    expect(avec(mois.slice(0, 11)).besoinVsLivre).toBeNull();
    expect(avec([...mois.slice(0, 11), { besoin_m3_jour: 100, livre_m3_jour: null }]).besoinVsLivre).toBeNull();
    expect(avec([...mois.slice(0, 11), { besoin_m3_jour: '100', livre_m3_jour: 90 }]).besoinVsLivre).toBeNull();
    // clé absente
    const { besoin_vs_livre: _b, ...sans } = SERVIE;
    expect(syntheseAgricole(payload(sans))!.besoinVsLivre).toBeNull();
  });

  it('point de fonctionnement : sans courbe ou sans point → null (la phrase d’omission servie reste lisible)', () => {
    const { point_fonctionnement: _p, ...sans } = SERVIE;
    const omission = { bloc: 'point_fonctionnement', motif: 'courbe constructeur non disponible pour cette pompe : point de fonctionnement omis' };
    const s = syntheseAgricole(payload({ ...sans, omissions: [omission] }))!;
    expect(s.pointFonctionnement).toBeNull();
    expect(omissionSynthese(s, 'point_fonctionnement')).toBe(omission.motif);
    expect(omissionSynthese(s, 'inconnu')).toBeNull();
    const pf = SERVIE.point_fonctionnement as { courbe: unknown; point: unknown };
    expect(syntheseAgricole(payload({ ...SERVIE, point_fonctionnement: { courbe: [[0, 90]], point: pf.point } }))!.pointFonctionnement).toBeNull();
    expect(syntheseAgricole(payload({ ...SERVIE, point_fonctionnement: { courbe: pf.courbe, point: { debit_m3h: 30 } } }))!.pointFonctionnement).toBeNull();
  });

  it('schema_svg : inséré seulement s’il s’agit d’un <svg> servi', () => {
    expect(syntheseAgricole(payload({ ...SERVIE, schema_svg: '<script>alert(1)</script>' }))!.schemaSvg).toBeNull();
    expect(syntheseAgricole(payload({ ...SERVIE, schema_svg: '' }))!.schemaSvg).toBeNull();
    expect(syntheseAgricole(payload({ ...SERVIE, schema_svg: null }))!.schemaSvg).toBeNull();
  });

  it('pompe existante : plaque lue (kW, V, phases) ; sans plaque → null', () => {
    const existante = syntheseAgricole(payload({
      ...SERVIE, mode_pompe: 'existante',
      pompe: { cv: null, kw: 5.5, plaque: { kw: 5.5, tension_v: 380, phases: 'tri', cv: null, courant_a: null } },
    }))!;
    expect(existante.modePompe).toBe('existante');
    expect(existante.pompe!.plaque).toEqual({ kw: 5.5, tensionV: 380, phases: 'tri', cv: null, courantA: null });
    const sansPlaque = syntheseAgricole(payload({ ...SERVIE, mode_pompe: 'existante', pompe: { cv: null, kw: 5.5 } }))!;
    expect(sansPlaque.pompe!.plaque).toBeNull();
    expect(syntheseAgricole(payload({ ...SERVIE, mode_pompe: 'autre' }))!.modePompe).toBeNull();
  });

  it('une estimation reste une estimation sauf « false » explicite', () => {
    expect(syntheseAgricole(payload({ ...SERVIE, eau: { m3_jour: 100 } }))!.eau!.estimation).toBe(true);
    expect(syntheseAgricole(payload({ ...SERVIE, eau: { m3_jour: 100, estimation: false } }))!.eau!.estimation).toBe(false);
  });
});

describe('AGW303 — provenance : déclaré / mesuré / à confirmer', () => {
  it('la date ISO est reformatée JJ/MM/AAAA, une date illisible → null', () => {
    expect(dateJjMmAaaa('2026-09-12')).toBe('12/09/2026');
    expect(dateJjMmAaaa('demain')).toBeNull();
    expect(dateJjMmAaaa(null)).toBeNull();
  });

  it('même règle que le renderer : mesure_visite / foreur → mesuré ; saisie / lead → déclaré', () => {
    expect(provenanceKind({ cle: 'a', origine: 'lead', detail: 'mesure_visite', date: '2026-09-15' })).toEqual({ kind: 'mesure', date: '15/09/2026' });
    expect(provenanceKind({ cle: 'a', origine: 'saisie', detail: 'foreur', date: '2026-09-15' }).kind).toBe('mesure');
    expect(provenanceKind({ cle: 'a', origine: 'lead', detail: 'client', date: '2026-09-12' })).toEqual({ kind: 'declare', date: '12/09/2026' });
    expect(provenanceKind({ cle: 'a', origine: 'derive', detail: null, date: '2026-09-12' }).kind).toBe('a_confirmer');
  });

  it('sans date lisible : « à confirmer par la visite », jamais une date inventée', () => {
    expect(provenanceKind({ cle: 'a', origine: 'saisie', detail: null, date: null })).toEqual({ kind: 'a_confirmer', date: null });
    expect(provenanceKind({ cle: 'a', origine: 'lead', detail: 'mesure_visite', date: 'xx' }).kind).toBe('a_confirmer');
  });

  it('les phrases reprennent les mots du devis, dans les 3 langues', () => {
    const d = phraseProvenance({ cle: 'a', origine: 'lead', detail: 'client', date: '2026-09-12' });
    expect(d.fr).toBe('déclaré par vous le 12/09/2026');
    expect(d.en).toBe('declared by you on 12/09/2026');
    expect(d.ar).toContain('12/09/2026');
    const m = phraseProvenance({ cle: 'a', origine: 'lead', detail: 'mesure_visite', date: '2026-09-15' });
    expect(m.fr).toBe('mesuré par TAQINOR le 15/09/2026');
    expect(phraseProvenance({ cle: 'a', origine: 'x', detail: null, date: null }).fr).toBe('à confirmer par la visite');
  });
});

describe('AGW303 — courbeGeometrie : mise à l’échelle seule', () => {
  it('null sans point de fonctionnement', () => {
    expect(courbeGeometrie(null)).toBeNull();
  });
  it('le point et la courbe tiennent dans les axes', () => {
    const g = courbeGeometrie(syntheseAgricole(payload(SERVIE))!.pointFonctionnement)!;
    expect(g.point.x).toBeGreaterThan(g.axe.x0);
    expect(g.point.x).toBeLessThanOrEqual(g.axe.x1);
    expect(g.point.y).toBeLessThan(g.axe.y0);
    expect(g.point.y).toBeGreaterThanOrEqual(g.axe.y1);
    expect(g.polyline.split(' ')).toHaveLength(6);
    expect(g.hmtMax).toBe(91);
  });
});

describe('AGW303 — la page', () => {
  const page = lire('../src/pages/proposition/[...token].astro');
  const lib = lire('../src/lib/proposition.ts');

  it('agricoleMonthlyDelivery a disparu (fonction et usage)', () => {
    const code = (s: string) => s.replace(/^\s*\/\/.*$/gm, '');
    expect(code(lib)).not.toMatch(/function agricoleMonthlyDelivery/);
    expect(code(page)).not.toContain('agricoleMonthlyDelivery(');
    expect(code(page)).not.toContain('waterDelivery');
  });

  it('lit la synthèse servie, sans rien calculer', () => {
    expect(page).toContain('syntheseAgricole(data!)');
    expect(page).toContain('set:html={synth.schemaSvg}');
    expect(page).toContain('bvl.mois.map(');
    expect(page).toContain('data-agri-besoin-livre');
    expect(page).toContain('data-agri-schema');
    expect(page).toContain('data-agri-point');
    expect(page).toContain('data-agri-provenance');
    expect(page).toContain('data-agri-hectares');
    // Aucune constante ni formule de pompage dans la section agricole.
    const section = page.slice(page.indexOf('id="mode-agricole"'), page.indexOf('id="mode-autoconso"'));
    expect(section).not.toMatch(/\*\s*365|×\s*365/);
  });

  it('chaque bloc est gaté : sans synthèse, ni graphe ni schéma', () => {
    expect(page).toContain('{bvl && (');
    expect(page).toContain('{synth?.schemaSvg && (');
    expect(page).toContain('{synth && (');
  });

  it('libellés FR/EN/AR sur les nouveaux blocs', () => {
    const section = page.slice(page.indexOf('data-agri-besoin-livre'), page.indexOf('id="mode-autoconso"'));
    expect(section.match(/data-en=/g)!.length).toBeGreaterThan(10);
    expect(section.match(/data-ar=/g)!.length).toBeGreaterThan(10);
  });
});
