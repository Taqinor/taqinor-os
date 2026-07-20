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
  syncStatus: vi.fn(),
  connGet: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    metrics: { adsCockpit: mocks.adsCockpit },
    media: { resolve: mocks.mediaResolve },
    previews: { get: vi.fn() },
    breakdowns: { list: mocks.breakdownsList },
    // PUB8 — courbe de rétention (réutilise reporting/creatifs/nuage/).
    reports: { scatter: mocks.reportsScatter },
    syncStatus: { get: mocks.syncStatus },
    connection: { get: mocks.connGet },
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
  window.localStorage.clear() // PUB43 — jamais de fuite de vue enregistrée entre tests
  mocks.adsCockpit.mockResolvedValue({ data: ROWS })
  mocks.mediaResolve.mockResolvedValue({ data: { url: 'https://cdn.example/img.jpg' } })
  mocks.breakdownsList.mockResolvedValue({ data: [] })
  mocks.reportsScatter.mockResolvedValue({ data: { points: [] } })
  mocks.syncStatus.mockResolvedValue({ data: { types: [], stale: false, worst: null } })
  mocks.connGet.mockResolvedValue({ data: { currency: 'MAD' } })
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

  // ── FIXPUB8 — panneau visible au clic (scroll jusqu'au panneau) ─────────
  it('FIXPUB8 — ouvrir le détail fait défiler jusqu’au panneau (jamais au montage)', async () => {
    const scrollIntoView = vi.fn()
    window.HTMLElement.prototype.scrollIntoView = scrollIntoView
    renderScreen()
    await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
    expect(scrollIntoView).not.toHaveBeenCalled() // jamais au montage
    fireEvent.click(screen.getAllByTestId('ae-cockpit-open')[0])
    await screen.findByTestId('ae-cockpit-detail')
    await waitFor(() => expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' }))
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

  // ── PUB44 — Lien croisé vers la fiche « histoire complète » ─────────────
  it('chaque ligne porte un lien vers sa fiche complète', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
    const links = screen.getAllByTestId('ae-cockpit-full-story')
    expect(links.length).toBeGreaterThan(0)
    expect(links[0]).toHaveAttribute('href', expect.stringMatching(/^\/publicite\/ad\/ad-\d$/))
  })

  // ── FIXPUB9 — devise du compte Meta + colonnes Odoo ──────────────────────
  describe('FIXPUB9 — devise + colonnes Odoo', () => {
    it('étiquette les montants Meta dans la devise du compte (ex. USD), CPL (Odoo) reste en MAD', async () => {
      mocks.connGet.mockResolvedValue({ data: { currency: 'USD' } })
      mocks.adsCockpit.mockResolvedValue({ data: [
        { ...ROWS[0], leads_odoo: 4, cpl_odoo: '225.00' },
      ] })
      renderScreen()
      await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
      const row = screen.getByTestId('ae-cockpit-row')
      expect(row).toHaveTextContent('900 USD') // dépense (Meta)
      expect(row).toHaveTextContent('180 USD') // CPL (Meta)
      expect(row).toHaveTextContent('225 MAD') // CPL (Odoo) — reste en MAD
      expect(row).toHaveTextContent('4') // Leads (Odoo)
    })

    it('Leads (Odoo) / CPL (Odoo) absents -> tirets, jamais fabriqués', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
      const row = screen.getAllByTestId('ae-cockpit-row')[0]
      expect(row).toHaveTextContent('—')
    })
  })

  // ── PUB40 — Sélecteur de période + comparaison ─────────────────────────
  describe('PUB40 — sélecteur de période', () => {
    it('affiche la barre de période et recharge le cockpit au changement', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
      expect(screen.getByTestId('ae-daterange')).toBeInTheDocument()
      mocks.adsCockpit.mockClear()
      fireEvent.click(screen.getByTestId('ae-daterange-preset-hier'))
      await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
      const params = mocks.adsCockpit.mock.calls[0][0]
      expect(params.debut).toBe(params.fin)
    })

    it('comparaison activée -> bandeau de dépense totale + delta', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
      expect(screen.queryByTestId('ae-cockpit-compare-summary')).toBeNull()
      // FIXPUB2 — défaut « Tout » (sans bornes) : la case comparer reste
      // désactivée tant qu'une période BORNÉE n'est pas choisie.
      fireEvent.click(screen.getByTestId('ae-daterange-preset-7j'))
      await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalledTimes(2))
      mocks.adsCockpit.mockClear()
      fireEvent.click(screen.getByTestId('ae-daterange-compare'))
      // Comparaison active -> 2 appels (période courante + précédente).
      await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalledTimes(2))
      expect(await screen.findByTestId('ae-cockpit-compare-summary'))
        .toHaveTextContent('vs période précédente')
    })
  })

  // ── FIXPUB2 — défaut « Tout » (aucune borne) ────────────────────────────
  describe('FIXPUB2 — fenêtre par défaut', () => {
    it('démarre sur « Tout » (aucune borne envoyée à l’API)', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
      expect(screen.getByTestId('ae-daterange-preset-tout')).toHaveAttribute('aria-pressed', 'true')
      const params = mocks.adsCockpit.mock.calls[0][0]
      expect(params.debut).toBeUndefined()
      expect(params.fin).toBeUndefined()
    })
  })

  // ── PUB41 — Fraîcheur + panne visibles ─────────────────────────────────
  describe('PUB41 — état-erreur distinct de l’état-vide', () => {
    it('panne réseau -> message d’erreur, PAS « aucune ad synchronisée »', async () => {
      mocks.adsCockpit.mockRejectedValue(new Error('network'))
      renderScreen()
      expect(await screen.findByTestId('ae-cockpit-load-error')).toBeInTheDocument()
      expect(screen.queryByText('Aucune ad synchronisée')).toBeNull()
    })

    it('liste réellement vide (succès) -> état-vide normal, pas d’erreur', async () => {
      mocks.adsCockpit.mockResolvedValue({ data: [] })
      renderScreen()
      await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
      expect(screen.getByText('Aucune ad synchronisée')).toBeInTheDocument()
      expect(screen.queryByTestId('ae-cockpit-load-error')).toBeNull()
    })

    it('bandeau global de panne monté (mock syncStatus stale)', async () => {
      mocks.syncStatus.mockResolvedValue({ data: {
        types: [{ type: 'insights', label: 'Insights', age_minutes: 2000, last_ok_at: '2026-07-17T08:00:00Z', stale: true }],
        stale: true,
        worst: { type: 'insights', label: 'Insights', age_minutes: 2000, last_ok_at: '2026-07-17T08:00:00Z' },
      } })
      renderScreen()
      expect(await screen.findByTestId('ae-sync-banner')).toBeInTheDocument()
    })
  })

  // ── PUB43 — Vues enregistrées un-clic ────────────────────────────────────
  describe('PUB43 — vues enregistrées un-clic', () => {
    // Fixture dédiée : distingue « en fatigue » (fired, sévérité NON critique)
    // de « en baisse » (fired ET critique) — le jeu ROWS global ne les
    // différencie pas (une seule ad fired, et elle est critique).
    const VIEW_ROWS = [
      { id: 1, meta_id: 'ad-1', nom: 'Vidéo gagnante', thumbnail_kind: 'video',
        depense_mad: '500.00', signatures: 3, cost_per_signature_mad: '166.67',
        fatigue: { fired: false, insufficient_data: false, severity: 'info' } },
      { id: 2, meta_id: 'ad-2', nom: 'Statique correcte', thumbnail_kind: 'image',
        depense_mad: '200.00', signatures: 1, cost_per_signature_mad: '200.00',
        fatigue: { fired: false, insufficient_data: false, severity: 'info' } },
      { id: 3, meta_id: 'ad-3', nom: 'Fatiguée possible', thumbnail_kind: 'image',
        depense_mad: '400.00', signatures: 0, cost_per_signature_mad: null,
        fatigue: { fired: true, severity: 'avertissement' } },
      { id: 4, meta_id: 'ad-4', nom: 'En chute confirmée', thumbnail_kind: 'video',
        depense_mad: '1200.00', signatures: 0, cost_per_signature_mad: null,
        fatigue: { fired: true, severity: 'critique' } },
    ]

    it('affiche les 5 onglets (Toutes + 4 vues prédéfinies)', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
      for (const key of ['toutes', 'top', 'fatigue', 'baisse', 'videos']) {
        expect(screen.getByTestId(`ae-cockpit-view-${key}`)).toBeInTheDocument()
      }
      expect(screen.getByTestId('ae-cockpit-view-toutes')).toHaveAttribute('aria-pressed', 'true')
    })

    it('« Top Ads » : signatures>0 triées par coût/signature croissant', async () => {
      mocks.adsCockpit.mockResolvedValue({ data: VIEW_ROWS })
      renderScreen()
      await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
      fireEvent.click(screen.getByTestId('ae-cockpit-view-top'))
      const rows = screen.getAllByTestId('ae-cockpit-row')
      expect(rows).toHaveLength(2) // ad-1 (166.67) et ad-2 (200) — ad-3/ad-4 sans signature exclues
      expect(within(rows[0]).getByText('Vidéo gagnante')).toBeInTheDocument()
      expect(within(rows[1]).getByText('Statique correcte')).toBeInTheDocument()
    })

    it('« En fatigue » : toute sévérité déclenchée, triées par dépense décroissante', async () => {
      mocks.adsCockpit.mockResolvedValue({ data: VIEW_ROWS })
      renderScreen()
      await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
      fireEvent.click(screen.getByTestId('ae-cockpit-view-fatigue'))
      const rows = screen.getAllByTestId('ae-cockpit-row')
      expect(rows).toHaveLength(2) // ad-3 (avertissement) + ad-4 (critique)
      expect(within(rows[0]).getByText('En chute confirmée')).toBeInTheDocument() // 1200 > 400
      expect(within(rows[1]).getByText('Fatiguée possible')).toBeInTheDocument()
    })

    it('« En baisse » : UNIQUEMENT la fatigue confirmée (sévérité critique)', async () => {
      mocks.adsCockpit.mockResolvedValue({ data: VIEW_ROWS })
      renderScreen()
      await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
      fireEvent.click(screen.getByTestId('ae-cockpit-view-baisse'))
      const rows = screen.getAllByTestId('ae-cockpit-row')
      expect(rows).toHaveLength(1)
      expect(within(rows[0]).getByText('En chute confirmée')).toBeInTheDocument()
    })

    it('« Meilleures vidéos » : format vidéo uniquement, triées par coût/signature', async () => {
      mocks.adsCockpit.mockResolvedValue({ data: VIEW_ROWS })
      renderScreen()
      await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
      fireEvent.click(screen.getByTestId('ae-cockpit-view-videos'))
      const rows = screen.getAllByTestId('ae-cockpit-row')
      expect(rows).toHaveLength(2) // ad-1 et ad-4 sont vidéo
      expect(within(rows[0]).getByText('Vidéo gagnante')).toBeInTheDocument() // 166.67 avant null
    })

    it('le tri par colonne est DÉSACTIVÉ tant qu’une vue prédéfinie est active', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
      fireEvent.click(screen.getByTestId('ae-cockpit-view-top'))
      expect(screen.getByTestId('ae-cockpit-sort-nb_leads')).toBeDisabled()
      fireEvent.click(screen.getByTestId('ae-cockpit-view-toutes'))
      expect(screen.getByTestId('ae-cockpit-sort-nb_leads')).not.toBeDisabled()
    })

    it('mémorise le dernier onglet choisi (localStorage) entre deux montages', async () => {
      const { unmount } = renderScreen()
      await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
      fireEvent.click(screen.getByTestId('ae-cockpit-view-fatigue'))
      await waitFor(() => expect(
        JSON.parse(window.localStorage.getItem('ae-cockpit-view')).tab).toBe('fatigue'))
      unmount()

      renderScreen()
      await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalledTimes(2))
      expect(screen.getByTestId('ae-cockpit-view-fatigue')).toHaveAttribute('aria-pressed', 'true')
    })

    it('mémorise aussi le tri manuel de « Toutes » entre deux montages', async () => {
      const { unmount } = renderScreen()
      await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
      fireEvent.click(screen.getByTestId('ae-cockpit-sort-nb_leads')) // asc
      await waitFor(() => {
        const saved = JSON.parse(window.localStorage.getItem('ae-cockpit-view'))
        expect(saved.sort).toEqual({ key: 'nb_leads', dir: 'asc' })
      })
      unmount()

      renderScreen()
      await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalledTimes(2))
      const rows = screen.getAllByTestId('ae-cockpit-row')
      // Tri restauré (croissant par leads) : Explainer(0) en tête.
      expect(within(rows[0]).getByText('Explainer')).toBeInTheDocument()
    })
  })

  // ── DATAPUB5 — Sélecteur de colonnes (parité Ads Manager) ────────────────
  describe('DATAPUB5 — sélecteur de colonnes', () => {
    it('ajoute une colonne masquée par défaut (Impressions) et la persiste', async () => {
      mocks.adsCockpit.mockResolvedValue({ data: [
        { ...ROWS[0], impressions: 12000, reach: 8000, ctr: 0.021, cpm_mad: '75.00' },
      ] })
      const { unmount } = renderScreen()
      await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
      // Masquée par défaut (pas d'en-tête triable).
      expect(screen.queryByTestId('ae-cockpit-sort-impressions')).toBeNull()
      // Ouvre le sélecteur et coche « Impressions ».
      fireEvent.click(screen.getByTestId('ae-cockpit-columns-toggle'))
      fireEvent.click(within(screen.getByTestId('ae-cockpit-column-impressions')).getByRole('checkbox'))
      // La colonne apparaît (en-tête + valeur groupée).
      expect(screen.getByTestId('ae-cockpit-sort-impressions')).toBeInTheDocument()
      expect(screen.getByTestId('ae-cockpit-row')).toHaveTextContent('12 000')
      // Persistée.
      await waitFor(() => expect(
        JSON.parse(window.localStorage.getItem('ae-cockpit-columns'))).toContain('impressions'))
      unmount()
      renderScreen()
      await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalledTimes(2))
      expect(screen.getByTestId('ae-cockpit-sort-impressions')).toBeInTheDocument()
    })

    it('CTR/CPC/CPM manquants -> « — », jamais fabriqués', async () => {
      mocks.adsCockpit.mockResolvedValue({ data: [
        { ...ROWS[2], impressions: null, ctr: null, cpc_mad: null, cpm_mad: null },
      ] })
      renderScreen()
      await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
      fireEvent.click(screen.getByTestId('ae-cockpit-columns-toggle'))
      fireEvent.click(within(screen.getByTestId('ae-cockpit-column-ctr')).getByRole('checkbox'))
      // La cellule CTR d'une valeur nulle est « — » (formatPercent(null)).
      expect(screen.getByTestId('ae-cockpit-row')).toHaveTextContent('—')
    })
  })
})
