import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* ============================================================================
   PACT170 — « Questions terrain » : repère → fiche → export, monté de bout en
   bout.
   ----------------------------------------------------------------------------
   `Annotateur` (qui porte `RepereMarker`), `QuestionFiche` et `ExportQR`
   étaient livrés, testés, et importés par PERSONNE : l'écran réellement monté
   (`SeriesPage`) n'affichait que le tableau des séries. Ce que ces tests
   protègent :
     1. on peut poser un repère sur une image DEPUIS cet écran ;
     2. ouvrir sa fiche ouvre la question DE CE REPÈRE — celle du serveur si
        elle existe, sinon un brouillon rattaché à la série (jamais celle d'un
        autre repère) ;
     3. « Enregistrer » écrit VRAIMENT (aoApi.questions), en création comme en
        correction ;
     4. le refus produit est tenu côté écran comme côté serveur : pas d'impact
        chiffré, pas de question créée — et le motif est ÉCRIT ;
     5. l'export « prêt à coller » reçoit l'image ANNOTÉE, pas la photo nue.

   `svgToPng` est mocké : la rasterisation réelle a besoin d'un canvas que
   jsdom n'a pas — ce que ce fichier teste est le CÂBLAGE, pas le rendu PNG
   (déjà couvert par `svgToPng.test.mjs`).
   ========================================================================== */

const mocks = vi.hoisted(() => ({
  seriesList: vi.fn(),
  seriesCreate: vi.fn(),
  questionsCreate: vi.fn(),
  questionsUpdate: vi.fn(),
  svgVersPng: vi.fn(),
  svgVersPngBlob: vi.fn(),
}))

vi.mock('../../../api/aoApi', () => ({
  default: {
    seriesQR: { list: mocks.seriesList, create: mocks.seriesCreate },
    questions: { create: mocks.questionsCreate, update: mocks.questionsUpdate },
  },
}))

vi.mock('../studio/svgToPng', () => ({
  svgVersPng: mocks.svgVersPng,
  svgVersPngBlob: mocks.svgVersPngBlob,
  LARGEUR_EXPORT_DEFAUT: 1000,
}))

// Seul `toast` est neutralisé : les primitifs de `ui` restent les VRAIS (un
// écran testé contre des composants factices ne prouverait rien).
vi.mock('../../../ui', async () => {
  const actual = await vi.importActual('../../../ui')
  return { ...actual, toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }
})

import SeriesPage from './SeriesPage'

const QUESTION_A = {
  id: 11,
  repere: 'A',
  texte: 'Emprise de l’édicule à confirmer',
  statut: 'posee',
  statut_display: 'Posée',
  reponse: '',
  impact_min_modules: -2,
  impact_max_modules: 0,
}

const serie = (questions) => ({
  id: 3,
  numero: 1,
  date_envoi: '2026-08-01',
  canal: 'email',
  canal_display: 'Courriel',
  destinataire: 'Maîtrise d’œuvre',
  impact_total_modules: { min: -2, max: 0 },
  questions,
})

beforeEach(() => {
  vi.clearAllMocks()
  mocks.seriesList.mockResolvedValue({ data: [serie([QUESTION_A])] })
  mocks.questionsCreate.mockResolvedValue({ data: { id: 12 } })
  mocks.questionsUpdate.mockResolvedValue({ data: { id: 11 } })
  mocks.svgVersPng.mockResolvedValue({
    dataUrl: 'data:image/png;base64,AAAA', largeur: 1000, hauteur: 750,
  })
})

/** Déplie la série, charge une image et pose UN repère (le repère « A »). */
async function poserUnRepere() {
  await screen.findByText('Série 1')
  await userEvent.click(screen.getByRole('button', { name: 'Voir' }))

  const fichier = new File(['photo'], 'toiture.png', { type: 'image/png' })
  await userEvent.upload(screen.getByLabelText('Charger une image à annoter'), fichier)

  // L'annotateur ne rend son SVG qu'une fois l'image lue (FileReader).
  const ajouter = await screen.findByRole('button', { name: 'Ajouter un repère' })
  await userEvent.click(ajouter)
  return screen.findByRole('button', { name: 'Ouvrir la fiche du repère A' })
}

describe('SeriesPage — annotateur, fiche question et export (PACT170)', () => {
  it('permet de poser un repère sur une image depuis l’écran réellement monté', async () => {
    render(<SeriesPage affaireId={7} />)

    await poserUnRepere()

    expect(screen.getByLabelText('Annotateur d’image — cliquez pour poser un repère'))
      .toBeInTheDocument()
    expect(screen.getByText('1 repère(s)')).toBeInTheDocument()
  })

  it('ouvrir la fiche d’un repère ouvre LA question de ce repère (celle du serveur)', async () => {
    render(<SeriesPage affaireId={7} />)
    const ouvrir = await poserUnRepere()

    await userEvent.click(ouvrir)

    expect(await screen.findByText('Fiche — Repère A')).toBeInTheDocument()
    expect(document.querySelector('[data-question-fiche="A"]')).not.toBeNull()
    // Les valeurs viennent du serveur, jamais d'un brouillon vide qui les
    // écraserait au premier enregistrement.
    expect(screen.getByLabelText('Question')).toHaveValue('Emprise de l’édicule à confirmer')
    expect(screen.getByLabelText('Impact minimal (modules)')).toHaveValue(-2)
  })

  it('corriger une question existante PATCHe la ressource réelle', async () => {
    render(<SeriesPage affaireId={7} />)
    const ouvrir = await poserUnRepere()
    await userEvent.click(ouvrir)
    await screen.findByText('Fiche — Repère A')

    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer la question' }))

    await waitFor(() => expect(mocks.questionsUpdate).toHaveBeenCalled())
    const [id, corps] = mocks.questionsUpdate.mock.calls[0]
    expect(id).toBe(11)
    expect(corps.impact_min_modules).toBe(-2)
    expect(mocks.questionsCreate).not.toHaveBeenCalled()
  })

  it('un repère SANS question au serveur crée la question, rattachée à la série', async () => {
    mocks.seriesList.mockResolvedValue({ data: [serie([])] })
    render(<SeriesPage affaireId={7} />)
    const ouvrir = await poserUnRepere()
    await userEvent.click(ouvrir)
    await screen.findByText('Fiche — Repère A')

    await userEvent.type(screen.getByLabelText('Question'), 'Hauteur du muret ?')
    await userEvent.type(screen.getByLabelText('Impact maximal (modules)'), '3')
    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer la question' }))

    await waitFor(() => expect(mocks.questionsCreate).toHaveBeenCalled())
    const corps = mocks.questionsCreate.mock.calls[0][0]
    expect(corps.serie).toBe(3)
    expect(corps.repere).toBe('A')
    expect(corps.texte).toBe('Hauteur du muret ?')
    expect(corps.impact_max_modules).toBe(3)
  })

  it('une question SANS impact chiffré n’est pas créée, et le motif est ÉCRIT', async () => {
    mocks.seriesList.mockResolvedValue({ data: [serie([])] })
    render(<SeriesPage affaireId={7} />)
    const ouvrir = await poserUnRepere()
    await userEvent.click(ouvrir)
    await screen.findByText('Fiche — Repère A')

    // « Enregistrer la réponse » ne porte aucun impact : la création doit être
    // refusée avec la règle produit, pas partir en 400 traduit en « erreur ».
    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer la réponse' }))

    expect(await screen.findByText(/chiffrez d’abord son impact prévisionnel/i))
      .toBeInTheDocument()
    expect(mocks.questionsCreate).not.toHaveBeenCalled()
  })

  it('l’export reçoit l’image ANNOTÉE, préparée depuis le SVG de l’annotateur', async () => {
    render(<SeriesPage affaireId={7} />)
    await poserUnRepere()

    // Le panneau d'export est monté dès l'ouverture de la série.
    expect(document.querySelector('[data-export-qr]')).not.toBeNull()

    await userEvent.click(screen.getByRole('button', { name: 'Préparer l’image annotée' }))

    await waitFor(() => expect(mocks.svgVersPng).toHaveBeenCalled())
    await waitFor(() => expect(
      document.querySelector('[data-export-qr] img[src^="data:image/png"]'),
    ).not.toBeNull())
  })

  it('sans repère posé, la préparation de l’export est refusée AVEC sa raison', async () => {
    render(<SeriesPage affaireId={7} />)
    await screen.findByText('Série 1')
    await userEvent.click(screen.getByRole('button', { name: 'Voir' }))

    expect(await screen.findByRole('button', { name: 'Préparer l’image annotée' }))
      .toBeDisabled()
    expect(screen.getByText(/Posez au moins un repère/)).toBeInTheDocument()
  })
})
