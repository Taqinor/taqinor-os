// ACAL528 — rectangles de modules en lng/lat depuis le SEUL document enregistré. Aucun import de
// `three` ni de `maplibre-gl` : la page « Photos du site » (ERP, alias `@roofpro/modulesGeo`) n'a que
// le document. `panelQuadsLngLat` est la formule UNIQUE (CAL104), déplacée telle quelle de
// `scene3d.ts` (qui la ré-exporte) : aucun calcul de quadrilatère neuf.
import { WGS84_RADIUS } from '../../lib/geo';
import { MODULE_ATELIER_PAR_DEFAUT } from '../../lib/roofPro2';
import type { LngLat } from '../../lib/roof';

/** Un module posé, en lng/lat : les quatre coins tels que la 3D les a placés. */
export type PlanQuad = LngLat[];

export const PLAN_DEG2RAD = Math.PI / 180;
export const PLAN_DEG2M = PLAN_DEG2RAD * WGS84_RADIUS;

/**
 * CAL104 — quads lng/lat des modules POSÉS, reconstruits depuis la géométrie que la 3D a
 * déjà placée : centres ENU (`cx`, `cy`, repère `origin`), empreinte au sol du module
 * (`slopeLenM × cos β` dans le sens de la pente, `rowWidthM` le long de la rangée) et
 * azimut du pavage. AUCUN pavage n'est refait : on habille des centres existants, donc le
 * COMPTE est exactement celui de la 3D.
 */
export function panelQuadsLngLat(
  origin: LngLat,
  centers: readonly { cx: number; cy: number }[],
  slopeLenM: number,
  rowWidthM: number,
  tiltDeg: number,
  azimuthDeg: number,
): PlanQuad[] {
  const cosLat = Math.max(1e-6, Math.cos(origin[1] * PLAN_DEG2RAD));
  // Empreinte AU SOL dans le sens de la pente : la longueur du module vue de dessus.
  const depth = Math.max(1e-6, slopeLenM * Math.cos((tiltDeg || 0) * PLAN_DEG2RAD));
  const width = Math.max(1e-6, rowWidthM);
  // L'azimut oriente les rangées : on tourne le rectangle du même angle.
  const a = (azimuthDeg || 0) * PLAN_DEG2RAD;
  const ca = Math.cos(a);
  const sa = Math.sin(a);
  const half: [number, number][] = [
    [-width / 2, -depth / 2],
    [width / 2, -depth / 2],
    [width / 2, depth / 2],
    [-width / 2, depth / 2],
  ];
  return centers.map((c) =>
    half.map(([dx, dy]) => {
      const e = c.cx + dx * ca + dy * sa;
      const n = c.cy - dx * sa + dy * ca;
      return [origin[0] + e / (PLAN_DEG2M * cosLat), origin[1] + n / PLAN_DEG2M] as LngLat;
    }),
  );
}

/** Un pan du document, vu par la page de photo : ses modules en lng/lat, ou le MOTIF de leur absence. */
export interface ModulesDuPan {
  panId: string;
  quads: PlanQuad[];
  /** Le modèle posé, nommé. Le module par défaut de l'atelier est dit tel quel, jamais en silence. */
  moduleNomme?: string;
  motif?: string;
}

export const MODULE_PAR_DEFAUT_NOMME = "module par défaut de l'atelier";
type Obj = Record<string, unknown>;
const estObj = (v: unknown): v is Obj => !!v && typeof v === 'object' && !Array.isArray(v);
const positif = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v) && v > 0;

/** Les rectangles de modules de CHAQUE pan posé du document enregistré. Grand côté du module le long
 *  de la rangée, petit côté dans la pente (comme `roofPro2.cotesDePavage`). Dimensions `null` ou module
 *  introuvable au catalogue ⇒ ce pan est rendu SANS quadrilatère, avec son motif — jamais une
 *  dimension supposée. L'angle par module n'existe pas dans `panelQuadsLngLat` : non repris. */
export function modulesDuDocument(document: unknown): ModulesDuPan[] {
  const doc = estObj(document) ? document : {};
  const catalogue = (Array.isArray(doc.modules) ? doc.modules : []).filter(estObj);
  const resultat: ModulesDuPan[] = [];
  for (const z of Array.isArray(doc.zones) ? doc.zones : []) {
    const g = estObj(z) && estObj(z.geometry) ? z.geometry : null;
    if (!g || !Array.isArray(g.panels) || !Array.isArray(g.origin)) continue;
    const panId = String((z as Obj).id ?? '');
    const moduleId = typeof g.moduleId === 'string' && g.moduleId ? g.moduleId : null;
    let rowWidthM: number;
    let slopeLenM: number;
    let moduleNomme: string;
    if (moduleId === null) {
      rowWidthM = MODULE_ATELIER_PAR_DEFAUT.longM;
      slopeLenM = MODULE_ATELIER_PAR_DEFAUT.courtM;
      moduleNomme = MODULE_PAR_DEFAUT_NOMME;
    } else {
      const m = catalogue.find((c) => c.id === moduleId);
      if (!m) {
        resultat.push({ panId, quads: [], motif: `module « ${moduleId} » introuvable au catalogue du document` });
        continue;
      }
      if (!positif(m.longueurMm) || !positif(m.largeurMm)) {
        resultat.push({ panId, quads: [], moduleNomme: String(m.libelle ?? moduleId), motif: 'dimensions du module non saisies' });
        continue;
      }
      rowWidthM = Math.max(m.longueurMm, m.largeurMm) / 1000;
      slopeLenM = Math.min(m.longueurMm, m.largeurMm) / 1000;
      moduleNomme = String(m.libelle ?? moduleId);
    }
    const centres = (g.panels as unknown[]).filter(estObj).filter((p) => Number.isFinite(p.cx) && Number.isFinite(p.cy)) as unknown as { cx: number; cy: number }[];
    const quads = panelQuadsLngLat(g.origin as unknown as LngLat, centres, slopeLenM, rowWidthM, Number(g.tiltDeg) || 0, Number(g.azimuthDeg) || 0);
    resultat.push({ panId, quads, moduleNomme });
  }
  return resultat;
}
