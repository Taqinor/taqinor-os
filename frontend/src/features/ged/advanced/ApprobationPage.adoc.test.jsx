import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import gedApi from '../../../api/gedApi'
import { toast } from '../../../ui'
import ApprobationPage from './ApprobationPage.jsx'

/* ADOC63 / ADOC76 — écran Approbation, versant signature.
   Réponses de forme RÉELLE (DemandeSignatureDocumentSerializer : id, token,
   lien_signature absolu, signataires[]) — jamais un champ inventé. */

const LIEN = 'https://erp.exemple.ma/ged/signature/tok-adoc63/'

vi.mock('../../../api/gedApi', () => ({
  default: {
    getDemandesApprobation: vi.fn(() => Promise.resolve({ data: [] })),
    getDemandesSignature: vi.fn(() => Promise.resolve({ data: [] })),
    getModelesDocument: vi.fn(() => Promise.resolve({ data: [] })),
    getDocumentsList: vi.fn(() => Promise.resolve({ data: [{ id: 4, nom: 'Bail.pdf' }] })),
    getRolesSignataire: vi.fn(() => Promise.resolve({ data: [] })),
    getLotsEnvoi: vi.fn(() => Promise.resolve({ data: [] })),
    getAnalytique: vi.fn(() => Promise.resolve({ data: null })),
    getTableauBordSignatures: vi.fn(() => Promise.resolve({ data: null })),
    createDemandeSignature: vi.fn(),
    creerDemandeMultiSignataires: vi.fn(),
    getChampsSignature: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))

vi.mock('../../../api/crmApi', () => ({
  default: { getClients: vi.fn(() => Promise.resolve({ data: [] })) },
}))

vi.mock('../../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn(), message: vi.fn() } }
})

function renderPage() {
  return render(
    <MemoryRouter><ThemeProvider><ApprobationPage /></ThemeProvider></MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('ADOC63 ApprobationPage — lien de signature', () => {
  it('la demande créée affiche Copier le lien de signature', async () => {
    gedApi.createDemandeSignature.mockResolvedValue({
      data: {
        id: 12, document: 4, document_nom: 'Bail.pdf', statut: 'en_attente',
        signataire_nom: 'Client A', signataire_email: 'a@x.ma',
        token: 'tok-adoc63', lien_signature: LIEN, signataires: [],
      },
    })
    renderPage()
    await userEvent.click(await screen.findByRole('tab', { name: 'Signatures' }))
    await userEvent.click((await screen.findAllByRole('button', { name: /Nouvelle demande/i }))[0])
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('combobox', { name: /Choisir un document/i }))
    await userEvent.click(within(await screen.findByRole('listbox')).getByText('Bail.pdf'))
    const champs = within(dialog).getAllByRole('textbox')
    await userEvent.type(champs[0], 'Client A')
    await userEvent.type(champs[1], 'a@x.ma')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Créer la demande' }))

    const lien = await screen.findByLabelText('Lien de signature')
    expect(lien).toHaveValue(LIEN)
    await userEvent.click(screen.getByRole('button', { name: 'Copier le lien de signature' }))
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith('Lien de signature copié.'))
  })
})

describe('ADOC76 ApprobationPage — circuit multi-signataires', () => {
  it('le rôle est un choix fermé', async () => {
    gedApi.creerDemandeMultiSignataires.mockResolvedValue({
      data: { id: 30, document: 4, statut: 'en_attente', lien_signature: null, signataires: [] },
    })
    renderPage()
    await userEvent.click(await screen.findByRole('tab', { name: 'Signatures' }))
    await userEvent.click((await screen.findAllByRole('button', { name: /Circuit multi-signataires/i }))[0])
    const dialog = await screen.findByRole('dialog')

    // Plus aucune saisie libre du rôle.
    expect(within(dialog).queryByPlaceholderText('Rôle')).not.toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('combobox', { name: 'Rôle du destinataire 1' }))
    const options = within(await screen.findByRole('listbox')).getAllByRole('option')
    expect(options.map((o) => o.textContent)).toEqual(['Signataire', 'Copie', 'Approbateur'])
    await userEvent.click(options[2])

    await userEvent.click(within(dialog).getByRole('combobox', { name: /Choisir un document/i }))
    await userEvent.click(within(await screen.findByRole('listbox')).getByText('Bail.pdf'))
    await userEvent.type(within(dialog).getByPlaceholderText('Nom'), 'Sofia')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Créer le circuit' }))

    await waitFor(() => expect(gedApi.creerDemandeMultiSignataires).toHaveBeenCalledWith(
      expect.objectContaining({
        destinataires: [expect.objectContaining({ nom: 'Sofia', role: 'approbateur', ordre: 1 })],
      })))
  })
})
