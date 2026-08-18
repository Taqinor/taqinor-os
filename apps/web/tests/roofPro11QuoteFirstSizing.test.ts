// ORDRE FONDATEUR (2026-08-18) — « la logique du calepinage 3D ne part JAMAIS du prix,
// toujours du nombre de panneaux du DEVIS, et n'utilise QUE les composants du devis ». Ce
// test couvre le correctif de `consumption.ts` (`applyConsumptionToSizing`) : une CIBLE déjà
// FIGÉE en amont (devis vendu / verrou manuel — `ctx.neededAuto === false` sans que ce
// module l'ait posé lui-même) ne doit JAMAIS être écrasée par un besoin recalculé depuis la
// facture ou les appareils du panneau « Affiner ma consommation ». Le tunnel public SANS
// devis (mode auto) reste, lui, RÉVERSIBLE (W83) : ajouter/retirer un appareil doit toujours
// faire grandir/rétrécir le besoin.
import { describe, expect, it, vi } from 'vitest';
import { createConsumption, type ConsumptionDom, type ConsumptionDeps } from '../src/scripts/roofPro11/consumption';
import { type Ctx } from '../src/scripts/roofPro11/context';
import { emptyCurve } from '../src/lib/applianceConsumption';

/** DOM minimal : consumption.ts garde chaque accès DOM derrière `if (el)` / `?.`, donc
 *  `null` partout est un état légitime (panneau jamais ouvert dans ces tests). */
function emptyDom(): ConsumptionDom {
  return {
    consWindowEl: null,
    consToggleEl: null,
    consPanelEl: null,
    consTotalEl: null,
    consSelfEl: null,
    consSavingsEl: null,
    consBattEl: null,
    consGraphEl: null,
    consInputsEl: null,
    consRecalEl: null,
    consResetEl: null,
    consPaybackEl: null,
    consSeasonalToggleEl: null,
    consSeasonalControlsEl: null,
    consSummerFactorEl: null,
    consWinterFactorEl: null,
    consMonthlyChartEl: null,
    applKindEl: null,
    applAddEl: null,
    applAcEl: null,
    acBtuEl: null,
    acEerEl: null,
    acHoursEl: null,
    acWattsEl: null,
    applEvEl: null,
    evKwEl: null,
    evHoursEl: null,
    evKmEl: null,
    applNoteEl: null,
    applListEl: null,
  };
}

/** Plafond « panneaux nécessaires » identique à celui de l'optimiseur (1..400, arrondi) —
 *  dupliqué ici pour ne dépendre que de la surface publique de `consumption.ts`. */
const clampNeeded = (n: number): number => Math.max(1, Math.min(400, Math.round(n)));

function makeCtx(overrides: Partial<Ctx> = {}): Ctx {
  return {
    centroidLat: 33.57,
    neededPanels: 0,
    neededAuto: true,
    consMode: false,
    consCurve: emptyCurve(),
    consHandEdited: false,
    consAppliances: [],
    consDailyTarget: 0,
    consApplCounter: 0,
    consSeasonal: false,
    consSummerFactor: 1,
    consWinterFactor: 1,
    prodMonth: 0,
    prodPanels: 0,
    prodScaled: null,
    prodSpecificDate: null,
    ...overrides,
  } as unknown as Ctx;
}

function makeDeps(monthlyBillMad: number, renderActive = vi.fn()): ConsumptionDeps {
  return {
    renderActive,
    clampNeeded,
    monthlyBill: () => monthlyBillMad,
    fmt1: (n: number) => n.toFixed(1),
  };
}

describe('Ordre fondateur — le calepinage part du devis, jamais de la facture', () => {
  it('une cible VENDUE (devis, neededAuto=false) survit à un besoin conso/facture plus grand', () => {
    // Devis vendu : 8 panneaux imposés (PV19 hydrateFromDevis aurait déjà posé ceci).
    const ctx = makeCtx({ neededPanels: 8, neededAuto: false });
    const renderActive = vi.fn();
    // Facture/appareils qui, seuls, dimensionneraient largement AU-DESSUS de 8 panneaux.
    const deps = makeDeps(3000, renderActive);
    const cons = createConsumption(ctx, emptyDom(), deps);

    cons.applyConsumptionToSizing(15000); // conso annuelle énorme → consNeeded ≫ 8

    expect(ctx.neededPanels).toBe(8); // la cible du devis n'a PAS bougé
    expect(ctx.neededAuto).toBe(false); // toujours figée par le devis
    expect(renderActive).not.toHaveBeenCalled(); // aucun re-rendu déclenché par la conso
  });

  it('un verrou manuel (neededAuto=false posé par l\'utilisateur) est protégé de la même façon', () => {
    const ctx = makeCtx({ neededPanels: 12, neededAuto: false });
    const renderActive = vi.fn();
    const cons = createConsumption(ctx, emptyDom(), makeDeps(5000, renderActive));

    cons.applyConsumptionToSizing(20000);

    expect(ctx.neededPanels).toBe(12);
    expect(renderActive).not.toHaveBeenCalled();
  });

  it('sans devis (tunnel public, neededAuto=true) le dimensionnement reste RÉVERSIBLE (W83)', () => {
    const ctx = makeCtx({ neededPanels: 0, neededAuto: true });
    const renderActive = vi.fn();
    const deps = makeDeps(600, renderActive);
    const cons = createConsumption(ctx, emptyDom(), deps);

    // Un appareil « en plus » fait grandir le besoin.
    cons.applyConsumptionToSizing(6000);
    const withAppliance = ctx.neededPanels;
    expect(withAppliance).toBeGreaterThan(0);
    expect(ctx.neededAuto).toBe(false); // NOUS avons posé le latch (consOwnsLock)
    expect(renderActive).toHaveBeenCalledTimes(1);

    // Le retirer fait RÉTRÉCIR le besoin — la réversibilité W83 doit survivre au correctif.
    cons.applyConsumptionToSizing(3000);
    expect(ctx.neededPanels).toBeLessThan(withAppliance);
    expect(renderActive).toHaveBeenCalledTimes(2);
  });

  it('après un devis, une facture plus GRANDE ne fait pas non plus déborder la cible', () => {
    const ctx = makeCtx({ neededPanels: 5, neededAuto: false });
    const renderActive = vi.fn();
    const cons = createConsumption(ctx, emptyDom(), makeDeps(9000, renderActive));

    // annualConsKwh omis → passe par annualSummary() (courbe vide ici, donc 0) : la garde
    // doit de toute façon couper AVANT tout calcul dès que neededAuto est false et pas nôtre.
    cons.applyConsumptionToSizing();

    expect(ctx.neededPanels).toBe(5);
    expect(renderActive).not.toHaveBeenCalled();
  });
});
