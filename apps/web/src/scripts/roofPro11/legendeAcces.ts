// ACAL441 — légende graphique de la carte d'accès solaire : trois repères (0, 0,5, 1) dont les
// couleurs sont LUES de `solarAccessColorRGB` (jamais recopiées). Les extrémités 0 % / 100 % sont
// les bornes du domaine de la fonction, pas des mesures.
import { couleurAccesActive, solarAccessColorRGB } from '../../lib/shadingEngine';
import { esc } from './dom';

/** ACAL1821 — la palette ACTIVE est-elle celle du site (rouge → vert, `solarAccessColorRGB`) ? Lu des couleurs. */
function paletteDuSite(): boolean {
  return [0, 0.5, 1].every((a) => JSON.stringify(couleurAccesActive(a)) === JSON.stringify(solarAccessColorRGB(a)));
}

/** ACAL1821 — ce que la note dit des couleurs : sur la palette du site, ses deux couleurs (texte inchangé) ; sur une
 *  autre palette (atelier : bleu nuit → or), aucun nom de couleur — la légende ci-dessous les montre. */
export function phraseCouleursAcces(periode: string): string {
  return paletteDuSite()
    ? `vert = plein soleil ${periode}, rouge = souvent à l’ombre`
    : `teinte de chaque panneau selon la légende ci-dessous, de l’ombre (0 %) au plein soleil (100 %) ${periode}`;
}

function css(a: number): string {
  const c = couleurAccesActive(a); // palette active (site : solarAccessColorRGB, inchangée)
  return `rgb(${Math.round(c.r * 255)},${Math.round(c.g * 255)},${Math.round(c.b * 255)})`;
}

/** HTML de la barre de légende ; `periode` = libellé de la période évaluée. */
export function htmlLegendeAcces(periode: string): string {
  const [c0, c1, c2] = [css(0), css(0.5), css(1)];
  return (
    `<div style="height:8px;border-radius:4px;background:linear-gradient(to right,${c0},${c1},${c2})"></div>` +
    '<div style="display:flex;justify-content:space-between">' +
    '<span>à l’ombre (0 %)</span><span>plein soleil (100 %)</span></div>' +
    `<div>Période évaluée : ${esc(periode)}</div>`
  );
}

/** Pose (ou retire, `periode` null) la légende juste sous la note ; sans note, rien n'est créé. */
export function poserLegendeAcces(noteEl: HTMLElement | null, periode: string | null): void {
  const parent = noteEl?.parentElement;
  if (!noteEl || !parent) return;
  let el = parent.querySelector('#rp9-heatmap-legend');
  if (periode == null) {
    el?.remove();
    return;
  }
  if (!el) {
    el = document.createElement('div');
    el.id = 'rp9-heatmap-legend';
    el.className = 'text-xs text-lune-faint';
    // ACAL1821 — dans une rangée flex (atelier ERP), la légende prenait la largeur de son texte : les deux bornes se
    // collaient (« à l'ombre (0 %)plein soleil (100 %) »). Pleine largeur : elles sont aux deux bouts de la barre.
    (el as HTMLElement).style.width = '100%';
    (el as HTMLElement).style.flexBasis = '100%';
    noteEl.after(el);
  }
  el.innerHTML = htmlLegendeAcces(periode);
}
