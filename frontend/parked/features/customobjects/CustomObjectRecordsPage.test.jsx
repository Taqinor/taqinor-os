import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

/* PACT140 — Écran générique des enregistrements d'un objet personnalisé
   (XPLT16/NTEXT2/NTEXT3). Le point structurant prouvé ici : l'écran ne connaît
   AUCUN champ à l'avance — colonnes et formulaire viennent des deux schémas
   auto-générés par le serveur. */

const { get, post, patch, del } = vi.hoisted(() => ({
  get: vi.fn(), post: vi.fn(), patch: vi.fn(), del: vi.fn(),
}))
vi.mock('../../api/axios', () => ({
  default: { get, post, patch, delete: del },
}))

import CustomObjectRecordsPage from './CustomObjectRecordsPage'

const VUE_LISTE = {
  count: 1, next: null, previous: null,
  results: [{ id: 21, objet: 3, data: { nom: 'Clé bureau 2', rendue: true } }],
  colonnes: [
    { code: 'nom', libelle: 'Nom', type: 'text', largeur: 200, formatage: 'texte' },
    { code: 'rendue', libelle: 'Rendue', type: 'boolean', largeur: 90, formatage: 'oui_non' },
  ],
}
const VUE_FORMULAIRE = {
  champs: [
    { code: 'nom', libelle: 'Nom', type: 'text', obligatoire: true, options: [] },
    { code: 'rendue', libelle: 'Rendue', type: 'boolean', obligatoire: false, options: [] },
  ],
}

function mockSchemas({ liste = VUE_LISTE, formulaire = VUE_FORMULAIRE } = {}) {
  get.mockImplementation((url) => {
    if (url.endsWith('/vue-liste/')) return Promise.resolve({ data: liste })
    if (url.endsWith('/vue-formulaire/')) return Promise.resolve({ data: formulaire })
    return Promise.reject(new Error(`URL inattendue : ${url}`))
  })
}

afterEach(() => { cleanup(); vi.clearAllMocks() })

function afficher(code = 'cles') {
  return render(
    <MemoryRouter initialEntries={[`/objets/${code}`]}>
      <Routes>
        <Route path="/objets/:code" element={<CustomObjectRecordsPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('CustomObjectRecordsPage (PACT140)', () => {
  it('génère colonnes et formulaire à partir des schémas serveur', async () => {
    mockSchemas()
    afficher()

    const table = await screen.findByTestId('table-enregistrements')
    expect(within(table).getByText('Nom')).toBeInTheDocument()
    expect(within(table).getByText('Rendue')).toBeInTheDocument()

    const ligne = screen.getByTestId('enregistrement-21')
    expect(within(ligne).getByText('Clé bureau 2')).toBeInTheDocument()
    // Le formatage « oui_non » annoncé par le serveur est appliqué.
    expect(within(ligne).getByText('Oui')).toBeInTheDocument()

    // Les deux schémas sont bien lus depuis le code de l'URL.
    expect(get).toHaveBeenCalledWith('/custom-fields/custom-objects/cles/vue-liste/')
    expect(get).toHaveBeenCalledWith('/custom-fields/custom-objects/cles/vue-formulaire/')
    // Le formulaire est rendu à partir du schéma, pas d'une liste codée en dur.
    expect(screen.getByLabelText('Nom *')).toBeInTheDocument()
    expect(screen.getByLabelText('Rendue')).toBeInTheDocument()
  })

  it('crée un enregistrement avec les valeurs saisies', async () => {
    const user = userEvent.setup()
    mockSchemas()
    post.mockResolvedValue({ data: {} })
    afficher()

    await screen.findByTestId('table-enregistrements')
    await user.type(screen.getByLabelText('Nom *'), 'Clé atelier')
    await user.click(screen.getByLabelText('Rendue'))
    await user.click(screen.getByRole('button', { name: /Ajouter l'enregistrement/ }))

    await waitFor(() => expect(post).toHaveBeenCalledWith(
      '/custom-fields/custom-objects/cles/records/',
      { data: { nom: 'Clé atelier', rendue: true } },
    ))
    // `company` n'est jamais envoyée : la société vient du serveur.
    expect(Object.keys(post.mock.calls[0][1])).toEqual(['data'])
  })

  it('modifie un enregistrement existant', async () => {
    const user = userEvent.setup()
    mockSchemas()
    patch.mockResolvedValue({ data: {} })
    afficher()

    await screen.findByTestId('enregistrement-21')
    await user.click(screen.getByRole('button', { name: 'Modifier' }))

    // Le formulaire est pré-rempli avec les données de la ligne.
    const champNom = screen.getByLabelText('Nom *')
    expect(champNom).toHaveValue('Clé bureau 2')
    await user.clear(champNom)
    await user.type(champNom, 'Clé bureau 3')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(patch).toHaveBeenCalledWith(
      '/custom-fields/custom-objects/cles/records/21/',
      { data: { nom: 'Clé bureau 3', rendue: true } },
    ))
  })

  it('affiche un état vide quand l\'objet n\'a encore aucun champ', async () => {
    mockSchemas({
      liste: { count: 0, results: [], colonnes: [] },
      formulaire: { champs: [] },
    })
    afficher()

    expect(await screen.findByText('Aucun champ défini pour cet objet'))
      .toBeInTheDocument()
  })

  it('affiche un état clair quand l\'objet est introuvable, sans planter', async () => {
    get.mockRejectedValue({ response: { status: 404 } })
    afficher('inconnu')

    expect(await screen.findByText('Objet personnalisé introuvable'))
      .toBeInTheDocument()
    expect(screen.getByText('Retour aux objets personnalisés'))
      .toBeInTheDocument()
  })
})
