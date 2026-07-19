import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { rankCreatives } from './adsengine'

/* ENG24 — Campagnes : liste + hiérarchie (ADSDEEP60) des miroirs, bouton
   sync-now, classement des créatifs par réponses WhatsApp / coût par asset
   (pas de CTR). */

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  hierarchy: vi.fn(),
  syncNow: vi.fn(),
  ranking: vi.fn(),
  connGet: vi.fn(),
  breakdownsList: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    campaigns: {
      list: mocks.list, hierarchy: mocks.hierarchy,
      syncNow: mocks.syncNow, creativeRanking: mocks.ranking,
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
          { id: 111, nom: 'Reel toiture', statut_display: 'Actif', depense_mad: 150, nb_leads: 4 },
          { id: 112, nom: 'Statique prix', statut_display: 'Actif', depense_mad: 150, nb_leads: 3 },
        ] },
      { id: 12, nom: 'Ad set pompage', statut_display: 'En pause',
        learning_badge: { label: 'Optimisé', tone: 'success' },
        budget_quotidien_mad: 40, depense_mad: 320, nb_leads: 5, ads: [] },
    ],
  } })
  mocks.syncNow.mockResolvedValue({ data: {} })
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

  it('le bouton Synchroniser appelle syncNow puis recharge', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalledTimes(1))
    fireEvent.click(screen.getByTestId('ae-camp-sync'))
    await waitFor(() => expect(mocks.syncNow).toHaveBeenCalled())
    await waitFor(() => expect(mocks.list).toHaveBeenCalledTimes(2))
    expect(await screen.findByTestId('ae-camp-msg')).toHaveTextContent('Synchronisation lancée')
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
})
