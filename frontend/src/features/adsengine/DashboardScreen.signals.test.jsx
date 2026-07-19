import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* SIG4 — extension ADDITIVE du dashboard ENG23 : onglet Signaux avec les DEUX
   scores de santé (créatif/opérations, bandes FR), le quadrant de garde-fous
   DURS (ne fait QUE freiner) et le drill-down par signal/cohorte (filigrane
   de maturation). Chargé PARESSEUSEMENT (au clic), chiffres = API mockée. */

const mocks = vi.hoisted(() => ({
  dashboard: vi.fn(),
  leads: vi.fn(),
  alerts: vi.fn(),
  signalsGet: vi.fn(),
  signalsCohort: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    metrics: { dashboard: mocks.dashboard, leads: mocks.leads },
    // PUB48 — cloche console (AlertCenter) : `history` distinct du bandeau `list`.
    alerts: { list: mocks.alerts, history: () => Promise.resolve({ data: [] }) },
    signals: { get: mocks.signalsGet, cohort: mocks.signalsCohort },
  },
}))

import DashboardScreen from './DashboardScreen'

const renderScreen = () => render(<MemoryRouter><DashboardScreen /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.dashboard.mockResolvedValue({ data: {
    cost_per_signature: 1850, spend: 4200, cpl: 95, frequency: 1.8 } })
  mocks.alerts.mockResolvedValue({ data: { alerts: [] } })
  mocks.leads.mockResolvedValue({ data: [] })
  mocks.signalsGet.mockResolvedValue({ data: {
    creatif: { score: 0.72, bande: 'vert', bande_display: 'Vert' },
    operations: { score: 0.42, bande: 'orange', bande_display: 'Orange' },
    guardrails: [
      { key: 'frequence', label: 'Fréquence', valeur: 2.4, seuil: 3, freine: false, statut_display: 'OK' },
      { key: 'cpl', label: 'CPL', valeur: 140, seuil: 120, freine: true, statut_display: 'Freine' },
    ],
  } })
  mocks.signalsCohort.mockResolvedValue({ data: [
    { id: 1, fenetre: 'Proxy 7j', valeur: 0.8, maturite_display: 'Précoce' },
    { id: 2, fenetre: 'CPL 14-28j', valeur: 0.6, maturite_display: 'En maturation' },
  ] })
})

describe('DashboardScreen — SIG4 Signaux', () => {
  it('la vue d\'ensemble reste par défaut (signaux non appelés)', async () => {
    renderScreen()
    expect(await screen.findByTestId('ae-hero')).toBeInTheDocument()
    expect(mocks.signalsGet).not.toHaveBeenCalled()
  })

  it('l\'onglet Signaux affiche les deux scores de santé avec leur bande FR', async () => {
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-tab-signaux'))
    await waitFor(() => expect(mocks.signalsGet).toHaveBeenCalled())
    expect(await screen.findByTestId('ae-signal-creatif-score')).toHaveTextContent('0,7')
    expect(screen.getByTestId('ae-signal-creatif-bande')).toHaveTextContent('Vert')
    expect(screen.getByTestId('ae-signal-operations-score')).toHaveTextContent('0,4')
    expect(screen.getByTestId('ae-signal-operations-bande')).toHaveTextContent('Orange')
  })

  it('le quadrant de garde-fous durs affiche chaque garde-fou avec son statut', async () => {
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-tab-signaux'))
    const quadrant = await screen.findByTestId('ae-guardrail-quadrant')
    expect(quadrant).toBeInTheDocument()
    expect(screen.getByTestId('ae-guardrail-statut-frequence')).toHaveTextContent('OK')
    expect(screen.getByTestId('ae-guardrail-statut-cpl')).toHaveTextContent('Freine')
  })

  it('cliquer un score de santé ouvre le drill-down par cohorte', async () => {
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-tab-signaux'))
    const creatifCard = await screen.findByTestId('ae-signal-creatif')
    fireEvent.click(creatifCard)
    await waitFor(() => expect(mocks.signalsCohort).toHaveBeenCalledWith({ signal: 'creatif' }))
    expect(await screen.findByTestId('ae-signal-drill-table')).toBeInTheDocument()
    expect(screen.getAllByTestId('ae-signal-drill-row').length).toBe(2)
    expect(screen.getByText('Proxy 7j')).toBeInTheDocument()
  })

  it('fermer le drill-down le retire', async () => {
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-tab-signaux'))
    fireEvent.click(await screen.findByTestId('ae-signal-operations'))
    await screen.findByTestId('ae-signal-drill')
    fireEvent.click(screen.getByTestId('ae-signal-drill-close'))
    await waitFor(() => expect(screen.queryByTestId('ae-signal-drill')).toBeNull())
  })
})
