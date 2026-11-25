// ═══════════ ACAL193 — PROVENANCE DE L'ÉPINGLE (D-ACAL-13) ═══════════
// Sorti de `prefill.ts` (ACAL593 : un fichier de 2 000 lignes ou plus ne grossit pas) — à
// l'identique : `serializeLayout` l'appelle toujours en dernier.
import { type LngLat } from '../../lib/roof';
import { type Ctx } from './context';

const copieJson = <T>(v: T): T => JSON.parse(JSON.stringify(v)) as T;

/** L'épingle DÉPLACÉE À LA MAIN dans cette session, par scène (le contexte vivant de
 *  l'atelier) — hors du type `Ctx` : c'est un état de geste, pas une couche du document. */
const epinglesDeplacees = new WeakMap<object, { lat: number; lng: number }>();

/** ACAL193 — le dessinateur a déplacé l'épingle à la main : la scène passe `pinSource` à
 *  'manuel' et le prochain document porte CETTE épingle. Une coordonnée non finie est
 *  ignorée (jamais une épingle inventée). */
export function deplacerEpingleALaMain(ctx: Ctx, lngLat: LngLat): void {
  const [lng, lat] = lngLat;
  if (!Number.isFinite(lng) || !Number.isFinite(lat)) return;
  epinglesDeplacees.set(ctx as object, { lat, lng });
  localiserSite(ctx, 'epingle'); // T4-U4-013 — l'épingle posée à la main localise le site
}

/** ACAL193 — oublie le déplacement (nouveau lead, effacement complet de la scène). */
export function oublierEpingleDeplacee(ctx: Ctx): void {
  epinglesDeplacees.delete(ctx as object);
  const site = sitesLocalises.get(ctx as object);
  if (site) changerSite(site, site.initial);
}

// ═══════════ T4-U4-013 — LE DOCUMENT DIT SI LE SITE A ÉTÉ LOCALISÉ ═══════════
// `pin` est le centre du pan tracé, que quelqu'un ait localisé le site ou non : un toit
// tracé par clics à l'échelle du pays partait avec une épingle « posée » au milieu du
// Maroc, et la simulation y calculait. La clé racine `siteLocalise` (contrat
// `roof_layout_v2.schema.json`) dit D'OÙ vient le site : 'lead' (GPS de la fiche),
// 'adresse' (recherche d'adresse, « Localiser », coordonnées collées), 'epingle'
// (épingle déplacée à la main), 'trace' (toit tracé ou créé sur la carte zoomée au
// niveau du toit) ; `null` = personne ne l'a localisé. Le serveur
// (`services/site.py::epingle_posee`) n'utilise l'épingle que si elle porte une
// provenance. Rien n'est écrit tant que la page hôte n'a pas ACTIVÉ le suivi
// (calepinage de l'ERP) : le site public et les autres modes repartent octet-identiques.

/** Les provenances qui localisent le site. */
export type ProvenanceSite = 'lead' | 'adresse' | 'epingle' | 'trace';
/** `undefined` = document ancien sans la clé (règle du serveur, rien n'est écrit). */
export type EtatSite = ProvenanceSite | null | undefined;

/** Zoom de la carte à partir duquel un toit tracé est un toit VU (≈ 1 m par pixel). */
export const ZOOM_TOIT_VISIBLE = 17;

interface SuiviSite { initial: EtatSite; valeur: EtatSite; ecouter?: (etat: EtatSite) => void }
const sitesLocalises = new WeakMap<object, SuiviSite>();

function changerSite(site: SuiviSite, valeur: EtatSite): void {
  if (site.valeur === valeur) return;
  site.valeur = valeur;
  site.ecouter?.(valeur);
}

/** T4-U4-013 — la page hôte active le suivi avec l'état LU (`siteLocaliseInitial` côté
 *  ERP) ; `ecouter` reçoit l'état courant tout de suite, puis à chaque changement. */
export function activerSuiviSite(ctx: Ctx, initial: EtatSite, ecouter?: (etat: EtatSite) => void): void {
  sitesLocalises.set(ctx as object, { initial, valeur: initial, ecouter });
  ecouter?.(initial);
}

/** L'état courant du site (`undefined` aussi quand le suivi n'est pas activé). */
export function etatSite(ctx: Ctx): EtatSite {
  return sitesLocalises.get(ctx as object)?.valeur;
}

/** Un geste de l'utilisateur a localisé le site (sans effet si le suivi est éteint). */
export function localiserSite(ctx: Ctx, provenance: ProvenanceSite): void {
  const site = sitesLocalises.get(ctx as object);
  if (site) changerSite(site, provenance);
}

/** Un coin tracé (ou un toit créé par ses cotes) à `zoom` : il localise le site seulement
 *  quand la carte montre le toit (zoom ≥ ZOOM_TOIT_VISIBLE) et que rien ne l'a déjà fait. */
export function localiserSiTraceVisible(ctx: Ctx, zoom: number): void {
  const site = sitesLocalises.get(ctx as object);
  if (site && !site.valeur && Number.isFinite(zoom) && zoom >= ZOOM_TOIT_VISIBLE) changerSite(site, 'trace');
}

/** ACAL193 — `pinSource` / `repereAcquitte` du document RELU, réémis octet-identiques ;
 *  une épingle déplacée à la main dans la session pose `pin` + `pinSource: 'manuel'`. Un
 *  document qui ne porte aucune des deux clés repart sans elles (rien d'inventé). */
export function emettreProvenanceEpingle<T extends object>(layout: T, ctx: Ctx): T {
  const relu = ctx.documentRelu ?? null;
  const sortie = layout as unknown as Record<string, unknown>;
  if (relu && typeof relu === 'object') {
    if ('pinSource' in relu) sortie.pinSource = copieJson(relu.pinSource);
    if ('repereAcquitte' in relu) sortie.repereAcquitte = copieJson(relu.repereAcquitte);
  }
  const deplacee = epinglesDeplacees.get(ctx as object);
  if (deplacee) {
    sortie.pin = { ...deplacee };
    sortie.pinSource = 'manuel';
  }
  // T4-U4-013 — suivi activé : la provenance du site (ou `null`) ; document ancien
  // (`undefined`) : la clé relue, s'il y en a une, repart telle quelle.
  const site = sitesLocalises.get(ctx as object);
  if (site && site.valeur !== undefined) sortie.siteLocalise = site.valeur;
  return layout;
}

// ═══════════ T4-X2-005 — UN SEUL LIEU POUR TOUS LES CALCULS D'UN CALEPINAGE ═══════════
// Site non localisé : la simulation (serveur) calcule sur le point de repli (ville de
// référence, repère GPS de la fiche — `calepinage.site_de_repli_point`), alors que l'atelier
// calait le pas entre rangées et ses autres calculs solaires sur la latitude du TRACÉ (un toit
// dessiné sur la carte au niveau du pays : 31,79° au lieu de 33,57°). Tant que le suivi dit
// « non localisé » (`null`), la latitude des calculs est celle du repli SERVI ; sinon (site
// localisé, document ancien, site public sans suivi) celle du tracé, comme avant.

/** Le point de repli SERVI utilisé pour les calculs, ou `null` (site localisé, pas de repli, pas de suivi). */
export function lieuDeRepli(ctx: Ctx): { lat: number; libelle: string } | null {
  const repli = (ctx.opts as { suiviSite?: { repli?: { lat?: unknown; libelle?: unknown } | null } } | undefined)?.suiviSite?.repli;
  if (etatSite(ctx) !== null || !repli || typeof repli.lat !== 'number' || !Number.isFinite(repli.lat)) return null;
  return { lat: repli.lat, libelle: typeof repli.libelle === 'string' ? repli.libelle : '' };
}

/** La latitude des calculs solaires de l'atelier : le repli servi tant que le site n'est pas localisé, sinon celle du tracé. */
export function latitudeDuCalcul(ctx: Ctx, latitudeDuTrace: number): number {
  return lieuDeRepli(ctx)?.lat ?? latitudeDuTrace;
}
