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
//  - le mini-cashflow / la livraison d'eau se dégradent en `null` quand la
//    donnée source manque.
import { describe, expect, it } from 'vitest';
import {
  resolveInstallMode,
  agricoleKpis,
  autoconsoKpis,
  hasInjection,
  autoconsoCashflow,
  agricoleMonthlyDelivery,
  commercialArchetype,
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
    m3_jour: 112, champ_kwc: 9.24, bassin_m3: 224, fda_eligible: true,
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
    expect(k.bassin_m3).toBe(224);
    expect(k.fda_eligible).toBe(true);
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
    expect(k.fda_eligible).toBe(false);
  });

  it('champ manquant → null, jamais 0 fabriqué ; FDA absente → false', () => {
    const k = agricoleKpis(makeProposal({
      mode_installation: 'agricole',
      mode_kpis: { pompe_cv: 5, m3_jour: 80 },
    }))!;
    expect(k.pompe_cv).toBe(5);
    expect(k.m3_jour).toBe(80);
    expect(k.hmt_m).toBeNull();
    expect(k.bassin_m3).toBeNull();
    expect(k.fda_eligible).toBe(false);
  });

  it('coerce une chaîne numérique backend (pompe_cv "7.5")', () => {
    const k = agricoleKpis(makeProposal({
      mode_installation: 'agricole',
      mode_kpis: { pompe_cv: '7.5' as unknown as number },
    }))!;
    expect(k.pompe_cv).toBe(7.5);
  });
});

describe('WJ126 — agricoleMonthlyDelivery (livraison d\'eau mensuelle)', () => {
  it('répartit la capacité annuelle (m3_jour×365) selon l\'ensoleillement', () => {
    const series = agricoleMonthlyDelivery(AGRICOLE, agricoleKpis(AGRICOLE))!;
    expect(series).toHaveLength(12);
    expect(series[0].monthIndex).toBe(0);
    // Somme ≈ m3_jour × 365 (aux arrondis près).
    const total = series.reduce((a, m) => a + m.m3, 0);
    expect(total).toBeGreaterThan(112 * 365 * 0.98);
    expect(total).toBeLessThan(112 * 365 * 1.02);
    // La livraison suit la production : juillet (index 6, pic) > décembre (11).
    expect(series[6].m3).toBeGreaterThan(series[11].m3);
  });

  it('null si m3_jour manque', () => {
    const p = makeProposal({ mode_installation: 'agricole', mode_kpis: { champ_kwc: 9 }, monthly_production: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] });
    expect(agricoleMonthlyDelivery(p, agricoleKpis(p))).toBeNull();
  });

  it('null si la production mensuelle manque (bloc omis, jamais fabriqué)', () => {
    const p = makeProposal({ mode_installation: 'agricole', mode_kpis: { m3_jour: 100 } });
    expect(agricoleMonthlyDelivery(p, agricoleKpis(p))).toBeNull();
  });

  it('null hors agricole (kpis null)', () => {
    expect(agricoleMonthlyDelivery(INDUSTRIEL, agricoleKpis(INDUSTRIEL))).toBeNull();
  });
});

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

describe('WJ126 — autoconsoCashflow (mini-cashflow 10 ans)', () => {
  it('trace -TTC puis +économies/an (11 points, modèle linéaire)', () => {
    const cf = autoconsoCashflow(INDUSTRIEL, 'sans_batterie', autoconsoKpis(INDUSTRIEL), 10)!;
    expect(cf).toHaveLength(11);
    expect(cf[0]).toEqual({ year: 0, cumulative: -1080000 });
    expect(cf[10].cumulative).toBe(-1080000 + 420000 * 10);
    // Monotone croissant + franchit zéro (point mort ~ année 3).
    for (let i = 1; i < cf.length; i++) expect(cf[i].cumulative).toBeGreaterThan(cf[i - 1].cumulative);
    expect(cf.find((p) => p.cumulative >= 0)!.year).toBe(3);
  });

  it('null quand l\'économie annuelle manque', () => {
    const auto = autoconsoKpis(makeProposal({ mode_installation: 'industriel', mode_kpis: { taux_autoconso: 80 } }));
    expect(autoconsoCashflow(INDUSTRIEL, 'sans_batterie', auto, 10)).toBeNull();
  });

  it('null quand aucun prix TTC réel (jamais bâti sur un montant fabriqué)', () => {
    const noPrice = makeProposal({
      mode_installation: 'industriel',
      mode_kpis: { economies_annuelles: 420000 },
      quote: { totaux_sans: undefined },
      option_totals: { sans_batterie: 0, avec_batterie: 0, display_total: 0, nb_options: 1 },
    });
    expect(autoconsoCashflow(noPrice, 'sans_batterie', autoconsoKpis(noPrice), 10)).toBeNull();
  });

  it('null quand auto est null (résidentiel/agricole)', () => {
    expect(autoconsoCashflow(RESIDENTIEL, 'sans_batterie', null, 10)).toBeNull();
  });
});

// ── COMMERCIAL : archétype par catégorie ──────────────────────────────────────

describe('WJ126 — commercialArchetype', () => {
  it('résout une catégorie connue (hôtel)', () => {
    const a = commercialArchetype('hotel');
    expect(a.key).toBe('hotel');
    expect(a.labelFr).toContain('Hôtel');
    expect(a.labelEn.length).toBeGreaterThan(0);
    expect(a.labelAr.length).toBeGreaterThan(0);
    expect(a.accrocheFr.length).toBeGreaterThan(0);
  });

  it('repli honnête sur "autre" pour une catégorie inconnue / nulle', () => {
    expect(commercialArchetype('mystere').key).toBe('autre');
    expect(commercialArchetype(null).key).toBe('autre');
    expect(commercialArchetype(undefined).key).toBe('autre');
    expect(commercialArchetype('').key).toBe('autre');
  });

  it('couvre les catégories du backend (froid/restaurant/ecole/bureau)', () => {
    expect(commercialArchetype('froid').key).toBe('froid');
    expect(commercialArchetype('restaurant').key).toBe('restaurant');
    expect(commercialArchetype('ecole').key).toBe('ecole');
    expect(commercialArchetype('bureau').key).toBe('bureau');
  });
});

// ── Intégration : zéro champ résiduel d'un autre mode ─────────────────────────

describe('WJ126 — zéro fuite inter-mode (le contrat central de la vitrine)', () => {
  it('page AGRICOLE : aucun bloc autoconsommation ne se calcule', () => {
    expect(resolveInstallMode(AGRICOLE)).toBe('agricole');
    expect(autoconsoKpis(AGRICOLE)).toBeNull();
    expect(autoconsoCashflow(AGRICOLE, 'sans_batterie', autoconsoKpis(AGRICOLE), 10)).toBeNull();
    expect(agricoleKpis(AGRICOLE)).not.toBeNull();
  });

  it('page INDUSTRIELLE : aucun bloc pompage ne se calcule', () => {
    expect(resolveInstallMode(INDUSTRIEL)).toBe('industriel');
    expect(agricoleKpis(INDUSTRIEL)).toBeNull();
    expect(agricoleMonthlyDelivery(INDUSTRIEL, agricoleKpis(INDUSTRIEL))).toBeNull();
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
