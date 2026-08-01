// ODY34 — Changer de société renvoie à MA grille.
// Le bug corrigé : `window.location.reload()` rechargeait l'URL COURANTE, alors
// que la société B a un autre jeu de ModuleToggle — un utilisateur
// multi-société qui basculait depuis un écran RH atterrissait sur « App non
// activée » (ODY8) au lieu de ses apps.
//
// Seule la NAVIGATION est doublée (`rechargerVers`) : jsdom interdit de
// remplacer `window.location`. La règle d'atterrissage, elle, est la VRAIE
// (`landingApresBasculeSociete`, via `importActual`).
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

const { postMock, rechargerMock } = vi.hoisted(() => ({
  postMock: vi.fn(() => Promise.resolve({ data: {} })),
  rechargerMock: vi.fn(),
}))

vi.mock('../../api/axios', () => ({ default: { post: postMock, get: vi.fn() } }))

vi.mock('../../router/moduleRoutes', () => ({
  moduleConfigs: [{ key: 'rh', nav: { label: 'RH', items: [{ to: '/rh' }] } }],
}))

vi.mock('../../lib/apps/landing', async () => {
  const actual = await vi.importActual('../../lib/apps/landing')
  return { ...actual, rechargerVers: rechargerMock }
})

import CompanySwitcher from './CompanySwitcher'
import { LANDING_KEY } from '../../pages/preferences/prefs'

const USER = {
  active_company_id: 1,
  societes_operables: [{ id: 1, nom: 'Société A' }, { id: 2, nom: 'Société B' }],
}

function renderSwitcher(user = USER) {
  const store = configureStore({ reducer: { auth: (s = { user }) => s } })
  return render(<Provider store={store}><CompanySwitcher /></Provider>)
}

const choisirSociete = (value) => fireEvent.change(
  screen.getByRole('combobox', { name: /Changer de société active/ }),
  { target: { value } },
)

describe('ODY34 — CompanySwitcher', () => {
  beforeEach(() => {
    postMock.mockClear()
    rechargerMock.mockClear()
    window.localStorage.removeItem(LANDING_KEY)
  })

  it('un compte mono-société ne rend rien (comportement inchangé)', () => {
    const { container } = renderSwitcher({
      active_company_id: 1, societes_operables: [{ id: 1, nom: 'A' }],
    })
    expect(container.firstChild).toBeNull()
  })

  it('bascule → POST puis atterrissage sur le Menu d’accueil (jamais l’URL courante)', async () => {
    renderSwitcher()
    choisirSociete('2')
    await waitFor(() => expect(postMock).toHaveBeenCalledWith(
      '/auth/switch-company/', { company_id: 2 },
    ))
    await waitFor(() => expect(rechargerMock).toHaveBeenCalledWith('/apps'))
  })

  it('préférence d’atterrissage VX46 renseignée : elle est respectée', async () => {
    window.localStorage.setItem(LANDING_KEY, 'rh')
    renderSwitcher()
    choisirSociete('2')
    await waitFor(() => expect(rechargerMock).toHaveBeenCalledWith('/rh'))
  })

  it('choisir la société DÉJÀ active ne déclenche rien', () => {
    renderSwitcher()
    choisirSociete('1')
    expect(postMock).not.toHaveBeenCalled()
    expect(rechargerMock).not.toHaveBeenCalled()
  })

  it('un POST en échec ne navigue nulle part (l’utilisateur reste où il est)', async () => {
    postMock.mockImplementationOnce(() => Promise.reject(new Error('403')))
    renderSwitcher()
    choisirSociete('2')
    await waitFor(() => expect(postMock).toHaveBeenCalled())
    expect(rechargerMock).not.toHaveBeenCalled()
  })
})
