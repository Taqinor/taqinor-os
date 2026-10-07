import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { reponseContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   ACAL37 (D-ACAL-1) — `/ventes/devis/:id/design` ouvre et enregistre le
   CALEPINAGE lié, puis resynchronise le devis.

   1. la route devis résout le calepinage par `POST calepinages/depuis-modele/
      {devis_id}` et boote COMME le mode calepinage (design-context du
      calepinage, catalogue de modules) — l'en-tête reste celui du devis
      (`calepinage.devis_lie`) ;
   2. « Enregistrer la conception » range le document sur le CALEPINAGE puis
      appelle `calepinages/<id>/sync-devis/` — jamais `syncDevisLayout`, jamais
      le `roof-image` du devis.

   Seul le client HTTP est doublé (comme les autres tests ToitureDesign) ; les
   charges utiles viennent des exemples COMMITTÉS.
   ========================================================================== */

vi.mock('../../hooks/useHasPermission', () => ({ useHasPermission: () => false }))

import {
  CTX_CALEPINAGE_DEVIS as CTX, DEVIS_ID_CALEPINAGE as DEVIS_ID,
} from '../../test/toitureDesignHarnessCalepinage'
import {
  initRoofToolPro8, rendreDevis, reinitialiserBootMinimal,
} from '../../test/toitureDesignHarness'
import api from '../../api/axios'
import ventesApi from '../../api/ventesApi'
import calepinageApi from '../../api/calepinageApi'

const MODULES = [{ id: 7, nom: 'Module 500 Wc', puissance_wc: 500 }]

beforeEach(() => {
  vi.clearAllMocks()
  reinitialiserBootMinimal()
  calepinageApi.calepinages.depuisModele.mockResolvedValue(
    { data: { id: CTX.calepinage.id } })
  calepinageApi.calepinages.designContext.mockResolvedValue(
    reponseContrat('calepinage', 'calepinage_design_context'))
  calepinageApi.calepinages.modulesDisponibles.mockResolvedValue({ data: MODULES })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ACAL37 — la conception d’un devis EST son calepinage', () => {
  it('mode devis résout le calepinage lié et charge le catalogue', async () => {
    rendreDevis(DEVIS_ID)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(calepinageApi.calepinages.depuisModele)
      .toHaveBeenCalledWith({ devis_id: DEVIS_ID })
    expect(calepinageApi.calepinages.designContext)
      .toHaveBeenCalledWith(String(CTX.calepinage.id))
    // D-ACAL-10 — le catalogue de modules est chargé, comme en mode calepinage.
    expect(calepinageApi.calepinages.modulesDisponibles)
      .toHaveBeenCalledWith(String(CTX.calepinage.id))
    const options = initRoofToolPro8.mock.calls[0][0]
    expect(options.modulesDisponibles).toEqual(MODULES)
    // Plus aucune lecture du contexte DEVIS : le calepinage fait foi.
    expect(ventesApi.getDevisDesignContext).not.toHaveBeenCalled()
    // L'en-tête reste celui du devis lié.
    const titre = await screen.findByRole('heading', { level: 1 })
    expect(titre).toHaveTextContent(CTX.calepinage.devis_lie.reference)
    expect(titre).toHaveTextContent(CTX.calepinage.devis_lie.client_nom)
  })

  it('Enregistrer la conception enregistre le calepinage puis sync-devis, jamais syncDevisLayout', async () => {
    calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel.mockResolvedValue(
      { data: { inchange: false, version: 4, empreinte_document: 'b'.repeat(64) } })
    calepinageApi.calepinages.syncDevis.mockResolvedValue(
      { data: { inchange: false, avertissements: [] } })

    rendreDevis(DEVIS_ID)
    const bouton = await screen.findByRole('button', { name: /Enregistrer la conception/ })
    await userEvent.click(bouton)

    await waitFor(() => expect(calepinageApi.calepinages.syncDevis)
      .toHaveBeenCalledWith(String(CTX.calepinage.id), {}))
    const ecrire = calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel
    expect(ecrire).toHaveBeenCalledTimes(1)
    expect(ecrire.mock.calls[0][0]).toBe(String(CTX.calepinage.id))
    // L'ORDRE : le calepinage d'abord, le devis ensuite.
    expect(ecrire.mock.invocationCallOrder[0])
      .toBeLessThan(calepinageApi.calepinages.syncDevis.mock.invocationCallOrder[0])
    expect(ventesApi.syncDevisLayout).not.toHaveBeenCalled()
    const urlsPost = api.post.mock.calls.map((appel) => String(appel[0]))
    expect(urlsPost.some((url) => url.includes('/ventes/devis/'))).toBe(false)
  })

  it('un 409 révisable de la resynchronisation offre « Réviser (v2) »', async () => {
    calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel.mockResolvedValue(
      { data: { inchange: true, empreinte_document: CTX.geometrie.empreinte_document } })
    calepinageApi.calepinages.syncDevis.mockRejectedValue({
      response: { status: 409, data: { detail: 'Devis envoyé : révisez-le', revision_possible: true } },
    })

    rendreDevis(DEVIS_ID)
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer la conception/ }))

    const encart = await screen.findByTestId('pv21-reviser')
    expect(encart).toHaveTextContent('Devis envoyé : révisez-le')
    expect(screen.getByRole('button', { name: 'Réviser (v2)' })).toBeInTheDocument()
  })

  it('devis introuvable : message FR, aucun boot du builder', async () => {
    calepinageApi.calepinages.depuisModele.mockRejectedValue(
      { response: { status: 400, data: { devis_id: 'Devis introuvable (#999).' } } })

    rendreDevis(999)

    expect(await screen.findByRole('alert')).toHaveTextContent('Devis introuvable (#999).')
    expect(initRoofToolPro8).not.toHaveBeenCalled()
  })
})
