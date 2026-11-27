import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   La cible SERVIE par design-context, telle que l'atelier la dit — sortis de
   `ToitureDesign.calepinage.test.jsx` (fichier gelé, C20), même harnais :
   1. ACAL1331 — la pose suit la cible servie et son origine (mots compris) ;
   2. Revue ACAL1738 — « renseignez la facture » n'est dit qu'UNE fois.
   PACT13 — les charges utiles viennent des exemples COMMITTÉS du contrat.
   ========================================================================== */

// CALX27 — le bandeau « lecture seule » de l'atelier lit `useHasPermission`
// (store Redux) : ce test rend la page sans Provider, on fige le droit à faux.
vi.mock('../../hooks/useHasPermission', () => ({ useHasPermission: () => false }))

import '../../test/toitureDesignHarnessCalepinage'
import { initRoofToolPro8, rendreCalepinage, reinitialiserBoot } from '../../test/toitureDesignHarness'
import calepinageApi from '../../api/calepinageApi'

beforeEach(() => {
  vi.clearAllMocks()
  reinitialiserBoot()
})
afterEach(() => {
  cleanup(); vi.clearAllMocks()
  // ACAL1731 — l'étape où l'on s'arrête est mémorisée par calepinage : aucune fuite d'un cas au suivant.
  try {
    Object.keys(window.localStorage).filter((k) => k.startsWith('calepinage.etape.'))
      .forEach((k) => window.localStorage.removeItem(k))
  } catch { /* stockage refusé : rien à nettoyer */ }
})

describe('ToitureDesign — mode calepinage (CAL37)', () => {
  /* ACAL1331 (D-ACAL-76 « dimensionner », 23/11) — un calepinage vierge se pose à la taille de la cible SERVIE : l'atelier
     reçoit le nombre (cible.panneaux) ET son origine, qu'il DIT (« Posé d'après la facture … ») ; sans facture ni devis,
     aucune cible ni origine : la pose d'aujourd'hui (ce qui tient), dite par l'atelier. */
  it('ACAL1331 — décision dimensionner : la pose suit la cible servie et son origine ; sans facture, inchangée', async () => {
    const FACTURES = exempleContrat('calepinage', 'calepinage_design_context', 'exemple_cible_lead')
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context', 'exemple_cible_lead'))
    rendreCalepinage(FACTURES.calepinage.id)
    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    const devis = initRoofToolPro8.mock.calls[0][0].hydrate.devis
    expect(FACTURES.cible.source).toBe('factures')
    expect([devis.cible.panneaux, devis.cibleVendue, devis.origineCible]).toEqual([FACTURES.cible.panneaux, false, 'factures'])
    expect(devis.libelleOrigineCible).toBe('Factures du lead') // T4-X8-012 (une cible) — les mots de la carte « Source de la cible »
    expect(devis.libelleApresOrigineCible).toBe('les factures du lead')

    cleanup(); vi.clearAllMocks(); reinitialiserBoot()
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context', 'exemple_sans_devis'))
    rendreCalepinage(exempleContrat('calepinage', 'calepinage_design_context', 'exemple_sans_devis').calepinage.id)
    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    const sans = initRoofToolPro8.mock.calls[0][0].hydrate.devis
    expect([sans.cible.panneaux, sans.origineCible]).toEqual([null, null])
    expect(sans.libelleOrigineCible).toBeNull()
    expect(sans.libelleApresOrigineCible).toBeNull()
  })
})

describe('ToitureDesign — cible estimée vs cible vendue (ACAL195)', () => {
  it('Revue ACAL1738 — « renseignez la facture » dite UNE fois : le bandeau se tait tant que le cadre de taille la dit', async () => {
    // Le 409 du contrat (motif `facture_absente`) : son `refus` EST `cible.refus` du design-context (services/devis.py).
    const QUESTION = exempleContrat('calepinage', 'calepinage_publication', 'exemple_409_confirmation_taille')
    expect(QUESTION.motif).toBe('facture_absente')
    const base = exempleContrat('calepinage', 'calepinage_design_context', 'exemple_cible_refus')
    const ctx = { ...base, cible: { ...base.cible, refus: QUESTION.refus } }
    expect(ctx.calepinage.lead).toBeTruthy()
    calepinageApi.calepinages.designContext.mockResolvedValue({ data: ctx })
    calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel.mockResolvedValue(
      { data: { inchange: true, version: null } })
    calepinageApi.calepinages.genererDevis.mockRejectedValue({ response: { status: 409, data: QUESTION } })
    calepinageApi.calepinages.get.mockResolvedValue(reponseContrat('calepinage', 'calepinage_detail', 'exemple_vide'))

    rendreCalepinage(ctx.calepinage.id, '?onglet=documents')
    expect(await screen.findByTestId('acal-cible-estimee', {}, { timeout: 15_000 })).toHaveTextContent(QUESTION.refus)
    await screen.findByTestId('cal-generer-devis', {}, { timeout: 15_000 })
    await waitFor(() => expect(screen.getByTestId('cal-generer-devis')).toBeEnabled())
    await userEvent.click(screen.getByTestId('cal-generer-devis'))

    expect(await screen.findByTestId('cal-devis-confirmation-taille', {}, { timeout: 10_000 }))
      .toHaveTextContent(QUESTION.detail)
    await waitFor(() => expect(screen.queryByTestId('acal-cible-estimee')).toBeNull())
    expect(screen.getAllByText(/renseignez la facture/i)).toHaveLength(1)
  })
})
