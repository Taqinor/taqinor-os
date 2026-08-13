import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* PACT58 — Contrôle documentaire de projet : registre et révisions (FG297). */

function mockMatchMedia() {
  window.matchMedia = (query) => ({
    matches: false, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })
}
beforeAll(() => { if (typeof window.matchMedia !== 'function') mockMatchMedia() })

const inst = vi.hoisted(() => ({
  getInstallations: vi.fn(() => Promise.resolve({ data: { count: 1, results: [
    { id: 9, reference: 'CH-009' },
  ] } })),
  getDocumentsProjet: vi.fn(() => Promise.resolve({ data: { count: 1, results: [
    { id: 4, titre: 'Schéma unifilaire toiture A', type_doc: 'schema_unifilaire', type_doc_display: 'Schéma unifilaire', nb_revisions: 1, inst_revisions: [
      { id: 30, indice: 'B', date_revision: '2026-08-01', auteur_nom: 'ahmed' },
    ] },
  ] } })),
  createDocumentProjet: vi.fn(() => Promise.resolve({ data: {} })),
  getRevisionsDocument: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
  createRevisionDocument: vi.fn(() => Promise.resolve({ data: {} })),
}))
vi.mock('../../api/installationsApi', () => ({ default: inst }))

import DocumentsProjet from './DocumentsProjet'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('DocumentsProjet (PACT58)', () => {
  it('affiche les documents du chantier sélectionné avec l\'indice courant', async () => {
    render(<DocumentsProjet />)
    expect(await screen.findByTestId('document-4')).toBeInTheDocument()
    expect(within(screen.getByTestId('document-4')).getByText('Indice courant : B')).toBeInTheDocument()
    expect(within(screen.getByTestId('document-4')).getByTestId('revision-30')).toBeInTheDocument()
  })

  it('affiche l\'état vide quand le chantier n\'a aucun document', async () => {
    inst.getDocumentsProjet.mockResolvedValueOnce({ data: { count: 0, results: [] } })
    render(<DocumentsProjet />)
    expect((await screen.findAllByText('Aucun document technique enregistré')).length).toBeGreaterThan(0)
  })

  it('crée un document technique', async () => {
    const user = userEvent.setup()
    render(<DocumentsProjet />)
    await screen.findByTestId('document-4')
    await user.click(screen.getAllByRole('button', { name: /Nouveau document/ })[0])
    await user.type(screen.getByLabelText('Titre'), 'Calepinage toiture B')
    await user.click(screen.getAllByRole('button', { name: 'Créer' })[0])
    await waitFor(() => expect(inst.createDocumentProjet).toHaveBeenCalledWith(
      expect.objectContaining({ installation: 9, titre: 'Calepinage toiture B' })))
  })

  it('ajoute une nouvelle révision à un document existant', async () => {
    const user = userEvent.setup()
    render(<DocumentsProjet />)
    const row = await screen.findByTestId('document-4')
    await user.click(within(row).getByRole('button', { name: /Nouvelle révision/ }))
    await user.clear(screen.getByLabelText('Indice'))
    await user.type(screen.getByLabelText('Indice'), 'C')
    await user.type(screen.getByLabelText('Date de révision'), '2026-08-05')
    await user.click(screen.getAllByRole('button', { name: 'Créer' })[0])
    await waitFor(() => expect(inst.createRevisionDocument).toHaveBeenCalledWith(
      expect.objectContaining({ document: 4, indice: 'C', date_revision: '2026-08-05' })))
  })
})
