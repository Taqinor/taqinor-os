import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import Temps from './Temps.jsx'

/* XRH10/11/13 — Temps & présence : le module charge les devices kiosque et
   expose l'onglet Kiosque + l'import CSV. Smoke : ne plante pas au montage. */

vi.mock('../../api/rhApi', () => {
  const empty = () => Promise.resolve({ data: [] })
  return {
    default: {
      getPointages: vi.fn(empty),
      getRoster: vi.fn(empty),
      getPresencesChantier: vi.fn(empty),
      getHeuresSupp: vi.fn(empty),
      getDevicesKiosque: vi.fn(empty),
      pointagerDepart: vi.fn(),
      exportPaieHeuresSupp: vi.fn(empty),
      importPointageCsv: vi.fn(),
      emettreDeviceKiosque: vi.fn(),
      revoquerDeviceKiosque: vi.fn(),
      updatePointage: vi.fn(),
      getCorrectionsPointage: vi.fn(empty),
      // ZRH6/ZRH18 — absents non justifiés + rapport de présence.
      getAbsentsNonJustifies: vi.fn(empty),
      genererIncidentAbsence: vi.fn(() => Promise.resolve({ data: {} })),
      getRapportPresence: vi.fn(() => Promise.resolve({ data: { par_employe: [], totaux_departement: [] } })),
      // WIR195 — incidents de présence (liste + justification).
      getIncidentsPresence: vi.fn(empty),
      justifierIncidentPresence: vi.fn(),
      // WIR238 — roster : création/édition + conflits de congé.
      createRoster: vi.fn(),
      updateRoster: vi.fn(),
      getConflitsRoster: vi.fn(empty),
      // WIR239 — émargement de présence chantier (colonne Geofence morte).
      emargerPresenceChantier: vi.fn(),
      getEmployes: vi.fn(() => Promise.resolve({
        data: [{ id: 9, nom: 'Bennani', prenom: 'Youssef' }],
      })),
    },
  }
})

function renderTemps() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <Temps />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('Temps — kiosque & import (XRH10/13)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('charge les devices kiosque et propose l’onglet Kiosque', async () => {
    renderTemps()
    expect((await screen.findAllByText('Temps & présence')).length).toBeGreaterThan(0)
    expect(rhApi.getDevicesKiosque).toHaveBeenCalled()
    expect(screen.getByRole('radio', { name: 'Kiosque' })).toBeInTheDocument()
  })

  it('affiche le bouton d’import CSV sur les pointages', async () => {
    renderTemps()
    await screen.findAllByText('Temps & présence')
    expect(screen.getAllByRole('button', { name: /Importer CSV/ })[0]).toBeInTheDocument()
  })
})

describe('Temps — XRH11/12 : audit des corrections & géofence', () => {
  beforeEach(() => vi.clearAllMocks())

  it('ouvre l’historique immuable des corrections d’un pointage (XRH11)', async () => {
    rhApi.getPointages.mockResolvedValueOnce({
      data: [{
        id: 7, employe: 2, employe_nom: 'Bennani Youssef',
        heure_arrivee: '2026-08-12T08:00:00Z', heure_depart: '2026-08-12T17:00:00Z',
        type_pointage: 'complet', type_pointage_display: 'Complet',
      }],
    })
    rhApi.getCorrectionsPointage.mockResolvedValueOnce({
      data: [{
        id: 3, pointage: 7, champ: 'heure_depart',
        ancienne_valeur: '16:00', nouvelle_valeur: '17:00',
        motif: 'Oubli de pointage', auteur_nom: 'rh1',
        date_creation: '2026-08-12T18:00:00Z',
      }],
    })
    renderTemps()
    await screen.findAllByText('Temps & présence')

    fireEvent.click((await screen.findAllByRole('button', { name: 'Historique des corrections' }))[0])
    await waitFor(() => expect(rhApi.getCorrectionsPointage).toHaveBeenCalledWith(7))
    expect(await screen.findByText('heure_depart')).toBeInTheDocument()
    expect(screen.getByText(/Oubli de pointage/)).toBeInTheDocument()
  })

  it('signale une présence chantier émargée hors zone (XRH12)', async () => {
    rhApi.getPresencesChantier.mockResolvedValueOnce({
      data: [{
        id: 11, employe: 2, employe_nom: 'Bennani Youssef',
        installation_id: 4, date: '2026-08-12',
        statut: 'present', statut_display: 'Présent',
        emarge: true, hors_zone: true,
      }],
    })
    renderTemps()
    await screen.findAllByText('Temps & présence')

    fireEvent.click(screen.getByRole('radio', { name: 'Présences chantier' }))
    expect((await screen.findAllByText('Hors zone'))[0]).toBeInTheDocument()
  })
})

describe('Temps — PACT19 : « Export paie » appelle la route qui existe vraiment', () => {
  beforeEach(() => vi.clearAllMocks())

  it('le bouton vit sur « Heures supp. », pas sur « Pointages »', async () => {
    renderTemps()
    await screen.findAllByText('Temps & présence')
    // Vue « Pointages » (défaut) : plus d'export paie ici — il exportait des
    // heures supplémentaires depuis l'écran des pointages, via une route
    // (`/rh/pointages/export-paie/`) qui n'a jamais existé.
    expect(screen.queryByRole('button', { name: /Export paie/ })).toBeNull()

    fireEvent.click(screen.getByRole('radio', { name: 'Heures supp.' }))
    expect((await screen.findAllByRole('button', { name: /Export paie/ }))[0]).toBeInTheDocument()
  })

  it('appelle exportPaieHeuresSupp (/rh/heures-supp/export-paie/) au clic', async () => {
    renderTemps()
    await screen.findAllByText('Temps & présence')
    fireEvent.click(screen.getByRole('radio', { name: 'Heures supp.' }))
    fireEvent.click((await screen.findAllByRole('button', { name: /Export paie/ }))[0])
    await waitFor(() => expect(rhApi.exportPaieHeuresSupp).toHaveBeenCalled())
  })
})

describe('Temps — ZRH6/ZRH18 : absents non justifiés & rapport de présence', () => {
  beforeEach(() => vi.clearAllMocks())

  it('liste les absents du jour et crée un incident (ZRH6)', async () => {
    rhApi.getAbsentsNonJustifies.mockResolvedValueOnce({
      data: [{ employe_id: 9, matricule: 'M009', nom: 'Bennani Youssef' }],
    })
    renderTemps()
    await screen.findAllByText('Temps & présence')

    fireEvent.click(screen.getByRole('radio', { name: 'Absents du jour' }))
    expect((await screen.findAllByText('Bennani Youssef'))[0]).toBeInTheDocument()

    fireEvent.click((await screen.findAllByRole('button', { name: 'Créer un incident d’absence' }))[0])
    await waitFor(() => expect(rhApi.genererIncidentAbsence).toHaveBeenCalledWith({ employe: 9 }))
  })

  it('affiche le rapport de présence du mois (ZRH18)', async () => {
    rhApi.getRapportPresence.mockResolvedValueOnce({
      data: {
        par_employe: [{
          employe_id: 9, nom: 'Bennani Youssef', jours_pointes: 18,
          heures_totales: 144.0, heures_supp: 6, jours_absence: 1,
          taux_presence_pct: 90.0,
        }],
        totaux_departement: [],
      },
    })
    renderTemps()
    await screen.findAllByText('Temps & présence')

    fireEvent.click(screen.getByRole('radio', { name: 'Rapport de présence' }))
    expect((await screen.findAllByText('Bennani Youssef'))[0]).toBeInTheDocument()
    expect(screen.getAllByText('90,0 %').length).toBeGreaterThan(0)
  })
})

describe('Temps — WIR195 : incidents de présence (liste + justification)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('liste un incident ouvert et le justifie via rhApi.justifierIncidentPresence', async () => {
    rhApi.getIncidentsPresence.mockResolvedValueOnce({
      data: [{
        id: 21, employe: 9, employe_nom: 'Bennani Youssef',
        type_incident: 'retard', type_incident_display: 'Retard',
        date: '2026-08-12', minutes_retard: 15, justifie: false, motif: '',
      }],
    })
    rhApi.justifierIncidentPresence.mockResolvedValueOnce({
      data: { id: 21, justifie: true, motif: 'Panne de voiture' },
    })
    renderTemps()
    await screen.findAllByText('Temps & présence')

    fireEvent.click(screen.getByRole('radio', { name: 'Incidents de présence' }))
    expect((await screen.findAllByText('Bennani Youssef'))[0]).toBeInTheDocument()
    expect(screen.getAllByText('Ouvert').length).toBeGreaterThan(0)

    fireEvent.click((await screen.findAllByRole('button', { name: 'Justifier' }))[0])
    const dialog = within(await screen.findByRole('dialog'))
    fireEvent.change(dialog.getByLabelText('Motif'), { target: { value: 'Panne de voiture' } })
    fireEvent.click(dialog.getByRole('button', { name: 'Justifier' }))

    await waitFor(() => expect(rhApi.justifierIncidentPresence).toHaveBeenCalledWith(
      21, { motif: 'Panne de voiture' },
    ))
  })

  it('bascule sur « Incidents de présence » après génération d’un incident (ZRH6/WIR195)', async () => {
    rhApi.getAbsentsNonJustifies.mockResolvedValueOnce({
      data: [{ employe_id: 9, matricule: 'M009', nom: 'Bennani Youssef' }],
    })
    renderTemps()
    await screen.findAllByText('Temps & présence')

    fireEvent.click(screen.getByRole('radio', { name: 'Absents du jour' }))
    fireEvent.click((await screen.findAllByRole('button', { name: 'Créer un incident d’absence' }))[0])

    await waitFor(() => expect(screen.getByRole('radio', { name: 'Incidents de présence' })).toHaveAttribute('aria-checked', 'true'))
  })
})

describe('Temps — WIR238 : roster (création + conflits de congé)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('crée une affectation via rhApi.createRoster (sans semaine_du/conflit_conge)', async () => {
    rhApi.createRoster.mockResolvedValueOnce({ data: { id: 1 } })
    renderTemps()
    await screen.findAllByText('Temps & présence')
    fireEvent.click(screen.getByRole('radio', { name: 'Roster' }))

    fireEvent.click((await screen.findAllByRole('button', { name: /Nouvelle affectation/ }))[0])
    const dialog = within(await screen.findByRole('dialog'))
    fireEvent.change(dialog.getByLabelText('Employé'), { target: { value: '9' } })
    fireEvent.change(dialog.getByLabelText('Date'), { target: { value: '2026-08-20' } })
    fireEvent.click(dialog.getByRole('button', { name: 'Créer l’affectation' }))

    await waitFor(() => expect(rhApi.createRoster).toHaveBeenCalledWith(
      expect.objectContaining({ employe: '9', date: '2026-08-20', creneau: 'journee' }),
    ))
    expect(rhApi.createRoster.mock.calls[0][0]).not.toHaveProperty('semaine_du')
    expect(rhApi.createRoster.mock.calls[0][0]).not.toHaveProperty('conflit_conge')
  })

  it('affiche le bandeau de conflits (30 j) et la colonne Conflit congé', async () => {
    rhApi.getConflitsRoster.mockResolvedValueOnce({
      data: [{ id: 3, employe: 9, employe_nom: 'Bennani Youssef', date: '2026-08-20', conflit_conge: true }],
    })
    rhApi.getRoster.mockResolvedValueOnce({
      data: [{ id: 3, employe: 9, employe_nom: 'Bennani Youssef', date: '2026-08-20', conflit_conge: true }],
    })
    renderTemps()
    await screen.findAllByText('Temps & présence')
    fireEvent.click(screen.getByRole('radio', { name: 'Roster' }))

    expect(await screen.findByText(/en conflit de congé sur les 30 prochains jours/)).toBeInTheDocument()
    expect((await screen.findAllByText('Conflit congé')).length).toBeGreaterThan(1)
  })
})

describe('Temps — WIR239 : émargement de présence chantier (colonne Geofence morte)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('émarge une présence chantier non émargée', async () => {
    rhApi.getPresencesChantier.mockResolvedValueOnce({
      data: [{
        id: 15, employe: 9, employe_nom: 'Bennani Youssef',
        installation_id: 4, date: '2026-08-12',
        statut: 'present', statut_display: 'Présent', emarge: false, hors_zone: false,
      }],
    })
    rhApi.emargerPresenceChantier.mockResolvedValueOnce({
      data: { id: 15, emarge: true, hors_zone: false },
    })
    renderTemps()
    await screen.findAllByText('Temps & présence')
    fireEvent.click(screen.getByRole('radio', { name: 'Présences chantier' }))
    await screen.findAllByText('Bennani Youssef')

    fireEvent.click((await screen.findAllByRole('button', { name: 'Émarger' }))[0])
    await waitFor(() => expect(rhApi.emargerPresenceChantier).toHaveBeenCalledWith(15))
  })
})
