import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, cleanup, waitFor } from '@testing-library/react'

/* CAD177 - les surcharges de traduction ne sont chargees qu une fois la
   session etablie (jamais au montage : un visiteur public ne doit pas
   declencher de 401 en console). */

let mockState = { auth: { isAuthenticated: false, user: null } }
vi.mock('react-redux', () => ({
  useSelector: (sel) => sel(mockState),
}))
vi.mock('./langueInterfaceApi', () => ({ patchLangueInterface: vi.fn() }))
vi.mock('./overridesApi', () => ({
  fetchTranslationOverrides: vi.fn(async () => ({ fr: { 'common.save': 'Garder' } })),
}))

import { I18nProvider, useI18n } from './index'
import ServerLocaleSync from './ServerLocaleSync'
import { fetchTranslationOverrides } from './overridesApi'

function Probe() {
  const { t } = useI18n()
  return <span data-testid="save">{t('common.save')}</span>
}

function Harness() {
  return (
    <I18nProvider chargerSurcharges={false}>
      <ServerLocaleSync />
      <Probe />
    </I18nProvider>
  )
}

beforeEach(() => {
  mockState = { auth: { isAuthenticated: false, user: null } }
  fetchTranslationOverrides.mockClear()
})
afterEach(() => cleanup())

describe('CAD177 surcharges de traduction apres authentification', () => {
  it('ne charge rien hors session', async () => {
    render(<Harness />)
    await Promise.resolve()
    expect(fetchTranslationOverrides).not.toHaveBeenCalled()
  })

  it('charge et applique les surcharges une fois connecte', async () => {
    const { getByTestId, rerender } = render(<Harness />)
    mockState = { auth: { isAuthenticated: true, user: { id: 1, portee: 'interne' } } }
    rerender(<Harness />)
    await waitFor(() => expect(getByTestId('save').textContent).toBe('Garder'))
    expect(fetchTranslationOverrides).toHaveBeenCalledTimes(1)
  })

  it('ERR-PORTAIL-TRADUCTIONS-403 : aucun appel pour un compte portail', async () => {
    const { getByTestId, rerender } = render(<Harness />)
    mockState = { auth: { isAuthenticated: true, user: { id: 2, portee: 'portail_client' } } }
    rerender(<Harness />)
    await Promise.resolve()
    expect(fetchTranslationOverrides).not.toHaveBeenCalled()
    expect(getByTestId('save').textContent).not.toBe('Garder')
  })

  it('ERR-PORTAIL-TRADUCTIONS-403 : attend la portée avant de charger', async () => {
    const { rerender } = render(<Harness />)
    mockState = { auth: { isAuthenticated: true, user: { username: 'x' } } }
    rerender(<Harness />)
    await Promise.resolve()
    expect(fetchTranslationOverrides).not.toHaveBeenCalled()
    mockState = { auth: { isAuthenticated: true, user: { username: 'x', portee: 'interne' } } }
    rerender(<Harness />)
    await waitFor(() => expect(fetchTranslationOverrides).toHaveBeenCalledTimes(1))
  })

  it('ERR-PORTAIL-TRADUCTIONS-403 : provider compteExterne ne charge rien', async () => {
    render(<I18nProvider compteExterne><Probe /></I18nProvider>)
    await Promise.resolve()
    expect(fetchTranslationOverrides).not.toHaveBeenCalled()
  })
})
