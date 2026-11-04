/**
 * WAUD6 (D-WAUD-2=a, décision fondateur) — l'ORIGINE du visiteur (campagne
 * utm_* / fbclid / gclid, page d'arrivée, hôte du référent) est conservée 90
 * jours sur l'appareil, SANS clic « Accepter » : elle ne part qu'avec le lead
 * que le visiteur envoie volontairement (case « être recontacté » cochée).
 * Aucun script tiers n'est déclenché ici ; le consentement continue de régir
 * le pixel Meta/Google et le relais CAPI (adsConsent, QJW14).
 *
 * Capture first-touch : le premier enregistrement valide est gardé, SAUF s'il
 * ne portait aucune campagne et que l'arrivée courante en porte une (une
 * arrivée par annonce est plus informative qu'un accès organique).
 *
 * Le chemin d'arrivée n'a JAMAIS sa requête (pas d'e-mail ni de jeton dans
 * l'URL) ; le référent n'est que l'hôte, et seulement s'il est externe.
 */
export const CLE_ORIGINE = 'tq_origine';
export const DUREE_ORIGINE_MS = 90 * 24 * 60 * 60 * 1000;
export const CLES_CAMPAGNE = [
  'fbclid', 'gclid', 'gbraid', 'wbraid',
  'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
] as const;

export type Origine = Partial<Record<(typeof CLES_CAMPAGNE)[number] | 'landingPath' | 'referrerHost', string>>;

interface StockageMin {
  getItem(k: string): string | null;
  setItem(k: string, v: string): void;
}

export interface FenetreOrigine {
  location: { search: string; pathname: string; hostname: string };
  document: { referrer: string };
  localStorage: StockageMin;
  sessionStorage: StockageMin;
}

const HOTE_OK = /^[a-z0-9]([a-z0-9.-]{0,98}[a-z0-9])?$/;

/** Hôte du référent externe, ou '' (accès direct, même site, valeur douteuse). */
export function hoteReferent(referrer: string, hoteCourant: string): string {
  if (!referrer) return '';
  try {
    const h = new URL(referrer).hostname.toLowerCase();
    if (!HOTE_OK.test(h)) return '';
    const norm = (x: string) => x.replace(/^www\./, '');
    return norm(h) === norm((hoteCourant || '').toLowerCase()) ? '' : h;
  } catch {
    return '';
  }
}

function origineDepuisUrl(win: FenetreOrigine): Origine {
  const o: Origine = {};
  const p = new URLSearchParams(win.location.search);
  for (const k of CLES_CAMPAGNE) {
    const v = p.get(k);
    if (v) o[k] = v.slice(0, k === 'fbclid' ? 500 : k.endsWith('clid') || k.endsWith('braid') ? 255 : 300);
  }
  const chemin = win.location.pathname || '/';
  if (chemin.startsWith('/') && chemin.length <= 200) o.landingPath = chemin;
  const hote = hoteReferent(win.document.referrer, win.location.hostname);
  if (hote) o.referrerHost = hote;
  return o;
}

const aCampagne = (o: Origine) => CLES_CAMPAGNE.some((k) => !!o[k]);

function lireStocke(st: StockageMin, maintenant: number): Origine | null {
  try {
    const brut = st.getItem(CLE_ORIGINE);
    if (!brut) return null;
    const j = JSON.parse(brut) as { v?: Origine; t?: number };
    if (!j || typeof j.t !== 'number' || !j.v || typeof j.v !== 'object') return null;
    if (maintenant - j.t > DUREE_ORIGINE_MS || j.t > maintenant + 60_000) return null;
    return j.v;
  } catch {
    return null;
  }
}

/**
 * Capture l'origine de l'arrivée courante, la fusionne avec celle déjà gardée
 * (90 jours), l'enregistre, et la RECOPIE dans `sessionStorage` (`tq_<clé>`,
 * sans écraser) où le tunnel et les formulaires la lisent déjà. Tolère un
 * stockage indisponible (mode privé) : jamais d'exception.
 */
export function capturerOrigine(win: FenetreOrigine, maintenant: number = Date.now()): Origine {
  const courante = origineDepuisUrl(win);
  let retenue: Origine = courante;
  let t = maintenant;
  const ancienne = lireStocke(win.localStorage, maintenant);
  if (ancienne) {
    const garder = aCampagne(ancienne) || !aCampagne(courante);
    if (garder) {
      retenue = ancienne;
      try {
        t = (JSON.parse(win.localStorage.getItem(CLE_ORIGINE) || '{}') as { t?: number }).t ?? maintenant;
      } catch { /* garde t = maintenant */ }
    }
  }
  try {
    win.localStorage.setItem(CLE_ORIGINE, JSON.stringify({ v: retenue, t }));
  } catch { /* stockage indisponible : la copie de session suffit */ }
  for (const [k, v] of Object.entries(retenue)) {
    if (!v) continue;
    try {
      if (!win.sessionStorage.getItem('tq_' + k)) win.sessionStorage.setItem('tq_' + k, v);
    } catch { /* idem */ }
  }
  return retenue;
}
