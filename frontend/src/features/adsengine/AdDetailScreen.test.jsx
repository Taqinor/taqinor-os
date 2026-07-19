import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

/* PUB44 — fiche « histoire complète » d'une ad (/publicite/ad/:id) : créatif,
   métriques (même ligne que le cockpit), actions passées, commentaires,
   règles l'ayant touchée, expériences, ventilations — en UN SEUL écran. */

const mocks = vi.hoisted(() => ({
  fullStory: vi.fn(),
  mediaResolve: vi.fn(),
  syncStatus: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    ads: { fullStory: mocks.fullStory },
    media: { resolve: mocks.mediaResolve },
    previews: { get: vi.fn() },
    syncStatus: { get: mocks.syncStatus },
  },
}))

import AdDetailScreen from './AdDetailScreen'

const renderScreen = (id = 'ad-1') => render(
  <MemoryRouter initialEntries={[`/publicite/ad/${id}`]}>
    <Routes>
      <Route path="/publicite/ad/:id" element={<AdDetailScreen />} />
    </Routes>
  </MemoryRouter>)

const STORY = {
  ad: { id: 1, meta_id: 'ad-1', nom: 'Reel toiture', statut: 'ACTIVE', statut_display: 'Active' },
  creatif: { title: 'Toiture solaire', body: 'Économisez.', video_id: '', image_hash: '' },
  metriques: {
    depense_mad: '900.00', nb_leads: 5, cpl_mad: '180.00', signatures: 1,
    cost_per_signature_mad: '900.00', frequency: '2.10',
    fatigue: { fired: true, severity: 'critique', message_fr: 'Fatigue confirmée' },
  },
  actions: [
    { id: 11, kind: 'edit_copy', kind_display: 'Édition du texte / créatif',
      reason_fr: "Rafraîchir l'accroche.", status: 'approuvee', status_display: 'Approuvée', auto: false },
  ],
  commentaires: [
    { id: 21, from_name: 'Client X', message: 'Combien ça coûte ?' },
  ],
  regles: [
    { id: 31, kind: 'cost_spike', kind_display: 'Pic de coût', severity: 'warning',
      message_fr: 'Pic de coût détecté.', rule_label: 'CPL hors bande' },
  ],
  experiences: [
    { id: 41, label: 'Bras A', is_active: true, experiment_nom: 'Test hooks', experiment_statut: 'running' },
  ],
  breakdowns: [
    { id: 51, dimension: 'region', dimension_display: 'Région', key: 'Casablanca', date: '2026-07-18', spend: '30.00' },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.fullStory.mockResolvedValue({ data: STORY })
  mocks.mediaResolve.mockResolvedValue({ data: { url: 'https://cdn.example/img.jpg' } })
  mocks.syncStatus.mockResolvedValue({ data: { types: [], stale: false, worst: null } })
})

describe('AdDetailScreen (PUB44)', () => {
  it('charge la fiche pour l’id de la route', async () => {
    renderScreen('ad-1')
    await waitFor(() => expect(mocks.fullStory).toHaveBeenCalledWith('ad-1'))
  })

  it('affiche le nom + statut de l’ad', async () => {
    renderScreen()
    expect(await screen.findByText('Reel toiture')).toBeInTheDocument()
    expect(screen.getByTestId('ae-ad-detail-statut')).toHaveTextContent('Active')
  })

  it('rend le créatif via AdCreativePanel (réutilisé, pas réinventé)', async () => {
    renderScreen()
    expect(await screen.findByTestId('ae-creative-panel')).toBeInTheDocument()
    expect(screen.getByTestId('ae-creative-title')).toHaveTextContent('Toiture solaire')
  })

  it('affiche les métriques (même ligne que le cockpit)', async () => {
    renderScreen()
    const metrics = await screen.findByTestId('ae-ad-detail-metrics')
    expect(metrics).toHaveTextContent('900 MAD') // dépense
    expect(metrics).toHaveTextContent('5') // leads
    expect(screen.getByTestId('ae-ad-detail-fatigue')).toHaveTextContent('Fatigue confirmée')
  })

  it('liste les actions passées', async () => {
    renderScreen()
    const rows = await screen.findAllByTestId('ae-ad-detail-action-row')
    expect(rows).toHaveLength(1)
    expect(rows[0]).toHaveTextContent('Édition du texte / créatif')
    expect(rows[0]).toHaveTextContent('Approuvée')
  })

  it('liste les commentaires', async () => {
    renderScreen()
    const rows = await screen.findAllByTestId('ae-ad-detail-comment-row')
    expect(rows[0]).toHaveTextContent('Client X')
    expect(rows[0]).toHaveTextContent('Combien ça coûte ?')
  })

  it('liste les règles l’ayant touchée', async () => {
    renderScreen()
    const rows = await screen.findAllByTestId('ae-ad-detail-rule-row')
    expect(rows[0]).toHaveTextContent('CPL hors bande')
  })

  it('liste les expériences', async () => {
    renderScreen()
    const rows = await screen.findAllByTestId('ae-ad-detail-experiment-row')
    expect(rows[0]).toHaveTextContent('Test hooks')
    expect(rows[0]).toHaveTextContent('Bras A')
  })

  it('liste les ventilations', async () => {
    renderScreen()
    const rows = await screen.findAllByTestId('ae-ad-detail-breakdown-row')
    expect(rows[0]).toHaveTextContent('Casablanca')
  })

  it('sections vides -> message dédié par section (jamais fabriqué)', async () => {
    mocks.fullStory.mockResolvedValue({ data: {
      ad: { meta_id: 'ad-1', nom: 'Ad seule', statut_display: 'Active' },
      creatif: null, metriques: null, actions: [], commentaires: [],
      regles: [], experiences: [], breakdowns: [],
    } })
    renderScreen()
    expect(await screen.findByTestId('ae-ad-detail-no-creative')).toBeInTheDocument()
    expect(screen.getByText('Aucune action enregistrée sur cette ad.')).toBeInTheDocument()
    expect(screen.getByText('Aucun commentaire sur cette ad.')).toBeInTheDocument()
    expect(screen.getByText('Cette ad ne participe à aucune expérience.')).toBeInTheDocument()
  })

  it('ad introuvable (404) -> message dédié, distinct d’une panne', async () => {
    const err = new Error('not found')
    err.response = { status: 404 }
    mocks.fullStory.mockRejectedValue(err)
    renderScreen('nope')
    expect(await screen.findByTestId('ae-ad-detail-not-found')).toBeInTheDocument()
    expect(screen.queryByTestId('ae-ad-detail-load-error')).toBeNull()
  })

  it('panne réseau (pas 404) -> message d’erreur distinct', async () => {
    mocks.fullStory.mockRejectedValue(new Error('network'))
    renderScreen()
    expect(await screen.findByTestId('ae-ad-detail-load-error')).toBeInTheDocument()
    expect(screen.queryByTestId('ae-ad-detail-not-found')).toBeNull()
  })
})
