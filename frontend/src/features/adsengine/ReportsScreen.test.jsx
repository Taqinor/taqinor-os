import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ENG45 — Drill-downs reporting (ENG33) : table variantes, entonnoir campagne,
   cohortes/lag, export CSV. Tous les chiffres = ceux de l'API mockée. PUB12 :
   l'export CSV est SERVI PAR LE BACKEND (reports.export), plus fabriqué ici. */

const mocks = vi.hoisted(() => ({
  variants: vi.fn(),
  funnel: vi.fn(),
  cohorts: vi.fn(),
  leaderboard: vi.fn(),
  scatter: vi.fn(),
  audit: vi.fn(),
  exportCsv: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    reports: {
      variants: mocks.variants, funnel: mocks.funnel, cohorts: mocks.cohorts,
      leaderboard: mocks.leaderboard, scatter: mocks.scatter, audit: mocks.audit,
      export: mocks.exportCsv,
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

  it('l\'export CSV appelle le ReportExportView serveur (blob), pas un CSV client', async () => {
    mocks.exportCsv.mockResolvedValue({ data: new Blob(['x'], { type: 'text/csv' }) })
    // Stubs jsdom pour le téléchargement du blob.
    const createUrl = vi.fn(() => 'blob:mock')
    const revokeUrl = vi.fn()
    URL.createObjectURL = createUrl
    URL.revokeObjectURL = revokeUrl
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => {})

    renderScreen()
    const btn = await screen.findByTestId('ae-reports-export')
    fireEvent.click(btn)

    await waitFor(() => expect(mocks.exportCsv).toHaveBeenCalledWith({ table: 'variantes' }))
    await waitFor(() => expect(createUrl).toHaveBeenCalled())
    expect(clickSpy).toHaveBeenCalled()
    clickSpy.mockRestore()
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

  // PUB52 — entrée vers le comparateur côte-à-côte.
  it('propose un lien vers le Comparateur', async () => {
    renderScreen()
    const link = await screen.findByTestId('ae-reports-compare-link')
    expect(link).toHaveAttribute('href', '/publicite/comparateur')
  })

  // PUB56 — repli mobile (< 768px) : `.data-table` n'affiche le nom du champ
  // sur les cartes que via `data-label` (index.css, pattern déjà établi de
  // l'ERP) — sans lui, une carte mobile n'est qu'une pile de valeurs nues.
  it('les cellules du tableau variantes portent data-label (repli carte mobile)', async () => {
    renderScreen()
    // La fixture renvoie plusieurs variantes → plusieurs lignes : les vérifier
    // toutes (findAllByTestId, jamais le singulier qui lèverait « multiple »).
    const rows = await screen.findAllByTestId('ae-reports-variant-row')
    expect(rows.length).toBeGreaterThan(0)
    rows.forEach(row => {
      const cells = row.querySelectorAll('td')
      expect(cells.length).toBeGreaterThan(0)
      cells.forEach(td => expect(td).toHaveAttribute('data-label'))
    })
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

  it('PUB8 — affiche la courbe de rétention par ad vidéo (jamais un 0 fabriqué sans donnée)', async () => {
    mocks.scatter.mockResolvedValue({ data: {
      median_hook_rate: 0.2, median_spend: 300,
      points: [
        { ad_meta_id: 'a1', name: 'Reel pépite', spend: '50.00', hook_rate: 0.5,
          quadrant: 'pepites_cachees', quadrant_label_fr: 'Pépites cachées',
          hold_rate: 0.3, ratio_15s_to_6s: 0.5, watch_time_avg_s: 12.5,
          retention: { p25: 0.8, p50: 0.5, p75: 0.25, p100: 0.1 } },
        // Ad sans bundle vidéo (pas de retention) — jamais un "0 %" fabriqué.
        { ad_meta_id: 'a2', name: 'Statique gouffre', spend: '950.00', hook_rate: 0.05,
          quadrant: 'gouffres', quadrant_label_fr: 'Gouffres à budget' },
      ],
    } })
    renderScreen()
    screen.getByTestId('ae-reports-tab-creatifs').click()
    const rows = await screen.findAllByTestId('ae-creatifs-scatter-row')
    expect(rows[0].querySelector('[data-testid="ae-creatifs-scatter-retention"]'))
      .toHaveTextContent('80 % · 50 % · 25 % · 10 %')
    expect(rows[1].querySelector('[data-testid="ae-creatifs-scatter-retention"]'))
      .toHaveTextContent('—')
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

  // PUB54 — aide contextuelle FR sur les métriques techniques (hook rate,
  // coût par résultat).
  it('le classement et le nuage ont leur « ? » sur hook rate / coût par résultat', async () => {
    renderScreen()
    screen.getByTestId('ae-reports-tab-creatifs').click()
    await screen.findAllByTestId('ae-creatifs-leaderboard-row')
    expect(screen.getByTestId('ae-metric-help-toggle-cost_per_result')).toBeInTheDocument()
    expect(screen.getAllByTestId('ae-metric-help-toggle-hook_rate').length).toBe(2)
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
