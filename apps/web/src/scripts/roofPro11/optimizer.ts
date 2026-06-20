/**
 * Moteur d'optimisation VIVANTE du builder pro-11 (toit plat W34/cerveau V7 +
 * toit en pente W35/cerveau V8 + matrice V6). Extrait de roof-tool-pro11.ts
 * (split modulaire 2026-06-20) — comportement INCHANGÉ, octet pour octet.
 *
 * Contient : la résolution contrainte vivante (`liveResolveFlat`/
 * `liveResolvePitched`), le rendu du gagnant (`renderLiveWinner`/
 * `renderPitchedWinner`/`renderConfig`/`renderPitched`), les badges/puces/
 * comparatifs (`updateLiveBadges`/`updatePitchedBadges`/`syncPitchedChips`/
 * `paintPitchedComparison`), les contrôles (`syncNeedControl`/`syncTiltControl`),
 * la carte de résultat (`paintCard`/`paintMaxLine`), les adaptateurs flush
 * (`flushToPack`/`flushGridToPanelGrid`), les verrous (`buildFlatLocks`/
 * `buildPitchedLocks`/`resetFlatLocks`/`resetPitchedLocks`), la matrice PVGIS
 * (`buildMatrix`/`computeMatrixPvgis`) et tous les accès PVGIS (caches +
 * `fetchPvgis`/`v4SpecificYield`/`pitchedSpecificYield`/`ensurePvgisForLockedTilt`/
 * `refinePitchedPvgis`).
 *
 * L'orchestration `recompute()`/`recalc()`/`close()` + le câblage des événements
 * DOM RESTENT dans l'entrée et appellent ces fonctions via l'objet renvoyé.
 * L'état partagé (sélection/verrous/affinages PVGIS/caches) passe par `ctx`.
 */
import {
  packConfig,
  productionKwh,
  billToAnnualKwh,
  annualSavingsMad,
  neededPanelsForTarget,
  roofDominantAzimuthDeg,
  tariffForCity,
  type PackResult,
  type PanelGrid,
  type ConfigFamily,
} from '../../lib/estimatorBrainV2';
import { PERIMETER_SETBACK_M, PANEL2_LONG_M, PANEL2_SHORT_M } from '../../lib/roofPro2';
import {
  recommendPitched,
  type FlushPack,
  type FlushGrid,
  type RoofPlane,
} from '../../lib/estimatorBrainV3';
import { pitchedPlaneLeg } from '../../lib/estimatorBrainV5';
import {
  fineGridMatrixV6,
  pvgisCoarsePairs,
  pvgisMatrixCandidatePairs,
  pvgisRefinePairs,
} from '../../lib/estimatorBrainV6';
import {
  solveLive,
  type AxisLocks,
  type LayoutAxis,
  type LiveConfigEval,
  type LiveSolveResult,
} from '../../lib/estimatorBrainV7';
import {
  solveLivePitched,
  type PitchedLiveResult,
  type PitchedLayoutAxis,
  type PitchedMarginAxis,
} from '../../lib/estimatorBrainV8';
import { type LngLat } from '../../lib/roof';
import { $, fmt, fmtMad } from './dom';
import { type CardData, type RenderConfigOpts } from './types';
import { type Ctx } from './context';

/** Dépendances injectées (rendu 3D + matrice + fenêtres + entrée). Les fonctions
 *  déclarées plus tard dans l'entrée sont passées en wrappers paresseux pour éviter
 *  les TDZ ; les modules frères sont passés directement. */
export interface OptimizerDeps {
  /** Rendu 3D d'une config (scene3d). */
  renderScene: (
    pack: PackResult,
    grid: PanelGrid,
    tiltDeg: number,
    family: ConfigFamily,
    maxCount: number,
    flush?: boolean,
    occupiedSet?: Set<number>,
  ) => void;
  /** Repeint le tableau matrice (toit plat) — module matrix. */
  paintComparison: () => void;
  /** Surligne la ligne gagnante (ou null) du tableau comparatif — module matrix. */
  highlightRow: (id: string | null) => void;
  /** Reflète le plan gagnant dans la fenêtre de production — module prodWindow. */
  syncProductionWindow: () => void;
  /** Pré-remplit le diagnostic depuis la carte de résultat — module prefill. */
  prefillLead: (d: CardData) => void;
  /** Met à jour l'état pressé des puces de config — entrée. */
  syncChips: () => void;
  /** Repeint la carte « Optimum calculé » depuis la matrice — entrée. */
  renderMatrixOptimumCard: () => void;
  /** Facture mensuelle (MAD) saisie — entrée. */
  monthlyBill: () => number;
  /** Anneaux lng/lat des obstacles (zones d'exclusion) — entrée. */
  obstructionRings: () => LngLat[][];
  /** Affiche un message dans le bandeau de statut — entrée. */
  setStatus: (msg: string) => void;
}

export interface Optimizer {
  /** Cœur W34 : re-résolution CONTRAINTE vivante (toit plat) + rendu + badges. */
  liveResolveFlat: () => void;
  /** Cœur W35 : re-résolution CONTRAINTE vivante (toit en pente) + rendu + badges. */
  liveResolvePitched: () => void;
  /** Alias historique → liveResolveFlat (toit plat). */
  renderSelection: () => void;
  /** Rendu UNIFIÉ d'une config toit plat (carte + 3D + contrôles). */
  renderConfig: (o: RenderConfigOpts) => void;
  /** Recalcul/rendu de l'optimiseur en pente (recommandation + vivant + PVGIS). */
  pitchedRecompute: () => void;
  /** « Réinitialiser » (toit plat) : relâche tous les verrous → optimum global. */
  resetFlatLocks: () => void;
  /** « Réinitialiser » (toit en pente) : relâche pose/marge → optimum global. */
  resetPitchedLocks: () => void;
  /** Construit la matrice V6 (estimé) + repeint + re-résout — appelée par computeMatrixPvgis. */
  buildMatrix: (ring: LngLat[], bill: number) => void;
  /** Affine la matrice au PVGIS exact (coarse-then-fine) — appelée par recompute. */
  computeMatrixPvgis: () => Promise<void>;
  /** Plafonne le besoin (1–400, arrondi) — partagé avec l'entrée. */
  clampNeeded: (n: number) => number;
}

export function createOptimizer(ctx: Ctx, deps: OptimizerDeps): Optimizer {
  const {
    renderScene,
    paintComparison,
    highlightRow,
    syncProductionWindow,
    prefillLead,
    syncChips,
    renderMatrixOptimumCard,
    monthlyBill,
    obstructionRings,
    setStatus,
  } = deps;

  // — DOM propre à l'optimiseur (mêmes nœuds que l'entrée ; getElementById idempotent) —
  const needInputEl = $<HTMLInputElement>('rp9-need-input');
  const needMinusEl = $<HTMLButtonElement>('rp9-need-minus');
  const needPlusEl = $<HTMLButtonElement>('rp9-need-plus');
  const needNoteEl = $('rp9-need-note');
  const tiltRangeEl = $<HTMLInputElement>('rp9-tilt-range');
  const tiltValueEl = $('rp9-tilt-value');
  const tiltRecoBtn = $<HTMLButtonElement>('rp9-tilt-reco');
  const azimuthGroup = $('rp9-azimuth-group');
  const optimumNoteEl = $('rp9-optimum-note');
  const pitchValueEl = $('rp9-pitch-value');
  const pitchedNoteEl = $('rp9-pitched-note');

  // — Affinage PVGIS : clés de cache + jetons/timer anti-course (internes) —
  const pvgisKey = (family: ConfigFamily, tiltDeg: number, azimuthDeg: number): string =>
    `${ctx.centroid[1].toFixed(5)},${ctx.centroid[0].toFixed(5)}|${family}|${tiltDeg}|${Math.round(azimuthDeg)}`;
  const v4Key = (tiltDeg: number, aspect: number): string => `${Math.round(tiltDeg)}|${Math.round(aspect * 10) / 10}`;
  const pitchedKey = (pitch: number, facing: number): string => `${Math.round(pitch)}|${Math.round(facing)}`;
  let matrixToken = 0;
  let liveToken = 0;
  let liveTiltTimer: ReturnType<typeof setTimeout> | null = null;
  let pitchedToken = 0;

  // W1 — Aspect PVGIS (écart au sud) d'une famille selon son azimut de face réel :
  // Sud → azimut−180 ; E-O → azimut−90.
  const aspectForLeg = (family: ConfigFamily, azimuthDeg: number): number =>
    family === 'eastwest' ? azimuthDeg - 90 : azimuthDeg - 180;

  // — Plafond « panneaux nécessaires » (Change A) —
  const clampNeeded = (n: number): number => Math.max(1, Math.min(400, Math.round(n)));
  /** Posés = min(plafond besoin, ce qui tient). Sans facture (besoin 0) il n'y a
   *  pas de besoin à plafonner → on montre ce qui tient (comportement historique). */
  const placedFor = (grid: PanelGrid): number =>
    ctx.neededPanels > 0 ? Math.max(0, Math.min(ctx.neededPanels, grid.count)) : grid.count;

  /** Synchronise le contrôle éditable + sa note honnête (besoin vs ce qui tient). */
  function syncNeedControl(fitCount: number, familyLabel: string) {
    const active = ctx.neededPanels > 0;
    if (needInputEl) {
      needInputEl.disabled = !active;
      if (document.activeElement !== needInputEl) needInputEl.value = active ? fmt(ctx.neededPanels) : '—';
    }
    if (needMinusEl) needMinusEl.disabled = !active || ctx.neededPanels <= 1;
    if (needPlusEl) needPlusEl.disabled = !active || ctx.neededPanels >= 400;
    if (!needNoteEl) return;
    if (!active) {
      needNoteEl.textContent = 'Indiquez votre facture pour dimensionner le nombre de panneaux.';
      return;
    }
    const placed = Math.min(ctx.neededPanels, fitCount);
    if (placed < ctx.neededPanels) {
      needNoteEl.textContent = `${fmt(ctx.neededPanels)} nécessaires — ${fmt(placed)} tiennent en ${familyLabel} (toit ou obstacles). On pose ${fmt(placed)}.`;
    } else if (fitCount > ctx.neededPanels) {
      needNoteEl.textContent = `${fmt(ctx.neededPanels)} couvrent votre facture (+10 %) — il reste de la place sur le toit, laissée libre.`;
    } else {
      needNoteEl.textContent = `On pose ${fmt(placed)} panneaux.`;
    }
  }

  /** Rendu UNIFIÉ : pose min(besoin, ce qui tient), recalcule kWc/kWh/économies
   *  depuis ce nombre POSÉ (jamais la capacité max de la config). */
  function renderConfig(o: RenderConfigOpts) {
    const placed = placedFor(o.grid);
    const kwc = o.grid.count > 0 ? (o.grid.kwc * placed) / o.grid.count : 0;
    // W1 : production à l'aspect réel (le rendement/panneau baisse honnêtement
    // quand l'array suit un toit tourné).
    const aspect = aspectForLeg(o.family, o.azimuthDeg);
    const tableAnnual = productionKwh(ctx.centroidLat, o.family, o.tiltDeg, kwc, aspect);
    // Affinage PVGIS : rendement par kWc × kWc POSÉ (suit le plafond/contrainte).
    const annualKwh = o.isReco && ctx.pvgisPerKwc != null ? ctx.pvgisPerKwc * kwc : tableAnnual;
    const target = ctx.rec ? ctx.rec.targetAnnualKwh : billToAnnualKwh(monthlyBill());
    const savings = annualSavingsMad(annualKwh, target); // plafonné à la conso
    renderScene(o.pack, o.grid, o.tiltDeg, o.family, placed);
    paintCard(
      {
        title: o.title,
        isReco: o.isReco,
        count: placed,
        kwc,
        annualKwh,
        pct: target > 0 ? (annualKwh / target) * 100 : 0,
        savingsLow: savings.low,
        savingsHigh: savings.high,
        why: o.why,
      },
      o.sourceLabel,
    );
    syncNeedControl(o.grid.count, o.family === 'eastwest' ? 'Est-Ouest' : 'plein sud');
    syncTiltControl(o.tiltDeg, o.isReco);
    if (o.isReco) paintMaxLine();
    highlightRow(o.rowId);
  }

  /** Reflète l'inclinaison RÉELLEMENT dessinée dans le curseur + son libellé.
   *  Ne touche pas le curseur pendant que l'utilisateur le manipule. */
  function syncTiltControl(tiltDeg: number, isReco: boolean) {
    const t = Math.round(tiltDeg);
    if (tiltRangeEl && document.activeElement !== tiltRangeEl) tiltRangeEl.value = String(t);
    if (tiltValueEl) tiltValueEl.textContent = `${t}°${isReco ? ' · reco' : ''}`;
    if (tiltRecoBtn) tiltRecoBtn.setAttribute('aria-pressed', String(isReco && ctx.useRecommended));
  }

  // ═════════════ W34 — OPTIMISEUR CONTRAINT VIVANT (toit plat, cerveau V7) ═════════════
  // renderSelection() est un ALIAS de liveResolveFlat() : recompute, renderActive et tous
  // les handlers d'options passent par le solveur vivant. Chaque option est un AXE ; un
  // clic VERROUILLE cet axe (épingle dans `pinned`) et RE-RÉSOUT en direct tous les axes
  // encore AUTO (les verrous s'accumulent), via solveLive (V7, PVGIS au GPS exact, repli
  // table « estimé »). Chaque groupe affiche la valeur « Recommandé » = la valeur que cet
  // axe prendrait s'il était libéré, les autres verrous tenus.

  /** Verrous courants dérivés des axes épinglés (pinned) + de la cible « besoin ».
   *  L'orientation (un seul axe V7) est reconstruite depuis les groupes Orientation
   *  (famille) et Azimut de la page. */
  function buildFlatLocks(): AxisLocks {
    const locks: AxisLocks = {};
    if (ctx.pinned.has('family') && ctx.sel.family === 'eastwest') locks.orientation = 'eastwest';
    else if (ctx.pinned.has('azimuth') && ctx.sel.azimuth === 'aligned') locks.orientation = 'aligned';
    else if ((ctx.pinned.has('family') && ctx.sel.family === 'south') || (ctx.pinned.has('azimuth') && ctx.sel.azimuth === 'south'))
      locks.orientation = 'south';
    if (ctx.pinned.has('tilt') && ctx.sel.tilt !== 'reco') locks.tiltDeg = ctx.sel.tilt;
    if (ctx.pinned.has('orient') && ctx.sel.orient !== 'auto') locks.layout = ctx.sel.orient as LayoutAxis;
    if (ctx.pinned.has('margin')) locks.margin = ctx.sel.margin;
    if (!ctx.neededAuto && ctx.neededPanels > 0) locks.need = ctx.neededPanels;
    return locks;
  }

  /** Reflète le gagnant courant dans `sel` (miroir d'affichage des puces). */
  function mapWinnerToSel(w: LiveConfigEval) {
    ctx.sel = {
      family: w.family,
      tilt: w.tiltDeg,
      orient: w.layout,
      azimuth: w.orientation === 'aligned' ? 'aligned' : 'south',
      margin: w.margin,
    };
  }

  function liveOrientationLabel(w: LiveConfigEval): string {
    if (w.family === 'eastwest') return 'Est-Ouest';
    return w.orientation === 'aligned' ? 'Sud (aligné toit)' : 'Plein sud';
  }

  /** Pose le badge « Recommandé » sur la valeur recommandée de CHAQUE groupe (axe
   *  libéré, autres verrous tenus) — reste correct même si l'utilisateur a verrouillé
   *  une autre valeur. */
  function updateLiveBadges(res: LiveSolveResult) {
    const rcm = res.recommended;
    const show = (b: Element | null, on: boolean) => {
      const badge = b?.querySelector<HTMLElement>('.rp9-reco-badge');
      if (badge) badge.hidden = !on;
    };
    const recFamily = rcm.orientation === 'eastwest' ? 'eastwest' : 'south';
    document.querySelectorAll<HTMLButtonElement>('[data-family]').forEach((b) => show(b, b.dataset.family === recFamily));
    const tiltRounded = Math.round(rcm.tiltDeg);
    const tiltChips = Array.from(document.querySelectorAll<HTMLButtonElement>('[data-tilt]'));
    const numericMatch = tiltChips.find((b) => b.dataset.tilt !== 'reco' && Number(b.dataset.tilt) === tiltRounded);
    tiltChips.forEach((b) => {
      if (numericMatch) show(b, b === numericMatch);
      else show(b, b.dataset.tilt === 'reco');
    });
    document.querySelectorAll<HTMLButtonElement>('[data-orient]').forEach((b) =>
      show(b, b.dataset.orient !== 'auto' && b.dataset.orient === rcm.layout),
    );
    const azReco = rcm.orientation === 'aligned' ? 'aligned' : 'south';
    document.querySelectorAll<HTMLButtonElement>('[data-azimuth]').forEach((b) => show(b, b.dataset.azimuth === azReco));
    document.querySelectorAll<HTMLButtonElement>('[data-margin]').forEach((b) => show(b, b.dataset.margin === rcm.margin));
  }

  /** Rend le gagnant vivant (3D + carte + contrôles) avec SES chiffres (PVGIS/estimé). */
  function renderLiveWinner(res: LiveSolveResult, isReco: boolean) {
    const w = res.winner;
    const ring: LngLat[] = [...ctx.vertices];
    const setbackM = w.margin === 'keep' ? PERIMETER_SETBACK_M : 0;
    const pack = packConfig(ring, ctx.centroidLat, {
      family: w.family,
      tiltDeg: w.tiltDeg,
      azimuthDeg: w.azimuthDeg,
      obstructions: obstructionRings(),
      setbackM,
    });
    const grid = w.layout === 'portrait' ? pack.portrait : pack.landscape;
    renderScene(pack, grid, w.tiltDeg, w.family, w.placedCount);
    const cov = Math.round(w.pctOfTarget);
    // W74 — AUCUNE config viable (toit trop petit / contraint à néant) : on n'affiche
    // PAS un faux « 0 panneau gagnant », mais un message honnête.
    const why = res.noViableConfig
      ? `Configuration non viable sur ce toit : aucun panneau ne tient (tracé trop petit ou entièrement occupé par des obstacles). Agrandissez la zone ou retirez des obstacles.`
      : isReco
        ? `Meilleure combinaison pour votre facture : ${liveOrientationLabel(w)} à ${w.tiltDeg}°, ${w.placedCount} panneaux ≈ ${cov} % de la facture. Touchez une option pour la verrouiller — le reste se re-résout.`
        : `Vos choix sont tenus, le reste a été re-résolu : ${w.placedCount} panneaux ≈ ${cov} % de la facture. Les badges « Recommandé » montrent l'option optimale de chaque groupe.`;
    paintCard(
      {
        title: `${liveOrientationLabel(w)} ${w.tiltDeg}° · ${w.layoutLabel}`,
        isReco,
        count: w.placedCount,
        kwc: w.kwc,
        annualKwh: w.annualKwh,
        pct: w.pctOfTarget,
        savingsLow: w.savingsLow,
        savingsHigh: w.savingsHigh,
        why,
      },
      w.yieldSource === 'pvgis' ? '(production PVGIS au GPS exact)' : '(production estimée — table par latitude)',
    );
    syncNeedControl(grid.count, liveOrientationLabel(w));
    syncTiltControl(w.tiltDeg, isReco);
    paintMaxLine();
    highlightRow(null);
    if (optimumNoteEl) {
      optimumNoteEl.textContent = isReco
        ? 'Optimum vivant : tout est calé sur la meilleure combinaison (chaque groupe badgé « Recommandé »). Verrouillez une option et le reste se re-résout en direct.'
        : 'Optimum vivant : votre choix est tenu, le reste se re-résout pour maximiser la génération. « Réinitialiser » relâche tous les verrous.';
    }
  }

  /** Cœur W34 : re-résolution CONTRAINTE vivante (verrous courants) + rendu + badges. */
  function liveResolveFlat() {
    if (!ctx.closed || ctx.vertices.length < 3 || ctx.roofType !== 'flat') return;
    const ring: LngLat[] = [...ctx.vertices];
    const bill = monthlyBill();
    const locks = buildFlatLocks();
    const yieldFn = (tiltDeg: number, aspect: number): number | null => {
      const v = ctx.v4YieldCache.get(v4Key(tiltDeg, aspect));
      return v == null ? null : v;
    };
    const res = solveLive(ring, ctx.centroidLat, bill, obstructionRings(), locks, { yieldFn });
    ctx.liveResult = res;
    if (ctx.neededAuto) ctx.neededPanels = res.neededPanels > 0 ? clampNeeded(res.neededPanels) : 0;
    const hasLocks = !!(locks.orientation || locks.tiltDeg != null || locks.layout || locks.margin || locks.need != null);
    ctx.useRecommended = !hasLocks;
    mapWinnerToSel(res.winner);
    if (azimuthGroup) azimuthGroup.hidden = !res.hasAlignedChoice;
    renderLiveWinner(res, !hasLocks);
    updateLiveBadges(res);
    syncChips();
    ensurePvgisForLockedTilt(locks);
    syncProductionWindow(); // W50 — reflète le plan gagnant dans la fenêtre de production
  }

  /** Affine PVGIS pour une inclinaison VERROUILLÉE hors grille (curseur fin), en
   *  arrière-plan (débattu) puis re-résout. La grille standard est déjà couverte par
   *  computeMatrixPvgis ; ici on n'interroge QUE l'inclinaison choisie. */
  function ensurePvgisForLockedTilt(locks: AxisLocks) {
    if (ctx.roofType !== 'flat' || locks.tiltDeg == null || !ctx.closed) return;
    const t = Math.round(locks.tiltDeg);
    const roofAz = roofDominantAzimuthDeg([...ctx.vertices]);
    const aspects = [...new Set(pvgisMatrixCandidatePairs(ctx.centroidLat, roofAz).map((p) => p.aspect))];
    const missing = aspects.filter((a) => !ctx.v4YieldCache.has(v4Key(t, a)));
    if (!missing.length) return;
    if (liveTiltTimer != null) clearTimeout(liveTiltTimer);
    const token = ++liveToken;
    liveTiltTimer = setTimeout(() => {
      void Promise.all(missing.map((a) => v4SpecificYield(t, a))).then(() => {
        if (token !== liveToken || ctx.roofType !== 'flat') return;
        liveResolveFlat();
      });
    }, 280);
  }

  /** « Réinitialiser » (toit plat) : relâche TOUS les verrous → optimum global. */
  function resetFlatLocks() {
    ctx.pinned.clear();
    ctx.neededAuto = true;
    ctx.useRecommended = true;
    liveResolveFlat();
  }

  /** renderSelection : alias historique → solveur vivant (toit plat). */
  function renderSelection() {
    liveResolveFlat();
  }

  function paintCard(d: CardData, sourceLabel?: string) {
    const set = (id: string, v: string) => {
      const el = $(id);
      if (el) el.textContent = v;
    };
    set('rp9-reco-title', d.isReco ? `${d.title}  ·  ✓ recommandé` : d.title);
    set('rp9-reco-kwc', `${d.kwc.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} kWc`);
    set('rp9-reco-panels', `${fmt(d.count)} × 720 W`);
    set('rp9-reco-prod', d.annualKwh > 0 ? `${fmt(Math.round(d.annualKwh))} kWh/an` : '—');
    set('rp9-reco-cover', d.pct > 0 ? `${Math.round(d.pct)} %` : '—');
    set('rp9-reco-savings', `${fmtMad(d.savingsLow)} – ${fmtMad(d.savingsHigh)}/an`);
    const why = $('rp9-reco-why');
    if (why) why.textContent = d.why + (sourceLabel ? ` ${sourceLabel}` : '');
    const bif = $('rp9-reco-bifacial');
    if (bif) {
      const gain = d.annualKwh * 0.05;
      bif.textContent = d.annualKwh > 0 ? `+ gain bifacial (estimation prudente, ~+5 %) : ~${fmt(Math.round(gain))} kWh/an — non compté dans le chiffre ci-dessus.` : '';
    }
    $('rp9-results')?.classList.add('rp9-results--ready');
    const cta = $<HTMLButtonElement>('rp9-cta');
    if (cta && d.count > 0) {
      cta.hidden = false;
      cta.onclick = () => prefillLead(d);
    }
  }

  function paintMaxLine() {
    if (!ctx.rec) return;
    const maxline = $('rp9-maxline');
    if (maxline) {
      maxline.textContent = `Rendement max par panneau : ~${ctx.rec.maxPerPanelTiltDeg}° plein sud. Énergie totale max sur CE toit : ~${ctx.rec.maxRoofEnergyTiltDeg}° (un toit limité gagne à être plus plat pour loger plus de panneaux).`;
    }
  }

  // ═══════════ V3 — toit en pente (pose affleurante) ═══════════

  const facingLabel = (az: number): string => {
    const m: Record<number, string> = { 180: 'sud', 135: 'sud-est', 225: 'sud-ouest', 90: 'est', 270: 'ouest', 0: 'nord' };
    return m[Math.round(az)] ?? `${Math.round(az)}°`;
  };

  // Adaptateurs FlushPack/FlushGrid (V3) → PackResult/PanelGrid pour réutiliser le
  // rendu 3D existant en mode affleurant (flush=true). family='south' (mono-MPPT,
  // jamais de chevron), azimut = face du pan, inclinaison = pente.
  function flushGridToPanelGrid(fg: FlushGrid): PanelGrid {
    const slopeLenM = fg.orientation === 'portrait' ? PANEL2_LONG_M : PANEL2_SHORT_M;
    const rowWidthM = fg.orientation === 'portrait' ? PANEL2_SHORT_M : PANEL2_LONG_M;
    return {
      panelOrientation: fg.orientation,
      count: fg.count,
      kwc: fg.kwc,
      rowPitchM: fg.rowPitchM,
      panels: fg.panels,
      slopeLenM,
      rowWidthM,
      footprintPerPanelM2: fg.footprintPerPanelM2,
    };
  }
  function flushToPack(fp: FlushPack): PackResult {
    return {
      origin: fp.origin,
      ringENU: fp.ringENU,
      azimuthDeg: fp.facingAzimuthDeg,
      tiltDeg: fp.pitchDeg,
      family: 'south',
      areaM2: fp.areaM2,
      usableAreaM2: fp.usableAreaM2,
      portrait: flushGridToPanelGrid(fp.portrait),
      landscape: flushGridToPanelGrid(fp.landscape),
      best: flushGridToPanelGrid(fp.best),
    };
  }

  function pitchedWhy(): string {
    if (!ctx.pitchedRec) return '';
    const p = ctx.pitchedRec.planes[0];
    if (p.northFacing) {
      return `Ce pan est orienté ${facingLabel(ctx.facingAzimuthDeg)} (trop au nord) : aucune pose recommandée. Choisissez un pan orienté sud, est ou ouest.`;
    }
    const cover = Math.round(ctx.pitchedRec.pctOfTarget);
    const head = `Pose affleurante sur la pente (~${Math.round(p.pitchDeg)}°, face ${facingLabel(ctx.facingAzimuthDeg)})`;
    if (ctx.pitchedRec.roofLimited) {
      return `${head} : ${ctx.pitchedRec.totalPlacedCount} panneaux, ~${cover} % de votre consommation. Ce pan ne couvre pas tout le besoin.`;
    }
    return `${head} : dimensionné à votre besoin — ${ctx.pitchedRec.totalPlacedCount} panneaux, ~${cover} %. Inclinaison et azimut imposés par le toit.`;
  }
  function pitchedNote(): string {
    if (!ctx.pitchedRec) return '';
    const p = ctx.pitchedRec.planes[0];
    const yld = ctx.pitchedPvgisPerKwc != null ? Math.round(ctx.pitchedPvgisPerKwc) : Math.round(p.perPanelYield);
    const src = ctx.pitchedPvgisPerKwc != null ? 'PVGIS, pose « building »' : 'table committée (PVGIS indisponible)';
    return `Inclinaison ${Math.round(p.pitchDeg)}° = pente · azimut ${Math.round(p.facingAzimuthDeg)}° = face (imposés, non balayés). Rendement ${src} : ~${yld} kWh/kWc/an. Panneaux qui tiennent sur ce pan : ${p.fitCount}.`;
  }

  function renderPitched() {
    if (!ctx.pitchedRec) return;
    const plane = ctx.pitchedRec.planes[0];
    const fp = plane.pack;
    const fg = plane.orientation === 'portrait' ? fp.portrait : fp.landscape;
    renderScene(flushToPack(fp), flushGridToPanelGrid(fg), fp.pitchDeg, 'south', plane.placedCount, true);
    // V5 : production de vérité = PVGIS au (pente, face) réels, pose 'building'.
    // Disponible → on remplace la valeur table par le chiffre PVGIS et on recalcule
    // couverture + économies de façon cohérente ; sinon repli table (« estimé »).
    const target = ctx.pitchedRec.targetAnnualKwh;
    const usePvgis = ctx.pitchedPvgisPerKwc != null && ctx.pitchedRec.totalKwc > 0 && !plane.northFacing;
    const annualKwh = usePvgis ? ctx.pitchedRec.totalKwc * (ctx.pitchedPvgisPerKwc as number) : ctx.pitchedRec.totalAnnualKwh;
    const pct = target > 0 ? (annualKwh / target) * 100 : 0;
    const savings = usePvgis ? annualSavingsMad(annualKwh, target, tariffForCity(undefined)) : { low: ctx.pitchedRec.savingsLow, high: ctx.pitchedRec.savingsHigh };
    paintCard(
      {
        title: `Toit en pente ~${Math.round(fp.pitchDeg)}° · face ${facingLabel(ctx.facingAzimuthDeg)}`,
        isReco: true,
        count: ctx.pitchedRec.totalPlacedCount,
        kwc: ctx.pitchedRec.totalKwc,
        annualKwh,
        pct,
        savingsLow: savings.low,
        savingsHigh: savings.high,
        why: pitchedWhy(),
      },
      usePvgis ? '(production PVGIS · pose affleurante « building »)' : '(production estimée · table committée — PVGIS indisponible)',
    );
    syncNeedControl(plane.fitCount, 'pente');
    if (pitchedNoteEl) pitchedNoteEl.textContent = pitchedNote();
    if (pitchValueEl) pitchValueEl.textContent = `${Math.round(fp.pitchDeg)}°`;
    highlightRow(null);
  }

  // ═══════════ W35 — OPTIMISEUR CONTRAINT VIVANT (toit en pente, cerveau V8) ═══════════
  // Jumeau de l'optimiseur plat (W34) : axes libres = pose + marge (+ cible besoin),
  // inclinaison = pente et azimut = face IMPOSÉS (jamais optimisés). Verrouiller un axe
  // le tient et re-résout l'autre ; production PVGIS au (pente, face), pose 'building'.

  /** Verrous pente courants (pose + marge) + cible besoin (partagée via neededAuto). */
  function buildPitchedLocks(): { layout?: PitchedLayoutAxis; margin?: PitchedMarginAxis; need?: number } {
    const locks: { layout?: PitchedLayoutAxis; margin?: PitchedMarginAxis; need?: number } = {};
    if (ctx.pitchedLocks.layout) locks.layout = ctx.pitchedLocks.layout;
    if (ctx.pitchedLocks.margin) locks.margin = ctx.pitchedLocks.margin;
    if (!ctx.neededAuto && ctx.neededPanels > 0) locks.need = ctx.neededPanels;
    return locks;
  }

  function liveResolvePitched() {
    if (!ctx.closed || ctx.vertices.length < 3 || ctx.roofType !== 'pitched') return;
    const ring: LngLat[] = [...ctx.vertices];
    const bill = monthlyBill();
    const locks = buildPitchedLocks();
    const yieldFn = (pitch: number, facing: number): number | null => {
      const v = ctx.pitchedYieldCache.get(pitchedKey(pitch, facing));
      return v == null ? null : v;
    };
    const res = solveLivePitched(ring, ctx.centroidLat, bill, ctx.pitchDeg, ctx.facingAzimuthDeg, obstructionRings(), locks, { yieldFn });
    ctx.pitchedLiveResult = res;
    if (ctx.neededAuto) ctx.neededPanels = res.neededPanels > 0 ? clampNeeded(res.neededPanels) : 0;
    const hasLocks = !!(locks.layout || locks.margin || locks.need != null);
    renderPitchedWinner(res, !hasLocks);
    updatePitchedBadges(res);
    paintPitchedComparison(res);
    syncPitchedChips(res);
    syncProductionWindow(); // W50 — reflète le plan gagnant (pente) dans la fenêtre de production
  }

  function renderPitchedWinner(res: PitchedLiveResult, isReco: boolean) {
    const w = res.winner;
    renderScene(flushToPack(w.pack), flushGridToPanelGrid(w.grid), w.pack.pitchDeg, 'south', w.placedCount, true);
    const cov = Math.round(w.pctOfTarget);
    const tiltTxt = `${Math.round(ctx.pitchDeg)}°`;
    // W74 — pan orienté nord (production quasi nulle) ET pan non viable (trop petit /
    // contraint à néant) ont chacun leur message honnête, distincts d'un faux gagnant.
    const why = res.northFacing
      ? `Ce pan est orienté nord (face ${facingLabel(ctx.facingAzimuthDeg)}) : production quasi nulle, aucune pose rentable proposée. Indiquez la vraie face descendante du pan.`
      : res.noViableConfig
        ? `Configuration non viable sur ce toit : aucun panneau ne tient sur ce pan (trop petit ou entièrement occupé par des obstacles). Agrandissez le pan ou retirez des obstacles.`
        : isReco
          ? `Pose affleurante optimale : ${w.placedCount} panneaux (${w.layoutLabel}, ${w.marginLabel}) ≈ ${cov} % de la facture. Inclinaison ${tiltTxt} = pente, azimut = face — imposés par la toiture, non optimisés.`
          : `Vos choix sont tenus, le reste re-résolu : ${w.placedCount} panneaux ≈ ${cov} % de la facture. Les badges « Recommandé » montrent la pose/marge optimale.`;
    paintCard(
      {
        title: `Toit en pente ~${tiltTxt} · face ${facingLabel(ctx.facingAzimuthDeg)} · ${w.layoutLabel}`,
        isReco,
        count: w.placedCount,
        kwc: w.kwc,
        annualKwh: w.annualKwh,
        pct: w.pctOfTarget,
        savingsLow: w.savingsLow,
        savingsHigh: w.savingsHigh,
        why,
      },
      w.yieldSource === 'pvgis' ? '(production PVGIS · pose affleurante « building »)' : '(production estimée · table committée — PVGIS indisponible)',
    );
    syncNeedControl(w.grid.count, 'pente');
    if (pitchValueEl) pitchValueEl.textContent = tiltTxt;
    if (pitchedNoteEl) {
      pitchedNoteEl.textContent = `Inclinaison ${tiltTxt} = pente · azimut ${Math.round(ctx.facingAzimuthDeg)}° = face (imposés, non balayés). Pose affleurante, sans rangées espacées. Panneaux qui tiennent : ${w.fitCount}.`;
    }
    highlightRow(null);
    if (optimumNoteEl) {
      optimumNoteEl.textContent = isReco
        ? 'Optimum vivant (pente) : pose et marge calées au mieux ; inclinaison et azimut imposés par le toit.'
        : 'Optimum vivant (pente) : votre choix est tenu, pose/marge re-résolues autour. « Réinitialiser » relâche tout.';
    }
  }

  /** Badge « Recommandé » sur la pose (data-orient) et la marge (data-margin) en pente. */
  function updatePitchedBadges(res: PitchedLiveResult) {
    const show = (b: Element | null, on: boolean) => {
      const badge = b?.querySelector<HTMLElement>('.rp9-reco-badge');
      if (badge) badge.hidden = !on;
    };
    document.querySelectorAll<HTMLButtonElement>('[data-orient]').forEach((b) =>
      show(b, b.dataset.orient !== 'auto' && b.dataset.orient === res.recommended.layout),
    );
    document.querySelectorAll<HTMLButtonElement>('[data-margin]').forEach((b) => show(b, b.dataset.margin === res.recommended.margin));
  }

  /** Puces pose/marge : la valeur du gagnant affichée pressée (verrou ou auto). */
  function syncPitchedChips(res: PitchedLiveResult) {
    const w = res.winner;
    document.querySelectorAll<HTMLButtonElement>('[data-orient]').forEach((b) =>
      b.setAttribute('aria-pressed', String(b.dataset.orient === w.layout)),
    );
    document.querySelectorAll<HTMLButtonElement>('[data-margin]').forEach((b) =>
      b.setAttribute('aria-pressed', String(b.dataset.margin === w.margin)),
    );
  }

  /** Tableau comparatif de l'espace LIBRE en pente (≤ 4 lignes : pose × marge),
   *  l'optimum badgé « Recommandé ». Réutilise le tableau de la matrice plate. */
  function paintPitchedComparison(res: PitchedLiveResult) {
    const tbody = $('rp9-compare');
    const wrap = $('rp9-compare-wrap');
    if (!tbody) return;
    const rowKey = (r: PitchedLiveResult['winner']) => `${r.layout}|${r.margin}`;
    const wk = rowKey(res.winner);
    const rows = [...res.rows].sort((a, b) => b.annualKwh - a.annualKwh);
    tbody.innerHTML = '';
    for (const r of rows) {
      const tr = document.createElement('tr');
      const key = rowKey(r);
      tr.dataset.id = key;
      const badge = key === wk ? ' <span style="color:var(--color-brass-300)">✓ Recommandé</span>' : '';
      tr.innerHTML =
        `<td>${r.label}${badge}</td>` +
        `<td class="num">${fmt(r.placedCount)}</td>` +
        `<td class="num">${r.kwc.toLocaleString('fr-FR', { maximumFractionDigits: 1 })}</td>` +
        `<td class="num">${fmt(Math.round(r.annualKwh))}</td>` +
        `<td class="num">${Math.round(r.pctOfTarget)} %</td>` +
        `<td class="num">${fmtMad(r.savingsLow)} – ${fmtMad(r.savingsHigh)}</td>`;
      tr.addEventListener('click', () => {
        ctx.pitchedLocks.layout = r.layout;
        ctx.pitchedLocks.margin = r.margin;
        liveResolvePitched();
      });
      tbody.appendChild(tr);
    }
    if (wrap) wrap.hidden = false;
    highlightRow(wk);
  }

  /** « Réinitialiser » (toit en pente) : relâche les verrous pose/marge → optimum global. */
  function resetPitchedLocks() {
    delete ctx.pitchedLocks.layout;
    delete ctx.pitchedLocks.margin;
    ctx.neededAuto = true;
    liveResolvePitched();
  }

  // V5 — rendement spécifique PVGIS (kWh/kWc/an) du plan en pente, pose 'building',
  // à kWc=1 (mis à l'échelle ensuite). Cache par (pente|face), repli table (null).
  async function pitchedSpecificYield(pitch: number, facing: number): Promise<number | null> {
    const key = pitchedKey(pitch, facing);
    if (ctx.pitchedYieldCache.has(key)) return ctx.pitchedYieldCache.get(key) ?? null;
    try {
      const res = await fetch('/api/roof-yield', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ lat: ctx.centroid[1], lon: ctx.centroid[0], mountingplace: 'building', legs: [pitchedPlaneLeg(pitch, facing, 1)] }),
      });
      const data = await res.json();
      const v = res.ok && data.ok && typeof data.annualKwh === 'number' ? data.annualKwh : null;
      ctx.pitchedYieldCache.set(key, v);
      return v;
    } catch {
      ctx.pitchedYieldCache.set(key, null);
      return null;
    }
  }

  // Affine la production du toit en pente avec PVGIS (une seule requête, cachée).
  async function refinePitchedPvgis() {
    if (!ctx.pitchedRec) return;
    const p = ctx.pitchedRec.planes[0];
    if (!p || p.northFacing) return;
    const token = ++pitchedToken;
    const perKwc = await pitchedSpecificYield(p.pitchDeg, p.facingAzimuthDeg);
    if (token !== pitchedToken || perKwc == null) return;
    ctx.pitchedPvgisPerKwc = perKwc;
    // W35 — le cache PVGIS (pente, face) est rempli : re-résout l'optimiseur vivant.
    if (ctx.roofType === 'pitched') liveResolvePitched();
  }

  function pitchedRecompute() {
    if (!ctx.closed || ctx.vertices.length < 3) return;
    const ring: LngLat[] = [...ctx.vertices];
    const plane: RoofPlane = { ring, pitchDeg: ctx.pitchDeg, facingAzimuthDeg: ctx.facingAzimuthDeg, obstructions: obstructionRings() };
    ctx.pitchedRec = recommendPitched([plane], ctx.centroidLat, monthlyBill());
    ctx.pitchedPvgisPerKwc = null; // nouvelle config → chiffre PVGIS obsolète (repli table)
    if (ctx.neededAuto) {
      const n = neededPanelsForTarget(ctx.pitchedRec.targetAnnualKwh, ctx.centroidLat);
      ctx.neededPanels = n > 0 ? clampNeeded(n) : 0;
    }
    // W35 — l'optimiseur vivant en pente rend le gagnant + son comparatif (pose × marge).
    liveResolvePitched();
    setStatus('Mode pente : pose affleurante, inclinaison et azimut imposés par le toit.');
    void refinePitchedPvgis(); // production de vérité PVGIS (building) au (pente, face)
  }

  // ── V4 — PVGIS SOURCE DE VÉRITÉ ──────────────────────────────────────────────

  // W1 — Jambes PVGIS pour une famille/azimut donné. Sud = une jambe (aspect =
  // azimut−180). Est-Ouest = deux jambes, base = azimut−90, ∓90.
  function legsFor(family: ConfigFamily, tiltDeg: number, azimuthDeg: number, kwc: number) {
    if (family === 'eastwest') {
      const base = azimuthDeg - 90;
      return [
        { kwc: kwc / 2, tiltDeg, aspect: base - 90 },
        { kwc: kwc / 2, tiltDeg, aspect: base + 90 },
      ];
    }
    return [{ kwc, tiltDeg, aspect: azimuthDeg - 180 }];
  }

  /**
   * W1 — Production PVGIS live (kWh) pour une config, avec CACHE partagé entre TOUS
   * les réglages : une même config (lat,lon|famille|tilt|azimut) n'est jamais
   * re-demandée. PVGIS injoignable/null → on mémorise null (repli table côté
   * appelant) sans erreur visible. On ne requête QUE les configs réellement
   * affichées (recommandée + sélection visible), jamais tout l'espace théorique.
   */
  async function fetchPvgis(family: ConfigFamily, tiltDeg: number, azimuthDeg: number, kwc: number): Promise<number | null> {
    if (kwc <= 0) return null;
    const key = pvgisKey(family, tiltDeg, azimuthDeg);
    if (ctx.pvgisCache.has(key)) return ctx.pvgisCache.get(key) ?? null;
    try {
      const res = await fetch('/api/roof-yield', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ lat: ctx.centroid[1], lon: ctx.centroid[0], legs: legsFor(family, tiltDeg, azimuthDeg, kwc) }),
      });
      const data = await res.json();
      if (res.ok && data.ok && typeof data.annualKwh === 'number') {
        ctx.pvgisCache.set(key, data.annualKwh);
        return data.annualKwh;
      }
      ctx.pvgisCache.set(key, null); // PVGIS a répondu « estimate » → repli table mémorisé
      return null;
    } catch {
      // Pas d'erreur visible : la table committée a déjà fourni un chiffre.
      ctx.pvgisCache.set(key, null);
      return null;
    }
  }

  async function refinePvgis() {
    if (!ctx.rec) return;
    const r = ctx.rec.recommended;
    const kwh = await fetchPvgis(r.family, r.tiltDeg, r.azimuthDeg, r.kwc);
    if (kwh != null && r.kwc > 0) {
      // Stocke le rendement (kWh/kWc) — réappliqué au nombre POSÉ, qui peut être
      // sous le besoin si le toit/les obstacles contraignent.
      ctx.pvgisPerKwc = kwh / r.kwc;
      if (ctx.useRecommended) renderSelection();
    }
  }

  // ── V4 — PVGIS SOURCE DE VÉRITÉ : optimum de grille fine au GPS exact ────────
  // Rendement spécifique (kWh/kWc/an) pour un (tilt, aspect) — kWc=1, pose 'free'
  // (toit plat racké). Mémorisé/réutilisé ; PVGIS null → repli table (null en cache).
  async function v4SpecificYield(tiltDeg: number, aspect: number): Promise<number | null> {
    const key = v4Key(tiltDeg, aspect);
    if (ctx.v4YieldCache.has(key)) return ctx.v4YieldCache.get(key) ?? null;
    try {
      const res = await fetch('/api/roof-yield', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ lat: ctx.centroid[1], lon: ctx.centroid[0], mountingplace: 'free', legs: [{ kwc: 1, tiltDeg, aspect }] }),
      });
      const data = await res.json();
      if (res.ok && data.ok && typeof data.annualKwh === 'number') {
        ctx.v4YieldCache.set(key, data.annualKwh);
        return data.annualKwh;
      }
      ctx.v4YieldCache.set(key, null);
      return null;
    } catch {
      ctx.v4YieldCache.set(key, null);
      return null;
    }
  }

  // V6 — la MATRICE complète notée sur le rendement PVGIS du GPS EXACT, en
  // COARSE-THEN-FINE pour rester rapide et dans les limites de débit PVGIS : le
  // rendement spécifique est interrogé UNE fois par (tilt, aspect), mis en cache et
  // réutilisé (cache partagé v4YieldCache). Phase 1 = grille grossière (tous aspects)
  // → trouve la base ; phase 2 = grille fine autour de l'aspect gagnant. Les cellules
  // non interrogées retombent gracieusement sur l'estimation maison (« estimé »).
  const buildMatrix = (ring: LngLat[], bill: number) => {
    const yieldFn = (tiltDeg: number, aspect: number): number | null => {
      const v = ctx.v4YieldCache.get(v4Key(tiltDeg, aspect));
      return v == null ? null : v;
    };
    ctx.matrixResult = fineGridMatrixV6(ring, ctx.centroidLat, bill, obstructionRings(), { yieldFn });
    paintComparison();
    renderMatrixOptimumCard();
    // W34 — le cache PVGIS vient d'être enrichi : re-résout le solveur vivant pour que
    // le gagnant affiché + les badges « Recommandé » suivent la production PVGIS exacte.
    if (ctx.roofType === 'flat') liveResolveFlat();
  };

  async function computeMatrixPvgis() {
    if (!ctx.closed || ctx.vertices.length < 3 || ctx.roofType !== 'flat') return;
    const token = ++matrixToken;
    const ring: LngLat[] = [...ctx.vertices];
    const bill = monthlyBill();
    const roofAz = roofDominantAzimuthDeg(ring);
    // Phase 1 — GROSSIÈRE : tous les aspects, inclinaisons grossières → la base.
    await Promise.all(pvgisCoarsePairs(ctx.centroidLat, roofAz).map((p) => v4SpecificYield(p.tiltDeg, p.aspect)));
    if (token !== matrixToken) return; // un tracé/réglage plus récent a pris la main
    buildMatrix(ring, bill);
    // Phase 2 — FINE : on raffine la grille fine complète autour de l'aspect gagnant.
    const refine = pvgisRefinePairs(ctx.centroidLat, roofAz, ctx.matrixResult ? ctx.matrixResult.winner.aspect : 0);
    if (!refine.length) return;
    await Promise.all(refine.map((p) => v4SpecificYield(p.tiltDeg, p.aspect)));
    if (token !== matrixToken) return;
    buildMatrix(ring, bill);
  }

  // tiltOf/gridFor : helpers de sélection historiques (conservés tels quels).
  function tiltOf(family: ConfigFamily): number {
    if (ctx.sel.tilt === 'reco') {
      if (ctx.useRecommended && ctx.rec) return ctx.rec.recommended.tiltDeg;
      return family === 'eastwest' ? 10 : (ctx.rec?.maxPerPanelTiltDeg ?? 29);
    }
    return ctx.sel.tilt;
  }

  function gridFor(pack: PackResult): PanelGrid {
    if (ctx.sel.orient === 'portrait') return pack.portrait;
    if (ctx.sel.orient === 'landscape') return pack.landscape;
    return pack.best;
  }

  // tiltOf/gridFor/renderPitched/refinePvgis : helpers historiques conservés tels quels
  // (déjà non appelés avant le split — surface préservée à l'identique, jamais ré-écrite).

  return {
    liveResolveFlat,
    liveResolvePitched,
    renderSelection,
    renderConfig,
    pitchedRecompute,
    resetFlatLocks,
    resetPitchedLocks,
    buildMatrix,
    computeMatrixPvgis,
    clampNeeded,
  };
}
