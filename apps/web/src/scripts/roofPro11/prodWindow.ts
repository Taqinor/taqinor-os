/**
 * W50 — fenêtre « Production estimée » (Année / Mois / Jour) : rendu, requête
 * serveur (/api/roof-production → PVGIS, jamais le client directement) et
 * synchronisation avec le plan gagnant de l'optimiseur. Extrait de
 * roof-tool-pro11.ts (split modulaire 2026-06-20) — comportement INCHANGÉ.
 *
 * GARDE-FOU : ce module n'interroge QUE /api/roof-production (estimation de
 * production) ; il ne poste AUCUN lead (ni route lead, ni route de simulation).
 */
import {
  yearSeries,
  monthSeries,
  daySeries,
  fmtKwh,
  annualSavings,
  monthlySavings,
  dailySavings,
  fmtSavings,
  sourceLabel as prodSourceLabel,
  isEstimate,
  MONTH_NAMES_FR,
  daysInMonth,
  rescaleByPanels,
} from '../../lib/productionWindow';
import { PANEL_KWC, type PerKwcProduction } from '../../lib/productionEngine';
import { occupiedCount } from '../../lib/layoutVariability';
import { type Ctx } from './context';
import { type Graphs } from './graphs';
import { type ProdConfig, type ProdPlaneKey, type ProductionApiResponse } from './types';

/** Références DOM de la fenêtre de production. */
export interface ProdWindowDom {
  prodWindowEl: HTMLElement | null;
  prodScopeWrap: HTMLElement | null;
  prodMonthPickerEl: HTMLElement | null;
  prodMonthLabelEl: HTMLElement | null;
  prodDayPickerEl: HTMLElement | null;
  prodDayLabelEl: HTMLElement | null;
  prodDayResetEl: HTMLElement | null;
  prodHeadlineEl: HTMLElement | null;
  prodSubEl: HTMLElement | null;
  prodGraphEl: HTMLElement | null;
  prodSourceEl: HTMLElement | null;
  prodSavingsEl: HTMLElement | null;
}

/** Dépendances injectées (autres modules + rendus). */
export interface ProdWindowDeps {
  graphs: Graphs;
  renderConsumption: () => void;
  renderLayoutPanel: () => void;
  snapshotActiveAreaResult: () => void;
  renderAreasPanel: () => void;
}

export interface ProdWindow {
  renderProdWindow: () => void;
  updateProductionWindow: (cfg: ProdConfig) => void;
  prodConfigFromState: () => ProdConfig | null;
  syncProductionWindow: () => void;
}

export function createProdWindow(ctx: Ctx, dom: ProdWindowDom, deps: ProdWindowDeps): ProdWindow {
  const { graphs, renderConsumption, renderLayoutPanel, snapshotActiveAreaResult, renderAreasPanel } = deps;

  const prodPlaneKeyOf = (p: ProdPlaneKey): string =>
    `${p.lat.toFixed(4)},${p.lon.toFixed(4)},${Math.round(p.tiltDeg)},${Math.round(p.aspect)},${p.mountingplace}`;

  /** Rend la fenêtre de production complète (toggle, pickers, headline, graphe, économies). */
  function renderProdWindow() {
    const { prodWindowEl, prodMonthPickerEl, prodDayPickerEl, prodScopeWrap, prodMonthLabelEl, prodDayLabelEl, prodDayResetEl, prodHeadlineEl, prodSubEl, prodGraphEl, prodSourceEl, prodSavingsEl } = dom;
    if (!prodWindowEl) return;
    const prod = ctx.prodScaled;
    if (!prod || ctx.prodPanels <= 0) {
      prodWindowEl.hidden = true;
      return;
    }
    prodWindowEl.hidden = false;
    const prodScope = ctx.prodScope;
    const prodMonth = ctx.prodMonth;
    const prodDay = ctx.prodDay;
    const prodTarget = ctx.prodTarget;
    const estimated = isEstimate(ctx.prodSource);
    const approx = estimated; // « estimé » → on préfixe « ~ »
    const tag = estimated ? ' (estimé)' : '';

    // Visibilité des pickers selon le scope.
    if (prodMonthPickerEl) prodMonthPickerEl.hidden = prodScope === 'year';
    if (prodDayPickerEl) prodDayPickerEl.hidden = prodScope !== 'day';

    // Boutons de scope : aria-pressed reflète le scope courant.
    if (prodScopeWrap) {
      prodScopeWrap.querySelectorAll<HTMLButtonElement>('[data-prod-scope]').forEach((b) => {
        b.setAttribute('aria-pressed', String(b.dataset.prodScope === prodScope));
      });
    }

    // Libellés des pickers.
    if (prodMonthLabelEl) prodMonthLabelEl.textContent = MONTH_NAMES_FR[prodMonth];
    if (prodDayLabelEl) {
      prodDayLabelEl.textContent =
        prodDay == null ? `jour type · ${MONTH_NAMES_FR[prodMonth]}` : `${prodDay} ${MONTH_NAMES_FR[prodMonth]}`;
    }
    if (prodDayResetEl) prodDayResetEl.hidden = prodDay == null;

    let headline = '';
    let sub = '';
    let graph = '';
    let savingsTxt = '';

    if (prodScope === 'year') {
      const { totalKwh } = yearSeries(prod);
      headline = `${fmtKwh(totalKwh, approx)}/an${tag}`;
      sub = 'Production annuelle estimée · 12 mois';
      graph = graphs.renderYearGraph(prod);
      const s = annualSavings(totalKwh, prodTarget);
      savingsTxt = prodTarget > 0 ? `Économies estimées (plafonnées) : ${fmtSavings(s.low, s.high)}/an` : '';
    } else if (prodScope === 'month') {
      const { totalKwh } = monthSeries(prod, prodMonth);
      headline = `${fmtKwh(totalKwh, approx)}${tag}`;
      sub = `Production de ${MONTH_NAMES_FR[prodMonth]} · ${daysInMonth(prodMonth)} jours`;
      graph = graphs.renderMonthGraph(prod);
      const s = monthlySavings(totalKwh, prodTarget);
      savingsTxt = prodTarget > 0 ? `Économies estimées (plafonnées) : ${fmtSavings(s.low, s.high)}/mois` : '';
    } else {
      const { totalKwh, isTypical } = daySeries(prod, prodMonth, ctx.prodSpecificDate);
      headline = `${fmtKwh(totalKwh, approx)}${tag}`;
      const dayTxt = prodDay == null ? `jour type de ${MONTH_NAMES_FR[prodMonth]}` : `${prodDay} ${MONTH_NAMES_FR[prodMonth]}`;
      sub = `Courbe horaire · ${dayTxt}${isTypical ? ' (moyenne du mois)' : ''}`;
      graph = graphs.renderDayGraph(prod);
      const s = dailySavings(totalKwh, prodTarget);
      savingsTxt = prodTarget > 0 ? `Économies estimées (plafonnées) : ${fmtSavings(s.low, s.high)}/jour` : '';
    }

    if (prodHeadlineEl) prodHeadlineEl.textContent = headline;
    if (prodSubEl) prodSubEl.textContent = sub;
    if (prodGraphEl) prodGraphEl.innerHTML = graph;
    if (prodSourceEl) prodSourceEl.textContent = `Source : ${prodSourceLabel(ctx.prodSource)}`;
    if (prodSavingsEl) prodSavingsEl.textContent = savingsTxt;
    // W68 — la fenêtre « Affiner ma consommation » suit le même plan/production.
    renderConsumption();
  }

  /**
   * Met à jour la fenêtre de production pour le plan courant. Si le PLAN (GPS/inclinaison/
   * azimut/pose) a changé, on interroge /api/roof-production (serveur → PVGIS, jamais le
   * client directement). Si seul le NOMBRE de panneaux change (même plan), on RESCALE côté
   * client (linéaire en kWc) sans appel serveur. La date précise sélectionnée est
   * re-demandée au serveur (la silhouette inter-années ne se rescale pas en pur kWc côté
   * client sans la série horaire — on la garde donc serveur-side, rescalée par le serveur).
   */
  function updateProductionWindow(cfg: ProdConfig) {
    if (!dom.prodWindowEl) return;
    ctx.prodPanels = Math.max(0, Math.round(cfg.panels));
    ctx.prodTarget = Math.max(0, cfg.target);
    if (ctx.prodPanels <= 0) {
      ctx.prodScaled = null;
      ctx.prodPerKwc = null;
      renderProdWindow();
      return;
    }
    const planKey = prodPlaneKeyOf(cfg);
    const planeChanged = planKey !== ctx.prodPlaneKey;
    const dateChanged = ctx.prodScope === 'day' && ctx.prodDay != null;

    // Plan inchangé ET pas de date à (re)charger → rescale CLIENT pur (zéro appel serveur).
    if (!planeChanged && !dateChanged && ctx.prodPerKwc) {
      ctx.prodScaled = rescaleByPanels(ctx.prodPerKwc, ctx.prodPanels, PANEL_KWC);
      renderProdWindow();
      return;
    }

    const token = ++ctx.prodToken;
    const wantDay = ctx.prodScope === 'day' && ctx.prodDay != null;
    const dayMonth = ctx.prodMonth + 1; // l'API attend 1-based
    void fetch('/api/roof-production', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        lat: cfg.lat,
        lon: cfg.lon,
        tiltDeg: cfg.tiltDeg,
        aspect: cfg.aspect,
        mountingplace: cfg.mountingplace,
        placedPanels: ctx.prodPanels,
        ...(wantDay ? { dateMonth: dayMonth, dateDay: ctx.prodDay } : {}),
      }),
    })
      .then((r) => r.json())
      .then((data: ProductionApiResponse) => {
        if (token !== ctx.prodToken) return; // une requête plus récente a pris la main
        if (!data || data.ok !== true) return;
        // On reconstitue la production PAR 1 kWc (pour rescaler ensuite côté client) en
        // divisant la réponse mise à l'échelle par le kWc posé renvoyé.
        const placedKwc = typeof data.placedKwc === 'number' && data.placedKwc > 0 ? data.placedKwc : ctx.prodPanels * PANEL_KWC;
        ctx.prodPerKwc = perKwcFromResponse(data, placedKwc);
        ctx.prodScaled = {
          source: data.source,
          placedKwc,
          annualKwh: data.annualKwh,
          monthlyKwh: data.monthlyKwh,
          typicalDayByMonth: data.typicalDayByMonth,
          dailyKwhByMonth: data.dailyKwhByMonth,
        };
        ctx.prodSource = data.source;
        ctx.prodPlaneKey = planKey;
        ctx.prodSpecificDate = data.specificDate ?? null;
        renderProdWindow();
      })
      .catch(() => {
        /* réseau indisponible : on garde l'affichage précédent (repli gracieux) */
      });
  }

  /** Reconstitue une production PAR 1 kWc à partir d'une réponse mise à l'échelle. */
  function perKwcFromResponse(data: ProductionApiResponse, placedKwc: number): PerKwcProduction {
    const inv = placedKwc > 0 ? 1 / placedKwc : 0;
    return {
      source: data.source,
      annualKwh: data.annualKwh * inv,
      monthlyKwh: data.monthlyKwh.map((v) => v * inv),
      typicalDayByMonth: data.typicalDayByMonth.map((prof) => prof.map((v) => v * inv)),
      dailyKwhByMonth: data.dailyKwhByMonth.map((v) => v * inv),
    };
  }

  /** Déduit la config de production du winner de l'optimiseur courant (plat ou pente). */
  function prodConfigFromState(): ProdConfig | null {
    if (!ctx.closed || ctx.vertices.length < 3) return null;
    const centroid = ctx.centroid;
    if (ctx.roofType === 'pitched') {
      const res = ctx.pitchedLiveResult;
      if (!res || res.northFacing) return null;
      const w = res.winner;
      if (w.placedCount <= 0) return null;
      return {
        lat: centroid[1],
        lon: centroid[0],
        tiltDeg: res.pitchDeg,
        aspect: res.facingAzimuthDeg - 180, // jambe sud : aspect = azimut − 180
        mountingplace: 'building',
        panels: w.placedCount,
        target: res.target,
      };
    }
    const res = ctx.liveResult;
    if (!res) return null;
    const w = res.winner;
    if (w.placedCount <= 0) return null;
    return {
      lat: centroid[1],
      lon: centroid[0],
      tiltDeg: w.tiltDeg,
      aspect: w.aspect,
      mountingplace: 'free', // toit plat racké
      panels: w.placedCount,
      target: res.target,
    };
  }

  /** Synchronise la fenêtre de production avec l'état courant (appelée après chaque rendu). */
  function syncProductionWindow() {
    if (!dom.prodWindowEl) {
      // Même sans la fenêtre de production, on garde l'instantané de zone + le total à jour.
      snapshotActiveAreaResult();
      renderAreasPanel();
      return;
    }
    const cfg = prodConfigFromState();
    if (!cfg) {
      ctx.prodScaled = null;
      ctx.prodPerKwc = null;
      ctx.prodPanels = 0;
      renderProdWindow();
      renderLayoutPanel();
      snapshotActiveAreaResult();
      renderAreasPanel();
      return;
    }
    // W69 — en mode disposition personnalisée, le NOMBRE posé vient de l'occupation
    // éditée (pas de l'optimiseur) ; le plan (GPS/tilt/azimut) reste celui du gagnant.
    if (ctx.layoutMode && ctx.layoutState) {
      updateProductionWindow({ ...cfg, panels: occupiedCount(ctx.layoutState) });
    } else {
      updateProductionWindow(cfg);
    }
    renderLayoutPanel();
    // « Plusieurs zones » — APRÈS chaque recompute/rendu de la zone active, on écrit son
    // résultat courant (gagnant vivant) dans l'enregistrement de la zone active, puis on
    // rafraîchit le total. Hook unique partagé par les optimiseurs plat ET pente.
    snapshotActiveAreaResult();
    renderAreasPanel();
  }

  return { renderProdWindow, updateProductionWindow, prodConfigFromState, syncProductionWindow };
}
