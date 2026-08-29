// QJW6 — PARITÉ DES TROIS LOCALES DU TUNNEL « mon-toit ».
//
// CE QUE CES TESTS EXISTENT POUR ATTRAPER, ET POURQUOI LES AUTRES NE LE
// POUVAIENT PAS. Le tunnel a vécu en trois copies complètes (FR, EN, AR) avec
// chacune son `buildBody()`. Neuf réponses L-WEBT (`occupation_jour` + les
// équipements et leurs détails kW/créneau) et le jeton anti-fraude
// `appareilId` n'étaient collectés QUE sur la copie française — pendant des
// mois, sans un seul test rouge. Vérifié : les tests de locale existants
// épinglent chacun SA propre fonctionnalité par regex sur la source, donc
// aucun d'eux ne pouvait remarquer ce qu'une locale ne fait PAS.
//
// D'où deux assertions, et deux seulement :
//
//  (1) COMPORTEMENTALE — la seule qui compte. Le MÊME état fixe donné à
//      `construireCorps` pour les trois locales doit produire le MÊME ENSEMBLE
//      de clés. L'égalité d'ensembles échoue automatiquement dès qu'un champ
//      part dans une locale et pas dans une autre : c'est structurellement
//      impossible à contourner sans que ce test rougisse.
//
//  (2) STRUCTURELLE — le balisage, lui, RESTE par locale (la mise en page RTL
//      arabe diffère réellement). Chaque descripteur du registre qui porte un
//      `domId` doit donc voir son identifiant présent dans les TROIS sources
//      `.astro` : c'est ce qui attrape la dérive de balisage, exactement le
//      défaut qui a laissé les 16 identifiants L-WEBT absents des pages EN et
//      AR.
//
//  (3) L'exhaustivité i18n n'a besoin d'AUCUNE assertion ici : `LIBELLES` est
//      un `Record` sur l'union littérale des clés du registre (QJW4), donc une
//      clé sans ses trois traductions est déjà une erreur `tsc`.

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { CHAMPS_TUNNEL, DOM_IDS_TUNNEL, etatVide, type EtatTunnel } from '../src/lib/tunnel/champs';
import { construireCorps, type LocaleTunnel } from '../src/lib/tunnel/corps';
import { ERREURS } from '../src/lib/tunnel/i18n';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

const SOURCES: Array<[LocaleTunnel, string]> = [
  ['fr', read('../src/pages/devis/mon-toit.astro')],
  ['en', read('../src/pages/en/devis/mon-toit.astro')],
  ['ar', read('../src/pages/ar/devis/mon-toit.astro')],
];

const LOCALES: LocaleTunnel[] = ['fr', 'en', 'ar'];

/**
 * UN état fixe, le même pour les trois locales. Il remplit délibérément des
 * champs de TOUS les sous-panneaux (résidentiel, C&I, agricole, L-WEBT, carte,
 * tracking) : un champ qu'une seule locale émettrait se verrait immédiatement.
 */
function etatComplet(): EtatTunnel {
  return {
    ...etatVide(),
    nomComplet: 'Reda Kasri',
    telephone: '0612345678',
    email: 'reda@example.ma',
    ville: 'Casablanca',
    consentement: true,
    appelAutorise: true,
    mode: 'industriel',
    languePreferee: 'fr',
    factureHiverMad: 2200,
    trancheFacture: '1500-3000',
    factureProValeur: 4000,
    factureProUnite: 'mad',
    tarifProMadKwh: 1.2,
    raisonSociale: 'SARL Atlas',
    tension: 'bt',
    activite: 'day',
    categorieCommerciale: 'hotel',
    equipes: '3x8',
    typeSurface: 'bac_acier',
    surfaceM2: 900,
    sourceEau: 'puits',
    uniteEau: 'm3h',
    profondeurM: 40,
    hmtM: 55,
    besoinEau: 12,
    heuresPompage: 7,
    culture: 'avocatier',
    regionAgricole: 'gharb-loukkos',
    surfaceHa: 3,
    depenseCarburantMad: 4000,
    creneauVisitePartie: 'matin',
    creneauVisiteSemaine: 'cette_semaine',
    occupationJour: 'present',
    equipChauffeEau: true,
    equipChauffeEauKw: 2.4,
    equipChauffeEauCreneau: 'nuit',
    equipVoitureElectrique: true,
    equipVeKmSemaine: 150,
    equipVeChargeurKw: 7.4,
    equipVeCreneau: 'nuit',
    equipClim: true,
    equipClimPieces: 4,
    equipClimKw: 3.5,
    equipClimCreneau: 'soir',
    equipPiscine: true,
    equipPiscinePompeKw: 1.1,
    equipPiscineHeuresJour: 6.5,
    equipPiscineCreneau: 'soir',
    clientRef: 'KAS-1',
    idempotencyKey: 'idem-1',
    eventId: 'evt-1',
    appareilId: 'app-1',
    estimationAffichee: { kwc: 6.4, nbPanneaux: 9 },
    tracking: { utm_source: 'meta', fbclid: 'fb-1' },
    repereToit: { lat: 33.57, lng: -7.59 },
    contourToit: [[1, 2], [3, 4], [5, 6]],
    honeypot: '',
  };
}

const clesEmises = (locale: LocaleTunnel, etat: EtatTunnel): string[] =>
  Object.keys(construireCorps(etat, { messages: ERREURS[locale] }).body).sort();

describe('QJW6 (1) — égalité d’ENSEMBLES des clés émises par les trois locales', () => {
  it('un état complet produit exactement les mêmes clés en fr, en et ar', () => {
    const [reference, ...autres] = LOCALES.map((l) => clesEmises(l, etatComplet()));
    for (const [i, cles] of autres.entries()) {
      expect(cles, LOCALES[i + 1]).toEqual(reference);
    }
  });

  it('un état VIDE aussi (le cas où rien n’a été répondu)', () => {
    const [reference, ...autres] = LOCALES.map((l) => clesEmises(l, etatVide()));
    for (const [i, cles] of autres.entries()) {
      expect(cles, LOCALES[i + 1]).toEqual(reference);
    }
  });

  it('les 16 clés L-WEBT et appareilId sont bien DANS cet ensemble commun', () => {
    // Ce sont exactement celles qu'aucun visiteur anglophone ou arabophone
    // n'alimentait avant QJW5.
    const cles = clesEmises('en', etatComplet());
    for (const cle of [
      'occupation_jour',
      'equip_chauffe_eau_electrique', 'equip_chauffe_eau_kw', 'equip_chauffe_eau_creneau',
      'equip_voiture_electrique', 'equip_ve_km_semaine', 'equip_ve_chargeur_kw', 'equip_ve_creneau',
      'equip_clim', 'equip_clim_pieces', 'equip_clim_kw', 'equip_clim_creneau',
      'equip_piscine', 'equip_piscine_pompe_kw', 'equip_piscine_heures_jour', 'equip_piscine_creneau',
      'appareilId',
    ]) {
      expect(cles, cle).toContain(cle);
    }
  });

  it('la locale ne change QUE les messages d’erreur, jamais les clés', () => {
    // Un état invalide : les trois locales refusent les mêmes champs, avec
    // leurs propres mots. Le corps, lui, reste identique clé pour clé.
    const invalide = { ...etatVide(), mode: 'residentiel' };
    const rendus = LOCALES.map((l) => construireCorps(invalide, { messages: ERREURS[l] }));
    const champsEnErreur = rendus.map((r) => Object.keys(r.errors).sort());
    expect(champsEnErreur[1]).toEqual(champsEnErreur[0]);
    expect(champsEnErreur[2]).toEqual(champsEnErreur[0]);
    expect(Object.keys(rendus[1].body)).toEqual(Object.keys(rendus[0].body));
    // …et les mots, eux, diffèrent bien (sinon la couche i18n ne sert à rien).
    expect(rendus[1].errors.city).not.toBe(rendus[0].errors.city);
    expect(rendus[2].errors.city).not.toBe(rendus[0].errors.city);
  });
});

describe('QJW6 (2) — chaque domId du registre existe dans les TROIS sources', () => {
  it.each(SOURCES)('%s — porte tous les identifiants du registre', (locale, src) => {
    const manquants = DOM_IDS_TUNNEL.filter((id) => !src.includes(`id="${id}"`));
    expect(manquants, `${locale} : identifiants absents du balisage`).toEqual([]);
  });

  it('le registre couvre bien les 16 identifiants L-WEBT', () => {
    for (const id of [
      'mt-occupation-jour',
      'mt-equip-chauffe-eau', 'mt-equip-chauffe-eau-kw', 'mt-equip-chauffe-eau-creneau',
      'mt-equip-ve', 'mt-equip-ve-km', 'mt-equip-ve-kw', 'mt-equip-ve-creneau',
      'mt-equip-clim', 'mt-equip-clim-pieces', 'mt-equip-clim-kw', 'mt-equip-clim-creneau',
      'mt-equip-piscine', 'mt-equip-piscine-kw', 'mt-equip-piscine-heures', 'mt-equip-piscine-creneau',
    ]) {
      expect(DOM_IDS_TUNNEL, id).toContain(id);
    }
  });
});

describe('QJW6 — plus aucune page ne construit son propre corps', () => {
  it.each(SOURCES)('%s — n’a plus de buildBody local et importe le module partagé', (locale, src) => {
    expect(src, `${locale} : un buildBody local subsiste`).not.toContain('function buildBody(');
    expect(src, `${locale} : dérivation de payload recopiée`).not.toContain('function resolveRoofType(');
    expect(src, `${locale} : dérivation de payload recopiée`).not.toContain('function resolveProBillRange(');
    expect(src, `${locale} : n'importe pas le constructeur partagé`)
      .toContain("lib/tunnel/corps'");
    expect(src).toContain('construireCorps(lireEtatTunnel()');
  });
});

describe('QJW6 — invariants du registre', () => {
  it('aucun webhookKey en double (deux champs ne peuvent pas se marcher dessus)', () => {
    const cles = CHAMPS_TUNNEL.map((c) => c.webhookKey);
    // `mt-water-need` alimente DEUX descripteurs (débit m³/h vs besoin m³/j),
    // mais sous deux webhookKey distinctes — c'est le domId qui se partage,
    // jamais la clé de sortie.
    expect(new Set(cles).size, `doublons : ${cles.filter((k, i) => cles.indexOf(k) !== i)}`)
      .toBe(cles.length);
  });

  it('aucune clé de registre en double', () => {
    const cles = CHAMPS_TUNNEL.map((c) => c.cle);
    expect(new Set(cles).size).toBe(cles.length);
  });
});
