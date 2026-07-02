// QG3 — « + Nouveau client » quick-create depuis le générateur de devis
// (chemin sans lead). Vérifie la création (crmApi.createClient, company
// forcée côté serveur) et le rappel onCreated qui permet à l'appelant de
// sélectionner automatiquement le nouveau client.

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import ClientQuickCreateModal from './ClientQuickCreateModal'

vi.mock('../../api/crmApi', () => ({
  default: { createClient: vi.fn() },
}))
import crmApi from '../../api/crmApi'

beforeEach(() => {
  vi.clearAllMocks()
})

describe('ClientQuickCreateModal (QG3)', () => {
  it('crée le client et rappelle onCreated avec la donnée serveur', async () => {
    crmApi.createClient.mockResolvedValue({
      data: { id: 77, nom: 'Alaoui', prenom: 'Karim' },
    })
    const onCreated = vi.fn()
    render(<ClientQuickCreateModal open onClose={() => {}} onCreated={onCreated} />)

    fireEvent.change(document.getElementById('cqc-nom'), { target: { value: 'Alaoui' } })
    fireEvent.change(screen.getByLabelText(/Prénom/), { target: { value: 'Karim' } })
    fireEvent.click(screen.getByRole('button', { name: /Créer et sélectionner/ }))

    await waitFor(() => expect(crmApi.createClient).toHaveBeenCalledWith(
      expect.objectContaining({ nom: 'Alaoui', prenom: 'Karim' })))
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(
      expect.objectContaining({ id: 77, nom: 'Alaoui' })))
  })

  it('refuse la soumission sans nom (validation locale, pas d\'appel réseau)', async () => {
    const onCreated = vi.fn()
    render(<ClientQuickCreateModal open onClose={() => {}} onCreated={onCreated} />)
    fireEvent.click(screen.getByRole('button', { name: /Créer et sélectionner/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Le nom est requis')
    expect(crmApi.createClient).not.toHaveBeenCalled()
    expect(onCreated).not.toHaveBeenCalled()
  })

  it('affiche le message serveur en cas d\'échec', async () => {
    crmApi.createClient.mockRejectedValue({
      response: { data: { detail: 'Un client avec cet email existe déjà.' } },
    })
    render(<ClientQuickCreateModal open onClose={() => {}} onCreated={() => {}} />)
    fireEvent.change(document.getElementById('cqc-nom'), { target: { value: 'Bennani' } })
    fireEvent.click(screen.getByRole('button', { name: /Créer et sélectionner/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Un client avec cet email existe déjà.')
  })
})
