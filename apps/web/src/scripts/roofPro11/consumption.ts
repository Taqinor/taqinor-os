/**
 * W68 — « Affiner ma consommation » : courbe horaire éditable + calculateur
 * d'appareils + impact dimensionnement/batterie. Extrait de roof-tool-pro11.ts
 * (split modulaire 2026-06-20) — comportement INCHANGÉ.
 *
 * La logique PURE reste dans ../../lib/applianceConsumption (jamais dupliquée) ;
 * ce module ne fait que la brancher au DOM et à l'état du builder via le Ctx.
 * Les dépendances vers l'optimiseur (`renderActive`, `clampNeeded`) et la facture
 * (`monthlyBill`) sont injectées — ce module ne les ré-implémente pas.
 */
import {
  HOURS_PER_DAY,
  MONTHS_PER_YEAR,
  DAYS_IN_MONTH,
  emptyCurve,
  curveTotal,
  baselineCurve,
  composeConsumption,
  rescaleToDaily,
  annualConsumptionFromDaily,
  annualSelfConsumptionKwh,
  annualSavingsFromMonthly,
  annualBatterySizing,
  seasonalConsumptionByMonth,
  annualSelfConsumptionSeasonalKwh,
  batteryPaybackYears,
  acWattsFromBtu,
  kwhFromWattsHours,
  evKwhFromDistance,
  slotEndHour,
  applianceFromTypical,
  APPLIANCE_TYPICALS,
  AC_BTU_PRESETS,
  AC_EER_DEFAULT_NON_INVERTER,
  EV_CHARGER_KW_PRESETS,
  EV_KWH_PER_100KM_DEFAULT,
  type Appliance,
  type HourlyCurve,
} from '../../lib/applianceConsumption';
import { annualSavingsMad, billToAnnualKwh, neededPanelsForTarget, tariffForCity } from '../../lib/estimatorBrainV2';
import { fmtSavings } from '../../lib/productionWindow';
import { fmt as fmtInt, esc } from './dom';
import { type Ctx } from './context';

/** Références DOM du panneau « Affiner ma consommation ». */
export interface ConsumptionDom {
  consWindowEl: HTMLElement | null;
  consToggleEl: HTMLButtonElement | null;
  consPanelEl: HTMLElement | null;
  consTotalEl: HTMLElement | null;
  consSelfEl: HTMLElement | null;
  consSavingsEl: HTMLElement | null;
  consBattEl: HTMLElement | null;
  consGraphEl: HTMLElement | null;
  consInputsEl: HTMLElement | null;
  consRecalEl: HTMLButtonElement | null;
  /** W83 — « Réinitialiser la courbe » (efface l'override, rebâtit socle + appareils). */
  consResetEl: HTMLButtonElement | null;
  /** W96 — fourchette de retour sur investissement batterie (rendu conditionnel). */
  consPaybackEl: HTMLElement | null;
  /** W95 — bascule du profil saisonnier (été ≠ hiver). */
  consSeasonalToggleEl: HTMLButtonElement | null;
  /** W95 — bloc des facteurs été/hiver (visible quand le profil saisonnier est actif). */
  consSeasonalControlsEl: HTMLElement | null;
  /** W95 — saisie du facteur d'été. */
  consSummerFactorEl: HTMLInputElement | null;
  /** W95 — saisie du facteur d'hiver. */
  consWinterFactorEl: HTMLInputElement | null;
  /** W95 — mini-graphe SVG de l'autoconsommation mensuelle (12 barres). */
  consMonthlyChartEl: HTMLElement | null;
  applKindEl: HTMLSelectElement | null;
  applAddEl: HTMLButtonElement | null;
  applAcEl: HTMLElement | null;
  acBtuEl: HTMLSelectElement | null;
  acEerEl: HTMLInputElement | null;
  acHoursEl: HTMLInputElement | null;
  acWattsEl: HTMLElement | null;
  applEvEl: HTMLElement | null;
  evKwEl: HTMLSelectElement | null;
  evHoursEl: HTMLInputElement | null;
  evKmEl: HTMLInputElement | null;
  applNoteEl: HTMLElement | null;
  applListEl: HTMLElement | null;
}

/** Dépendances injectées (optimiseur + facture + formatage). */
export interface ConsumptionDeps {
  /** Re-résout l'optimiseur actif (plat ou pente) — chemin existant. */
  renderActive: () => void;
  /** Borne le besoin « panneaux nécessaires » (1..400). */
  clampNeeded: (n: number) => number;
  /** Facture mensuelle saisie (MAD). */
  monthlyBill: () => number;
  /** Entier formaté à une décimale (séparateur fr-FR). */
  fmt1: (n: number) => string;
}

export interface Consumption {
  billDailyKwh: () => number;
  productionHourly: () => HourlyCurve;
  rebuildConsCurve: () => void;
  applyConsumptionToSizing: () => void;
  renderConsGraph: () => void;
  renderConsInputs: () => void;
  renderConsumption: () => void;
  renderApplianceList: () => void;
  renderConsumptionSummaryOnly: () => void;
  /** Attache tous les écouteurs d'événements du panneau de consommation. */
  wire: () => void;
}

export function createConsumption(ctx: Ctx, dom: ConsumptionDom, deps: ConsumptionDeps): Consumption {
  const { renderActive, clampNeeded, monthlyBill, fmt1 } = deps;

  /** kWh/jour dérivé de la facture (le socle). billToAnnualKwh ÷ 365. */
  function billDailyKwh(): number {
    const annual = billToAnnualKwh(monthlyBill());
    return annual > 0 ? annual / 365 : 0;
  }

  /** Profil horaire de PUISSANCE (kW) du jour-type courant (production), aligné 24 h.
   *  Source = la même production PVGIS que la fenêtre (jour-type du mois sélectionné,
   *  ou la date précise). Vide si aucun plan n'est calculé. */
  function productionHourly(): HourlyCurve {
    const prodScaled = ctx.prodScaled;
    if (!prodScaled) return emptyCurve();
    const prodSpecificDate = ctx.prodSpecificDate;
    if (prodSpecificDate && Array.isArray(prodSpecificDate.hourlyKw) && prodSpecificDate.hourlyKw.length === HOURS_PER_DAY) {
      return prodSpecificDate.hourlyKw.map((v) => (Number.isFinite(v) && v > 0 ? v : 0));
    }
    const prof = prodScaled.typicalDayByMonth[ctx.prodMonth];
    if (Array.isArray(prof) && prof.length === HOURS_PER_DAY) return prof.map((v) => (Number.isFinite(v) && v > 0 ? v : 0));
    return emptyCurve();
  }

  /** Les 12 jours-types de PRODUCTION (kW = kWh au pas 1 h), alignés sur 24 h chacun —
   *  source de l'INTÉGRALE ANNUELLE (W82) : économies/autoconso/batterie qui ne dépendent
   *  PAS du mois affiché. Vide (12 × 0) tant qu'aucun plan de production n'existe. */
  function typicalDayByMonth(): HourlyCurve[] {
    const prodScaled = ctx.prodScaled;
    if (!prodScaled || !Array.isArray(prodScaled.typicalDayByMonth)) {
      return Array.from({ length: MONTHS_PER_YEAR }, () => emptyCurve());
    }
    return Array.from({ length: MONTHS_PER_YEAR }, (_, m) => {
      const prof = prodScaled.typicalDayByMonth[m];
      return Array.isArray(prof) && prof.length === HOURS_PER_DAY
        ? prof.map((v) => (Number.isFinite(v) && v > 0 ? v : 0))
        : emptyCurve();
    });
  }

  /** Σ de l'énergie journalière des appareils « en plus » (onTop) — l'énergie qui s'AJOUTE
   *  au-dessus du socle facture (W83). Sert à recaler la courbe en PRÉSERVANT cette énergie. */
  function onTopDailyKwh(): number {
    let sum = 0;
    for (const a of ctx.consAppliances) {
      if (a.billing === 'onTop' && Number.isFinite(a.dailyKwh) && a.dailyKwh > 0) sum += a.dailyKwh;
    }
    return sum;
  }

  /** Construit les 12 courbes de conso MENSUELLES (W95). En mode saisonnier (toggle
   *  `consSeasonal`) on applique le facteur été/hiver à la courbe de référence ; sinon les
   *  12 mois partagent la même courbe (intégrale 12 mois « à plat »). */
  function consumptionByMonth(): HourlyCurve[] {
    if (ctx.consSeasonal) {
      return seasonalConsumptionByMonth(ctx.consCurve, ctx.consSummerFactor, ctx.consWinterFactor);
    }
    return Array.from({ length: MONTHS_PER_YEAR }, () => ctx.consCurve.slice());
  }

  /** Synthèse ANNUELLE honnête (W82/W84/W95) : autoconsommation + économies + batterie
   *  intégrées sur les 12 mois réels, donc INVARIANTES au mois affiché. En mode saisonnier
   *  la conso varie par mois (W95). Renvoie le détail mensuel d'autoconso pour le mini-graphe. */
  function annualSummary(): {
    selfAnnualKwh: number;
    selfDailyAvgKwh: number;
    annualConsKwh: number;
    savings: { low: number; high: number };
    batteries: number;
    perMonthSelfKwh: number[];
  } {
    const months = typicalDayByMonth();
    const dailyTotal = curveTotal(ctx.consCurve);
    if (ctx.consSeasonal) {
      const byMonth = consumptionByMonth();
      // Conso annuelle réelle = Σ (total journalier du mois × jours du mois).
      let annualCons = 0;
      for (let m = 0; m < MONTHS_PER_YEAR; m++) {
        annualCons += curveTotal(byMonth[m]) * (DAYS_IN_MONTH[m] ?? 0);
      }
      const self = annualSelfConsumptionSeasonalKwh(byMonth, months);
      // Économies : autoconso 12 mois saisonnière plafonnée par le modèle billMAD existant
      // (JAMAIS production × tarif). Batterie : intégrée 12 mois sur la courbe d'ÉTÉ (la plus
      // consommatrice) → stable au mois affiché.
      const savings = annualSavingsMad(self.annualKwh, Math.max(0, annualCons), tariffForCity(undefined));
      const batt = annualBatterySizing(byMonth[6] ?? ctx.consCurve, months);
      return {
        selfAnnualKwh: self.annualKwh,
        selfDailyAvgKwh: self.annualKwh / 365,
        annualConsKwh: annualCons,
        savings: { low: savings.low, high: savings.high },
        batteries: batt.batteries,
        perMonthSelfKwh: self.perMonthKwh,
      };
    }
    const annualCons = annualConsumptionFromDaily(dailyTotal);
    const self = annualSelfConsumptionKwh(ctx.consCurve, months);
    const savings = annualSavingsFromMonthly(ctx.consCurve, months, annualCons, tariffForCity(undefined));
    const batt = annualBatterySizing(ctx.consCurve, months);
    return {
      selfAnnualKwh: self.annualKwh,
      selfDailyAvgKwh: self.annualKwh / 365,
      annualConsKwh: annualCons,
      savings: { low: savings.low, high: savings.high },
      batteries: batt.batteries,
      perMonthSelfKwh: self.perMonthKwh,
    };
  }

  /** Recompose la courbe de conso depuis le socle (facture) + appareils, SAUF si
   *  l'utilisateur l'a éditée à la main (auquel cas on garde son override). */
  function rebuildConsCurve() {
    ctx.consDailyTarget = billDailyKwh();
    if (ctx.consHandEdited) return; // override manuel respecté
    const base = baselineCurve(ctx.consDailyTarget);
    ctx.consCurve = composeConsumption(base, ctx.consAppliances);
  }

  /** Met à jour le besoin « panneaux nécessaires » quand des appareils « en plus »
   *  augmentent la conso (taille-au-besoin via le chemin existant). N'agit qu'en mode
   *  auto (l'utilisateur n'a pas figé le besoin).
   *
   *  GARDE DE RÉ-ENTRANCE (correctif du FIGEAGE) : ce chemin boucle —
   *  applyConsumptionToSizing → renderActive → liveResolveFlat (qui réécrit `neededPanels`
   *  depuis la FACTURE, ≠ besoin issu de la conso) → syncProductionWindow → renderProdWindow
   *  → renderConsumption → applyConsumptionToSizing → … Comme les deux besoins divergent, la
   *  page bouclait à l'infini dès qu'on ouvrait « Affiner ma consommation ». On garde donc la
   *  ré-entrance ET on FIGE le besoin issu de la conso (`neededAuto = false`) pour que
   *  liveResolveFlat ne le rebascule pas — la boucle se termine en un seul cycle. */
  let inConsSizing = false;
  function applyConsumptionToSizing(annualConsKwh?: number) {
    // W83 — RÉVERSIBLE (correctif du cliquet à sens unique). L'ancienne garde
    // `if (!ctx.neededAuto) return` rendait le besoin IRRÉVERSIBLE : le premier appareil
    // « en plus » latchait `neededAuto = false`, et le besoin n'était plus jamais RECALCULÉ —
    // supprimer l'appareil ne rétrécissait donc jamais les panneaux/la batterie. On REDÉRIVE
    // maintenant le besoin à CHAQUE rendu = max(besoin facture, besoin dicté par la conso).
    // Retirer un appareil « en plus » fait baisser le besoin conso → le système RÉTRÉCIT ;
    // sans appareil en plus le besoin conso ≈ le besoin facture → rien ne change.
    //
    // On garde le LATCH `neededAuto = false` (sinon `liveResolveFlat`, en mode auto, réécrit
    // `neededPanels` depuis la facture et écrase notre max), mais on n'en fait PLUS une
    // condition de sortie : la réversibilité vient du recalcul, pas du flag.
    if (inConsSizing) return;
    const annualCons = annualConsKwh ?? annualSummary().annualConsKwh;
    // Besoin DICTÉ PAR LA FACTURE seule (le socle, sans les « en plus »).
    const annualBill = annualConsumptionFromDaily(billDailyKwh());
    const billNeeded = annualBill > 0 ? clampNeeded(neededPanelsForTarget(annualBill, ctx.centroidLat)) : 0;
    // Besoin DICTÉ PAR LA CONSO (socle facture + Σ « en plus » composés dans consCurve).
    const consNeeded = annualCons > 0 ? clampNeeded(neededPanelsForTarget(annualCons, ctx.centroidLat)) : 0;
    const target = Math.max(billNeeded, consNeeded);
    if (target <= 0 || target === ctx.neededPanels) return;
    inConsSizing = true;
    ctx.neededPanels = target;
    ctx.neededAuto = false; // figé pour que liveResolveFlat ne réécrive pas notre max ;
    //                         la réversibilité vient du recalcul ci-dessus à chaque rendu.
    renderActive(); // re-résout l'optimiseur avec le nouveau besoin (chemin existant)
    inConsSizing = false;
  }

  /** Rendu du graphe de conso (barres glissables) + superposition production (or pâle). */
  function renderConsGraph() {
    const { consGraphEl } = dom;
    if (!consGraphEl) return;
    const W = 480;
    const H = 160;
    const padBottom = 16;
    const padTop = 8;
    const plotH = H - padTop - padBottom;
    const consCurve = ctx.consCurve;
    const prod = productionHourly();
    const maxC = consCurve.reduce((m, v) => Math.max(m, v), 0);
    const maxP = prod.reduce((m, v) => Math.max(m, v), 0);
    const max = Math.max(maxC, maxP, 1e-6);
    const slot = W / HOURS_PER_DAY;
    const barW = slot * 0.74;
    const yFor = (v: number) => padTop + (plotH - (v / max) * plotH);
    // Aire de production (or pâle) en arrière-plan.
    let prodPath = '';
    prod.forEach((v, h) => {
      const x = h * slot + slot / 2;
      prodPath += `${h === 0 ? 'M' : 'L'}${x.toFixed(1)} ${yFor(v).toFixed(1)} `;
    });
    const baseY = (H - padBottom).toFixed(1);
    const prodArea = maxP > 0
      ? `<path d="${prodPath}L${(W).toFixed(1)} ${baseY} L0 ${baseY} Z" fill="var(--color-brass-400,#e8b54a)" fill-opacity="0.10"/><path d="${prodPath}" fill="none" stroke="var(--color-brass-400,#e8b54a)" stroke-opacity="0.4" stroke-width="1.5"/>`
      : '';
    // Barres de conso (glissables) — chacune porte data-hour.
    const bars = consCurve
      .map((v, h) => {
        const x = h * slot + (slot - barW) / 2;
        const y = yFor(v);
        const barH = Math.max(0, H - padBottom - y);
        return `<rect class="rp9-cons-bar" data-hour="${h}" x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW.toFixed(1)}" height="${barH.toFixed(1)}" rx="1" fill="var(--color-azur-300,#7fb4e8)" fill-opacity="0.85" tabindex="0" role="slider" aria-label="Consommation à ${h} h" aria-valuenow="${v.toFixed(2)}"><title>${h} h : ${v.toFixed(2)} kWh</title></rect>`;
      })
      .join('');
    const ticks = [0, 6, 12, 18, 23]
      .map((h) => `<text x="${(h * slot + slot / 2).toFixed(1)}" y="${(H - 4).toFixed(1)}" text-anchor="middle" font-size="8" fill="var(--color-lune-faint,#6f7791)">${h}h</text>`)
      .join('');
    consGraphEl.innerHTML = `<line x1="0" y1="${baseY}" x2="${W}" y2="${baseY}" stroke="var(--color-white,#fff)" stroke-opacity="0.12" stroke-width="1"/>${prodArea}${bars}${ticks}`;
  }

  /** Saisie numérique des 24 heures (obligatoire mobile + mouvement réduit). */
  function renderConsInputs() {
    const { consInputsEl } = dom;
    if (!consInputsEl) return;
    consInputsEl.innerHTML = ctx.consCurve
      .map(
        (v, h) =>
          `<label class="rp9-cons-hour">${h}h<input type="text" inputmode="decimal" data-hour="${h}" value="${v.toFixed(2)}" aria-label="Consommation à ${h} h en kWh" /></label>`,
      )
      .join('');
  }

  /** Initiales des mois (mini-graphe W95) — jan→déc. */
  const MONTH_INITIALS = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];
  const MONTH_NAMES = [
    'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
    'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
  ];

  /** W96 — RETOUR SUR INVESTISSEMENT INDICATIF de la batterie. Affiche une fourchette
   *  d'années à côté du nombre de batteries recommandé, plafonnée à l'économie SUPPLÉMENTAIRE
   *  honnête (la part de l'économie annuelle qu'un report soir/nuit fait gagner). Quand il n'y
   *  a ni batterie ni économie honnête, `batteryPaybackYears` renvoie `years: null` → on
   *  N'AFFICHE RIEN (on n'invente jamais un retour). Toujours étiqueté « pas un devis ». */
  function renderBatteryPayback(batteries: number, savings: { low: number; high: number }) {
    const { consPaybackEl } = dom;
    if (!consPaybackEl) return;
    if (batteries <= 0) {
      consPaybackEl.hidden = true;
      consPaybackEl.textContent = '';
      return;
    }
    // L'économie ATTRIBUABLE à la batterie est, prudemment, l'économie annuelle d'autoconso :
    // sans report soir/nuit cette part serait perdue (surplus à zéro). On prend la borne BASSE
    // de la fourchette d'économies comme gain annuel additionnel honnête (jamais surévalué).
    const annualBattSaving = Math.max(0, savings.low);
    const payback = batteryPaybackYears(batteries, annualBattSaving);
    if (!payback.years) {
      consPaybackEl.hidden = true; // pas d'économie honnête → on n'invente pas de retour
      consPaybackEl.textContent = '';
      return;
    }
    const lo = Math.max(0, Math.round(payback.years.low));
    const hi = Math.max(lo, Math.round(payback.years.high));
    const range = lo === hi ? `≈ ${lo} ans` : `≈ ${lo} – ${hi} ans`;
    consPaybackEl.hidden = false;
    consPaybackEl.textContent = `Retour batterie ${range} · estimation indicative, pas un devis`;
  }

  /** W95 — MINI-GRAPHE SVG de l'autoconsommation MENSUELLE (12 barres). Hauteur RÉSERVÉE
   *  côté page (zéro CLS), sans transition (mouvement réduit). Une barre par mois, étiquetée
   *  par initiale, avec `<title>` détaillé pour le survol/lecteur d'écran. */
  function renderMonthlyChart(perMonthSelfKwh: number[]) {
    const { consMonthlyChartEl } = dom;
    if (!consMonthlyChartEl) return;
    const months = Array.isArray(perMonthSelfKwh) && perMonthSelfKwh.length === 12
      ? perMonthSelfKwh.map((v) => (Number.isFinite(v) && v > 0 ? v : 0))
      : new Array<number>(12).fill(0);
    const W = 360;
    const H = 120;
    const padBottom = 14;
    const padTop = 6;
    const plotH = H - padTop - padBottom;
    const max = months.reduce((m, v) => Math.max(m, v), 1e-6);
    const slot = W / 12;
    const barW = slot * 0.62;
    const baseY = (H - padBottom).toFixed(1);
    const bars = months
      .map((v, m) => {
        const x = m * slot + (slot - barW) / 2;
        const h = (v / max) * plotH;
        const y = H - padBottom - h;
        return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW.toFixed(1)}" height="${Math.max(0, h).toFixed(1)}" rx="1" fill="var(--color-brass-400,#e8b54a)" fill-opacity="0.7"><title>${MONTH_NAMES[m]} : ${fmt1(v)} kWh autoconsommés</title></rect>`;
      })
      .join('');
    const labels = MONTH_INITIALS
      .map((l, m) => `<text x="${(m * slot + slot / 2).toFixed(1)}" y="${(H - 3).toFixed(1)}" text-anchor="middle" font-size="7" fill="var(--color-lune-faint,#6f7791)">${l}</text>`)
      .join('');
    consMonthlyChartEl.innerHTML = `<line x1="0" y1="${baseY}" x2="${W}" y2="${baseY}" stroke="var(--color-white,#fff)" stroke-opacity="0.12" stroke-width="1"/>${bars}${labels}`;
  }

  /** W95 — état visuel des contrôles saisonniers (bascule + bloc des facteurs). */
  function renderSeasonalControls() {
    const { consSeasonalToggleEl, consSeasonalControlsEl, consSummerFactorEl, consWinterFactorEl } = dom;
    if (consSeasonalToggleEl) {
      consSeasonalToggleEl.setAttribute('aria-pressed', String(ctx.consSeasonal));
      consSeasonalToggleEl.textContent = ctx.consSeasonal ? 'Profil saisonnier : activé' : 'Profil saisonnier : désactivé';
    }
    if (consSeasonalControlsEl) consSeasonalControlsEl.hidden = !ctx.consSeasonal;
    // On NE réécrit la valeur des champs que s'ils ne sont pas en cours de saisie (focus).
    if (consSummerFactorEl && document.activeElement !== consSummerFactorEl) {
      consSummerFactorEl.value = String(ctx.consSummerFactor);
    }
    if (consWinterFactorEl && document.activeElement !== consWinterFactorEl) {
      consWinterFactorEl.value = String(ctx.consWinterFactor);
    }
  }

  /** Recompute complet de la conso (synthèse + graphe + saisie) + impact sizing/batterie. */
  function renderConsumption() {
    const { consWindowEl, consTotalEl, consSelfEl, consSavingsEl, consBattEl } = dom;
    if (!consWindowEl) return;
    // La fenêtre n'apparaît que lorsqu'un plan de production existe.
    const ready = !!ctx.prodScaled && ctx.prodPanels > 0;
    consWindowEl.hidden = !ready;
    if (!ready) return;
    rebuildConsCurve();
    if (!ctx.consMode) return; // panneau replié : rien à dessiner

    const dailyTotal = curveTotal(ctx.consCurve);
    // W82 — la synthèse de TÊTE (autoconso/économies/batterie) est l'INTÉGRALE ANNUELLE
    // 12 mois, donc INVARIANTE au mois de production affiché (le graphe reste mois-aware).
    const summary = annualSummary();

    if (consTotalEl) consTotalEl.textContent = `${fmt1(dailyTotal)} kWh`;
    if (consSelfEl) consSelfEl.textContent = `${fmt1(summary.selfDailyAvgKwh)} kWh/j`;
    if (consSavingsEl) consSavingsEl.textContent = summary.annualConsKwh > 0 ? fmtSavings(summary.savings.low, summary.savings.high) + ' MAD' : '—';
    if (consBattEl) consBattEl.textContent = summary.batteries > 0 ? `${summary.batteries} × 6 kWh` : 'aucune';

    renderBatteryPayback(summary.batteries, summary.savings);
    renderMonthlyChart(summary.perMonthSelfKwh);
    renderSeasonalControls();
    renderConsGraph();
    renderConsInputs();
    renderApplianceList();
    applyConsumptionToSizing(summary.annualConsKwh);
  }

  /** Liste des appareils ajoutés : créneau + bascule « en plus » / « déjà compris » + suppr. */
  function renderApplianceList() {
    const { applListEl } = dom;
    if (!applListEl) return;
    const consAppliances = ctx.consAppliances;
    if (consAppliances.length === 0) {
      applListEl.innerHTML = '<li class="text-xs text-lune-faint">Aucun appareil ajouté — votre courbe suit le type calé sur la facture.</li>';
      return;
    }
    applListEl.innerHTML = consAppliances
      .map((a, i) => {
        const onTop = a.billing === 'onTop';
        return `<li class="flex flex-wrap items-center gap-x-3 gap-y-1 border border-white/10 bg-nuit-900/40 p-3 text-sm" data-appl="${i}">
          <span class="font-semibold text-white">${esc(a.label)}</span>
          <span class="text-xs text-lune-faint">${fmt1(a.dailyKwh)} kWh/j · ${a.startHour}h–${((a.endHour % 24) + 24) % 24}h</span>
          <button type="button" data-appl-toggle="${i}" class="ml-auto border px-2.5 py-1 text-xs font-semibold transition-colors ${onTop ? 'border-brass-400 text-brass-300' : 'border-white/25 text-lune-soft'}">${onTop ? 'En plus de la facture' : 'Déjà compris'}</button>
          <button type="button" data-appl-del="${i}" aria-label="Supprimer" class="border border-alert-300/60 px-2.5 py-1 text-xs font-semibold text-alert-300 transition-colors hover:bg-alert-300/10">×</button>
        </li>`;
      })
      .join('');
  }

  /** Recompute UNIQUEMENT la synthèse (total/autoconso/économies/batterie) sans
   *  retoucher la saisie ni la liste — pour ne pas casser le focus pendant l'édition. */
  function renderConsumptionSummaryOnly() {
    const { consTotalEl, consSelfEl, consSavingsEl, consBattEl } = dom;
    if (!ctx.prodScaled || !ctx.consMode) return;
    const dailyTotal = curveTotal(ctx.consCurve);
    const summary = annualSummary(); // W82 — intégrale annuelle, invariante au mois affiché
    if (consTotalEl) consTotalEl.textContent = `${fmt1(dailyTotal)} kWh`;
    if (consSelfEl) consSelfEl.textContent = `${fmt1(summary.selfDailyAvgKwh)} kWh/j`;
    if (consSavingsEl) consSavingsEl.textContent = summary.annualConsKwh > 0 ? fmtSavings(summary.savings.low, summary.savings.high) + ' MAD' : '—';
    if (consBattEl) consBattEl.textContent = summary.batteries > 0 ? `${summary.batteries} × 6 kWh` : 'aucune';
    renderBatteryPayback(summary.batteries, summary.savings);
    renderMonthlyChart(summary.perMonthSelfKwh);
  }

  function populateConsSelects() {
    const { applKindEl, acBtuEl, evKwEl } = dom;
    if (applKindEl && applKindEl.options.length === 0) {
      for (const t of APPLIANCE_TYPICALS) {
        const o = document.createElement('option');
        o.value = t.kind;
        o.textContent = t.label;
        applKindEl.appendChild(o);
      }
      const other = document.createElement('option');
      other.value = 'autre';
      other.textContent = 'Autre appareil…';
      applKindEl.appendChild(other);
    }
    if (acBtuEl && acBtuEl.options.length === 0) {
      for (const p of AC_BTU_PRESETS) {
        const o = document.createElement('option');
        o.value = String(p.btu);
        o.textContent = `${fmtInt(p.btu)} BTU (≈ ${p.cv} CV)`;
        acBtuEl.appendChild(o);
      }
    }
    if (evKwEl && evKwEl.options.length === 0) {
      for (const kw of EV_CHARGER_KW_PRESETS) {
        const o = document.createElement('option');
        o.value = String(kw);
        o.textContent = `${fmt1(kw)} kW`;
        evKwEl.appendChild(o);
      }
      evKwEl.value = '7.4';
    }
  }

  function wire() {
    const {
      consToggleEl, consPanelEl, applKindEl, applAcEl, applEvEl, acBtuEl, acEerEl, acHoursEl,
      acWattsEl, applAddEl, evKmEl, evKwEl, evHoursEl, applNoteEl, applListEl, consRecalEl,
      consResetEl, consInputsEl, consGraphEl, consSeasonalToggleEl, consSummerFactorEl,
      consWinterFactorEl,
    } = dom;

    populateConsSelects();

    // Ouvrir / fermer le panneau d'affinage.
    consToggleEl?.addEventListener('click', () => {
      ctx.consMode = !ctx.consMode;
      consToggleEl.setAttribute('aria-expanded', String(ctx.consMode));
      if (consPanelEl) consPanelEl.hidden = !ctx.consMode;
      renderConsumption();
    });

    // Saisie / preset spécifiques selon l'appareil choisi.
    function syncApplianceInputs() {
      const kind = applKindEl?.value ?? '';
      if (applAcEl) applAcEl.hidden = kind !== 'clim';
      if (applEvEl) applEvEl.hidden = kind !== 'ev';
      if (kind === 'clim') refreshAcWatts();
    }
    applKindEl?.addEventListener('change', syncApplianceInputs);
    syncApplianceInputs();

    function readNum(el: HTMLInputElement | null, fallback: number): number {
      const v = parseFloat((el?.value ?? '').replace(',', '.'));
      return Number.isFinite(v) && v > 0 ? v : fallback;
    }

    function refreshAcWatts() {
      const btu = readNum(acBtuEl as unknown as HTMLInputElement, 9000);
      const eer = readNum(acEerEl, AC_EER_DEFAULT_NON_INVERTER);
      const hours = readNum(acHoursEl, 6);
      const watts = acWattsFromBtu(btu, eer);
      const kwh = kwhFromWattsHours(watts, hours);
      if (acWattsEl) acWattsEl.textContent = `≈ ${fmtInt(Math.round(watts))} W · ${fmt1(kwh)} kWh/j`;
    }
    acBtuEl?.addEventListener('change', refreshAcWatts);
    acEerEl?.addEventListener('input', refreshAcWatts);
    acHoursEl?.addEventListener('input', refreshAcWatts);

    // Ajouter un appareil → recompose la courbe et recompute tout.
    applAddEl?.addEventListener('click', () => {
      const kind = applKindEl?.value ?? '';
      let appliance: Appliance | null = null;
      if (kind === 'clim') {
        const btu = readNum(acBtuEl as unknown as HTMLInputElement, 9000);
        const eer = readNum(acEerEl, AC_EER_DEFAULT_NON_INVERTER);
        const hours = readNum(acHoursEl, 6);
        const watts = acWattsFromBtu(btu, eer);
        // W84 — le créneau respecte les HEURES SAISIES (slotEndHour) au lieu d'un 13–23 codé
        // en dur qui étalait une clim « 3 h » sur 10 h (forme d'autoconso faussée).
        const startHour = 13;
        appliance = { kind: 'clim', label: `Climatisation ${fmtInt(btu)} BTU`, dailyKwh: kwhFromWattsHours(watts, hours), startHour, endHour: slotEndHour(startHour, hours), billing: 'onTop' };
      } else if (kind === 'ev') {
        const km = parseFloat((evKmEl?.value ?? '').replace(',', '.'));
        const hours = readNum(evHoursEl, 3);
        let kwh: number;
        if (Number.isFinite(km) && km > 0) {
          kwh = evKwhFromDistance(km, EV_KWH_PER_100KM_DEFAULT);
        } else {
          const kw = readNum(evKwEl as unknown as HTMLInputElement, 7.4);
          kwh = kwhFromWattsHours(kw * 1000, hours);
        }
        // W84 — créneau VE depuis les heures saisies (slotEndHour), pas le 11–15 codé en dur.
        const startHour = 11;
        appliance = { kind: 'ev', label: 'Recharge voiture électrique', dailyKwh: kwh, startHour, endHour: slotEndHour(startHour, hours), billing: 'onTop' };
      } else if (kind === 'autre') {
        appliance = { kind: 'autre', label: `Autre appareil ${++ctx.consApplCounter}`, dailyKwh: 1, startHour: 18, endHour: 22, billing: 'onTop' };
      } else {
        const t = APPLIANCE_TYPICALS.find((x) => x.kind === kind);
        if (t) appliance = applianceFromTypical(t);
      }
      if (!appliance) return;
      ctx.consAppliances.push(appliance);
      ctx.consHandEdited = false; // un nouvel appareil recompose la courbe (l'override manuel est repris)
      if (applNoteEl) applNoteEl.textContent = `${appliance.label} ajouté (${fmt1(appliance.dailyKwh)} kWh/j).`;
      renderConsumption();
    });

    // Bascule « en plus » ↔ « déjà compris » et suppression d'un appareil (délégation).
    applListEl?.addEventListener('click', (e) => {
      const t = e.target as HTMLElement;
      const toggle = t.closest<HTMLElement>('[data-appl-toggle]');
      const del = t.closest<HTMLElement>('[data-appl-del]');
      if (toggle) {
        const i = parseInt(toggle.dataset.applToggle ?? '', 10);
        const a = ctx.consAppliances[i];
        if (a) {
          a.billing = a.billing === 'onTop' ? 'inBill' : 'onTop';
          ctx.consHandEdited = false;
          renderConsumption();
        }
      } else if (del) {
        const i = parseInt(del.dataset.applDel ?? '', 10);
        if (i >= 0 && i < ctx.consAppliances.length) {
          ctx.consAppliances.splice(i, 1);
          ctx.consHandEdited = false;
          renderConsumption();
        }
      }
    });

    // « Recaler sur ma facture » (W83) : remet le total de la courbe ÉDITÉE à la cible
    // facture + Σ « en plus ». L'ancienne version recalait sur la SEULE facture, EFFAÇANT
    // l'énergie des appareils « en plus » (clim/VE neufs pas encore dans la facture) — le
    // recalage ne doit que reproportionner la FORME, jamais supprimer cette énergie légitime.
    consRecalEl?.addEventListener('click', () => {
      ctx.consCurve = rescaleToDaily(ctx.consCurve, billDailyKwh() + onTopDailyKwh());
      ctx.consHandEdited = true; // c'est un override manuel recalé
      renderConsumption();
    });

    // « Réinitialiser la courbe » (W83) : efface l'override manuel et RECONSTRUIT la courbe
    // depuis le socle facture + appareils composés — la forme calculée est ainsi RESTAURABLE
    // après n'importe quelle édition à la main.
    consResetEl?.addEventListener('click', () => {
      ctx.consHandEdited = false;
      rebuildConsCurve();
      renderConsumption();
    });

    // W95 — bascule du profil saisonnier (été ≠ hiver). Active/désactive l'intégrale 12 mois
    // saisonnière qui change HONNÊTEMENT l'autoconsommation annuelle.
    consSeasonalToggleEl?.addEventListener('click', () => {
      ctx.consSeasonal = !ctx.consSeasonal;
      renderConsumption();
    });

    // W95 — facteurs été/hiver (jamais rejetés ; tout nombre fini > 0 accepté, sinon neutre 1).
    function readFactor(el: HTMLInputElement | null): number {
      const v = parseFloat((el?.value ?? '').replace(',', '.'));
      return Number.isFinite(v) && v > 0 ? v : 1;
    }
    consSummerFactorEl?.addEventListener('input', () => {
      ctx.consSummerFactor = readFactor(consSummerFactorEl);
      renderConsumptionSummaryOnly();
    });
    consWinterFactorEl?.addEventListener('input', () => {
      ctx.consWinterFactor = readFactor(consWinterFactorEl);
      renderConsumptionSummaryOnly();
    });

    // Saisie numérique des heures (délégation sur le conteneur).
    consInputsEl?.addEventListener('input', (e) => {
      const inp = e.target as HTMLInputElement;
      const h = parseInt(inp.dataset.hour ?? '', 10);
      if (!Number.isFinite(h) || h < 0 || h >= HOURS_PER_DAY) return;
      const v = parseFloat((inp.value || '').replace(',', '.'));
      ctx.consCurve[h] = Number.isFinite(v) && v >= 0 ? v : 0;
      ctx.consHandEdited = true;
      // On ne re-rend pas la saisie (curseur), seulement le reste de la synthèse.
      renderConsGraph();
      renderConsumptionSummaryOnly();
    });

    // Glissé d'une barre du graphe de conso (pointer) — fallback tactile + tap.
    let consDragHour: number | null = null;
    function hourFromEvent(target: EventTarget | null): number | null {
      const rect = (target as HTMLElement | null)?.closest<HTMLElement>('[data-hour]');
      if (!rect) return null;
      const h = parseInt(rect.dataset.hour ?? '', 10);
      return Number.isFinite(h) ? h : null;
    }
    function valueFromPointer(clientY: number): number {
      if (!consGraphEl) return 0;
      const box = consGraphEl.getBoundingClientRect();
      const H = 160;
      const padTop = 8;
      const padBottom = 16;
      const plotH = H - padTop - padBottom;
      // Position relative dans le SVG (viewBox 0..160 en Y).
      const yViewBox = ((clientY - box.top) / box.height) * H;
      const frac = Math.max(0, Math.min(1, (H - padBottom - yViewBox) / plotH));
      const prod = productionHourly();
      const maxC = ctx.consCurve.reduce((m, v) => Math.max(m, v), 0);
      const maxP = prod.reduce((m, v) => Math.max(m, v), 0);
      // Même plancher d'échelle que renderConsGraph (1e-6) : sinon le glissé et le dessin
      // des barres utilisent deux échelles différentes et la barre saisie ne suit pas le doigt.
      const max = Math.max(maxC, maxP, 1e-6);
      return frac * max;
    }
    consGraphEl?.addEventListener('pointerdown', (e) => {
      const h = hourFromEvent(e.target);
      if (h == null) return;
      consDragHour = h;
      (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
      ctx.consCurve[h] = valueFromPointer(e.clientY);
      ctx.consHandEdited = true;
      renderConsGraph();
      renderConsumptionSummaryOnly();
      e.preventDefault();
    });
    consGraphEl?.addEventListener('pointermove', (e) => {
      if (consDragHour == null) return;
      ctx.consCurve[consDragHour] = valueFromPointer(e.clientY);
      renderConsGraph();
      renderConsumptionSummaryOnly();
    });
    const endConsDrag = () => {
      if (consDragHour == null) return;
      consDragHour = null;
      renderConsInputs(); // resynchronise la saisie numérique après un glissé
      renderConsumption();
    };
    consGraphEl?.addEventListener('pointerup', endConsDrag);
    consGraphEl?.addEventListener('pointercancel', endConsDrag);
    // Clavier (mouvement réduit / accessibilité) : ↑/↓ ajuste la barre focalisée.
    consGraphEl?.addEventListener('keydown', (e) => {
      const h = hourFromEvent(e.target);
      if (h == null) return;
      const step = e.shiftKey ? 0.5 : 0.1;
      if (e.key === 'ArrowUp') ctx.consCurve[h] += step;
      else if (e.key === 'ArrowDown') ctx.consCurve[h] = Math.max(0, ctx.consCurve[h] - step);
      else return;
      ctx.consHandEdited = true;
      e.preventDefault();
      renderConsGraph();
      renderConsInputs();
      renderConsumptionSummaryOnly();
    });
  }

  return {
    billDailyKwh,
    productionHourly,
    rebuildConsCurve,
    applyConsumptionToSizing,
    renderConsGraph,
    renderConsInputs,
    renderConsumption,
    renderApplianceList,
    renderConsumptionSummaryOnly,
    wire,
  };
}
