import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import gedApi from '../../api/gedApi'
import PublicPartagePage from './PublicPartagePage.jsx'

/* ASEC77 — partage GED public : 403 ⇒ formulaire, POST {password} ⇒ PDF,
 * gel serveur ⇒ « Trop d'essais » affiché tel quel. */

vi.mock('../../api/gedApi', () => ({
  default: { ouvrirPartagePublic: vi.fn() },
}))

const MDP_REQUIS = { response: { status: 403, data: { detail: 'Mot de passe requis ou incorrect pour ce document.' } } }
const GEL = { response: { status: 403, data: { detail: "Trop d'essais, réessayez plus tard." } } }

function renderAt(path) {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/ged/partage/:token" element={<PublicPartagePage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  )
}

const assign = vi.fn()
const origLocation = window.location

beforeEach(() => {
  vi.clearAllMocks()
  URL.createObjectURL = vi.fn(() => 'blob:pdf-1')
  URL.revokeObjectURL = vi.fn()
  Object.defineProperty(window, 'location', { configurable: true, value: { ...origLocation, assign } })
})
afterEach(() => {
  Object.defineProperty(window, 'location', { configurable: true, value: origLocation })
})

describe('ASEC77 PublicPartagePage', () => {
  it('demande le mot de passe puis ouvre le PDF par POST', async () => {
    const pdf = new Blob(['%PDF-'], { type: 'application/pdf' })
    gedApi.ouvrirPartagePublic
      .mockRejectedValueOnce(MDP_REQUIS)
      .mockResolvedValueOnce({ data: pdf })
    renderAt('/ged/partage/tok-1')

    const champ = await screen.findByLabelText(/Mot de passe/i)
    expect(gedApi.ouvrirPartagePublic).toHaveBeenCalledWith('tok-1')
    await userEvent.type(champ, 's3cret')
    await userEvent.click(screen.getByRole('button', { name: /Ouvrir le document/i }))

    await waitFor(() =>
      expect(gedApi.ouvrirPartagePublic).toHaveBeenLastCalledWith('tok-1', 's3cret'))
    await waitFor(() => expect(assign).toHaveBeenCalledWith('blob:pdf-1'))
    expect(URL.createObjectURL).toHaveBeenCalledWith(pdf)
  })

  it('affiche le message du serveur après le gel', async () => {
    gedApi.ouvrirPartagePublic
      .mockRejectedValueOnce(MDP_REQUIS)
      .mockRejectedValueOnce(GEL)
    renderAt('/ged/partage/tok-2')
    await userEvent.type(await screen.findByLabelText(/Mot de passe/i), 'faux')
    await userEvent.click(screen.getByRole('button', { name: /Ouvrir le document/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent("Trop d'essais, réessayez plus tard.")
    expect(assign).not.toHaveBeenCalled()
  })

  it('ouvre directement un partage sans mot de passe', async () => {
    gedApi.ouvrirPartagePublic.mockResolvedValueOnce({ data: new Blob(['x']) })
    renderAt('/ged/partage/tok-3')
    await waitFor(() => expect(assign).toHaveBeenCalledWith('blob:pdf-1'))
    expect(screen.queryByLabelText(/Mot de passe/i)).not.toBeInTheDocument()
  })

  it('affiche un message honnête sur un lien expiré', async () => {
    gedApi.ouvrirPartagePublic.mockRejectedValueOnce({
      response: { status: 410, data: { detail: "Ce lien de partage a expiré ou n'est plus disponible." } },
    })
    renderAt('/ged/partage/vieux')
    expect(await screen.findByRole('alert')).toHaveTextContent(/expiré/i)
  })
})
