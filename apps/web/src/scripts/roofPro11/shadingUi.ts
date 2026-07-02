/**
 * WJ19 — UI « Ombres voisines » (shadow-tracing) du builder pro-11.
 *
 * L'utilisateur trace une ombre VISIBLE sur l'image satellite (clic 1 = pied de
 * l'obstacle, clic 2 = bout de l'ombre). La hauteur est DÉDUITE (h = L·tan α) de la
 * position du soleil au moment supposé de la prise de vue (hypothèse ÉTIQUETÉE,
 * défaut ~10 h 30 solaire mi-saison — orbites héliosynchrones), puis :
 *   - l'obstruction est rendue en 3D (scene3d la lit via ctx.shadeObstructions) et
 *     projette une vraie ombre Three.js ;
 *   - la production PVGIS horaire est DÉRATÉE (ctx.shadeFactors, appliqué par la
 *     fenêtre de production) et le chiffre annuel suit (ctx.shadeAnnualFactor,
 *     appliqué par l'optimiseur).
 *
 * Tout le calcul vit dans le module PUR lib/shadingEngine.ts (testé). Ici : état,
 * câblage DOM, tracé sur la carte. Aucun réseau, aucun lead. Tous les nœuds DOM
 * sont optionnels (le harness jsdom ne les fournit pas) — l'outil tourne sans eux.
 */
import type maplibregl from 'maplibre-gl';
import { sunDirection } from '../../lib/roofPro2';
import {
  IMAGERY_SUN_DEFAULT,
  SHADE_OBSTRUCTION_HALF_WIDTH_M,
  hourlyShadeFactors,
  annualShadeFactor,
  obstructionHeightFromShadow,
  shadeObstructionsENU,
  shadowVector,
  pointSolarAccess,
  solarAccessColorRGB,
  type ShadeObstruction,
} from '../../lib/shadingEngine';
import { fallbackPerKwc } from '../../lib/productionEngine';
import { type LngLat } from '../../lib/roof';
import { FLOORS, FLOOR_HEIGHT_M, GOLD } from './constants';
import { $, esc } from './dom';
import { type Ctx } from './context';

export interface ShadingUiDeps {
  map: maplibregl.Map;
  setStatus: (msg: string) => void;
  /** Re-rend la zone active (3D + carte de résultat + fenêtre de production). */
  recalcDisplays: () => void;
  /** WJ21 — applique la teinte d'accès solaire aux panneaux 3D (scene3d), ou l'efface
   *  (colorFor null). Injecté en wrapper paresseux (scene3d est construit après). */
  applyHeatmap: (colorFor: ((cellIndex: number) => { r: number; g: number; b: number }) | null) => void;
}

export interface ShadingUi {
  /** Intercepte un clic carte quand le tracé d'ombre est actif. true = consommé. */
  handleMapClick: (lngLat: LngLat) => boolean;
  /** Recalcule hauteurs (hypothèse de prise de vue) + facteurs + affichages. */
  recomputeShading: () => void;
  /** WJ21 — ré-applique la heatmap d'accès solaire si elle est active (après un re-rendu
   *  qui a recréé les instances de panneaux). No-op si la heatmap est OFF. */
  refreshHeatmap: () => void;
  /** Efface toutes les ombres tracées (« Effacer » / nouveau tracé). */
  reset: () => void;
}

const SHADE_SRC = 'rp9-shade-lines';

export function createShadingUi(ctx: Ctx, deps: ShadingUiDeps): ShadingUi {
  const { map, setStatus, recalcDisplays, applyHeatmap } = deps;

  const addBtn = $<HTMLButtonElement>('rp9-shade-add');
  const clearBtn = $<HTMLButtonElement>('rp9-shade-clear');
  const hourEl = $<HTMLInputElement>('rp9-shade-hour');
  const hourValueEl = $('rp9-shade-hour-value');
  const listEl = $('rp9-shade-list');
  const noteEl = $('rp9-shade-note');
  // WJ21 — carte d'accès solaire (heatmap d'irradiance).
  const heatmapBtn = $<HTMLButtonElement>('rp9-heatmap-toggle');
  const heatmapNoteEl = $('rp9-heatmap-note');
  let heatmapOn = false;

  // — Hypothèse du moment de prise de vue (jour de l'année + heure solaire) —
  let imageryDay: number = IMAGERY_SUN_DEFAULT.dayOfYear;
  let imageryHour: number = IMAGERY_SUN_DEFAULT.solarHour;

  // — Tracé en cours : null = inactif ; sinon le pied déjà posé (ou null en attente) —
  let tracing = false;
  let pendingBase: LngLat | null = null;
  let shadeCounter = 0;

  const fmtH = (h: number) => {
    const whole = Math.floor(h);
    const mins = Math.round((h - whole) * 60);
    return mins > 0 ? `${whole} h ${String(mins).padStart(2, '0')}` : `${whole} h`;
  };
  const fmt1 = (n: number) => n.toLocaleString('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

  /** Élévation solaire de l'hypothèse courante à la latitude du toit. */
  const imagerySunElevation = (): number =>
    sunDirection(ctx.centroidLat, imageryDay, imageryHour).elevationDeg;

  /** (Re)calcule la matrice de dérate + le facteur annuel depuis les ombres tracées.
   *  Horizon évalué au CENTROÏDE du tracé (documenté) ; hauteur de champ = toit 3D. */
  function recomputeFactors() {
    if (!ctx.shadeObstructions.length || ctx.vertices.length < 3) {
      ctx.shadeFactors = null;
      ctx.shadeAnnualFactor = 1;
      return;
    }
    const roofH = FLOORS * FLOOR_HEIGHT_M;
    const enu = shadeObstructionsENU(ctx.shadeObstructions, ctx.centroid, roofH);
    if (!enu.length) {
      ctx.shadeFactors = null;
      ctx.shadeAnnualFactor = 1;
      return;
    }
    ctx.shadeFactors = hourlyShadeFactors(ctx.centroidLat, enu);
    // Facteur annuel pondéré par la vraie saisonnalité : profils PVGIS si présents,
    // sinon le repli interne étiqueté (forme saisonnière plausible, même pondération).
    const prod = ctx.prodPerKwc ?? fallbackPerKwc();
    ctx.shadeAnnualFactor = annualShadeFactor(prod, ctx.shadeFactors);
  }

  /** Recalcule les hauteurs déduites (l'hypothèse de prise de vue a pu changer). */
  function recomputeHeights() {
    const elev = imagerySunElevation();
    for (const o of ctx.shadeObstructions) {
      const v = shadowVector(o.base, o.tip);
      const h = obstructionHeightFromShadow(v.lengthM, elev);
      if (h != null) o.heightM = h;
    }
  }

  function recomputeShading() {
    recomputeHeights();
    recomputeFactors();
    renderList();
    drawShadeLines();
    recalcDisplays();
    // WJ21 — le re-rendu (recalcDisplays) a recréé les instances de panneaux : ré-applique
    // la teinte d'accès solaire si la heatmap est active.
    refreshHeatmap();
  }

  // WJ21 — CARTE D'ACCÈS SOLAIRE : teinte chaque panneau par sa part RÉELLE d'irradiation
  // annuelle reçue (obstructions tracées retirées du soleil direct, diffus conservé),
  // pondérée par les vrais profils PVGIS. Astronomie pure, aucune API, aucun chiffre
  // inventé (même modèle que le dérate de production, évalué par panneau).
  function buildHeatmapColorFn(): ((cellIndex: number) => { r: number; g: number; b: number }) | null {
    const plan = ctx.layoutPlan;
    if (!plan || !plan.grid.panels.length || ctx.vertices.length < 3) return null;
    const roofH = FLOORS * FLOOR_HEIGHT_M;
    const enu = shadeObstructionsENU(ctx.shadeObstructions, ctx.centroid, roofH);
    const prod = ctx.prodPerKwc ?? fallbackPerKwc();
    const panels = plan.grid.panels;
    // Accès solaire pré-calculé par cellule (0–1). Sans obstruction → tout à 1 (plein
    // soleil uniforme) : la heatmap est alors verte partout, ce qui est honnête.
    const access: number[] = panels.map((p) =>
      enu.length ? pointSolarAccess(ctx.centroidLat, enu, prod, p.cx, p.cy) : 1,
    );
    return (cellIndex: number) => {
      const a = cellIndex >= 0 && cellIndex < access.length ? access[cellIndex] : 1;
      return solarAccessColorRGB(a);
    };
  }

  function refreshHeatmap() {
    if (!heatmapOn) return;
    applyHeatmap(buildHeatmapColorFn());
  }

  function setHeatmap(on: boolean) {
    heatmapOn = on;
    if (heatmapBtn) heatmapBtn.setAttribute('aria-pressed', String(on));
    if (heatmapNoteEl) {
      heatmapNoteEl.textContent = on
        ? 'Carte d’accès solaire : vert = plein soleil toute l’année, rouge = souvent à l’ombre (calcul astronomique, pondéré par l’irradiation réelle du lieu). Tracez des ombres voisines pour la voir varier.'
        : '';
    }
    applyHeatmap(on ? buildHeatmapColorFn() : null);
  }

  /** Ligne pointillée base→bout de chaque ombre tracée, sur la carte 2D. */
  function drawShadeLines() {
    const src = map.getSource(SHADE_SRC) as maplibregl.GeoJSONSource | undefined;
    const data = {
      type: 'FeatureCollection',
      features: ctx.shadeObstructions.map((o) => ({
        type: 'Feature',
        properties: {},
        geometry: { type: 'LineString', coordinates: [o.base, o.tip] },
      })),
    };
    if (src) {
      src.setData(data as never);
      return;
    }
    try {
      map.addSource(SHADE_SRC, { type: 'geojson', data: data as never });
      map.addLayer({
        id: SHADE_SRC,
        type: 'line',
        source: SHADE_SRC,
        paint: { 'line-color': '#8f9bb8', 'line-width': 2, 'line-dasharray': [1, 1.2] },
      });
      map.addLayer({
        id: `${SHADE_SRC}-pts`,
        type: 'circle',
        source: SHADE_SRC,
        paint: { 'circle-radius': 4, 'circle-color': '#8f9bb8', 'circle-stroke-color': '#070b1d', 'circle-stroke-width': 1.5 },
      });
    } catch {
      /* style pas encore chargé : les lignes apparaîtront au prochain redraw */
    }
  }

  function renderList() {
    if (noteEl) {
      if (!ctx.shadeObstructions.length) {
        noteEl.textContent = '';
      } else {
        const lossPct = Math.round((1 - ctx.shadeAnnualFactor) * 100);
        noteEl.textContent =
          lossPct > 0
            ? `Ombrage tracé : −${lossPct} % de production annuelle (heures masquées ramenées à la part diffuse ~25 %). Hypothèse de prise de vue affichée ci-dessus — pas une mesure.`
            : `Obstacle(s) tracé(s) sous le niveau du toit : aucune heure masquée pour ce champ.`;
      }
    }
    if (!listEl) return;
    listEl.innerHTML = '';
    ctx.shadeObstructions.forEach((o, i) => {
      const v = shadowVector(o.base, o.tip);
      const row = document.createElement('div');
      row.className = 'flex flex-wrap items-center gap-2 border border-white/10 bg-nuit-900/40 p-2 text-xs text-lune-soft';
      row.innerHTML =
        `<span class="font-semibold text-white">Ombre ${i + 1}</span>` +
        `<span>ombre ${esc(fmt1(v.lengthM))} m → hauteur estimée ~<span class="fig">${esc(fmt1(o.heightM))}</span> m</span>` +
        `<button type="button" data-shade-del="${esc(o.id)}" class="ml-auto border border-alert-300/60 px-2 py-1 font-semibold text-alert-300 hover:bg-alert-300/10">× Supprimer</button>`;
      listEl.appendChild(row);
    });
  }

  function setTracing(on: boolean) {
    tracing = on;
    pendingBase = null;
    if (addBtn) addBtn.setAttribute('aria-pressed', String(on));
    if (on) {
      setStatus('Ombre : cliquez le PIED de l’obstacle (arbre, immeuble…), puis le BOUT de son ombre sur l’image.');
    }
  }

  function handleMapClick(lngLat: LngLat): boolean {
    if (!tracing) return false;
    if (ctx.vertices.length < 3 || !ctx.closed) {
      setStatus('Tracez et fermez d’abord le toit — l’ombrage se calcule pour ce champ.');
      return true;
    }
    if (!pendingBase) {
      pendingBase = lngLat;
      setStatus('Pied posé — cliquez maintenant le BOUT de l’ombre.');
      return true;
    }
    const base = pendingBase;
    const v = shadowVector(base, lngLat);
    const h = obstructionHeightFromShadow(v.lengthM, imagerySunElevation());
    if (h == null || v.lengthM < 0.5) {
      setStatus('Ombre trop courte (ou soleil rasant) pour déduire une hauteur — re-tracez.');
      pendingBase = null;
      return true;
    }
    ctx.shadeObstructions.push({
      id: `shade-${++shadeCounter}`,
      base,
      tip: lngLat,
      heightM: h,
      halfWidthM: SHADE_OBSTRUCTION_HALF_WIDTH_M,
    });
    setTracing(false);
    recomputeShading();
    setStatus(`Obstacle ajouté : hauteur estimée ~${fmt1(h)} m (déduite de l’ombre, hypothèse de prise de vue affichée).`);
    return true;
  }

  function reset() {
    ctx.shadeObstructions.length = 0;
    ctx.shadeFactors = null;
    ctx.shadeAnnualFactor = 1;
    setTracing(false);
    renderList();
    drawShadeLines();
  }

  // — Câblage DOM (tous les nœuds optionnels) —
  addBtn?.addEventListener('click', () => setTracing(!tracing));
  clearBtn?.addEventListener('click', () => {
    reset();
    recalcDisplays();
  });
  if (hourEl) {
    hourEl.addEventListener('input', () => {
      const v = Number(hourEl.value);
      if (!Number.isFinite(v)) return;
      imageryHour = v;
      if (hourValueEl) hourValueEl.textContent = fmtH(v);
      if (ctx.shadeObstructions.length) recomputeShading();
    });
  }
  document.querySelectorAll<HTMLButtonElement>('[data-shade-season]').forEach((b) => {
    b.addEventListener('click', () => {
      const d = Number(b.dataset.shadeSeason);
      if (!Number.isFinite(d)) return;
      imageryDay = d;
      document.querySelectorAll<HTMLButtonElement>('[data-shade-season]').forEach((o) =>
        o.setAttribute('aria-pressed', String(o === b)),
      );
      if (ctx.shadeObstructions.length) recomputeShading();
    });
  });
  listEl?.addEventListener('click', (e) => {
    const del = (e.target as HTMLElement).closest<HTMLElement>('[data-shade-del]');
    if (!del?.dataset.shadeDel) return;
    const idx = ctx.shadeObstructions.findIndex((o) => o.id === del.dataset.shadeDel);
    if (idx >= 0) {
      ctx.shadeObstructions.splice(idx, 1);
      recomputeShading();
    }
  });
  // WJ21 — bascule de la carte d'accès solaire (heatmap d'irradiance).
  heatmapBtn?.addEventListener('click', () => setHeatmap(!heatmapOn));

  return { handleMapClick, recomputeShading, refreshHeatmap, reset };
}
