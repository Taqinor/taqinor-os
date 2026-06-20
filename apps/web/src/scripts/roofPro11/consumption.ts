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
  emptyCurve,
  curveTotal,
  baselineCurve,
  composeConsumption,
  rescaleToDaily,
  selfConsumptionDailyKwh,
  savingsFromHourly,
  annualConsumptionFromDaily,
  batterySizing,
  acWattsFromBtu,
  kwhFromWattsHours,
  evKwhFromDistance,
  applianceFromTypical,
  APPLIANCE_TYPICALS,
  AC_BTU_PRESETS,
  AC_EER_DEFAULT_NON_INVERTER,
  EV_CHARGER_KW_PRESETS,
  EV_KWH_PER_100KM_DEFAULT,
  type Appliance,
  type HourlyCurve,
} from '../../lib/applianceConsumption';
import { billToAnnualKwh, neededPanelsForTarget, tariffForCity } from '../../lib/estimatorBrainV2';
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
  function applyConsumptionToSizing() {
    if (!ctx.neededAuto || inConsSizing) return;
    const dailyTotal = curveTotal(ctx.consCurve);
    const annualCons = annualConsumptionFromDaily(dailyTotal);
    if (annualCons <= 0) return;
    const n = neededPanelsForTarget(annualCons, ctx.centroidLat);
    if (n <= 0) return;
    const clamped = clampNeeded(n);
    if (clamped === ctx.neededPanels) return;
    inConsSizing = true;
    ctx.neededPanels = clamped;
    ctx.neededAuto = false; // besoin issu de la conso → figé (liveResolveFlat ne le réécrit plus)
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

    const consCurve = ctx.consCurve;
    const prod = productionHourly();
    const dailyTotal = curveTotal(consCurve);
    const annualCons = annualConsumptionFromDaily(dailyTotal);
    const selfDaily = selfConsumptionDailyKwh(consCurve, prod);
    const savings = savingsFromHourly(consCurve, prod, annualCons, tariffForCity(undefined));
    const batt = batterySizing(consCurve, prod);

    if (consTotalEl) consTotalEl.textContent = `${fmt1(dailyTotal)} kWh`;
    if (consSelfEl) consSelfEl.textContent = `${fmt1(selfDaily)} kWh/j`;
    if (consSavingsEl) consSavingsEl.textContent = annualCons > 0 ? fmtSavings(savings.low, savings.high) + ' MAD' : '—';
    if (consBattEl) consBattEl.textContent = batt.batteries > 0 ? `${batt.batteries} × 6 kWh` : 'aucune';

    renderConsGraph();
    renderConsInputs();
    renderApplianceList();
    applyConsumptionToSizing();
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
    const consCurve = ctx.consCurve;
    const prod = productionHourly();
    const dailyTotal = curveTotal(consCurve);
    const annualCons = annualConsumptionFromDaily(dailyTotal);
    const selfDaily = selfConsumptionDailyKwh(consCurve, prod);
    const savings = savingsFromHourly(consCurve, prod, annualCons, tariffForCity(undefined));
    const batt = batterySizing(consCurve, prod);
    if (consTotalEl) consTotalEl.textContent = `${fmt1(dailyTotal)} kWh`;
    if (consSelfEl) consSelfEl.textContent = `${fmt1(selfDaily)} kWh/j`;
    if (consSavingsEl) consSavingsEl.textContent = annualCons > 0 ? fmtSavings(savings.low, savings.high) + ' MAD' : '—';
    if (consBattEl) consBattEl.textContent = batt.batteries > 0 ? `${batt.batteries} × 6 kWh` : 'aucune';
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
      consInputsEl, consGraphEl,
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
        appliance = { kind: 'clim', label: `Climatisation ${fmtInt(btu)} BTU`, dailyKwh: kwhFromWattsHours(watts, hours), startHour: 13, endHour: 23, billing: 'onTop' };
      } else if (kind === 'ev') {
        const km = parseFloat((evKmEl?.value ?? '').replace(',', '.'));
        let kwh: number;
        if (Number.isFinite(km) && km > 0) {
          kwh = evKwhFromDistance(km, EV_KWH_PER_100KM_DEFAULT);
        } else {
          const kw = readNum(evKwEl as unknown as HTMLInputElement, 7.4);
          const hours = readNum(evHoursEl, 3);
          kwh = kwhFromWattsHours(kw * 1000, hours);
        }
        appliance = { kind: 'ev', label: 'Recharge voiture électrique', dailyKwh: kwh, startHour: 11, endHour: 15, billing: 'onTop' };
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

    // « Recaler sur ma facture » : remet le total de la courbe ÉDITÉE à la valeur facture.
    consRecalEl?.addEventListener('click', () => {
      ctx.consCurve = rescaleToDaily(ctx.consCurve, billDailyKwh());
      ctx.consHandEdited = true; // c'est un override manuel recalé
      renderConsumption();
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
