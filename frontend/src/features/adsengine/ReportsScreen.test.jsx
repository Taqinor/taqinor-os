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
  leaderboard: vi.fn(),
  scatter: vi.fn(),
  audit: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    reports: {
      variants: mocks.variants, funnel: mocks.funnel, cohorts: mocks.cohorts,
      leaderboard: mocks.leaderboard, scatter: mocks.scatter, audit: mocks.audit,
    },
    // PUB48 — cloche de la console (AlertCenter), historique vide par défaut :
    // hors périmètre de ce fichier, mais montée sur l'écran (import réel).
    alerts: { history: () => Promise.resolve({ data: [] }) },
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
  mocks.leaderboard.mockResolvedValue({ data: {
    dimension: 'hook', untagged_count: 1,
    classement: [
      { tag: 'PAIN', spend: '900.00', results: 10, cost_per_result: '90.00',
        hook_rate_weighted: 0.32, ad_count: 3 },
      { tag: 'PEUR', spend: '300.00', results: 4, cost_per_result: '75.00',
        hook_rate_weighted: 0.18, ad_count: 1 },
    ],
  } })
  mocks.scatter.mockResolvedValue({ data: {
    median_hook_rate: 0.2, median_spend: 300,
    points: [
      { ad_meta_id: 'a1', name: 'Reel pépite', spend: '50.00', hook_rate: 0.5,
        quadrant: 'pepites_cachees', quadrant_label_fr: 'Pépites cachées' },
      { ad_meta_id: 'a2', name: 'Statique gouffre', spend: '950.00', hook_rate: 0.05,
        quadrant: 'gouffres', quadrant_label_fr: 'Gouffres à budget' },
    ],
  } })
  mocks.audit.mockResolvedValue({ data: {
    genere_le: '2026-07-17',
    sections: {
      naming: { statut: 'attention', resume: '1/3 ad(s) taguée(s).',
        items: ['2/3 ad(s) sans tag.'], lien: '/publicite/creatifs' },
      fragmentation_budgetaire: { statut: 'ok', resume: 'Aucune fragmentation.',
        items: [], lien: '/publicite/campagnes' },
      fatigue: { statut: 'attention', resume: '1 campagne en fatigue forte.',
        items: ['Camp X : fréquence 3.0'], lien: '/publicite/regles' },
      tracking: { statut: 'ok', resume: 'Pixel, CAPI et UTM en ordre.',
        items: [], lien: '/publicite/connexion' },
      fenetres_donnees: { statut: 'info', resume: 'Rappel.',
        items: ['Meta efface les leads après 90 jours.'], lien: '/publicite/reporting' },
    },
  } })
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

  // PUB47 — impression navigateur (feuille globale print.css, VX80), zéro
  // dépendance nouvelle : toujours visible, quel que soit l'onglet.
  it('le bouton Imprimer appelle window.print()', async () => {
    const printSpy = vi.spyOn(window, 'print').mockImplementation(() => {})
    renderScreen()
    const btn = await screen.findByTestId('ae-reports-print')
    btn.click()
    expect(printSpy).toHaveBeenCalled()
    printSpy.mockRestore()
  })
})

describe('ReportsScreen — onglet Créatifs (ADSDEEP47)', () => {
  it('affiche le classement spend-weighted et masque l\'export CSV', async () => {
    renderScreen()
    screen.getByTestId('ae-reports-tab-creatifs').click()
    const rows = await screen.findAllByTestId('ae-creatifs-leaderboard-row')
    expect(rows.length).toBe(2)
    // Trié par dépense décroissante (comme le backend le renvoie).
    expect(rows[0]).toHaveTextContent('PAIN')
    expect(rows[0]).toHaveTextContent('900 MAD')
    expect(rows[0]).toHaveTextContent('32')
    expect(screen.getByTestId('ae-creatifs-untagged')).toHaveTextContent('1 ad(s)')
    // Le bouton d'export CSV (onglet Vue d'ensemble) disparaît sur cet onglet.
    expect(screen.queryByTestId('ae-reports-export')).toBeNull()
  })

  it('affiche le nuage hook rate × dépense avec les quadrants FR', async () => {
    renderScreen()
    screen.getByTestId('ae-reports-tab-creatifs').click()
    const rows = await screen.findAllByTestId('ae-creatifs-scatter-row')
    expect(rows.length).toBe(2)
    expect(rows[0]).toHaveTextContent('Reel pépite')
    expect(rows[0]).toHaveTextContent('Pépites cachées')
    expect(rows[1]).toHaveTextContent('Gouffres à budget')
  })

  it('change de dimension et relance l\'appel API', async () => {
    renderScreen()
    screen.getByTestId('ae-reports-tab-creatifs').click()
    await screen.findAllByTestId('ae-creatifs-leaderboard-row')
    mocks.leaderboard.mockClear()
    screen.getByTestId('ae-creatifs-dimension-angle').click()
    await waitFor(() => expect(mocks.leaderboard).toHaveBeenCalledWith(
      expect.objectContaining({ dimension: 'angle' })))
  })

  it('change de période et relance l\'appel API', async () => {
    renderScreen()
    screen.getByTestId('ae-reports-tab-creatifs').click()
    await screen.findAllByTestId('ae-creatifs-leaderboard-row')
    mocks.leaderboard.mockClear()
    screen.getByTestId('ae-creatifs-period-7').click()
    await waitFor(() => expect(mocks.leaderboard).toHaveBeenCalledWith(
      expect.objectContaining({ dimension: 'hook', debut: expect.any(String), fin: expect.any(String) })))
  })

  it('affiche des états vides quand rien n\'est tagué/calculable', async () => {
    mocks.leaderboard.mockResolvedValue({ data: { dimension: 'hook', untagged_count: 0, classement: [] } })
    mocks.scatter.mockResolvedValue({ data: { points: [], median_hook_rate: null, median_spend: null } })
    renderScreen()
    screen.getByTestId('ae-reports-tab-creatifs').click()
    expect(await screen.findByTestId('ae-creatifs-leaderboard-empty')).toBeInTheDocument()
    expect(screen.getByTestId('ae-creatifs-scatter-empty')).toBeInTheDocument()
  })
})

describe('ReportsScreen — onglet Audit de compte (ADSDEEP63)', () => {
  it('n\'appelle jamais l\'audit tant que le bouton n\'est pas cliqué', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.variants).toHaveBeenCalled())
    screen.getByTestId('ae-reports-tab-audit').click()
    expect(await screen.findByTestId('ae-audit-empty')).toBeInTheDocument()
    expect(mocks.audit).not.toHaveBeenCalled()
  })

  it('lance l\'audit au clic et affiche les 5 sections', async () => {
    renderScreen()
    screen.getByTestId('ae-reports-tab-audit').click()
    const bouton = await screen.findByTestId('ae-audit-lancer')
    bouton.click()
    await waitFor(() => expect(mocks.audit).toHaveBeenCalled())
    expect(await screen.findByTestId('ae-audit-section-naming')).toBeInTheDocument()
    expect(screen.getByTestId('ae-audit-section-fragmentation_budgetaire')).toBeInTheDocument()
    expect(screen.getByTestId('ae-audit-section-fatigue')).toBeInTheDocument()
    expect(screen.getByTestId('ae-audit-section-tracking')).toBeInTheDocument()
    expect(screen.getByTestId('ae-audit-section-fenetres_donnees')).toBeInTheDocument()
  })

  it('affiche le statut et un lien actionnable par section', async () => {
    renderScreen()
    screen.getByTestId('ae-reports-tab-audit').click()
    const bouton = await screen.findByTestId('ae-audit-lancer')
    bouton.click()
    await screen.findByTestId('ae-audit-section-naming')
    expect(screen.getByTestId('ae-audit-statut-naming')).toHaveTextContent('Attention')
    expect(screen.getByTestId('ae-audit-statut-tracking')).toHaveTextContent('OK')
    const lien = screen.getByTestId('ae-audit-lien-naming')
    expect(lien).toHaveAttribute('href', '/publicite/creatifs')
  })

  it('affiche une erreur si l\'audit échoue', async () => {
    mocks.audit.mockRejectedValue(new Error('boom'))
    renderScreen()
    screen.getByTestId('ae-reports-tab-audit').click()
    const bouton = await screen.findByTestId('ae-audit-lancer')
    bouton.click()
    expect(await screen.findByTestId('ae-audit-error')).toBeInTheDocument()
  })
})
