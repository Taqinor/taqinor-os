import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
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
      // WIR195 — incidents de présence : liste, régularisation et compteur.
      getIncidentsPresence: vi.fn(empty),
      getCompteurIncidentsPresence: vi.fn(empty),
      justifierIncidentPresence: vi.fn(),
      // WIR238 — écriture du roster + conflits de congé + référentiel employés.
      createAffectationRoster: vi.fn(),
      updateAffectationRoster: vi.fn(),
      getConflitsRoster: vi.fn(empty),
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
    // WIR195 — l'écran bascule sur la vue qui montre ce qui vient d'être créé.
    await waitFor(() => expect(
      screen.getByRole('radio', { name: 'Incidents de présence' }),
    ).toBeChecked())
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

/* WIR238 — le roster était en lecture seule et le drapeau `conflit_conge`
   calculé par le serveur n'apparaissait nulle part : on pouvait planifier un
   technicien sur un congé validé sans jamais le voir. */
describe('Temps — WIR238 : roster écrivable et conflits de congé visibles', () => {
  const AFFECTATION = {
    id: 21, employe: 9, employe_nom: 'Bennani Youssef', equipe: 'Camionnette 2',
    date: '2026-08-20', creneau: 'journee', creneau_display: 'Journée',
    conflit_conge: true,
  }

  beforeEach(() => vi.clearAllMocks())

  it('crée une affectation sans jamais envoyer semaine_du ni conflit_conge', async () => {
    rhApi.createAffectationRoster.mockResolvedValueOnce({ data: { id: 22 } })
    renderTemps()
    await screen.findAllByText('Temps & présence')
    fireEvent.click(screen.getByRole('radio', { name: 'Roster' }))

    fireEvent.click((await screen.findAllByRole('button', { name: /Nouvelle affectation/ }))[0])
    expect(await screen.findByRole('dialog')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Employé'), { target: { value: '9' } })
    fireEvent.change(screen.getByLabelText('Équipe'), { target: { value: 'Camionnette 2' } })
    fireEvent.change(screen.getByLabelText('Date'), { target: { value: '2026-08-20' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Enregistrer' })[0])

    await waitFor(() => expect(rhApi.createAffectationRoster).toHaveBeenCalled())
    const corps = rhApi.createAffectationRoster.mock.calls[0][0]
    expect(corps).toMatchObject({ employe: '9', equipe: 'Camionnette 2', date: '2026-08-20', creneau: 'journee' })
    // Les deux champs CALCULÉS serveur ne doivent jamais partir du client.
    expect(corps).not.toHaveProperty('semaine_du')
    expect(corps).not.toHaveProperty('conflit_conge')
    expect(corps).not.toHaveProperty('company')
  })

  it('affiche le conflit de congé en colonne ET le bandeau 30 jours', async () => {
    rhApi.getRoster.mockResolvedValueOnce({ data: [AFFECTATION] })
    rhApi.getConflitsRoster.mockResolvedValueOnce({ data: [AFFECTATION] })
    renderTemps()
    await screen.findAllByText('Temps & présence')
    fireEvent.click(screen.getByRole('radio', { name: 'Roster' }))

    expect((await screen.findAllByText('Congé validé'))[0]).toBeInTheDocument()
    expect(screen.getByText(/1 affectation\(s\) en conflit de congé sur les 30 prochains jours/))
      .toBeInTheDocument()
  })

  it('modifie une affectation existante via updateAffectationRoster', async () => {
    rhApi.getRoster.mockResolvedValueOnce({ data: [AFFECTATION] })
    rhApi.updateAffectationRoster.mockResolvedValueOnce({ data: {} })
    renderTemps()
    await screen.findAllByText('Temps & présence')
    fireEvent.click(screen.getByRole('radio', { name: 'Roster' }))

    fireEvent.click((await screen.findAllByRole('button', { name: 'Modifier' }))[0])
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Équipe'), { target: { value: 'Camionnette 3' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Enregistrer' })[0])

    await waitFor(() => expect(rhApi.updateAffectationRoster).toHaveBeenCalledWith(
      21, expect.objectContaining({ equipe: 'Camionnette 3' }),
    ))
  })
})

/* WIR195 — un incident de présence créé n'était relisible NULLE PART : ni
   liste, ni régularisation. La vue « Incidents de présence » les affiche et
   les fait passer en « Justifié » via l'@action serveur. */
describe('Temps — WIR195 : incidents de présence relisibles et justifiables', () => {
  const INCIDENT = {
    id: 42, employe: 9, employe_nom: 'Bennani Youssef',
    type_incident: 'absence_injustifiee',
    type_incident_display: 'Absence injustifiée',
    date: '2026-08-12', minutes_retard: 0, justifie: false, motif: '',
  }

  beforeEach(() => {
    vi.clearAllMocks()
    rhApi.getIncidentsPresence.mockResolvedValue({ data: [INCIDENT] })
    rhApi.getCompteurIncidentsPresence.mockResolvedValue({
      data: [{
        employe_id: 9, retards: 0, absences: 1,
        departs_anticipes: 0, total: 1, minutes_retard_total: 0,
      }],
    })
  })

  it('charge la liste + le compteur et rend l’onglet', async () => {
    renderTemps()
    await screen.findAllByText('Temps & présence')
    expect(rhApi.getIncidentsPresence).toHaveBeenCalled()
    expect(rhApi.getCompteurIncidentsPresence).toHaveBeenCalled()

    fireEvent.click(screen.getByRole('radio', { name: 'Incidents de présence' }))
    expect((await screen.findAllByText('Absence injustifiée'))[0]).toBeInTheDocument()
    // Le compteur serveur est rendu sous le nom résolu depuis la liste.
    expect(screen.getByText(/Incidents non justifiés par employé/)).toBeInTheDocument()
  })

  it('justifie un incident via rhApi.justifierIncidentPresence (motif requis)', async () => {
    rhApi.justifierIncidentPresence.mockResolvedValueOnce({
      data: { ...INCIDENT, justifie: true, motif: 'Certificat médical' },
    })
    renderTemps()
    await screen.findAllByText('Temps & présence')
    fireEvent.click(screen.getByRole('radio', { name: 'Incidents de présence' }))

    fireEvent.click((await screen.findAllByRole('button', { name: 'Justifier' }))[0])
    expect(await screen.findByRole('dialog')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Motif de la régularisation'), {
      target: { value: 'Certificat médical' },
    })
    const valider = screen.getAllByRole('button', { name: 'Justifier' })
      .find((b) => b.getAttribute('type') === 'submit')
    fireEvent.click(valider)

    await waitFor(() => expect(rhApi.justifierIncidentPresence).toHaveBeenCalledWith(
      42, { motif: 'Certificat médical' },
    ))
  })

  it('un incident déjà justifié n’expose plus l’action', async () => {
    rhApi.getIncidentsPresence.mockResolvedValue({
      data: [{ ...INCIDENT, justifie: true, motif: 'Certificat médical' }],
    })
    renderTemps()
    await screen.findAllByText('Temps & présence')
    fireEvent.click(screen.getByRole('radio', { name: 'Incidents de présence' }))
    expect((await screen.findAllByText('Justifié'))[0]).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Justifier' })).toBeNull()
  })
})
