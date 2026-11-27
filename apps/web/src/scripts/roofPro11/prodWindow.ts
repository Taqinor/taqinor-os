/**
 * W50 — fenêtre « Production estimée » (Année / Mois / Jour) : rendu, requête
 * serveur (/api/roof-production → PVGIS, jamais le client directement) et
 * synchronisation avec le plan gagnant de l'optimiseur. Extrait de
 * roof-tool-pro11.ts (split modulaire 2026-06-20) — comportement INCHANGÉ.
 *
 * GARDE-FOU : ce module n'interroge QUE /api/roof-production (estimation de
 * production) ; il ne poste AUCUN lead (ni route lead, ni route de simulation).
 *
 * PV75 — couche d'AFFICHAGE bancable (P50/P90 + ratio de performance + cascade des
 * pertes) optionnelle, en pur AJOUT sous le chiffre de tête : lue depuis
 * `ctx.opts.bankable` (jamais calculée/appelée ici — la page hôte l'injecte au boot
 * après l'avoir lue elle-même sur le devis). Absent → rendu strictement inchangé.
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
import { PANEL_KWC, type PerKwcProduction, type ScaledProduction, type SpecificDateProfile } from '../../lib/productionEngine';
import { facteurDerateAnnuel } from './optimizer'; // lot 10 — LE dérate de la carte de la pose
import { clipDcAcKwh, effectiveDcAcRatio, type ConfigFamily } from '../../lib/estimatorBrainV2';
import { catalogueAvecModulesDuDocument, estRefus, kwcDuPan, lireModulesDisponibles, resoudreModuleDuPan } from './moduleSelect'; // demande croisée
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

/** Aspect PVGIS ramené dans [−180 ; 180[ (ce que `/api/roof-production` accepte). */
const aspectBorne = (a: number): number => ((((a + 180) % 360) + 360) % 360) - 180;

/**
 * ACAL982 (revue) — les plans PVGIS d'une pose et leur poids, la règle de la CARTE (`estimatorBrainV7.ts::evalOne`,
 * `optimizer.ts::legsFor`) : un plan Sud/pente = une jambe ; une pose est-ouest = deux jambes `aspect − 90` (est) et
 * `aspect + 90` (ouest), la moitié du kWc chacune. Avant : UN plan à `aspect` (le faîte, donc le sud) pour l'est-ouest.
 */
export function jambesDeProduction(cfg: { aspect: number; family?: ConfigFamily }): { aspect: number; poids: number }[] {
  if (cfg.family !== 'eastwest') return [{ aspect: cfg.aspect, poids: 1 }];
  return [{ aspect: aspectBorne(cfg.aspect - 90), poids: 0.5 }, { aspect: aspectBorne(cfg.aspect + 90), poids: 0.5 }];
}

/** ACAL982 (revue) — l'écrêtage DC/AC de la famille que la carte applique au kWh PVGIS (W94, `renderLiveWinner`) :
 *  1 pour un Sud/une pente (ratio de conception), < 1 pour une « tente » est-ouest. Linéaire : `clip(x) = x × facteur`. */
export function facteurEcretageFamille(family: ConfigFamily | undefined): number {
  return family ? clipDcAcKwh(1, effectiveDcAcRatio(family)) : 1;
}

const SOURCE_RANG: Record<PerKwcProduction['source'], number> = { pvgis: 0, 'pvgis-monthly': 1, estimate: 2 };

/** ACAL982 (revue) — UNE production par kWc depuis les jambes : moyenne pondérée série par série (année, mois, jour
 *  type, journalier) puis écrêtage de la famille ; la source est la moins sûre des jambes. Une jambe à 1 = elle-même. */
export function combinerJambes(parts: { perKwc: PerKwcProduction; poids: number }[], facteur = 1): PerKwcProduction {
  const somme = (lire: (p: PerKwcProduction) => number): number => parts.reduce((s, j) => s + j.poids * lire(j.perKwc), 0) * facteur;
  const premier = parts[0].perKwc;
  return {
    source: parts.reduce<PerKwcProduction['source']>((s, j) => (SOURCE_RANG[j.perKwc.source] > SOURCE_RANG[s] ? j.perKwc.source : s), premier.source),
    annualKwh: somme((p) => p.annualKwh),
    monthlyKwh: premier.monthlyKwh.map((_, m) => somme((p) => p.monthlyKwh[m] ?? 0)),
    typicalDayByMonth: premier.typicalDayByMonth.map((prof, m) => prof.map((_, h) => somme((p) => p.typicalDayByMonth[m]?.[h] ?? 0))),
    dailyKwhByMonth: premier.dailyKwhByMonth.map((_, m) => somme((p) => p.dailyKwhByMonth[m] ?? 0)),
  };
}

/** ACAL982 (revue) — jumeau ERP : l'option `productionAtelier` interrogée PAR JAMBE (même `cfg`, l'aspect de la jambe),
 *  puis la même combinaison. Plan Sud/pente : `fournir(cfg)` tel quel. Une jambe sans production ⇒ null. */
export function productionAtelierDesJambes(
  fournir: (cfg: ProdConfig) => PerKwcProduction | null,
  cfg: ProdConfig,
): PerKwcProduction | null {
  const jambes = jambesDeProduction(cfg);
  const facteur = facteurEcretageFamille(cfg.family);
  if (jambes.length === 1 && facteur === 1) return fournir(cfg);
  const parts = jambes.map((j) => ({ perKwc: fournir({ ...cfg, aspect: j.aspect }), poids: j.poids }));
  return parts.every((p) => p.perKwc) ? combinerJambes(parts as { perKwc: PerKwcProduction; poids: number }[], facteur) : null;
}

/** Même règle pour le profil d'une date précise (déjà mis à l'échelle par la route) ; une jambe sans profil ⇒ null. */
function combinerDates(dates: (SpecificDateProfile | null | undefined)[], poids: number[], facteur: number): SpecificDateProfile | null {
  if (!dates.length || dates.some((d) => !d)) return null;
  const ds = dates as SpecificDateProfile[];
  const somme = (lire: (d: SpecificDateProfile) => number): number => ds.reduce((s, d, i) => s + poids[i] * lire(d), 0) * facteur;
  return {
    month: ds[0].month,
    day: ds[0].day,
    hourlyKw: ds[0].hourlyKw.map((_, h) => somme((d) => d.hourlyKw[h] ?? 0)),
    dailyKwh: somme((d) => d.dailyKwh),
    yearsAveraged: Math.min(...ds.map((d) => d.yearsAveraged)),
  };
}

/** Lot 10 (production-un-chiffre) — la production AFFICHÉE par la fenêtre : la série posée × `f`, LE dérate
 *  annuel de la carte de la pose (`optimizer.ts::facteurDerateAnnuel`, ombrage tracé × horizon). `f` = 1 ⇒ la
 *  série telle quelle. Pur : `ctx.prodScaled` (lu par la conso) n'est jamais modifié. */
export function productionAffichee<T extends PerKwcProduction>(prod: T, f: number): T {
  if (f === 1) return prod;
  return {
    ...prod,
    annualKwh: prod.annualKwh * f,
    monthlyKwh: prod.monthlyKwh.map((v) => v * f),
    typicalDayByMonth: prod.typicalDayByMonth.map((jour) => jour.map((v) => v * f)),
    dailyKwhByMonth: prod.dailyKwhByMonth.map((v) => v * f),
  };
}

/** Même dérate pour le profil d'une date précise (jour choisi de la fenêtre). */
function dateAffichee(d: SpecificDateProfile | null, f: number): SpecificDateProfile | null {
  return d && f !== 1 ? { ...d, hourlyKw: d.hourlyKw.map((v) => v * f), dailyKwh: d.dailyKwh * f } : d;
}

export function createProdWindow(ctx: Ctx, dom: ProdWindowDom, deps: ProdWindowDeps): ProdWindow {
  const { graphs, renderConsumption, renderLayoutPanel, snapshotActiveAreaResult, renderAreasPanel } = deps;

  /** Demande croisée — kWc d'UN panneau : le module DÉSIGNÉ du pan actif, même résolution que le bandeau (layoutEditor,
   *  ACAL1520) ; sans choix ou sans puissance renseignée : le défaut de l'atelier (720 W). */
  const kwcParPanneau = (): number => {
    const m = resoudreModuleDuPan(catalogueAvecModulesDuDocument(lireModulesDisponibles(ctx.opts?.modulesDisponibles).choisissables, ctx.modulesDuDocument).catalogue, ctx.activeArea?.()?.moduleId);
    return (!estRefus(m) && kwcDuPan(1, m)) || PANEL_KWC;
  };

  const prodPlaneKeyOf = (p: ProdPlaneKey): string =>
    `${p.lat.toFixed(4)},${p.lon.toFixed(4)},${Math.round(p.tiltDeg)},${Math.round(p.aspect)},${p.mountingplace}${p.family ? `,${p.family}` : ''}`; // ACAL982 (revue) — la famille change les jambes

  // PV75 — éléments DYNAMIQUES (ligne P50/P90 + mini cascade des pertes), créés
  // UNIQUEMENT si `ctx.opts.bankable` est fourni par la page hôte. Zéro modification
  // du DOM astro (`toiture-3d-pro-11.astro`) : quand `bankable` est absent, ces
  // éléments ne sont jamais créés → rendu de la fenêtre STRICTEMENT INCHANGÉ (golden).
  let bankableLineEl: HTMLElement | null = null;
  let lossCascadeEl: HTMLElement | null = null;

  /** Crée (une seule fois, paresseusement) les deux éléments bancables, insérés
   *  juste après le chiffre de tête et juste après le graphe. Idempotent. */
  function ensureBankableEls(): void {
    const { prodHeadlineEl, prodGraphEl } = dom;
    if (!bankableLineEl && prodHeadlineEl) {
      bankableLineEl = document.createElement('p');
      bankableLineEl.className = 'mt-1 text-xs text-lune-faint';
      bankableLineEl.dataset.prodBankable = 'true';
      prodHeadlineEl.insertAdjacentElement('afterend', bankableLineEl);
    }
    const graphWrap = prodGraphEl?.parentElement ?? null;
    if (!lossCascadeEl && graphWrap) {
      lossCascadeEl = document.createElement('div');
      lossCascadeEl.className = 'mt-2';
      lossCascadeEl.dataset.prodLossCascade = 'true';
      graphWrap.insertAdjacentElement('afterend', lossCascadeEl);
    }
  }

  /** Rend la ligne compacte « ~P50 kWh/an (P50) · P90 … · PR … » + la mini cascade
   *  des pertes, SEULEMENT si la page hôte a fourni un payload bancable (PV75). Ces
   *  chiffres sont ANNUELS (étude bancable) — affichés indépendamment du scope
   *  année/mois/jour de la fenêtre, en complément du chiffre de tête scopé. */
  function renderBankable(): void {
    const bankable = ctx.opts.bankable;
    if (!bankable) return;
    ensureBankableEls();
    if (bankableLineEl) {
      const pr = Number.isFinite(bankable.performance_ratio) ? bankable.performance_ratio : 0;
      bankableLineEl.textContent =
        `${fmtKwh(bankable.p50_kwh, true)}/an (P50) · P90 ${fmtKwh(bankable.p90_kwh)} · PR ${Math.round(pr * 100)} %`;
    }
    if (lossCascadeEl) {
      lossCascadeEl.innerHTML = graphs.renderLossCascade(bankable.loss_breakdown || {});
    }
  }

  /** Rend la fenêtre de production complète (toggle, pickers, headline, graphe, économies). */
  function renderProdWindow() {
    const { prodWindowEl, prodMonthPickerEl, prodDayPickerEl, prodScopeWrap, prodMonthLabelEl, prodDayLabelEl, prodDayResetEl, prodHeadlineEl, prodSubEl, prodGraphEl, prodSourceEl, prodSavingsEl } = dom;
    if (!prodWindowEl) return;
    if (!ctx.prodScaled || ctx.prodPanels <= 0) {
      prodWindowEl.hidden = true;
      return;
    }
    // Lot 10 — un chiffre par pose : la fenêtre dit la production de la carte (même dérate ombrage × horizon).
    const derate = facteurDerateAnnuel(ctx);
    const prod: ScaledProduction = productionAffichee(ctx.prodScaled, derate);
    const date = dateAffichee(ctx.prodSpecificDate, derate);
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
      const { totalKwh, isTypical } = daySeries(prod, prodMonth, date);
      headline = `${fmtKwh(totalKwh, approx)}${tag}`;
      const dayTxt = prodDay == null ? `jour type de ${MONTH_NAMES_FR[prodMonth]}` : `${prodDay} ${MONTH_NAMES_FR[prodMonth]}`;
      sub = `Courbe horaire · ${dayTxt}${isTypical ? ' (moyenne du mois)' : ''}`;
      graph = graphs.renderDayGraph(prod, date);
      const s = dailySavings(totalKwh, prodTarget);
      savingsTxt = prodTarget > 0 ? `Économies estimées (plafonnées) : ${fmtSavings(s.low, s.high)}/jour` : '';
    }

    if (prodHeadlineEl) prodHeadlineEl.textContent = headline;
    if (prodSubEl) prodSubEl.textContent = sub;
    if (prodGraphEl) prodGraphEl.innerHTML = graph;
    if (prodSourceEl) prodSourceEl.textContent = `Source : ${prodSourceLabel(ctx.prodSource)}`;
    if (prodSavingsEl) prodSavingsEl.textContent = savingsTxt;
    // PV75 — P50/P90/PR + cascade des pertes, SEULEMENT si la page hôte a injecté un
    // payload bancable. Aucun appel réseau ici : lecture pure de `ctx.opts.bankable`.
    renderBankable();
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
      ctx.prodScaled = rescaleByPanels(ctx.prodPerKwc, ctx.prodPanels, kwcParPanneau());
      renderProdWindow();
      return;
    }

    const token = ++ctx.prodToken;
    const wantDay = ctx.prodScope === 'day' && ctx.prodDay != null;
    const dayMonth = ctx.prodMonth + 1; // l'API attend 1-based
    // ACAL982 (revue) — une requête PAR JAMBE (est-ouest : `aspect ∓ 90`), comme la carte ; un plan Sud/pente = une.
    const jambes = jambesDeProduction(cfg);
    const facteur = facteurEcretageFamille(cfg.family);
    const lireJambe = (aspect: number): Promise<ProductionApiResponse> =>
      fetch('/api/roof-production', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          lat: cfg.lat,
          lon: cfg.lon,
          tiltDeg: cfg.tiltDeg,
          aspect,
          mountingplace: cfg.mountingplace,
          placedPanels: ctx.prodPanels,
          ...(wantDay ? { dateMonth: dayMonth, dateDay: ctx.prodDay } : {}),
        }),
      }).then((r) => r.json());
    const placedKwcDe = (d: ProductionApiResponse): number =>
      typeof d.placedKwc === 'number' && d.placedKwc > 0 ? d.placedKwc : ctx.prodPanels * PANEL_KWC;
    void Promise.all(jambes.map((j) => lireJambe(j.aspect)))
      .then((reponses: ProductionApiResponse[]) => {
        if (token !== ctx.prodToken) return; // une requête plus récente a pris la main
        if (reponses.some((d) => !d || d.ok !== true)) return;
        const data = reponses[0];
        // On reconstitue la production PAR 1 kWc (pour rescaler ensuite côté client) en
        // divisant la réponse mise à l'échelle par le kWc posé renvoyé.
        const placedKwc = placedKwcDe(data);
        if (reponses.length === 1 && facteur === 1) {
          ctx.prodPerKwc = perKwcFromResponse(data, placedKwc);
          ctx.prodScaled = {
            source: data.source,
            placedKwc,
            annualKwh: data.annualKwh,
            monthlyKwh: data.monthlyKwh,
            typicalDayByMonth: data.typicalDayByMonth,
            dailyKwhByMonth: data.dailyKwhByMonth,
          };
          // Demande croisée — la route met à l'échelle à 720 W/panneau ; un module désigné d'une autre puissance est rescalé.
          if (kwcParPanneau() !== PANEL_KWC) ctx.prodScaled = rescaleByPanels(ctx.prodPerKwc, ctx.prodPanels, kwcParPanneau());
          ctx.prodSpecificDate = data.specificDate ?? null;
        } else {
          // ACAL982 (revue) — jambes moyennées à leurs poids réels puis écrêtées comme la carte : UNE valeur, UNE source.
          ctx.prodPerKwc = combinerJambes(reponses.map((d, i) => ({ perKwc: perKwcFromResponse(d, placedKwcDe(d)), poids: jambes[i].poids })), facteur);
          ctx.prodScaled = rescaleByPanels(ctx.prodPerKwc, ctx.prodPanels, kwcParPanneau());
          ctx.prodSpecificDate = combinerDates(reponses.map((d) => d.specificDate), jambes.map((j) => j.poids), facteur);
        }
        ctx.prodSource = ctx.prodPerKwc.source;
        ctx.prodPlaneKey = planKey;
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
      aspect: w.aspect, // est-ouest : l'aspect du FAÎTE (az − 90) ; les jambes viennent de `jambesDeProduction`
      family: w.family, // ACAL982 (revue)
      mountingplace: 'free', // toit plat racké
      panels: w.placedCount,
      target: res.target,
    };
  }

  /**
   * ERR-ACAL311-PANNEAU-ABSENT-ERP — page hôte SANS fenêtre de production ni route
   * /api/roof-production (l'atelier ERP) : la production du plan courant vient de l'option
   * INJECTÉE `ctx.opts.productionAtelier(cfg)` (production PAR 1 kWc, aucune requête), puis
   * est rescalée au nombre posé — c'est ce plan qui fait apparaître « Affiner ma
   * consommation ». Option absente (pages publiques) ⇒ no-op, comportement inchangé.
   */
  function syncProductionSansFenetre() {
    const fournir = ctx.opts?.productionAtelier;
    if (typeof fournir !== 'function') return;
    const cfg = prodConfigFromState();
    // W69 — même règle que la fenêtre : en disposition personnalisée, le nombre posé édité.
    const panels = !cfg ? 0 : ctx.layoutMode && ctx.layoutState ? occupiedCount(ctx.layoutState) : cfg.panels;
    const perKwc = cfg && panels > 0 ? productionAtelierDesJambes(fournir, cfg) : null;
    ctx.prodPanels = perKwc ? Math.max(0, Math.round(panels)) : 0;
    ctx.prodTarget = cfg ? Math.max(0, cfg.target) : 0;
    ctx.prodPerKwc = perKwc;
    ctx.prodScaled = perKwc ? rescaleByPanels(perKwc, ctx.prodPanels, kwcParPanneau()) : null;
    if (perKwc) ctx.prodSource = perKwc.source;
    renderConsumption();
  }

  /** Synchronise la fenêtre de production avec l'état courant (appelée après chaque rendu). */
  function syncProductionWindow() {
    if (!dom.prodWindowEl) {
      syncProductionSansFenetre();
      // Même sans la fenêtre de production, on garde l'instantané de zone + le total à jour.
      renderLayoutPanel();
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
