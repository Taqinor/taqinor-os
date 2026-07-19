import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ENG42 — extension ADDITIVE du dashboard ENG23 : onglet Pacing (enveloppe /
   burn / projection / état) + vue Réconciliation Meta-vs-ERP (écart + statut).
   Les onglets chargent leur donnée PARESSEUSEMENT (au clic) ; les chiffres sont
   ceux de l'API ENG20/ENG31 mockée et sont cliquables vers le détail. */

const mocks = vi.hoisted(() => ({
  dashboard: vi.fn(),
  leads: vi.fn(),
  alerts: vi.fn(),
  pacing: vi.fn(),
  reconciliation: vi.fn(),
  reportsExport: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    metrics: { dashboard: mocks.dashboard, leads: mocks.leads, pacing: mocks.pacing },
    // PUB48 — cloche console (AlertCenter) : `history` distinct du bandeau `list`.
    alerts: { list: mocks.alerts, history: () => Promise.resolve({ data: [] }) },
    reconciliation: { list: mocks.reconciliation },
    // PUB57 — tuile score d'audit auto-chargée (AuditScoreTile) partage la
    // même clé `reports` que l'export CSV (PUB47).
    reports: { export: mocks.reportsExport, audit: () => Promise.resolve({ data: { score_tile: null } }) },
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
  mocks.pacing.mockResolvedValue({ data: {
    enveloppe_mad: 30000, depense_mad: 12000, projection_mad: 31500,
    jours_restants: 12, etat: 'sur_rythme', etat_display: 'Sur le rythme',
    lignes: [
      { id: 1, label: 'Résidentiel', montant_mad: 8000 },
      { id: 2, label: 'Pompage', montant_mad: 4000 },
    ] } })
  mocks.reconciliation.mockResolvedValue({ data: [
    { id: 3, campagne: 'Résidentiel Casa', meta_mad: 12000, erp_mad: 11800,
      ecart_mad: 200, ecart_pct: 0.017, statut: 'ecart', statut_display: 'Écart mineur',
      lignes: [{ id: 1, label: '10 juil', meta_mad: 600, erp_mad: 590 }] },
  ] })
  mocks.reportsExport.mockResolvedValue({ data: new Blob(['csv']) })
  // jsdom ne fournit pas createObjectURL/revokeObjectURL (PUB47 — export CSV
  // serveur en blob téléchargeable).
  globalThis.URL.createObjectURL = vi.fn(() => 'blob:fake')
  globalThis.URL.revokeObjectURL = vi.fn()
})

describe('DashboardScreen — ENG42 Pacing', () => {
  it('la vue d\'ensemble reste par défaut (héro visible, pacing non appelé)', async () => {
    renderScreen()
    expect(await screen.findByTestId('ae-hero')).toBeInTheDocument()
    expect(mocks.pacing).not.toHaveBeenCalled()
  })

  it('l\'onglet Pacing charge enveloppe / burn / projection / état de l\'API', async () => {
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-tab-pacing'))
    await waitFor(() => expect(mocks.pacing).toHaveBeenCalled())
    expect(await screen.findByTestId('ae-pacing-enveloppe-val')).toHaveTextContent('30 000 MAD')
    expect(screen.getByTestId('ae-pacing-burn-val')).toHaveTextContent('12 000 MAD')
    expect(screen.getByTestId('ae-pacing-projection-val')).toHaveTextContent('31 500 MAD')
    expect(screen.getByTestId('ae-pacing-etat-val')).toHaveTextContent('Sur le rythme')
  })

  it('le burn est cliquable vers le détail des dépenses', async () => {
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-tab-pacing'))
    fireEvent.click(await screen.findByTestId('ae-pacing-burn'))
    expect(await screen.findByTestId('ae-pacing-detail')).toBeInTheDocument()
    expect(screen.getAllByTestId('ae-pacing-detail-row').length).toBe(2)
    expect(screen.getByText('Résidentiel')).toBeInTheDocument()
  })
})

describe('DashboardScreen — ENG42 Réconciliation', () => {
  it('l\'onglet Réconciliation affiche l\'écart Meta-vs-ERP et le statut', async () => {
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-tab-reconciliation'))
    await waitFor(() => expect(mocks.reconciliation).toHaveBeenCalled())
    const row = await screen.findByTestId('ae-recon-row')
    expect(row).toHaveTextContent('Résidentiel Casa')
    expect(screen.getByTestId('ae-recon-ecart-3')).toHaveTextContent('200 MAD')
    expect(row).toHaveTextContent('Écart mineur')
  })

  it('cliquer une ligne ouvre son détail poste par poste', async () => {
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-tab-reconciliation'))
    fireEvent.click(await screen.findByTestId('ae-recon-open-3'))
    expect(await screen.findByTestId('ae-recon-detail')).toHaveTextContent('Résidentiel Casa')
    expect(screen.getByTestId('ae-recon-detail-row')).toHaveTextContent('10 juil')
  })

  // PUB47 — export CSV serveur (ReportExportView, jusqu'ici sans consommateur
  // sur cette table) + impression navigateur (window.print(), print.css VX80).
  it('exporte la réconciliation en CSV serveur (table=reconciliation)', async () => {
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-tab-reconciliation'))
    fireEvent.click(await screen.findByTestId('ae-recon-export'))
    await waitFor(() => expect(mocks.reportsExport).toHaveBeenCalledWith(
      { table: 'reconciliation' }))
  })

  it('un export CSV en échec affiche une erreur', async () => {
    mocks.reportsExport.mockRejectedValue(new Error('500'))
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-tab-reconciliation'))
    fireEvent.click(await screen.findByTestId('ae-recon-export'))
    expect(await screen.findByTestId('ae-recon-export-err')).toBeInTheDocument()
  })

  it('le bouton Imprimer appelle window.print()', async () => {
    const printSpy = vi.spyOn(window, 'print').mockImplementation(() => {})
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-dashboard-print'))
    expect(printSpy).toHaveBeenCalled()
    printSpy.mockRestore()
  })

  // PUB56 — repli mobile (< 768px) : chaque cellule porte data-label pour que
  // le repli carte (index.css, pattern déjà établi de l'ERP) affiche le nom
  // du champ au lieu d'une pile de valeurs nues.
  it('les cellules de la table de réconciliation portent data-label', async () => {
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-tab-reconciliation'))
    const row = await screen.findByTestId('ae-recon-row')
    expect(row.querySelector('td[data-label="Campagne"]')).not.toBeNull()
    expect(row.querySelector('td[data-label="Écart"]')).not.toBeNull()
  })
})
