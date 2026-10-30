import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   ACAL311 — LA CONSOMMATION PROPOSÉE PAR LE SERVEUR ATTEINT L'ATELIER.

   `POST calepinages/<pk>/consommation/proposer/` (ACAL310) convertit les factures du lead
   au barème de la SOCIÉTÉ. L'atelier 3D ne parle jamais à Django : la page HÔTE lui donne
   `proposerConsommation(corps)` (patron de `rendementPvgis`), liée au calepinage ouvert —
   la réponse 200 telle quelle, ou le refus décodé par `refusServeur`. La réponse est posée
   dans le ctx par la VRAIE fonction d'application de l'atelier (`appliquerHydratationAuCtx`)
   et le document enregistré porte la consumption servie.

   PACT13 — la charge utile vient de l'exemple COMMITTÉ, jamais d'un objet tapé à la main.
   ========================================================================== */

vi.mock('../../hooks/useHasPermission', () => ({ useHasPermission: () => false }))

import '../../test/toitureDesignHarnessCalepinage'
import {
  initRoofToolPro8, rendreCalepinage, rendreLead, reinitialiserBootMinimal, simulerApiLead,
  stubberEmpreinteOsm,
} from '../../test/toitureDesignHarness'
import api from '../../api/axios'
import calepinageApi from '../../api/calepinageApi'
import { hydratationDeProposition } from '@roofpro/consumption'
import { appliquerHydratationAuCtx } from '@roofpro/hydratation'
import { serializeConsumption } from '@roofpro/prefill'

stubberEmpreinteOsm()

const CTX = exempleContrat('calepinage', 'calepinage_design_context')
const NOM = 'calepinage_consommation_proposee'
const SERVIE = exempleContrat('calepinage', NOM)

/** Le ctx minimal d'un atelier : seule la consommation y vit. */
function ctxAtelier() {
  return {
    consCurve: [], consHandEdited: false, consAppliances: [], consDailyTarget: 0,
    consSeasonal: false, consSummerFactor: 1.3, consWinterFactor: 0.9,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  reinitialiserBootMinimal()
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ACAL311 — consommation proposée par le serveur', () => {
  it("Reprendre du lead poste source:'lead' et le document enregistré porte la consumption servie", async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.modulesDisponibles.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_modules_disponibles'))
    calepinageApi.calepinages.proposerConsommation.mockResolvedValue(reponseContrat('calepinage', NOM))
    calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel.mockResolvedValue(
      { data: { inchange: false, version: null } })
    // Le builder : la VRAIE application de l'atelier, puis le VRAI sérialiseur de la conso.
    const atelier = ctxAtelier()
    reinitialiserBootMinimal({
      serializeLayout: vi.fn(() => ({ version: 2, zones: [], ...serializeConsumption(atelier) })),
    })

    rendreCalepinage(CTX.calepinage.id)
    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    const { proposerConsommation } = initRoofToolPro8.mock.calls[0][0]
    expect(typeof proposerConsommation).toBe('function')

    // « Reprendre du lead » : le corps du contrat, vers le calepinage OUVERT.
    const rep = await proposerConsommation(exempleContrat('calepinage', NOM, 'corps_lead'))
    expect(calepinageApi.calepinages.proposerConsommation)
      .toHaveBeenCalledWith(String(CTX.calepinage.id), { source: 'lead' })
    expect(rep).toEqual(SERVIE)
    appliquerHydratationAuCtx(atelier, hydratationDeProposition(rep))

    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer le calepinage/ }))
    await waitFor(() => expect(calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel).toHaveBeenCalled())
    const [, layout] = calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel.mock.calls[0]
    expect(layout.consumption.source).toEqual(SERVIE.consumption.source)
    expect(layout.consumption.source.bareme).toBe('societe')
    expect(layout.consumption.courbe24).toEqual(SERVIE.consumption.courbe24)
    expect(layout.consumption.saisons).toEqual(SERVIE.consumption.saisons)
  })

  it('un refus 409 arrive à l’atelier DÉCODÉ (champ nommé), jamais l’erreur axios brute', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(reponseContrat('calepinage', 'calepinage_design_context'))
    const refus = exempleContrat('calepinage', NOM, 'refus_400_facture')
    calepinageApi.calepinages.proposerConsommation.mockRejectedValue({ response: { status: 409, data: refus } })
    rendreCalepinage(CTX.calepinage.id)
    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    const { proposerConsommation } = initRoofToolPro8.mock.calls[0][0]
    await expect(proposerConsommation(exempleContrat('calepinage', NOM, 'corps_factures')))
      .rejects.toEqual({ message: refus['factures.hiver_mad'], champs: refus })
  })

  it('mode LEAD (aucun calepinage) : `proposerConsommation: null` — estimation affichée', async () => {
    simulerApiLead(api)
    rendreLead()
    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(initRoofToolPro8.mock.calls[0][0].proposerConsommation).toBeNull()
  })
})
