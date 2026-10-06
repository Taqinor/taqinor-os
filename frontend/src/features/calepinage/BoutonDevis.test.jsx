import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import userEvent from '@testing-library/user-event'
import { exempleContrat } from '../../test/fixtures/contractSamples'

/* CAL38 — les TROIS issues du pont vers le devis (création, 422 de
   composition, 409 « devis envoyé »), et la preuve qu'AUCUNE ne fabrique de
   texte côté client : la phrase affichée est celle du corps de réponse.

   PACT13 — l'état du calepinage vient de l'exemple COMMITTÉ
   (`apps/calepinage/contract_samples/calepinage_detail.json`), jamais d'un
   objet tapé à la main. */

vi.mock('../../api/calepinageApi', () => ({
  default: { calepinages: { genererDevis: vi.fn(), syncDevis: vi.fn() } },
}))
vi.mock('../../api/ventesApi', () => ({
  default: { reviserDevis: vi.fn() },
}))
const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigateMock }
})

import calepinageApi from '../../api/calepinageApi'
import ventesApi from '../../api/ventesApi'
import BoutonDevis from './BoutonDevis'

const DETAIL = exempleContrat('calepinage', 'calepinage_detail')
const DETAIL_VIDE = exempleContrat('calepinage', 'calepinage_detail',
  'exemple_vide')

/* L'agrégat de détail arrive en PROP : il est lu UNE fois par
   `AtelierPanneaux` et descendu ici (une seule lecture, une seule vérité). */
function rendre(props = {}) {
  return render(
    <MemoryRouter>
      <BoutonDevis calepinageId={DETAIL.id} detail={DETAIL} {...props} />
    </MemoryRouter>,
  )
}

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('BoutonDevis (CAL38)', () => {
  it('détail absent (agrégat pas encore lu) : aucun bouton deviné', async () => {
    rendre({ detail: null })
    expect(screen.queryByTestId('cal-bouton-devis')).toBeNull()
  })

  it('sans devis lié : génère, puis rouvre la conception SUR le devis créé', async () => {
    // `exemple_vide` du contrat : aucun devis, aucune variante.
    calepinageApi.calepinages.genererDevis.mockResolvedValue({
      data: { devis: 42, reference: 'DEV-2609-0042', deduplique: false },
    })

    rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE })
    await userEvent.click(await screen.findByTestId('cal-generer-devis'))

    await waitFor(() => expect(calepinageApi.calepinages.genererDevis)
      .toHaveBeenCalledWith(DETAIL_VIDE.id, {}))
    expect(navigateMock).toHaveBeenCalledWith('/ventes/devis/42/design')
    // Jamais l'autre geste : un calepinage sans devis ne « resynchronise » rien.
    expect(screen.queryByTestId('cal-resynchroniser-devis')).toBeNull()
  })

  it('refus 422 : le message du SERVEUR s’affiche, sous le champ qu’il nomme', async () => {
    const MESSAGE = 'Le catalogue ne porte aucun panneau avec un prix : '
      + 'complétez-le avant de chiffrer.'
    calepinageApi.calepinages.genererDevis.mockRejectedValue({
      response: { status: 422, data: { detail: MESSAGE, errors: [MESSAGE] } },
    })

    rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE })
    await userEvent.click(await screen.findByTestId('cal-generer-devis'))

    const bloc = await screen.findByTestId('cal-devis-refus')
    expect(bloc).toHaveTextContent(MESSAGE)
    // Le champ est NOMMÉ en français ; le message n'est pas réécrit.
    expect(bloc).toHaveTextContent('Devis')
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it('devis lié : resynchronise, et le 409 offre la révision sans rien inventer', async () => {
    const DETAIL_409 = 'Ce devis est déjà parti chez le client : créez une '
      + 'révision pour le modifier.'
    calepinageApi.calepinages.syncDevis.mockRejectedValue({
      response: {
        status: 409,
        data: { detail: DETAIL_409, revision_possible: true },
      },
    })
    ventesApi.reviserDevis.mockResolvedValue({ data: { id: 77 } })

    rendre()
    // L'état SERVEUR décide du geste : un devis lié ⇒ « Resynchroniser ».
    await userEvent.click(await screen.findByTestId('cal-resynchroniser-devis'))

    const conflit = await screen.findByTestId('cal-devis-conflit')
    expect(conflit).toHaveTextContent(DETAIL_409)
    expect(screen.queryByTestId('cal-devis-refus')).toBeNull()

    await userEvent.click(screen.getByTestId('cal-devis-reviser'))
    await waitFor(() => expect(ventesApi.reviserDevis)
      .toHaveBeenCalledWith(DETAIL.devis.id))
    expect(navigateMock).toHaveBeenCalledWith('/ventes/devis/77/design')
  })

  it('409 sans révision possible : le motif s’affiche, aucun bouton « Réviser »', async () => {
    calepinageApi.calepinages.syncDevis.mockRejectedValue({
      response: {
        status: 409,
        data: { detail: 'Ce devis est clos.', revision_possible: false },
      },
    })

    rendre()
    await userEvent.click(await screen.findByTestId('cal-resynchroniser-devis'))

    expect(await screen.findByTestId('cal-devis-conflit'))
      .toHaveTextContent('Ce devis est clos.')
    expect(screen.queryByTestId('cal-devis-reviser')).toBeNull()
  })

  it('variantes présentes mais aucune retenue : bouton désactivé ET expliqué', async () => {
    rendre({
      calepinageId: DETAIL_VIDE.id,
      detail: {
        ...DETAIL_VIDE,
        variantes: { total: 3, retenue_id: null, non_simulees: 0 },
      },
    })

    const bouton = await screen.findByTestId('cal-generer-devis')
    expect(bouton).toBeDisabled()
    expect(screen.getByTestId('cal-devis-variante-manquante'))
      .toHaveTextContent('Choisissez d’abord une variante retenue.')
    await userEvent.click(bouton)
    expect(calepinageApi.calepinages.genererDevis).not.toHaveBeenCalled()
  })

  it('une variante EST retenue : le bouton est actif', async () => {
    expect(DETAIL.variantes.retenue_id).toBeTruthy()

    rendre()

    expect(await screen.findByTestId('cal-resynchroniser-devis')).toBeEnabled()
    expect(screen.queryByTestId('cal-devis-variante-manquante')).toBeNull()
  })

  it('lecture seule : aucun bouton d’écriture n’est rendu', async () => {
    rendre({ lectureSeule: true })

    expect(screen.queryByTestId('cal-bouton-devis')).toBeNull()
  })

  // ACAL93 — en lecture seule, « Réviser (v2) » reste OFFERT quand le serveur
  // le dit possible (jamais masqué) ; aucun geste d'écriture n'apparaît.
  it('lecture seule + revision_possible : seul « Réviser (v2) » est offert', async () => {
    ventesApi.reviserDevis.mockResolvedValue({ data: { id: 81, reference: 'DEV-V2' } })
    rendre({ lectureSeule: true, revisionPossible: true })

    const bouton = await screen.findByTestId('cal-devis-reviser-lecture-seule')
    expect(screen.queryByTestId('cal-resynchroniser-devis')).toBeNull()
    expect(screen.queryByTestId('cal-generer-devis')).toBeNull()
    await userEvent.click(bouton)
    await waitFor(() => expect(ventesApi.reviserDevis).toHaveBeenCalledWith(DETAIL.devis.id))
    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith('/ventes/devis/81/design'))
  })
})

/* ACAL95 — ce que la génération et la resynchro n'ont pas pu faire se LIT
   avant de naviguer ou de recharger. Charges : l'échantillon COMMITTÉ
   `calepinage_publication.json` (PACT13). */
describe('BoutonDevis — retour du serveur (ACAL95)', () => {
  const PUBLICATION = exempleContrat('calepinage', 'calepinage_publication')
  const SYNC = exempleContrat('calepinage', 'calepinage_publication', 'sync_devis')

  it('resynchro : avertissements et lignes ajoutées affichés', async () => {
    const onRecharger = vi.fn()
    const onRelire = vi.fn()
    calepinageApi.calepinages.syncDevis.mockResolvedValue({
      data: { ...SYNC.exemple, lignes_ajoutees: 1 },
    })

    rendre({ onRecharger, onRelire })
    await userEvent.click(await screen.findByTestId('cal-resynchroniser-devis'))

    const bloc = await screen.findByTestId('cal-devis-avertissements')
    expect(bloc).toHaveTextContent(SYNC.exemple.avertissements[0])
    expect(bloc).toHaveTextContent('1 ligne ajoutée au devis')
    // Le rechargement complet attend « J'ai lu ».
    expect(onRecharger).not.toHaveBeenCalled()
    await userEvent.click(screen.getByTestId('cal-devis-j-ai-lu'))
    await waitFor(() => expect(onRecharger).toHaveBeenCalledTimes(1))
    expect(onRelire).toHaveBeenCalledTimes(1)
  })

  it('génération avec avertissements : pas de navigation immédiate', async () => {
    calepinageApi.calepinages.genererDevis.mockResolvedValue({ data: PUBLICATION })

    rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE })
    await userEvent.click(await screen.findByTestId('cal-generer-devis'))

    const bloc = await screen.findByTestId('cal-devis-avertissements')
    expect(bloc).toHaveTextContent(PUBLICATION.avertissements[0])
    expect(bloc).toHaveTextContent(PUBLICATION.marques_manquantes[0])
    expect(navigateMock).not.toHaveBeenCalled()
    expect(screen.getByTestId('cal-devis-ouvrir'))
      .toHaveAttribute('href', `/ventes/devis/${PUBLICATION.devis}/design`)
  })

  it('inchangé : Aucun changement', async () => {
    const onRecharger = vi.fn()
    calepinageApi.calepinages.syncDevis.mockResolvedValue({ data: SYNC.exemple_inchange })

    rendre({ onRecharger })
    await userEvent.click(await screen.findByTestId('cal-resynchroniser-devis'))

    expect(await screen.findByTestId('cal-devis-avertissements'))
      .toHaveTextContent('Aucun changement')
    expect(onRecharger).not.toHaveBeenCalled()
  })

  it('génération sans message : navigation comme aujourd’hui', async () => {
    calepinageApi.calepinages.genererDevis.mockResolvedValue({
      data: { ...PUBLICATION, avertissements: [], marques_manquantes: [] },
    })

    rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE })
    await userEvent.click(await screen.findByTestId('cal-generer-devis'))

    await waitFor(() => expect(navigateMock)
      .toHaveBeenCalledWith(`/ventes/devis/${PUBLICATION.devis}/design`))
    expect(screen.queryByTestId('cal-devis-avertissements')).toBeNull()
  })
})

/* ACAL94 — Générer / Resynchroniser enregistrent d'abord l'ÉCRAN (une seule
   fonction d'enregistrement, prop `enregistrerAvant`) ; un échec n'envoie rien
   et ne recharge rien ; Réviser avertit des retouches non enregistrées sans
   jamais refuser. */
describe('BoutonDevis — enregistrer avant le geste (ACAL94)', () => {
  it('Resynchroniser enregistre l’écran avant sync-devis', async () => {
    const ordre = []
    const enregistrerAvant = vi.fn(async () => { ordre.push('enregistrer'); return true })
    calepinageApi.calepinages.syncDevis.mockImplementation(async () => {
      ordre.push('sync-devis')
      return { data: { inchange: false, lignes_ajoutees: 0, avertissements: [] } }
    })
    const onRecharger = vi.fn(async () => { ordre.push('recharger') })

    rendre({ enregistrerAvant, onRecharger })
    await userEvent.click(await screen.findByTestId('cal-resynchroniser-devis'))

    await waitFor(() => expect(onRecharger).toHaveBeenCalledTimes(1))
    expect(ordre).toEqual(['enregistrer', 'sync-devis', 'recharger'])
  })

  it('échec d’enregistrement : ni sync-devis ni rechargement', async () => {
    const enregistrerAvant = vi.fn(async () => false)
    const onRecharger = vi.fn()

    rendre({ enregistrerAvant, onRecharger })
    await userEvent.click(await screen.findByTestId('cal-resynchroniser-devis'))

    expect(await screen.findByTestId('cal-devis-refus'))
      .toHaveTextContent('n’a pas pu être enregistrée')
    expect(enregistrerAvant).toHaveBeenCalledTimes(1)
    expect(calepinageApi.calepinages.syncDevis).not.toHaveBeenCalled()
    expect(onRecharger).not.toHaveBeenCalled()
  })

  it('Générer enregistre aussi d’abord, et n’appelle rien sur échec', async () => {
    const enregistrerAvant = vi.fn(async () => false)
    rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE, enregistrerAvant })
    await userEvent.click(await screen.findByTestId('cal-generer-devis'))
    await screen.findByTestId('cal-devis-refus')
    expect(calepinageApi.calepinages.genererDevis).not.toHaveBeenCalled()
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it('Réviser sur accepté : avertit sans refuser', async () => {
    calepinageApi.calepinages.syncDevis.mockRejectedValue({
      response: {
        status: 409,
        data: { detail: 'Le devis lié est accepté : utilisez « Réviser ».', revision_possible: true },
      },
    })
    let resoudre
    ventesApi.reviserDevis.mockImplementation(() => new Promise((r) => { resoudre = r }))
    const aDesRetouches = vi.fn(() => true)

    rendre({ enregistrerAvant: vi.fn(async () => true), aDesRetouches })
    await userEvent.click(await screen.findByTestId('cal-resynchroniser-devis'))
    await userEvent.click(await screen.findByTestId('cal-devis-reviser'))

    expect(await screen.findByTestId('cal-devis-retouches'))
      .toHaveTextContent('Retouches non enregistrées')
    // Jamais un refus : la révision part quand même.
    await waitFor(() => expect(ventesApi.reviserDevis).toHaveBeenCalledWith(DETAIL.devis.id))
    resoudre({ data: { id: 78 } })
    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith('/ventes/devis/78/design'))
  })
})
