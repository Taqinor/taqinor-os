/**
 * T4-X9 (classe « un chiffre de la conception à côté d'une pose d'une autre taille ») — LE prédicat et LA phrase.
 *
 * La conception du lead est calculée par le moteur unique pour SA taille (`chiffrage.kwc`) ; au niveau de règles du jour
 * elle ignore les panneaux posés. Ses chiffres (production, économie, part de la consommation) ne se lisent donc qu'à côté
 * d'une pose de la MÊME taille. Ce module est le SEUL endroit qui compare les deux tailles : l'atelier (`affichageErp.ts`,
 * `optimizer.ts`, `zones.ts`) et les écrans de l'ERP (`@roofpro/tailleConception` : étape Résultats, vue client, bande de
 * l'étape Panneaux) l'appellent, aucun n'a sa copie de la comparaison.
 *
 * Aucun calcul : on choisit seulement quel chiffre servi se montre, ou aucun.
 */
import { fmtKwc } from './dom';

/** Écart d'ÉGALITÉ de deux puissances (kWc) : l'arrondi d'affichage à deux décimales, pas un seuil métier. */
const ECART_KWC = 0.005;

const nombre = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

/** Les deux tailles sont connues et égales (au centième de kWc) : un chiffre de la conception se lit à côté de la pose. */
export function memeTaille(kwcConception: unknown, kwcPose: unknown): boolean {
  return nombre(kwcConception) && nombre(kwcPose) && Math.abs(kwcConception - kwcPose) < ECART_KWC;
}

/** Les deux tailles sont connues et DIFFÉRENTES : la phrase remplace les chiffres de la conception. */
export function tailleDifferente(kwcConception: unknown, kwcPose: unknown): boolean {
  return nombre(kwcConception) && nombre(kwcPose) && !memeTaille(kwcConception, kwcPose);
}

/** « 4,40 kWc » : une puissance, deux décimales, virgule française (le formateur unique de l'atelier). */
export const texteKwc = (kwc: number): string => `${fmtKwc(kwc)} kWc`;

/** T4-X9-007 — pose (ou retire) la phrase en TEXTE COURANT, une fois, juste après `apres` (le bloc des cartes qu'elle
 *  explique) : un `<p id>` créé à la demande, taille normale ; texte vide ⇒ le paragraphe est retiré. */
export function peindrePhraseTailles(apres: Element | null | undefined, id: string, texte: string): void {
  if (typeof document === 'undefined') return;
  let el = document.getElementById(id);
  if (!texte) return void el?.remove();
  if (!apres) return;
  if (!el) {
    el = document.createElement('p');
    el.id = id;
    el.className = 'mt-3 text-sm text-foreground';
    el.setAttribute('data-phrase-tailles', '');
  }
  if (el.previousElementSibling !== apres) apres.insertAdjacentElement('afterend', el);
  el.textContent = texte;
}

/** La phrase, en texte courant : « <grandeur> calculée(s) pour la conception du lead : 4,40 kWc — votre pose en compte
 *  5,68 kWc. » La grandeur est nommée par l'appelant (« Production », « Production et économie »…). */
export function phraseTailles(grandeur: string, kwcConception: number, kwcPose: number, pluriel = false): string {
  return `${grandeur} ${pluriel ? 'calculées' : 'calculée'} pour la conception du lead : ${texteKwc(kwcConception)} — `
    + `votre pose en compte ${texteKwc(kwcPose)}.`;
}
