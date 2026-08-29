/**
 * QJW11 — LE LECTEUR TYPÉ DU CONTRAT `proposal_data`, ÉPROUVÉ CONTRE
 * L'ÉCHANTILLON.
 *
 * CE QUE CE FICHIER PROUVE, ET POURQUOI C'EST LE POINT. Avant ce lecteur, la
 * page faisait `await res.json() as ProposalResponse` : un CAST, c'est-à-dire
 * une promesse, pas une vérification. Une interface TypeScript n'existe pas à
 * l'exécution — donc un renommage de clé côté backend ne provoquait AUCUNE
 * erreur nulle part : les champs devenaient silencieusement `undefined`, et la
 * seule chose qui « signalait » la rupture était une page qui s'affiche vide,
 * chez le client, sur sa proposition.
 *
 * La garde centrale ci-dessous SIMULE ce renommage, clé par clé, sur
 * l'échantillon de contrat, et exige qu'il change ce que la page lit — donc
 * qu'il fasse ROUGIR. Un contrat qui bouge devient un test rouge chez nous,
 * plus une page vide chez le client.
 */
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { lireProposal, type Proposal } from '../src/lib/proposition';

const read = (rel: string): string =>
  readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

const CONTRAT = JSON.parse(read('../src/contract_samples/proposal_data.json')) as Record<string, unknown>;
const EXEMPLE = CONTRAT.exemple as Record<string, unknown>;
const EXEMPLE_STANDARD = CONTRAT.exemple_standard as Record<string, unknown>;

/** Une copie profonde de l'exemple, pour muter sans contaminer les autres tests. */
const copie = (): Record<string, unknown> => JSON.parse(JSON.stringify(EXEMPLE));

/** Renomme une clé (racine, ou `parent.enfant`) — le renommage backend simulé. */
function renommer(doc: Record<string, unknown>, chemin: string, neuf: string): Record<string, unknown> {
  const bouts = chemin.split('.');
  let cible = doc;
  for (const b of bouts.slice(0, -1)) cible = cible[b] as Record<string, unknown>;
  const feuille = bouts[bouts.length - 1]!;
  cible[neuf] = cible[feuille];
  delete cible[feuille];
  return doc;
}

describe('QJW11 — le lecteur lit l’échantillon du contrat, champ par champ', () => {
  const p = lireProposal(EXEMPLE) as Proposal;

  it('l’échantillon EST une proposition lisible', () => {
    expect(p).not.toBeNull();
  });

  it('identité et état', () => {
    expect(p.reference).toBe('DEV-2026-000412');
    expect(p.date).toBe('2026-08-15');
    expect(p.clientName).toBe('Amine Benali');
    expect(p.statut).toBe('envoye');
    expect(p.niveau).toBe('confiance');
    expect(p.apercuInterne).toBe(false);
    expect(p.accepted).toBe(false);
    // Chaînes vides du contrat ⇒ `null` : un « signé par : » vide serait pire
    // qu'absent.
    expect(p.acceptedParNom).toBeNull();
    expect(p.dateAcceptation).toBeNull();
  });

  it('mode d’installation, calepinage et schéma', () => {
    expect(p.modeInstallation).toBe('residentiel');
    expect(p.categorieCommerciale).toBe('residentiel');
    expect(p.roofImageUrl).toBe('https://cdn.taqinor.ma/roofs/abc123.png');
    expect(p.layoutStale).toBe(false);
    expect(p.layoutNbPanneaux).toBe(14);
    expect(p.sldSvg).toContain('<svg');
  });

  it('le devis et ses totaux', () => {
    expect(p.quote).not.toBeNull();
    expect(p.quote!.ref).toBe('DEV-2026-000412');
    expect(p.quote!.puissanceKwc).toBe(8.52);
    expect(p.quote!.nbOptions).toBe(2);
    expect(p.quote!.sansOk).toBe(true);
    expect(p.quote!.avecOk).toBe(true);
    expect(p.quote!.displayTotal).toBe(114000);
    expect(p.quote!.scenario).toBe('Les deux (Sans + Avec)');
    expect(p.quote!.totauxSans).toEqual({ htBrut: null, remise: null, htNet: 65000, tva: 13000, ttc: 78000 });
    expect(p.quote!.totauxAvec).toEqual({ htBrut: null, remise: null, htNet: 95000, tva: 19000, ttc: 114000 });
  });

  it('les totaux d’options au niveau racine', () => {
    expect(p.optionTotals).not.toBeNull();
    expect(p.optionTotals!.sansBatterie?.ttc).toBe(78000);
    expect(p.optionTotals!.avecBatterie?.ttc).toBe(114000);
    expect(p.optionTotals!.displayTotal).toBe(114000);
    expect(p.optionTotals!.nbOptions).toBe(2);
  });

  it('variantes servables, séries mensuelles et grandeurs de facture', () => {
    expect(p.variantesServables).toEqual(['sans', 'avec']);
    expect(p.productionMensuelle).toHaveLength(12);
    expect(p.consommationMensuelle).toHaveLength(12);
    expect(p.savingsModel).toBe('factures');
    expect(p.factureSansSolaire).toBe(1450);
    expect(p.factureAvecSolaireSans).toBe(620);
    expect(p.factureAvecSolaireAvec).toBe(180);
    expect(p.pctCut).toBe(62);
    expect(p.annualBefore).toBe(17400);
    expect(p.annualAfter).toBe(6600);
    expect(p.coveragePct).toBe(78.5);
    expect(p.coverageEstimated).toBe(false);
  });

  it('le second exemple du contrat (niveau standard) se lit aussi', () => {
    const s = lireProposal(EXEMPLE_STANDARD) as Proposal;
    expect(s).not.toBeNull();
    expect(s.niveau).toBe('standard');
  });
});

// ── LA GARDE QUI JUSTIFIE TOUT LE MODULE ────────────────────────────────────

/**
 * Chaque clé du contrat que la page LIT, avec la façon de la relire. Renommer
 * l'une d'elles côté backend doit CHANGER ce que la page voit — sinon le
 * lecteur ne protège de rien.
 */
const CLES_LUES: ReadonlyArray<readonly [string, (p: Proposal) => unknown]> = [
  ['date', (x) => x.date],
  ['client_name', (x) => x.clientName],
  ['statut', (x) => x.statut],
  ['niveau', (x) => x.niveau],
  ['mode_installation', (x) => x.modeInstallation],
  ['categorie_commerciale', (x) => x.categorieCommerciale],
  ['roof_image_url', (x) => x.roofImageUrl],
  ['layout_stale', (x) => x.layoutStale],
  ['layout_nb_panneaux', (x) => x.layoutNbPanneaux],
  ['sld_svg', (x) => x.sldSvg],
  ['quote', (x) => x.quote],
  ['option_totals', (x) => x.optionTotals],
  ['variantes_servables', (x) => x.variantesServables],
  ['monthly_production', (x) => x.productionMensuelle],
  ['monthly_consumption', (x) => x.consommationMensuelle],
  ['savings_model', (x) => x.savingsModel],
  ['facture_sans_solaire', (x) => x.factureSansSolaire],
  ['facture_avec_solaire_s', (x) => x.factureAvecSolaireSans],
  ['facture_avec_solaire_a', (x) => x.factureAvecSolaireAvec],
  ['pct_cut', (x) => x.pctCut],
  ['annual_before', (x) => x.annualBefore],
  ['annual_after', (x) => x.annualAfter],
  ['coverage_pct', (x) => x.coveragePct],
  ['coverage_estimated', (x) => x.coverageEstimated],
  ['quote.ref', (x) => x.quote?.ref],
  ['quote.puissance_kwc', (x) => x.quote?.puissanceKwc],
  ['quote.nb_options', (x) => x.quote?.nbOptions],
  ['quote.display_total', (x) => x.quote?.displayTotal],
  ['quote.sans_ok', (x) => x.quote?.sansOk],
  ['quote.avec_ok', (x) => x.quote?.avecOk],
  ['quote.scenario', (x) => x.quote?.scenario],
  ['quote.totaux_sans', (x) => x.quote?.totauxSans],
  ['quote.totaux_avec', (x) => x.quote?.totauxAvec],
  ['option_totals.sans_batterie', (x) => x.optionTotals?.sansBatterie],
  ['option_totals.avec_batterie', (x) => x.optionTotals?.avecBatterie],
  ['option_totals.display_total', (x) => x.optionTotals?.displayTotal],
  ['option_totals.nb_options', (x) => x.optionTotals?.nbOptions],
];

describe('QJW11 — un renommage de clé côté backend fait ROUGIR, pas une page vide', () => {
  const sain = lireProposal(EXEMPLE) as Proposal;

  it.each(CLES_LUES.map(([cle]) => cle))(
    'renommer `%s` change ce que la page lit',
    (cle) => {
      const paire = CLES_LUES.find(([c]) => c === cle)!;
      const casse = lireProposal(renommer(copie(), cle, `${cle}_v2`)) as Proposal;
      expect(casse, 'le payload reste lisible : seule CETTE clé a bougé').not.toBeNull();
      expect(
        paire[1](casse),
        `renommer \`${cle}\` n’a RIEN changé : le lecteur ne protège pas cette clé`,
      ).not.toEqual(paire[1](sain));
    },
  );

  it('renommer `reference` rend la proposition ILLISIBLE (plutôt qu’un cadre vide sous un en-tête anonyme)', () => {
    expect(lireProposal(renommer(copie(), 'reference', 'reference_v2'))).toBeNull();
  });

  it('les 37 clés surveillées existent VRAIMENT dans l’échantillon (une garde sur une clé fantôme ne garde rien)', () => {
    for (const [cle] of CLES_LUES) {
      const bouts = cle.split('.');
      let noeud: unknown = EXEMPLE;
      for (const b of bouts) {
        expect(noeud && typeof noeud === 'object', `${cle} : chemin cassé`).toBe(true);
        noeud = (noeud as Record<string, unknown>)[b];
      }
      expect(noeud, `${cle} absente du contrat`).not.toBeUndefined();
    }
  });
});

describe('QJW11 — l’omission est HÉRITÉE, jamais comblée', () => {
  it('ce qui n’est pas un objet n’est pas une proposition', () => {
    for (const brut of [null, undefined, 42, 'DEV-2026-000412', [], true]) {
      expect(lireProposal(brut)).toBeNull();
    }
  });

  it('un payload réduit à sa référence se lit — tout le reste reste `null`, jamais un 0 fabriqué', () => {
    const p = lireProposal({ reference: 'DEV-2026-000001' }) as Proposal;
    expect(p).not.toBeNull();
    expect(p.reference).toBe('DEV-2026-000001');
    expect(p.quote).toBeNull();
    expect(p.optionTotals).toBeNull();
    expect(p.coveragePct).toBeNull();
    expect(p.factureSansSolaire).toBeNull();
    expect(p.productionMensuelle).toBeNull();
    expect(p.variantesServables).toEqual([]);
    // Les défauts sont les plus RESTRICTIFS : moins d'informations, jamais plus.
    expect(p.niveau).toBe('standard');
    expect(p.apercuInterne).toBe(false);
    expect(p.accepted).toBe(false);
    // Un booléen sur lequel le serveur ne s'est pas prononcé reste `null` —
    // jamais un `false` fabriqué qui affirmerait quelque chose.
    expect(p.layoutStale).toBeNull();
    expect(p.coverageEstimated).toBeNull();
  });

  it('DOUZE OU RIEN : une série de onze mois se lirait comme une année en dessous de la vérité', () => {
    const onze = { reference: 'X', monthly_production: Array.from({ length: 11 }, () => 100) };
    expect((lireProposal(onze) as Proposal).productionMensuelle).toBeNull();
    const troue = { reference: 'X', monthly_production: [1, 2, 3, 4, 5, null, 7, 8, 9, 10, 11, 12] };
    expect((lireProposal(troue) as Proposal).productionMensuelle).toBeNull();
    const douze = { reference: 'X', monthly_production: Array.from({ length: 12 }, (_, i) => i) };
    expect((lireProposal(douze) as Proposal).productionMensuelle).toHaveLength(12);
  });

  it('une variante inconnue est ÉCARTÉE, jamais réinterprétée', () => {
    const p = lireProposal({ reference: 'X', variantes_servables: ['sans', 'peut-etre', 'avec'] }) as Proposal;
    expect(p.variantesServables).toEqual(['sans', 'avec']);
  });

  it('un `quote` qui n’est pas un objet ne devient pas un devis vide', () => {
    expect((lireProposal({ reference: 'X', quote: 'DEV-1' }) as Proposal).quote).toBeNull();
    expect((lireProposal({ reference: 'X', quote: [] }) as Proposal).quote).toBeNull();
  });
});
