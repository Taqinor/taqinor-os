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
  ['quote.date', (x) => x.quote?.date],
  ['quote.client_name', (x) => x.quote?.clientName],
  ['quote.mode_installation', (x) => x.quote?.modeInstallation],
  ['quote.puissance_kwc', (x) => x.quote?.puissanceKwc],
  ['quote.nb_options', (x) => x.quote?.nbOptions],
  ['quote.display_total', (x) => x.quote?.displayTotal],
  ['quote.sans_ok', (x) => x.quote?.sansOk],
  ['quote.avec_ok', (x) => x.quote?.avecOk],
  ['quote.scenario', (x) => x.quote?.scenario],
  ['quote.totaux_sans', (x) => x.quote?.totauxSans],
  ['quote.totaux_avec', (x) => x.quote?.totauxAvec],
  // QJW20 — les FEUILLES de la chaîne argent, une par une : `lireTotaux` les
  // lit toutes, et un renommage à ce niveau-là doit rougir comme un autre.
  ['quote.totaux_sans.ht_net', (x) => x.quote?.totauxSans?.htNet],
  ['quote.totaux_sans.tva', (x) => x.quote?.totauxSans?.tva],
  ['quote.totaux_sans.ttc', (x) => x.quote?.totauxSans?.ttc],
  ['quote.totaux_avec.ht_net', (x) => x.quote?.totauxAvec?.htNet],
  ['quote.totaux_avec.tva', (x) => x.quote?.totauxAvec?.tva],
  ['quote.totaux_avec.ttc', (x) => x.quote?.totauxAvec?.ttc],
  ['option_totals.sans_batterie', (x) => x.optionTotals?.sansBatterie],
  ['option_totals.avec_batterie', (x) => x.optionTotals?.avecBatterie],
  ['option_totals.sans_batterie.ht_net', (x) => x.optionTotals?.sansBatterie?.htNet],
  ['option_totals.sans_batterie.tva', (x) => x.optionTotals?.sansBatterie?.tva],
  ['option_totals.sans_batterie.ttc', (x) => x.optionTotals?.sansBatterie?.ttc],
  ['option_totals.avec_batterie.ht_net', (x) => x.optionTotals?.avecBatterie?.htNet],
  ['option_totals.avec_batterie.tva', (x) => x.optionTotals?.avecBatterie?.tva],
  ['option_totals.avec_batterie.ttc', (x) => x.optionTotals?.avecBatterie?.ttc],
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

  it('chaque clé surveillée existe VRAIMENT dans l’échantillon (une garde sur une clé fantôme ne garde rien)', () => {
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

// ── QJW20 — LA COUVERTURE DES FEUILLES, DANS LES DEUX SENS ──────────────────
//
// CE QUI MANQUAIT. `CLES_LUES` ci-dessus est une table des clés que la page
// LIT : elle prouve qu'un renommage backend rougit. Elle ne dit RIEN de ce
// qu'on n'a pas pensé à lire. Une clé ajoutée à `proposal_data` — la
// principale charge utile client de la page proposition — pouvait donc
// arriver sans qu'aucun test ne force une DÉCISION à son sujet. C'est
// exactement l'angle mort que `taille_detail` n'a plus depuis QJW10 : là-bas,
// chaque feuille du contrat est soit LUE, soit REFUSÉE avec une raison
// ÉCRITE. `proposal_data` était la dernière surface gardée d'un seul côté.
//
// CE QUE « LUE » VEUT DIRE ICI, EXACTEMENT : lue par le LECTEUR TYPÉ
// `lireProposal`. Beaucoup de feuilles refusées ci-dessous sont bel et bien
// AFFICHÉES par la page — mais par le frontmatter et les modules de rendu
// (`lib/proposition.ts` hors lecteur, `lib/proposalCurve.ts`,
// `lib/dayProfiles.ts`, `lib/jourTypeData.ts`, `lib/offresTailles.ts`,
// `pages/proposition/[...token].astro`), qui ont leur propre chemin de
// lecture. Le refus n'est donc pas « ce nombre n'est nulle part » : c'est
// « ce lecteur-ci ne le lit pas, et voici pourquoi » — la même nuance que
// `NON_AFFICHE` porte pour les chiffres de tête de `taille_detail`.
//
// L'ÉCHANTILLON N'EST JAMAIS MODIFIÉ. Il est le jumeau JSON-égal de
// `apps/ventes/contract_samples/proposal_data.json` et la garde de parité
// QJW1 le compare octet à octet : le cas négatif ci-dessous injecte donc sa
// feuille dans une COPIE EN MÉMOIRE, jamais dans le fichier.

/**
 * LES SEPT BLOCS QUI ONT LEUR PROPRE CONTRAT PACT10. L'échantillon les reprend
 * « en version COMPACTE, illustrative de la NATURE seulement — le contrat
 * dédié fait foi sur la forme complète » (`notes.cles_avec_contrat_dedie`).
 * Descendre dedans fabriquerait des justifications pour des clés dont la forme
 * autoritaire vit ailleurs, et qui se périmeraient à la première évolution du
 * contrat dédié : on s'arrête donc à la clé, et la décision porte sur elle.
 */
const CONTRAT_DEDIE = [
  'variantes_servables', 'profils_comparatifs', 'offres_tailles',
  'calepinage_options', 'paliers_batterie', 'couverture_batterie',
  'conception_electrique',
] as const;

/** Les trois exemples du contrat — la charge utile ; le reste est de la prose. */
const EXEMPLES = ['exemple', 'exemple_standard', 'exemple_sections_masquees'] as const;

/**
 * Toutes les feuilles d'un document, en chemins pointés. Trois conventions,
 * les mêmes que QJW10 plus deux que CETTE charge utile impose :
 *  1. un TABLEAU est une feuille (`monthly_production[]`) — c'est la série
 *     entière qui est servie ou omise, pas ses éléments un par un ;
 *  2. une clé NUMÉRIQUE est de la DONNÉE, pas une clé de contrat : le mois
 *     d'un `jours_types` devient `*` (sinon la table dirait quatre fois la
 *     même chose, et un cinquième mois servi rougirait pour rien) ;
 *  3. un bloc à contrat dédié s'arrête à sa racine (voir `CONTRAT_DEDIE`).
 */
function feuilles(noeud: unknown, prefixe: string, sortie: Set<string>, racineDediee = false): void {
  if (Array.isArray(noeud)) { sortie.add(`${prefixe}[]`); return; }
  if (noeud && typeof noeud === 'object') {
    const entrees = Object.entries(noeud as Record<string, unknown>);
    if (racineDediee || entrees.length === 0) { sortie.add(prefixe); return; }
    for (const [k, v] of entrees) {
      const segment = /^\d+$/.test(k) ? '*' : k;
      feuilles(v, prefixe ? `${prefixe}.${segment}` : segment, sortie);
    }
    return;
  }
  sortie.add(prefixe);
}

/** `estimation_conso.ajouts` est indexé par APPAREIL : même règle que les mois. */
const normaliserAjouts = (p: string): string =>
  p.replace(/^estimation_conso\.ajouts\.[^.[]+/, 'estimation_conso.ajouts.*');

/** Les feuilles de la CHARGE UTILE (union des trois exemples). */
function feuillesPayload(doc: Record<string, unknown>): string[] {
  const brut = new Set<string>();
  for (const ex of EXEMPLES) {
    const exemple = doc[ex] as Record<string, unknown> | undefined;
    if (!exemple) continue;
    for (const [k, v] of Object.entries(exemple)) {
      feuilles(v, k, brut, (CONTRAT_DEDIE as readonly string[]).includes(k));
    }
  }
  const chemins = new Set([...brut].map(normaliserAjouts));
  // Un exemple porte `gammes: null` là où un autre porte `gammes.soeur.nom` :
  // la RACINE nue n'est alors pas une feuille, c'est un chemin déjà énuméré
  // plus profondément. On la retire pour ne pas demander deux décisions pour
  // une seule clé.
  return [...chemins]
    .filter((c) => {
      const base = c.endsWith('[]') ? c.slice(0, -2) : c;
      if (c !== base) return true;
      return ![...chemins].some((a) => a !== c && (a.startsWith(`${base}.`) || a === `${base}[]`));
    })
    .sort();
}

/** Les chemins qui ne sont PAS de la charge utile (documentation du contrat). */
function feuillesDocumentation(doc: Record<string, unknown>): string[] {
  const out = new Set<string>();
  for (const [k, v] of Object.entries(doc)) {
    if ((EXEMPLES as readonly string[]).includes(k)) continue;
    feuilles(v, k, out);
  }
  return [...out].sort();
}

/**
 * LUES SANS PASSER PAR LA GARDE DE RENOMMAGE. `lireProposal` lit bien ces cinq
 * clés, mais la garde `CLES_LUES` ne peut pas les exercer : l'échantillon en
 * porte la valeur NEUTRE (`""` ou `false`), et le lecteur rend la même chose
 * pour une clé renommée que pour une chaîne vide — le renommage « ne changerait
 * rien » et le test rougirait à tort. La décision est donc écrite ici.
 */
const LUES_HORS_RENOMMAGE: Readonly<Record<string, string>> = {
  'reference': 'Lue par `lireProposal`, et sa disparition rend la proposition ILLISIBLE — c’est son propre test juste au-dessus, pas une ligne de `CLES_LUES` (qui exige un payload encore lisible).',
  'apercu_interne': 'Lue (`p.apercu_interne === true`), mais l’échantillon vaut `false` : un renommage rendrait `false` lui aussi, donc la garde de renommage ne peut pas l’exercer.',
  'accepted': 'Lue (`p.accepted === true`), mais l’échantillon vaut `false` : même angle mort de la garde de renommage que `apercu_interne`.',
  'accepte_par_nom': 'Lue, mais l’échantillon porte la chaîne VIDE — que le lecteur rend `null`, exactement comme une clé absente : indiscernable par renommage.',
  'date_acceptation': 'Lue, mais l’échantillon porte la chaîne VIDE : `null` avant comme après un renommage, donc indiscernable par renommage.',
};

/**
 * LES DÉCISIONS ÉCRITES. Chaque feuille que `lireProposal` ne lit PAS est ici,
 * avec ce qu'elle est et pourquoi ce lecteur ne la lit pas. C'est le prix à
 * payer pour qu'une clé ajoutée demain devienne rouge au lieu d'arriver sans
 * que personne n'ait tranché.
 */
const NON_LU: Readonly<Record<string, string>> = {
  // ── Contrôle de la réponse, pas une valeur de proposition ────────────────
  'detail': 'Message d’erreur des réponses 404/403 (jeton expiré, OTP non vérifié) : la page traite l’échec par le code HTTP, elle ne lit pas ce texte.',
  'mode_kpis': 'Bloc de KPI propre aux modes non résidentiels : rendu par le frontmatter selon `mode_installation`, jamais par le lecteur typé.',
  'niveau_masque[]': 'Liste de ce que le niveau `standard` a retiré : servie au rendu serveur pour l’expliquer au client, hors périmètre du lecteur typé.',
  'resync_apres_envoi': 'Drapeau de resynchronisation après envoi : lu par le frontmatter pour son bandeau, pas par `lireProposal`.',

  // ── Les sept blocs à CONTRAT DÉDIÉ (voir `CONTRAT_DEDIE`) ────────────────
  'conception_electrique': 'Conception électrique : sa forme complète est gardée par son propre contrat PACT10 `conception_electrique.json` ; ici elle n’est qu’illustrative.',
  'offres_tailles': 'Les trois tailles proposées : forme gardée par `offres_tailles.json` et lue par `lib/offresTailles.ts`, pas par le lecteur typé.',
  'calepinage_options': 'Calepinage par taille : forme gardée par `calepinage_options.json` ; la page la lit pour la visionneuse 3D, pas `lireProposal`.',
  'couverture_batterie': 'Courbe de couverture par nombre de packs : forme gardée par `couverture_batterie.json`, lue par le curseur batterie.',
  'paliers_batterie[]': 'Paliers de dimensionnement batterie : forme gardée par `paliers_batterie.json`, lue par le curseur batterie.',
  'profils_comparatifs': 'Simulation par profil d’occupation : forme gardée par `profils_comparatifs.json`, rendue par le frontmatter.',

  // ── `quote` — l'objet INTERNE du moteur, hors périmètre de ce contrat ────
  // `notes.portee_de_quote` le dit : la forme interne de `quote` est
  // documentée par `devis_composition.json`/`devis_totaux.json`. Le lecteur
  // typé n'en prend que l'entête et la chaîne argent.
  'quote.sans_items[]': 'Lignes du devis en niveau `standard` (kit agrégé) : rendues par le frontmatter depuis le dict interne du moteur, jamais par le lecteur typé.',

  // ── Multi-villa — un mode que le lecteur typé ne couvre pas ──────────────
  'nombre_proprietes': 'Nombre de propriétés du mode multi-villa : lu par le frontmatter quand ce mode est actif, pas par le lecteur typé.',
  'multi_villa': 'Détail du mode multi-villa (répartition par propriété) : rendu par le frontmatter, hors périmètre du lecteur typé.',
  'display_total_multi': 'Total affiché du mode multi-villa : rendu par le frontmatter à côté de son propre tableau, pas par le lecteur typé.',
  'totaux_multi': 'Chaîne HT→TVA→TTC du mode multi-villa : rendue par le frontmatter, hors périmètre du lecteur typé.',

  // ── Calepinage brut ──────────────────────────────────────────────────────
  'roof_layout.version': 'Version du format de calepinage : lue par la visionneuse (`scripts/roofPro11`) pour choisir son décodeur, pas par le lecteur typé.',
  'roof_layout.zones[]': 'Zones et panneaux dessinés sur le toit : lus par la visionneuse 3D, jamais par le lecteur typé (qui n’en garde que l’URL de la photo).',

  // ── `savings_method` — la méthode d'économie, rendue en toutes lettres ───
  'savings_method.model': 'Modèle d’économie retenu : la page en rend la version RACINE (`savings_model`, elle LUE) — lire les deux ferait deux chemins pour un même mot.',
  'savings_method.facture_actuelle': 'Facture actuelle du bloc méthode : la page rend la version racine `facture_sans_solaire`, qui est lue — pas ce doublon.',
  'savings_method.facture_avec_solaire': 'Facture après solaire du bloc méthode : la version racine `facture_avec_solaire_s` est lue à sa place.',
  'savings_method.economie': 'Économie mensuelle du bloc méthode : dérivée des deux factures que la page rend déjà — l’afficher en plus serait un troisième chiffre pour la même chose.',
  'savings_method.approximatif': 'Drapeau « estimation » de la méthode : rendu par le frontmatter dans sa mention de méthode, pas par le lecteur typé.',
  'savings_method.ligne_methode': 'Phrase qui explique le calcul au client : rendue telle quelle par le frontmatter, jamais reformatée par le lecteur typé.',
  'savings_method.exemple': 'Exemple chiffré facultatif de la méthode : rendu par le frontmatter quand il est servi, hors périmètre du lecteur typé.',

  // ── `hypotheses` — le bloc « Nos hypothèses », rendu au serveur ──────────
  'hypotheses.titre': 'Titre du bloc d’hypothèses : rendu par le frontmatter, avec sa traduction FR/EN/AR — le lecteur typé ne porte aucun libellé.',
  'hypotheses.items[]': 'Les hypothèses en toutes lettres : rendues par le frontmatter, hors périmètre du lecteur typé.',
  'hypotheses.tarif_kwh': 'Tarif kWh retenu : rendu par le frontmatter dans le bloc d’hypothèses, pas par le lecteur typé.',
  'hypotheses.tarif_kwh_txt': 'Le même tarif DÉJÀ formaté par le serveur (« 1,36 MAD/kWh (tranche 3) ») : la page imprime ce texte, elle ne le refabrique pas.',
  'hypotheses.tranche_source': 'D’où vient la tranche tarifaire (facture réelle ou estimation) : rendu par le frontmatter avec la mention correspondante.',
  'hypotheses.tranche_approximatif': 'Drapeau « tranche approximative » : rendu par le frontmatter à côté du tarif, pas par le lecteur typé.',
  'hypotheses.autoconso_first': 'Drapeau « autoconsommation prioritaire » (loi 82-21) : rendu par le frontmatter dans la liste des hypothèses.',
  'hypotheses.productible_kwh_kwc': 'Productible retenu (kWh/kWc) : rendu par le frontmatter parmi les hypothèses, hors périmètre du lecteur typé.',

  // ── `gammes` — la proposition sœur (Essentielle / Premium) ───────────────
  'gammes.envoi': 'Ce que le dialogue d’envoi a coché (une gamme, ou les deux) : lu par le frontmatter pour décider s’il montre la sœur.',
  'gammes.courante.nom': 'Nom de la gamme affichée : rendu par le frontmatter dans le sélecteur de gammes, pas par le lecteur typé.',
  'gammes.courante.recommandee': 'Drapeau « recommandée » de la gamme affichée : rendu par le frontmatter sous forme de pastille.',
  'gammes.courante.reference': 'Référence du devis de la gamme affichée : la page rend la référence RACINE, qui est lue — pas ce doublon.',
  'gammes.courante.total_ttc': 'Total TTC de la gamme affichée : la page rend le total racine (`option_totals`), lu — deux chemins pour un même montant sont exactement ce qu’on évite.',
  'gammes.soeur.nom': 'Nom de la gamme sœur : rendu par le frontmatter dans la carte de comparaison.',
  'gammes.soeur.recommandee': 'Drapeau « recommandée » de la sœur : rendu par le frontmatter sur sa carte.',
  'gammes.soeur.reference': 'Référence du devis de la gamme sœur : rendue par le frontmatter, hors périmètre du lecteur typé.',
  'gammes.soeur.total_ttc': 'Total TTC de la gamme sœur : rendu par le frontmatter sur sa carte, jamais recalculé côté client.',
  'gammes.soeur.ecart_ttc': 'Écart de prix avec la sœur : SERVI par le backend et rendu tel quel — la page ne soustrait jamais deux totaux elle-même.',
  'gammes.soeur.proposition_path': 'Lien vers la proposition de la gamme sœur : posé par le frontmatter dans l’ancre, pas par le lecteur typé.',
  'gammes.comparatif.familles_diff[]': 'Familles de matériel qui diffèrent entre les deux gammes : rendues par le frontmatter dans le comparatif.',

  // ── `economies_mensuelles` — le bloc « mois par mois » (CJ2b) ────────────
  'economies_mensuelles.sans[]': 'Les douze économies mensuelles sans batterie : lues par le frontmatter pour la grille des mois, pas par le lecteur typé.',
  'economies_mensuelles.avec[]': 'Les douze économies mensuelles avec batterie : même grille, même chemin de lecture — hors périmètre du lecteur typé.',
  'economies_mensuelles.total_sans': 'Total annuel sans batterie du bloc mois par mois : rendu par le frontmatter sous la grille.',
  'economies_mensuelles.total_avec': 'Total annuel avec batterie : rendu par le frontmatter dans le bloc « · avec batterie : » sous la grille.',
  'economies_mensuelles.devise': 'MAD est déjà dans le texte que `formatMAD` produit : l’imprimer une seconde fois donnerait « 640 MAD MAD ».',
  'economies_mensuelles.modele': 'Modèle de calcul (horaire ou mensuel) : rendu par le frontmatter dans la note de méthode sous la grille.',
  'economies_mensuelles.estimation': 'Drapeau « estimation » : rendu par le frontmatter sous la grille (« consommation déduite de votre facture »).',
  'economies_mensuelles.note': 'Phrase de méthode servie par le backend : imprimée telle quelle par le frontmatter, jamais reformulée côté client.',

  // ── `economies_periodes` — les mêmes économies, par période (LECO) ───────
  'economies_periodes.devise': 'Devise du bloc par périodes : déjà portée par le texte formaté — même raison que pour le bloc mois par mois.',
  'economies_periodes.modele': 'Modèle de calcul du bloc par périodes : rendu par le frontmatter dans sa note de méthode.',
  'economies_periodes.estimation': 'Drapeau « estimation » du bloc par périodes : rendu par le frontmatter à côté des montants.',
  'economies_periodes.source_mois': 'D’où vient le montant du mois affiché (« jour type du mois ») : mention de provenance rendue par le frontmatter.',
  'economies_periodes.source_retour_investissement': 'D’où vient le retour sur investissement (`quote.roi_s`/`roi_a`) : mention de provenance, rendue par le frontmatter.',
  'economies_periodes.sans.annuel_mad': 'Économie annuelle sans batterie du bloc par périodes : rendue par le frontmatter, hors périmètre du lecteur typé.',
  'economies_periodes.sans.mois[]': 'Économies mois par mois, variante sans batterie : rendues par le frontmatter dans le sélecteur de période.',
  'economies_periodes.sans.saisons.ete': 'Économie d’été sans batterie : rendue par le frontmatter dans la vue par saison.',
  'economies_periodes.sans.retour_investissement_ans': 'Retour sur investissement sans batterie : SERVI par le backend et rendu tel quel, jamais recalculé côté client.',
  'economies_periodes.avec.annuel_mad': 'Économie annuelle avec batterie : rendue par le frontmatter, hors périmètre du lecteur typé.',
  'economies_periodes.avec.mois[]': 'Économies mois par mois, variante avec batterie : rendues par le frontmatter dans le sélecteur de période.',
  'economies_periodes.avec.saisons.ete': 'Économie d’été avec batterie : rendue par le frontmatter dans la vue par saison.',
  'economies_periodes.avec.retour_investissement_ans': 'Retour sur investissement avec batterie : servi par le backend, rendu tel quel.',

  // ── `courbes_journalieres` — la courbe du jour (WJ119) ───────────────────
  'courbes_journalieres.note_horaire': 'Phrase de méthode de la courbe journalière : imprimée telle quelle par le frontmatter.',
  'courbes_journalieres.occupation': 'Profil d’occupation retenu : lu par `lib/proposalCurve.ts` pour tracer la courbe, pas par le lecteur typé.',
  'courbes_journalieres.occupation_source': 'D’où vient ce profil (lead, ou défaut) : mention de provenance rendue à côté de la courbe.',
  'courbes_journalieres.unites.forme': 'Libellé d’unité de la forme horaire (« part du total du jour ») : documentation d’unité, rendue au besoin, jamais un nombre.',
  'courbes_journalieres.unites.kwh_jour': 'Libellé d’unité des kWh/jour : documentation d’unité du contrat, pas une valeur à lire.',
  'courbes_journalieres.unites.pic_kw': 'Libellé d’unité du pic (kW) : documentation d’unité du contrat, pas une valeur à lire.',
  'courbes_journalieres.unites.batterie_kwh': 'Libellé d’unité de la batterie (kWh) : documentation d’unité du contrat, pas une valeur à lire.',
  'courbes_journalieres.production.forme[]': 'Forme horaire de la production (somme = 1) : lue par `lib/proposalCurve.ts` pour dessiner, pas par le lecteur typé.',
  'courbes_journalieres.production.kwh_jour': 'Production du jour type (kWh) : lue par le traceur de courbe, hors périmètre du lecteur typé.',
  'courbes_journalieres.production.pic_kw': 'Pic de production du jour type (kW) : lu par le traceur de courbe, hors périmètre du lecteur typé.',
  'courbes_journalieres.consommation.forme[]': 'Forme horaire de la consommation : lue par le traceur de courbe, jamais par le lecteur typé.',
  'courbes_journalieres.consommation.kwh_jour': 'Consommation du jour type (kWh) : lue par le traceur de courbe, hors périmètre du lecteur typé.',

  // ── `jours_types` — quatre journées de référence (clés = MOIS) ───────────
  'jours_types.*.prod_kw[]': 'Production heure par heure d’un jour type : lue par `lib/jourTypeData.ts`, jamais par le lecteur typé.',
  'jours_types.*.conso_kw[]': 'Consommation heure par heure d’un jour type : lue par `lib/jourTypeData.ts`, hors périmètre du lecteur typé.',
  'jours_types.*.prod_jour_kwh': 'Total produit sur le jour type : servi par le backend et rendu tel quel sous le graphe.',
  'jours_types.*.conso_jour_kwh': 'Total consommé sur le jour type : servi par le backend et rendu tel quel sous le graphe.',
  'jours_types.*.autoconsomme_kwh': 'Part autoconsommée du jour type : servie par le backend, rendue sous le graphe — jamais dérivée côté client.',
  'jours_types.*.surplus_kwh': 'Surplus injecté du jour type : servi par le backend, rendu sous le graphe — jamais dérivé côté client.',

  // ── `estimation_conso` — la consommation reconstituée ────────────────────
  'estimation_conso.base_mensuelle[]': 'Consommation de base mois par mois : lue par le frontmatter pour expliquer l’estimation, pas par le lecteur typé.',
  'estimation_conso.ajouts.*[]': 'Le supplément mensuel d’un appareil déclaré (piscine, clim…) : lu par le frontmatter dans le détail de l’estimation.',
  'estimation_conso.totale_mensuelle[]': 'Consommation totale reconstituée : la page rend la version racine `monthly_consumption`, qui est lue — pas ce doublon.',

  // ── `dimensionnement_options` / `production_par_option` ──────────────────
  'dimensionnement_options.sans.nb_panneaux': 'Nombre de panneaux de l’option sans batterie : rendu par le frontmatter dans le comparatif des deux options.',
  'dimensionnement_options.sans.puissance_kwc': 'Puissance de l’option sans batterie : rendue par le frontmatter dans le comparatif des options.',
  'dimensionnement_options.sans.nb_batteries': 'Nombre de batteries de l’option sans batterie (zéro) : rendu par le frontmatter dans le comparatif.',
  'dimensionnement_options.sans.capacite_batterie_kwh': 'Capacité batterie de l’option sans batterie (`null`) : rendue par le frontmatter, ou omise — jamais un zéro fabriqué.',
  'dimensionnement_options.sans.production_annuelle_kwh': 'Production annuelle de l’option sans batterie : rendue par le frontmatter dans le comparatif des options.',
  'dimensionnement_options.avec.nb_panneaux': 'Nombre de panneaux de l’option avec batterie : rendu par le frontmatter dans le comparatif.',
  'dimensionnement_options.avec.puissance_kwc': 'Puissance de l’option avec batterie : rendue par le frontmatter dans le comparatif des options.',
  'dimensionnement_options.avec.nb_batteries': 'Nombre de batteries de l’option avec batterie : rendu par le frontmatter dans le comparatif.',
  'dimensionnement_options.avec.capacite_batterie_kwh': 'Capacité de la banque de l’option avec batterie : rendue par le frontmatter dans le comparatif.',
  'dimensionnement_options.avec.production_annuelle_kwh': 'Production annuelle de l’option avec batterie : rendue par le frontmatter dans le comparatif.',
  'dimensionnement_options.divergent': 'Drapeau « les deux options ne dimensionnent pas pareil » : lu par le frontmatter pour décider s’il montre le comparatif.',
  'production_par_option.sans': 'Série de production propre à l’option sans batterie, quand elle diffère : lue par le frontmatter pour son graphe.',
  'production_par_option.avec': 'Série de production propre à l’option avec batterie, quand elle diffère : lue par le frontmatter pour son graphe.',

  // ── Batterie : régime, balayage, paliers ─────────────────────────────────
  'batterie_regime.remplissage_moyen_pct': 'Remplissage moyen de la banque : servi par le backend et rendu tel quel dans le bloc batterie.',
  'batterie_regime.couverture_glitch_pct': 'Couverture assurée pendant une coupure : servie par le backend, rendue telle quelle dans le bloc batterie.',
  'balayage_stockage.paliers[]': 'Les paliers de stockage explorés (capacité, coût, payback) : lus par le frontmatter pour le balayage, pas par le lecteur typé.',
  'balayage_stockage.refuse.nb_packs': 'Nombre de packs du palier ÉCARTÉ : rendu par le frontmatter pour dire pourquoi on ne l’a pas retenu.',
  'balayage_stockage.refuse.capacite_kwh': 'Capacité du palier écarté : rendue par le frontmatter avec la raison du refus.',
  'balayage_stockage.refuse.remplissage_pire_mois_pct': 'Remplissage du pire mois du palier écarté — c’est LA raison du refus : rendue par le frontmatter, pas par le lecteur typé.',

  // ── `tranche_tarifaire` — la tranche ONEE visée ──────────────────────────
  'tranche_tarifaire.tranche_actuelle.libelle': 'Libellé de la tranche ONEE actuelle : rendu par le frontmatter, avec sa traduction — le lecteur typé ne porte aucun libellé.',
  'tranche_tarifaire.tranche_visee.libelle': 'Libellé de la tranche visée après solaire : rendu par le frontmatter dans le même bloc.',
  'tranche_tarifaire.cible_kwh_mois': 'Consommation mensuelle à ne pas dépasser pour tomber dans la tranche visée : rendue par le frontmatter.',
  'tranche_tarifaire.residuel_kwh_mois': 'Consommation résiduelle prévue après solaire : rendue par le frontmatter à côté de la cible.',

  // ── Le reste des blocs additifs ──────────────────────────────────────────
  'bankable.p50_kwh': 'Productible P50 du dossier bancable : rendu par le frontmatter dans le bloc bancabilité, hors périmètre du lecteur typé.',
  'bankable.economies_25_ans': 'Économies cumulées sur 25 ans du dossier bancable : servies par le backend et rendues telles quelles.',
  'bankable.source': 'Source du productible bancable (PVGIS…) : mention de provenance rendue par le frontmatter sous le chiffre.',
  'parametres_site.orientation': 'Orientation retenue pour le site : rendue par le frontmatter dans le rappel des paramètres d’étude.',
  'parametres_site.inclinaison_deg': 'Inclinaison retenue : rendue par le frontmatter dans le rappel des paramètres d’étude.',
  'parametres_site.source_irradiation': 'Source d’irradiation (PVGIS) : mention de provenance rendue par le frontmatter, jamais un nombre.',
  'options_proposees[]': 'Options commerciales proposées en plus (extension de garantie…) : rendues par le frontmatter dans leur propre bloc.',
  'lignes_structure[]': 'Titres de structure du devis (sections, ordre) : rendus par le frontmatter pour ordonner l’affichage des lignes.',
  'variants[]': 'Les variantes de ce devis (v2, v3…) : rendues par le frontmatter dans le sélecteur de variantes, pas par le lecteur typé.',
};

/** La prose du contrat : jamais servie à un navigateur, mais elle se décide aussi. */
const NON_LU_DOCUMENTATION: Readonly<Record<string, string>> = {
  'endpoint': 'Documentation du contrat : la route elle-même (`GET /api/django/public/proposal/<token>/data/`), pas une donnée.',
  'forme_serveur': 'Déclaration pour `scripts/check_api_shapes.py` : elle pilote la garde de forme côté serveur, elle n’est jamais servie au navigateur.',
  'pourquoi': 'Documentation du contrat : pourquoi cette carte existe (l’incident PACT10 du 03/08/2026).',
  'notes.structure_de_la_reponse': 'Note de contrat : les 44 clés de base et les ~17 additives (documentation).',
  'notes.cles_additives_15_a_17': 'Note de contrat : la liste des clés additives (documentation).',
  'notes.portee_de_quote': 'Note de contrat : la forme interne de `quote` est hors périmètre (documentation).',
  'notes.cles_avec_contrat_dedie': 'Note de contrat : les blocs qui ont leur propre contrat PACT10 (documentation) — c’est elle que `CONTRAT_DEDIE` doit suivre.',
  'notes.additif_vs_null': 'Note de contrat : clé de base à `null` contre clé additive ABSENTE (documentation).',
  'notes.argent': 'Note de contrat : aucune clé ne porte `prix_achat` ni de marge, règle #4 (documentation).',
  'notes.futur_test_de_forme': 'Note de contrat : le test de forme QJR7 viendra plus tard (documentation).',
  'notes.forme_serveur_qjr228': 'Note de contrat : pourquoi cette carte déclare `forme_serveur` (documentation).',
  'notes.cle_detail': 'Note de contrat : pourquoi `detail` figure dans l’exemple à `null` (documentation).',
};

describe('QJW20 — chaque feuille de `proposal_data` est soit LUE, soit REFUSÉE par écrit', () => {
  const PAYLOAD = feuillesPayload(CONTRAT);
  const DOCUMENTATION = feuillesDocumentation(CONTRAT);
  const LUES = new Set<string>([
    ...CLES_LUES.map(([c]) => c),
    ...Object.keys(LUES_HORS_RENOMMAGE),
  ]);
  const sansCrochets = (f: string): string => (f.endsWith('[]') ? f.slice(0, -2) : f);
  const estLue = (f: string): boolean => LUES.has(sansCrochets(f));
  const indecises = (feuilles_: readonly string[]): string[] =>
    feuilles_.filter((f) => !estLue(f) && NON_LU[f] === undefined);

  it('l’échantillon est bien lu et non vide (une garde sur zéro feuille ne garde rien)', () => {
    expect(PAYLOAD.length).toBeGreaterThan(100);
    expect(DOCUMENTATION.length).toBeGreaterThan(5);
    expect(LUES.size).toBeGreaterThan(30);
  });

  it('CHAQUE feuille de la charge utile est lue OU justifiée par écrit', () => {
    const orphelines = indecises(PAYLOAD);
    expect(
      orphelines,
      `feuille(s) de \`proposal_data\` sans décision — les LIRE dans \`lireProposal\` (et les déclarer dans CLES_LUES), ou les ajouter à NON_LU avec une raison ÉCRITE : ${orphelines.join(', ')}`,
    ).toEqual([]);
  });

  it('LE CAS NÉGATIF, EXÉCUTÉ : une feuille ajoutée au contrat rend la garde ROUGE', () => {
    // Sur une COPIE EN MÉMOIRE — l'échantillon commité n'est jamais touché,
    // la parité QJW1 avec `apps/ventes/contract_samples/proposal_data.json`
    // reste intacte.
    const copieContrat = JSON.parse(JSON.stringify(CONTRAT)) as Record<string, unknown>;
    (copieContrat.exemple as Record<string, unknown>).prime_etat_mad = 12000;
    ((copieContrat.exemple as Record<string, unknown>).bankable as Record<string, unknown>)
      .p90_kwh = 11200;

    expect(indecises(feuillesPayload(copieContrat)))
      .toEqual(['bankable.p90_kwh', 'prime_etat_mad']);
    // …et la garde reste verte sur le contrat RÉEL, non modifié.
    expect(indecises(PAYLOAD)).toEqual([]);
    expect(feuillesPayload(CONTRAT)).not.toContain('prime_etat_mad');
  });

  it('CHAQUE clé de la documentation du contrat est justifiée par écrit', () => {
    const orphelines = DOCUMENTATION.filter((c) => NON_LU_DOCUMENTATION[c] === undefined);
    expect(orphelines, `documentation sans décision : ${orphelines.join(', ')}`).toEqual([]);
  });

  it('AUCUNE justification périmée : toute clé de NON_LU existe encore dans le contrat', () => {
    const connues = new Set(PAYLOAD);
    const perimees = Object.keys(NON_LU).filter((c) => !connues.has(c));
    expect(
      perimees,
      `justification(s) sans feuille correspondante — le contrat a bougé : ${perimees.join(', ')}`,
    ).toEqual([]);
  });

  it('AUCUNE feuille n’est à la fois lue et refusée', () => {
    const doubles = Object.keys(NON_LU).filter((c) => estLue(c));
    expect(doubles, `décision contradictoire : ${doubles.join(', ')}`).toEqual([]);
  });

  it('chaque raison est une VRAIE phrase, pas un « n/a » qui vide la garde de son sens', () => {
    for (const [cle, raison] of Object.entries({ ...NON_LU, ...NON_LU_DOCUMENTATION, ...LUES_HORS_RENOMMAGE })) {
      expect(raison.length, `${cle} : raison trop courte`).toBeGreaterThan(30);
      expect(raison, `${cle} : raison vide de contenu`).not.toMatch(/^(?:n\/a|na|tbd|todo|—|-)\.?$/i);
    }
  });

  it('les sept blocs à contrat dédié sont ceux que le contrat lui-même désigne', () => {
    // Si un huitième bloc gagnait son propre contrat PACT10, la note bougerait
    // et cette liste devrait bouger avec elle — jamais l’inverse.
    const note = String((CONTRAT.notes as Record<string, unknown>).cles_avec_contrat_dedie);
    for (const cle of CONTRAT_DEDIE) {
      expect(note, `${cle} n’est pas annoncée comme ayant un contrat dédié`).toContain(cle);
    }
  });

  it('les clés que `lireProposal` lit VRAIMENT sont toutes déclarées lues', () => {
    // La garde dans l'autre sens : le lecteur typé est relu, et chaque clé
    // snake qu'il consomme doit apparaître dans la table de couverture. Sans
    // elle, on pourrait « refuser » par écrit une clé que le lecteur lit.
    const LECTEUR = read('../src/lib/proposition.ts').slice(
      read('../src/lib/proposition.ts').indexOf('export function lireProposal'),
    );
    const corps = LECTEUR.slice(0, LECTEUR.indexOf('\n}'));
    const cles = [...corps.matchAll(/\bp\.([a-z0-9_]+)\b/g)].map((m) => m[1]!);
    expect(cles.length, 'le corps de `lireProposal` n’a pas été retrouvé').toBeGreaterThan(20);
    for (const c of cles) {
      expect(
        LUES.has(c),
        `\`${c}\` est LUE par \`lireProposal\` mais absente de la table de couverture`,
      ).toBe(true);
    }
  });
});
