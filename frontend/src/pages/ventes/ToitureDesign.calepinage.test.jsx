import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import userEvent from '@testing-library/user-event'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   CAL37 — MODE `calepinage` de l'atelier 3D : le MÊME builder, un quatrième
   mode. Ce que ce fichier prouve :

   1. `/calepinage/:id` boote le builder sur UN SEUL appel (`design-context`),
      hydrate depuis le calepinage et enregistre par `POST …/layout/` ;
   2. la cible peut être ABSENTE (`cible: null`, `exemple_vide` du contrat) —
      l'écran l'écrit « non renseignée » et n'invente AUCUNE puissance ;
   3. le mode DEVIS ne bouge pas : monté dans ce même harnais, il ne frappe
      AUCUNE route calepinage (garde de non-régression demandée par CAL37).

   PACT13 — les charges utiles viennent des exemples COMMITTÉS
   (`apps/calepinage/contract_samples/calepinage_design_context.json` et son
   jumeau ventes), jamais d'un objet tapé à la main : si le serveur change de
   forme, ce test casse tout seul.
   ========================================================================== */

vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))
vi.mock('../../api/ventesApi', () => ({
  default: {
    getDevisDesignContext: vi.fn(),
    getDevisById: vi.fn(() => Promise.resolve({ data: {} })),
    syncDevisLayout: vi.fn(),
    shareLinkDevis: vi.fn(),
    whatsappPreviewDevis: vi.fn(),
    reviserDevis: vi.fn(),
  },
}))
vi.mock('../../api/aoApi', () => ({
  default: { affaires: { designContext: vi.fn(), enregistrerLayout: vi.fn() } },
}))
// Le double SUIT la surface RÉELLE de `calepinageApi` : chaque méthode du
// module est remplacée par un espion qui résout `{ data: null }`. Une
// liste écrite à la main laissait `calepinageApi.parametres` indéfini —
// et le panneau « allées » de l'atelier (CAL71) faisait alors planter tout
// l'écran (`Cannot read properties of undefined`), ce qui rendait les
// assertions illisibles.
vi.mock('../../api/calepinageApi', async (importOriginal) => {
  const actual = await importOriginal()
  const espionner = (groupe) => Object.fromEntries(
    Object.entries(groupe).map(([cle, valeur]) => [
      cle,
      typeof valeur === 'function'
        ? vi.fn(() => Promise.resolve({ data: null }))
        : valeur,
    ]),
  )
  return {
    default: Object.fromEntries(
      Object.entries(actual.default).map(([nom, groupe]) => [
        nom,
        (groupe && typeof groupe === 'object') ? espionner(groupe) : groupe,
      ]),
    ),
  }
})
vi.mock('../../api/crmApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: {
      ...actual.default,
      getLeadPhotoToit: vi.fn(() => Promise.resolve({
        data: { visite_id: null, url: null, texture_calage: null },
      })),
    },
  }
})
vi.mock('../../lib/toast', () => ({ toastInfo: vi.fn() }))

const LAYOUT = { version: 2, zones: [{ id: 'z1' }] }
const serializeLayout = vi.fn(() => LAYOUT)
const snapshot = vi.fn(() => null)
const setReferenceContourVisible = vi.fn()
const recommencerDepuisTraceClient = vi.fn(() => true)
const initRoofToolPro8 = vi.fn((options) => {
  options?.onApiReady?.({
    serializeLayout, snapshot, setReferenceContourVisible,
    recommencerDepuisTraceClient,
  })
})
vi.mock('@roofbuilder', () => ({ initRoofToolPro8: (...a) => initRoofToolPro8(...a) }))

import ventesApi from '../../api/ventesApi'
import calepinageApi from '../../api/calepinageApi'
import { toastInfo } from '../../lib/toast'
import ToitureDesign from './ToitureDesign'

const CTX = exempleContrat('calepinage', 'calepinage_design_context')
const CTX_VIDE = exempleContrat('calepinage', 'calepinage_design_context',
  'exemple_vide')

function rendreCalepinage(id) {
  return render(
    <MemoryRouter initialEntries={[`/calepinage/${id}`]}>
      <Routes>
        <Route path="/calepinage/:id"
          element={<ToitureDesign mode="calepinage" />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  delete window.__taqinorRoofBooted
  serializeLayout.mockReturnValue(LAYOUT)
  snapshot.mockReturnValue(null)
  initRoofToolPro8.mockImplementation((options) => {
    options?.onApiReady?.({
      serializeLayout, snapshot, setReferenceContourVisible,
      recommencerDepuisTraceClient,
    })
  })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ToitureDesign — mode calepinage (CAL37)', () => {
  it('boote sur UN SEUL appel design-context et hydrate depuis le calepinage', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))

    rendreCalepinage(CTX.calepinage.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(calepinageApi.calepinages.designContext).toHaveBeenCalledTimes(1)
    expect(calepinageApi.calepinages.designContext)
      .toHaveBeenCalledWith(String(CTX.calepinage.id))
    // Aucun contexte de DEVIS n'est exigé : le mode calepinage ne frappe
    // jamais la porte ventes (décision fondateur D3).
    expect(ventesApi.getDevisDesignContext).not.toHaveBeenCalled()

    const options = initRoofToolPro8.mock.calls[0][0]
    expect(options.maptilerKey).toBe(CTX.carte.maptilerKey)
    expect(options.hydrate.lead).toBeUndefined()
    expect(options.hydrate.devis).toEqual({
      // Un calepinage N'EST PAS un devis : `id` reste nul.
      id: null,
      geometrie: {
        roof_layout: CTX.geometrie.roof_layout,
        roof_point: CTX.geometrie.pin,
        roof_outline: CTX.geometrie.outline,
      },
      cible: {
        panneaux: CTX.cible.panneaux,
        panel_watt: CTX.cible.panel_watt,
        scenario: CTX.cible.scenario,
      },
      // Ce calepinage-là porte un devis lié : sa cible EST une cible vendue,
      // et l'atelier se comporte alors exactement comme en mode devis.
      cibleVendue: true,
      fullName: CTX.calepinage.titre,
    })

    expect(await screen.findByRole('heading', { level: 1 }))
      .toHaveTextContent(CTX.calepinage.titre)
    expect(screen.queryByTestId('pv20-lecture-seule')).toBeNull()
    // Le bouton du flux LEAD n'existe jamais ici.
    expect(screen.queryByRole('button',
      { name: /Générer le devis & envoyer au client/ })).toBeNull()
  })

  it('enregistre la conception par POST layout, puis envoie l’aperçu', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.enregistrerLayoutCalepinage.mockResolvedValue(
      { data: { inchange: false, version: 3 } })
    calepinageApi.calepinages.envoyerImage.mockResolvedValue({ data: {} })
    snapshot.mockReturnValue('data:image/png;base64,aGk=')

    rendreCalepinage(CTX.calepinage.id)
    const bouton = await screen.findByRole('button',
      { name: /Enregistrer le calepinage/ })
    await userEvent.click(bouton)

    await waitFor(() => expect(calepinageApi.calepinages.enregistrerLayoutCalepinage)
      .toHaveBeenCalledWith(String(CTX.calepinage.id), LAYOUT))
    await waitFor(() => expect(calepinageApi.calepinages.envoyerImage)
      .toHaveBeenCalledTimes(1))
    expect(calepinageApi.calepinages.envoyerImage.mock.calls[0][0])
      .toBe(String(CTX.calepinage.id))
    expect(calepinageApi.calepinages.envoyerImage.mock.calls[0][1])
      .toBeInstanceOf(FormData)
    // Aucune écriture ventes : le devis n'est pas touché par un enregistrement.
    expect(ventesApi.syncDevisLayout).not.toHaveBeenCalled()
  })

  it('conception inchangée : on le DIT, et aucune image n’est envoyée', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.enregistrerLayoutCalepinage.mockResolvedValue(
      { data: { inchange: true, version: null } })
    snapshot.mockReturnValue('data:image/png;base64,aGk=')

    rendreCalepinage(CTX.calepinage.id)
    await userEvent.click(await screen.findByRole('button',
      { name: /Enregistrer le calepinage/ }))

    await waitFor(() => expect(toastInfo).toHaveBeenCalledWith('Aucun changement'))
    expect(calepinageApi.calepinages.envoyerImage).not.toHaveBeenCalled()
  })

  it('refus 400 : le message du SERVEUR s’affiche, jamais un texte fabriqué', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.enregistrerLayoutCalepinage.mockRejectedValue({
      response: {
        status: 400,
        data: { roof_layout: 'Conception manquante ou invalide : le corps attendu est le document de conception.' },
      },
    })

    rendreCalepinage(CTX.calepinage.id)
    await userEvent.click(await screen.findByRole('button',
      { name: /Enregistrer le calepinage/ }))

    expect(await screen.findByTestId('cal-erreur-enregistrement'))
      .toHaveTextContent('Conception manquante ou invalide')
  })

  it('cible absente : « non renseignée », jamais une puissance inventée', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context', 'exemple_vide'))

    rendreCalepinage(CTX_VIDE.calepinage.id)

    // Le contrat sert `carte.available: false` sur l'exemple vide : le builder
    // ne boote pas, et l'écran DIT pourquoi au lieu d'afficher une carte morte.
    expect(await screen.findByRole('alert'))
      .toHaveTextContent(/clé MapTiler/)
    expect(initRoofToolPro8).not.toHaveBeenCalled()
    // Les avertissements SERVEUR sont affichés tels quels.
    expect(screen.getByTestId('pv20-avertissements'))
      .toHaveTextContent(CTX_VIDE.avertissements[0])
  })

  it('cible nulle avec une carte disponible : le panneau écrit « non renseignée »', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue({
      data: {
        ...CTX_VIDE,
        carte: CTX.carte,
      },
    })

    rendreCalepinage(CTX_VIDE.calepinage.id)

    expect(await screen.findByTestId('cal-cible-panneaux'))
      .toHaveTextContent('non renseignée')
    const options = initRoofToolPro8.mock.calls[0][0]
    // AUCUN chiffre n'est fabriqué pour le builder.
    expect(options.hydrate.devis.cible).toEqual({
      panneaux: null, panel_watt: null, scenario: null,
    })
    // `outline: []` n'est pas un polygone : on ne l'envoie pas.
    expect(options.hydrate.devis.geometrie.roof_outline).toBeNull()
  })

  /* ──────────────────────────────────────────────────────────────────────
     RÉGRESSION (constat en production, 20/09/2026) — `/calepinage/<id>` né
     d'un LEAD restait figé : « Surface : — », recommandation « — », aucune
     requête de rendement, alors que `/ventes/devis/<id>/design` ouvrait le
     MÊME toit du MÊME lead en quelques secondes. Deux causes, l'une ici :
     l'écran envoyait au builder une cible entièrement nulle SANS dire qu'il
     n'y a aucune vente derrière ce document — et le builder lit alors
     « cible vendue de ZÉRO panneau » (L2, incident DEV-202608-0016) et
     refuse de poser quoi que ce soit. Le contrat dit pourtant l'inverse :
     « LA CIBLE N'EST JAMAIS INVENTÉE », `cible: null` = pas de cible.
     ────────────────────────────────────────────────────────────────────── */
  it('calepinage né d’un lead : le builder reçoit un centre, le tracé client et AUCUNE cible vendue', async () => {
    const CTX_LEAD = exempleContrat('calepinage', 'calepinage_design_context',
      'exemple_sans_devis')
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context',
        'exemple_sans_devis'))

    rendreCalepinage(CTX_LEAD.calepinage.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    const options = initRoofToolPro8.mock.calls[0][0]
    // Le CENTRE : sans l'épingle du lead, la carte démarre au niveau Maroc et
    // rien ne s'affiche jamais.
    expect(options.hydrate.devis.geometrie.roof_point)
      .toEqual(CTX_LEAD.geometrie.pin)
    // LE PAN VIENT DU TRACÉ CLIENT : c'est ce contour, et lui seul, que
    // `hydrateFromDevis` referme en zone active (aucun re-tracé manuel).
    expect(options.hydrate.devis.geometrie.roof_outline)
      .toEqual(CTX_LEAD.geometrie.outline)
    expect(options.referenceContour).toEqual(CTX_LEAD.geometrie.contour_client)
    // AUCUN chiffre inventé…
    expect(options.hydrate.devis.cible).toEqual({
      panneaux: null, panel_watt: null, scenario: null,
    })
    // …mais le silence est QUALIFIÉ : rien n'a été vendu, donc l'optimiseur
    // travaille librement au lieu de se figer sur une cible de zéro.
    expect(options.hydrate.devis.cibleVendue).toBe(false)
  })

  it('lecture seule : la raison du serveur s’affiche et le bouton disparaît', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue({
      data: {
        ...CTX,
        modifiable: false,
        raison_lecture_seule: 'Le devis lié est déjà parti chez le client.',
      },
    })

    rendreCalepinage(CTX.calepinage.id)

    expect(await screen.findByTestId('pv20-lecture-seule'))
      .toHaveTextContent('Le devis lié est déjà parti chez le client.')
    expect(screen.queryByRole('button',
      { name: /Enregistrer le calepinage/ })).toBeNull()
    // Le panneau du module reste monté : consulter une conception figée est
    // exactement ce que la lecture seule doit permettre.
    expect(screen.getByTestId('cal-atelier-panneaux')).toBeTruthy()
  })
})

describe('ToitureDesign — le mode devis ne bouge pas (garde CAL37)', () => {
  it('ne frappe AUCUNE route calepinage', async () => {
    ventesApi.getDevisDesignContext.mockResolvedValue(
      reponseContrat('ventes', 'devis_design_context'))
    const CTX_DEVIS = exempleContrat('ventes', 'devis_design_context')

    render(
      <MemoryRouter initialEntries={[`/ventes/devis/${CTX_DEVIS.devis.id}/design`]}>
        <Routes>
          <Route path="/ventes/devis/:id/design"
            element={<ToitureDesign mode="devis" />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(ventesApi.getDevisDesignContext).toHaveBeenCalledTimes(1)
    for (const appel of Object.values(calepinageApi.calepinages)) {
      expect(appel).not.toHaveBeenCalled()
    }
    // Ni le panneau du module, ni son bouton d'enregistrement.
    expect(screen.queryByTestId('cal-atelier-panneaux')).toBeNull()
    expect(screen.queryByTestId('cal-enregistrer-calepinage')).toBeNull()
  })
})
