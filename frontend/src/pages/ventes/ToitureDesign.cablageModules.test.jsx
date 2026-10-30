import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, screen, cleanup, waitFor } from '@testing-library/react'
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
import { createConsumption, hydratationDeProposition } from '@roofpro/consumption'
import { ctxAtelierNeuf } from '@roofpro/harnaisDocument' // ERR-ACAL311-PANNEAU-ABSENT-ERP
import { appliquerHydratationAuCtx } from '@roofpro/hydratation'
import { serializeConsumption } from '@roofpro/prefill'
import { createProdWindow } from '@roofpro/prodWindow' // ERR-ACAL311 — vrai module, fenêtre absente
import { fallbackPerKwc } from '@rooflib/productionEngine'
import { MESSAGE_ENREGISTREMENT_ECHOUE } from '../../features/calepinage/BoutonDevis'

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

  // ERR-ACAL311-PANNEAU-ABSENT-ERP — preuve en direct P5.5 : 0 `rp9-cons*` dans l'atelier ERP.
  it("l'atelier CALEPINAGE rend le panneau ; « Reprendre du lead » appelle proposerConsommation", async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.proposerConsommation.mockResolvedValue(reponseContrat('calepinage', NOM))
    rendreCalepinage(CTX.calepinage.id)
    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    const panneau = document.getElementById('rp9-cons-panel')
    expect(panneau).not.toBeNull()
    expect(document.getElementById('rp9-cons-window').textContent).toContain('Affiner ma consommation')
    // Le VRAI module de l'atelier, monté sur le DOM servi par l'ERP, avec l'option du boot.
    const dom = new Proxy({ consPanelEl: panneau }, { get: (t, k) => t[k] ?? null })
    const ctx = { ...ctxAtelierNeuf(), opts: { proposerConsommation: initRoofToolPro8.mock.calls[0][0].proposerConsommation } }
    createConsumption(ctx, dom, {
      renderActive: () => undefined, clampNeeded: (n) => n, monthlyBill: () => 0, fmt1: (n) => String(n),
    }).wire()
    const bouton = panneau.querySelector('[data-cons-action="lead"]')
    expect(bouton.textContent).toBe('Reprendre du lead')
    bouton.click()
    await waitFor(() => expect(calepinageApi.calepinages.proposerConsommation)
      .toHaveBeenCalledWith(String(CTX.calepinage.id), { source: 'lead' }))
    await waitFor(() => expect(ctx.consSource?.bareme).toBe('societe'))
  })

  it('mode LEAD (aucun calepinage) : `proposerConsommation: null` — estimation affichée', async () => {
    simulerApiLead(api)
    rendreLead()
    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(initRoofToolPro8.mock.calls[0][0].proposerConsommation).toBeNull()
  })

  // ERR-ACAL311-PANNEAU-ABSENT-ERP (vague 9) — le panneau était dans le DOM mais restait
  // `hidden` : sans `#rp9-prod-window` ni `/api/roof-production`, aucun plan de production.
  it('`productionAtelier` transmis : sans fenêtre de production, « Affiner ma consommation » devient visible', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(reponseContrat('calepinage', 'calepinage_design_context'))
    // Vague 10 (rejeu P5.5) — comme le VRAI constructeur (`roof-tool-pro11.ts` : `$('rp9-cons-window')`
    // au boot), l'élément est saisi PENDANT `initRoofToolPro8`, AVANT les re-rendus React
    // déclenchés par `onApiReady`/`onHydrationTerminee`. En direct, React 19 réécrivait
    // `innerHTML` à chaque rendu (objet `__html` neuf) : le module montrait un nœud DÉTACHÉ.
    const bootMinimal = initRoofToolPro8.getMockImplementation()
    let saisiAuBoot = null
    initRoofToolPro8.mockImplementation((options) => {
      saisiAuBoot = document.getElementById('rp9-cons-window')
      return bootMinimal(options)
    })
    rendreCalepinage(CTX.calepinage.id)
    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    await screen.findByRole('button', { name: /Enregistrer le calepinage/ })
    const { productionAtelier } = initRoofToolPro8.mock.calls[0][0]
    expect(typeof productionAtelier).toBe('function')
    expect(productionAtelier({ panels: 10 })).toEqual(fallbackPerKwc())
    const fenetre = saisiAuBoot
    expect(fenetre, 'saisi au boot').not.toBeNull()
    expect(fenetre.isConnected, 'le nœud saisi au boot survit aux re-rendus React').toBe(true)
    expect(document.getElementById('rp9-cons-window')).toBe(fenetre)
    expect(fenetre.hidden).toBe(true)
    // Les VRAIS modules de l'atelier sur le DOM servi par l'ERP (aucun `#rp9-prod-window`).
    const ctx = {
      ...ctxAtelierNeuf(), opts: { productionAtelier }, closed: true, centroid: [-7.6, 33.5],
      vertices: [[-7.6, 33.5], [-7.59, 33.5], [-7.59, 33.51]], prodMonth: 0, prodPanels: 0,
      liveResult: { target: 6000, winner: { placedCount: 10, tiltDeg: 10, aspect: 0 } },
    }
    const domConso = new Proxy({ consWindowEl: fenetre }, { get: (t, k) => t[k] ?? null })
    const conso = createConsumption(ctx, domConso, {
      renderActive: () => undefined, clampNeeded: (n) => n, monthlyBill: () => 0, fmt1: (n) => String(n),
    })
    createProdWindow(ctx, new Proxy({}, { get: () => null }), {
      graphs: {}, renderConsumption: conso.renderConsumption, renderLayoutPanel: () => undefined,
      snapshotActiveAreaResult: () => undefined, renderAreasPanel: () => undefined,
    }).syncProductionWindow()
    expect(ctx.prodPanels).toBe(10)
    expect(document.getElementById('rp9-cons-window').hidden, 'visible À L’ÉCRAN (nœud connecté)').toBe(false)
    expect(document.getElementById('rp9-cons-toggle')).not.toBeNull()

    cleanup()
    initRoofToolPro8.mockClear()
    delete window.__taqinorRoofBooted
    simulerApiLead(api)
    rendreLead()
    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(typeof initRoofToolPro8.mock.calls[0][0].productionAtelier).toBe('function')
  })

  // Rejeu P5.5 (vague 10) — F5 puis « Enregistrer » AVANT l'hydratation (faite au `load` de
  // la carte, APRÈS `onApiReady`) réécrivait le document sans sa consommation relue.
  it('rien ne s’enregistre entre `onApiReady` et `onHydrationTerminee` (le document relu survit)', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(reponseContrat('calepinage', 'calepinage_design_context'))
    const serializeLayout = vi.fn(() => ({ version: 2, zones: [] })) // scène NON hydratée : sans `consumption`
    let options = null
    initRoofToolPro8.mockImplementation((o) => {
      options = o
      o.onApiReady?.({ serializeLayout, snapshot: vi.fn(() => null) }) // la carte n'a pas encore fini de charger
    })
    rendreCalepinage(CTX.calepinage.id)
    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    const bouton = await screen.findByRole('button', { name: /Enregistrer le calepinage/ })
    expect(bouton).toBeDisabled()
    await userEvent.click(bouton)
    expect(calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel).not.toHaveBeenCalled()
    expect(serializeLayout).not.toHaveBeenCalled()

    await act(async () => { options.onHydrationTerminee?.() })
    await waitFor(() => expect(screen.getByRole('button', { name: /Enregistrer le calepinage/ })).toBeEnabled())
  })

  // CI vague 10 (e2e CAL221/CALX386) — sans clé carte, le boot s'arrête sur « Carte
  // indisponible » et `onHydrationTerminee` n'arrive jamais. Comme sur `main` avant la garde :
  // le bouton est cliquable, l'enregistrement préalable refuse (aucun constructeur) et le
  // refus se lit dans `cal-devis-refus` — ni écriture de layout, ni appel au pont devis.
  // (Sans `enregistrerAvant`, le serveur répondait 409 `roof_layout` → `cal-devis-conflit`,
  // que l'e2e n'attend pas : rouge CI run 41024909999.)
  it('carte absente → Resynchroniser cliquable, refus `cal-devis-refus`, rien n’est écrit ni envoyé', async () => {
    const ctx = { ...CTX, carte: { available: false, maptilerKey: '', mapboxToken: null } }
    calepinageApi.calepinages.designContext.mockResolvedValue({ data: ctx })
    calepinageApi.calepinages.get.mockResolvedValue(reponseContrat('calepinage', 'calepinage_detail'))
    api.get.mockResolvedValue({ data: [] }) // champs personnalisés de la fiche (indépendant de l'ordre)
    calepinageApi.calepinages.syncDevis.mockResolvedValue({ data: { devis: 1 } })
    rendreCalepinage(CTX.calepinage.id)
    const bouton = await screen.findByTestId('cal-resynchroniser-devis')
    await waitFor(() => expect(bouton).toBeEnabled())
    expect(initRoofToolPro8).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /Enregistrer le calepinage/ })).toBeDisabled()
    await userEvent.click(bouton)
    const refus = await screen.findByTestId('cal-devis-refus')
    expect(refus.textContent).toContain(MESSAGE_ENREGISTREMENT_ECHOUE)
    expect(screen.queryByTestId('cal-devis-conflit')).toBeNull()
    expect(calepinageApi.calepinages.syncDevis).not.toHaveBeenCalled()
    expect(calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel).not.toHaveBeenCalled()
  })

  it('carte présente → Resynchroniser inactif jusqu’à `onHydrationTerminee` (la garde tient)', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.get.mockResolvedValue(reponseContrat('calepinage', 'calepinage_detail'))
    api.get.mockResolvedValue({ data: [] }) // champs personnalisés de la fiche (indépendant de l'ordre)
    let options = null
    initRoofToolPro8.mockImplementation((o) => {
      options = o
      o.onApiReady?.({ serializeLayout: vi.fn(() => ({ version: 2, zones: [] })), snapshot: vi.fn(() => null) })
    })
    rendreCalepinage(CTX.calepinage.id)
    const bouton = await screen.findByTestId('cal-resynchroniser-devis')
    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(bouton).toBeDisabled()
    await act(async () => { options.onHydrationTerminee?.() })
    await waitFor(() => expect(screen.getByTestId('cal-resynchroniser-devis')).toBeEnabled())
  })
})
