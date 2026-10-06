import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import authReducer from '../auth/store/authSlice'

/* ADOC119 — l'écran de mot de passe temporaire sert les TROIS portées et
   renvoie vers `portalHomePath(user)`. Le « serveur de test » est l'axios
   simulé : POST /auth/change-password/ puis GET /auth/me/ (drapeau tombé). */

const serveur = vi.hoisted(() => ({ post: vi.fn(), get: vi.fn() }))
vi.mock('../../api/axios', () => ({ default: serveur }))

import PortailMotDePasse from './PortailMotDePasse.jsx'
import PortailClientMotDePasse from './client/PortailClientMotDePasse.jsx'
import { cheminMotDePassePortail } from './portalScope'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderPour(portee) {
  const user = { id: 1, portee, must_change_password: true }
  const store = configureStore({
    reducer: { auth: authReducer },
    preloadedState: {
      auth: {
        user, role: 'normal', role_nom: null, permissions: [],
        modulesDesactives: [], isAuthenticated: true, loading: false,
      },
    },
  })
  serveur.post.mockResolvedValue({ data: {} })
  serveur.get.mockResolvedValue({ data: { ...user, must_change_password: false } })
  const home = `/portail/${portee.replace('portail_', '')}`
  render(
    <Provider store={store}>
      <MemoryRouter initialEntries={[cheminMotDePassePortail(portee)]}>
        <Routes>
          <Route path={cheminMotDePassePortail(portee)} element={<PortailMotDePasse />} />
          <Route path={home} element={<div>ACCUEIL {home}</div>} />
        </Routes>
      </MemoryRouter>
    </Provider>,
  )
  return home
}

function soumettre() {
  fireEvent.change(screen.getByLabelText('Mot de passe temporaire'), { target: { value: 'tmp-123' } })
  fireEvent.change(screen.getByLabelText('Nouveau mot de passe'), { target: { value: 'Solide-2026-xyz' } })
  fireEvent.change(screen.getByLabelText('Confirmez le nouveau mot de passe'), { target: { value: 'Solide-2026-xyz' } })
  fireEvent.click(screen.getByRole('button', { name: /Valider mon mot de passe/ }))
}

describe('PortailMotDePasse — ADOC119', () => {
  it.each(['portail_fournisseur', 'portail_partenaire', 'portail_client'])(
    '%s : change le mot de passe puis va à l’accueil de sa portée',
    async (portee) => {
      const home = renderPour(portee)
      soumettre()
      await waitFor(() => expect(serveur.post).toHaveBeenCalledWith(
        '/auth/change-password/',
        { current_password: 'tmp-123', new_password: 'Solide-2026-xyz' },
      ))
      expect(await screen.findByText(`ACCUEIL ${home}`)).toBeTruthy()
    },
  )

  it('l’ancien écran client est le MÊME composant (ré-export)', () => {
    expect(PortailClientMotDePasse).toBe(PortailMotDePasse)
  })
})
