import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* NTOBS16 — badge SLA auto-calculé (cockpit direction). Dégrade en silence
   sans snapshot, jamais un pourcentage inventé. */

vi.mock('../../api/parametresApi', () => ({
  default: { getSlaSnapshots: vi.fn(), getReliabilitySettings: vi.fn() },
}))

import parametresApi from '../../api/parametresApi'
import SlaBadgeCard from './SlaBadgeCard'

// auth = palier admin par défaut (lit les réglages) ; `lecteur` = rôle sans `fiabilite_voir`.
function renderCard(auth = { role: 'admin', role_nom: 'Administrateur', permissions: [] }) {
  const store = configureStore({ reducer: { auth: () => auth } })
  return render(
    <Provider store={store}><MemoryRouter><SlaBadgeCard /></MemoryRouter></Provider>)
}

describe('SlaBadgeCard (NTOBS16)', () => {
  it('affiche le pourcentage du dernier snapshot', async () => {
    parametresApi.getSlaSnapshots.mockResolvedValueOnce({
      data: [{ id: 1, periode: '2026-06-01', uptime_pct: '99.9500', latence_p95_ms: 120 }],
    })
    renderCard()
    await waitFor(() =>
      expect(screen.getByTestId('sla-badge-card')).toBeInTheDocument())
    expect(screen.getByText('99.95%')).toBeInTheDocument()
    expect(screen.getByText(/Voir le rapport SLA complet/)).toBeInTheDocument()
  })

  it("ne rend rien sans snapshot (pas de pourcentage invente)", async () => {
    parametresApi.getSlaSnapshots.mockResolvedValueOnce({ data: [] })
    const { container } = renderCard()
    await waitFor(() => expect(parametresApi.getSlaSnapshots).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })

  it("degrade en silence sur une erreur reseau", async () => {
    parametresApi.getSlaSnapshots.mockRejectedValueOnce(new Error('network'))
    const { container } = renderCard()
    await waitFor(() => expect(parametresApi.getSlaSnapshots).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })

  it("NTOBS21 — masque si la societe a coupe le badge", async () => {
    parametresApi.getSlaSnapshots.mockResolvedValueOnce({
      data: [{ id: 1, periode: '2026-06-01', uptime_pct: '99.9500', latence_p95_ms: 120 }],
    })
    parametresApi.getReliabilitySettings.mockResolvedValueOnce({
      data: { afficher_badge_sla_dashboard: false },
    })
    const { container } = renderCard()
    await waitFor(() => expect(parametresApi.getReliabilitySettings).toHaveBeenCalled())
    await waitFor(() => expect(container).toBeEmptyDOMElement())
  })

  it("ERR-ACC — un Lecteur sans fiabilite_voir ne lit jamais les réglages (aucun 403)", async () => {
    parametresApi.getReliabilitySettings.mockClear()
    parametresApi.getSlaSnapshots.mockResolvedValueOnce({
      data: [{ id: 1, periode: '2026-06-01', uptime_pct: '99.9500', latence_p95_ms: 120 }],
    })
    renderCard({ role: 'normal', role_nom: 'Lecteur', permissions: ['crm_voir'] })
    await waitFor(() =>
      expect(screen.getByTestId('sla-badge-card')).toBeInTheDocument())
    expect(parametresApi.getReliabilitySettings).not.toHaveBeenCalled()
  })
})
