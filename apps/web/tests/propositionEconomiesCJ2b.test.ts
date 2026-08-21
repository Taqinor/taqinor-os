// CJ2b (21/08/2026) — trois ordres du fondateur sur /proposition/<token> :
//
//  1. « on ne voit ni l'économie calculée réelle ni la donnée PVGIS — cette
//     donnée doit servir à COMPARER la courbe de consommation ». Le backend
//     sert désormais `economies_mensuelles` (clé additive, sœur de
//     `courbes_journalieres`) : l'argent MAD, mois par mois, à poser à côté
//     du graphe production/consommation.
//  2. « ne retire pas la courbe journalière, rends-la meilleure et réaliste » :
//     le SERVEUR devient propriétaire de la FORME de consommation
//     (`courbes_journalieres.consommation[saison].forme`), plus seulement du
//     niveau — `dayProfiles.OCCUPANCY_SHAPES` reste, mais comme repli.
//  3. « le bouton avec batterie a mystérieusement disparu — remets-le à une
//     meilleure place, plus grand, pour que le client ne le rate jamais » —
//     ET, honnêteté oblige : jamais de bouton ni de figure batterie quand
//     l'option n'est pas VENDABLE à ce devis.
//
// Ces tests pincent les quatre invariants : (A) la forme servie est lue
// défensivement et préférée à OCCUPANCY_SHAPES, un payload SANS forme reste
// byte-identique ; (B) `economiesMensuelles` ne rend jamais un bloc à moitié
// lu ; (C) le bouton batterie utilise le langage de bouton du design system
// et vit en tête du bloc ; (D) tout ceci s'éteint proprement quand les clés
// manquent — jamais un zéro déguisé.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { OCCUPANCY_IDS, OCCUPANCY_SHAPES, parseDailyCurves } from '../src/lib/dayProfiles';
import { consumptionKwhShape, renderYearCurve } from '../src/lib/proposalCurve';
import { economiesMensuelles, type ProposalResponse } from '../src/lib/proposition';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8');
const PAGE = read('../src/pages/proposition/[...token].astro');
const CSS = read('../src/styles/global.css');

/** Même discipline que P18/PV80 : le code réel, comments retirés — un
 *  commentaire qui mentionne une clause ne doit jamais faire passer un test. */
const CODE = PAGE
  .replace(/<!--[\s\S]*?-->/g, ' ')
  .replace(/\{\/\*[\s\S]*?\*\/\}/g, ' ')
  .replace(/\/\*[\s\S]*?\*\//g, ' ')
  .replace(/^[ \t]*\/\/.*$/gm, ' ');

// ════════════════════════════════════════════════════════════════════════════
// A. dayProfiles — la FORME de consommation devient servable, résidentiel
// ════════════════════════════════════════════════════════════════════════════

// Forme normalisée somme=1 (convention serveur), volontairement DIFFÉRENTE
// des trois OCCUPANCY_SHAPES pour que « préférée » soit vérifiable sans
// ambiguïté (poids concentrés en toute fin de journée, aucune ne fait ça).
const RAW_SERVED = Array.from({ length: 24 }, (_, h) => (h >= 20 && h <= 23 ? 4 : 0.5));
const SERVED_SUM = RAW_SERVED.reduce((a, b) => a + b, 0);
const SERVED_FORME = RAW_SERVED.map((v) => v / SERVED_SUM);

const BASE_PAYLOAD = {
  note_horaire: 'x',
  occupation: 'presence_jour',
  occupation_source: 'defaut_residentiel_fondateur',
  consommation_forme_source: 'silhouette_occupation:presence_jour',
  production: {},
  consommation: {
    ete: { kwh_jour: 22.5, forme: SERVED_FORME },
    hiver: { kwh_jour: 14.2 }, // niveau SEUL — le cas fréquent avant CJ2b
  },
  options: [],
};

describe('CJ2b — parseDailyCurves lit la forme de consommation, défensivement', () => {
  it('une forme VALIDE (24, finie, ≥0, somme>0) est exposée telle quelle', () => {
    const curves = parseDailyCurves(BASE_PAYLOAD)!;
    expect(curves.consommation.ete!.forme).toEqual(SERVED_FORME);
    expect(curves.consommation.ete!.kwhJour).toBe(22.5);
  });

  it('une saison SANS forme garde son niveau, `forme` reste absente (repli honnête)', () => {
    const curves = parseDailyCurves(BASE_PAYLOAD)!;
    expect(curves.consommation.hiver!.kwhJour).toBe(14.2);
    expect(curves.consommation.hiver!.forme).toBeUndefined();
    expect(Object.keys(curves.consommation.hiver!)).toEqual(['kwhJour']);
  });

  it('`consommation_forme_source` est lue au niveau racine, chaîne vide si absente', () => {
    expect(parseDailyCurves(BASE_PAYLOAD)!.consommationFormeSource).toBe('silhouette_occupation:presence_jour');
    const { consommation_forme_source, ...sansSource } = BASE_PAYLOAD;
    expect(parseDailyCurves(sansSource)!.consommationFormeSource).toBe('');
  });

  it('longueur ≠ 24 → forme ignorée, le niveau reste', () => {
    const curves = parseDailyCurves({
      ...BASE_PAYLOAD,
      consommation: { ete: { kwh_jour: 10, forme: [1, 2, 3] } },
    })!;
    expect(curves.consommation.ete!.kwhJour).toBe(10);
    expect(curves.consommation.ete!.forme).toBeUndefined();
  });

  it('une valeur négative → forme ignorée (jamais une forme à moitié lue)', () => {
    const negative = SERVED_FORME.map((v, i) => (i === 5 ? -0.1 : v));
    const curves = parseDailyCurves({
      ...BASE_PAYLOAD,
      consommation: { ete: { kwh_jour: 10, forme: negative } },
    })!;
    expect(curves.consommation.ete!.forme).toBeUndefined();
    expect(curves.consommation.ete!.kwhJour).toBe(10);
  });

  it('une forme entièrement nulle → écartée (une ligne plate n’est pas une consommation)', () => {
    const curves = parseDailyCurves({
      ...BASE_PAYLOAD,
      consommation: { ete: { kwh_jour: 10, forme: new Array(24).fill(0) } },
    })!;
    expect(curves.consommation.ete!.forme).toBeUndefined();
  });

  it('un ANCIEN payload (sans `forme` ni `consommation_forme_source` nulle part) reste byte-identique', () => {
    const oldPayload = {
      note_horaire: 'x',
      occupation: 'presence_jour',
      occupation_source: 'defaut_residentiel_fondateur',
      production: {},
      consommation: { ete: { kwh_jour: 22.5 } },
      options: [],
    };
    const curves = parseDailyCurves(oldPayload)!;
    expect(curves.consommation.ete).toEqual({ kwhJour: 22.5 });
    expect(curves.consommationFormeSource).toBe('');
  });
});

// ════════════════════════════════════════════════════════════════════════════
// B. proposalCurve — la forme SERVIE est PRÉFÉRÉE, repli EXACT sinon
// ════════════════════════════════════════════════════════════════════════════

describe('CJ2b — rawConsumptionShape (via consumptionKwhShape) préfère la forme servie', () => {
  it('résidentiel + forme servie VALIDE → la forme du client l’emporte sur OCCUPANCY_SHAPES', () => {
    const dailyKwh = 24;
    const withServed = consumptionKwhShape(dailyKwh, {
      mode: 'residentiel', occupancy: 'absence_jour', servedShape: SERVED_FORME,
    });
    const withoutServed = consumptionKwhShape(dailyKwh, { mode: 'residentiel', occupancy: 'absence_jour' });
    // Même niveau (le total du jour ne bouge pas)…
    expect(withServed.reduce((a, b) => a + b, 0)).toBeCloseTo(dailyKwh, 9);
    // …mais une forme RÉELLEMENT différente de l’occupation locale.
    expect(withServed).not.toEqual(withoutServed);
    // Et la forme servie retombe EXACTEMENT sur ses propres proportions × dailyKwh.
    SERVED_FORME.forEach((w, h) => expect(withServed[h]).toBeCloseTo(w * dailyKwh, 9));
  });

  it('absente/invalide (undefined, null, mauvaise longueur) → repli EXACT sur OCCUPANCY_SHAPES', () => {
    const dailyKwh = 18;
    for (const occupancy of OCCUPANCY_IDS) {
      const base = consumptionKwhShape(dailyKwh, { mode: 'residentiel', occupancy });
      expect(consumptionKwhShape(dailyKwh, { mode: 'residentiel', occupancy, servedShape: null }))
        .toEqual(base);
      expect(consumptionKwhShape(dailyKwh, { mode: 'residentiel', occupancy, servedShape: undefined }))
        .toEqual(base);
      expect(consumptionKwhShape(dailyKwh, { mode: 'residentiel', occupancy, servedShape: [1, 2, 3] }))
        .toEqual(base);
    }
  });

  it('hors résidentiel, la forme servie est IGNORÉE — chaque mode garde son propre archétype', () => {
    const dailyKwh = 40;
    for (const mode of ['industriel', 'commercial', 'agricole'] as const) {
      const withServed = consumptionKwhShape(dailyKwh, { mode, servedShape: SERVED_FORME });
      const withoutServed = consumptionKwhShape(dailyKwh, { mode });
      expect(withServed).toEqual(withoutServed);
    }
  });

  it('un appelant qui ne passe jamais `servedShape` (ancien payload) ne voit STRICTEMENT rien changer', () => {
    const out = renderYearCurve(9000, undefined, 'fr', { mode: 'residentiel', occupancy: 'presence_jour' });
    const outAgain = renderYearCurve(9000, undefined, 'fr', {
      mode: 'residentiel', occupancy: 'presence_jour', servedShape: null,
    });
    expect(outAgain.svg).toBe(out.svg);
  });

  it('OCCUPANCY_SHAPES reste le contenu PINGLÉ (fallback, jamais réécrit)', () => {
    // Épinglage minimal ici : la valeur exacte est verrouillée côté backend par
    // test_etude_horaire.py::test_les_trois_silhouettes_sont_identiques_au_typescript.
    // On vérifie seulement que le module ne l’a pas VIDÉE ni renommée.
    expect(OCCUPANCY_IDS).toHaveLength(3);
    for (const id of OCCUPANCY_IDS) {
      expect(OCCUPANCY_SHAPES[id]).toHaveLength(24);
    }
  });
});

// ════════════════════════════════════════════════════════════════════════════
// C. proposition.ts — economiesMensuelles : lecture DÉFENSIVE, jamais un bloc à moitié
// ════════════════════════════════════════════════════════════════════════════

const ECO_FULL = {
  sans: [636, 590, 720, 810, 905, 930, 940, 880, 800, 700, 600, 560],
  avec: [921, 860, 1010, 1120, 1240, 1270, 1280, 1200, 1090, 960, 840, 790],
  total_sans: 8689,
  total_avec: 12551,
  devise: 'MAD',
  modele: 'horaire',
  estimation: false,
  note: 'Calculé heure par heure : production PVGIS contre votre courbe de consommation.',
};

function proposalWith(economies: unknown): ProposalResponse {
  return { economies_mensuelles: economies } as unknown as ProposalResponse;
}

describe('CJ2b — economiesMensuelles : la clé ADDITIVE au niveau racine', () => {
  it('un bloc COMPLET est lu tel quel', () => {
    const eco = economiesMensuelles(proposalWith(ECO_FULL))!;
    expect(eco.sans).toEqual(ECO_FULL.sans);
    expect(eco.avec).toEqual(ECO_FULL.avec);
    expect(eco.totalSans).toBe(8689);
    expect(eco.totalAvec).toBe(12551);
    expect(eco.devise).toBe('MAD');
    expect(eco.modele).toBe('horaire');
    expect(eco.estimation).toBe(false);
    expect(eco.note).toBe(ECO_FULL.note);
  });

  it('clé ABSENTE (le cas fréquent) → null, jamais un bloc à zéro', () => {
    expect(economiesMensuelles(proposalWith(undefined))).toBeNull();
    expect(economiesMensuelles({} as unknown as ProposalResponse)).toBeNull();
    expect(economiesMensuelles(null)).toBeNull();
    expect(economiesMensuelles(undefined)).toBeNull();
  });

  it('`avec` EXPLICITEMENT null (option non vendable) → avec/totalAvec restent null', () => {
    const eco = economiesMensuelles(proposalWith({ ...ECO_FULL, avec: null, total_avec: null }))!;
    expect(eco.sans).toEqual(ECO_FULL.sans);
    expect(eco.avec).toBeNull();
    expect(eco.totalAvec).toBeNull();
    // Le SANS reste servi — ce n’est que l’option batterie qui disparaît.
    expect(eco.totalSans).toBe(8689);
  });

  it('`avec` présent mais `total_avec` illisible → la PAIRE disparaît ensemble (jamais dépareillée)', () => {
    const eco = economiesMensuelles(proposalWith({ ...ECO_FULL, total_avec: 'beaucoup' }))!;
    expect(eco.avec).toBeNull();
    expect(eco.totalAvec).toBeNull();
  });

  it('`sans` illisible (11 valeurs, ou un non-nombre dedans) → le bloc ENTIER est null', () => {
    expect(economiesMensuelles(proposalWith({ ...ECO_FULL, sans: ECO_FULL.sans.slice(0, 11) }))).toBeNull();
    const withNaN = [...ECO_FULL.sans];
    withNaN[3] = Number.NaN;
    expect(economiesMensuelles(proposalWith({ ...ECO_FULL, sans: withNaN }))).toBeNull();
    expect(economiesMensuelles(proposalWith({ ...ECO_FULL, total_sans: undefined }))).toBeNull();
  });

  it('`modele` inconnu ou absent → replie sur `\'estimation\'` (jamais un mensonge de provenance)', () => {
    expect(economiesMensuelles(proposalWith({ ...ECO_FULL, modele: undefined }))!.modele).toBe('estimation');
    expect(economiesMensuelles(proposalWith({ ...ECO_FULL, modele: 'n’importe quoi' }))!.modele).toBe('estimation');
    expect(economiesMensuelles(proposalWith({ ...ECO_FULL, modele: 'factures' }))!.modele).toBe('factures');
  });

  it('`devise` absente → replie sur "MAD" ; `note` absente → chaîne vide (jamais une phrase inventée)', () => {
    const { devise, note, ...sansDeviseNiNote } = ECO_FULL;
    const eco = economiesMensuelles(proposalWith(sansDeviseNiNote))!;
    expect(eco.devise).toBe('MAD');
    expect(eco.note).toBe('');
  });

  it('`estimation: true` est portée telle quelle', () => {
    expect(economiesMensuelles(proposalWith({ ...ECO_FULL, estimation: true }))!.estimation).toBe(true);
  });

  it('drapeau `estimation` ABSENT ou malformé → étiqueté estimation (fail-safe, jamais fail-open)', () => {
    // Retomber sur `false` reviendrait à présenter un modèle comme une mesure :
    // le pire défaut possible sous la règle « zéro chiffre inventé ».
    for (const mauvais of [undefined, null, 'false', 0, {}]) {
      const eco = economiesMensuelles(
        proposalWith({ ...ECO_FULL, estimation: mauvais, modele: 'factures' }))!;
      expect(eco.estimation).toBe(true);
    }
  });

  it('un modèle NON horaire est une estimation, quoi que dise le drapeau', () => {
    // La provenance prime sur le drapeau : « factures » et « estimation »
    // répartissent un total annuel sur douze mois, ils ne les calculent pas.
    for (const modele of ['factures', 'estimation', 'n’importe quoi']) {
      const eco = economiesMensuelles(
        proposalWith({ ...ECO_FULL, modele, estimation: false }))!;
      expect(eco.estimation).toBe(true);
    }
  });

  it('la page appelle bien `economiesMensuelles(data!)`, gardée par `ok`', () => {
    expect(CODE).toContain('const ecoMensuelles: EconomiesMensuelles | null = ok ? economiesMensuelles(data!) : null');
  });
});

// ════════════════════════════════════════════════════════════════════════════
// D. La page : le bouton batterie EN TÊTE, langage `.btn-pill`, honnêteté #4
// ════════════════════════════════════════════════════════════════════════════

describe('CJ2b — le bouton « Avec batterie » revient, dans le langage `.btn-pill`', () => {
  it('`.btn-pill` est bien un utilitaire du design system (global.css)', () => {
    expect(CSS).toContain('.btn-pill {');
  });

  it('le bouton batterie porte la classe `.btn-pill`, pas une case à cocher nue', () => {
    expect(CODE).toContain('id="prod-battery-toggle"');
    expect(CODE).not.toMatch(/type="checkbox"[^>]*id="prod-battery-toggle"/);
    // Le bloc autour de l'id porte bien `btn-pill` (on cherche dans une fenêtre
    // proche plutôt que d'exiger un ordre d'attributs précis).
    const idx = CODE.indexOf('id="prod-battery-toggle"');
    const nearby = CODE.slice(Math.max(0, idx - 400), idx + 400);
    expect(nearby).toContain('btn-pill');
    // Délibérément plus grand que les puces voisines (px-3 py-1) : padding relevé.
    expect(nearby).toContain('px-5 py-2.5');
  });

  it('le bouton porte aria-pressed (accessible, état vrai/faux) plutôt qu’un aria-checked de case', () => {
    const idx = CODE.indexOf('id="prod-battery-toggle"');
    const nearby = CODE.slice(idx, idx + 300);
    expect(nearby).toContain('aria-pressed=');
  });

  it('la commande batterie vit AVANT le calque « CALQUE ANNÉE » (en tête de bloc, pas tout en bas)', () => {
    const battery = CODE.indexOf('data-prod-battery-control');
    const viewTabs = CODE.indexOf('data-prod-view-btn="annee"');
    const monthlyLayer = CODE.indexOf('data-prod-layer="monthly"');
    expect(battery).toBeGreaterThan(-1);
    expect(viewTabs).toBeGreaterThan(-1);
    expect(monthlyLayer).toBeGreaterThan(-1);
    // Après le sélecteur de vue (qui ouvre le bloc), avant le premier calque dessiné.
    expect(battery).toBeGreaterThan(viewTabs);
    expect(battery).toBeLessThan(monthlyLayer);
  });

  it('le script client bascule le bouton au CLIC (plus un `change` de case à cocher)', () => {
    expect(CODE).toContain("document.getElementById('prod-battery-toggle')");
    expect(CODE).toContain('setBatteryLayer(state, !state.battery, availability)');
    expect(CODE).not.toContain('batteryToggle.checked');
  });

  it('honnêteté #4 — l’option batterie disparaît quand `economies_mensuelles.avec` est explicitement null', () => {
    expect(CODE).toContain('ecoMensuellesForbidsBattery');
    expect(CODE).toContain('!!ecoMensuelles && ecoMensuelles.avec === null');
    expect(CODE).toContain('battery: showBatterySim && !!batteryInitial && !ecoMensuellesForbidsBattery');
  });
});

// ════════════════════════════════════════════════════════════════════════════
// E. La page : l’argent mensuel apparaît près des barres, jamais un bloc à zéro
// ════════════════════════════════════════════════════════════════════════════

describe('CJ2b — le chapitre « Votre production » affiche l’argent mois par mois', () => {
  it('le bloc entier est gated sur `ecoMensuelles` — absent ⇒ rien ne rend', () => {
    expect(CODE).toContain('{ecoMensuelles && (');
  });

  it('vit DANS le calque `monthly` (à côté des barres), pas dans un chapitre séparé', () => {
    const monthlyLayerStart = PAGE.indexOf('data-prod-layer="monthly"');
    const monthlyLayerCloseIdx = PAGE.indexOf('CALQUE JOURNÉE', monthlyLayerStart);
    const ecoBlockIdx = PAGE.indexOf('{ecoMensuelles && (');
    expect(monthlyLayerStart).toBeGreaterThan(-1);
    expect(ecoBlockIdx).toBeGreaterThan(monthlyLayerStart);
    expect(ecoBlockIdx).toBeLessThan(monthlyLayerCloseIdx);
  });

  it('affiche le total ANNUEL sans/avec ET la phrase source, jamais réécrite', () => {
    expect(CODE).toContain('formatMAD(ecoMensuelles.totalSans)');
    expect(CODE).toContain('ecoMensuelles.totalAvec !== null');
    expect(CODE).toContain('formatMAD(ecoMensuelles.totalAvec)');
    // Le `note` est affiché TEL QUEL (pas de retraduction/gabarit autour du texte).
    expect(CODE).toContain('{ecoMensuelles.note}');
  });

  it('la figure « avec batterie » ne s’affiche QUE quand `avec` est un tableau (jamais un 0 déguisé)', () => {
    expect(CODE).toContain('{ecoMensuelles.avec && (');
  });

  it('l’étiquette « estimation » suit le même idiome que `couverture.estimated`', () => {
    expect(CODE).toContain('{ecoMensuelles.estimation && (');
    expect(CODE).toContain('estimation — consommation déduite de votre facture');
  });
});
