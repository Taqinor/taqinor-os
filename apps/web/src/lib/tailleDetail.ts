/**
 * OPTIONS CHARGEABLES (ordre fondateur, 29/08/2026) — « i want the 3 options
 * to be LOADABLE in the webpage if client clicks on one of them ».
 *
 * CE QUE CE MODULE EST. Le lecteur — au sens strict — du contrat
 * `apps/ventes/contract_samples/taille_detail.json` : il VALIDE et NOMME ce
 * que le backend a déjà calculé pour UNE taille (`eco` | `max`) dans UNE
 * variante, et il porte les quelques DÉCISIONS de la page (quelle taille est
 * chargeable, quelle clé de cache, quelle URL). Rien d'autre.
 *
 * CE QU'IL N'EST PAS. Il ne calcule AUCUN chiffre d'installation : pas une
 * somme, pas une moyenne, pas un pourcentage, pas un payback. Un nombre qui
 * s'affiche vient du serveur ou n'existe pas (règle fondateur « zéro chiffre
 * inventé »). La seule arithmétique de ce fichier est une LONGUEUR D'ARC de
 * dessin (:func:`arcDonut`), et elle y vit précisément pour n'exister qu'UNE
 * fois — voir sa propre note.
 *
 * POURQUOI UN MODULE PLUTÔT QUE DU CODE DANS L'ÎLOT. L'îlot `<script>` de la
 * page n'est testable que par assertions de chaîne sur la source `.astro`
 * (idiome de la maison). Tout ce qui MÉRITE un vrai test unitaire — la
 * validation du payload, l'omission champ par champ, la clé de cache, le
 * refus de `recommande` — vit donc ici, où vitest peut l'exécuter pour de
 * vrai ; l'îlot ne garde que le câblage DOM.
 */

/** Les SEULES tailles qui se CHARGENT. `recommande` n'en est pas une. */
export const TAILLES_CHARGEABLES = ['eco', 'max'] as const;
export type TailleChargeable = (typeof TAILLES_CHARGEABLES)[number];

export type VarianteDetail = 'sans' | 'avec';

/**
 * `recommande` EST le devis : la page le RESTAURE depuis les textes originaux
 * mis en cache au chargement, elle ne le recharge jamais. Lui faire suivre le
 * chemin réseau aurait recréé le risque « 21 contre 22 » — deux origines pour
 * un même chiffre, deux arrondis, deux vérités.
 */
export function estChargeable(cle: string | null | undefined): cle is TailleChargeable {
  return TAILLES_CHARGEABLES.includes(cle as TailleChargeable);
}

/** La clé de cache navigateur d'un détail : une entrée par taille ET variante. */
export function cleCacheDetail(cle: string, variante: string): string {
  return `${cle}:${variante}`;
}

/** URL du proxy SAME-ORIGIN (le navigateur n'appelle jamais le backend). */
export function detailProxyUrl(token: string, cle: string, variante: string): string {
  const p = new URLSearchParams({ token, cle, variante });
  return `/api/proposition-taille?${p.toString()}`;
}

/**
 * URL backend du détail (contrat `taille_detail.json`), endpoint PUBLIC monté
 * sous `public/` — même convention que `engagementEndpoint`. Utilisée
 * SEULEMENT côté serveur, par le proxy `pages/api/proposition-taille.ts`.
 */
export function tailleDetailEndpoint(
  apiBase: string, token: string, cle: string, variante: string,
): string {
  const base = (apiBase || 'https://api.taqinor.ma').replace(/\/+$/, '');
  const q = new URLSearchParams({ variante });
  return `${base}/api/django/public/proposal/${encodeURIComponent(token)}`
    + `/taille/${encodeURIComponent(cle)}/?${q.toString()}`;
}

/**
 * LA LONGUEUR D'ARC DE L'ANNEAU DE COUVERTURE — UNE SEULE DÉFINITION.
 *
 * C'est du DESSIN (une longueur, en unités du `viewBox`), pas un recalcul du
 * pourcentage servi : le pourcentage arrive du serveur et n'est jamais
 * retouché. Cette fonction existe pour que le rendu SERVEUR de l'anneau et sa
 * mise à jour quand le client charge une autre taille partagent le MÊME
 * calcul — la page en avait une expression en ligne, et une seconde copie
 * dans l'îlot aurait été exactement le genre de divergence que cette page
 * paie cher. Elle est ici, importée des deux côtés.
 */
export function arcDonut(pct: number | null | undefined, rayon: number): { dash: number; circ: number } {
  const circ = 2 * Math.PI * rayon;
  const valeur = typeof pct === 'number' && Number.isFinite(pct) ? pct : 0;
  const borne = Math.max(0, Math.min(100, valeur));
  return { dash: (circ * borne) / 100, circ };
}

/** `stroke-dasharray` prêt à poser, avec les mêmes deux décimales que le SSR. */
export function dasharrayDonut(pct: number | null | undefined, rayon: number): string {
  const { dash, circ } = arcDonut(pct, rayon);
  return `${dash.toFixed(2)} ${(circ - dash).toFixed(2)}`;
}

// ── LECTURE DU CONTRAT ──────────────────────────────────────────────────────

function nombre(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

function objet(v: unknown): Record<string, unknown> | null {
  return v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : null;
}

export interface DetailBatterie {
  nbModules: number | null;
  moduleKwh: number | null;
  capaciteUtileKwh: number | null;
  /** `false` UNIQUEMENT quand le moteur l'affirme — absent ⇒ `null`. */
  remplissageOk: boolean | null;
}

export interface DetailCarte {
  nbPanneaux: number | null;
  puissanceKwc: number | null;
  prixTtc: number | null;
  economieAnnuelleMad: number | null;
  paybackAnnees: number | null;
  couverturePct: number | null;
  tauxAutoconsommationPct: number | null;
  productionAnnuelleKwh: number | null;
  economiesCumulees25AnsMad: number | null;
  batterie: DetailBatterie | null;
}

export interface DetailEconomiesMensuelles {
  /** DOUZE valeurs MAD, janvier → décembre. Jamais onze, jamais treize. */
  valeurs: number[];
  total: number;
  devise: string;
}

export interface DetailCashflow {
  cumulative: number[];
  horizonAnnees: number | null;
  escaladeTarifairePct: number | null;
}

export interface TailleDetail {
  cle: string;
  titre: string | null;
  variante: VarianteDetail;
  estLeDevis: boolean;
  carte: DetailCarte | null;
  economiesMensuelles: DetailEconomiesMensuelles | null;
  cashflow: DetailCashflow | null;
}

function lireBatterie(brut: unknown): DetailBatterie | null {
  const b = objet(brut);
  if (!b) return null;
  return {
    nbModules: nombre(b.nb_modules),
    moduleKwh: nombre(b.module_kwh),
    capaciteUtileKwh: nombre(b.capacite_utile_kwh),
    remplissageOk: typeof b.remplissage_ok === 'boolean' ? b.remplissage_ok : null,
  };
}

function lireCarte(brut: unknown): DetailCarte | null {
  const c = objet(brut);
  if (!c) return null;
  return {
    nbPanneaux: nombre(c.nb_panneaux),
    puissanceKwc: nombre(c.puissance_kwc),
    prixTtc: nombre(c.prix_ttc),
    economieAnnuelleMad: nombre(c.economie_annuelle_mad),
    paybackAnnees: nombre(c.payback_annees),
    couverturePct: nombre(c.couverture_pct),
    tauxAutoconsommationPct: nombre(c.taux_autoconsommation_pct),
    productionAnnuelleKwh: nombre(c.production_annuelle_kwh),
    economiesCumulees25AnsMad: nombre(c.economies_cumulees_25_ans_mad),
    batterie: lireBatterie(c.batterie),
  };
}

/**
 * DOUZE OU RIEN. Le backend applique déjà la règle « année complète ou rien »
 * du moteur ; la page la RÉ-APPLIQUE parce qu'une série de onze mois se
 * lirait comme une année en dessous de la vérité. `total` est SERVI (jamais
 * resommé ici — ce serait le treizième chiffre, celui qui diverge).
 */
function lireMensuelles(brut: unknown): DetailEconomiesMensuelles | null {
  const m = objet(brut);
  if (!m) return null;
  const valeurs = m.valeurs;
  if (!Array.isArray(valeurs) || valeurs.length !== 12) return null;
  const propres: number[] = [];
  for (const v of valeurs) {
    const n = nombre(v);
    if (n === null) return null;
    propres.push(n);
  }
  const total = nombre(m.total);
  if (total === null) return null;
  return {
    valeurs: propres,
    total,
    devise: typeof m.devise === 'string' && m.devise ? m.devise : 'MAD',
  };
}

function lireCashflow(brut: unknown): DetailCashflow | null {
  const c = objet(brut);
  if (!c) return null;
  const serie = c.cumulative;
  if (!Array.isArray(serie) || serie.length === 0) return null;
  const propres: number[] = [];
  for (const v of serie) {
    const n = nombre(v);
    if (n === null) return null;
    propres.push(n);
  }
  return {
    cumulative: propres,
    horizonAnnees: nombre(c.horizon_annees),
    escaladeTarifairePct: nombre(c.escalade_tarifaire_pct),
  };
}

/**
 * Lit le payload du détail, ou `null` si ce n'en est pas un.
 *
 * L'OMISSION EST HÉRITÉE, JAMAIS COMBLÉE : un bloc absent côté serveur reste
 * `null` ici, et la page masque la section correspondante au lieu de laisser
 * voir le chiffre du DEVIS OFFICIEL sous une carte qui n'est pas lui — un
 * nombre réel attribué à la mauvaise offre est un mensonge de plus, pas de
 * moins.
 */
export function tailleDetail(payload: unknown): TailleDetail | null {
  const p = objet(payload);
  if (!p) return null;
  const cle = typeof p.cle === 'string' ? p.cle : '';
  if (!estChargeable(cle)) return null;
  const variante = p.variante === 'avec' ? 'avec' : p.variante === 'sans' ? 'sans' : null;
  if (variante === null) return null;
  return {
    cle,
    titre: typeof p.titre === 'string' && p.titre ? p.titre : null,
    variante,
    estLeDevis: p.est_le_devis === true,
    carte: lireCarte(p.carte),
    economiesMensuelles: lireMensuelles(p.economies_mensuelles),
    cashflow: lireCashflow(p.cashflow),
  };
}
