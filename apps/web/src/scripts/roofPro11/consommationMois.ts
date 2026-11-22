/**
 * ACAL837 — la grille « Mes factures (1 à 12 mois) » du panneau « Affiner ma consommation ».
 *
 * Un mois par ligne, en kWh ou en MAD. 600 ms après la dernière frappe, l'atelier poste
 * `{source: 'factures', factures: {mois: [...]}}` à `consommation/proposer/` (ACAL836) et dessine
 * les 12 mois LUS dans `mois[]` de la réponse : les mois de facture pleins, les mois `estime` au
 * contour en pointillé, avec « estimé » sous la valeur. Un refus qui nomme `factures.mois[i].…`
 * s'affiche sous la ligne du mois envoyé en position i. Rien n'est calculé ici : les valeurs
 * affichées sont celles du serveur.
 */
import { esc } from './dom';
import type { CorpsPropositionConsommation } from './consumption';

export interface MoisPropose {
  mois: number;
  facture_mad: number | null;
  kwh: number;
  source: 'facture' | 'estime';
}

export const MOIS_COURTS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];
export const DELAI_FRAPPE_MS = 600;

export interface LigneSaisie {
  mois: number;
  valeur: string;
  unite: 'kwh' | 'mad';
}

/** Les mois renseignés, dans l'ordre des mois ; `null` quand aucun montant lisible n'est saisi. */
export function corpsDepuisLignes(lignes: readonly LigneSaisie[], classe: string): CorpsPropositionConsommation | null {
  const mois: Array<Record<string, number>> = [];
  for (const l of lignes) {
    const n = Number(l.valeur.trim().replace(',', '.'));
    if (l.valeur.trim() && Number.isFinite(n) && n > 0) mois.push({ mois: l.mois, [l.unite]: n });
  }
  if (!mois.length) return null;
  const enMad = mois.some((m) => 'mad' in m); // la classe ne sert qu'à convertir des MAD
  return { source: 'factures', factures: { mois, ...(enMad && classe ? { classe } : {}) } } as unknown as CorpsPropositionConsommation;
}

/** Les 12 barres lues dans `mois[]` : pleines (facture) ou en pointillé avec « estimé ». */
export function htmlBarres(mois: readonly MoisPropose[]): string {
  const max = Math.max(...mois.map((m) => m.kwh), 1);
  return mois.map((m) => `<div data-cons-mois-barre="${m.mois}" data-source="${m.source}" class="flex-1 text-center text-xs">
    <div style="height:${Math.round((m.kwh / max) * 64)}px;${m.source === 'estime' ? 'border:2px dashed currentColor;' : 'background:currentColor;'}"></div>
    <div>${esc(MOIS_COURTS[m.mois - 1] ?? String(m.mois))}</div><div>${Math.round(m.kwh)}</div>
    ${m.source === 'estime' ? '<div>estimé</div>' : '<div>facture</div>'}</div>`).join('');
}

export interface DepsGrille {
  lancer: (corps: CorpsPropositionConsommation) => void;
  classe: () => string;
  /** Reçoit chaque réponse (`mois[]`) ou refus (`champs`) du serveur. */
  ecouter: (f: (rep: { mois?: MoisPropose[] } | null, refus?: { champs?: Record<string, string> } | null) => void) => void;
}

export function monterGrilleFactures(hote: HTMLElement, deps: DepsGrille): void {
  const grille = document.createElement('details');
  grille.setAttribute('data-cons-mois-grille', '');
  grille.innerHTML = `<summary style="min-height:44px">Mes factures (1 à 12 mois)</summary>
    ${MOIS_COURTS.map((nom, i) => `<div data-cons-mois-ligne="${i + 1}" class="flex flex-wrap items-center gap-2 text-sm">
      <span style="min-width:4rem">${nom}</span>
      <input data-cons-mois-valeur inputmode="decimal" step="any" aria-label="Facture de ${nom}" style="min-height:44px">
      <select data-cons-mois-unite aria-label="Unité de ${nom}" style="min-height:44px"><option value="kwh">kWh</option><option value="mad">MAD</option></select>
      <p data-cons-mois-refus hidden role="alert" class="text-xs"></p></div>`).join('')}
    <div data-cons-mois-barres class="flex items-end gap-1"></div>`;
  hote.appendChild(grille);
  const lignes = (): LigneSaisie[] => Array.from(grille.querySelectorAll<HTMLElement>('[data-cons-mois-ligne]')).map((el) => ({
    mois: Number(el.getAttribute('data-cons-mois-ligne')),
    valeur: el.querySelector<HTMLInputElement>('[data-cons-mois-valeur]')?.value ?? '',
    unite: (el.querySelector<HTMLSelectElement>('[data-cons-mois-unite]')?.value === 'mad' ? 'mad' : 'kwh'),
  }));
  let envoyes: number[] = []; // les mois du dernier envoi, dans l'ordre : `factures.mois[i]` → envoyes[i]
  let minuterie: ReturnType<typeof setTimeout> | null = null;
  const envoyer = () => {
    minuterie = null;
    const corps = corpsDepuisLignes(lignes(), deps.classe());
    if (!corps) return;
    envoyes = (corps.factures as unknown as { mois: Array<{ mois: number }> }).mois.map((m) => m.mois);
    deps.lancer(corps);
  };
  grille.addEventListener('input', () => {
    if (minuterie != null) clearTimeout(minuterie);
    minuterie = setTimeout(envoyer, DELAI_FRAPPE_MS);
  });
  deps.ecouter((rep, refus) => {
    grille.querySelectorAll<HTMLElement>('[data-cons-mois-refus]').forEach((el) => { el.textContent = ''; el.hidden = true; });
    for (const [champ, motif] of Object.entries(refus?.champs ?? {})) {
      const rang = /^factures\.mois\[(\d+)\]/.exec(champ)?.[1];
      const ligne = rang === undefined ? null : grille.querySelector<HTMLElement>(`[data-cons-mois-ligne="${envoyes[Number(rang)]}"] [data-cons-mois-refus]`);
      if (ligne) { ligne.textContent = String(motif); ligne.hidden = false; }
    }
    const barres = grille.querySelector<HTMLElement>('[data-cons-mois-barres]');
    if (barres && rep?.mois?.length) barres.innerHTML = htmlBarres(rep.mois);
  });
}
