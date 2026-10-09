import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

/* ASAV29 — la page publique QR affiche la décision du serveur : refus photo
   (400 `photo`) sous le champ, rejeu (200) avec la référence existante. */

vi.mock('../../api/axios', () => ({ default: { post: vi.fn() } }))

import api from '../../api/axios'
import EquipementSignalerPage from './EquipementSignalerPage'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const renderPage = () => render(
  <MemoryRouter initialEntries={['/e/tok']}>
    <Routes><Route path="/e/:token" element={<EquipementSignalerPage />} /></Routes>
  </MemoryRouter>,
)

const remplirEtEnvoyer = () => {
  fireEvent.change(screen.getByLabelText('Description du problème'), {
    target: { value: 'Panne onduleur' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Envoyer le signalement' }))
}

describe('EquipementSignalerPage ASAV29', () => {
  it('400 photo : message serveur sous Photo, formulaire conservé, pas de succès', async () => {
    api.post.mockRejectedValueOnce({
      response: { status: 400, data: { photo: ['Format non supporté'] } },
    })
    renderPage()
    remplirEtEnvoyer()
    expect(await screen.findByText('Format non supporté')).toBeInTheDocument()
    expect(screen.queryByText(/a bien été enregistré/)).toBeNull()
    expect(screen.getByLabelText('Description du problème').value).toBe('Panne onduleur')
  })

  it('rejeu (200) : référence existante annoncée', async () => {
    api.post.mockResolvedValueOnce({ status: 200, data: { reference: 'SAV-2026-007' } })
    renderPage()
    remplirEtEnvoyer()
    await waitFor(() => expect(
      screen.getByText(/Signalement déjà enregistré : SAV-2026-007/)).toBeInTheDocument())
    expect(screen.queryByText(/a bien été enregistré/)).toBeNull()
  })

  it('création (201) : succès comme avant', async () => {
    api.post.mockResolvedValueOnce({ status: 201, data: { reference: 'SAV-2026-008' } })
    renderPage()
    remplirEtEnvoyer()
    expect(await screen.findByText(/a bien été enregistré/)).toBeInTheDocument()
  })
})
