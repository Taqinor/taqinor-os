/**
 * ACAL420 — L'ATELIER VIERGE DIT LE PROCHAIN GESTE SUR LA CARTE ELLE-MÊME.
 *
 * Avant tout tracé, l'atelier ne parlait que par la ligne de statut placée SOUS la carte. Une carte
 * d'aide flottante (même patron que `#rp9-marquee`) dit « 1 · Localisez le toit… » puis « 2 · Un
 * clic par coin… » et disparaît contour fermé (le statut prend le relais). Elle ne bloque aucun
 * clic (`pointer-events: none`) et reste `aria-hidden` : le statut `aria-live` est le canal des
 * lecteurs d'écran.
 */
import { optionsGestesCarte } from './gestesCarte';

export const ETAPE_LOCALISER = '1 · Localisez le toit : tapez l’adresse, puis cliquez le premier coin';
export const ETAPE_COINS = '2 · Un clic par coin, double-clic pour fermer le contour';
/** ACAL1808 — mêmes étapes au doigt : aucun mot de souris sur un écran tactile. */
export const ETAPE_LOCALISER_TACTILE = '1 · Localisez le toit : tapez l’adresse, puis touchez le premier coin';
export const ETAPE_COINS_TACTILE = '2 · Touchez la carte pour poser chaque coin, puis « Terminer le tracé »';

/** Le pointeur est un doigt : la détection est celle des gestes de la carte (1 définition). */
export function pointeurTactile(fenetre: { matchMedia?: (requete: string) => { matches: boolean } } | undefined): boolean {
  return Boolean(fenetre && optionsGestesCarte(fenetre).cooperativeGestures);
}

/** Le texte de la carte pour l'état du tracé, ou null quand elle doit disparaître. */
export function texteEtatVide(sommets: number, ferme: boolean, tactile = false): string | null {
  if (ferme) return null;
  if (tactile) return sommets === 0 ? ETAPE_LOCALISER_TACTILE : ETAPE_COINS_TACTILE;
  return sommets === 0 ? ETAPE_LOCALISER : ETAPE_COINS;
}

export function creerEtatVide(conteneur: HTMLElement | null): { maj: (sommets: number, ferme: boolean) => void } {
  let el: HTMLElement | null = null;
  const maj = (sommets: number, ferme: boolean) => {
    const t = texteEtatVide(sommets, ferme, pointeurTactile(typeof window === 'undefined' ? undefined : window));
    if (!el && (t === null || !conteneur || typeof document === 'undefined')) return;
    if (!el) {
      el = document.createElement('div');
      el.id = 'rp9-etat-vide';
      el.setAttribute('aria-hidden', 'true');
      el.style.cssText = 'position:absolute;left:50%;top:12px;transform:translateX(-50%);z-index:6;pointer-events:none;'
        + 'padding:8px 14px;border-radius:8px;background:rgba(7,11,29,0.82);color:#f4efe3;font-size:14px;text-align:center;max-width:90%';
      conteneur!.appendChild(el);
    }
    el.hidden = t === null;
    el.textContent = t ?? '';
  };
  return { maj };
}
