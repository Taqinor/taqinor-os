import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import migrationApi from '../../api/migrationApi'
import MigrationWizard from './MigrationWizard'

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useParams: () => ({ id: '7' }) }
})

vi.mock('../../api/migrationApi', () => ({
  default: {
    getProjet: vi.fn(),
    listLots: vi.fn(),
    createLot: vi.fn(),
    analyserLot: vi.fn(),
    chargerLot: vi.fn(),
    reconcilierLot: vi.fn(),
    derogerLot: vi.fn(),
    terminerProjet: vi.fn(),
    rapportUrl: (id) => `/api/django/migration/projets-migration/${id}/rapport/`,
  },
}))

vi.mock('../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn() } }
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const PROJET = {
  id: 7, nom: 'Reprise Odoo', source: 'odoo', statut: 'chargement',
  lots_total: 1, lots_reconcilies: 0,
}

function lot(extra = {}) {
  return {
    id: 11, projet: 7, entite: 'clients', statut: 'en_attente',
    source_lignes: 0, crees: 0, maj: 0, erreurs: 0,
    derogation_reconcile: false, dernier_rapport: null, ...extra,
  }
}

function withProviders(ui) {
  return render(
    <MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

function mockLoad(lots) {
  migrationApi.getProjet.mockResolvedValue({ data: PROJET })
  migrationApi.listLots.mockResolvedValue({ data: lots })
}

describe('MigrationWizard (NTMIG17)', () => {
  it('étape 1 — crée un lot par entité cochée, avec un ordre stable', async () => {
    mockLoad([])
    migrationApi.createLot.mockResolvedValue({ data: {} })
    const user = userEvent.setup()
    withProviders(<MigrationWizard />)

    await screen.findByText(/Étape 1/)
    await user.click(screen.getByLabelText('Clients'))
    await user.click(screen.getByRole('button', { name: /Créer les lots/i }))

    await waitFor(() => {
      expect(migrationApi.createLot).toHaveBeenCalledWith(
        { projet: '7', entite: 'clients', ordre: 0 })
    })
  })

  it('étape 2 — l\'analyse dit explicitement que rien n\'a été écrit', async () => {
    mockLoad([lot()])
    migrationApi.analyserLot.mockResolvedValue({
      data: { total_lignes: 250, non_mappees: ['zip'], ecrasements_total: 0 },
    })
    const user = userEvent.setup()
    withProviders(<MigrationWizard />)

    const input = await screen.findByLabelText(/Fichier source du lot clients/)
    await user.upload(
      input, new File(['nom\nA'], 'clients.csv', { type: 'text/csv' }))
    await user.click(screen.getByRole('button', { name: /^Analyser$/ }))

    expect(await screen.findByText(/rien n'a été écrit/i)).toBeTruthy()
    expect(screen.getByText(/250/)).toBeTruthy()
    expect(
      screen.getByText(/Aucune valeur déjà saisie ne serait remplacée/i),
    ).toBeTruthy()
  })

  it('étape 2 — annonce que les valeurs déjà saisies seront CONSERVÉES', async () => {
    mockLoad([lot()])
    migrationApi.analyserLot.mockResolvedValue({
      data: { total_lignes: 10, non_mappees: [], ecrasements_total: 4 },
    })
    const user = userEvent.setup()
    withProviders(<MigrationWizard />)

    const input = await screen.findByLabelText(/Fichier source du lot clients/)
    await user.upload(
      input, new File(['nom\nA'], 'clients.csv', { type: 'text/csv' }))
    await user.click(screen.getByRole('button', { name: /^Analyser$/ }))

    expect(await screen.findByText(/seront CONSERVÉES/)).toBeTruthy()
  })

  it('étape 4 — affiche le rapport de réconciliation et ses écarts', async () => {
    mockLoad([lot({
      statut: 'charge', source_lignes: 100, crees: 97, erreurs: 3,
      dernier_rapport: {
        id: 1, nb_source: 100, nb_cible_crees: 97, nb_cible_existants: 0,
        nb_erreurs: 3, conforme: false,
        ecarts: [{ type: 'erreurs', detail: '3 ligne(s) en erreur.' }],
      },
    })])
    withProviders(<MigrationWizard />)

    expect(await screen.findByText(/Étape 4/)).toBeTruthy()
    expect(screen.getByText('Écarts détectés')).toBeTruthy()
    expect(screen.getByText('3 ligne(s) en erreur.')).toBeTruthy()
  })

  it('une dérogation sans motif n\'est jamais envoyée', async () => {
    mockLoad([lot({
      statut: 'charge',
      dernier_rapport: { id: 1, conforme: false, ecarts: [], nb_source: 1 },
    })])
    const user = userEvent.setup()
    withProviders(<MigrationWizard />)

    await user.click(
      await screen.findByRole('button', { name: /Déroger \(avec motif\)/i }))
    await user.click(
      screen.getByRole('button', { name: /Enregistrer la dérogation/i }))

    expect(migrationApi.derogerLot).not.toHaveBeenCalled()
  })

  it('une dérogation motivée part avec son motif', async () => {
    mockLoad([lot({
      statut: 'charge',
      dernier_rapport: { id: 1, conforme: false, ecarts: [], nb_source: 1 },
    })])
    migrationApi.derogerLot.mockResolvedValue({ data: {} })
    const user = userEvent.setup()
    withProviders(<MigrationWizard />)

    await user.click(
      await screen.findByRole('button', { name: /Déroger \(avec motif\)/i }))
    await user.type(
      screen.getByLabelText(/Motif de la dérogation/), 'Doublons acceptés')
    await user.click(
      screen.getByRole('button', { name: /Enregistrer la dérogation/i }))

    await waitFor(() => {
      expect(migrationApi.derogerLot).toHaveBeenCalledWith(11, 'Doublons acceptés')
    })
  })

  it('une clôture refusée affiche les écarts bloquants par lot', async () => {
    mockLoad([lot({ statut: 'charge' })])
    migrationApi.terminerProjet.mockRejectedValue({
      response: {
        data: {
          detail: 'Des lots ne sont pas réconciliés ni dérogés : clôture refusée.',
          ecarts: [{
            lot: 11, entite: 'clients',
            ecarts: [{ type: 'sans_rapport', detail: 'Aucun rapport.' }],
          }],
        },
      },
    })
    const user = userEvent.setup()
    withProviders(<MigrationWizard />)

    await user.click(
      await screen.findByRole('button', { name: /Terminer le projet/i }))

    expect(await screen.findByText(/écarts bloquants/i)).toBeTruthy()
    expect(screen.getByText(/Aucun rapport\./)).toBeTruthy()
  })

  it('propose le PV de migration en PDF', async () => {
    mockLoad([lot()])
    withProviders(<MigrationWizard />)
    const lien = await screen.findByRole('link', { name: /PV de migration/i })
    expect(lien.getAttribute('href')).toBe(
      '/api/django/migration/projets-migration/7/rapport/')
  })
})
