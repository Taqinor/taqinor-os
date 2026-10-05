/**
 * ACAL233 — la PARCELLE tracée dans l'atelier 3D (clé racine `parcelle` du document).
 *
 * Constat C-ACAL-131 : le plan de masse (`plan-masse.pdf`) lit `parcelle {vertices}` mais aucun
 * écran ne l'écrivait. Ce module porte la géométrie PURE (refus d'un point qui croise, refus
 * de moins de 3 sommets, lecture/émission du document) et la petite session de tracé ; l'entrée
 * (`roof-tool-pro11.ts`) ne fait que router les clics carte et peindre le calque pointillé.
 *
 * Aucune valeur inventée : la parcelle n'existe que si l'utilisateur l'a tracée (ou si le
 * document rouvert la portait) ; sans parcelle, aucune clé n'est émise.
 */
import { isSimplePolygon, type LngLat } from '../../lib/roof';
import { type Ctx } from './context';

/** La parcelle du document : un anneau [lng, lat] (les autres clés relues sont conservées). */
export interface Parcelle {
  vertices: LngLat[];
  [cle: string]: unknown;
}

export const PARCELLE_MIN_SOMMETS = 3;

export const MOTIFS_PARCELLE = {
  troisSommets: 'Une parcelle compte au moins 3 sommets — posez encore un point.',
  croise: 'Ce point croiserait le contour de la parcelle — placez-le ailleurs pour garder un polygone simple.',
  contourCroise: 'Le contour de la parcelle se croise — corrigez-le avant de terminer.',
} as const;

const estCouple = (p: unknown): p is LngLat =>
  Array.isArray(p) && p.length >= 2 && Number.isFinite(p[0]) && Number.isFinite(p[1]);

/** Verdict de validité d'un anneau de parcelle (≥ 3 sommets, polygone simple). */
export function validerParcelle(vertices: readonly LngLat[]): { ok: boolean; motif?: string } {
  if (!Array.isArray(vertices) || vertices.length < PARCELLE_MIN_SOMMETS || !vertices.every(estCouple)) {
    return { ok: false, motif: MOTIFS_PARCELLE.troisSommets };
  }
  if (!isSimplePolygon([...vertices] as LngLat[])) return { ok: false, motif: MOTIFS_PARCELLE.contourCroise };
  return { ok: true };
}

/** Refus d'un sommet qui ferait CROISER le polygone (même garde que le tracé du toit, W76). */
export function sommetParcelleAcceptable(vertices: readonly LngLat[], p: LngLat): { ok: boolean; motif?: string } {
  if (vertices.length >= PARCELLE_MIN_SOMMETS && !isSimplePolygon([...vertices, p] as LngLat[])) {
    return { ok: false, motif: MOTIFS_PARCELLE.croise };
  }
  return { ok: true };
}

/** La parcelle du document relu (copie), ou `null` quand elle est absente / inexploitable. */
export function lireParcelle(doc: unknown): Parcelle | null {
  const brut = (doc as { parcelle?: unknown } | null | undefined)?.parcelle;
  if (!brut || typeof brut !== 'object') return null;
  const v = (brut as { vertices?: unknown }).vertices;
  if (!Array.isArray(v) || v.length < PARCELLE_MIN_SOMMETS || !v.every(estCouple)) return null;
  return JSON.parse(JSON.stringify(brut)) as Parcelle;
}

/** Fragment du document : `{ parcelle }` quand elle existe, `{}` sinon (aucune clé inventée). */
export function emettrePourDocument(parcelle: Parcelle | null | undefined): { parcelle?: Parcelle } {
  if (!parcelle || !Array.isArray(parcelle.vertices) || parcelle.vertices.length < PARCELLE_MIN_SOMMETS) return {};
  return { parcelle: JSON.parse(JSON.stringify(parcelle)) as Parcelle };
}

export interface ParcelleUiDeps {
  /** Repeint le calque pointillé et l'état des boutons. */
  render?: () => void;
  /** Message du bandeau de statut. */
  setStatus?: (msg: string) => void;
}

export interface ParcelleUi {
  isActive: () => boolean;
  sessionPoints: () => LngLat[];
  begin: () => void;
  cancel: () => void;
  /** Pose un sommet ; renvoie `false` (et rien n'est posé) si le point croiserait le contour. */
  addPoint: (p: LngLat) => boolean;
  /** Ferme la parcelle : refuse (sans rien écrire) sous 3 sommets. */
  finish: () => { ok: boolean; motif?: string };
  /** Retire la parcelle du document (la clé disparaît à l'enregistrement). */
  clear: () => void;
  get: () => Parcelle | null;
}

/** La petite session de tracé ; l'état vivant de la parcelle est `ctx.parcelle`. */
export function createParcelleUi(ctx: Ctx, deps: ParcelleUiDeps = {}): ParcelleUi {
  let session: LngLat[] | null = null;
  const render = () => deps.render?.();
  const dire = (m: string) => deps.setStatus?.(m);
  return {
    isActive: () => session !== null,
    sessionPoints: () => (session ? session.slice() : []),
    begin() {
      session = [];
      render();
      dire('Touchez la carte pour poser les sommets de la parcelle, puis « Terminer la parcelle ».');
    },
    cancel() {
      session = null;
      render();
    },
    addPoint(p) {
      if (!session) return false;
      const verdict = sommetParcelleAcceptable(session, p);
      if (!verdict.ok) {
        dire(verdict.motif ?? MOTIFS_PARCELLE.croise);
        return false;
      }
      session.push([p[0], p[1]]);
      render();
      return true;
    },
    finish() {
      if (!session) return { ok: false, motif: MOTIFS_PARCELLE.troisSommets };
      const verdict = validerParcelle(session);
      if (!verdict.ok) {
        dire(verdict.motif ?? MOTIFS_PARCELLE.troisSommets);
        return verdict;
      }
      const existante = (ctx.parcelle ?? {}) as Partial<Parcelle>;
      ctx.parcelle = { ...existante, vertices: session.map((p) => [p[0], p[1]] as LngLat) };
      session = null;
      render();
      dire('Parcelle posée — enregistrez pour la conserver.');
      return { ok: true };
    },
    clear() {
      session = null;
      ctx.parcelle = null;
      render();
    },
    get: () => (ctx.parcelle ? (JSON.parse(JSON.stringify(ctx.parcelle)) as Parcelle) : null),
  };
}
