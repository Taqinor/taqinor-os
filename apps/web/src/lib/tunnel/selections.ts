// RWEB17-M3 — SECTION « SÉLECTIONS » du tunnel « mon-toit » (FR/EN/AR) : créneau
// de visite, occupation de la journée, équipements, « journée type », groupes de
// cartes (pro / commercial / industriel / agricole), cultures, heures de
// pompage, facture mensuelle.
//
// Extrait À L'IDENTIQUE de la page FR (code vérifié identique sur les trois
// locales, aux commentaires près). Seules divergences, réglées par locale :
//   - `renderJourType(<locale>)` (la page AR l'appelle plus tôt, avant le
//     funnel : ordre sans effet, c'est un rendu DOM pur) ;
//   - le libellé de la tranche détectée (`syncBillRangeFromExact`) : FR
//     `billRangeLabel`, EN table anglaise, AR texte de l'`<option>` (repli
//     `billRangeLabel`).
// Possède les 15 `let` de sélection de `ctx.etat` (visitWindowPart,
// visitWindowWeek, occupationJour, proUnit, tension, activity, tensionTouched,
// activityTouched, surfaceType, waterSource, waterUnit, commercialCategory,
// ccUnit, equipes, regionAgricole). Le classement des cartes reste celui de
// `cardSelectedWJ117` (aria-pressed + classes de bordure). Aucune page ne
// l'importe encore (M13).
//
// CROCHETS REQUIS : `markDataEntered`, `saveWizardState` (persistance) et
// `computeEstimate` (estimation). INSCRITS ICI : `syncEquipDetails`,
// `resolveMonthlyBill`, `syncBillRangeFromExact`, `wireCardGroup`,
// `syncOccupancySelection`, `syncCultureCards`, `syncHeuresLabel`.
//
// PHASES : `brancherVisiteOccupationEquipements()` (FR l. 2646-2799, avant le
// boot de la carte) puis `brancherGroupes()` (FR l. 3198-3330, après la
// réhydratation).

import { billRangeFromExact, billRangeLabel, type BillRangeId } from '../billRange';
import { OCCUPANCY_IDS, OCCUPANCY_SHAPES, type OccupancyId } from '../dayProfiles';
import { renderJourType } from '../../scripts/tunnel/jourType';
import type { ContexteTunnel } from './contexte';
import type { LocaleTunnel } from './etat';

const OCC_COLORS: Record<OccupancyId, { stroke: string; dash: string | null; fill?: string }> = {
  presence_jour: { stroke: '#2a78d6', dash: null, fill: 'rgba(42,120,214,0.10)' },
  absence_jour: { stroke: '#eb6834', dash: '6,3' },
  presence_partielle: { stroke: '#1baf7a', dash: '2,3' },
};
// Lead.occupation_jour n'utilise PAS le vocabulaire des identifiants d'affichage
// OCCUPANCY_IDS — cette table est la SEULE traduction entre les deux.
const OCC_TO_LEAD_FIELD: Record<OccupancyId, 'present' | 'absent' | 'partiel'> = {
  presence_jour: 'present', absence_jour: 'absent', presence_partielle: 'partiel',
};

const EQUIP_TOGGLES: Array<{ checkId: string; detailId?: string }> = [
  { checkId: 'mt-equip-chauffe-eau', detailId: 'mt-equip-chauffe-eau-kw' },
  { checkId: 'mt-equip-ve', detailId: 'mt-equip-ve-km' },
  { checkId: 'mt-equip-clim', detailId: 'mt-equip-clim-pieces' },
  { checkId: 'mt-equip-piscine', detailId: 'mt-equip-piscine-kw' },
];

/** Milieu indicatif d'une tranche (MAD) — uniquement pour ESTIMER quand le
 *  montant exact est absent ; jamais pour le seuil. */
export const RANGE_MIDPOINT: Record<string, number> = {
  'lt800': 600, '800-1000': 900, '1000-1500': 1250, '1500-3000': 2250,
  '3000-5000': 4000, '5000-10000': 7500, 'gt10000': 12000,
};

/** Libellés anglais des tranches (page EN). */
export const BILL_RANGE_LABEL_EN: Record<string, string> = {
  lt800: 'Under 800 MAD',
  '800-1000': '800 – 1,000 MAD',
  '1000-1500': '1,000 – 1,500 MAD',
  '1500-3000': '1,500 – 3,000 MAD',
  '3000-5000': '3,000 – 5,000 MAD',
  '5000-10000': '5,000 – 10,000 MAD',
  gt10000: 'Over 10,000 MAD',
};

/** Libellé affiché pour la tranche détectée, par locale. */
function libelleTranche(locale: LocaleTunnel, rid: BillRangeId, billSelect: HTMLSelectElement): string {
  if (locale === 'en') return BILL_RANGE_LABEL_EN[rid] ?? '';
  if (locale === 'ar') {
    const opt = billSelect.querySelector<HTMLOptionElement>(`option[value="${rid}"]`);
    return (opt?.textContent ?? '').trim() || billRangeLabel(rid);
  }
  return billRangeLabel(rid);
}

export interface OptionsGroupe {
  allowUnset?: boolean;
  recompute?: boolean;
  onChange?: () => void;
}

export interface Selections {
  wireVisitToggle: (selector: string, getCurrent: () => string, setCurrent: (v: string) => void) => void;
  wireCardGroup: (selector: string, getCurrent: () => string, setCurrent: (v: string) => void, opts?: OptionsGroupe) => void;
  syncOccupancySelection: () => void;
  syncEquipDetails: () => void;
  syncCultureCards: () => void;
  syncHeuresLabel: () => void;
  resolveMonthlyBill: () => number | null;
  syncBillRangeFromExact: () => void;
  brancherVisiteOccupationEquipements: () => void;
  brancherGroupes: () => void;
}

export function installerSelections(ctx: ContexteTunnel): Selections {
  const { etat, dom, crochets } = ctx;
  const { doc, $, val, num, setFieldError, maxBillFor, occShapePaths } = dom;
  const marquerEtSauver = () => {
    crochets.appeler('markDataEntered');
    crochets.appeler('saveWizardState');
  };

  // ——— W353 : créneau de visite technique — deux puces à bascule unique INDÉPENDANTES ———
  function wireVisitToggle(selector: string, getCurrent: () => string, setCurrent: (v: string) => void) {
    doc.querySelectorAll<HTMLButtonElement>(selector).forEach((btn) => {
      btn.addEventListener('click', () => {
        const same = getCurrent() === btn.dataset.value;
        setCurrent(same ? '' : (btn.dataset.value || ''));
        doc.querySelectorAll<HTMLButtonElement>(selector).forEach((b) => {
          const on = !same && b === btn;
          b.setAttribute('aria-pressed', String(on));
          b.classList.toggle('border-brass-400', on);
          b.classList.toggle('border-white/15', !on);
        });
        marquerEtSauver();
      });
    });
    const current = getCurrent();
    if (current) {
      doc.querySelectorAll<HTMLButtonElement>(selector).forEach((b) => {
        const on = b.dataset.value === current;
        b.setAttribute('aria-pressed', String(on));
        b.classList.toggle('border-brass-400', on);
        b.classList.toggle('border-white/15', !on);
      });
    }
  }

  // ——— L-WEBT : « Passez-vous la journée à la maison ? » — trois silhouettes 24 h ———
  function renderOccupancyChart() {
    const svg = $('mt-occ-chart');
    if (!svg) return;
    const W = 320;
    const H = 140;
    const PAD = 8;
    let markup = '';
    for (const id of OCCUPANCY_IDS) {
      const shape = OCCUPANCY_SHAPES[id];
      const { line, area } = occShapePaths(shape, W, H, PAD);
      const c = OCC_COLORS[id];
      if (c.fill) markup += `<path d="${area}" fill="${c.fill}" stroke="none"></path>`;
      markup += `<path data-occ-line="${id}" d="${line}" fill="none" stroke="${c.stroke}" stroke-width="2"${c.dash ? ` stroke-dasharray="${c.dash}"` : ''}></path>`;
    }
    svg.innerHTML = markup;
  }
  function syncOccupancySelection() {
    doc.querySelectorAll<HTMLButtonElement>('.mt-occ-btn').forEach((btn) => {
      const id = (btn.dataset.occId || '') as OccupancyId;
      const field = OCC_TO_LEAD_FIELD[id];
      const on = !!field && etat.occupationJour === field;
      btn.setAttribute('aria-pressed', String(on));
      btn.classList.toggle('border-brass-400', on);
      btn.classList.toggle('border-white/15', !on);
      const badge = btn.querySelector<HTMLElement>('.mt-occ-chosen');
      if (badge) badge.hidden = !on;
    });
    doc.querySelectorAll<SVGPathElement>('[data-occ-line]').forEach((p) => {
      const id = (p.getAttribute('data-occ-line') || '') as OccupancyId;
      const on = !etat.occupationJour || OCC_TO_LEAD_FIELD[id] === etat.occupationJour;
      p.style.opacity = on ? '1' : '0.25';
      p.setAttribute('stroke-width', OCC_TO_LEAD_FIELD[id] === etat.occupationJour ? '3' : '2');
    });
    const hidden = $('mt-occupation-jour') as HTMLInputElement | null;
    if (hidden) hidden.value = etat.occupationJour;
  }

  // ——— L-WEBT : équipements (facultatifs) — la case révèle son détail SEULEMENT si cochée ———
  // Ré-appelée après la réhydratation WJ61 : `.checked` par script ne déclenche pas `change`.
  function syncEquipDetails() {
    for (const { checkId, detailId } of EQUIP_TOGGLES) {
      const chk = $(checkId) as HTMLInputElement | null;
      const detail = detailId ? $(detailId) : null;
      const wrap = detail?.closest<HTMLElement>('[data-equip-detail]') || null;
      if (wrap) wrap.hidden = !chk?.checked;
    }
  }

  function brancherVisiteOccupationEquipements() {
    wireVisitToggle('.mt-visit-part', () => etat.visitWindowPart, (v) => { etat.visitWindowPart = v; });
    wireVisitToggle('.mt-visit-week', () => etat.visitWindowWeek, (v) => { etat.visitWindowWeek = v; });
    renderOccupancyChart();
    doc.querySelectorAll<HTMLButtonElement>('.mt-occ-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const id = (btn.dataset.occId || '') as OccupancyId;
        const field = OCC_TO_LEAD_FIELD[id];
        if (!field) return;
        etat.occupationJour = etat.occupationJour === field ? '' : field;
        syncOccupancySelection();
        marquerEtSauver();
      });
    });
    syncOccupancySelection();
    for (const { checkId } of EQUIP_TOGGLES) {
      const chk = $(checkId) as HTMLInputElement | null;
      chk?.addEventListener('change', () => { syncEquipDetails(); marquerEtSauver(); });
    }
    syncEquipDetails();
    // QJR664 — « Une journée type » : rendu partagé fr/en/ar.
    renderJourType(ctx.locale, doc);
  }

  // ——— QX : groupes de cartes/segments à sélection unique (aria-pressed) ———
  function wireCardGroup(
    selector: string,
    getCurrent: () => string,
    setCurrent: (v: string) => void,
    opts: OptionsGroupe = {},
  ) {
    const paint = () => {
      const current = getCurrent();
      doc.querySelectorAll<HTMLButtonElement>(selector).forEach((b) => {
        const on = current !== '' && b.dataset.value === current;
        b.setAttribute('aria-pressed', String(on));
        b.classList.toggle('border-brass-400', on);
        b.classList.toggle('border-white/15', !on);
      });
    };
    doc.querySelectorAll<HTMLButtonElement>(selector).forEach((btn) => {
      btn.addEventListener('click', () => {
        const same = getCurrent() === btn.dataset.value;
        setCurrent(same && opts.allowUnset ? '' : (btn.dataset.value || ''));
        paint();
        opts.onChange?.();
        marquerEtSauver();
        if (opts.recompute) crochets.appeler('computeEstimate');
      });
    });
    paint();
  }

  const cultureSelect = $('mt-culture') as HTMLSelectElement | null;
  function syncCultureCards() {
    const current = cultureSelect?.value || '';
    doc.querySelectorAll<HTMLButtonElement>('.mt-culture-card').forEach((b) => {
      const on = current !== '' && b.dataset.value === current;
      b.setAttribute('aria-pressed', String(on));
      b.classList.toggle('border-brass-400', on);
      b.classList.toggle('border-white/15', !on);
    });
  }
  const heuresInput = $('mt-heures-pompage') as HTMLInputElement | null;
  function syncHeuresLabel() {
    const out = $('mt-heures-pompage-value');
    if (out && heuresInput) out.textContent = `${heuresInput.value} h`;
  }

  function brancherGroupes() {
    wireCardGroup('.mt-pro-unit', () => etat.proUnit, (v) => { etat.proUnit = v || 'mad'; }, { recompute: true });
    wireCardGroup('.mt-tension', () => etat.tension, (v) => { etat.tension = v || 'bt'; etat.tensionTouched = true; }, { recompute: true });
    wireCardGroup('.mt-activity', () => etat.activity, (v) => { etat.activity = v || 'day'; etat.activityTouched = true; }, { recompute: true });
    wireCardGroup('.mt-surface-type', () => etat.surfaceType, (v) => { etat.surfaceType = v; }, { allowUnset: true, recompute: true });
    // WJ122 — COMMERCIAL : cartes catégorie + bascule d'unité de facture.
    wireCardGroup('.mt-commercial-cat', () => etat.commercialCategory, (v) => { etat.commercialCategory = v; }, { allowUnset: true, recompute: true });
    wireCardGroup('.mt-cc-unit', () => etat.ccUnit, (v) => { etat.ccUnit = v || 'mad'; }, { recompute: true });
    // WJ123 — INDUSTRIEL : pattern d'équipes.
    wireCardGroup('.mt-equipes', () => etat.equipes, (v) => { etat.equipes = v; }, { allowUnset: true, recompute: true });
    // WJ124 — AGRICOLE : région (moteur eau) ; culture synchronise le <select> sr-only.
    wireCardGroup('.mt-region-card', () => etat.regionAgricole, (v) => { etat.regionAgricole = v; }, { allowUnset: true, recompute: true });
    doc.querySelectorAll<HTMLButtonElement>('.mt-culture-card').forEach((btn) => {
      btn.addEventListener('click', () => {
        if (cultureSelect) cultureSelect.value = cultureSelect.value === btn.dataset.value ? '' : (btn.dataset.value || '');
        syncCultureCards();
        marquerEtSauver();
        crochets.appeler('computeEstimate');
      });
    });
    syncCultureCards();
    wireCardGroup('.mt-water-source', () => etat.waterSource, (v) => { etat.waterSource = v; }, { allowUnset: true, recompute: true });
    wireCardGroup('.mt-water-unit', () => etat.waterUnit, (v) => { etat.waterUnit = v || 'm3h'; }, { recompute: true });
    // AGW403 — `data-touche="1"` posé dès le premier événement input/change du curseur.
    const marquerHeuresTouchees = () => { if (heuresInput) heuresInput.dataset.touche = '1'; };
    heuresInput?.addEventListener('change', marquerHeuresTouchees);
    heuresInput?.addEventListener('input', () => {
      marquerHeuresTouchees();
      syncHeuresLabel();
      crochets.appeler('computeEstimate');
    });
    syncHeuresLabel();
    // Recalcul en direct sur chaque champ numérique qui pilote un chiffre affiché.
    for (const id of ['mt-pro-bill', 'mt-cc-bill', 'mt-surface-m2', 'mt-profondeur', 'mt-hmt', 'mt-water-need', 'mt-fuel-spend']) {
      $(id)?.addEventListener('input', () => crochets.appeler('computeEstimate'));
    }
  }

  // ——— WJ1 : résoudre la facture mensuelle (montant exact prioritaire, sinon tranche) ———
  function resolveMonthlyBill(): number | null {
    const exact = num('mt-facture-hiver');
    if (exact != null && exact > 0) return exact;
    const range = val('mt-bill');
    if (range && RANGE_MIDPOINT[range] != null) return RANGE_MIDPOINT[range];
    return null;
  }

  // ——— QX : FIX « tranche redondante » (résidentiel) ———
  function syncBillRangeFromExact() {
    const wrap = $('mt-bill-wrap');
    const detected = $('mt-bill-detected');
    const detectedValue = $('mt-bill-detected-value');
    const billSelect = $('mt-bill') as HTMLSelectElement | null;
    const exact = num('mt-facture-hiver');
    if (exact != null && exact > 0 && exact <= maxBillFor('residentiel')) {
      const rid = billRangeFromExact(exact);
      if (rid && billSelect) {
        billSelect.value = rid;
        if (detectedValue) detectedValue.textContent = libelleTranche(ctx.locale, rid, billSelect);
        if (wrap) wrap.hidden = true;
        if (detected) detected.hidden = false;
        setFieldError('mt-bill', 'mt-bill-err', null);
        return;
      }
    }
    if (wrap) wrap.hidden = false;
    if (detected) detected.hidden = true;
  }

  crochets.installer('syncEquipDetails', syncEquipDetails);
  crochets.installer('resolveMonthlyBill', resolveMonthlyBill);
  crochets.installer('syncBillRangeFromExact', syncBillRangeFromExact);
  crochets.installer('wireCardGroup', wireCardGroup);
  crochets.installer('syncOccupancySelection', syncOccupancySelection);
  crochets.installer('syncCultureCards', syncCultureCards);
  crochets.installer('syncHeuresLabel', syncHeuresLabel);
  return {
    wireVisitToggle, wireCardGroup, syncOccupancySelection, syncEquipDetails, syncCultureCards,
    syncHeuresLabel, resolveMonthlyBill, syncBillRangeFromExact,
    brancherVisiteOccupationEquipements, brancherGroupes,
  };
}
