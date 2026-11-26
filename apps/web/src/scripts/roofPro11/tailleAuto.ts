// ACAL1331 + ACAL1448 (D-ACAL-76 « dimensionner », 23/11/2026) — LA TAILLE POSÉE D'ELLE-MÊME, DITE.
// Un calepinage VIERGE de l'atelier ERP (aucune pose enregistrée) se pose, dès que son toit est fermé, à la taille de la
// cible SERVIE — celle du devis lié (option retenue, ACAL1951), sinon celle tirée de la facture du lead (même calcul que
// le devis, `ventes.selectors.cible_depuis_lead`). La pose elle-même passe par le chemin existant (`hydrateFromDevis` →
// `imposeTarget` → `placedFor`) ; ce module la DIT (« Posé d'après la facture : … — ajustez si besoin ») tant que le
// commercial n'a rien ajusté, et garde la taille quand le toit est découpé en pans. Une pose tenue (relue, déplacée)
// n'est jamais re-posée (ACAL1900, `poseTenue`). Site public : `opts.chiffrage` absent ⇒ rien ne change.
import type { Ctx } from './context';
import type { AreaRecord } from './types';
import { fmt, fmtKwc } from './dom';
import { poseTenue } from './panExistant';

/** D'où vient la cible servie (`design-context` → `cible.source`, projeté par l'ERP en `origineCible`). T4-X8-012 (une cible) — les MOTS viennent
 *  du payload (`libelleApresOrigineCible`, la table de l'ERP `contexteAtelier.js::LIBELLES_APRES_SOURCE_CIBLE`, la même que la carte) ; ceci n'est
 *  que le repli d'un payload sans ce mot. */
const ORIGINES: Record<string, string> = { devis: 'le devis', factures: 'la facture', lead: 'la taille souhaitée du lead' };

type CtxTaille = Parameters<typeof poseTenue>[0] & Pick<Ctx, 'neededPanels'> & {
  opts?: { chiffrage?: unknown; hydrate?: { devis?: Record<string, unknown> | null } | null };
};

/** Le document relu au boot ne porte aucune pose enregistrée (aucun pan avec des panneaux). */
export function documentVierge(doc: unknown): boolean {
  const zones = (doc as { zones?: unknown } | null | undefined)?.zones;
  if (!Array.isArray(zones)) return true;
  return !zones.some((z) => ((z as { geometry?: { panels?: unknown[] } } | null)?.geometry?.panels?.length ?? 0) > 0);
}

/** La taille posée d'elle-même, si elle est EN VIGUEUR : atelier ERP, payload de boot à cible servie d'origine connue,
 *  document vierge, nombre voulu = cible, pose non tenue. `null` sinon (ajustée, relue, site public). */
export function tailleAutoEnVigueur(ctx: CtxTaille): { panneaux: number; origine: string; apres: string } | null {
  if (ctx.opts?.chiffrage === undefined) return null;
  const p = ctx.opts?.hydrate?.devis;
  const origine = typeof p?.origineCible === 'string' && ORIGINES[p.origineCible] ? p.origineCible : null;
  const panneaux = Math.round(Number((p?.cible as { panneaux?: unknown } | null | undefined)?.panneaux));
  if (!origine || !(panneaux > 0) || !documentVierge((p?.geometrie as { roof_layout?: unknown } | null)?.roof_layout)) return null;
  const mots = typeof p?.libelleApresOrigineCible === 'string' ? p.libelleApresOrigineCible.trim() : '';
  return ctx.neededPanels === panneaux && !poseTenue(ctx) ? { panneaux, origine, apres: mots || ORIGINES[origine] } : null;
}

/** La note du nombre de panneaux (`rp9-need-note`) quand la taille posée est celle de la cible : « Posé d'après la
 *  facture : 8 panneaux · 5,68 kWc — ajustez si besoin. », ou, toit trop petit, « … : 4 panneaux · 2,84 kWc sur 8 —
 *  seuls 4 tiennent … ; ajustez si besoin. » (la raison de l'écart reprise de `note`, après `prefixe`). Sinon `note`. */
export function noteTailleAuto(ctx: CtxTaille, placed: number, carte: { count: number; kwc: number } | null, note: string, prefixe: string): string {
  const t = tailleAutoEnVigueur(ctx);
  if (!t || !(placed > 0)) return note;
  const kwc = carte && carte.count > 0 ? ` · ${fmtKwc((carte.kwc * placed) / carte.count)} kWc` : '';
  const tete = `Posé d’après ${t.apres} : ${fmt(placed)} panneaux${kwc}`;
  if (placed >= t.panneaux) return `${tete} — ajustez si besoin.`;
  const raison = note.startsWith(prefixe) ? note.slice(prefixe.length).replace(/\.$/, '') : '';
  return `${tete} sur ${fmt(t.panneaux)}${raison} ; ajustez si besoin.`;
}

/** ACAL1448 — « Forme du toit » (2 pans, 4 pans…) remplace le pan actif par ses découpes : dans l'atelier ERP (`erp`), le
 *  premier pan (le mieux exposé, celui que l'atelier charge) garde le nombre voulu du pan découpé, et tous gardent son
 *  module — sinon la cible tombait et chaque pan se remplissait (15 panneaux pour une cible de 5, module changé). */
export function heriterDuPanDecoupe(
  ancien: Pick<AreaRecord, 'moduleId'> | null | undefined,
  besoin: { neededPanels: number; neededAuto: boolean },
  pans: AreaRecord[],
  erp: boolean,
): void {
  if (!erp || !pans.length) return;
  pans[0].neededPanels = besoin.neededPanels;
  pans[0].neededAuto = besoin.neededAuto;
  repartirLeNombre(besoin, pans); // ACAL1707
  if (ancien?.moduleId) for (const p of pans) if (!p.existant) p.moduleId = ancien.moduleId;
}

/** Surface relative d'un contour lng/lat (formule des lacets, longitude pondérée par cos(latitude)) : sert seulement de poids. */
function surfaceRelative(v: readonly (readonly [number, number])[]): number {
  if (v.length < 3) return 0;
  const k = Math.cos((v.reduce((s, p) => s + p[1], 0) / v.length) * (Math.PI / 180));
  let a = 0;
  for (let i = 0; i < v.length; i++) { const [x1, y1] = v[i]; const [x2, y2] = v[(i + 1) % v.length]; a += x1 * k * y2 - x2 * k * y1; }
  return Math.abs(a) / 2;
}

/** ACAL1707 — un nombre voulu FIGÉ (la pose existante) est RÉPARTI entre les pans découpés au prorata de leur surface, hors pans
 *  tournés vers le nord (rien n'y tient) ; leur somme reste le nombre d'avant, jamais un pan rempli en plus. Aucun contour ⇒ rien
 *  n'est réparti (le premier pan garde tout, comme avant). Plus grand reste pour l'arrondi. */
function repartirLeNombre(besoin: { neededPanels: number; neededAuto: boolean }, pans: AreaRecord[]): void {
  if (besoin.neededAuto || !(besoin.neededPanels > 0) || pans.length < 2) return;
  const ecartSud = (az: number) => { const d = (((az - 180) % 360) + 360) % 360; return Math.min(d, 360 - d); };
  const poids = pans.map((p) => (Number.isFinite(p.facingAzimuthDeg) && ecartSud(p.facingAzimuthDeg) > 90 ? 0 : surfaceRelative(p.vertices ?? [])));
  const total = poids.reduce((a, b) => a + b, 0);
  if (!(total > 0)) return;
  const n = Math.round(besoin.neededPanels);
  const parts = poids.map((w) => (w / total) * n);
  const base = parts.map(Math.floor);
  let reste = n - base.reduce((a, b) => a + b, 0);
  parts.map((x, i) => ({ i, f: x - base[i] })).sort((a, b) => b.f - a.f || a.i - b.i).forEach(({ i }) => { if (reste > 0 && poids[i] > 0) { base[i]++; reste--; } });
  pans.forEach((p, i) => { p.neededPanels = base[i]; p.neededAuto = false; });
}
