/**
 * ACAL837 — la grille « Mes factures (1 à 12 mois) » du panneau « Affiner ma consommation ».
 *
 * Un mois par ligne, en kWh ou en MAD. 600 ms après la dernière frappe, l'atelier poste
 * `{source: 'factures', factures: {mois: [...]}}` à `consommation/proposer/` (ACAL836) et dessine
 * les 12 mois LUS dans `mois[]` de la réponse : les mois de facture pleins, les mois `estime` au
 * contour en pointillé, avec « estimé » sous la valeur. Un refus qui nomme `factures.mois[i].…`
 * s'affiche sous la ligne du mois envoyé en position i. Rien n'est calculé ici : les valeurs
 * affichées sont celles du serveur.
 *
 * ACAL840 — sous la grille, « Lire une photo de facture » : montré SEULEMENT quand le serveur dit la
 * lecture disponible. Chaque ligne lue `{mois: null, kWh}` se propose à confirmer : le mois se choisit
 * (la lecture n'en rend jamais), le kWh se corrige, « Garder » remplit le mois de la grille.
 */
import { esc } from './dom';
import type { CorpsPropositionConsommation } from './consumption';
import type { Ctx } from './context';

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

/** ACAL1610 — une facture mensuelle du document (`consumption.factures_mois`, contrat ACAL1601). */
export interface FactureMois { mois: number; valeur: number; unite: 'kwh' | 'mad' }

/** Les factures à écrire au document, tirées des lignes par `corpsDepuisLignes` (une seule lecture). */
function facturesDepuisLignes(lignes: readonly LigneSaisie[]): FactureMois[] {
  const corps = corpsDepuisLignes(lignes, '') as unknown as { factures: { mois: Array<Record<string, number>> } } | null;
  return (corps?.factures.mois ?? []).map(({ mois, ...m }) => ('mad' in m
    ? { mois, valeur: m.mad, unite: 'mad' } : { mois, valeur: m.kwh, unite: 'kwh' }));
}

/** Les factures RELUES d'un bloc `consumption` ; une entrée hors contrat (mois 13, valeur ≤ 0…) est ignorée. */
export function releireFacturesMois(consumption: unknown): FactureMois[] {
  const brutes = (consumption as { factures_mois?: unknown } | null | undefined)?.factures_mois;
  return (Array.isArray(brutes) ? brutes : []).filter((f): f is FactureMois => Boolean(f) && Number.isInteger(f.mois)
    && f.mois >= 1 && f.mois <= 12 && typeof f.valeur === 'number' && f.valeur > 0 && (f.unite === 'kwh' || f.unite === 'mad'))
    .map((f) => ({ mois: f.mois, valeur: f.valeur, unite: f.unite }));
}

type CtxFactures = Pick<Ctx, 'documentRelu'> & { consFacturesMois?: FactureMois[] };
type LiaisonFactures = { lire: () => FactureMois[]; ecrire: (liste: FactureMois[]) => void };

/** Celles de l'écran (`consFacturesMois`) si l'utilisateur y a touché, sinon celles relues ; `null` = rien. */
export function facturesAEcrire(ctx: CtxFactures): FactureMois[] | null {
  const liste = Array.isArray(ctx.consFacturesMois) ? ctx.consFacturesMois : releireFacturesMois(ctx.documentRelu?.consumption);
  return liste.length ? liste : null;
}

/** La liaison grille ↔ document que l'atelier passe à `monterGrilleFactures`. */
export const liaisonFactures = (ctx: CtxFactures): LiaisonFactures => ({
  lire: () => facturesAEcrire(ctx) ?? [], ecrire: (liste) => { ctx.consFacturesMois = liste; } });

/** Les 12 barres lues dans `mois[]` : pleines (facture) ou en pointillé avec « estimé ». */
export function htmlBarres(mois: readonly MoisPropose[]): string {
  const max = Math.max(...mois.map((m) => m.kwh), 1);
  return mois.map((m) => `<div data-cons-mois-barre="${m.mois}" data-source="${m.source}" class="text-center" style="flex-grow:1;flex-shrink:1;flex-basis:0;min-width:0;overflow-wrap:anywhere;font-size:0.625rem;line-height:1.2">
    <div style="height:${Math.round((m.kwh / max) * 64)}px;${m.source === 'estime' ? 'border:2px dashed currentColor;' : 'background:currentColor;'}"></div>
    <div>${esc(MOIS_COURTS[m.mois - 1] ?? String(m.mois))}</div><div>${Math.round(m.kwh)}</div>
    ${m.source === 'estime' ? '<div>estimé</div>' : '<div>facture</div>'}</div>`).join('');
}

/** ACAL840 — la lecture d'une photo (contrat `calepinage_consommation_photo_facture.json`). */
export interface LectureFacture { disponible: boolean; motif: string | null; lignes: Array<{ mois: number | null; kwh: number }> }
export interface OptionLireFacture {
  disponible: () => Promise<{ disponible: boolean; motif?: string | null }>;
  lire: (fichier: File) => Promise<LectureFacture>;
}

export const MOTIF_LECTURE_VIDE = 'La photo n’a pas pu être lue : saisissez les mois à la main';

function el<K extends keyof HTMLElementTagNameMap>(tag: K, attrs: Record<string, string> = {}, texte = ''): HTMLElementTagNameMap[K] {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (texte) n.textContent = texte;
  return n;
}

/** Une ligne lue à confirmer : mois à choisir (obligatoire), kWh modifiable, « Garder » / « Ignorer ». */
function ligneLue(l: { kwh: number }, garder: (mois: number, kwh: number) => void): HTMLElement {
  const ligne = el('div', { 'data-cons-photo-ligne': '', class: 'flex flex-wrap items-center gap-2 text-sm' });
  const choix = el('select', { 'data-cons-photo-mois': '', 'aria-label': 'Mois de cette facture', style: 'min-height:44px' });
  choix.appendChild(el('option', { value: '' }, 'Choisir le mois'));
  MOIS_COURTS.forEach((nom, i) => choix.appendChild(el('option', { value: String(i + 1) }, nom)));
  const kwh = el('input', { 'data-cons-photo-kwh': '', inputmode: 'decimal', step: 'any', 'aria-label': 'kWh lus', value: String(l.kwh), style: 'min-height:44px' });
  const oui = el('button', { type: 'button', 'data-cons-photo-garder': '', style: 'min-height:44px' }, 'Garder');
  const non = el('button', { type: 'button', 'data-cons-photo-ignorer': '', style: 'min-height:44px' }, 'Ignorer');
  const refus = el('p', { 'data-cons-photo-refus': '', role: 'alert', class: 'text-xs' });
  refus.hidden = true;
  oui.addEventListener('click', () => {
    const n = Number(kwh.value.trim().replace(',', '.'));
    refus.hidden = false;
    if (!choix.value) refus.textContent = 'Choisissez le mois de cette facture.';
    else if (!Number.isFinite(n) || n <= 0) refus.textContent = 'Saisissez les kWh lus sur la facture (un nombre positif).';
    else { garder(Number(choix.value), n); ligne.remove(); }
  });
  non.addEventListener('click', () => ligne.remove());
  ligne.append(choix, kwh, oui, non, refus);
  return ligne;
}

/** Le bloc photo : rien sans option ; le bouton n'existe que si `disponible` est vrai (sinon : la raison, en petit). */
function monterBlocPhoto(grille: HTMLElement, option: OptionLireFacture, remplir: (mois: number, kwh: number) => void): void {
  const bloc = el('div', { 'data-cons-photo': '' });
  grille.appendChild(bloc);
  const message = (t: string) => { bloc.querySelector('[data-cons-photo-message]')?.remove(); bloc.appendChild(el('p', { 'data-cons-photo-message': '', class: 'text-xs' }, t)); };
  void option.disponible().then((d) => {
    if (!d?.disponible) { if (d?.motif) message(d.motif); return; }
    const choisir = el('input', { type: 'file', accept: 'image/*', 'data-cons-photo-fichier': '', 'aria-label': 'Lire une photo de facture', style: 'min-height:44px' });
    const liste = el('div', { 'data-cons-photo-lignes': '' });
    bloc.append(el('p', { class: 'text-sm' }, 'Lire une photo de facture'), choisir, liste);
    choisir.addEventListener('change', () => {
      const fichier = choisir.files?.[0];
      if (!fichier) return;
      liste.replaceChildren();
      bloc.querySelector('[data-cons-photo-message]')?.remove();
      option.lire(fichier).then((rep) => {
        if (!rep?.lignes?.length) { message(rep?.motif || MOTIF_LECTURE_VIDE); return; }
        rep.lignes.forEach((l) => liste.appendChild(ligneLue(l, remplir)));
      }, () => message(MOTIF_LECTURE_VIDE));
    });
  }, () => undefined);
}

export interface DepsGrille {
  /** ACAL840 — la lecture de photo fournie par la page hôte ; absente ⇒ aucun bouton. */
  lireFacture?: OptionLireFacture | null;
  lancer: (corps: CorpsPropositionConsommation) => void;
  classe: () => string;
  /** Reçoit chaque réponse (`mois[]`) ou refus (`champs`) du serveur. */
  ecouter: (f: (rep: { mois?: MoisPropose[] } | null, refus?: { champs?: Record<string, string> } | null) => void) => void;
  /** ACAL1610 — la grille se remplit depuis le document et y réécrit chaque frappe (`liaisonFactures`). */
  factures?: LiaisonFactures;
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
    <div data-cons-mois-barres class="flex items-end" style="gap:2px;width:100%;min-width:0"></div>`;
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
  // ACAL1909 — la grille est montée à l'init de l'atelier, AVANT que le document relu soit posé : les
  // mois enregistrés se relisent donc aussi à l'ouverture de la grille et au premier focus, tant que
  // l'utilisateur n'y a rien saisi (un mois effacé à la main n'est jamais ressuscité).
  let touchee = false;
  const remplirDepuisDocument = () => {
    if (touchee) return;
    let rempli = false;
    for (const f of deps.factures?.lire() ?? []) {
      const ligne = grille.querySelector<HTMLElement>(`[data-cons-mois-ligne="${f.mois}"]`)!;
      const champ = ligne.querySelector<HTMLInputElement>('[data-cons-mois-valeur]')!;
      if (champ.value.trim()) continue;
      champ.value = String(f.valeur);
      ligne.querySelector<HTMLSelectElement>('[data-cons-mois-unite]')!.value = f.unite;
      rempli = true;
    }
    if (rempli) envoyer();
  };
  grille.addEventListener('toggle', remplirDepuisDocument);
  grille.addEventListener('focusin', remplirDepuisDocument);
  grille.addEventListener('input', () => {
    remplirDepuisDocument(); // un mois saisi avant toute relecture part avec les mois enregistrés, jamais seul
    touchee = true;
    deps.factures?.ecrire(facturesDepuisLignes(lignes())); // ACAL1610 — écrit au document sans délai
    if (minuterie != null) clearTimeout(minuterie);
    minuterie = setTimeout(envoyer, DELAI_FRAPPE_MS);
  });
  // ACAL1610 — les mois relus du document remplissent la grille ; la proposition (barres) est relancée.
  remplirDepuisDocument();
  if (deps.lireFacture) {
    monterBlocPhoto(grille, deps.lireFacture, (mois, kwh) => {
      const ligne = grille.querySelector<HTMLElement>(`[data-cons-mois-ligne="${mois}"]`);
      const champ = ligne?.querySelector<HTMLInputElement>('[data-cons-mois-valeur]');
      const unite = ligne?.querySelector<HTMLSelectElement>('[data-cons-mois-unite]');
      if (!champ || !unite) return;
      unite.value = 'kwh';
      champ.value = String(kwh);
      grille.dispatchEvent(new Event('input', { bubbles: true })); // relance la proposition (même délai de frappe)
    });
  }
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
