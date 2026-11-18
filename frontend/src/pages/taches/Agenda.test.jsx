import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../test/fixtures/contractSamples'
import { lireAgenda, listerAgendasExternes, rouvrirTache, terminerTache } from '../../api/tachesApi'
import Agenda from './Agenda'

vi.mock('../../api/tachesApi', async (importOriginal) => ({
  ...(await importOriginal()),
  lireAgenda: vi.fn(),
  terminerTache: vi.fn(),
  rouvrirTache: vi.fn(),
  planifierTache: vi.fn(),
  listerAgendasExternes: vi.fn(),
}))

/* TCH104 — l'écran Agenda rend `agenda.json` (contrat partagé) : vues Jour / Semaine / Mois /
   À venir, « ← Aujourd'hui → », Toute la journée, rendez-vous externes en lecture seule,
   créneau vide = « Ajouter à HH:MM », cocher sans relire l'agenda, échec qui ne vide rien. */

const AUJOURDHUI = '2026-11-17'
const MAINTENANT = new Date(2026, 10, 17, 9, 41)
const agenda = () => structuredClone(exempleContrat('taches', 'agenda'))

function Adresse() {
  const { search } = useLocation()
  return <output data-testid="adresse">{search}</output>
}

function monter(url = '/taches/agenda') {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/taches/agenda" element={<><Agenda aujourdhui={AUJOURDHUI} maintenant={MAINTENANT} /><Adresse /></>} />
        <Route path="/taches/reglages/iphone" element={<><p>Réglages iPhone</p><Adresse /></>} />
      </Routes>
    </MemoryRouter>,
  )
}

const grille = (container) => container.querySelector('.grille-agenda')
const dernierAppel = () => lireAgenda.mock.calls.at(-1)[0]

beforeEach(() => {
  lireAgenda.mockResolvedValue({ data: agenda() })
  terminerTache.mockResolvedValue({ data: {} })
  rouvrirTache.mockResolvedValue({ data: {} })
  listerAgendasExternes.mockResolvedValue({ data: exempleContrat('taches', 'agendas_externes') })
})
afterEach(() => { vi.clearAllMocks() })

describe('TCH104 — vue Jour', () => {
  it('lit la semaine du jour et rend blocs, sans heure, toute la journée et échéance', async () => {
    const { container } = monter()
    const bloc = await screen.findByRole('button', { name: /Devis Settat/ })
    expect(lireAgenda).toHaveBeenCalledWith({ du: '2026-11-16', au: '2026-11-22' })
    expect(within(grille(container)).getByText('10:00 – 11:00')).toBeInTheDocument()
    expect(bloc.closest('.bloc')).toHaveAttribute('data-p', 'vert')
    expect(within(grille(container)).getByRole('checkbox', { name: 'Fait : Devis Settat' })).not.toBeChecked()
    expect(screen.getByRole('button', { name: 'Timbres' })).toBeInTheDocument()
    const journee = screen.getByRole('group', { name: 'Toute la journée' })
    expect(within(journee).getByRole('link', { name: /Visite — Karim Benali/ })).toHaveAttribute('href', '/visites')
    expect(within(journee).getByText('Dossier subvention · échéance')).toBeInTheDocument()
    expect(container.querySelector('.maintenant-heure')).toHaveTextContent('09:41')
    expect(screen.getByRole('tab', { name: 'Mardi 17 novembre' })).toHaveAttribute('aria-selected', 'true')
  })

  it('un rendez-vous externe est en lecture seule : puce de l\'agenda, détail au toucher, aucune case', async () => {
    const { container } = monter()
    const externe = await screen.findByRole('button', { name: 'Réunion banque · 11:00–12:00 · Microsoft 365' })
    expect(within(externe).getByText('Microsoft 365')).toBeInTheDocument()
    expect(within(grille(container)).queryByRole('checkbox', { name: /Réunion banque/ })).toBeNull()
    fireEvent.click(externe)
    expect(externe).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText("Réunion banque · 11:00–12:00 · Microsoft 365 · Ouvrir dans ton agenda d'origine"))
      .toBeInTheDocument()
  })

  it('un créneau vide ouvre la saisie à son heure', async () => {
    monter()
    await screen.findByRole('button', { name: /Devis Settat/ })
    const ecoute = vi.fn()
    window.addEventListener('taqinor:taches:saisir', ecoute)
    fireEvent.click(screen.getByRole('button', { name: 'Ajouter à 14:30' }))
    window.removeEventListener('taqinor:taches:saisir', ecoute)
    expect(ecoute).toHaveBeenCalledTimes(1)
    expect(ecoute.mock.calls[0][0].detail).toEqual({ jour_prevu: '2026-11-17', heure_debut: '14:30' })
  })

  it('« Férié » et « Jour non travaillé » viennent du jour servi', async () => {
    const ferie = agenda()
    Object.assign(ferie.jours[0], { ferie: true, blocs: [], sans_heure: [], echeances: [], toute_la_journee: [], externes: [] })
    lireAgenda.mockResolvedValue({ data: ferie })
    monter()
    expect(await screen.findByText('Férié')).toBeInTheDocument()
    expect(screen.queryByText('Rien ce jour-là')).toBeNull()
  })

  it('un jour sans rien dit « Rien ce jour-là »', async () => {
    monter('/taches/agenda?jour=2026-11-18')
    expect(await screen.findByText('Rien ce jour-là')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Mercredi 18 novembre' })).toHaveAttribute('aria-selected', 'true')
  })
})

describe('TCH104 — cocher sans relire l\'agenda', () => {
  it('la case d\'un bloc termine la tâche, optimiste, et propose Annuler', async () => {
    const { container } = monter()
    await screen.findByRole('button', { name: /Devis Settat/ })
    const caseBloc = within(grille(container)).getByRole('checkbox', { name: 'Fait : Devis Settat' })
    fireEvent.click(caseBloc)
    expect(caseBloc).toHaveAttribute('aria-checked', 'true')
    await waitFor(() => expect(terminerTache).toHaveBeenCalledWith(20, {}))
    expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Faite')
    expect(lireAgenda).toHaveBeenCalledTimes(1)
  })

  it('un refus du serveur remet la case et le dit', async () => {
    terminerTache.mockRejectedValue({ response: { status: 400, data: { detail: 'Refusé.' } } })
    const { container } = monter()
    await screen.findByRole('button', { name: /Devis Settat/ })
    const caseBloc = within(grille(container)).getByRole('checkbox', { name: 'Fait : Devis Settat' })
    fireEvent.click(caseBloc)
    await waitFor(() => expect(caseBloc).toHaveAttribute('aria-checked', 'false'))
    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(lireAgenda).toHaveBeenCalledTimes(1)
  })
})

describe('TCH104 — vues et navigation', () => {
  it('Semaine : sept colonnes, `vue=semaine` lu, créneaux nommés par leur jour', async () => {
    const { container } = monter()
    await screen.findByRole('button', { name: /Devis Settat/ })
    fireEvent.click(screen.getByRole('radio', { name: 'Semaine' }))
    expect(screen.getByRole('radio', { name: 'Semaine' })).toHaveAttribute('aria-checked', 'true')
    await waitFor(() => expect(dernierAppel()).toEqual({ du: '2026-11-16', au: '2026-11-22', vue: 'semaine' }))
    expect(container.querySelectorAll('.grille-agenda .ag-colonne')).toHaveLength(7)
    expect(screen.getByRole('button', { name: 'Ajouter à 09:00 · mar. 17' })).toBeInTheDocument()
    expect(screen.getByTestId('adresse').textContent).toContain('vue=semaine')
  })

  it('F2 acceptation (P139.1) — Semaine sur iPhone : l\'en-tête d\'un jour dit sa charge « {n} tâches · {h} pour {cap} »', async () => {
    const { container } = monter('/taches/agenda?vue=semaine')
    await waitFor(() => expect(container.querySelector('.ag-sem .ag-sj[aria-current="date"]')).not.toBeNull())
    // mar. 17 du contrat : Timbres (15 min) + Devis Settat (60 min) ; capacité servie `capacite.minutes` = 240
    expect(container.querySelector('.ag-sem .ag-sj[aria-current="date"] .ag-sj-tete')).toHaveTextContent('2 tâches · 1 h 15 pour 4 h')
  })

  it('F2 acceptation — Semaine sur iPhone : un jour passé dit « {n} faites » (maquette agenda-semaine.html, `ag-sj passe`)', async () => {
    const d = agenda()
    const base = d.jours[0].sans_heure[0]
    d.jours.unshift({
      ...d.jours[0], jour: '2026-11-16', toute_la_journee: [], echeances: [], externes: [], blocs: [],
      sans_heure: [
        { ...base, id: 901, titre: 'Faite lundi', statut: 'fait', jour_prevu: '2026-11-16' },
        { ...base, id: 902, titre: 'Encore une faite', statut: 'fait', jour_prevu: '2026-11-16' },
        { ...base, id: 903, titre: 'Restée à faire', statut: 'a_faire', jour_prevu: '2026-11-16' },
      ],
    })
    lireAgenda.mockResolvedValue({ data: d })
    const { container } = monter('/taches/agenda?vue=semaine')
    await waitFor(() => expect(container.querySelector('.ag-sem .ag-sj.passe')).not.toBeNull())
    expect(container.querySelector('.ag-sem .ag-sj.passe .ag-sj-tete')).toHaveTextContent(/^2 faites$/)
  })

  it('F2 acceptation (P139.1) — sans capacité servie, l\'en-tête ne dit que le nombre (jamais une capacité devinée)', async () => {
    const sans = agenda()
    delete sans.capacite
    lireAgenda.mockResolvedValue({ data: sans })
    const { container } = monter('/taches/agenda?vue=semaine')
    await waitFor(() => expect(container.querySelector('.ag-sem .ag-sj[aria-current="date"]')).not.toBeNull())
    expect(container.querySelector('.ag-sem .ag-sj[aria-current="date"] .ag-sj-tete').textContent).not.toMatch(/pour/)
  })

  it('← → décalent la période, « Aujourd\'hui » y revient', async () => {
    monter('/taches/agenda?vue=semaine')
    await waitFor(() => expect(lireAgenda).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('button', { name: 'Semaine suivante' }))
    await waitFor(() => expect(dernierAppel()).toMatchObject({ du: '2026-11-23', au: '2026-11-29' }))
    fireEvent.click(screen.getByRole('button', { name: "Aujourd'hui" }))
    await waitFor(() => expect(dernierAppel()).toMatchObject({ du: '2026-11-16', au: '2026-11-22' }))
  })

  it('Mois : les semaines entières du mois (≤ 42 jours), un jour se choisit', async () => {
    monter('/taches/agenda?vue=mois')
    await waitFor(() => expect(dernierAppel()).toEqual({ du: '2026-10-26', au: '2026-12-06' }))
    const dix7 = await screen.findByRole('gridcell', { name: 'Mardi 17 novembre · 3 tâches' })
    expect(dix7).toHaveAttribute('aria-current', 'date')
    expect(dix7).toHaveAttribute('aria-selected', 'true')
    fireEvent.click(screen.getByRole('gridcell', { name: /^Mercredi 18 novembre/ }))
    expect(screen.getByRole('gridcell', { name: /^Mercredi 18 novembre/ })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByTestId('adresse').textContent).toContain('jour=2026-11-18')
  })

  it('À venir : quatorze jours depuis aujourd\'hui, un jour vide le dit', async () => {
    monter('/taches/agenda?vue=a-venir')
    await waitFor(() => expect(dernierAppel()).toEqual({ du: '2026-11-17', au: '2026-11-30' }))
    const mardi = await screen.findByRole('region', { name: 'Mardi 17 novembre' })
    expect(within(mardi).getByRole('button', { name: 'Timbres' })).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Mercredi 18 novembre' })).getByText('Rien ce jour-là'))
      .toBeInTheDocument()
  })
})

describe('TCH104 — une lecture en échec ne vide rien', () => {
  it('l\'agenda reste, bandeau « Pas à jour · HH:MM » et Réessayer', async () => {
    monter()
    await screen.findByRole('button', { name: /Devis Settat/ })
    lireAgenda.mockRejectedValueOnce({ response: { status: 503, data: {} } })
    fireEvent.click(screen.getByRole('radio', { name: 'Semaine' }))
    const bandeau = await screen.findByText(/^Pas à jour · \d{2}:\d{2}/)
    expect(bandeau).toBeInTheDocument()
    expect(screen.getAllByText('Devis Settat').length).toBeGreaterThan(0)
    lireAgenda.mockResolvedValue({ data: agenda() })
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Réessayer' })) })
    await waitFor(() => expect(screen.queryByText(/^Pas à jour/)).toBeNull())
  })

  it('Raccord F2 — premier échec : « Pas à jour » seul et Réessayer, sans grille vide ni « Rien ce jour-là »', async () => {
    lireAgenda.mockRejectedValueOnce({ response: { status: 503, data: {} } })
    const { container } = monter()
    expect(await screen.findByText('Pas à jour')).toBeInTheDocument()
    expect(screen.queryByText(/n'a pas pu être lu/)).toBeNull()
    expect(screen.queryByText('Rien ce jour-là')).toBeNull()
    expect(grille(container)).toBeNull()
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Réessayer' })) })
    expect(await screen.findByRole('button', { name: /Devis Settat/ })).toBeInTheDocument()
  })
})

describe('Raccord F2 — Mes agendas', () => {
  it('aucun agenda externe : « Ajoute ton agenda pour voir tes rendez-vous ici. » [Mes agendas] mène aux réglages', async () => {
    listerAgendasExternes.mockResolvedValue({ data: { results: [] } })
    monter()
    const invitation = await screen.findByRole('region', { name: 'Mes agendas' })
    expect(invitation).toHaveTextContent('Ajoute ton agenda pour voir tes rendez-vous ici.')
    fireEvent.click(within(invitation).getByRole('button', { name: 'Mes agendas' }))
    expect(await screen.findByText('Réglages iPhone')).toBeInTheDocument()
    expect(screen.getByTestId('adresse')).toHaveTextContent('?etape=calendrier')
  })

  it('l\'action d\'écran « Mes agendas » mène à la même adresse', async () => {
    monter()
    await screen.findByRole('button', { name: /Devis Settat/ })
    await userEvent.click(screen.getByRole('button', { name: "Plus d'actions" }))
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Mes agendas' }))
    expect(await screen.findByText('Réglages iPhone')).toBeInTheDocument()
    expect(screen.getByTestId('adresse')).toHaveTextContent('?etape=calendrier')
  })

  it('un agenda déjà ajouté : pas d\'invitation', async () => {
    listerAgendasExternes.mockResolvedValue({ data: exempleContrat('taches', 'agendas_externes') })
    monter()
    await screen.findByRole('button', { name: /Devis Settat/ })
    await waitFor(() => expect(listerAgendasExternes).toHaveBeenCalled())
    expect(screen.queryByRole('region', { name: 'Mes agendas' })).toBeNull()
  })
})
