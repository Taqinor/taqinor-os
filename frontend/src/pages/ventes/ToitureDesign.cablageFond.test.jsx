import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   CÂBLAGE DU CALQUE DE FOND (lot 2, Groupe CALX) côté PAGE HÔTE.

   CALX107 — l'atelier sait peindre un fond de genre « plan » (`underlay.ts` +
   `mapDraw.setFond`) mais il ne parle jamais à Django : il attend une
   `RessourceFond` (`url`, `tailleImage`). Le câblage HOOKS2 ne servait que le
   genre « photo », faute d'une porte publiant l'URL et la taille de la pièce
   jointe d'un plan. `GET calepinages/<pk>/plan-importe/` la publie désormais :
   ce fichier prouve la ligne d'appel qui l'amène au constructeur, et RIEN
   d'autre.

   PACT13 — les charges utiles viennent des exemples COMMITTÉS, jamais d'un
   objet tapé à la main.
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
// Le double SUIT la surface RÉELLE de `calepinageApi` : une liste écrite à la
// main laisserait des groupes indéfinis et ferait planter l'écran au lieu de
// montrer l'assertion.
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
      getRoofFootprint: vi.fn(() => Promise.resolve({ data: {} })),
    },
  }
})
vi.mock('../../lib/toast', () => ({ toastInfo: vi.fn() }))
vi.mock('../../hooks/useHasPermission', () => ({ useHasPermission: () => false }))

const poserFond = vi.fn(() => ({ ok: true }))
const fondDuDocument = vi.fn(() => null)
const motifFondRefuse = vi.fn(() => null)
const initRoofToolPro8 = vi.fn()
vi.mock('@roofbuilder', () => ({ initRoofToolPro8: (...a) => initRoofToolPro8(...a) }))

import ventesApi from '../../api/ventesApi'
import calepinageApi from '../../api/calepinageApi'
import ToitureDesign from './ToitureDesign'

const CTX = exempleContrat('calepinage', 'calepinage_design_context')
const CTX_DEVIS = exempleContrat('ventes', 'devis_design_context')
const PLAN = exempleContrat('calepinage', 'calepinage_plan_importe')
const PLAN_SANS_TAILLE = exempleContrat('calepinage', 'calepinage_plan_importe',
  'exemple_taille_inconnue')

/** Le fond de genre « plan » que le document demande (contrat CALX86). */
function fondPlan() {
  return { kind: 'plan', attachmentId: PLAN.attachment }
}

function rendreCalepinage(id) {
  return render(
    <MemoryRouter initialEntries={[`/calepinage/${id}`]}>
      <Routes>
        <Route path="/calepinage/:id" element={<ToitureDesign mode="calepinage" />} />
      </Routes>
    </MemoryRouter>,
  )
}

function rendreDevis(id) {
  return render(
    <MemoryRouter initialEntries={[`/ventes/devis/${id}/design`]}>
      <Routes>
        <Route path="/ventes/devis/:id/design"
          element={<ToitureDesign mode="devis" />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  delete window.__taqinorRoofBooted
  fondDuDocument.mockReturnValue(null)
  motifFondRefuse.mockReturnValue(null)
  poserFond.mockReturnValue({ ok: true })
  initRoofToolPro8.mockImplementation((options) => {
    options?.onApiReady?.({
      serializeLayout: vi.fn(() => ({ version: 2, zones: [] })),
      snapshot: vi.fn(() => null),
      fondDuDocument,
      motifFondRefuse,
      poserFond,
    })
  })
  calepinageApi.calepinages.designContext.mockResolvedValue(
    reponseContrat('calepinage', 'calepinage_design_context'))
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('CALX107 câblage — le PLAN importé atteint enfin le calque de fond', () => {
  it('va chercher la pièce jointe et redonne `url` + `tailleImage` au constructeur', async () => {
    fondDuDocument.mockReturnValue(fondPlan())
    calepinageApi.calepinages.planImporte.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_plan_importe'))

    rendreCalepinage(CTX.calepinage.id)

    await waitFor(() => expect(poserFond).toHaveBeenCalled())
    expect(calepinageApi.calepinages.planImporte)
      .toHaveBeenCalledWith(String(CTX.calepinage.id))
    expect(poserFond).toHaveBeenCalledWith(fondPlan(), {
      url: PLAN.url,
      tailleImage: { largeur: PLAN.largeur, hauteur: PLAN.hauteur },
    })
  })

  it('taille non publiée ⇒ `tailleImage: null` — aucune étendue supposée', async () => {
    fondDuDocument.mockReturnValue(fondPlan())
    calepinageApi.calepinages.planImporte.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_plan_importe',
        'exemple_taille_inconnue'))

    rendreCalepinage(CTX.calepinage.id)

    await waitFor(() => expect(poserFond).toHaveBeenCalled())
    expect(PLAN_SANS_TAILLE.largeur).toBeNull()
    expect(poserFond).toHaveBeenCalledWith(fondPlan(), {
      url: PLAN_SANS_TAILLE.url,
      tailleImage: null,
    })
  })

  it('porte en échec (404 nommé, réseau) ⇒ le fond part SANS ressource, et le constructeur dit pourquoi', async () => {
    fondDuDocument.mockReturnValue(fondPlan())
    calepinageApi.calepinages.planImporte.mockRejectedValue(
      { response: { status: 404 } })

    rendreCalepinage(CTX.calepinage.id)

    await waitFor(() => expect(poserFond).toHaveBeenCalled())
    expect(poserFond).toHaveBeenCalledWith(fondPlan(), {})
  })

  it('un fond de genre PHOTO ne passe jamais par la porte des plans', async () => {
    fondDuDocument.mockReturnValue({ kind: 'photo', photoSiteId: 7 })
    calepinageApi.calepinages.photos.mockResolvedValue({
      data: { photos: [] },
    })

    rendreCalepinage(CTX.calepinage.id)

    await waitFor(() => expect(poserFond).toHaveBeenCalled())
    expect(calepinageApi.calepinages.planImporte).not.toHaveBeenCalled()
  })

  it('aucun fond demandé ⇒ aucune requête : l’écran d’aujourd’hui, inchangé', async () => {
    fondDuDocument.mockReturnValue(null)

    rendreCalepinage(CTX.calepinage.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(calepinageApi.calepinages.planImporte).not.toHaveBeenCalled()
    expect(poserFond).not.toHaveBeenCalled()
  })
})

describe('CALX104/CALX403 câblage — `reglagesAtelier` en mode DEVIS, SANS requête annexe', () => {
  it('les deux sections du contexte agrégé partent TELLES QUELLES au builder', async () => {
    ventesApi.getDevisDesignContext.mockResolvedValue(
      reponseContrat('ventes', 'devis_design_context'))

    rendreDevis(CTX_DEVIS.devis.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    // LA garantie du mode DEVIS : un seul appel, aucune porte de complément.
    expect(ventesApi.getDevisDesignContext).toHaveBeenCalledTimes(1)
    expect(calepinageApi.parametres.get).not.toHaveBeenCalled()

    expect(initRoofToolPro8.mock.calls[0][0].reglagesAtelier).toEqual({
      zones_types: CTX_DEVIS.zones_types,
      degagements: CTX_DEVIS.degagements,
    })
  })

  it('un contexte SANS les deux sections ⇒ `null` : aucune cote de repli', async () => {
    const sansReglages = { ...CTX_DEVIS }
    delete sansReglages.zones_types
    delete sansReglages.degagements
    ventesApi.getDevisDesignContext.mockResolvedValue({ data: sansReglages })

    rendreDevis(CTX_DEVIS.devis.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(initRoofToolPro8.mock.calls[0][0].reglagesAtelier).toBeNull()
    expect(calepinageApi.parametres.get).not.toHaveBeenCalled()
  })
})
