import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* PACT52 — registre légal des bénéficiaires effectifs (UBO). Le test verrouille
   l'exigence de la tâche : tant que la somme des pourcentages déclarés est sous
   le seuil, l'alerte de complétude est AFFICHÉE (jamais masquée) ; elle
   disparaît dès que le serveur déclare le registre complet. */

vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}))
vi.mock('../../ui/confirm', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  useConfirmDialog: () => ({
    confirm: () => Promise.resolve(true),
    confirmDelete: () => Promise.resolve(true),
  }),
}))

import api from '../../api/axios'
import BeneficiairesEffectifsPage from './BeneficiairesEffectifsPage'

const UBO = {
  id: 1, nom: 'Reda Kasri', cin_passeport: 'AB123456', nationalite: 'Marocaine',
  pourcentage_detention: '15.00', type_controle: 'direct',
  date_declaration: '2026-01-15',
}

const registre = (complet, total, beneficiaires = [UBO]) => ({
  data: { beneficiaires, total_pourcentage: total, complet },
})

beforeEach(() => { api.get.mockResolvedValue(registre(false, '15.00')) })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('BeneficiairesEffectifsPage (PACT52)', () => {
  it('affiche l\'alerte de complétude tant que le seuil n\'est pas atteint', async () => {
    render(<BeneficiairesEffectifsPage />)
    await waitFor(() => expect(api.get)
      .toHaveBeenCalledWith('/fiscal/beneficiaires-effectifs/registre/'))
    const alerte = await screen.findByRole('alert')
    expect(alerte).toHaveTextContent(/Registre incomplet/)
    expect(screen.getByText('Reda Kasri')).toBeInTheDocument()
  })

  it('remplace l\'alerte par « Registre complet » quand le serveur le dit', async () => {
    api.get.mockResolvedValue(registre(true, '100.00'))
    render(<BeneficiairesEffectifsPage />)
    expect(await screen.findByText('Registre complet')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('déclare un bénéficiaire sans jamais envoyer la société', async () => {
    const user = userEvent.setup()
    api.post.mockResolvedValue({ data: { id: 2 } })
    render(<BeneficiairesEffectifsPage />)
    await screen.findByText('Reda Kasri')

    await user.click(screen.getByRole('button', { name: /Déclarer un bénéficiaire/ }))
    await user.type(await screen.findByLabelText('Nom'), 'Meryem')
    await user.type(screen.getByLabelText('% de détention'), '30')
    await user.click(screen.getByRole('button', { name: 'Déclarer' }))

    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/fiscal/beneficiaires-effectifs/',
      expect.objectContaining({ nom: 'Meryem', pourcentage_detention: '30' })))
    expect(api.post.mock.calls[0][1]).not.toHaveProperty('company')
  })

  it('affiche un registre vide sans masquer l\'alerte de complétude', async () => {
    api.get.mockResolvedValue(registre(false, '0.00', []))
    render(<BeneficiairesEffectifsPage />)
    expect(await screen.findByText('Aucun bénéficiaire déclaré')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent(/Registre incomplet/)
  })
})
