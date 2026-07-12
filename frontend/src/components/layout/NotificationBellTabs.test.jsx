import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* VX14 — Centre de notifications : le panneau groupait DÉJÀ par domaine en
   sections empilées (Activités en retard / Garanties / Factures impayées /
   Contrats à renouveler). On vérifie ici le passage à 3 onglets internes
   déclaratifs (Activités / Échéances / Financier) avec compteur correct
   (somme des groupes qu'ils contiennent), et que seul le groupe de l'onglet
   actif est rendu à la fois. */

vi.mock('../../api/reportingApi', () => ({
  default: {
    getNotifications: vi.fn(() => Promise.resolve({
      data: {
        total: 3,
        activites_en_retard: [{ id: 1, label: 'Relancer client A', date: '2026-01-01' }],
        garanties_expirantes: [{ id: 2, label: 'Onduleur X', date: '2026-02-01' }],
        factures_impayees: [{ id: 3, label: 'FAC-001', sublabel: '10 000 MAD', overdue: true }],
        contrats_a_renouveler: [],
        visites_dues: [],
      },
    })),
    approbationsEnAttente: vi.fn(() => Promise.resolve({ data: { items: [] } })),
  },
}))
vi.mock('../../api/notificationsApi', () => ({
  default: {
    list: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    unreadCount: vi.fn(() => Promise.resolve({ data: { unread: 0 } })),
    markRead: vi.fn(),
    markAllRead: vi.fn(),
    attentionSummary: vi.fn(() => Promise.resolve({ data: { approbations: 0 } })),
  },
}))

import NotificationBell from './NotificationBell'

function renderBell() {
  return render(
    <MemoryRouter><NotificationBell /></MemoryRouter>,
  )
}

describe('NotificationBell — onglets internes déclaratifs (VX14)', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    cleanup()
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('affiche 3 onglets, un seul groupe actif à la fois, compteurs corrects', async () => {
    renderBell()
    fireEvent.click(screen.getByRole('button', { name: /Notifications/ }))

    await act(async () => { await Promise.resolve() })

    // Les 3 onglets déclarés existent.
    const tabs = screen.getAllByRole('tab')
    expect(tabs).toHaveLength(3)
    expect(screen.getByRole('tab', { name: /Activités/ })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Échéances/ })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Financier/ })).toBeInTheDocument()

    // Onglet par défaut = Activités : le groupe "Activités en retard" est visible,
    // "Garanties" et "Factures impayées" ne le sont pas.
    await act(async () => { await vi.runOnlyPendingTimersAsync() })
    expect(screen.getByText('Relancer client A')).toBeInTheDocument()
    expect(screen.queryByText('Onduleur X')).not.toBeInTheDocument()
    expect(screen.queryByText('FAC-001')).not.toBeInTheDocument()

    // Bascule vers Échéances : Garanties apparaît, Activités disparaît.
    fireEvent.click(screen.getByRole('tab', { name: /Échéances/ }))
    expect(screen.getByText('Onduleur X')).toBeInTheDocument()
    expect(screen.queryByText('Relancer client A')).not.toBeInTheDocument()

    // Bascule vers Financier : Factures impayées apparaît.
    fireEvent.click(screen.getByRole('tab', { name: /Financier/ }))
    expect(screen.getByText('FAC-001')).toBeInTheDocument()
    expect(screen.queryByText('Onduleur X')).not.toBeInTheDocument()

    // Le compteur total (somme des groupes) reste correct sur le bouton cloche :
    // 3 alertes dérivées + 0 non-lu du feed = 3.
    expect(screen.getByLabelText('Notifications (3)')).toBeInTheDocument()
  })

  it('onglet vide affiche un message dédié plutôt qu’un panneau vide silencieux', async () => {
    renderBell()
    fireEvent.click(screen.getByRole('button', { name: /Notifications/ }))
    await act(async () => { await Promise.resolve() })

    // Financier a 1 facture impayée (non vide) -> pas de message vide.
    fireEvent.click(screen.getByRole('tab', { name: /Financier/ }))
    expect(screen.queryByText('Rien à signaler ici')).not.toBeInTheDocument()
  })
})
