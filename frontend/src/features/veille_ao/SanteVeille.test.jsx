import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   VAO37 — Bandeau de santé + carte d'honnêteté « ce que la veille NE voit
   pas ». Deux blocs indissociables (préambule Groupe VAO — promettre
   l'exhaustivité serait faux dès le premier jour, l'erreur qui a coûté FRDISI).
   ========================================================================== */

const mocks = vi.hoisted(() => ({
  sante: vi.fn(),
  create: vi.fn(),
}))

vi.mock('../../api/veilleAoApi', () => ({
  default: { sante: mocks.sante, avis: { create: mocks.create } },
}))

import SanteVeille, { ageLabel } from './SanteVeille'

const renderScreen = (props) => render(<ThemeProvider><SanteVeille {...props} /></ThemeProvider>)

beforeEach(() => {
  vi.clearAllMocks()
})

describe('ageLabel (VAO37 Done= « l’âge de la dernière collecte est visible sans clic »)', () => {
  it('« à l’instant » sous 1 heure', () => {
    expect(ageLabel('2026-08-07T08:30:00', new Date('2026-08-07T08:45:00'))).toBe('à l’instant')
  })

  it('en heures sous 24 h', () => {
    expect(ageLabel('2026-08-07T02:00:00', new Date('2026-08-07T08:00:00'))).toBe('il y a 6 h')
  })

  it('en jours au-delà de 24 h', () => {
    expect(ageLabel('2026-08-04T06:00:00', new Date('2026-08-07T06:00:00'))).toBe('il y a 3 j')
  })

  it('null sans date ou avec une date invalide', () => {
    expect(ageLabel(null)).toBeNull()
    expect(ageLabel('pas une date')).toBeNull()
  })
})

describe('SanteVeille — bloc santé', () => {
  it('affiche la dernière collecte réussie ET son âge sans clic', async () => {
    mocks.sante.mockResolvedValue({
      data: {
        collecte_active: true, derniere_collecte_reussie: '2026-08-06T06:00:00',
        alarme_active: false, avis_examines_hier: 5,
      },
    })
    renderScreen()
    await waitFor(() => expect(mocks.sante).toHaveBeenCalled())
    expect(await screen.findByText('Dernière collecte réussie')).toBeInTheDocument()
    expect(screen.getByText(/il y a/)).toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('VAO37 (Done=) — une alarme active est IMPOSSIBLE à manquer', async () => {
    mocks.sante.mockResolvedValue({
      data: { alarme_active: true, alarme_message: 'La veille ne ramène plus rien — vérifiez.' },
    })
    renderScreen()
    const alerte = await screen.findByRole('alert')
    expect(alerte).toHaveTextContent('La veille ne ramène plus rien')
    expect(screen.queryByText(/aucune alarme/)).not.toBeInTheDocument()
  })

  it('sans alarme, affiche « aucune alarme » et aucun role=alert', async () => {
    mocks.sante.mockResolvedValue({ data: { alarme_active: false, derniere_collecte_reussie: null } })
    renderScreen()
    expect(await screen.findByText(/aucune alarme/)).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('« Jamais » quand aucune collecte n’a encore réussi', async () => {
    mocks.sante.mockResolvedValue({ data: { alarme_active: false, derniere_collecte_reussie: null } })
    renderScreen()
    expect(await screen.findByText('Jamais')).toBeInTheDocument()
  })
})

describe('SanteVeille — carte d’honnêteté (VAO37 Done= « le texte est présent et testé »)', () => {
  beforeEach(() => {
    mocks.sante.mockResolvedValue({ data: { alarme_active: false } })
  })

  it('énonce ce que la veille couvre et ne couvre PAS, avec les chiffres du préambule Groupe VAO', async () => {
    renderScreen()
    expect(await screen.findByText('Ce que la veille automatique ne voit pas')).toBeInTheDocument()
    expect(screen.getByText(/65 à 75 %/)).toBeInTheDocument()
    expect(screen.getByText(/FRDISI/)).toBeInTheDocument()
    expect(screen.getByText(/15 à 25 %/)).toBeInTheDocument()
    expect(screen.getByText(/0 % détectable/)).toBeInTheDocument()
    expect(screen.getByText(/ONEE-Électricité \/ MASEN \/ OCP/)).toBeInTheDocument()
    expect(screen.getByText(/10 % du nombre mais la majorité de la valeur/)).toBeInTheDocument()
  })

  it('rappelle le bouton « Ajouter un avis » pour un AO reçu par WhatsApp', async () => {
    renderScreen()
    expect(await screen.findByText('Un AO reçu par WhatsApp, SMS ou appel ?')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Ajouter un avis/ })).toBeInTheDocument()
  })
})

describe('SanteVeille — « Ajouter un avis » (VAO27)', () => {
  beforeEach(() => {
    mocks.sante.mockResolvedValue({ data: { alarme_active: false } })
  })

  it('informateur est le SEUL champ requis (400 FR sinon, aucun appel réseau)', async () => {
    renderScreen()
    fireEvent.click(await screen.findByRole('button', { name: /Ajouter un avis/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Ajouter' }))
    expect(await screen.findByText(/informateur requis/)).toBeInTheDocument()
    expect(mocks.create).not.toHaveBeenCalled()
  })

  it('avec un informateur choisi, crée l’avis avec source `tuyau_partenaire` et notifie le rafraîchissement', async () => {
    const user = userEvent.setup()
    mocks.create.mockResolvedValue({ data: { id: 9 } })
    const onAvisAjoute = vi.fn()
    renderScreen({ onAvisAjoute })

    fireEvent.click(await screen.findByRole('button', { name: /Ajouter un avis/ }))
    await user.click(screen.getByRole('combobox'))
    fireEvent.click(await screen.findByText('Partenaire'))
    fireEvent.click(screen.getByRole('button', { name: 'Ajouter' }))

    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith(
      expect.objectContaining({ informateur: 'partenaire', source: 'tuyau_partenaire' }),
    ))
    await waitFor(() => expect(onAvisAjoute).toHaveBeenCalled())
  })
})
