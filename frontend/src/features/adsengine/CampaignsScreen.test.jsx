import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { rankCreatives } from './adsengine'
import { presetRange, previousRange } from './dateRange'

/* ENG24 — Campagnes : liste + hiérarchie (ADSDEEP60) des miroirs, bouton
   sync-now, classement des créatifs par réponses WhatsApp / coût par asset
   (pas de CTR). */

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  hierarchy: vi.fn(),
  syncNow: vi.fn(),
  fullBackfill: vi.fn(),
  ranking: vi.fn(),
  connGet: vi.fn(),
  breakdownsList: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    campaigns: {
      list: mocks.list, hierarchy: mocks.hierarchy,
      syncNow: mocks.syncNow, fullBackfill: mocks.fullBackfill,
      creativeRanking: mocks.ranking,
    },
    connection: { get: mocks.connGet },
    breakdowns: { list: mocks.breakdownsList },
  },
}))

import CampaignsScreen from './CampaignsScreen'

const renderScreen = () => render(
  <MemoryRouter><CampaignsScreen /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: [
    { id: 1, nom: 'Solaire résidentiel Casa', statut_display: 'Actif', budget_quotidien_mad: 80, depense_mad: 620 },
    { id: 2, nom: 'Pompage agricole', statut_display: 'En pause', budget_quotidien_mad: 50, depense_mad: 210 },
  ] })
  mocks.hierarchy.mockResolvedValue({ data: {
    id: 1, nom: 'Solaire résidentiel Casa', statut_display: 'Actif',
    objectif: 'Messages', budget_quotidien_mad: 80, nb_leads: 12,
    adsets: [
      { id: 11, nom: 'Ad set toiture', statut_display: 'Actif',
        learning_badge: { label: 'En apprentissage', tone: 'info' },
        // PUB13 — brut Meta (conversions/fenêtres d'attribution) + dernière
        // édition significative.
        learning_stage_info: { conversions: 12, attribution_windows: ['7d_click'] },
        last_sig_edit: '2026-07-10T09:00:00Z',
        budget_quotidien_mad: 40, depense_mad: 300, nb_leads: 7,
        ads: [
          { id: 111, meta_id: 'ad-111', nom: 'Reel toiture', statut_display: 'Actif', depense_mad: 150, nb_leads: 4 },
          { id: 112, meta_id: 'ad-112', nom: 'Statique prix', statut_display: 'Actif', depense_mad: 150, nb_leads: 3 },
        ] },
      { id: 12, nom: 'Ad set pompage', statut_display: 'En pause',
        learning_badge: { label: 'Optimisé', tone: 'success' },
        budget_quotidien_mad: 40, depense_mad: 320, nb_leads: 5, ads: [] },
    ],
  } })
  mocks.syncNow.mockResolvedValue({ data: { synced: true } })
  mocks.fullBackfill.mockResolvedValue({ data: {} })
  mocks.connGet.mockResolvedValue({ data: { currency: 'MAD' } })
  mocks.ranking.mockResolvedValue({ data: [
    { id: 'a', nom: 'Reel toiture', reponses_whatsapp: 4, cout_mad: 400 },   // 100/rép
    { id: 'b', nom: 'Statique prix', reponses_whatsapp: 10, cout_mad: 500 },  // 50/rép (meilleur)
    { id: 'c', nom: 'Explainer', reponses_whatsapp: 0, cout_mad: 300 },       // sans réponse → dernier
  ] })
  mocks.breakdownsList.mockResolvedValue({ data: [] })
})

describe('rankCreatives (helper de tri — pur)', () => {
  it('classe par coût-par-réponse croissant, sans-réponse en dernier', () => {
    const ranked = rankCreatives([
      { id: 'a', reponses_whatsapp: 4, cout_mad: 400 },
      { id: 'b', reponses_whatsapp: 10, cout_mad: 500 },
      { id: 'c', reponses_whatsapp: 0, cout_mad: 300 },
    ])
    expect(ranked.map(c => c.id)).toEqual(['b', 'a', 'c'])
    expect(ranked[0]._coutParReponse).toBe(50)
    expect(ranked[2]._coutParReponse).toBeNull()
  })
})

describe('CampaignsScreen (ENG24)', () => {
  it('liste les miroirs de campagnes', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    expect(screen.getByText('Solaire résidentiel Casa')).toBeInTheDocument()
    expect(screen.getByText('Pompage agricole')).toBeInTheDocument()
    expect(screen.getAllByTestId('ae-camp-row')).toHaveLength(2)
  })

  it('AACQ68 — toutes les pages de campagnes sont lues (période courante et précédente)', async () => {
    mocks.list.mockImplementation((params = {}) => {
      const p = params.page || 1
      return Promise.resolve({ data: {
        count: 4, next: p === 1 ? 'p2' : null,
        results: [
          { id: p * 10, nom: `Camp page ${p} A`, statut_display: 'Actif', depense_mad: 100 },
          { id: p * 10 + 1, nom: `Camp page ${p} B`, statut_display: 'Actif', depense_mad: 100 },
        ],
      } })
    })
    renderScreen()
    expect(await screen.findByText('Camp page 2 B')).toBeInTheDocument()
  })

  it('AACQ68 — le total et son delta somment toutes les pages des deux périodes', async () => {
    // Frontière de l'API : la période précédente se reconnaît à son `debut`.
    const precedente = previousRange(presetRange('7j')).debut
    const servir = (pagesCourantes) => mocks.list.mockImplementation((params = {}) => {
      const prev = params.debut === precedente
      const pages = prev ? 2 : pagesCourantes
      const p = params.page || 1
      return Promise.resolve({ data: {
        count: pages * 2, next: p < pages ? `p${p + 1}` : null,
        results: [0, 1].map(i => ({ id: p * 10 + i, nom: `Camp ${prev ? 'P' : 'C'}${p}${i}`,
          statut_display: 'Actif', depense_mad: prev ? 50 : 100 })),
      } })
    })
    const comparer7j = async (total, deltaPct) => {
      const { unmount } = renderScreen()
      await waitFor(() => expect(mocks.list).toHaveBeenCalled())
      fireEvent.click(screen.getByTestId('ae-daterange-preset-7j'))
      await waitFor(() => expect(mocks.list).toHaveBeenCalledWith(
        expect.objectContaining({ debut: presetRange('7j').debut })))
      fireEvent.click(screen.getByTestId('ae-daterange-compare'))
      const bandeau = await screen.findByTestId('ae-camp-compare-summary')
      await waitFor(() => expect(bandeau).toHaveTextContent(`Dépense totale période : ${total}`))
      expect(bandeau).toHaveTextContent(`(${deltaPct} vs période précédente)`)
      unmount()
    }
    servir(2)  // courante 2 pages × 2 × 100 = 400 ; précédente 2 × 2 × 50 = 200
    await comparer7j('400 MAD', '+100 %')
    servir(3)  // une 3ᵉ page courante : le total suit (600), delta contre 200
    await comparer7j('600 MAD', '+200 %')
  })

  it('le bouton Synchroniser appelle syncNow puis recharge', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalledTimes(1))
    fireEvent.click(screen.getByTestId('ae-camp-sync'))
    await waitFor(() => expect(mocks.syncNow).toHaveBeenCalled())
    await waitFor(() => expect(mocks.list).toHaveBeenCalledTimes(2))
    expect(await screen.findByTestId('ae-camp-msg')).toHaveTextContent('Synchronisation lancée')
  })

  it('AACQ70 — synced:false affiche le détail serveur, jamais « lancée »', async () => {
    mocks.syncNow.mockResolvedValue({ data: {
      synced: false, detail: 'Connexion Meta non active — synchronisation impossible.' } })
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalledTimes(1))
    fireEvent.click(screen.getByTestId('ae-camp-sync'))
    const msg = await screen.findByTestId('ae-camp-msg')
    expect(msg).toHaveTextContent('Connexion Meta non active')
    expect(msg).not.toHaveTextContent('Synchronisation lancée')
  })

  it('AACQ70 — un 502 affiche le détail renvoyé', async () => {
    mocks.syncNow.mockRejectedValue({ response: { status: 502, data: { detail: 'Meta injoignable' } } })
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalledTimes(1))
    fireEvent.click(screen.getByTestId('ae-camp-sync'))
    expect(await screen.findByTestId('ae-camp-msg')).toHaveTextContent('Meta injoignable')
  })

  // ── FIXPUB3 — Récupérer tout l'historique ────────────────────────────────
  it('le bouton « Récupérer tout l\'historique » appelle fullBackfill et affiche le message', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalledTimes(1))
    const btn = screen.getByTestId('ae-camp-backfill')
    fireEvent.click(btn)
    expect(btn).toBeDisabled() // état occupé pendant l'appel
    await waitFor(() => expect(mocks.fullBackfill).toHaveBeenCalled())
    expect(await screen.findByTestId('ae-camp-msg'))
      .toHaveTextContent("Récupération de tout l'historique lancée…")
  })

  it('affiche le classement des créatifs par valeur (meilleur en tête)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.ranking).toHaveBeenCalled())
    const rows = await screen.findAllByTestId('ae-camp-ranking-row')
    // Meilleur (coût/réponse le plus bas) = « Statique prix » en première ligne.
    expect(rows[0]).toHaveTextContent('Statique prix')
    expect(rows[0]).toHaveTextContent('50 MAD') // coût/réponse
    // Le créatif sans réponse WhatsApp est relégué en dernier avec « — ».
    expect(rows[2]).toHaveTextContent('Explainer')
  })

  it('étiquette les montants dans la devise du COMPTE Meta (ex. USD)', async () => {
    // Régression : Meta rapporte en devise du compte (souvent USD) — les
    // montants ne doivent plus être étiquetés « MAD » en dur.
    mocks.connGet.mockResolvedValue({ data: { currency: 'USD' } })
    renderScreen()
    await waitFor(() => {
      const rows = screen.getAllByTestId('ae-camp-row')
      expect(rows[0]).toHaveTextContent('620 USD') // dépense
      expect(rows[0]).toHaveTextContent('80 USD') // budget/jour
    })
  })

  describe('ADSDEEP60 — hiérarchie Campagne → Ad sets → Ads', () => {
    it('ouvrir le détail charge la hiérarchie et liste les ad sets (badge apprentissage)', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.list).toHaveBeenCalled())
      fireEvent.click(screen.getAllByTestId('ae-camp-open')[0])
      await waitFor(() => expect(mocks.hierarchy).toHaveBeenCalledWith(1))
      const hierarchy = await screen.findByTestId('ae-camp-hierarchy')
      expect(hierarchy).toHaveTextContent('Messages') // objectif
      expect(hierarchy).toHaveTextContent('12') // leads réels campagne

      const adsetRows = screen.getAllByTestId('ae-camp-adset-row')
      expect(adsetRows).toHaveLength(2)
      expect(adsetRows[0]).toHaveTextContent('Ad set toiture')
      expect(adsetRows[0]).toHaveTextContent('En apprentissage')
      expect(adsetRows[1]).toHaveTextContent('Optimisé')
    })

    it('ouvrir un ad set descend au 3ᵉ niveau (ads) avec fil d’Ariane', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.list).toHaveBeenCalled())
      fireEvent.click(screen.getAllByTestId('ae-camp-open')[0])
      await screen.findByTestId('ae-camp-hierarchy')
      fireEvent.click(screen.getAllByTestId('ae-camp-adset-open')[0])

      const adsTable = await screen.findByTestId('ae-camp-ads-table')
      expect(adsTable).toHaveTextContent('Reel toiture')
      expect(adsTable).toHaveTextContent('Statique prix')

      const breadcrumb = screen.getByTestId('ae-camp-breadcrumb')
      expect(breadcrumb).toHaveTextContent('Campagnes')
      expect(breadcrumb).toHaveTextContent('Solaire résidentiel Casa')
      expect(breadcrumb).toHaveTextContent('Ad set toiture')

      // PUB44 — chaque ad porte un lien croisé vers sa fiche complète.
      const links = screen.getAllByTestId('ae-camp-ad-full-story')
      expect(links).toHaveLength(2)
      expect(links[0]).toHaveAttribute('href', '/publicite/ad/ad-111')
    })

    it('PUB3 — drill des ventilations par ad set, puis par ad', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.list).toHaveBeenCalled())
      fireEvent.click(screen.getAllByTestId('ae-camp-open')[0])
      await screen.findByTestId('ae-camp-hierarchy')

      // Niveau ad set : ouvrir les ventilations du 1er ad set (id 11).
      fireEvent.click(screen.getAllByTestId('ae-camp-adset-breakdowns')[0])
      await waitFor(() => expect(mocks.breakdownsList).toHaveBeenCalledWith({
        object_type: 'adset', object_id: 11,
      }))
      expect(await screen.findByTestId('ae-breakdowns-panel')).toBeInTheDocument()

      // Descendre au niveau ads : le panneau ad set disparaît, on peut ouvrir
      // les ventilations d'une ad (id 111).
      fireEvent.click(screen.getAllByTestId('ae-camp-adset-open')[0])
      await screen.findByTestId('ae-camp-ads-table')
      expect(screen.queryByTestId('ae-breakdowns-panel')).toBeNull()

      fireEvent.click(screen.getAllByTestId('ae-camp-ad-breakdowns')[0])
      await waitFor(() => expect(mocks.breakdownsList).toHaveBeenCalledWith({
        object_type: 'ad', object_id: 111,
      }))
      expect(await screen.findByTestId('ae-breakdowns-panel')).toBeInTheDocument()
    })

    it('PUB13 — le panneau « Apprentissage Meta » montre learning_stage_info brut + last_sig_edit', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.list).toHaveBeenCalled())
      fireEvent.click(screen.getAllByTestId('ae-camp-open')[0])
      await screen.findByTestId('ae-camp-hierarchy')
      fireEvent.click(screen.getAllByTestId('ae-camp-adset-open')[0])

      const panel = await screen.findByTestId('ae-camp-learning-panel')
      expect(panel).toHaveTextContent('conversions : 12')
      expect(within(panel).getByTestId('ae-camp-learning-last-sig-edit')).not.toHaveTextContent('Aucune.')
    })

    it('PUB13 — état vide sans learning_stage_info', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.list).toHaveBeenCalled())
      fireEvent.click(screen.getAllByTestId('ae-camp-open')[0])
      await screen.findByTestId('ae-camp-hierarchy')
      // 2ᵉ ad set (id 12, « Ad set pompage ») n'a ni learning_stage_info ni last_sig_edit.
      fireEvent.click(screen.getAllByTestId('ae-camp-adset-open')[1])
      expect(await screen.findByTestId('ae-camp-learning-empty')).toBeInTheDocument()
      expect(screen.getByTestId('ae-camp-learning-last-sig-edit')).toHaveTextContent('Aucune.')
    })

    it('« Retour aux ad sets » remonte au 2ᵉ niveau sans recharger la hiérarchie', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.list).toHaveBeenCalled())
      fireEvent.click(screen.getAllByTestId('ae-camp-open')[0])
      await screen.findByTestId('ae-camp-hierarchy')
      fireEvent.click(screen.getAllByTestId('ae-camp-adset-open')[0])
      await screen.findByTestId('ae-camp-ads-table')

      fireEvent.click(screen.getByTestId('ae-camp-adset-back'))
      expect(await screen.findByTestId('ae-camp-adsets-table')).toBeInTheDocument()
      expect(mocks.hierarchy).toHaveBeenCalledTimes(1) // pas de rechargement réseau

      expect(screen.queryByTestId('ae-camp-ads-table')).toBeNull()
    })

    it('le fil d’Ariane « Campagnes » ferme la hiérarchie', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.list).toHaveBeenCalled())
      fireEvent.click(screen.getAllByTestId('ae-camp-open')[0])
      await screen.findByTestId('ae-camp-hierarchy')
      fireEvent.click(screen.getByTestId('ae-camp-breadcrumb-campaigns'))
      expect(screen.queryByTestId('ae-camp-hierarchy')).toBeNull()
    })
  })

  // ── PUB40 — Sélecteur de période + comparaison ─────────────────────────
  describe('PUB40 — sélecteur de période', () => {
    it('affiche la barre de période et recharge les campagnes au changement', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.list).toHaveBeenCalled())
      expect(screen.getByTestId('ae-daterange')).toBeInTheDocument()
      mocks.list.mockClear()
      fireEvent.click(screen.getByTestId('ae-daterange-preset-hier'))
      await waitFor(() => expect(mocks.list).toHaveBeenCalled())
      const params = mocks.list.mock.calls[0][0]
      expect(params.debut).toBe(params.fin)
    })

    it('comparaison activée -> bandeau de dépense totale + delta', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.list).toHaveBeenCalled())
      expect(screen.queryByTestId('ae-camp-compare-summary')).toBeNull()
      // FIXPUB2 — défaut « Tout » (sans bornes) : la case comparer reste
      // désactivée tant qu'une période BORNÉE n'est pas choisie.
      fireEvent.click(screen.getByTestId('ae-daterange-preset-7j'))
      await waitFor(() => expect(mocks.list).toHaveBeenCalledTimes(2))
      mocks.list.mockClear()
      fireEvent.click(screen.getByTestId('ae-daterange-compare'))
      await waitFor(() => expect(mocks.list).toHaveBeenCalledTimes(2))
      expect(await screen.findByTestId('ae-camp-compare-summary'))
        .toHaveTextContent('vs période précédente')
    })
  })

  // ── FIXPUB2 — défaut « Tout » (aucune borne) ────────────────────────────
  describe('FIXPUB2 — fenêtre par défaut', () => {
    it('démarre sur « Tout » (aucune borne envoyée à l’API)', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.list).toHaveBeenCalled())
      expect(screen.getByTestId('ae-daterange-preset-tout')).toHaveAttribute('aria-pressed', 'true')
      const params = mocks.list.mock.calls[0][0]
      expect(params.debut).toBeUndefined()
      expect(params.fin).toBeUndefined()
    })
  })

  // ── PUB41 — Fraîcheur + panne visibles ─────────────────────────────────
  describe('PUB41 — état-erreur distinct de l’état-vide', () => {
    it('panne réseau -> message d’erreur, PAS « aucune campagne synchronisée »', async () => {
      mocks.list.mockRejectedValue(new Error('network'))
      renderScreen()
      expect(await screen.findByTestId('ae-camp-load-error')).toBeInTheDocument()
      expect(screen.queryByText('Aucune campagne synchronisée')).toBeNull()
    })

    it('liste réellement vide (succès) -> état-vide normal, pas d’erreur', async () => {
      mocks.list.mockResolvedValue({ data: [] })
      renderScreen()
      await waitFor(() => expect(mocks.list).toHaveBeenCalled())
      expect(screen.getByText('Aucune campagne synchronisée')).toBeInTheDocument()
      expect(screen.queryByTestId('ae-camp-load-error')).toBeNull()
    })
  })
})
