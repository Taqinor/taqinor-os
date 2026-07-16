import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ENG45 — Drill-downs reporting (ENG33) : table variantes, entonnoir campagne,
   cohortes/lag, export CSV. Tous les chiffres = ceux de l'API mockée ; le CSV
   est construit depuis ces mêmes chiffres. */

const mocks = vi.hoisted(() => ({
  variants: vi.fn(),
  funnel: vi.fn(),
  cohorts: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    reports: { variants: mocks.variants, funnel: mocks.funnel, cohorts: mocks.cohorts },
  },
}))

import ReportsScreen from './ReportsScreen'

const renderScreen = () => render(<MemoryRouter><ReportsScreen /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.variants.mockResolvedValue({ data: [
    { id: 1, nom: 'Reel toiture v1', impressions: 12000, reponses_whatsapp: 34, cout_mad: 1500, cout_par_reponse: 44 },
    { id: 2, nom: 'Statique prix', impressions: 8000, reponses_whatsapp: 12, cout_mad: 900, cout_par_reponse: 75 },
  ] })
  mocks.funnel.mockResolvedValue({ data: { etapes: [
    { key: 'impressions', label: 'Impressions', valeur: 20000 },
    { key: 'clics', label: 'Clics', valeur: 900 },
    { key: 'reponses', label: 'Réponses WhatsApp', valeur: 46 },
    { key: 'signatures', label: 'Signatures', valeur: 6 },
  ] } })
  mocks.cohorts.mockResolvedValue({ data: [
    { id: 1, cohorte: 'Juillet 2026', taille: 46, lag_jours_median: 9, signatures: 6 },
  ] })
})

describe('ReportsScreen (ENG45)', () => {
  it('affiche la table des variantes avec les chiffres de l\'API', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.variants).toHaveBeenCalled())
    const rows = await screen.findAllByTestId('ae-reports-variant-row')
    expect(rows.length).toBe(2)
    expect(rows[0]).toHaveTextContent('Reel toiture v1')
    expect(rows[0]).toHaveTextContent('12 000')
    expect(rows[0]).toHaveTextContent('44 MAD')
  })

  it('affiche l\'entonnoir de campagne', async () => {
    renderScreen()
    const steps = await screen.findAllByTestId('ae-reports-funnel-step')
    expect(steps.length).toBe(4)
    expect(steps[0]).toHaveTextContent('Impressions')
    expect(steps[3]).toHaveTextContent('Signatures')
    expect(steps[3]).toHaveTextContent('6')
  })

  it('affiche les cohortes avec le lag médian', async () => {
    renderScreen()
    const row = await screen.findByTestId('ae-reports-cohort-row')
    expect(row).toHaveTextContent('Juillet 2026')
    expect(row).toHaveTextContent('9')
  })

  it('l\'export CSV contient les chiffres des variantes', async () => {
    renderScreen()
    const link = await screen.findByTestId('ae-reports-export')
    expect(link).toHaveAttribute('download', 'variantes-taqinor.csv')
    const href = link.getAttribute('href')
    expect(href).toMatch(/^data:text\/csv/)
    const csv = decodeURIComponent(href.replace(/^data:text\/csv;charset=utf-8,/, ''))
    expect(csv).toContain('Variante,Impressions')
    expect(csv).toContain('Reel toiture v1,12000,34,1500,44')
    expect(csv).toContain('Statique prix,8000,12,900,75')
  })

  it('affiche des états vides quand tout est vide', async () => {
    mocks.variants.mockResolvedValue({ data: [] })
    mocks.funnel.mockResolvedValue({ data: { etapes: [] } })
    mocks.cohorts.mockResolvedValue({ data: [] })
    renderScreen()
    expect(await screen.findByTestId('ae-reports-variants-empty')).toBeInTheDocument()
    expect(screen.getByTestId('ae-reports-funnel-empty')).toBeInTheDocument()
    expect(screen.getByTestId('ae-reports-cohorts-empty')).toBeInTheDocument()
    // Pas de lien d'export sans variante.
    expect(screen.queryByTestId('ae-reports-export')).toBeNull()
  })
})
