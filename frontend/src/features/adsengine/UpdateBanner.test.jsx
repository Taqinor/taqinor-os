import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

/* FIXPUB4 — bandeau « version périmée » : réutilise `useRegisterSW`
   (virtual:pwa-register/react — le même hook que features/pwa/PwaPrompts.jsx,
   aliasé vers un stub côté Vitest, cf. frontend/vitest.config.js). */

const mocks = vi.hoisted(() => ({ needRefresh: false, updateServiceWorker: vi.fn() }))

vi.mock('virtual:pwa-register/react', () => ({
  useRegisterSW: () => ({
    needRefresh: [mocks.needRefresh, vi.fn()],
    offlineReady: [false, vi.fn()],
    updateServiceWorker: mocks.updateServiceWorker,
  }),
}))

import UpdateBanner from './UpdateBanner'

describe('UpdateBanner (FIXPUB4)', () => {
  it('rien affiché tant qu’aucune nouvelle version n’est prête', () => {
    mocks.needRefresh = false
    render(<UpdateBanner />)
    expect(screen.queryByTestId('ae-update-banner')).toBeNull()
  })

  it('nouvelle version prête -> bandeau + bouton Recharger appelle updateServiceWorker(true)', () => {
    mocks.needRefresh = true
    render(<UpdateBanner />)
    const banner = screen.getByTestId('ae-update-banner')
    expect(banner).toHaveTextContent('Nouvelle version disponible')
    fireEvent.click(screen.getByTestId('ae-update-banner-reload'))
    expect(mocks.updateServiceWorker).toHaveBeenCalledWith(true)
  })
})
