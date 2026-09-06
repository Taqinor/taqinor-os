// QJW24 — garde de parité de l'inversion facture → kWh, entre CE fichier web
// (billMAD/billToAnnualKwh, estimatorBrainV2.ts) et son miroir ERP déclaré
// (backend/django_core/apps/ventes/quote_engine/pricing.py, _kwh_from_bill_bisect
// + ONEE_TRANCHES, docstrings :430-432/:487-489 — « miroir EXACT »). Vérification
// faite pour QJW24 (06/09/2026) : les deux implémentations concordent aujourd'hui
// (même bissection 60 itérations, même recherche par doublement de la borne
// haute). Mais cette concordance n'était déclarée QUE par un commentaire — rien
// ne la faisait rougir si l'un des deux barèmes bougeait (un tarif ONEE, une
// tranche, une constante) sans que l'autre suive : le prospect lirait un kWc sur
// le site, le commercial un autre dans l'ERP. Ce fichier corrige ça côté web.
//
// `FROZEN_SHARED_TARIFF` est une copie FIGÉE, ATTRIBUÉE (estimatorBrainV2.ts
// REGIE_TARIFF, lignes 124-137 à la date d'écriture), du barème partagé — jamais
// un chiffre inventé, seulement le même barème dupliqué comme ancre de
// comparaison. Chaque facture mensuelle « point de contrôle » ci-dessous est
// DÉRIVÉE en appelant billMAD sur ce barème — aucun montant MAD n'est tapé à la
// main (règle zéro-chiffre-inventé). Si `REGIE_TARIFF` (le barème LIVE) bouge
// sans que cette copie suive, la garde rougit. La correction n'est PAS de
// resynchroniser cette copie au jugé : QJR405 (docs/PLAN2.md, moitié ERP)
// tranche laquelle des deux valeurs (web/ERP) fait foi.
import { describe, expect, it } from 'vitest';
import { billMAD, billToAnnualKwh, REGIE_TARIFF, type TariffGrid } from '../src/lib/estimatorBrainV2';

const FROZEN_SHARED_TARIFF: TariffGrid = {
  progressive: [
    { upToKwh: 100, rate: 0.916272 },
    { upToKwh: 150, rate: 1.091388 },
  ],
  selective: [
    { upToKwh: 200, rate: 1.091388 }, // effectif 151-210
    { upToKwh: 300, rate: 1.187388 }, // effectif 211-310
    { upToKwh: 500, rate: 1.381704 }, // effectif 311-510
    { upToKwh: Infinity, rate: 1.622856 }, // > 510
  ],
  selectiveThresholdKwh: 150,
  boundaryToleranceKwh: 10,
};

// Points de contrôle (kWh MENSUEL) : chaque tranche progressive et sélective,
// chaque marche (bornes nominales 100/150/200/300/500 + tolérance de 10 kWh
// → bornes effectives 210/310/510), et le cas nul. Les factures MAD attendues
// ne sont PAS écrites ici : elles sont calculées plus bas via billMAD sur le
// barème figé, pour chaque point.
const CHECKPOINTS_KWH = [0, 1, 50, 100, 130, 150, 160, 200, 210, 250, 300, 310, 400, 500, 510, 1000] as const;

describe('QJW24 — billMAD (live) == billMAD (barème partagé figé), pour chaque point de contrôle', () => {
  it.each(CHECKPOINTS_KWH)('kWh mensuel = %d MAD/kWh', (monthlyKwh) => {
    const liveBill = billMAD(monthlyKwh, REGIE_TARIFF);
    // Valeur de référence DÉRIVÉE du barème partagé — jamais un montant écrit à
    // la main.
    const frozenBill = billMAD(monthlyKwh, FROZEN_SHARED_TARIFF);
    expect(liveBill).toBeCloseTo(frozenBill, 6);
  });
});

describe('QJW24 — billToAnnualKwh inverse billMAD à ±1e-6 kWh mensuel près (sur le barème LIVE)', () => {
  it.each(CHECKPOINTS_KWH.filter((k) => k > 0))('kWh mensuel = %d', (monthlyKwh) => {
    const monthlyBill = billMAD(monthlyKwh, REGIE_TARIFF);
    const roundTrippedMonthlyKwh = billToAnnualKwh(monthlyBill, REGIE_TARIFF) / 12;
    expect(roundTrippedMonthlyKwh).toBeCloseTo(monthlyKwh, 6);
  });

  it('cas nul : facture 0 (ou négative/non-finie) → 0 kWh, dans les deux sens', () => {
    expect(billMAD(0, REGIE_TARIFF)).toBe(0);
    expect(billToAnnualKwh(0, REGIE_TARIFF)).toBe(0);
    expect(billToAnnualKwh(-10, REGIE_TARIFF)).toBe(0);
    expect(billToAnnualKwh(Number.NaN, REGIE_TARIFF)).toBe(0);
  });
});

describe('QJW24 — CAS NÉGATIF (preuve que la garde rougit réellement)', () => {
  it("une tranche mutée d'un seul côté casse la parité — la garde le détecte", () => {
    // Rejoue EXACTEMENT le défaut de l'audit : le barème « live » bouge (ici
    // simulé par une copie mutée localement), le barème « figé » — qui
    // représente l'autre côté resté immobile — ne suit pas.
    //
    // Preuve exécutée manuellement pour QJW24 (06/09/2026, avant écriture de ce
    // fichier) : en changeant en dur le taux > 510 de REGIE_TARIFF dans
    // estimatorBrainV2.ts (1.622856 → 1.7) puis en ré-exécutant la comparaison
    // ci-dessus contre FROZEN_SHARED_TARIFF, billMAD(1000) est passé de
    // 1622.856 (concordant) à 1700 (divergent) — la garde aurait rougi ; le
    // fichier source a ensuite été remis à l'identique (aucune trace dans le
    // diff commité) et la concordance est repassée au vert. Le test
    // ci-dessous rejoue la même preuve de façon autonome, sans toucher au
    // fichier source, pour que cette preuve reste exécutable en CI à chaque
    // run — pas seulement au moment de l'écriture du test.
    const oneSidedlyMutatedTariff: TariffGrid = {
      ...FROZEN_SHARED_TARIFF,
      selective: FROZEN_SHARED_TARIFF.selective.map((tranche, i) =>
        i === FROZEN_SHARED_TARIFF.selective.length - 1 ? { ...tranche, rate: 1.7 } : tranche,
      ),
    };
    const monthlyKwh = 1000; // tombe dans la tranche > 510, la seule mutée.
    const billFromFrozenTariff = billMAD(monthlyKwh, FROZEN_SHARED_TARIFF);
    const billFromOneSidedlyMutatedTariff = billMAD(monthlyKwh, oneSidedlyMutatedTariff);

    // La garde DOIT distinguer les deux — sinon elle ne détecterait jamais un
    // vrai écart d'un seul côté (exactement le défaut « rien ne rougit »).
    expect(billFromOneSidedlyMutatedTariff).not.toBeCloseTo(billFromFrozenTariff, 2);
    expect(() => expect(billFromOneSidedlyMutatedTariff).toBeCloseTo(billFromFrozenTariff, 6)).toThrow();

    // Et l'inversion, faite avec le MAUVAIS barème (mutatedTariff) sur une
    // facture produite par le BON barème (FROZEN_SHARED_TARIFF), ne retombe
    // plus sur le kWh d'origine — exactement le symptôme « le prospect lit un
    // kWc, le commercial en lit un autre ».
    const wronglyInvertedMonthlyKwh = billToAnnualKwh(billFromFrozenTariff, oneSidedlyMutatedTariff) / 12;
    expect(Math.abs(wronglyInvertedMonthlyKwh - monthlyKwh)).toBeGreaterThan(1);
  });
});
