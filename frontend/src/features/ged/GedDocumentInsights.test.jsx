import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider'

/* WIR70 — le panneau Détails charge la timeline et le rapport ACL d'un
   document, et exporte l'ACL en CSV. */

const H = vi.hoisted(() => ({
  getTimeline: vi.fn(() => Promise.resolve({
    data: [{ evenement: 'creation', message: 'Document créé', utilisateur: 'reda', created_at: '2026-07-18T09:00:00Z' }],
  })),
  // ERR-QAH-GED-DETAILS-CRASH-PERMISSIONS — le backend réel renvoie
  // `{"lignes":[…]}` (ni tableau, ni paginé), pas un tableau brut.
  getPermissionsEffectives: vi.fn(() => Promise.resolve({
    data: { lignes: [{ type: 'utilisateur', id: 5, label: 'Sami', niveau: 'lecture', source: 'heritage_dossier' }] },
  })),
  exportCsv: vi.fn(() => Promise.resolve({ data: 'csv,content' })),
  toggleFavori: vi.fn(() => Promise.resolve({ data: { favori: true } })),
  // WIR163 — gestion des droits AclGed (accorder/révoquer).
  getAcls: vi.fn(() => Promise.resolve({
    data: [{ id: 7, utilisateur_nom: 'sami', role_nom: null, niveau: 'lecture' }],
  })),
  createAcl: vi.fn(() => Promise.resolve({ data: { id: 8 } })),
  deleteAcl: vi.fn(() => Promise.resolve({ data: null })),
  getUsers: vi.fn(() => Promise.resolve({
    data: [{ id: 5, username: 'sami' }, { id: 6, username: 'reda' }],
  })),
  getRoles: vi.fn(() => Promise.resolve({ data: [{ id: 1, nom: 'RH' }] })),
  // XGED15 — chatter générique (FG7), consommé via ChatterWidget/recordsApi.
  getComments: vi.fn(() => Promise.resolve({ data: [] })),
}))
vi.mock('../../api/gedApi', () => ({
  default: {
    getTimeline: H.getTimeline,
    getPermissionsEffectives: H.getPermissionsEffectives,
    exportPermissionsEffectivesCsv: H.exportCsv,
    toggleFavoriDocument: H.toggleFavori,
    getAcls: H.getAcls,
    createAcl: H.createAcl,
    deleteAcl: H.deleteAcl,
    getUsers: H.getUsers,
  },
}))
vi.mock('../../api/rolesApi', () => ({
  default: { getRoles: H.getRoles },
}))
vi.mock('../../api/recordsApi', () => ({
  default: { getComments: H.getComments, createComment: vi.fn(), deleteComment: vi.fn() },
}))

import GedDocumentInsights from './GedDocumentInsights'

const doc = { id: 42, nom: 'Contrat.pdf', favori: false }
const renderPanel = () => {
  const store = configureStore({ reducer: { auth: () => ({ user: { username: 'reda', role: 'admin' } }) } })
  return render(
    <Provider store={store}>
      <ThemeProvider>
        <GedDocumentInsights document={doc} onClose={() => {}} />
      </ThemeProvider>
    </Provider>,
  )
}

beforeEach(() => Object.values(H).forEach((f) => f.mockClear()))
afterEach(() => cleanup())

describe('WIR70 GedDocumentInsights', () => {
  it('étoile pleine pour un favori à la réouverture', async () => {
    H.toggleFavori.mockResolvedValueOnce({ data: { favori: false } })
    const store = configureStore({ reducer: { auth: () => ({ user: { username: 'reda', role: 'admin' } }) } })
    render(
      <Provider store={store}>
        <ThemeProvider>
          <GedDocumentInsights document={{ ...doc, favori: true }} onClose={() => {}} />
        </ThemeProvider>
      </Provider>,
    )
    const etoile = await screen.findByRole('button', { name: 'Retirer des favoris' })
    await userEvent.click(etoile)
    expect(H.toggleFavori).toHaveBeenCalledWith(42, false)
    expect(await screen.findByRole('button', { name: 'Ajouter aux favoris' })).toBeInTheDocument()
  })

  it('charge la timeline du document', async () => {
    renderPanel()
    await waitFor(() => expect(H.getTimeline).toHaveBeenCalledWith(42))
    expect(await screen.findByText('Document créé')).toBeInTheDocument()
  })

  it('affiche le rapport ACL et exporte en CSV', async () => {
    const user = userEvent.setup()
    // jsdom : stub des API de téléchargement.
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:x')
    globalThis.URL.revokeObjectURL = vi.fn()
    renderPanel()
    await waitFor(() => expect(H.getPermissionsEffectives).toHaveBeenCalledWith(42))
    await user.click(screen.getByRole('tab', { name: /Accès/ }))
    expect(await screen.findByText('Sami')).toBeInTheDocument()
    expect(screen.getByText('heritage_dossier')).toBeInTheDocument()
    fireEvent.click(screen.getByText('CSV'))
    await waitFor(() => expect(H.exportCsv).toHaveBeenCalledWith(42))
  })

  it('liste les droits directs et retire une entrée (WIR163)', async () => {
    const user = userEvent.setup()
    renderPanel()
    await user.click(screen.getByRole('tab', { name: /Accès/ }))
    expect(await screen.findByText('sami')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Retirer ce droit/ }))
    await waitFor(() => expect(H.deleteAcl).toHaveBeenCalledWith(7))
    await waitFor(() => expect(H.getAcls).toHaveBeenCalledTimes(2))
  })

  it('accorde un nouveau droit depuis le formulaire de gestion (WIR163)', async () => {
    const user = userEvent.setup()
    renderPanel()
    await user.click(screen.getByRole('tab', { name: /Accès/ }))
    await screen.findByText('sami')
    await user.click(screen.getByRole('combobox', { name: /Choisir un utilisateur/ }))
    await user.click(await screen.findByText('reda'))
    // Nom exact : le regex /Ajouter/ matchait AUSSI le bouton favori
    // (aria-label « Ajouter aux favoris » quand `doc.favori` est faux).
    await user.click(screen.getByRole('button', { name: 'Ajouter' }))
    await waitFor(() => expect(H.createAcl).toHaveBeenCalledWith({
      document: 42, utilisateur: 6, niveau: 'lecture', herite: true,
    }))
  })

  it('ERR-QAH-GED-DETAILS-CRASH-PERMISSIONS — {"lignes":[…]} ne fait jamais planter le panneau', async () => {
    const user = userEvent.setup()
    renderPanel()
    await waitFor(() => expect(H.getPermissionsEffectives).toHaveBeenCalledWith(42))
    await user.click(screen.getByRole('tab', { name: /Accès/ }))
    // Rendu correct des lignes ACL issues de `{lignes:[…]}`, pas de crash.
    expect(await screen.findByText('Sami')).toBeInTheDocument()
    expect(within(screen.getByTestId('ged-acl')).getByText('lecture')).toBeInTheDocument()
    expect(screen.queryByText(/Une erreur est survenue/)).not.toBeInTheDocument()
  })

  it('lit TOUTES les pages des droits directs (51 objets ⇒ 51 lignes)', async () => {
    const tout = Array.from({ length: 51 }, (_, i) => ({
      id: 100 + i, utilisateur_nom: `u${i + 1}`, role_nom: null, niveau: 'lecture',
    }))
    H.getAcls.mockImplementation(({ page = 1 } = {}) => Promise.resolve({
      data: {
        count: 51,
        next: page === 1 ? 'http://x/?page=2' : null,
        results: page === 1 ? tout.slice(0, 50) : tout.slice(50),
      },
    }))
    const user = userEvent.setup()
    renderPanel()
    await user.click(screen.getByRole('tab', { name: /Accès/ }))
    const liste = await screen.findByTestId('ged-acl-entries')
    await waitFor(() => expect(within(liste).getAllByRole('listitem')).toHaveLength(51))
    H.getAcls.mockImplementation(() => Promise.resolve({
      data: [{ id: 7, utilisateur_nom: 'sami', role_nom: null, niveau: 'lecture' }],
    }))
  })

  it('tolère un objet non-tableau (repli défensif) sans planter', async () => {
    H.getPermissionsEffectives.mockResolvedValueOnce({ data: { inattendu: true } })
    renderPanel()
    await waitFor(() => expect(H.getPermissionsEffectives).toHaveBeenCalledWith(42))
    await userEvent.setup().click(screen.getByRole('tab', { name: /Accès/ }))
    expect(await screen.findByText("Aucune règle d'accès")).toBeInTheDocument()
  })

  it('XGED15 — onglet Notes affiche le chatter générique (@mentions) du document', async () => {
    const user = userEvent.setup()
    renderPanel()
    await user.click(screen.getByRole('tab', { name: /Notes/ }))
    await waitFor(() => expect(H.getComments).toHaveBeenCalledWith('ged.document', 42))
  })
})
