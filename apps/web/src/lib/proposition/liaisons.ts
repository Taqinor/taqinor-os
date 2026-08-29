/**
 * QJW7 — LES DEUX TABLES DE LIAISON DE LA PAGE PROPOSITION.
 *
 * CE QUE CE MODULE EST. La DÉCLARATION — et rien d'autre — de ce que « charger
 * une autre taille » change sur la page : quels nœuds, dans quelle enveloppe,
 * depuis quelle donnée. Aujourd'hui cette connaissance est éparpillée dans
 * quatre fonctions de l'îlot `<script>` de `pages/proposition/[...token].astro`,
 * chacune devant être informée de CHAQUE champ à la main. Un champ y a déjà été
 * OUBLIÉ — le tableau de trésorerie année par année, câblé après coup (voir le
 * commentaire « F2 (revue Fable 29/08/2026) » de la page). Une table, elle,
 * s'énumère : on peut la comparer au contrat et voir ce qui manque (QJW10).
 *
 * CE QU'IL N'EST PAS. Il ne CALCULE aucun chiffre d'installation. Les valeurs
 * viennent du contrat `taille_detail.json` lu par `lib/tailleDetail.ts` ; ce
 * module ne fait que les FORMATER, avec les MÊMES fonctions que le rendu
 * serveur (`formatMAD`, `formatNumber`, `formatPercent`, `formatPayback`,
 * `dasharrayDonut`) — jamais un second formatage maison, jamais une somme, un
 * pourcentage ou un payback recalculé côté client (règle fondateur « zéro
 * chiffre inventé »).
 *
 * LA DISCIPLINE QUE LES TABLES ENCODENT, ET QUI NE BOUGE PAS.
 *  1. `lire` rend `null` ⇒ la taille chargée NE SERT PAS ce champ. Le moteur
 *     (QJW8) CACHE alors l'enveloppe et n'écrit RIEN. Il ne substitue jamais
 *     une valeur, et il ne relit jamais l'original sous une autre carte : un
 *     chiffre RÉEL attribué à la MAUVAISE offre est un mensonge de plus, pas
 *     de moins.
 *  2. L'omission est HÉRITÉE du serveur, jamais comblée : un bloc absent du
 *     payload reste absent de la page.
 *  3. Le retour sur « Recommandé » RESTAURE les textes ORIGINAUX moissonnés au
 *     chargement — jamais une reconstruction depuis les cartes.
 *
 * IMPORTÉ PAR RIEN À CE STADE (QJW7). Le moteur `swap.ts` (QJW8) consomme ces
 * types, et la bascule de l'îlot (QJW9) consomme les deux tables.
 */

import { dasharrayDonut, type TailleDetail } from '../tailleDetail';
import { formatMAD, formatNumber, formatPayback, formatPercent } from '../proposition';

// ── LE VOCABULAIRE PARTAGÉ AVEC LE MOTEUR ───────────────────────────────────
// Ces types vivent ICI, avec les tables, et non dans `swap.ts` : une table doit
// pouvoir être écrite et relue sans ouvrir le moteur, et `swap.ts` (QJW8) les
// importe depuis ce module. La dépendance va donc moteur → tables, jamais
// l'inverse.

/**
 * COMMENT ON MOISSONNE L'ORIGINAL D'UN NŒUD. Trois natures, et trois
 * seulement, parce que la page n'en a que trois : du texte, du balisage rendu
 * par le serveur (le corps du tableau année par année), et un attribut
 * géométrique (l'arc de l'anneau de couverture).
 */
export type ModeCapture = 'texte' | 'html' | { readonly attribut: string };

/** Un nœud piloté : son sélecteur, s'il en désigne un ou plusieurs, sa capture. */
export interface SpecNoeud {
  readonly sel: string;
  /** `true` ⇒ `querySelectorAll` (les douze cellules de mois, par exemple). */
  readonly tous?: boolean;
  /** Défaut : `'texte'`. */
  readonly capture?: ModeCapture;
}

/** Les nœuds d'une liaison, nommés — c'est ce nom que `peindre` réutilise. */
export type SpecNoeuds = Readonly<Record<string, SpecNoeud>>;

/** Les mêmes, résolus dans le document par le moteur. */
export type NoeudsResolus = Readonly<Record<string, Element | Element[] | null>>;

/**
 * UNE LIAISON — la forme générique que le moteur sait appliquer, restaurer et
 * marquer en chargement.
 *
 * `lire` et `peindre` sont des MÉTHODES (et pas des propriétés de type
 * fonction) : c'est ce qui permet à une liaison typée sur SA valeur d'entrer
 * dans un tableau hétérogène `Liaison<C>` sans `any` ni cast à l'usage.
 */
export interface Liaison<C, V = unknown> {
  /** Identifiant stable, lisible dans les tests et les gardes de couverture. */
  readonly cle: string;
  /** Le bloc à MASQUER quand `lire` rend `null`. */
  readonly enveloppe?: string;
  readonly noeuds: SpecNoeuds;
  /** `null` ⇒ cette taille ne sert pas ce champ : cacher, n'écrire RIEN. */
  lire(ctx: C): V | null;
  peindre(noeuds: NoeudsResolus, valeur: V): void;
}

/** Un nœud unique, quand il peut ne pas être un `HTMLElement` (l'arc SVG). */
export function unEl(noeuds: NoeudsResolus, nom: string): Element | null {
  const n = noeuds[nom];
  return n instanceof Element ? n : null;
}

/** Un nœud unique `HTMLElement` (le cas ordinaire : il porte `hidden`). */
export function unHtml(noeuds: NoeudsResolus, nom: string): HTMLElement | null {
  const n = noeuds[nom];
  return n instanceof HTMLElement ? n : null;
}

/** Tous les nœuds d'un sélecteur multiple (les douze cellules de mois…). */
export function desHtml(noeuds: NoeudsResolus, nom: string): HTMLElement[] {
  const n = noeuds[nom];
  if (!Array.isArray(n)) return [];
  return n.filter((e): e is HTMLElement => e instanceof HTMLElement);
}

// ── TABLE 1 — LES CHIFFRES DE TÊTE ──────────────────────────────────────────
//
// Sept lignes qui remplacent les appels câblés à `appliquerChampHero` et leurs
// quatorze recherches de constantes. Chaque ligne dit la même chose : « le nœud
// `valeur`, dans l'enveloppe `enveloppe`, RECOPIE le texte DÉJÀ RENDU par le
// sélecteur `carte` de la carte choisie ». Aucun calcul : le texte de la carte
// a été formaté au serveur par les mêmes fonctions que le héros, donc il est
// structurellement impossible qu'un chiffre de tête diffère d'un chiffre de
// carte (la parade au « 21 contre 22 »).

/** Ce que le bloc « Économie / an » a RÉELLEMENT rendu au chargement. */
export type HeroEcoKind = 'eco' | 'payback';

export interface LiaisonHero {
  readonly cle: string;
  /** Le nœud qui porte le texte. */
  readonly valeur: string;
  /** L'item/carte entier, masqué quand la carte ne sert pas ce champ. */
  readonly enveloppe: string;
  /** Le sélecteur à lire DANS la carte sélectionnée. */
  readonly carte: string;
  /**
   * Présent UNIQUEMENT sur les deux lignes du créneau « Économie / an » : ce
   * bloc a rendu au chargement SOIT une économie SOIT un payback
   * (`data-hero-eco-kind`, figé côté serveur), et seul le champ HOMONYME de la
   * carte peut s'y substituer. Mélanger les deux afficherait un payback sous
   * un libellé pensé pour une économie. Les deux lignes sont mutuellement
   * exclusives : `liaisonsHero()` n'en retient qu'une.
   */
  readonly siKind?: HeroEcoKind;
}

export const HERO: readonly LiaisonHero[] = [
  {
    cle: 'ttc',
    valeur: '[data-hero-ttc-value]',
    enveloppe: '[data-hero-ttc-card]',
    carte: '[data-taille-ttc-value]',
  },
  {
    cle: 'eco',
    valeur: '[data-hero-eco-value]',
    enveloppe: '[data-hero-eco-card]',
    carte: '[data-taille-eco-value]',
    siKind: 'eco',
  },
  {
    cle: 'eco_payback',
    valeur: '[data-hero-eco-value]',
    enveloppe: '[data-hero-eco-card]',
    carte: '[data-taille-payback-value]',
    siKind: 'payback',
  },
  {
    cle: 'kwc',
    valeur: '[data-hero-kwc-value]',
    enveloppe: '[data-hero-kwc-item]',
    carte: '[data-taille-kwc-value]',
  },
  {
    cle: 'panneaux',
    valeur: '[data-hero-panneaux-value]',
    enveloppe: '[data-hero-panneaux-item]',
    carte: '[data-taille-panneaux-value]',
  },
  {
    // Le bandeau « Production estimée / an » du chapitre production est un
    // nœud DISTINCT du héros : même donnée, deux endroits de page, donc deux
    // crochets propres — jamais un sélecteur partagé qui masquerait l'un en
    // croyant piloter l'autre.
    cle: 'production',
    valeur: '[data-hero-production-value]',
    enveloppe: '[data-hero-production-card]',
    carte: '[data-taille-production-value]',
  },
  {
    // « Économie estimée / an » lit le MÊME champ carte que le héros : ce
    // bandeau n'a jamais rendu de payback au chargement, donc aucun risque de
    // croisement eco/payback ici — pas de `siKind`.
    cle: 'eco_annuelle',
    valeur: '[data-hero-eco-annual-value]',
    enveloppe: '[data-hero-eco-annual-card]',
    carte: '[data-taille-eco-value]',
  },
];

/** Ce dont une liaison de tête a besoin : le texte déjà rendu par la carte. */
export interface ContexteHero {
  /** `null` = cette carte ne sert pas ce champ (discipline d'omission). */
  texteCarte(selecteur: string): string | null;
}

/**
 * Les liaisons de tête ACTIVES pour ce qui a réellement été rendu au
 * chargement : les deux lignes `siKind` s'excluent, donc six liaisons sortent
 * des sept déclarées, quelle que soit la valeur de `data-hero-eco-kind`.
 */
export function liaisonsHero(kind: HeroEcoKind): readonly Liaison<ContexteHero, string>[] {
  return HERO.filter((h) => h.siKind === undefined || h.siKind === kind).map((h) => ({
    cle: h.cle,
    enveloppe: h.enveloppe,
    noeuds: { valeur: { sel: h.valeur } },
    lire(ctx: ContexteHero): string | null {
      return ctx.texteCarte(h.carte);
    },
    peindre(noeuds: NoeudsResolus, texte: string): void {
      const el = unHtml(noeuds, 'valeur');
      if (el) el.textContent = texte;
    },
  }));
}

// ── TABLE 2 — LES CHAPITRES PROFONDS ────────────────────────────────────────
//
// Six chapitres, alimentés par le contrat `taille_detail.json` — pas par le
// texte des cartes : ce sont précisément les blocs qui, avant les OPTIONS
// CHARGEABLES, continuaient d'afficher les nombres du DEVIS OFFICIEL sous une
// carte qui n'est pas lui.

/**
 * Les douze mois + le total forment UN chapitre (une seule enveloppe, une
 * seule donnée servie). Le mode `echec` existe parce qu'un appel raté doit
 * laisser voir le message « Réessayer » PORTÉ PAR CETTE ENVELOPPE tout en
 * masquant les douze chiffres du devis officiel qui sont encore dedans.
 */
export type ValeurMensuelles =
  | { readonly mode: 'serie'; readonly valeurs: readonly number[]; readonly total: number }
  | { readonly mode: 'echec' };

/** Petit constructeur : il fixe `V` par ligne sans imposer `any` au tableau. */
function profond<V>(l: Liaison<TailleDetail | null, V>): Liaison<TailleDetail | null> {
  return l;
}

export const PROFONDS: readonly Liaison<TailleDetail | null>[] = [
  profond<ValeurMensuelles>({
    cle: 'economies_mensuelles',
    enveloppe: '[data-detail-eco-bloc]',
    noeuds: {
      mois: { sel: '[data-detail-eco-mois]', tous: true },
      moisAvec: { sel: '[data-detail-eco-mois-avec]', tous: true },
      total: { sel: '[data-detail-eco-total]' },
      totalAvec: { sel: '[data-detail-eco-total-avec-bloc]' },
    },
    lire(detail) {
      if (detail === null) return { mode: 'echec' };
      const m = detail.economiesMensuelles;
      if (!m) return null;
      return { mode: 'serie', valeurs: m.valeurs, total: m.total };
    },
    peindre(noeuds, valeur) {
      const mois = desHtml(noeuds, 'mois');
      const total = unHtml(noeuds, 'total');
      // La ligne « avec batterie » de chaque cellule et le total « avec » sont
      // des chiffres d'une AUTRE variante : un détail n'en porte qu'une.
      for (const el of desHtml(noeuds, 'moisAvec')) el.hidden = true;
      const totalAvec = unHtml(noeuds, 'totalAvec');
      if (totalAvec) totalAvec.hidden = true;
      if (valeur.mode === 'echec') {
        for (const el of mois) el.hidden = true;
        if (total) total.hidden = true;
        return;
      }
      mois.forEach((el, i) => {
        const montantDuMois = valeur.valeurs[i];
        // Une cellule sans montant SERVI est masquée, jamais remplie : une
        // grille plus longue que la série ne fabrique pas les mois manquants.
        if (montantDuMois === undefined) { el.hidden = true; return; }
        el.textContent = formatMAD(montantDuMois);
        el.hidden = false;
      });
      if (total) {
        total.textContent = formatMAD(valeur.total);
        total.hidden = false;
      }
    },
  }),

  profond<string>({
    // La banque de cette taille vit DANS `carte.batterie` (forme
    // `offres_tailles`). Son nœud EST sa propre enveloppe : sans banque
    // composée, il disparaît — et son texte n'est pas réécrit, conformément à
    // la règle « cacher, n'écrire rien » (le retour sur Recommandé remet de
    // toute façon l'original moissonné au chargement).
    cle: 'banque_batterie',
    enveloppe: '[data-detail-banque]',
    noeuds: { texte: { sel: '[data-detail-banque]' } },
    lire(detail) {
      const b = detail?.carte?.batterie ?? null;
      if (!b) return null;
      const morceaux: string[] = [];
      if (b.nbModules !== null && b.moduleKwh !== null) {
        morceaux.push(`${formatNumber(b.nbModules)} × ${formatNumber(b.moduleKwh, 1)} kWh`);
      }
      if (b.capaciteUtileKwh !== null) {
        morceaux.push(`${formatNumber(b.capaciteUtileKwh, 1)} kWh utiles`);
      }
      return morceaux.length ? `Batterie · ${morceaux.join(' · ')}` : null;
    },
    peindre(noeuds, texte) {
      const el = unHtml(noeuds, 'texte');
      if (el) el.textContent = texte;
    },
  }),

  profond<number>({
    // L'ANNEAU DE COUVERTURE. Le pourcentage est SERVI ; la seule arithmétique
    // est la longueur d'arc, définie UNE fois dans `lib/tailleDetail.ts` et
    // partagée avec le rendu serveur. Sans pourcentage servi, la carte entière
    // est masquée — jamais un anneau figé sous un nouveau chiffre.
    cle: 'couverture',
    enveloppe: '[data-hero-couverture-card]',
    noeuds: {
      arc: { sel: '[data-detail-couverture-arc]', capture: { attribut: 'stroke-dasharray' } },
      valeur: { sel: '[data-detail-couverture-value]' },
    },
    lire(detail) {
      return detail?.carte?.couverturePct ?? null;
    },
    peindre(noeuds, pct) {
      const arc = unEl(noeuds, 'arc');
      if (arc) {
        const rayon = Number(arc.getAttribute('data-detail-donut-r'));
        if (Number.isFinite(rayon) && rayon > 0) {
          arc.setAttribute('stroke-dasharray', dasharrayDonut(pct, rayon));
        }
      }
      const val = unHtml(noeuds, 'valeur');
      if (val) val.textContent = formatPercent(pct, 0);
    },
  }),

  profond<number>({
    cle: 'cumul_25_ans',
    enveloppe: '[data-detail-cumul-card]',
    noeuds: { valeur: { sel: '[data-detail-cumul-value]' } },
    lire(detail) {
      return detail?.carte?.economiesCumulees25AnsMad ?? null;
    },
    peindre(noeuds, cumul) {
      const el = unHtml(noeuds, 'valeur');
      if (el) el.textContent = formatMAD(cumul);
    },
  }),

  profond<string>({
    cle: 'payback',
    enveloppe: '[data-detail-payback-card]',
    noeuds: { valeur: { sel: '[data-detail-payback-value]' } },
    lire(detail) {
      // `formatPayback` rend `null` sur un payback absent, nul ou négatif :
      // c'est LUI la règle d'omission, pas une seconde condition ici.
      return formatPayback(detail?.carte?.paybackAnnees ?? null);
    },
    peindre(noeuds, texte) {
      const el = unHtml(noeuds, 'valeur');
      if (el) el.textContent = texte;
    },
  }),

  profond<readonly number[]>({
    // LE TABLEAU ANNÉE PAR ANNÉE — le chapitre OUBLIÉ à la première livraison
    // (commentaire « F2 (revue Fable 29/08/2026) » de la page) : le grand
    // chiffre du cumul changeait, et les 25 lignes en dessous continuaient
    // d'afficher la série du Recommandé. Il est ici parce qu'une TABLE
    // s'énumère : QJW10 refuse désormais toute clé du contrat qui ne serait ni
    // liée ni justifiée par écrit.
    cle: 'cumul_annuel',
    enveloppe: '[data-cumul-annuel]',
    noeuds: { corps: { sel: '[data-cumul-annuel] tbody', capture: 'html' } },
    lire(detail) {
      const serie = detail?.cashflow?.cumulative ?? null;
      return serie && serie.length > 0 ? serie : null;
    },
    peindre(noeuds, serie) {
      const corps = unHtml(noeuds, 'corps');
      if (!corps) return;
      const doc = corps.ownerDocument;
      const frag = doc.createDocumentFragment();
      serie.forEach((cumulAnnee, i) => {
        const tr = doc.createElement('tr');
        tr.className = 'border-t border-white/10';
        const tdAnnee = doc.createElement('td');
        tdAnnee.className = 'py-1.5 text-lune-soft';
        tdAnnee.setAttribute('dir', 'ltr');
        // AUCUN calcul : on NUMÉROTE les années comme le rendu serveur
        // (`i + 1`), on ne dérive aucun montant.
        tdAnnee.textContent = String(i + 1);
        const tdVal = doc.createElement('td');
        tdVal.className = `py-1.5 text-end fig ${cumulAnnee >= 0 ? 'text-brass-300' : 'text-lune-faint'}`;
        tdVal.setAttribute('dir', 'ltr');
        tdVal.textContent = formatMAD(cumulAnnee);
        tr.append(tdAnnee, tdVal);
        frag.append(tr);
      });
      corps.replaceChildren(frag);
    },
  }),
];
