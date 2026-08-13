import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* PACT147 — Onglet « Politiques d'approbation » : `parametres.ApprovalPolicy`
   (FG25) avait un CRUD serveur et aucun écran de configuration. À ne pas
   confondre avec la boîte de réception des approbations en attente. */

const { get, post, patch, del } = vi.hoisted(() => ({
  get: vi.fn(), post: vi.fn(), patch: vi.fn(), del: vi.fn(),
}))
vi.mock('../../api/axios', () => ({
  default: { get, post, patch, delete: del },
}))

const { getAudit } = vi.hoisted(() => ({
  getAudit: vi.fn(() => Promise.resolve({
    data: [{
      id: 1, section: 'approbations', field: 'policy:discount',
      field_label: 'Politique créée', old_value: null,
      new_value: 'Remise sur devis (seuil 10.00, Administrateur uniquement)',
      user_nom: 'Reda', timestamp: '2026-08-13T09:00:00Z',
    }],
  })),
}))
vi.mock('../../api/parametresApi', () => ({
  default: { getAudit, getAuditSections: vi.fn(() => Promise.resolve({ data: { sections: [] } })) },
}))

import ApprobationsPolitiquesSection from './ApprobationsPolitiquesSection'

const POLITIQUES = [{
  id: 11, action_type: 'discount', action_type_label: 'Remise sur devis',
  seuil: '10.00', approver_tier: 'admin',
  approver_tier_label: 'Administrateur uniquement',
  enabled: true, note: 'Au-delà de 10 % de remise.',
}]

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderAvecRole(role) {
  const store = configureStore({ reducer: { auth: (state = { role }) => state } })
  return render(<Provider store={store}><ApprobationsPolitiquesSection /></Provider>)
}

describe('ApprobationsPolitiquesSection (PACT147)', () => {
  it('liste les politiques par type d\'action, seuil et palier', async () => {
    get.mockResolvedValue({ data: POLITIQUES })
    renderAvecRole('admin')

    expect(get).toHaveBeenCalledWith('/parametres/approbations/')
    const ligne = await screen.findByTestId('politique-discount')
    expect(within(ligne).getByText('Remise sur devis')).toBeInTheDocument()
    expect(within(ligne).getByText('Administrateur uniquement')).toBeInTheDocument()
    expect(within(ligne).getByText('À partir de 10.00')).toBeInTheDocument()
    expect(within(ligne).getByText('Activée')).toBeInTheDocument()
  })

  it('crée et active une politique sans jamais envoyer company', async () => {
    const user = userEvent.setup()
    get.mockResolvedValue({ data: [] })
    post.mockResolvedValue({ data: {} })
    renderAvecRole('admin')
    await screen.findByText("Aucune politique d'approbation")

    await user.click(screen.getByRole('combobox', { name: "Type d'action" }))
    await user.click(await screen.findByRole('option', { name: 'Remise sur devis' }))
    await user.type(screen.getByPlaceholderText('Seuil (vide = toujours)'), '5000')
    await user.click(screen.getByRole('button', { name: /Activer la politique/ }))

    await waitFor(() => expect(post).toHaveBeenCalledWith('/parametres/approbations/', {
      action_type: 'discount', seuil: '5000', approver_tier: 'admin',
      enabled: true, note: '',
    }))
    expect(Object.keys(post.mock.calls[0][1])).not.toContain('company')
  })

  it('désactive une politique existante (opt-in strict réversible)', async () => {
    const user = userEvent.setup()
    get.mockResolvedValue({ data: POLITIQUES })
    patch.mockResolvedValue({ data: {} })
    renderAvecRole('responsable')
    await screen.findByTestId('politique-discount')

    await user.click(screen.getByRole('button', { name: 'Activée' }))

    await waitFor(() => expect(patch).toHaveBeenCalledWith(
      '/parametres/approbations/11/', { enabled: false }))
  })

  it("affiche le journal d'audit de la section approbations", async () => {
    get.mockResolvedValue({ data: POLITIQUES })
    renderAvecRole('admin')

    expect(await screen.findByText('Politique créée')).toBeInTheDocument()
    expect(getAudit).toHaveBeenCalledWith(
      expect.objectContaining({ section: 'approbations' }))
  })

  it("un rôle simple lit les politiques mais n'a aucune commande d'écriture", async () => {
    get.mockResolvedValue({ data: POLITIQUES })
    renderAvecRole('normal')

    await screen.findByTestId('politique-discount')
    expect(screen.queryByRole('button', { name: /Activer la politique/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Supprimer la politique/ })).toBeNull()
  })

  it('affiche une erreur de chargement sans planter', async () => {
    get.mockRejectedValue(new Error('boom'))
    renderAvecRole('admin')
    expect(await screen.findByText(/Impossible de charger les politiques/))
      .toBeInTheDocument()
  })
})
