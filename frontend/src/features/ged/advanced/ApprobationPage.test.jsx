import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import gedApi from '../../../api/gedApi'
import { toast } from '../../../ui'
import ApprobationPage from './ApprobationPage.jsx'

/* PACT135 — onglet « Envoi en masse » : un modèle fusionné avec N
   destinataires (CSV OU sélection de clients CRM) → un document + une
   demande de signature PAR destinataire, suivis sous un `LotEnvoi` (XGED27).
   Couvre UNIQUEMENT le nouvel onglet (le smoke test des autres onglets vit
   déjà dans advanced.test.jsx). Mocks alignés sur `LotEnvoiSerializer`
   (id, libelle, modele_nom, total, nb_envoyes, nb_vus, nb_signes,
   nb_refuses, nb_erreurs) — jamais un champ inventé ni un total recalculé
   côté client. */

vi.mock('../../../api/gedApi', () => ({
  default: {
    getDemandesApprobation: vi.fn(() => Promise.resolve({ data: [] })),
    getDemandesSignature: vi.fn(() => Promise.resolve({ data: [] })),
    getModelesDocument: vi.fn(() => Promise.resolve({ data: [
      { id: 2, nom: 'Attestation maintenance', categorie: 'contrat', actif: true },
    ] })),
    getDocumentsList: vi.fn(() => Promise.resolve({ data: [] })),
    getRolesSignataire: vi.fn(() => Promise.resolve({ data: [] })),
    getLotsEnvoi: vi.fn(),
    envoyerLotSignature: vi.fn(() => Promise.resolve({
      data: { id: 9, libelle: 'Relance 2026', total: 2, nb_envoyes: 2, nb_vus: 0, nb_signes: 0, nb_refuses: 0, nb_erreurs: 0 },
    })),
  },
}))

vi.mock('../../../api/crmApi', () => ({
  default: {
    getClients: vi.fn(() => Promise.resolve({ data: [{ id: 5, nom: 'Client Alpha' }] })),
  },
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
  gedApi.getLotsEnvoi.mockResolvedValue({
    data: [{
      id: 3, modele: 2, modele_nom: 'Attestation maintenance', libelle: 'Renouvellement 2025',
      total: 5, nb_envoyes: 5, nb_vus: 2, nb_signes: 1, nb_refuses: 0, nb_erreurs: 0,
      created_at: '2026-07-01T09:00:00Z',
    }],
  })
})

describe('PACT135 ApprobationPage — Envoi en masse', () => {
  it('liste les lots avec leurs compteurs', async () => {
    renderPage()
    await userEvent.click(await screen.findByRole('tab', { name: 'Envoi en masse' }))
    expect((await screen.findAllByText('Renouvellement 2025')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Attestation maintenance').length).toBeGreaterThan(0)
  })

  it('envoie un lot par sélection de clients CRM et affiche les compteurs du lot créé', async () => {
    renderPage()
    await userEvent.click(await screen.findByRole('tab', { name: 'Envoi en masse' }))
    await screen.findAllByText('Renouvellement 2025')

    await userEvent.click(screen.getAllByRole('button', { name: /Nouvel envoi/i })[0])
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('combobox', { name: 'Choisir un modèle' }))
    await userEvent.click(within(await screen.findByRole('listbox')).getByText('Attestation maintenance'))

    // Bascule vers la sélection de clients CRM (par défaut : CSV).
    await userEvent.click(within(dialog).getByRole('combobox', { name: 'Choisir la source des destinataires' }))
    await userEvent.click(within(await screen.findByRole('listbox')).getByText('Sélection de clients CRM'))

    await userEvent.click(within(dialog).getByLabelText('Clients'))
    const listbox = await screen.findByRole('listbox')
    await userEvent.click(within(listbox).getByText('Client Alpha'))
    await userEvent.click(within(dialog).getByRole('button', { name: /Lancer l.envoi/i }))

    await waitFor(() => {
      expect(gedApi.envoyerLotSignature).toHaveBeenCalledWith({
        modele: '2', libelle: '', csvFile: undefined, clientIds: ['5'],
      })
      expect(toast.success).toHaveBeenCalledWith('Lot créé : 2/2 demande(s) envoyée(s).')
    })
  })

  it('refuse l’envoi CSV sans fichier choisi', async () => {
    renderPage()
    await userEvent.click(await screen.findByRole('tab', { name: 'Envoi en masse' }))
    await screen.findAllByText('Renouvellement 2025')

    await userEvent.click(screen.getAllByRole('button', { name: /Nouvel envoi/i })[0])
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('combobox', { name: 'Choisir un modèle' }))
    await userEvent.click(within(await screen.findByRole('listbox')).getByText('Attestation maintenance'))
    await userEvent.click(within(dialog).getByRole('button', { name: /Lancer l.envoi/i }))

    expect(gedApi.envoyerLotSignature).not.toHaveBeenCalled()
    expect(toast.error).toHaveBeenCalledWith('Choisissez un fichier CSV.')
  })
})
