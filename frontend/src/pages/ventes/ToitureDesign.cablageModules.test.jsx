import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   CALX109 CÂBLAGE — LE CATALOGUE DE MODULES DE LA SOCIÉTÉ ATTEINT L'ATELIER.

   `GET calepinages/<pk>/modules-disponibles/` sert les fiches « module » du stock avec
   leurs VRAIES cotes (contrat `calepinage_modules_disponibles.json`). L'atelier 3D ne parle
   jamais à Django : c'est la PAGE HÔTE qui lit cette porte et transmet la réponse TELLE
   QUELLE au constructeur (`InitOptions.modulesDisponibles`). Sans cette ligne, le sélecteur
   de module de l'atelier n'a rien à proposer et chaque pan reste pavé avec le module par
   défaut, quoi qu'il y ait au stock.

   Même patron, même discipline que `chargerReglagesAtelier` (CALX104/CALX403, éprouvé par
   `ToitureDesign.cablageHooks2.test.jsx`) : porte BEST-EFFORT lancée en parallèle du
   design-context, qui ne bloque JAMAIS le boot et n'invente rien quand elle échoue.

   PACT13 — la charge utile vient de l'exemple COMMITTÉ, jamais d'un objet tapé à la main.
   ========================================================================== */

vi.mock('../../hooks/useHasPermission', () => ({ useHasPermission: () => false }))

import '../../test/toitureDesignHarnessCalepinage'
import {
  initRoofToolPro8, rendreCalepinage, rendreDevis, rendreLead, reinitialiserBootMinimal, simulerApiLead,
  stubberEmpreinteOsm,
} from '../../test/toitureDesignHarness'
import api from '../../api/axios'
import calepinageApi from '../../api/calepinageApi'
// ACAL311 — la VRAIE application et le VRAI sérialiseur de la consommation de l'atelier.
import { hydratationDeProposition } from '@roofpro/consumption'
import { appliquerHydratationAuCtx } from '@roofpro/hydratation'
import { serializeConsumption } from '@roofpro/prefill'

stubberEmpreinteOsm()

const CTX = exempleContrat('calepinage', 'calepinage_design_context')
const MODULES = exempleContrat('calepinage', 'calepinage_modules_disponibles')

beforeEach(() => {
  vi.clearAllMocks()
  reinitialiserBootMinimal()
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('CALX109 câblage — le catalogue de modules atteint le constructeur', () => {
  it('le mode CALEPINAGE lit `modules-disponibles` et transmet la réponse TELLE QUELLE', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.modulesDisponibles.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_modules_disponibles'))

    rendreCalepinage(CTX.calepinage.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(calepinageApi.calepinages.modulesDisponibles)
      .toHaveBeenCalledWith(String(CTX.calepinage.id))
    expect(initRoofToolPro8.mock.calls[0][0].modulesDisponibles).toEqual(MODULES)
  })

  // ACAL30 — RÉÉCRIT : un catalogue illisible n'empêche pas de REGARDER la conception (le
  // boot a lieu, aucun module inventé), mais il INTERDIT l'enregistrement : sans catalogue,
  // le module de chaque pan retombait en silence sur le défaut 720 Wc (porte ATL-10).
  it('catalogue en échec → Enregistrer refusé (le boot a lieu, aucun module inventé, aucun POST)', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.modulesDisponibles.mockRejectedValue(new Error('403'))

    rendreCalepinage(CTX.calepinage.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    // `null` = aucun catalogue transmis : rien n'est inventé côté atelier.
    expect(initRoofToolPro8.mock.calls[0][0].modulesDisponibles).toBeNull()
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer le calepinage/ }))
    expect(await screen.findByText(/Catalogue des modules indisponible : rien n’est enregistré, rechargez/))
      .toBeTruthy()
    expect(calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel).not.toHaveBeenCalled()
  })

  it('catalogue lu : Enregistrer part normalement (le refus ne vaut que pour l’échec)', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.modulesDisponibles.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_modules_disponibles'))
    calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel.mockResolvedValue(
      { data: { inchange: true, version: null } })

    rendreCalepinage(CTX.calepinage.id)
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer le calepinage/ }))
    await waitFor(() => expect(calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel).toHaveBeenCalled())
  })

  // ACAL37 (D-ACAL-1, D-ACAL-10) — RÉÉCRIT : la route devis ouvre le calepinage lié et
  // charge le catalogue de modules comme le mode calepinage (plus de mode devis à part).
  it('la route DEVIS charge le catalogue du calepinage lié', async () => {
    calepinageApi.calepinages.depuisModele.mockResolvedValue(
      { data: { id: CTX.calepinage.id } })
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.modulesDisponibles.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_modules_disponibles'))

    rendreDevis(9, '/devis/:id/toiture')

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(calepinageApi.calepinages.depuisModele).toHaveBeenCalledWith({ devis_id: 9 })
    expect(calepinageApi.calepinages.modulesDisponibles)
      .toHaveBeenCalledWith(String(CTX.calepinage.id))
    expect(initRoofToolPro8.mock.calls[0][0].modulesDisponibles).toEqual(MODULES)
  })
})

// ACAL80 — l'ERP ne sert pas `/api/roof-yield` (route d'apps/web) : la page dit au
// constructeur de ne JAMAIS l'appeler (repli table), dans les deux modes.
describe('ACAL80 — point de rendement nul dans l’ERP', () => {
  it('mode CALEPINAGE et mode DEVIS : `rendementPvgis: null` transmis au constructeur', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    rendreCalepinage(CTX.calepinage.id)
    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(initRoofToolPro8.mock.calls[0][0].rendementPvgis).toBeNull()

    cleanup()
    initRoofToolPro8.mockClear()
    delete window.__taqinorRoofBooted
    // ACAL37 — la route devis ouvre le calepinage lié : même constructeur.
    calepinageApi.calepinages.depuisModele.mockResolvedValue(
      { data: { id: CTX.calepinage.id } })
    rendreDevis(9)
    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(initRoofToolPro8.mock.calls[0][0].rendementPvgis).toBeNull()
  })
})

// ACAL311
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
const NOM = 'calepinage_consommation_proposee'
const SERVIE = exempleContrat('calepinage', NOM)

/** Le ctx minimal d'un atelier : seule la consommation y vit. */
function ctxAtelier() {
  return {
    consCurve: [], consHandEdited: false, consAppliances: [], consDailyTarget: 0,
    consSeasonal: false, consSummerFactor: 1.3, consWinterFactor: 0.9,
  }
}

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
