import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

/* XSAV19 — page publique « Signaler un problème » via QR équipement, sans
   login. api (axios) mocké. */

vi.mock('../../api/axios', () => ({
  default: { post: vi.fn() },
}))

import api from '../../api/axios'
import EquipementSignalerPage from './EquipementSignalerPage'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const renderPage = (token = 'eq-tok-1') => render(
  <MemoryRouter initialEntries={[`/e/${token}`]}>
    <Routes>
      <Route path="/e/:token" element={<EquipementSignalerPage />} />
    </Routes>
  </MemoryRouter>,
)

describe('EquipementSignalerPage (public, XSAV19)', () => {
  it('envoie le signalement avec la description et affiche la référence créée', async () => {
    api.post.mockResolvedValueOnce({ data: { reference: 'SAV-2026-042' } })
    renderPage('eq-tok-1')

    fireEvent.change(screen.getByLabelText('Description du problème'), {
      target: { value: "L'onduleur ne s'allume plus." },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Envoyer le signalement' }))

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1))
    const [url, form] = api.post.mock.calls[0]
    expect(url).toBe('/public/sav/equipement/eq-tok-1/signaler/')
    expect(form.get('description')).toBe("L'onduleur ne s'allume plus.")

    expect(await screen.findByText(/SAV-2026-042/)).toBeInTheDocument()
  })

  it('affiche un message honnête si le lien est invalide (404)', async () => {
    api.post.mockRejectedValueOnce({
      response: { status: 404, data: { detail: 'Introuvable.' } },
    })
    renderPage('bad-token')
    fireEvent.change(screen.getByLabelText('Description du problème'), {
      target: { value: 'Panne' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Envoyer le signalement' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Introuvable.')
  })

  it('désactive le bouton tant que la description est vide', () => {
    renderPage()
    expect(screen.getByRole('button', { name: 'Envoyer le signalement' })).toBeDisabled()
  })
})
