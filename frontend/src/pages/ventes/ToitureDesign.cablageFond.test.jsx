import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { cleanup, waitFor } from '@testing-library/react'
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

vi.mock('../../hooks/useHasPermission', () => ({ useHasPermission: () => false }))

const poserFond = vi.fn(() => ({ ok: true }))
const fondDuDocument = vi.fn(() => null)
const motifFondRefuse = vi.fn(() => null)
import '../../test/toitureDesignHarnessCalepinage'
import {
  initRoofToolPro8, rendreCalepinage, rendreDevis, reinitialiserBootMinimal,
  stubberEmpreinteOsm,
} from '../../test/toitureDesignHarness'
import ventesApi from '../../api/ventesApi'
import calepinageApi from '../../api/calepinageApi'
import ToitureDesign from './ToitureDesign'

stubberEmpreinteOsm()

const CTX = exempleContrat('calepinage', 'calepinage_design_context')
const CTX_DEVIS = exempleContrat('ventes', 'devis_design_context')
const PLAN = exempleContrat('calepinage', 'calepinage_plan_importe')
const PLAN_SANS_TAILLE = exempleContrat('calepinage', 'calepinage_plan_importe',
  'exemple_taille_inconnue')

/** Le fond de genre « plan » que le document demande (contrat CALX86). */
function fondPlan() {
  return { kind: 'plan', attachmentId: PLAN.attachment }
}

beforeEach(() => {
  vi.clearAllMocks()
  fondDuDocument.mockReturnValue(null)
  motifFondRefuse.mockReturnValue(null)
  poserFond.mockReturnValue({ ok: true })
  reinitialiserBootMinimal({ fondDuDocument, motifFondRefuse, poserFond })
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

describe('ACAL68 — le fond est posé après l’hydratation', () => {
  it('le fond est posé après l’hydratation, jamais celui d’un document précédent', async () => {
    const fondPrecedent = { kind: 'plan', attachmentId: 999 }
    // À `onApiReady`, le singleton du constructeur décrit encore le document PRÉCÉDENT ;
    // l'hydratation du document ouvert le remplace par SON fond.
    initRoofToolPro8.mockImplementation((options) => {
      fondDuDocument.mockReturnValue(fondPrecedent)
      options?.onApiReady?.({
        serializeLayout: vi.fn(() => ({ version: 2, zones: [] })),
        snapshot: vi.fn(() => null),
        fondDuDocument,
        motifFondRefuse,
        poserFond,
      })
      fondDuDocument.mockReturnValue(fondPlan())
      options?.onHydrationTerminee?.()
    })
    calepinageApi.calepinages.planImporte.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_plan_importe'))

    rendreCalepinage(CTX.calepinage.id)

    await waitFor(() => expect(poserFond).toHaveBeenCalled())
    expect(poserFond).toHaveBeenCalledTimes(1)
    expect(poserFond.mock.calls[0][0]).toEqual(fondPlan())
  })
})

describe('CALX104/CALX403 câblage — `reglagesAtelier` sur la route DEVIS (ACAL37 : le calepinage lié)', () => {
  // ACAL37 (D-ACAL-1) — la route devis ouvre le CALEPINAGE lié : les réglages société
  // passent par la MÊME porte que le mode calepinage (`parametres.get`), jamais par le
  // contexte devis.
  const servirDevis = () => {
    calepinageApi.calepinages.depuisModele.mockResolvedValue(
      { data: { id: CTX.calepinage.id } })
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
  }

  it('les deux sections des réglages société partent TELLES QUELLES au builder', async () => {
    servirDevis()
    calepinageApi.parametres.get.mockResolvedValue({
      data: { zones_types: CTX_DEVIS.zones_types, degagements: CTX_DEVIS.degagements },
    })

    rendreDevis(CTX.calepinage.devis_lie.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(ventesApi.getDevisDesignContext).not.toHaveBeenCalled()
    expect(initRoofToolPro8.mock.calls[0][0].reglagesAtelier).toEqual({
      zones_types: CTX_DEVIS.zones_types,
      degagements: CTX_DEVIS.degagements,
    })
  })

  it('réglages illisibles ⇒ `null` : aucune cote de repli', async () => {
    servirDevis()
    calepinageApi.parametres.get.mockRejectedValue(new Error('403'))

    rendreDevis(CTX.calepinage.devis_lie.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(initRoofToolPro8.mock.calls[0][0].reglagesAtelier).toBeNull()
  })
})
