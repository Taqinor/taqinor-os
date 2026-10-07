// WJ126 — Proposition MODE-AWARE : logique pure des 4 variantes de devis.
//
// La page /proposition/<token> rend 4 variantes (résidentiel / agricole /
// industriel / commercial) à partir du bloc QX49 backend (`mode_installation`
// clé machine minuscule, `mode_kpis` whitelisté, `categorie_commerciale`). Ces
// tests prouvent, SANS DOM, que :
//  - la variante est choisie sur `mode_installation` et JAMAIS sur `inst_type`
//    (le bug historique : `inst_type` est un libellé capitalisé qui ne matchait
//    aucun littéral minuscule) ;
//  - chaque extracteur de KPI ne renvoie rien hors de son mode (zéro fuite
//    inter-mode) et met chaque champ manquant à `null` (omission honnête, jamais
//    un 0 fabriqué) ;
//  - (CIW300 : le mini-cashflow 10 ans est supprimé, l'argent C&I = `synthese_ci`).
import { describe, expect, it } from 'vitest';
import {
  resolveInstallMode,
  agricoleKpis,
  autoconsoKpis,
  hasInjection,
  MONTHS_SHORT,
  type ProposalResponse,
} from '../src/lib/proposition';

function makeProposal(over: Partial<ProposalResponse> = {}): ProposalResponse {
  const base: ProposalResponse = {
    reference: 'DEV-2026-126',
    date: '16/07/2026',
    client_name: 'Atlas Agri',
    statut: 'envoye',
    quote: {
      ref: 'DEV-2026-126',
      date: '16/07/2026',
      client_name: 'Atlas Agri',
      totaux_sans: { ht_brut: 900000, remise: 0, ht_net: 900000, tva: 180000, ttc: 1080000 },
      display_total: 1080000,
      nb_options: 1,
    },
    roof_image_url: null,
    option_totals: { sans_batterie: 1080000, avec_batterie: 0, display_total: 1080000, nb_options: 1 },
    accepted: false,
  };
  return { ...base, ...over, quote: { ...base.quote, ...(over.quote ?? {}) } };
}

// ── Fixtures par mode (miroir des payloads QX49 vérifiés côté backend) ────────

const AGRICOLE = makeProposal({
  mode_installation: 'agricole',
  mode_kpis: {
    pompe_cv: 7.5, pompe_kw: 5.5, hmt_m: 60, debit_hmt_m3h: 16,
    m3_jour: 112, heures_pompage: 7, champ_kwc: 9.24,
  },
  monthly_production: [700, 800, 1100, 1300, 1500, 1600, 1650, 1550, 1300, 1050, 800, 650],
  quote: { puissance_kwc: 9.24 },
});

const INDUSTRIEL = makeProposal({
  mode_installation: 'industriel',
  mode_kpis: {
    taux_autoconso: 88, taux_couverture: 67, economies_annuelles: 420000, payback: 3.1,
  },
});

const COMMERCIAL = makeProposal({
  mode_installation: 'commercial',
  categorie_commerciale: 'hotel',
  mode_kpis: {
    taux_autoconso: 78, taux_couverture: 59, economies_annuelles: 165000, payback: 3.4,
    injection_kwh_an: 45000, injection_dh_an: 30000,
  },
});

const RESIDENTIEL = makeProposal({
  mode_installation: 'residentiel',
  mode_kpis: null,
  quote: { puissance_kwc: 6.48 },
});

// ── resolveInstallMode : branche sur mode_installation, JAMAIS inst_type ──────

describe('WJ126 — resolveInstallMode (mode_installation, jamais inst_type)', () => {
  it('résout les 4 clés machine minuscules', () => {
    expect(resolveInstallMode(AGRICOLE)).toBe('agricole');
    expect(resolveInstallMode(INDUSTRIEL)).toBe('industriel');
    expect(resolveInstallMode(COMMERCIAL)).toBe('commercial');
    expect(resolveInstallMode(RESIDENTIEL)).toBe('residentiel');
  });

  it('repli résidentiel quand mode_installation est absent / vide / inconnu', () => {
    expect(resolveInstallMode(makeProposal({ mode_installation: undefined }))).toBe('residentiel');
    expect(resolveInstallMode(makeProposal({ mode_installation: '' }))).toBe('residentiel');
    expect(resolveInstallMode(makeProposal({ mode_installation: null }))).toBe('residentiel');
    expect(resolveInstallMode(makeProposal({ mode_installation: 'zzz' }))).toBe('residentiel');
  });

  it('tolère un libellé capitalisé et l\'alias professionnel=industriel', () => {
    expect(resolveInstallMode(makeProposal({ mode_installation: 'Agricole' }))).toBe('agricole');
    expect(resolveInstallMode(makeProposal({ mode_installation: 'professionnel' }))).toBe('industriel');
  });

  it('lit quote.mode_installation en repli du niveau racine', () => {
    const p = makeProposal({ mode_installation: undefined, quote: { mode_installation: 'commercial' } });
    expect(resolveInstallMode(p)).toBe('commercial');
  });

  it('IGNORE inst_type — la clé QX49 fait foi (bug historique)', () => {
    // inst_type dit "agricole" mais mode_installation dit "industriel" → industriel.
    const conflit = makeProposal({ mode_installation: 'industriel', quote: { inst_type: 'agricole' } });
    expect(resolveInstallMode(conflit)).toBe('industriel');
    // inst_type seul (mode_installation absent) ne suffit PAS → repli résidentiel.
    const legacyOnly = makeProposal({ mode_installation: undefined, quote: { inst_type: 'Agricole' } });
    expect(resolveInstallMode(legacyOnly)).toBe('residentiel');
  });
});

// ── AGRICOLE : héros pompe + KPI, zéro fuite, omission honnête ────────────────

describe('WJ126 — agricoleKpis (pompage)', () => {
  it('extrait les KPI pompage typés du payload', () => {
    const k = agricoleKpis(AGRICOLE)!;
    expect(k).not.toBeNull();
    expect(k.pompe_cv).toBe(7.5);
    expect(k.pompe_kw).toBe(5.5);
    expect(k.hmt_m).toBe(60);
    expect(k.debit_hmt_m3h).toBe(16);
    expect(k.m3_jour).toBe(112);
    expect(k.champ_kwc).toBe(9.24);
    // AGW301 — les heures de pompage (hypothèse du m³/jour) sont lues ; plus
    // aucun bassin ni verdict FDA propre au client.
    expect(k.heures_pompage).toBe(7);
    expect(k).not.toHaveProperty('bassin_m3');
    expect(k).not.toHaveProperty('fda_eligible');
  });

  it('renvoie null hors mode agricole (pas de bloc pompe ailleurs)', () => {
    expect(agricoleKpis(INDUSTRIEL)).toBeNull();
    expect(agricoleKpis(COMMERCIAL)).toBeNull();
    expect(agricoleKpis(RESIDENTIEL)).toBeNull();
  });

  it('agricole sans mode_kpis → objet à champs null (dégradation gracieuse)', () => {
    const k = agricoleKpis(makeProposal({ mode_installation: 'agricole', mode_kpis: null }))!;
    expect(k.pompe_cv).toBeNull();
    expect(k.m3_jour).toBeNull();
    expect(k.champ_kwc).toBeNull();
    expect(k.heures_pompage).toBeNull();
    expect(k).not.toHaveProperty('fda_eligible');
  });

  it('champ manquant → null, jamais 0 fabriqué (AGW301 : ni bassin ni FDA)', () => {
    const k = agricoleKpis(makeProposal({
      mode_installation: 'agricole',
      mode_kpis: { pompe_cv: 5, m3_jour: 80 },
    }))!;
    expect(k.pompe_cv).toBe(5);
    expect(k.m3_jour).toBe(80);
    expect(k.hmt_m).toBeNull();
    expect(k.heures_pompage).toBeNull();
    expect(k).not.toHaveProperty('bassin_m3');
  });

  it('AGW301 — un payload ancien qui porte encore bassin_m3/fda_eligible ne les ressort plus', () => {
    const k = agricoleKpis(makeProposal({
      mode_installation: 'agricole',
      mode_kpis: { pompe_cv: 5, bassin_m3: 224, fda_eligible: true } as unknown as ProposalResponse['mode_kpis'],
    }))!;
    expect(k).not.toHaveProperty('bassin_m3');
    expect(k).not.toHaveProperty('fda_eligible');
    expect(k.pompe_cv).toBe(5);
  });

  it('coerce une chaîne numérique backend (pompe_cv "7.5")', () => {
    const k = agricoleKpis(makeProposal({
      mode_installation: 'agricole',
      mode_kpis: { pompe_cv: '7.5' as unknown as number },
    }))!;
    expect(k.pompe_cv).toBe(7.5);
  });
});

// AGW303 — `agricoleMonthlyDelivery` (livraison d'eau dérivée dans le navigateur) est supprimée :
// la page lit `synthese_agricole` (propositionAgricoleSyntheseAGW303.test.ts).

// ── INDUSTRIEL / COMMERCIAL : tuiles autoconso + injection + cashflow ─────────

describe('WJ126 — autoconsoKpis (industriel / commercial)', () => {
  it('extrait les tuiles autoconso (industriel), injection null si absente', () => {
    const k = autoconsoKpis(INDUSTRIEL)!;
    expect(k.taux_autoconso).toBe(88);
    expect(k.taux_couverture).toBe(67);
    expect(k.economies_annuelles).toBe(420000);
    expect(k.payback).toBe(3.1);
    expect(k.injection_kwh_an).toBeNull();
    expect(k.injection_dh_an).toBeNull();
  });

  it('expose l\'injection 82-21 quand calculée (commercial)', () => {
    const k = autoconsoKpis(COMMERCIAL)!;
    expect(k.injection_kwh_an).toBe(45000);
    expect(k.injection_dh_an).toBe(30000);
  });

  it('renvoie null hors industriel/commercial (zéro fuite en résidentiel/agricole)', () => {
    expect(autoconsoKpis(RESIDENTIEL)).toBeNull();
    expect(autoconsoKpis(AGRICOLE)).toBeNull();
  });

  it('champ manquant → null (omission honnête)', () => {
    const k = autoconsoKpis(makeProposal({ mode_installation: 'industriel', mode_kpis: { taux_autoconso: 90 } }))!;
    expect(k.taux_autoconso).toBe(90);
    expect(k.economies_annuelles).toBeNull();
    expect(k.payback).toBeNull();
  });
});

describe('WJ126 — hasInjection', () => {
  it('vrai seulement pour un kWh injecté strictement positif', () => {
    expect(hasInjection(autoconsoKpis(COMMERCIAL))).toBe(true);
    expect(hasInjection(autoconsoKpis(INDUSTRIEL))).toBe(false);
    expect(hasInjection(null)).toBe(false);
    expect(hasInjection(autoconsoKpis(makeProposal({ mode_installation: 'commercial', mode_kpis: { injection_kwh_an: 0 } })))).toBe(false);
  });
});

describe('CIW300 — le mini-cashflow linéaire 10 ans est supprimé', () => {
  it('plus d\'export autoconsoCashflow : l\'argent C&I vient de synthese_ci', async () => {
    const lib = await import('../src/lib/proposition');
    expect((lib as Record<string, unknown>).autoconsoCashflow).toBeUndefined();
  });
});

// ── COMMERCIAL : archétype par catégorie ──────────────────────────────────────

// CIW306 — `commercialArchetype` (copie TS de categories.py) est supprimé : voir
// propositionCategorieCIW306.test.ts (le bloc catégorie est lu dans `synthese_ci.categorie`).

// ── Intégration : zéro champ résiduel d'un autre mode ─────────────────────────

describe('WJ126 — zéro fuite inter-mode (le contrat central de la vitrine)', () => {
  it('page AGRICOLE : aucun bloc autoconsommation ne se calcule', () => {
    expect(resolveInstallMode(AGRICOLE)).toBe('agricole');
    expect(autoconsoKpis(AGRICOLE)).toBeNull();
    expect(agricoleKpis(AGRICOLE)).not.toBeNull();
  });

  it('page INDUSTRIELLE : aucun bloc pompage ne se calcule', () => {
    expect(resolveInstallMode(INDUSTRIEL)).toBe('industriel');
    expect(agricoleKpis(INDUSTRIEL)).toBeNull();
    expect(autoconsoKpis(INDUSTRIEL)).not.toBeNull();
  });

  it('page RÉSIDENTIELLE : ni pompage ni autoconsommation dédiés', () => {
    expect(resolveInstallMode(RESIDENTIEL)).toBe('residentiel');
    expect(agricoleKpis(RESIDENTIEL)).toBeNull();
    expect(autoconsoKpis(RESIDENTIEL)).toBeNull();
  });
});

describe('WJ126 — MONTHS_SHORT (axe du mini-graphe eau)', () => {
  it('porte 12 mois dans les 3 langues', () => {
    expect(MONTHS_SHORT.fr).toHaveLength(12);
    expect(MONTHS_SHORT.en).toHaveLength(12);
    expect(MONTHS_SHORT.ar).toHaveLength(12);
  });
});

// AGW301 — la page ne rend plus les trois cartes retirées et affiche les heures.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
describe('AGW301 — page /proposition agricole : cartes retirées, heures affichées', () => {
  const page = readFileSync(
    fileURLToPath(new URL('../src/pages/proposition/[...token].astro', import.meta.url)),
    'utf-8',
  );
  const code = page.replace(/\{\/\*[\s\S]*?\*\/\}/g, '');
  it('plus de « Bassin recommandé », « Subvention FDA » ni « Fini le carburant »', () => {
    for (const bad of [
      'Bassin recommandé', 'Recommended reservoir', 'حوض موصى به',
      'Subvention FDA envisageable', 'FDA subsidy possible', 'دعم FDA ممكن',
      'Fini le carburant', 'No more fuel', 'وداعاً للوقود',
      'agri.bassin_m3', 'agri.fda_eligible',
    ]) expect(code).not.toContain(bad);
    expect(code).not.toMatch(/pouvant atteindre 30/);
  });
  it('les heures de pompage sont lues et affichées sous l\'eau/jour (hypothèse)', () => {
    expect(code).toContain('agri.heures_pompage');
    expect(code).toContain('h de pompage (hypothèse)');
    expect(code).toContain('of pumping (assumption)');
  });
});
