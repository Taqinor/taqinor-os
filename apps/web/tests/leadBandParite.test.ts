/**
 * QJW13 — GARDE DE PARITÉ : le repli local du formulaire de conversion et
 * l'estimateur d'accueil doivent rendre le MÊME kWc pour la MÊME facture.
 *
 * Avant cette garde, `runSimulation` servait une table statique (`LOCAL_BANDS`)
 * pendant que l'accueil (`InstantEstimator.astro` → `estimateFromBill`) servait
 * le moteur : 3 000 MAD/mois donnaient « 5 à 9 kWc » d'un côté et 16 kWc de
 * l'autre. La garde interroge les DEUX surfaces sur cinq points de contrôle et
 * exige l'égalité stricte.
 */
import { describe, expect, it } from 'vitest';
import { estimateFromBill } from '../src/lib/billEstimate';
import { BILL_RANGES, billRangeBounds, billRangeFromExact, type BillRangeId } from '../src/lib/billRange';
import { engineEstimateBand, runSimulation, type ValidatedLead } from '../src/lib/lead';

/** Les cinq points de contrôle : chacun est la borne BASSE d'une tranche
 *  qualifiée ET la borne HAUTE de la précédente — un seul montant teste donc
 *  les deux extrémités de la fourchette servie au prospect. */
const CONTROL_BILLS = [1000, 1500, 3000, 5000, 10000] as const;

function leadFor(billRange: BillRangeId): ValidatedLead {
  return {
    fullName: 'Test Parité',
    phoneE164: '+212600000000',
    whatsappOptIn: true,
    city: 'Casablanca',
    roofType: 'villa',
    billRange,
    consent: true,
    fbclid: null,
    utm: {},
  };
}

describe('QJW13 — parité repli local ↔ estimateur d’accueil', () => {
  it('rend le même kWc que le moteur d’accueil sur les cinq points de contrôle', () => {
    for (const bill of CONTROL_BILLS) {
      const attendu = estimateFromBill(bill);
      expect(attendu, `moteur d’accueil muet à ${bill} MAD`).not.toBeNull();

      // La tranche dont ce montant est la borne BASSE → son plancher kWc.
      const idBas = billRangeFromExact(bill);
      expect(idBas).not.toBeNull();
      expect(billRangeBounds(idBas as BillRangeId).min).toBe(bill);
      expect(engineEstimateBand(idBas as BillRangeId).kwcMin).toBe(attendu!.kwc);

      // La tranche dont ce montant est la borne HAUTE → son plafond kWc.
      const idHaut = BILL_RANGES.find((r) => billRangeBounds(r.id).max === bill)?.id;
      if (idHaut) expect(engineEstimateBand(idHaut).kwcMax).toBe(attendu!.kwc);
    }
  });

  it('les deux bornes de CHAQUE tranche sortent du moteur (aucune table à la main)', () => {
    for (const r of BILL_RANGES) {
      const { min, max } = billRangeBounds(r.id);
      const band = engineEstimateBand(r.id);
      expect(band.kwcMin).toBe(estimateFromBill(Math.max(min, 1))!.kwc);
      if (Number.isFinite(max)) {
        expect(band.kwcMax).toBe(estimateFromBill(max)!.kwc);
      } else {
        // Tranche ouverte : aucun plafond fabriqué, on annonce « à partir de ».
        expect(band.kwcMax).toBe(band.kwcMin);
        expect(band.kwcLabel).toContain('et plus');
      }
      expect(band.kwcMax).toBeGreaterThanOrEqual(band.kwcMin);
      expect(band.paybackLabel.length).toBeGreaterThan(0);
    }
  });

  it('le repli servi par runSimulation (sans SIMULATOR_API_URL) est celui du moteur', async () => {
    // Chemin (a) du constat : aucune URL de simulateur configurée.
    const band = await runSimulation(leadFor('3000-5000'), {});
    expect(band.source).toBe('local');
    expect(band.kwcMin).toBe(estimateFromBill(3000)!.kwc);
    expect(band.kwcMax).toBe(estimateFromBill(5000)!.kwc);
    // L'ancienne table promettait « 9 à 15 kWc » pour cette tranche : la
    // divergence exacte que cette garde interdit de revenir.
    expect(band.kwcLabel).not.toBe('9 à 15 kWc');
  });

  it('le repli servi APRÈS une panne du simulateur est le même (chemin catch)', async () => {
    // Chemin (b) du constat : `catch { return fallback; }` sur panne réseau.
    const fetchFn = (async () => {
      throw new Error('down');
    }) as unknown as typeof fetch;
    const band = await runSimulation(leadFor('1500-3000'), { SIMULATOR_API_URL: 'https://sim.example/api' }, fetchFn);
    expect(band.source).toBe('local');
    expect(band.kwcMin).toBe(estimateFromBill(1500)!.kwc);
    expect(band.kwcMax).toBe(estimateFromBill(3000)!.kwc);
  });
});
