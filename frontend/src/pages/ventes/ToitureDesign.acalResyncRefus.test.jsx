import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   Lot 2 critique #23 / #29 — « Enregistrer la conception » sur la route devis :
   la conception EST enregistrée ; un refus de la resynchro du devis lié se lit
   avec le motif SERVEUR décodé (`refusDevis.js`), jamais « données du tracé
   invalides » ; un refus ÉLECTRIQUE (422) liste les bloquants et offre
   « Passer outre » à un approbateur (droit servi par le détail).
   ========================================================================== */

vi.mock('../../hooks/useHasPermission', () => ({ useHasPermission: () => false }))

import '../../test/toitureDesignHarnessCalepinage'
import { rendreDevis, reinitialiserBootMinimal } from '../../test/toitureDesignHarness'
import calepinageApi from '../../api/calepinageApi'

const CTX = exempleContrat('calepinage', 'calepinage_design_context')
const DEVIS_ID = CTX.calepinage.devis_lie.id
const CAL = String(CTX.calepinage.id)
const APPROBATION = 'Approbation à jour exigée avant de générer ou resynchroniser le devis'
const REFUS_422 = {
  response: {
    status: 422,
    data: {
      detail: "Le verdict électrique est bloquant : le devis n'est pas resynchronisé.",
      electrique: {
        verdict: 'bloquant',
        bloquants: [{ code: 'ISC', libelle: 'Isc cumulé hors spécification', detail: 'MPPT 1' }],
        derogation_possible: true,
      },
    },
  },
}

beforeEach(() => {
  vi.clearAllMocks()
  reinitialiserBootMinimal()
  calepinageApi.calepinages.depuisModele.mockResolvedValue({ data: { id: CTX.calepinage.id } })
  calepinageApi.calepinages.designContext.mockResolvedValue(
    reponseContrat('calepinage', 'calepinage_design_context'))
  calepinageApi.calepinages.modulesDisponibles.mockResolvedValue({ data: [] })
  calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel.mockResolvedValue(
    { data: { inchange: false, version: 4, empreinte_document: 'b'.repeat(64) } })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

async function enregistrer() {
  rendreDevis(DEVIS_ID)
  await userEvent.click(await screen.findByRole('button', { name: /Enregistrer la conception/ }))
}

describe('Resynchro du devis lié refusée — motif serveur décodé', () => {
  it('400 {approbation} : « Conception enregistrée — devis NON resynchronisé : <raison> »', async () => {
    calepinageApi.calepinages.syncDevis.mockRejectedValue(
      { response: { status: 400, data: { approbation: [APPROBATION] } } })
    await enregistrer()
    expect(await screen.findByTestId('cal-erreur-enregistrement')).toHaveTextContent(
      `Conception enregistrée — devis NON resynchronisé : ${APPROBATION}`)
  })

  it('panne réseau : resynchronisation impossible (réseau)', async () => {
    calepinageApi.calepinages.syncDevis.mockRejectedValue(new Error('Network Error'))
    await enregistrer()
    expect(await screen.findByTestId('cal-erreur-enregistrement')).toHaveTextContent(
      'Conception enregistrée — resynchronisation du devis impossible (réseau)')
  })

  it('422 électrique, approbateur : bloquants listés puis « Passer outre » relance avec le motif', async () => {
    calepinageApi.calepinages.syncDevis
      .mockRejectedValueOnce(REFUS_422)
      .mockResolvedValueOnce({ data: { inchange: false, avertissements: [] } })
    calepinageApi.calepinages.get.mockResolvedValue(
      { data: { id: CTX.calepinage.id, permissions: { peut_deroger: true } } })
    await enregistrer()

    expect(await screen.findByTestId('cal-sync-bloquant'))
      .toHaveTextContent('Isc cumulé hors spécification')
    await userEvent.click(screen.getByTestId('cal-sync-passer-outre'))
    expect(await screen.findByTestId('cal-sync-motif-erreur'))
      .toHaveTextContent('Saisissez le motif de la dérogation.')
    await userEvent.type(screen.getByTestId('cal-sync-motif'), 'Validé par le BE')
    await userEvent.click(screen.getByTestId('cal-sync-passer-outre'))
    await waitFor(() => expect(calepinageApi.calepinages.syncDevis).toHaveBeenLastCalledWith(
      CAL, { derogation_electrique: { motif: 'Validé par le BE' } }))
    await waitFor(() => expect(screen.queryByTestId('cal-sync-bloquants')).not.toBeInTheDocument())
  })

  it('422 électrique, non approbateur : dérogation réservée', async () => {
    calepinageApi.calepinages.syncDevis.mockRejectedValue(REFUS_422)
    calepinageApi.calepinages.get.mockResolvedValue(
      { data: { id: CTX.calepinage.id, permissions: { peut_deroger: false } } })
    await enregistrer()
    expect(await screen.findByTestId('cal-sync-derogation-reservee'))
      .toHaveTextContent('Dérogation réservée aux approbateurs')
    expect(screen.queryByTestId('cal-sync-passer-outre')).not.toBeInTheDocument()
  })
})
