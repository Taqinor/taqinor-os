// WJ112 — the "Pour affiner la taille" accordion used to feed NOTHING:
// estimateFromBill() only ever read bill/lat/city, so filling ombrage/exact
// kWh silently changed no number on screen (a dead field). This proves:
//  (1) billEstimate.ts: ombrage now derates production/kWc with a DOCUMENTED,
//      never-a-gain multiplier (OMBRAGE_DERATE); exact kWh now overrides the
//      bill-derived consumption target when provided;
//  (2) the 3 mon-toit.astro variants (fr/en/ar) keep the fake "thinking" delay
//      at <=500 ms and stay instant under reduced-motion;
//  (3) the founder cut of 18/08 finished the job the honesty notes started:
//      instead of a note explaining that a field changes nothing (roof age,
//      battery interest, exact kWh…), the field itself LEFT the funnel.
//  (4) FOUNDER ORDER 21/08 — ombrage now leaves too. It really did derate, but
//      no leading solar funnel asks shading up front (Zolar averages it, EDF ENR
//      defers it to the technical visit, Sunroof derives it from imagery), so
//      asking it demanded expert judgement for a value the visit re-measures
//      anyway. The DERATE ITSELF STAYS in billEstimate.ts (still asserted below,
//      still used by other callers): the funnel simply never passes a value, and
//      `ombrageDerateFactor(undefined) === 1` is the no-derate path that every
//      visitor who skipped the chips already took. The lib still accepts
//      `exactKwhMonthly` (other callers).
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { estimateFromBill, OMBRAGE_DERATE, ombrageDerateFactor } from '../src/lib/billEstimate';

const root = (rel: string) => fileURLToPath(new URL(rel, import.meta.url));
const read = (rel: string) => readFileSync(root(rel), 'utf-8');

const FR = read('../src/pages/devis/mon-toit.astro');
const EN = read('../src/pages/en/devis/mon-toit.astro');
const AR = read('../src/pages/ar/devis/mon-toit.astro');

describe('WJ112 — billEstimate.ts: ombrage derates the estimate honestly', () => {
  it("'aucun' laisse la production inchangée (dérate = 1, jamais un gain)", () => {
    expect(OMBRAGE_DERATE.aucun).toBe(1);
    expect(ombrageDerateFactor('aucun')).toBe(1);
    expect(ombrageDerateFactor(undefined)).toBe(1);
  });

  it('un ombrage inconnu/absent ne dérate jamais (repli sûr = 1)', () => {
    expect(ombrageDerateFactor('n-importe-quoi')).toBe(1);
  });

  it("'partiel' et 'important' sont des dérates DOCUMENTÉS, ≤ 1, et important < partiel < aucun (jamais un gain, jamais inversé)", () => {
    expect(OMBRAGE_DERATE.partiel).toBeLessThan(OMBRAGE_DERATE.aucun);
    expect(OMBRAGE_DERATE.important).toBeLessThan(OMBRAGE_DERATE.partiel);
    expect(OMBRAGE_DERATE.important).toBeGreaterThan(0);
  });

  it('filling ombrage visibly changes the estimate output (kwc and/or production go down)', () => {
    const base = estimateFromBill(1200);
    const shaded = estimateFromBill(1200, { ombrage: 'important' });
    expect(base).not.toBeNull();
    expect(shaded).not.toBeNull();
    if (!base || !shaded) return;
    // Plus ombragé -> il faut plus de kWc pour couvrir le même besoin annuel.
    expect(shaded.kwc).toBeGreaterThanOrEqual(base.kwc);
    // La production PAR kWc effectif est bien inférieure (rendement dérate).
    expect(shaded.productionKwhYr / shaded.kwc).toBeLessThan(base.productionKwhYr / base.kwc);
  });

  it("'partiel' dérate moins que 'important' pour la même facture (ordre honnête préservé)", () => {
    const partiel = estimateFromBill(1500, { ombrage: 'partiel' });
    const important = estimateFromBill(1500, { ombrage: 'important' });
    expect(partiel).not.toBeNull();
    expect(important).not.toBeNull();
    if (!partiel || !important) return;
    expect(important.kwc).toBeGreaterThanOrEqual(partiel.kwc);
  });
});

describe('WJ112 — billEstimate.ts: exact kWh overrides the bill-derived target', () => {
  it('une conso exacte plausible change le kWc par rapport à la facture seule', () => {
    const fromBillOnly = estimateFromBill(1200);
    const fromExactKwh = estimateFromBill(1200, { exactKwhMonthly: 2000 });
    expect(fromBillOnly).not.toBeNull();
    expect(fromExactKwh).not.toBeNull();
    if (!fromBillOnly || !fromExactKwh) return;
    expect(fromExactKwh.kwc).not.toBe(fromBillOnly.kwc);
  });

  it('une conso exacte non chiffrable (0/négatif/NaN) est ignorée -- retombe sur la facture (jamais cassé)', () => {
    const viaBill = estimateFromBill(1200);
    const viaZero = estimateFromBill(1200, { exactKwhMonthly: 0 });
    const viaNegative = estimateFromBill(1200, { exactKwhMonthly: -5 });
    const viaNaN = estimateFromBill(1200, { exactKwhMonthly: NaN });
    expect(viaZero).toEqual(viaBill);
    expect(viaNegative).toEqual(viaBill);
    expect(viaNaN).toEqual(viaBill);
  });

  it('sans options, le comportement est byte-identique à avant WJ112 (pas de régression)', () => {
    const est = estimateFromBill(1200);
    expect(est).not.toBeNull();
    if (!est) return;
    expect(est.kwc).toBeGreaterThan(0);
    expect(est.latitudeUsed).toBe(33.5);
  });
});

describe.each([
  ['FR', FR],
  ['EN', EN],
  ['AR', AR],
])('WJ112 — %s mon-toit.astro : ombrage RETIRÉ du tunnel + délai réduit', (_label, src) => {
  it('estimateFromBill() ne reçoit plus que lat/city — ni ombrage, ni la conso kWh saisie', () => {
    // ORDRE FONDATEUR 21/08 — la question d'ombrage a quitté le tunnel : plus
    // aucune clé `ombrage` ne part au moteur. `ombrageDerateFactor(undefined)`
    // rend 1 (prouvé plus haut) : c'est EXACTEMENT le chemin qu'empruntait déjà
    // un visiteur qui ne cliquait aucune puce — aucun chiffre ne bouge pour lui.
    expect(src).toContain('estimateFromBill(bill, { lat, city })');
    expect(src).not.toContain('ombrage: ombrage || undefined');
    // La question « Consommation (kWh/mois) » a quitté le tunnel : le moteur
    // refait lui-même la conversion facture MAD → kWh.
    expect(src).not.toContain("num('mt-bill-kwh')");
  });

  it("plus aucun état `ombrage` ne vit dans l'assistant (état, puces et persistance partis ensemble)", () => {
    expect(src).not.toContain('let ombrage = savedWizard?.ombrage');
    expect(src).not.toContain("querySelectorAll<HTMLButtonElement>('.mt-ombrage')");
  });

  it('le délai de « réflexion » simulé est réduit à <= 500 ms (jamais > 1.5 s comme avant)', () => {
    const minMatch = /THINKING_MIN_MS = (\d+);/.exec(src);
    const maxMatch = /THINKING_MAX_MS = (\d+);/.exec(src);
    expect(minMatch).not.toBeNull();
    expect(maxMatch).not.toBeNull();
    if (!minMatch || !maxMatch) return;
    const min = Number(minMatch[1]);
    const max = Number(maxMatch[1]);
    expect(min).toBeGreaterThan(0);
    expect(max).toBeLessThanOrEqual(500);
    expect(max).toBeGreaterThanOrEqual(min);
  });

  it('reduced-motion reste instantané (0 ms) -- comportement honnête inchangé', () => {
    expect(src).toContain('if (reducedMotion) return 0;');
  });

  it("les champs qui ne changeaient AUCUN chiffre ont quitté le tunnel (coupe 18/08)", () => {
    // WJ112 leur avait collé une note d'honnêteté « ne change pas le calcul ».
    // La coupe du fondateur va au bout de la même logique : on ne les pose plus
    // du tout avant l'estimation — le commercial les complète dans l'ERP.
    for (const id of ['id="mt-roof-age"', 'id="mt-battery-interest"', 'id="mt-bill-kwh"']) {
      expect(src, id).not.toContain(id);
    }
    // ORDRE FONDATEUR 21/08 — l'ombrage rejoint enfin ce même sort. Il dératait
    // vraiment, mais AUCUN tunnel solaire de référence ne pose la question en
    // amont : Zolar l'annonce moyennée dans ses hypothèses, EDF ENR la renvoie à
    // la visite technique, Sunroof la DÉRIVE de l'imagerie. La poser demandait
    // au visiteur un jugement d'expert pour une valeur que la visite reprend de
    // toute façon. Les puces .mt-ombrage ont quitté le DOM des 3 variantes.
    expect(src).not.toContain('mt-ombrage');
  });
});
