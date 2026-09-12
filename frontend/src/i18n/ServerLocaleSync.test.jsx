import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, cleanup, waitFor, fireEvent } from '@testing-library/react'

/* NTI18N3 — ServerLocaleSync synchronise la locale avec le profil serveur
   SANS coupler I18nProvider à Redux (voir le commentaire du composant). Deux
   scénarios couverts :
   - le profil serveur charge une langue différente -> adoptée localement ;
   - la valeur qu'on vient de recevoir du serveur n'est JAMAIS renvoyée par
     PATCH (pas de rebond réseau inutile à chaque connexion). */

let mockState = { auth: { isAuthenticated: false, user: null } }
vi.mock('react-redux', () => ({
  useSelector: (sel) => sel(mockState),
}))

const patchMock = vi.fn()
vi.mock('./langueInterfaceApi', () => ({
  patchLangueInterface: (...args) => patchMock(...args),
}))

import { I18nProvider, useI18n } from './index'
import ServerLocaleSync from './ServerLocaleSync'

function Probe() {
  const { locale, setLocale } = useI18n()
  return (
    <>
      <span data-testid="locale">{locale}</span>
      <button type="button" onClick={() => setLocale('en')}>bascule EN</button>
    </>
  )
}

function Harness() {
  return (
    <I18nProvider>
      <ServerLocaleSync />
      <Probe />
    </I18nProvider>
  )
}

beforeEach(() => {
  window.localStorage.clear()
  document.documentElement.removeAttribute('dir')
  document.documentElement.removeAttribute('lang')
  mockState = { auth: { isAuthenticated: false, user: null } }
  patchMock.mockReset()
})
afterEach(() => cleanup())

describe('NTI18N3 ServerLocaleSync', () => {
  it('adopte la langue serveur une fois le profil chargé', async () => {
    const { getByTestId, rerender } = render(<Harness />)
    expect(getByTestId('locale').textContent).toBe('fr')

    mockState = { auth: { isAuthenticated: true, user: { langue_interface: 'ar' } } }
    rerender(<Harness />)

    await waitFor(() => expect(getByTestId('locale').textContent).toBe('ar'))
  })

  it("ne persiste jamais la valeur qu'il vient de recevoir du serveur", async () => {
    mockState = { auth: { isAuthenticated: true, user: { langue_interface: 'en' } } }
    const { getByTestId } = render(<Harness />)

    await waitFor(() => expect(getByTestId('locale').textContent).toBe('en'))
    expect(patchMock).not.toHaveBeenCalled()
  })

  it('sans utilisateur connecté, le comportement N93 (fr/localStorage) est inchangé', () => {
    const { getByTestId } = render(<Harness />)
    expect(getByTestId('locale').textContent).toBe('fr')
    expect(patchMock).not.toHaveBeenCalled()
  })

  it("un changement manuel de langue pendant la connexion est persisté (critère d'acceptation)", async () => {
    mockState = { auth: { isAuthenticated: true, user: { langue_interface: 'fr' } } }
    const { getByTestId, getByRole } = render(<Harness />)
    // Laisse le profil serveur (fr) s'appliquer d'abord (aucun PATCH pour ça).
    await waitFor(() => expect(getByTestId('locale').textContent).toBe('fr'))
    patchMock.mockClear()

    fireEvent.click(getByRole('button', { name: 'bascule EN' }))

    await waitFor(() => expect(patchMock).toHaveBeenCalledWith('en'))
  })

  it('sans connexion, une bascule locale ne tente jamais de PATCH serveur', () => {
    const { getByRole, getByTestId } = render(<Harness />)
    fireEvent.click(getByRole('button', { name: 'bascule EN' }))
    // fireEvent flushe les effets (RTL les enveloppe dans act()) : la locale a
    // déjà changé synchrone-équivalent au moment de cette assertion.
    expect(getByTestId('locale').textContent).toBe('en')
    expect(patchMock).not.toHaveBeenCalled()
  })
})
