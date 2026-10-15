import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { renderLeadWorkspace } from '../../../test/leadWorkspaceHarness'
import { LEAD_A, mockMatchMedia } from '../../../test/leadWorkspaceMocks'
import { cleanup, act } from '@testing-library/react'
import crmApi from '../../../api/crmApi'

/* LW25 — squelette d'ouverture, EN FORME de la vraie grille (rail identité /
   centre / rail contexte), piloté par useDelayedLoading + FadeSwap. Mêmes
   neutralisations que LeadWorkspaceCreate.test.jsx. */
vi.mock('../../../pages/crm/leads/LeadDevisPanel', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/SigneDialog', () => ({ default: () => null }))

vi.mock('../../../api/crmApi', async () => (await import('../../../test/leadWorkspaceMocks')).crmApiLeadWorkspace())


beforeEach(() => { mockMatchMedia(false); try { localStorage.clear() } catch { /* noop */ } })
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  crmApi.getLead.mockImplementation(() => Promise.resolve({ data: {} }))
})

function renderEdit(lead = LEAD_A) {
  return renderLeadWorkspace({ lead })
}

// FadeSwap garde TOUJOURS les deux couches (squelette/contenu) montées — seul
// `aria-hidden` bascule (crossfade CSS). La visibilité RÉELLE se lit donc là,
// jamais par simple présence DOM de `.lw-skeleton-pane` (toujours présente).
function skeletonVisible() {
  const layer = document.querySelector('.lw-skeleton-swap > div')
  return layer?.getAttribute('aria-hidden') === 'false'
}

describe('LW25 — squelette d’ouverture en forme de grille', () => {
  it('un chargement qui dépasse 500ms affiche le squelette (rail/centre/droite), jamais un spinner nu', async () => {
    vi.useFakeTimers()
    try {
      let resolveGet
      crmApi.getLead.mockImplementation(() => new Promise((resolve) => { resolveGet = resolve }))
      renderEdit()
      await act(async () => { await vi.advanceTimersByTimeAsync(500) })
      expect(skeletonVisible()).toBe(true)
      expect(document.querySelectorAll('.lw-skeleton-pane').length).toBeGreaterThanOrEqual(3)
      // Le GET systématique (LW25) résout et REMPLACE le squelette par la
      // grille réelle — c'est aussi le mécanisme de re-fetch d'arrière-plan
      // requis par LW24 après une navigation vers un voisin pré-chargé.
      await act(async () => { resolveGet({ data: LEAD_A }) })
      expect(skeletonVisible()).toBe(false)
    } finally {
      vi.useRealTimers()
    }
  })

  it('une ouverture rapide (<300ms) ne montre jamais le squelette', async () => {
    vi.useFakeTimers()
    try {
      crmApi.getLead.mockResolvedValue({ data: LEAD_A })
      renderEdit()
      await act(async () => { await vi.advanceTimersByTimeAsync(200) })
      expect(skeletonVisible()).toBe(false)
    } finally {
      vi.useRealTimers()
    }
  })
})
