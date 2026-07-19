import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ADSDEEP22 — Cockpit par ad : une ligne par ad (thumbnail, dépense,
   conversations, leads, CPL, signatures, coût/signature, fréquence, badge de
   fatigue, statut+apprentissage), table TRIABLE, drill vers le détail créatif. */

const mocks = vi.hoisted(() => ({
  adsCockpit: vi.fn(),
  mediaResolve: vi.fn(),
  breakdownsList: vi.fn(),
  reportsScatter: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    metrics: { adsCockpit: mocks.adsCockpit },
    media: { resolve: mocks.mediaResolve },
    previews: { get: vi.fn() },
    breakdowns: { list: mocks.breakdownsList },
    // PUB8 — courbe de rétention (réutilise reporting/creatifs/nuage/).
    reports: { scatter: mocks.reportsScatter },
  },
}))

import AdsCockpitScreen from './AdsCockpitScreen'

const renderScreen = () => render(<MemoryRouter><AdsCockpitScreen /></MemoryRouter>)

const ROWS = [
  {
    id: 1, meta_id: 'ad-1', nom: 'Reel toiture', statut: 'ACTIVE', statut_display: 'Active',
    learning_badge: { status: 'LEARNING', label: 'En apprentissage', tone: 'info' },
    thumbnail_ref: 'vid-123', thumbnail_kind: 'video',
    depense_mad: '900.00', conversations: 12, nb_leads: 5, cpl_mad: '180.00',
    signatures: 1, cost_per_signature_mad: '900.00', frequency: '2.10',
    fatigue: { fired: true, insufficient_data: false, severity: 'critique', message_fr: 'Fatigue confirmée' },
  },
  {
    id: 2, meta_id: 'ad-2', nom: 'Statique prix', statut: 'ACTIVE', statut_display: 'Active',
    learning_badge: { status: 'SUCCESS', label: 'Optimisé', tone: 'success' },
    thumbnail_ref: 'img-hash-1', thumbnail_kind: 'image',
    depense_mad: '300.00', conversations: 20, nb_leads: 8, cpl_mad: '37.50',
    signatures: 2, cost_per_signature_mad: '150.00', frequency: '1.20',
    fatigue: { fired: false, insufficient_data: false, severity: 'avertissement', message_fr: '' },
  },
  {
    id: 3, meta_id: 'ad-3', nom: 'Explainer', statut: 'PAUSED', statut_display: 'En pause',
    learning_badge: { status: '', label: 'Inconnu', tone: 'neutral' },
    thumbnail_ref: null, thumbnail_kind: 'image',
    depense_mad: '50.00', conversations: 0, nb_leads: 0, cpl_mad: null,
    signatures: 0, cost_per_signature_mad: null, frequency: null,
    fatigue: { fired: false, insufficient_data: true, severity: 'info', message_fr: '' },
  },
]

beforeEach(() => {
  vi.clearAllMocks()
  mocks.adsCockpit.mockResolvedValue({ data: ROWS })
  mocks.mediaResolve.mockResolvedValue({ data: { url: 'https://cdn.example/img.jpg' } })
  mocks.breakdownsList.mockResolvedValue({ data: [] })
  mocks.reportsScatter.mockResolvedValue({ data: { points: [] } })
})

describe('AdsCockpitScreen (ADSDEEP22)', () => {
  it('liste une ligne par ad avec toutes les colonnes attendues', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
    const rows = screen.getAllByTestId('ae-cockpit-row')
    expect(rows).toHaveLength(3)
    const row1 = within(rows[0])
    // Tri par défaut = dépense décroissante -> Reel toiture (900) en tête.
    expect(row1.getByText('Reel toiture')).toBeInTheDocument()
    // 900 MAD apparaît deux fois sur cette ligne (dépense ET coût/signature).
    expect(row1.getAllByText('900 MAD')).toHaveLength(2)
    expect(row1.getByText('180 MAD')).toBeInTheDocument() // CPL
    expect(row1.getByText('En apprentissage')).toBeInTheDocument()
  })

  it('affiche les fenêtres de données (ADSDEEP66) leads + insights', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
    expect(screen.getByTestId('ae-data-window-leads')).toBeInTheDocument()
    expect(screen.getByTestId('ae-data-window-insights')).toBeInTheDocument()
  })

  it('miniature : vidéo -> icône, image -> résolue, absente -> icône vide', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
    expect(screen.getByTestId('ae-cockpit-thumb-video')).toBeInTheDocument()
    await waitFor(() => expect(mocks.mediaResolve).toHaveBeenCalledWith('img-hash-1', 'image'))
    expect(await screen.findByTestId('ae-cockpit-thumb-image')).toHaveAttribute(
      'src', 'https://cdn.example/img.jpg')
    expect(screen.getByTestId('ae-cockpit-thumb-empty')).toBeInTheDocument()
  })

  it('badge de fatigue : confirmée / pas de fatigue / historique insuffisant', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
    const badges = screen.getAllByTestId('ae-cockpit-fatigue-badge')
    expect(badges[0]).toHaveTextContent('Fatigue confirmée')
    expect(badges[1]).toHaveTextContent('Pas de fatigue')
    expect(badges[2]).toHaveTextContent('Historique insuffisant')
  })

  it('tri sur une colonne : clic sur "Leads" trie croissant puis décroissant', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('ae-cockpit-sort-nb_leads'))
    let rows = screen.getAllByTestId('ae-cockpit-row')
    // Croissant : Explainer(0) < Reel toiture(5) < Statique prix(8).
    expect(within(rows[0]).getByText('Explainer')).toBeInTheDocument()
    expect(within(rows[2]).getByText('Statique prix')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('ae-cockpit-sort-nb_leads'))
    rows = screen.getAllByTestId('ae-cockpit-row')
    // Décroissant : Statique prix(8) en tête.
    expect(within(rows[0]).getByText('Statique prix')).toBeInTheDocument()
  })

  it('tri sur une colonne avec valeurs manquantes (CPL) : les "—" restent en fin', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('ae-cockpit-sort-cpl_mad'))
    const rows = screen.getAllByTestId('ae-cockpit-row')
    // Explainer (CPL null) toujours en dernier, peu importe le sens.
    expect(within(rows[2]).getByText('Explainer')).toBeInTheDocument()
  })

  it('un clic sur "Détail" ouvre le panneau créatif de l’ad (drill-down)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
    fireEvent.click(screen.getAllByTestId('ae-cockpit-open')[0])
    const detail = await screen.findByTestId('ae-cockpit-detail')
    expect(detail).toBeInTheDocument()
    expect(within(detail).getByTestId('ae-creative-panel')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('ae-cockpit-detail-close'))
    expect(screen.queryByTestId('ae-cockpit-detail')).toBeNull()
  })

  it('PUB8 — le détail d’une ad vidéo montre sa courbe de rétention', async () => {
    mocks.reportsScatter.mockResolvedValue({ data: { points: [
      { ad_meta_id: 'ad-1', name: 'Reel toiture', retention: { p25: 0.8, p50: 0.5, p75: 0.25, p100: 0.1 } },
    ] } })
    renderScreen()
    await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
    // Ligne 0 (par défaut, tri dépense décroissante) = Reel toiture (vidéo).
    fireEvent.click(screen.getAllByTestId('ae-cockpit-open')[0])
    await waitFor(() => expect(mocks.reportsScatter).toHaveBeenCalled())
    const curve = await screen.findByTestId('ae-cockpit-retention')
    expect(curve).toHaveTextContent('80 %')
    expect(curve).toHaveTextContent('10 %')
  })

  it('PUB8 — aucune courbe de rétention pour une ad image', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
    // Ligne 1 = « Statique prix » (image, kind !== 'video').
    fireEvent.click(screen.getAllByTestId('ae-cockpit-open')[1])
    await screen.findByTestId('ae-cockpit-detail')
    expect(mocks.reportsScatter).not.toHaveBeenCalled()
    expect(screen.queryByTestId('ae-cockpit-retention')).toBeNull()
  })

  it('PUB3 — le détail d’une ad monte le panneau de ventilations sur SON id', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
    fireEvent.click(screen.getAllByTestId('ae-cockpit-open')[0])
    const detail = await screen.findByTestId('ae-cockpit-detail')
    expect(within(detail).getByTestId('ae-breakdowns-panel')).toBeInTheDocument()
    await waitFor(() => expect(mocks.breakdownsList).toHaveBeenCalledWith({
      object_type: 'ad', object_id: 1,
    }))
  })

  it('état vide : aucune ad synchronisée', async () => {
    mocks.adsCockpit.mockResolvedValue({ data: [] })
    renderScreen()
    await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
    expect(screen.getByText('Aucune ad synchronisée')).toBeInTheDocument()
  })
})
