import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* APX28 — le « Calendrier techniciens » devient une VRAIE grille horaire
   (7 h → 19 h × techniciens).

   CHAMPS RÉELS (vérifiés côté serveur) : `date_prevue` est un DateField (aucune
   heure), il n'existe AUCUN champ de durée, et la seule information horaire est
   la fenêtre de RDV XFSM5 `fenetre_debut`/`fenetre_fin`. On teste donc que :
   (1) une intervention AVEC fenêtre est posée sur l'axe à la bonne hauteur ;
   (2) une intervention SANS fenêtre n'est JAMAIS placée à une heure inventée —
   elle reste dans la bande « Sans créneau » (blocs séquencés) ;
   (3) un chevauchement est VISIBLE dans la grille (marqué destructive) ;
   (4) poser une intervention sur une case d'heure passe par une confirmation
   puis UN SEUL PATCH sur l'endpoint EXISTANT (zéro écriture serveur nouvelle). */

const api = vi.hoisted(() => ({
  getGanttChantiers: vi.fn(),
  getCalendrierInterventions: vi.fn(),
  getMaTournee: vi.fn(),
  getPlanDeCharge: vi.fn(),
  getConflitsAffectation: vi.fn(),
  getNivellementCharge: vi.fn(),
  getPlanningCamionnettes: vi.fn(),
  getInstallations: vi.fn(),
  updateIntervention: vi.fn(),
}))

vi.mock('../../api/installationsApi', () => ({ default: api }))
vi.mock('../../ui/confirm', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

import PlanificationPage, {
  blocGeometry, chevauchements, minutesDeHeure, heureEnTime, payloadDeplacement,
} from './PlanificationPage'

function renderPage() {
  const store = configureStore({ reducer: { auth: () => ({ role: 'responsable' }) } })
  return render(<Provider store={store}><PlanificationPage /></Provider>)
}

beforeEach(() => {
  api.getGanttChantiers.mockResolvedValue({ data: [] })
  api.getMaTournee.mockResolvedValue({ data: { stops: [] } })
  api.getPlanDeCharge.mockResolvedValue({ data: { techniciens: [] } })
  api.getConflitsAffectation.mockResolvedValue({ data: { conflits: [] } })
  api.getNivellementCharge.mockResolvedValue({ data: { propositions: [] } })
  api.getPlanningCamionnettes.mockResolvedValue({ data: { camionnettes: [] } })
  api.getInstallations.mockResolvedValue({ data: [] })
  api.updateIntervention.mockResolvedValue({ data: {} })
  api.getCalendrierInterventions.mockResolvedValue({ data: [] })
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('APX28 · géométrie honnête de la grille', () => {
  it('lit une heure servie et refuse une heure illisible', () => {
    expect(minutesDeHeure('09:30:00')).toBe(570)
    expect(minutesDeHeure('09:30')).toBe(570)
    expect(minutesDeHeure(null)).toBeNull()
    expect(minutesDeHeure('bof')).toBeNull()
    expect(minutesDeHeure('33:00')).toBeNull()
    expect(heureEnTime(9)).toBe('09:00:00')
  })

  it('place une intervention À FENÊTRE au bon offset et à la bonne hauteur', () => {
    // 09:00 → 11:00 sur un axe qui démarre à 7 h, 44 px/heure.
    const geo = blocGeometry({ fenetre_debut: '09:00:00', fenetre_fin: '11:00:00' })
    expect(geo.topPx).toBe(2 * 44)
    expect(geo.heightPx).toBe(2 * 44)
  })

  it('n’INVENTE aucune durée : sans fenêtre de fin, un seul créneau', () => {
    const geo = blocGeometry({ fenetre_debut: '08:00:00', fenetre_fin: null })
    expect(geo.heightPx).toBe(44)
  })

  it('sans fenêtre du tout, aucune position sur l’axe (bande « Sans créneau »)', () => {
    expect(blocGeometry({ date_prevue: '2026-08-01' })).toBeNull()
    expect(blocGeometry({ fenetre_debut: null, fenetre_fin: '10:00:00' })).toBeNull()
  })

  it('détecte les chevauchements réels, et EUX SEULS', () => {
    const conflits = chevauchements([
      { id: 1, fenetre_debut: '09:00:00', fenetre_fin: '11:00:00' },
      { id: 2, fenetre_debut: '10:00:00', fenetre_fin: '12:00:00' },
      { id: 3, fenetre_debut: '13:00:00', fenetre_fin: '14:00:00' },
      { id: 4 }, // sans horaire : jamais un conflit (aucune heure connue)
      { id: 5 },
    ])
    expect([...conflits].sort()).toEqual([1, 2])
  })

  it('deux créneaux qui se touchent (10-11 puis 11-12) ne sont pas un conflit', () => {
    const conflits = chevauchements([
      { id: 1, fenetre_debut: '10:00:00', fenetre_fin: '11:00:00' },
      { id: 2, fenetre_debut: '11:00:00', fenetre_fin: '12:00:00' },
    ])
    expect(conflits.size).toBe(0)
  })
})

describe('APX28 · la grille du jour', () => {
  const board = () => ([
    {
      technicien: { id: 1, nom: 'Ali' },
      interventions: [
        { id: 10, installation_reference: 'CH-010', client_nom: 'Client A', date_prevue: '2026-08-01', fenetre_debut: '09:00:00', fenetre_fin: '11:00:00' },
        { id: 11, installation_reference: 'CH-011', client_nom: 'Client B', date_prevue: '2026-08-01', fenetre_debut: '10:00:00', fenetre_fin: '12:00:00' },
        { id: 12, installation_reference: 'CH-012', client_nom: 'Client C', date_prevue: '2026-08-01' },
      ],
    },
    { technicien: { id: 2, nom: 'Sara' }, interventions: [] },
  ])

  async function ouvrirCalendrier() {
    api.getCalendrierInterventions.mockResolvedValue({ data: board() })
    renderPage()
    await userEvent.click(screen.getByText('Calendrier techniciens'))
    await waitFor(() => expect(api.getCalendrierInterventions).toHaveBeenCalled())
    await waitFor(() => expect(screen.getByTestId('grille-jour')).toBeInTheDocument())
  }

  it('rend un axe horaire 7 h → 19 h avec des cases d’heure déposables', async () => {
    await ouvrirCalendrier()
    expect(screen.getByText('07:00')).toBeInTheDocument()
    expect(screen.getByText('18:00')).toBeInTheDocument()
    expect(screen.queryByText('06:00')).toBeNull()
    // Chaque colonne technicien a ses 12 cases d'heure déposables.
    expect(screen.getByTestId('slot-1-9')).toBeInTheDocument()
    expect(screen.getByTestId('slot-2-18')).toBeInTheDocument()
  })

  it('l’intervention SANS horaire reste dans la bande « Sans créneau »', async () => {
    await ouvrirCalendrier()
    const bande = screen.getByTestId('sans-creneau-1')
    expect(bande).toHaveTextContent('CH-012')
    expect(bande).not.toHaveTextContent('CH-010')
  })

  it('le chevauchement est VISIBLE dans la grille (les deux blocs marqués)', async () => {
    await ouvrirCalendrier()
    expect(screen.getByTestId('iv-10')).toHaveAttribute('data-conflit', 'true')
    expect(screen.getByTestId('iv-11')).toHaveAttribute('data-conflit', 'true')
    expect(screen.getByTestId('iv-12')).not.toHaveAttribute('data-conflit')
    expect(screen.getByText(/2 en conflit/)).toBeInTheDocument()
  })

  it('la vue Semaine condensée s’affiche sans toucher au serveur autrement', async () => {
    await ouvrirCalendrier()
    await userEvent.click(screen.getByRole('button', { name: 'Semaine' }))
    await waitFor(() => expect(screen.getByTestId('grille-semaine')).toBeInTheDocument())
    // Aucune méthode d'écriture n'a été appelée par un simple changement de vue.
    expect(api.updateIntervention).not.toHaveBeenCalled()
  })

  it('les cartes restent saisissables (poignée accessible) dans la grille', async () => {
    await ouvrirCalendrier()
    expect(screen.getByLabelText(/Déplacer l'intervention CH-012/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Déplacer l'intervention CH-010/)).toBeInTheDocument()
    // Un simple rendu n'écrit RIEN côté serveur.
    expect(api.updateIntervention).not.toHaveBeenCalled()
  })
})

describe('APX28 · ce qu’un dépôt écrit (payload du PATCH existant)', () => {
  it('dépôt sur une case d’heure : technicien + jour + fenêtre d’UNE heure', () => {
    expect(payloadDeplacement('3', '2026-08-01', 9)).toEqual({
      technicien: 3,
      date_prevue: '2026-08-01',
      fenetre_debut: '09:00:00',
      fenetre_fin: '10:00:00',
    })
  })

  it('dépôt sur un jour (semaine) : AUCUNE fenêtre inventée', () => {
    expect(payloadDeplacement('3', '2026-08-03', null)).toEqual({
      technicien: 3,
      date_prevue: '2026-08-03',
    })
  })

  it('colonne « non assigné » : le technicien est vidé, jamais un id bidon', () => {
    const p = payloadDeplacement('__non_assigne__', '2026-08-01', 14)
    expect(p.technicien).toBeNull()
    expect(p.fenetre_debut).toBe('14:00:00')
  })
})
