import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* CAD37 — la branche Ramadan est MORTE par défaut : `est_en_ramadan` renvoie
   faux tant que les DEUX dates ne sont pas saisies, et l'écran se contentait
   de dire « dates laissées vides = hors Ramadan » sans jamais rappeler de les
   remplir. Le calendrier hégirien glissant, il faut les retaper chaque année.

   Ce module verrouille les trois choses qui font que le remède tient :
     * sans dates pour l'année en cours, le rappel ET la proposition
       hégirienne s'affichent ;
     * la proposition ne POSE rien : elle remplit les champs au clic, et
       l'enregistrement reste un geste humain ;
     * avec des dates saisies, le bandeau disparaît (pas de bruit permanent).

   L'horloge est GELÉE : « pour l'année en cours » est exactement la question
   qu'une horloge vivante rend instable. */

import LeadsSection from './LeadsSection'
import { periodesRamadan, proposerRamadan, datesRamadanASaisir }
  from '../../lib/hijriDate'

// Dimanche 21 septembre 2026 — l'année en cours des tests.
const AUJOURDHUI = new Date(Date.UTC(2026, 8, 21, 9, 0, 0))

const CHAMPS_VIDES = {
  default_owner: '', default_installer: '', referral_enabled: false,
  referral_reward: '', lead_sla_hours: '24',
  message_heure_debut: '08:30', appel_heure_debut: '09:00',
  appel_heure_fin: '20:00', vendredi_pause_debut: '11:30',
  vendredi_pause_fin: '15:00', ramadan_debut: '', ramadan_fin: '',
  ramadan_appel_debut: '09:00', ramadan_appel_fin: '15:00',
  premier_contact_objectif_min: '5',
}

const LISTES = {
  assignables: [], tags: [], newTag: '', motifs: [], newMotif: '',
  canaux: [], newCanal: '',
}

function noop() {}

function renderSection(form, setForm = noop) {
  return render(
    <LeadsSection
      form={form} set={noop} setForm={setForm}
      {...LISTES}
      setNewTag={noop} addTag={noop} renameTag={noop} delTag={noop}
      archiveTag={noop} setTagColor={noop}
      setNewMotif={noop} addMotif={noop} renameMotif={noop} delMotif={noop}
      archiveMotif={noop}
      setNewCanal={noop} addCanal={noop} renameCanal={noop} delCanal={noop}
      archiveCanal={noop}
    />,
  )
}

describe('CAD37 — dates de Ramadan : rappel et proposition', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.setSystemTime(AUJOURDHUI)
  })

  afterEach(() => {
    vi.useRealTimers()
    cleanup()
  })

  it('affiche le rappel ET la proposition quand aucune date n’est saisie', () => {
    renderSection({ ...CHAMPS_VIDES })
    const rappel = screen.getByTestId('cad37-rappel-ramadan')
    expect(rappel).toBeInTheDocument()
    const attendu = proposerRamadan(AUJOURDHUI)
    expect(rappel).toHaveTextContent(attendu.debut)
    expect(rappel).toHaveTextContent(attendu.fin)
  })

  it('ne POSE aucune date : le clic remplit le formulaire, rien de plus', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const setForm = vi.fn()
    renderSection({ ...CHAMPS_VIDES }, setForm)

    // Avant le clic, les deux champs sont VIDES : rien n'a été posé au rendu.
    expect(screen.getByLabelText('Ramadan — début')).toHaveValue('')
    expect(screen.getByLabelText('Ramadan — fin')).toHaveValue('')
    expect(setForm).not.toHaveBeenCalled()

    await user.click(
      screen.getByRole('button', { name: /Utiliser cette proposition/i }))

    expect(setForm).toHaveBeenCalledTimes(1)
    const attendu = proposerRamadan(AUJOURDHUI)
    const suivant = setForm.mock.calls[0][0]({ ...CHAMPS_VIDES })
    expect(suivant.ramadan_debut).toBe(attendu.debut)
    expect(suivant.ramadan_fin).toBe(attendu.fin)
  })

  it('ne dit plus rien une fois les deux dates saisies pour l’année', () => {
    const periode = periodesRamadan(2026)[0]
    renderSection({
      ...CHAMPS_VIDES,
      ramadan_debut: periode.debut, ramadan_fin: periode.fin,
    })
    expect(screen.queryByTestId('cad37-rappel-ramadan')).toBeNull()
  })

  it('rappelle encore quand les dates datent de l’année précédente', () => {
    renderSection({
      ...CHAMPS_VIDES,
      ramadan_debut: '2025-03-01', ramadan_fin: '2025-03-30',
    })
    expect(screen.getByTestId('cad37-rappel-ramadan')).toBeInTheDocument()
  })
})

describe('CAD37 — le convertisseur hégirien ne fabrique aucune date fausse', () => {
  it('rend une période de Ramadan complète pour une année donnée', () => {
    const periodes = periodesRamadan(2026)
    expect(periodes).toHaveLength(1)
    expect(periodes[0].debut < periodes[0].fin).toBe(true)
    expect(periodes[0].anneeHegirienne).toMatch(/^\d{4}$/)
  })

  it('ne TRONQUE pas un Ramadan à cheval sur le 31 décembre', () => {
    // 2030 porte deux Ramadan : janvier, puis un qui déborde sur 2031.
    const periodes = periodesRamadan(2030)
    expect(periodes).toHaveLength(2)
    expect(periodes[1].debut.startsWith('2030-12')).toBe(true)
    expect(periodes[1].fin.startsWith('2031-')).toBe(true)
  })

  it('une année illisible ne lève jamais : tableau vide', () => {
    expect(periodesRamadan('pas une année')).toEqual([])
    expect(proposerRamadan('pas une date')).toBeNull()
  })

  it('deux dates manquantes valent « à saisir », deux dates de l’année non', () => {
    expect(datesRamadanASaisir('', '', AUJOURDHUI)).toBe(true)
    expect(datesRamadanASaisir('2026-02-18', '', AUJOURDHUI)).toBe(true)
    expect(datesRamadanASaisir('2026-02-18', '2026-03-19', AUJOURDHUI))
      .toBe(false)
  })
})
