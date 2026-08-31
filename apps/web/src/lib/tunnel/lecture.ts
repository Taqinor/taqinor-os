// QJW21 — LA LECTURE DU DOM DU TUNNEL, ÉCRITE UNE SEULE FOIS POUR LES TROIS
// LOCALES.
//
// CE QUE CE MODULE EXISTE POUR SUPPRIMER. QJW3 avait déjà réduit les trois
// `buildBody()` recopiés à UN constructeur piloté par le registre — mais la
// LECTURE, elle, restait recopiée trois fois : `lireEtatTunnel()` vivait à
// l'identique dans `src/pages/devis/mon-toit.astro`, `…/en/devis/mon-toit.astro`
// et `…/ar/devis/mon-toit.astro`. Trois copies d'une même liste de champs, donc
// trois occasions d'en oublier un : c'est EXACTEMENT ainsi que le bloc L-WEBT
// et `appareilId` étaient restés absents des pages EN et AR pendant des mois.
// La garde de parité ne pouvait pas le voir : elle construisait un état À LA
// MAIN puis appelait `construireCorps` trois fois — donc elle comparait trois
// fois la MÊME lecture (cf. tests/tunnelParite.test.ts avant QJW21).
//
// CE QUI RESTE À LA PAGE. Tout ce qui ne vient PAS d'un élément identifié :
// l'état interne des groupes de cartes (tension, activité, surface, source
// d'eau…), la carte (repère/contour), les jetons de session, le tracking, le
// mode et la langue active, et la facture C&I dont l'id DÉPEND du panneau actif.
// La page continue donc de lire SON propre DOM et de composer SON état — mais
// la partie « un champ ↔ un id » est unique, et c'est celle qui divergeait.
//
// PURETÉ : ce module ne touche à rien d'autre qu'au `Document` qu'on lui passe
// (jamais au `document` global implicitement), n'écrit nulle part, ne fabrique
// aucune valeur. Un élément absent rend exactement ce que rendaient les helpers
// des pages : `''`, `null` ou `false` — et c'est le registre (champs.ts) qui
// décide ensuite si la clé s'émet ou reste absente.

import type { EtatTunnel } from './champs';

/** Comment la valeur se lit sur l'élément — reproduit les helpers `val()`,
 *  `num()` et `coche()` que les trois pages portaient à l'identique. */
export type TypeLectureDom = 'texte' | 'nombre' | 'case';

export interface ChampDomTunnel {
  /** La propriété d'`EtatTunnel` alimentée. */
  readonly champ: keyof EtatTunnel;
  /** L'`id` de l'élément qui porte la réponse, identique dans les 3 locales. */
  readonly domId: string;
  readonly type: TypeLectureDom;
}

/**
 * LA TABLE — un champ, un id, un mode de lecture. Ajouter une question au
 * tunnel, c'est ajouter UNE ligne ici : les trois locales la lisent alors
 * ensemble, ou aucune. Ordre : celui de l'ancien `lireEtatTunnel()`, pour que
 * la revue ligne à ligne reste possible.
 */
export const CHAMPS_DOM_TUNNEL = [
  // ——— identité + contact ———
  { champ: 'nomComplet', domId: 'mt-name', type: 'texte' },
  { champ: 'telephone', domId: 'mt-phone', type: 'texte' },
  { champ: 'email', domId: 'mt-email', type: 'texte' },
  { champ: 'ville', domId: 'mt-city', type: 'texte' },
  { champ: 'consentement', domId: 'mt-consent', type: 'case' },
  // WJ51 — radio « Un conseiller peut m'appeler » (sinon : WhatsApp uniquement).
  { champ: 'appelAutorise', domId: 'mt-contact-phone', type: 'case' },

  // ——— facture résidentielle ———
  { champ: 'factureHiverMad', domId: 'mt-facture-hiver', type: 'nombre' },
  { champ: 'trancheFacture', domId: 'mt-bill', type: 'texte' },

  // ——— sous-panneau professionnel ———
  { champ: 'raisonSociale', domId: 'mt-raison-sociale', type: 'texte' },
  { champ: 'surfaceM2', domId: 'mt-surface-m2', type: 'nombre' },

  // ——— sous-panneau agricole (pompage) ———
  { champ: 'profondeurM', domId: 'mt-profondeur', type: 'nombre' },
  { champ: 'hmtM', domId: 'mt-hmt', type: 'nombre' },
  { champ: 'besoinEau', domId: 'mt-water-need', type: 'nombre' },
  // Le curseur part avec value="7" AVANT toute interaction : c'est le registre
  // qui le gate sur le mode agricole, jamais cette lecture.
  { champ: 'heuresPompage', domId: 'mt-heures-pompage', type: 'nombre' },
  { champ: 'culture', domId: 'mt-culture', type: 'texte' },
  { champ: 'surfaceHa', domId: 'mt-surface-ha', type: 'nombre' },
  { champ: 'depenseCarburantMad', domId: 'mt-fuel-spend', type: 'nombre' },

  // ——— L-WEBT : « Affiner mon profil de consommation » (facultatif) ———
  // Chaque détail kW/créneau est lu SANS condition ; le registre le gate sur sa
  // case parente, pour les trois locales à la fois.
  { champ: 'equipChauffeEau', domId: 'mt-equip-chauffe-eau', type: 'case' },
  { champ: 'equipChauffeEauKw', domId: 'mt-equip-chauffe-eau-kw', type: 'nombre' },
  { champ: 'equipChauffeEauCreneau', domId: 'mt-equip-chauffe-eau-creneau', type: 'texte' },
  { champ: 'equipVoitureElectrique', domId: 'mt-equip-ve', type: 'case' },
  { champ: 'equipVeKmSemaine', domId: 'mt-equip-ve-km', type: 'nombre' },
  { champ: 'equipVeChargeurKw', domId: 'mt-equip-ve-kw', type: 'nombre' },
  { champ: 'equipVeCreneau', domId: 'mt-equip-ve-creneau', type: 'texte' },
  { champ: 'equipClim', domId: 'mt-equip-clim', type: 'case' },
  { champ: 'equipClimPieces', domId: 'mt-equip-clim-pieces', type: 'nombre' },
  { champ: 'equipClimKw', domId: 'mt-equip-clim-kw', type: 'nombre' },
  { champ: 'equipClimCreneau', domId: 'mt-equip-clim-creneau', type: 'texte' },
  { champ: 'equipPiscine', domId: 'mt-equip-piscine', type: 'case' },
  { champ: 'equipPiscinePompeKw', domId: 'mt-equip-piscine-kw', type: 'nombre' },
  { champ: 'equipPiscineHeuresJour', domId: 'mt-equip-piscine-heures', type: 'nombre' },
  { champ: 'equipPiscineCreneau', domId: 'mt-equip-piscine-creneau', type: 'texte' },

  // ——— anti-spam ———
  // W317 — vide pour tout visiteur humain (champ masqué hors écran) ; rejeté
  // côté serveur si non vide.
  { champ: 'honeypot', domId: 'mt-hp', type: 'texte' },
] as const satisfies readonly ChampDomTunnel[];

/** Les champs d'`EtatTunnel` que ce module alimente (les autres restent à la page). */
export type CleChampDom = (typeof CHAMPS_DOM_TUNNEL)[number]['champ'];
export type ChampsDomLus = Pick<EtatTunnel, CleChampDom>;

/** `val()` des pages : la valeur brute, `''` si l'élément n'existe pas. */
function valeur(doc: Document, id: string): string {
  return (doc.getElementById(id) as HTMLInputElement | HTMLSelectElement | null)?.value ?? '';
}

/** `num()` des pages : nombre fini, sinon `null` — jamais une valeur inventée. */
function nombre(doc: Document, id: string): number | null {
  const brut = valeur(doc, id).trim();
  if (brut === '') return null;
  const n = Number(brut);
  return Number.isFinite(n) ? n : null;
}

/** `coche()` des pages : `true` seulement si la case existe ET est cochée. */
function coche(doc: Document, id: string): boolean {
  return (doc.getElementById(id) as HTMLInputElement | null)?.checked === true;
}

/**
 * Lit, dans le `Document` fourni, TOUS les champs « un champ ↔ un id » du
 * tunnel. Un id absent de CETTE page rend la valeur vide de son type — c'est
 * précisément ce qui rend une locale amputée VISIBLE dans le corps émis, donc
 * attrapable par la garde de parité.
 */
export function lireChampsDomTunnel(doc: Document): ChampsDomLus {
  // Construit dynamiquement : la table est la seule source, jamais une seconde
  // liste écrite à la main en dessous.
  const lus: Record<string, unknown> = {};
  for (const c of CHAMPS_DOM_TUNNEL) {
    lus[c.champ] =
      c.type === 'nombre' ? nombre(doc, c.domId) : c.type === 'case' ? coche(doc, c.domId) : valeur(doc, c.domId);
  }
  return lus as ChampsDomLus;
}
