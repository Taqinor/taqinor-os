import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* XSAV12/21/27/28, ZSAV8/9 — panneau d'actions avancées du ticket. savApi
   mocké. */

vi.mock('../../api/savApi', () => ({
  default: {
    neplusSuivreTicket: vi.fn(),
    suivreTicket: vi.fn(),
    getTicketsSimilaires: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    getTriageIa: vi.fn(),
    fusionnerTicket: vi.fn(),
    creerLeadDepuisTicket: vi.fn(),
    getPretsEquipement: vi.fn(() => Promise.resolve({ data: [] })),
    retournerPretEquipement: vi.fn(),
    getReponsesType: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))

import savApi from '../../api/savApi'
import TicketAdvancedPanel from './TicketAdvancedPanel'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const renderPanel = (ticket = { id: 5 }, opts = {}) => render(
  <MemoryRouter><TicketAdvancedPanel ticket={ticket} {...opts} /></MemoryRouter>,
)

describe('TicketAdvancedPanel — ZSAV9 suivre/ne plus suivre', () => {
  it('bascule de "Suivre" à "Ne plus suivre"', async () => {
    savApi.suivreTicket.mockResolvedValue({ data: {} })
    renderPanel()
    const btn = await screen.findByRole('button', { name: /Suivre ce ticket/ })
    fireEvent.click(btn)
    await waitFor(() => expect(savApi.suivreTicket).toHaveBeenCalledWith(5))
    expect(await screen.findByRole('button', { name: /Ne plus suivre/ })).toBeInTheDocument()
  })
})

describe('TicketAdvancedPanel — XSAV21 résolutions similaires', () => {
  it('affiche les tickets similaires renvoyés par l\'API', async () => {
    savApi.getTicketsSimilaires.mockResolvedValue({
      data: { results: [{ id: 9, reference: 'SAV-009', produit_nom: 'Onduleur Huawei' }] },
    })
    renderPanel()
    expect(await screen.findByText('SAV-009')).toBeInTheDocument()
  })
})

describe('TicketAdvancedPanel — XSAV28 triage IA', () => {
  it('affiche la suggestion de triage', async () => {
    savApi.getTriageIa.mockResolvedValue({
      data: {
        disponible: true,
        suggestion: {
          type_panne_suggere: 'Onduleur en défaut', priorite_suggeree: 'haute',
          resume: 'Onduleur ne redémarre plus.', brouillon_reponse: 'Bonjour, nous intervenons.',
        },
      },
    })
    renderPanel()
    fireEvent.click(screen.getByRole('button', { name: 'Suggérer' }))
    expect(await screen.findByText('Onduleur en défaut')).toBeInTheDocument()
  })

  it('affiche un message si le triage IA n\'est pas configuré', async () => {
    savApi.getTriageIa.mockResolvedValue({ data: { disponible: false } })
    renderPanel()
    fireEvent.click(screen.getByRole('button', { name: 'Suggérer' }))
    expect(await screen.findByText(/non configuré/)).toBeInTheDocument()
  })
})

describe('TicketAdvancedPanel — XSAV12 fusion de doublon', () => {
  it('fusionne un ticket doublon par ID', async () => {
    savApi.fusionnerTicket.mockResolvedValue({ data: {} })
    renderPanel()
    fireEvent.change(screen.getByPlaceholderText('ID du ticket doublon'), { target: { value: '12' } })
    fireEvent.click(screen.getByRole('button', { name: 'Fusionner' }))
    await waitFor(() => expect(savApi.fusionnerTicket).toHaveBeenCalledWith(5, '12'))
  })
})

describe('TicketAdvancedPanel — ZSAV8 conversion en lead', () => {
  it('convertit le ticket en lead CRM et affiche le badge', async () => {
    savApi.creerLeadDepuisTicket.mockResolvedValue({ data: { lead_id: 77, created: true } })
    renderPanel()
    fireEvent.click(screen.getByRole('button', { name: /Convertir en opportunité CRM/ }))
    await waitFor(() => expect(savApi.creerLeadDepuisTicket).toHaveBeenCalledWith(5))
    expect(await screen.findByText('Lead CRM #77')).toBeInTheDocument()
  })
})

describe('TicketAdvancedPanel — XSAV23 macro picker', () => {
  it('appelle onNoteInsert avec l\'id de la macro cliquée', async () => {
    savApi.getReponsesType.mockResolvedValue({
      data: { results: [{ id: 3, titre: 'Relance client' }] },
    })
    const onNoteInsert = vi.fn()
    renderPanel({ id: 5 }, { onNoteInsert })
    const btn = await screen.findByRole('button', { name: /Relance client/ })
    fireEvent.click(btn)
    expect(onNoteInsert).toHaveBeenCalledWith(3)
  })
})

describe('TicketAdvancedPanel — XSAV27 prêts d\'équipement', () => {
  it('affiche un prêt en cours et permet de le retourner', async () => {
    savApi.getPretsEquipement.mockResolvedValue({
      data: [{ id: 1, produit_nom: 'Onduleur de prêt', date_sortie: '2026-07-01', date_retour_reelle: null }],
    })
    savApi.retournerPretEquipement.mockResolvedValue({ data: {} })
    renderPanel()
    expect(await screen.findByText(/Onduleur de prêt/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Retourner/ }))
    await waitFor(() => expect(savApi.retournerPretEquipement).toHaveBeenCalledWith(5, 1))
  })
})
