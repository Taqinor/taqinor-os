// ACAL576 — COUPURES AUTOMATIQUES DU PAVAGE (contrat ACAL586, `zones[].coupuresPavage`).
// Des bandes INTERDITES du pan, qu'un pavage inchangé (`packConfig` n'est PAS modifié) évite
// comme une zone interdite. LA RÈGLE (contrat) : origine = bord gauche du posable (contour moins
// retrait latéral) ; c = pas de colonne du pavage ; n = ⌈largeur ÷ c⌉ colonnes ENTIÈRES ; la
// bande k ≥ 1 commence à origine + (k·N + (k−1)·n)·c et mesure n·c. Valeurs SAISIES uniquement.
import { type LngLat } from '../../lib/roof';
import { ringUVBounds, uvToENU, projectRingENU } from '../../lib/roofGrid';
import { geomAxes } from '../../lib/freeLayout';
import { PANEL_SIDE_GAP_M, resolveSetbacks, type PerimeterSetbacks } from '../../lib/roofPro2';
import { DEG2M } from './constants';
import { type Ctx } from './context';

export interface CoupuresPavage { tousLesNModules: number; largeurCoupureM: number; source: string }
const EPS_M = 1e-3; // la bande est rentrée d'1 mm de chaque bord : la colonne voisine ne la touche jamais

/** La clé relue, ou `null` (hors contrat = absente, jamais complétée). */
export function lireCoupures(brut: unknown): CoupuresPavage | null {
  const c = brut as Partial<CoupuresPavage> | null | undefined;
  if (!c || typeof c !== 'object') return null;
  if (!Number.isInteger(c.tousLesNModules) || (c.tousLesNModules as number) < 1) return null;
  if (typeof c.largeurCoupureM !== 'number' || !(c.largeurCoupureM > 0)) return null;
  if (typeof c.source !== 'string' || !c.source.trim()) return null;
  return { tousLesNModules: c.tousLesNModules as number, largeurCoupureM: c.largeurCoupureM, source: c.source };
}

/** Les trois champs saisis : un champ vide ⇒ aucune coupure ; une valeur ≤ 0 ⇒ refus qui nomme le champ. */
export function validerCoupures(n: string, largeur: string, source: string):
  { ok: true; coupures: CoupuresPavage | null } | { ok: false; champ: string; motif: string } {
  const [sn, sl, ss] = [n, largeur, source].map((v) => String(v ?? '').trim());
  if (!sn || !sl || !ss) return { ok: true, coupures: null };
  const nn = Number(sn.replace(',', '.'));
  if (!Number.isInteger(nn) || nn < 1) return { ok: false, champ: 'tousLesNModules', motif: 'Coupure tous les N modules : un entier, au moins 1.' };
  const l = Number(sl.replace(',', '.'));
  if (!Number.isFinite(l) || l <= 0) return { ok: false, champ: 'largeurCoupureM', motif: 'Largeur de la coupure (m) : un nombre supérieur à 0.' };
  return { ok: true, coupures: { tousLesNModules: nn, largeurCoupureM: l, source: ss } };
}

/** Fragment de pan : `{ coupuresPavage }` s'il y en a, `{}` sinon (pan inchangé à l'octet). */
export function emettreCoupures(c: CoupuresPavage | null | undefined): { coupuresPavage?: CoupuresPavage } {
  const v = lireCoupures(c);
  return v ? { coupuresPavage: { ...v } } : {};
}

/** Colonnes ENTIÈRES retirées par bande : n = ⌈largeur ÷ c⌉ (jamais moins que saisi). */
export const colonnesParCoupure = (largeurM: number, pasM: number): number => Math.ceil(largeurM / pasM - 1e-9);

/** Anneaux [lng, lat] des bandes interdites d'un contour, au pas de colonne `pasColonneM`. */
export function anneauxDeCoupures(ring: readonly LngLat[], c: CoupuresPavage | null, o: { azimuthDeg: number; pasColonneM: number; retraitLateralM: number }): LngLat[][] {
  if (!c || ring.length < 3 || !(o.pasColonneM > 0)) return [];
  const { olng, olat, ringENU } = projectRingENU([...ring]);
  const { u, s } = geomAxes(o.azimuthDeg);
  const { uMin, uMax, vMin, vMax } = ringUVBounds(ringENU, u, s);
  const toENU = uvToENU(u, s);
  const cosLat = Math.cos((olat * Math.PI) / 180);
  const versLngLat = ([x, y]: [number, number]): LngLat => [olng + x / (DEG2M * cosLat), olat + y / DEG2M];
  const n = colonnesParCoupure(c.largeurCoupureM, o.pasColonneM);
  const origine = uMin + o.retraitLateralM;
  const out: LngLat[][] = [];
  for (let k = 1; ; k++) {
    const debut = origine + (k * c.tousLesNModules + (k - 1) * n) * o.pasColonneM;
    if (debut >= uMax) break;
    const [a, b] = [debut + EPS_M, debut + n * o.pasColonneM - EPS_M];
    out.push([[a, vMin - 1], [b, vMin - 1], [b, vMax + 1], [a, vMax + 1]].map(([uu, vv]) => versLngLat(toENU(uu, vv))));
  }
  return out;
}

/** La phrase de la coupure RÉELLEMENT retirée (largeur lue au pas du pavage, jamais une constante). */
export function noteCoupure(c: CoupuresPavage, pasColonneM: number): string {
  const n = colonnesParCoupure(c.largeurCoupureM, pasColonneM);
  return `Coupure réelle : ${n} colonne${n > 1 ? 's' : ''} retirée${n > 1 ? 's' : ''} (largeur lue au pas du pavage) pour ${c.largeurCoupureM.toLocaleString('fr-FR', { minimumFractionDigits: 2 })} m demandés`;
}

/** Pas de colonne du pavage courant du pan actif (même règle que `packConfig`), ou null. */
function pasDuPavage(ctx: Ctx): number | null {
  const w = ctx.layoutPlan?.grid?.rowWidthM;
  const gap = Number.isFinite(ctx.colGapM) ? Math.max(0, ctx.colGapM as number) : PANEL_SIDE_GAP_M;
  return typeof w === 'number' && w > 0 ? w + gap : null;
}

/** Les bandes du pan ACTIF, dans le repère de son pavage courant ; aucune clé ou aucun pavage ⇒ []. */
export function anneauxCoupuresDuPanActif(ctx: Ctx, setbacks: Partial<PerimeterSetbacks> | undefined): LngLat[][] {
  const c = lireCoupures(ctx.activeArea?.()?.coupuresPavage);
  const pas = pasDuPavage(ctx);
  const az = ctx.layoutPlan?.pack?.azimuthDeg;
  if (!c || pas == null || typeof az !== 'number') return [];
  const lateral = ctx.sel?.margin === 'remove' ? 0 : resolveSetbacks(setbacks).lateralM;
  return anneauxDeCoupures(ctx.vertices, c, { azimuthDeg: az, pasColonneM: pas, retraitLateralM: lateral });
}

/** Les trois champs, rangés sous « Personnaliser la disposition » (rubrique « Avancé »). */
export function monterChampsCoupures(ctx: Ctx, deps: { recalc: () => void }): void {
  const hote = typeof document !== 'undefined' ? document.getElementById('rp9-layout-panel') : null;
  if (!hote || document.getElementById('rp9-coupures')) return;
  const bloc = document.createElement('details');
  bloc.id = 'rp9-coupures';
  bloc.className = 'mt-2 text-xs';
  const champ = (id: string, libelle: string, mode: string) =>
    `<label class="flex min-h-11 items-center gap-2" for="${id}">${libelle}<input type="text" id="${id}" class="rp9-input w-24" inputmode="${mode}" /></label>`;
  bloc.innerHTML = `<summary class="min-h-11 cursor-pointer">Avancé — coupures du pavage</summary>`
    + champ('rp9-coupure-n', 'Coupure tous les N modules', 'numeric') + champ('rp9-coupure-largeur', 'Largeur de la coupure (m)', 'decimal')
    + champ('rp9-coupure-source', 'Pourquoi (allée de maintenance…)', 'text')
    + `<p id="rp9-coupure-erreur" class="text-alert-300" role="alert" hidden></p><p id="rp9-coupure-note" class="text-lune-soft"></p>`;
  hote.appendChild(bloc);
  const val = (id: string) => (document.getElementById(id) as HTMLInputElement | null)?.value ?? '';
  const erreur = document.getElementById('rp9-coupure-erreur');
  const note = document.getElementById('rp9-coupure-note');
  const peindre = () => {
    const c = lireCoupures(ctx.activeArea?.()?.coupuresPavage);
    const pas = pasDuPavage(ctx);
    if (note) note.textContent = c && pas ? noteCoupure(c, pas) : '';
  };
  bloc.addEventListener('change', () => {
    const v = validerCoupures(val('rp9-coupure-n'), val('rp9-coupure-largeur'), val('rp9-coupure-source'));
    if (erreur) { erreur.hidden = v.ok; erreur.textContent = v.ok ? '' : v.motif; }
    const pan = ctx.activeArea?.();
    if (!v.ok || !pan) return;
    if (v.coupures) pan.coupuresPavage = v.coupures; else delete pan.coupuresPavage;
    deps.recalc();
    peindre();
  });
  bloc.addEventListener('toggle', () => {
    const c = lireCoupures(ctx.activeArea?.()?.coupuresPavage);
    const ecrire = (id: string, v: string) => { const el = document.getElementById(id) as HTMLInputElement | null; if (el) el.value = v; };
    ecrire('rp9-coupure-n', c ? String(c.tousLesNModules) : '');
    ecrire('rp9-coupure-largeur', c ? String(c.largeurCoupureM).replace('.', ',') : '');
    ecrire('rp9-coupure-source', c?.source ?? '');
    peindre();
  });
}
