// QG3 — « + Nouveau client » quick-create depuis le générateur de devis
// (chemin sans lead). Vérifie la création (crmApi.createClient, company
// forcée côté serveur) et le rappel onCreated qui permet à l'appelant de
// sélectionner automatiquement le nouveau client.

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import ClientQuickCreateModal from './ClientQuickCreateModal'

vi.mock('../../api/crmApi', () => ({
  default: { createClient: vi.fn(), searchClients: vi.fn() },
}))
import crmApi from '../../api/crmApi'

beforeEach(() => {
  vi.clearAllMocks()
  // jsdom : le Combobox de l'autocomplete QC1 utilise scrollIntoView.
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {}
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

describe('MB5 — Nom/Prénom : une colonne sous 640px, deux au-delà', () => {
  it('n\'utilise jamais une grille grid-cols-2 figée (déborde sur téléphone)', () => {
    render(<ClientQuickCreateModal open onClose={() => {}} onCreated={() => {}} />)
    // Le champ Nom vit dans une grille interne ("grid gap-1.5") elle-même
    // enfant de la rangée Nom/Prénom — on cible cette rangée (le parent).
    const wrap = document.getElementById('cqc-nom').closest('.grid').parentElement
    expect(wrap.className).toMatch(/\bgrid-cols-1\b/)
    expect(wrap.className).toMatch(/\bsm:grid-cols-2\b/)
    expect(wrap.className).not.toMatch(/"grid grid-cols-2\b/)
  })
})

describe('QC1 — autocomplete entreprise dans la modale QG3', () => {
  it('cherche, propose et remplit téléphone/email + avertit d\'un doublon client', async () => {
    crmApi.searchClients.mockResolvedValue({
      data: { results: [{
        source: 'client', id: 12, nom: 'Zellige SARL', ice: '001234567000089',
        telephone: '+212522000000', email: 'contact@zellige.ma',
      }] },
    })
    render(<ClientQuickCreateModal open onClose={() => {}} onCreated={() => {}} />)
    // Ouvre le combobox et tape une requête.
    fireEvent.click(screen.getByRole('combobox'))
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'zellige' } })
    // L'option apparaît → on la choisit. FLAKE CI (2026-07-16, ~50% sous
    // charge) : le listbox cmdk peut RE-RENDRE entre findByText et click
    // (résolution du debounce de recherche), le clic part alors sur un nœud
    // DÉTACHÉ et ne sélectionne rien → « expected '' to be 'Zellige SARL' ».
    // Remède : re-cliquer une option FRAÎCHE à chaque retry de waitFor tant
    // que le champ n'est pas rempli — l'assertion finale reste identique.
    await screen.findByText('Zellige SARL')
    await waitFor(() => {
      if (document.getElementById('cqc-nom').value !== 'Zellige SARL') {
        fireEvent.click(screen.getByText('Zellige SARL'))
      }
      // Les champs vides sont remplis depuis le match.
      expect(document.getElementById('cqc-nom').value).toBe('Zellige SARL')
    }, { timeout: 5000 })
    expect(document.getElementById('cqc-tel').value).toBe('+212522000000')
    expect(document.getElementById('cqc-email').value).toBe('contact@zellige.ma')
    // Avertissement de doublon (source client).
    expect(screen.getByTestId('cqc-dup-warning')).toHaveTextContent(/existe déjà/)
  })
})
