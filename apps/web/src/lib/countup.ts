/**
 * Logique pure du count-up de la page d'accueil — extraite de V2Enhance.astro
 * pour être testable unitairement (aucun accès au DOM ici).
 *
 * Règle de sûreté (W60) : une valeur « composée » (plage ou plusieurs nombres,
 * ex. « 60–90 % », « 3–7 ans », « 3 à 5 kWc », « 50 000 MAD – 115 000 MAD »)
 * ne doit JAMAIS être animée chiffre par chiffre — les deux bornes rouleraient
 * indépendamment et produiraient une image intermédiaire absurde (« 37–58 % »).
 * Pour ces valeurs, on n'anime pas le nombre : on révèle la valeur finale.
 * Une valeur simple (un seul nombre, unité optionnelle : « 25 ans », « 0 MAD »,
 * « 21 406 kWh/an ») garde le roulement 0 → valeur.
 *
 * Le formatage français (virgule décimale, espace milliers) est identique à
 * celui du site.
 *
 * W220 — anti-CLS : les éléments count-up portent `font-variant-numeric:
 * tabular-nums` (via v2.css) pour que chaque chiffre occupe une largeur
 * de colonne constante. En JS, `reserveWidth` capture la largeur de la valeur
 * finale AVANT l'animation et la verrouille comme `min-width` pour que l'élément
 * ne rétrécisse jamais pendant le roulement 0 → final.
 */

// Espaces admis DANS un nombre : normal (0x20), insécable (0xA0), fine (0x202F).
// Construit via fromCharCode pour garder la source en ASCII pur.
const SP = ' ' + String.fromCharCode(0xa0, 0x202f);
// Le jeton se termine TOUJOURS sur un chiffre : `\d(?:[\d<SP>]*\d)?` ne capture
// jamais l'espace qui sépare le nombre de son unité (« 21 406 kWh/an » → jeton
// « 21 406 », pas « 21 406 »), sinon l'image intermédiaire perdrait l'espace
// avant l'unité (« 10 703kWh/an »).
const NUM_RE = new RegExp('\\d(?:[\\d' + SP + ']*\\d)?(?:,\\d+)?', 'g');
const GROUP_RE = new RegExp('\\d[' + SP + ']\\d');
const SP_RE = new RegExp('[' + SP + ']', 'g');

export interface NumToken {
  /** Sous-chaîne brute telle qu'écrite (avec ses espaces de groupe). */
  raw: string;
  /** Index de début dans la chaîne d'origine. */
  idx: number;
  /** Nombre de décimales à conserver. */
  decimals: number;
  /** Le nombre utilise-t-il un séparateur de milliers ? */
  group: boolean;
  /** Valeur numérique finale. */
  val: number;
}

/** Formatage français : virgule décimale, espace milliers (comme le site). */
export function frFormat(value: number, decimals: number, group: boolean): string {
  let s = value.toFixed(decimals).replace('.', ',');
  if (group) {
    const [intPart, dec] = s.split(',');
    s = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ' ') + (dec ? ',' + dec : '');
  }
  return s;
}

/** Extrait tous les jetons numériques d'un texte, dans l'ordre. */
export function parseTokens(text: string): NumToken[] {
  return [...text.matchAll(NUM_RE)].map((m) => {
    const raw = m[0];
    const decimals = (raw.split(',')[1] || '').length;
    const group = GROUP_RE.test(raw);
    const val = parseFloat(raw.replace(SP_RE, '').replace(',', '.'));
    return { raw, idx: m.index ?? 0, decimals, group, val };
  });
}

/**
 * Une valeur est « composée » si elle contient plus d'un jeton numérique, OU un
 * séparateur de plage entre deux nombres : tiret demi-cadratin « – », tiret « - »,
 * ou le mot « à ». Une valeur composée ne doit pas être roulée chiffre par chiffre.
 */
export function isCompound(text: string): boolean {
  const tokens = parseTokens(text);
  if (tokens.length > 1) return true;
  // Un seul jeton mais un séparateur de plage explicite reste possible
  // (par sécurité — un seul nombre + « à »/« – » signale une plage rédigée).
  if (/\d\s*(?:[–-]|à)\s*\d/.test(text)) return true;
  return false;
}

/**
 * Faut-il animer cette valeur chiffre par chiffre ? Vrai uniquement pour une
 * valeur simple (exactement un nombre). Faux pour toute valeur composée/plage —
 * celles-ci sont révélées telles quelles (aucune image intermédiaire absurde).
 */
export function shouldDigitRoll(text: string): boolean {
  return parseTokens(text).length === 1 && !isCompound(text);
}

/**
 * W220 — Réserve la largeur d'un élément count-up AVANT l'animation pour
 * éviter tout micro-CLS pendant le roulement 0 → valeur finale.
 *
 * L'élément affiche déjà sa valeur finale dans le DOM (rendu serveur) ;
 * on mesure la largeur rendue, puis on la verrouille comme `min-width`.
 * Cela garantit que l'élément ne peut jamais rétrécir pendant l'animation
 * (quand le texte passe par des valeurs intermédiaires plus courtes, ex.
 * « 0 kWh/an » au lieu de « 21 406 kWh/an »).
 *
 * Note : ne modifie que `min-width` (jamais `width`) pour ne pas bloquer
 * le redimensionnement responsive. Sans DOM (SSR/tests unitaires), no-op.
 */
export function reserveWidth(el: HTMLElement): void {
  // La valeur finale est dans le texte courant — on mesure avant toute mutation.
  const rect = el.getBoundingClientRect();
  if (rect.width > 0) {
    el.style.minWidth = rect.width + 'px';
  }
}

/**
 * Rend l'image du count-up à la progression `progress` (0 → 1), pour une valeur
 * simple : seul le nombre est interpolé, tout le reste de la chaîne (unité,
 * ponctuation) est préservé tel quel. À `progress` = 1 la chaîne reproduit
 * EXACTEMENT le texte final.
 *
 * Pour une valeur composée (`shouldDigitRoll` faux), on ne roule rien : la
 * fonction renvoie le texte final à n'importe quelle progression — il n'existe
 * donc aucune image intermédiaire malformée.
 */
export function formatFrame(text: string, progress: number): string {
  const p = Math.max(0, Math.min(1, progress));
  if (!shouldDigitRoll(text)) return text;
  if (p >= 1) return text; // valeur finale exacte, octet pour octet
  const tokens = parseTokens(text);
  let out = '';
  let last = 0;
  for (const tk of tokens) {
    out += text.slice(last, tk.idx);
    out += frFormat(tk.val * p, tk.decimals, tk.group);
    last = tk.idx + tk.raw.length;
  }
  out += text.slice(last);
  return out;
}

/**
 * W361 — Progression scrub d'un count-up piloté par le défilement (au lieu
 * d'un fire-once déclenché par IntersectionObserver). Pure fonction : prend
 * la position d'un élément dans la fenêtre d'affichage et renvoie une
 * progression easée 0 → 1, exactement comme la course `animation-range`
 * posée en CSS pour `.v2-rise` (entry 0% → cover 35%) afin que le nombre et
 * son fondu terminent leur course ensemble.
 *
 * `elTop`/`elBottom` : rectangle de l'élément en coordonnées viewport
 * (`getBoundingClientRect`). `viewportHeight` : hauteur de la fenêtre.
 * L'entrée commence quand le haut de l'élément atteint le bas de la vue,
 * et se termine à 35 % de la hauteur de la vue parcourue par l'élément —
 * même fenêtre que `animation-range: entry 0% cover 35%` en CSS pour que
 * les deux mécanismes (transform/opacity en CSS natif, texte en JS) restent
 * visuellement synchrones.
 */
export function scrubProgress(elTop: number, viewportHeight: number): number {
  if (viewportHeight <= 0) return 1;
  const start = viewportHeight; // le haut de l'élément touche le bas de la vue
  const end = viewportHeight * 0.65; // course de 35% de la hauteur de vue
  if (elTop >= start) return 0;
  if (elTop <= end) return 1;
  const raw = (start - elTop) / (start - end);
  const p = Math.max(0, Math.min(1, raw));
  return 1 - Math.pow(1 - p, 3); // easeOutCubic, identique aux autres count-ups
}
