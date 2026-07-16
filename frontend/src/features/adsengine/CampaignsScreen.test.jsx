import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { rankCreatives } from './adsengine'

/* ENG24 — Campagnes : liste + détail des miroirs, bouton sync-now, classement
   des créatifs par réponses WhatsApp / coût par asset (pas de CTR). */

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  get: vi.fn(),
  syncNow: vi.fn(),
  ranking: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    campaigns: {
      list: mocks.list, get: mocks.get,
      syncNow: mocks.syncNow, creativeRanking: mocks.ranking,
    },
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
  mocks.get.mockResolvedValue({ data: {
    id: 1, nom: 'Solaire résidentiel Casa', statut_display: 'Actif',
    objectif: 'Messages', budget_quotidien_mad: 80, nb_leads: 12 } })
  mocks.syncNow.mockResolvedValue({ data: {} })
  mocks.ranking.mockResolvedValue({ data: [
    { id: 'a', nom: 'Reel toiture', reponses_whatsapp: 4, cout_mad: 400 },   // 100/rép
    { id: 'b', nom: 'Statique prix', reponses_whatsapp: 10, cout_mad: 500 },  // 50/rép (meilleur)
    { id: 'c', nom: 'Explainer', reponses_whatsapp: 0, cout_mad: 300 },       // sans réponse → dernier
  ] })
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

  it('ouvrir le détail charge campaigns.get et affiche les infos', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    fireEvent.click(screen.getAllByTestId('ae-camp-open')[0])
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith(1))
    const detail = await screen.findByTestId('ae-camp-detail')
    expect(detail).toHaveTextContent('Messages') // objectif du détail
    expect(detail).toHaveTextContent('12') // nb leads
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
})
