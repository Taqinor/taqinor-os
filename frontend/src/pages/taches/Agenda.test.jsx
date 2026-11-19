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
    // R2-112 — aucune phrase qui ressemble à un lien sans en être un : l'agenda ne sert pas d'adresse, la phrase est retirée
    expect(screen.getByText('Réunion banque · 11:00–12:00 · Microsoft 365')).toBeInTheDocument()
    expect(screen.queryByText(/Ouvrir dans ton agenda/)).toBeNull()
  })

  it('R2-112 — l\'agenda fournit une adresse : « Ouvrir dans ton agenda d\'origine » est un VRAI lien (sûr, nouvel onglet)', async () => {
    const d = agenda()
    d.jours[0].externes[0].url = 'https://outlook.office365.com/owa/?itemid=abc'
    d.jours[0].externes.push({ cle: '2-b', agenda_id: 2, agenda: 'Microsoft 365', titre: 'Appel piégé',
      debut: '2026-11-17T15:00:00+01:00', fin: '2026-11-17T16:00:00+01:00', journee_entiere: false, url: 'javascript:alert(1)' })
    lireAgenda.mockResolvedValue({ data: d })
    monter()
    fireEvent.click(await screen.findByRole('button', { name: 'Réunion banque · 11:00–12:00 · Microsoft 365' }))
    const lien = screen.getByRole('link', { name: "Ouvrir dans ton agenda d'origine" })
    expect(lien).toHaveAttribute('href', 'https://outlook.office365.com/owa/?itemid=abc')
    expect(lien).toHaveAttribute('target', '_blank')
    expect(lien).toHaveAttribute('rel', expect.stringContaining('noopener'))
    // une adresse qui n'est pas http(s) n'est jamais un lien
    fireEvent.click(screen.getByRole('button', { name: 'Appel piégé · 15:00–16:00 · Microsoft 365' }))
    expect(screen.getByText('Appel piégé · 15:00–16:00 · Microsoft 365')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: "Ouvrir dans ton agenda d'origine" })).toBeNull()
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
    expect(container.querySelector('.ag-sem .ag-sj[aria-current="date"] .ag-sj-tete')).toHaveTextContent('2 tâches · 1 h 15 sur 3 h')
  })

  it('F2 acceptation + R2-102 — Semaine sur iPhone : un jour passé dit « {n} faites » = les tâches FINIES ce jour-là, servies par `faites_nb` (maquette agenda-semaine.html, `ag-sj passe`)', async () => {
    const d = agenda()
    const base = d.jours[0].sans_heure[0]
    d.jours.unshift({
      ...d.jours[0], jour: '2026-11-16', toute_la_journee: [], echeances: [], externes: [], blocs: [], faites_nb: 4,
      sans_heure: [
        { ...base, id: 901, titre: 'Faite lundi', statut: 'fait', jour_prevu: '2026-11-16' },
        { ...base, id: 902, titre: 'Encore une faite', statut: 'fait', jour_prevu: '2026-11-16' },
        { ...base, id: 903, titre: 'Restée à faire', statut: 'a_faire', jour_prevu: '2026-11-16' },
      ],
    })
    lireAgenda.mockResolvedValue({ data: d })
    const { container } = monter('/taches/agenda?vue=semaine')
    await waitFor(() => expect(container.querySelector('.ag-sem .ag-sj.passe')).not.toBeNull())
    // 2 lignes prévues ce jour-là sont faites, mais 4 tâches y ont été FINIES : le nombre est celui du serveur (règle C-12)
    expect(container.querySelector('.ag-sem .ag-sj.passe .ag-sj-tete')).toHaveTextContent(/^4 faites$/)
  })

  it('R3-125 — un week-end où il a travaillé le dit : « 7 faites · jour non travaillé » (et sa colonne de bureau reste entière)', async () => {
    const d = agenda()
    const vide = { toute_la_journee: [], sans_heure: [], blocs: [], echeances: [], externes: [] }
    d.jours.unshift({ ...vide, jour: '2026-11-14', ouvre: false, ferie: false, faites_nb: 7 })
    d.jours.unshift({ ...vide, jour: '2026-11-15', ouvre: false, ferie: false, faites_nb: 0 })
    lireAgenda.mockResolvedValue({ data: d })
    const { container } = monter('/taches/agenda?vue=semaine&jour=2026-11-14')
    await waitFor(() => expect(container.querySelector('.ag-sem .ag-sj')).not.toBeNull())
    const tetes = [...container.querySelectorAll('.ag-sem .ag-sj .ag-sj-tete')].map((e) => e.textContent)
    expect(tetes).toContain('7 faites · jour non travaillé')
    expect(tetes).toContain('Jour non travaillé') // dim. 15 : rien fait, le libellé seul
  })

  it('R3-125 — pendant la lecture d\'une autre semaine, un jour passé non encore servi n\'est pas « Passé » : un squelette', async () => {
    let servir
    lireAgenda.mockReturnValueOnce(Promise.resolve({ data: agenda() })).mockReturnValueOnce(new Promise((r) => { servir = r }))
    const { container } = monter('/taches/agenda?vue=semaine')
    await waitFor(() => expect(container.querySelector('.ag-sem .ag-sj')).not.toBeNull())
    fireEvent.click(screen.getByRole('button', { name: 'Semaine précédente' }))
    await waitFor(() => expect(lireAgenda).toHaveBeenCalledTimes(2))
    expect(screen.queryByText('Passé')).toBeNull()
    expect(container.querySelector('.ag-sj-squelette')).not.toBeNull()
    servir({ data: agenda() })
  })

  it('R2-102 — un jour passé sans `faites_nb` servi ne devine rien : « Passé » seul', async () => {
    const d = agenda()
    d.jours.unshift({ ...d.jours[0], jour: '2026-11-16', toute_la_journee: [], echeances: [], externes: [], blocs: [],
      sans_heure: [{ ...d.jours[0].sans_heure[0], id: 901, statut: 'fait' }] })
    delete d.jours[0].faites_nb
    lireAgenda.mockResolvedValue({ data: d })
    const { container } = monter('/taches/agenda?vue=semaine')
    await waitFor(() => expect(container.querySelector('.ag-sem .ag-sj.passe')).not.toBeNull())
    expect(container.querySelector('.ag-sem .ag-sj.passe .ag-sj-tete')).toHaveTextContent(/^Passé$/)
  })

  it('F2 acceptation (P139.1) — sans capacité servie, l\'en-tête ne dit que le nombre (jamais une capacité devinée)', async () => {
    const sans = agenda()
    delete sans.capacite
    lireAgenda.mockResolvedValue({ data: sans })
    const { container } = monter('/taches/agenda?vue=semaine')
    await waitFor(() => expect(container.querySelector('.ag-sem .ag-sj[aria-current="date"]')).not.toBeNull())
    expect(container.querySelector('.ag-sem .ag-sj[aria-current="date"] .ag-sj-tete').textContent).not.toMatch(/pour/)
  })

  it('Passe visuelle n° 34 — Semaine : « Planifier ma semaine » en pied avec « À placer · n » (iPhone) et au bas du volet À placer (bureau), plus en haut', async () => {
    const { container } = monter('/taches/agenda?vue=semaine')
    await waitFor(() => expect(container.querySelector('.ag-sem')).not.toBeNull())
    expect(within(container.querySelector('.ag-vues')).queryByRole('button', { name: 'Planifier ma semaine' })).toBeNull()
    // contrat : a_placer (1) + Mes projets (1) = 2, le même nombre que le volet
    const barre = container.querySelector('.ag-barre')
    expect(barre).toHaveClass('mobile-seul')
    expect(barre.querySelector('.ag-barre-titre')).toHaveTextContent('À placer · 2')
    const volet = screen.getByRole('complementary', { name: 'À placer' })
    expect(within(volet).getByRole('heading', { name: 'À placer · 2' })).toBeInTheDocument()
    expect(volet.querySelector('.ag-aside-action')).toContainElement(within(volet).getByRole('button', { name: 'Planifier ma semaine' }))
    fireEvent.click(within(barre).getByRole('button', { name: 'Planifier ma semaine' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Planifier ma semaine' })).toBeInTheDocument()
    expect(screen.getByTestId('adresse').textContent).toContain('placer=1')
  })

  it('Passe visuelle n° 8 — Semaine sur iPhone : la visite de l\'ERP (Toute la journée) ouvre la liste du jour, sans heure, hors du compte', async () => {
    const { container } = monter('/taches/agenda?vue=semaine')
    await waitFor(() => expect(container.querySelector('.ag-sem .ag-sj[aria-current="date"]')).not.toBeNull())
    const mardi = container.querySelector('.ag-sem .ag-sj[aria-current="date"]')
    const lignes = mardi.querySelectorAll('.ag-sj-l')
    expect(lignes[0]).toHaveClass('erp')
    expect(lignes[0].querySelector('.t')).toHaveTextContent('Visite — Karim Benali')
    expect(lignes[0].querySelector('.h')).toHaveTextContent('')
    expect(lignes[0].querySelector('svg')).not.toBeNull()
    expect(lignes[1].querySelector('.t')).toHaveTextContent('Devis Settat')
    expect(mardi.querySelector('.ag-sj-tete')).toHaveTextContent('2 tâches · 1 h 15 sur 3 h')
  })

  it('Passe visuelle n° 59 — Semaine sur iPhone : un jour passé tient une ligne (ses faites), un jour chargé trois, le reste en « +N »', async () => {
    const d = agenda()
    const base = d.jours[0].sans_heure[0]
    const ligne = (id, titre, statut = 'a_faire') => ({ ...base, id, titre, statut })
    d.jours.unshift({
      ...d.jours[0], jour: '2026-11-16', toute_la_journee: [], echeances: [], externes: [], blocs: [],
      sans_heure: [ligne(901, 'Faite A', 'fait'), ligne(902, 'Faite B', 'fait'), ligne(903, 'Faite C', 'fait'),
        ligne(906, 'Restée à faire')],
    })
    d.jours[1].sans_heure.push(ligne(904, 'En plus 1'), ligne(905, 'En plus 2'))
    lireAgenda.mockResolvedValue({ data: d })
    const { container } = monter('/taches/agenda?vue=semaine')
    await waitFor(() => expect(container.querySelector('.ag-sem .ag-sj.passe')).not.toBeNull())
    const lundi = container.querySelector('.ag-sem .ag-sj.passe')
    expect(lundi.querySelectorAll('.ag-sj-l')).toHaveLength(1)
    expect(lundi.querySelector('.ag-sj-l .t')).toHaveTextContent('Faite A')
    expect(lundi.querySelector('.ag-sj-l .plus')).toHaveTextContent('+2')
    // mar. 17 : visite + Devis Settat + Réunion banque (R2-100) + Timbres + 2 = 6 lignes → 3 montrées, « +3 » sur la dernière
    const mardi = container.querySelector('.ag-sem .ag-sj[aria-current="date"]')
    const lignes = mardi.querySelectorAll('.ag-sj-l')
    expect(lignes).toHaveLength(3)
    expect(lignes[2].querySelector('.plus')).toHaveTextContent('+3')
    expect(lignes[0].querySelector('.plus')).toBeNull()
  })

  it('R2-100 — Semaine sur iPhone : le rendez-vous de l\'agenda externe est dans son jour (heure + titre), et son temps est retranché', async () => {
    const d = agenda()
    d.jours.push({
      ...d.jours[0], jour: '2026-11-18', toute_la_journee: [], sans_heure: [], blocs: [], echeances: [],
      externes: [{ cle: '2-b', agenda_id: 2, agenda: 'Microsoft 365', titre: 'Rendez-vous banque',
        debut: '2026-11-18T14:30:00+01:00', fin: '2026-11-18T16:00:00+01:00', journee_entiere: false }],
      rendez_vous_minutes: 90,
    })
    lireAgenda.mockResolvedValue({ data: d })
    const { container } = monter('/taches/agenda?vue=semaine')
    await waitFor(() => expect(container.querySelector('.ag-sem .ag-sj[aria-current="date"]')).not.toBeNull())
    const mercredi = [...container.querySelectorAll('.ag-sem .ag-sj')].find((b) => b.textContent.startsWith('mer.18'))
    const rdv = mercredi.querySelector('.ag-sj-l.ext')
    expect(rdv.querySelector('.h')).toHaveTextContent('14:30')
    expect(rdv.querySelector('.t')).toHaveTextContent('Rendez-vous banque')
    // 240 min de capacité − 90 min de rendez-vous servis = 2 h 30 de temps libre
    expect(mercredi.querySelector('.ag-sj-tete')).toHaveTextContent('Libre · 2 h 30')
    // et le rendez-vous de mardi (11:00) est dans sa ligne, avant les tâches sans heure
    const mardi = container.querySelector('.ag-sem .ag-sj[aria-current="date"]')
    expect(mardi.querySelector('.ag-sj-l.ext .t')).toHaveTextContent('Réunion banque')
  })

  const semaineAvecRepos = () => {
    const d = agenda()
    const vide = { toute_la_journee: [], sans_heure: [], blocs: [], echeances: [], externes: [] }
    d.jours.push({ ...vide, jour: '2026-11-21', ouvre: false, ferie: false }, { ...vide, jour: '2026-11-22', ouvre: false, ferie: false })
    return d
  }

  it('Passe visuelle n° 36 — Semaine au bureau : « Toute la journée » est une rangée DE la grille, sous les jours, jours non travaillés étroits', async () => {
    lireAgenda.mockResolvedValue({ data: semaineAvecRepos() })
    const { container } = monter('/taches/agenda?vue=semaine')
    await waitFor(() => expect(grille(container)).not.toBeNull())
    const tete = grille(container).querySelector('.semaine-tete')
    const journee = grille(container).querySelector('.ag-semtj')
    expect(journee).not.toBeNull()
    expect(tete.nextElementSibling).toBe(journee)
    expect(within(journee).getByRole('link', { name: /Visite — Karim Benali/ })).toBeInTheDocument()
    // une cellule par jour sous chaque tête, gouttière comprise : sam./dim. restent dans leur colonne
    expect(journee.children).toHaveLength(8)
    expect(grille(container).style.gridTemplateColumns)
      .toBe('56px minmax(120px, 1fr) minmax(120px, 1fr) minmax(120px, 1fr) minmax(120px, 1fr) minmax(120px, 1fr) minmax(56px, 0.5fr) minmax(56px, 0.5fr)')
  })

  it('R2-108 — Semaine au bureau : un week-end qui porte une tâche garde une colonne entière (étroit seulement s\'il est vide)', async () => {
    const d = semaineAvecRepos()
    const samedi = d.jours.find((j) => j.jour === '2026-11-21')
    samedi.sans_heure = [{ ...d.jours[0].sans_heure[0], id: 601, titre: 'Mise en service', jour_prevu: '2026-11-21' }]
    samedi.blocs = [{ ...d.jours[0].blocs[0], id: 602, titre: 'Réceptionner les panneaux', jour_prevu: '2026-11-21', heure_debut: '09:00' }]
    lireAgenda.mockResolvedValue({ data: d })
    const { container } = monter('/taches/agenda?vue=semaine')
    await waitFor(() => expect(grille(container)).not.toBeNull())
    expect(grille(container).style.gridTemplateColumns)
      .toBe('56px minmax(120px, 1fr) minmax(120px, 1fr) minmax(120px, 1fr) minmax(120px, 1fr) minmax(120px, 1fr) minmax(120px, 1fr) minmax(56px, 0.5fr)')
  })

  it('R3-120 — Semaine au bureau : deux tâches qui se chevauchent se rangent côte à côte en voies égales, sans se recouvrir', async () => {
    const d = semaineAvecRepos()
    const devis = d.jours[0].blocs[0]
    d.jours[0].blocs.push({ ...devis, id: 77, titre: 'Appel fournisseur', heure_debut: '10:30', estimation_minutes: 30 })
    lireAgenda.mockResolvedValue({ data: d })
    const { container } = monter('/taches/agenda?vue=semaine')
    await waitFor(() => expect(grille(container)).not.toBeNull())
    const blocDevis = grille(container).querySelector('[data-bloc="20"]')
    const blocAppel = grille(container).querySelector('[data-bloc="77"]')
    expect(blocDevis).toHaveClass('h1')
    // voie 1 à gauche, voie 2 à droite : la même largeur, jamais l'une SUR l'autre (plus de cascade décalée de 10 %)
    expect(blocDevis.style.right).toBe('calc(50% + 1px)')
    expect(blocAppel.style.left).toBe('calc(50% + 1px)')
    expect(blocAppel.style.right).toBe('')
    expect(blocAppel).not.toHaveClass('g2')
    expect(blocDevis).toHaveClass('en-voies')
    expect(blocAppel).toHaveClass('en-voies')
  })

  it('R3-120 — Semaine au bureau : une tâche seule garde toute la colonne', async () => {
    lireAgenda.mockResolvedValue({ data: semaineAvecRepos() })
    const { container } = monter('/taches/agenda?vue=semaine')
    await waitFor(() => expect(grille(container)).not.toBeNull())
    const seul = grille(container).querySelector('[data-bloc="20"]')
    expect(seul.style.left).toBe('')
    expect(seul.style.right).toBe('')
    expect(seul).not.toHaveClass('en-voies')
  })

  it('R3-120 — Semaine au bureau : « À placer (n) » est un bouton qui ouvre le panneau, la grille garde toute la largeur', async () => {
    const { container } = monter('/taches/agenda?vue=semaine')
    await waitFor(() => expect(grille(container)).not.toBeNull())
    const corps = container.querySelector('.ag-corps-semaine')
    // le bouton est dans la barre du haut (vues · navigation · À placer), le panneau est dans le corps de la Semaine
    const bouton = screen.getByRole('button', { name: 'À placer (2)' })
    expect(within(container.querySelector('.ag-barre-haute')).getByRole('button', { name: 'À placer (2)' })).toBe(bouton)
    expect(bouton).toHaveAttribute('aria-controls', corps.querySelector('.ag-aside').id)
    expect(bouton).toHaveAttribute('aria-expanded', 'false')
    expect(corps).toHaveAttribute('data-volet', 'ferme')
    fireEvent.click(bouton)
    expect(screen.getByRole('button', { name: 'À placer (2)' })).toHaveAttribute('aria-expanded', 'true')
    expect(corps).toHaveAttribute('data-volet', 'ouvert')
    // choisir une tâche au toucher referme le panneau : la grille se montre en entier pour y poser la tâche
    fireEvent.click(within(corps.querySelector('.ag-aside')).getByRole('button', { name: /Site web/ }))
    expect(corps).toHaveAttribute('data-volet', 'ferme')
    // Échap le referme aussi
    fireEvent.click(screen.getByRole('button', { name: 'À placer (2)' }))
    expect(corps).toHaveAttribute('data-volet', 'ouvert')
    fireEvent.keyDown(corps, { key: 'Escape' })
    expect(corps).toHaveAttribute('data-volet', 'ferme')
    expect(screen.getByRole('button', { name: 'À placer (2)' })).toHaveFocus()
  })

  it('R3-121 — Semaine au bureau : « Toute la journée » porte aussi les tâches sans heure et les échéances, « +n » ouvre le jour', async () => {
    const d = semaineAvecRepos()
    const base = d.jours[0].sans_heure[0]
    const samedi = d.jours.find((j) => j.jour === '2026-11-21')
    samedi.sans_heure = [{ ...base, id: 601, titre: 'Mise en service', jour_prevu: '2026-11-21', jalon: true }]
    samedi.echeances = [{ ...base, id: 603, titre: 'Livrer le rapport', jour_prevu: '2026-11-20', echeance: '2026-11-21' }]
    const dimanche = d.jours.find((j) => j.jour === '2026-11-22')
    dimanche.sans_heure = [{ ...base, id: 611, titre: 'Ranger A', jour_prevu: '2026-11-22' }, { ...base, id: 612, titre: 'Ranger B', jour_prevu: '2026-11-22' }]
    dimanche.echeances = [{ ...base, id: 613, titre: 'Payer C', jour_prevu: '2026-11-20', echeance: '2026-11-22' }]
    lireAgenda.mockResolvedValue({ data: d })
    const { container } = monter('/taches/agenda?vue=semaine')
    await waitFor(() => expect(grille(container)).not.toBeNull())
    const cases = [...grille(container).querySelector('.ag-semtj').children]
    // samedi : la tâche sans heure et l'échéance (puce « · échéance »), le jalon n'est pas perdu
    expect(within(cases[6]).getByRole('button', { name: 'Mise en service' })).toBeInTheDocument()
    expect(within(cases[6]).getByRole('button', { name: 'Livrer le rapport · échéance' })).toBeInTheDocument()
    // dimanche : trois choses, deux puces, « +1 » qui mène au jour
    expect(within(cases[7]).getAllByRole('button')).toHaveLength(3)
    fireEvent.click(within(cases[7]).getByRole('button', { name: /^\+1 de plus/ }))
    expect(screen.getByTestId('adresse').textContent).toContain('vue=jour')
    expect(screen.getByTestId('adresse').textContent).toContain('jour=2026-11-22')
  })

  it('R3-121 — Semaine au bureau : une échéance dont la tâche est déjà posée ce jour-là n\'est pas écrite deux fois', async () => {
    const d = semaineAvecRepos()
    const devis = d.jours[0].blocs[0]
    d.jours[0].echeances = [{ ...devis }]
    lireAgenda.mockResolvedValue({ data: d })
    const { container } = monter('/taches/agenda?vue=semaine')
    await waitFor(() => expect(grille(container)).not.toBeNull())
    const mardi = [...grille(container).querySelector('.ag-semtj').children][2]
    expect(within(mardi).queryByRole('button', { name: /Devis Settat/ })).toBeNull()
  })

  it('R3-121 — Semaine au bureau : l\'en-tête d\'un jour passé dit « {n} faites » (nombre servi), pas celui d\'aujourd\'hui ni d\'un jour sans nombre', async () => {
    const d = semaineAvecRepos()
    const vide = { toute_la_journee: [], sans_heure: [], blocs: [], echeances: [], externes: [] }
    d.jours.unshift({ ...vide, jour: '2026-11-16', ouvre: true, ferie: false, faites_nb: 3 })
    d.jours.push({ ...vide, jour: '2026-11-18', ouvre: true, ferie: false })
    lireAgenda.mockResolvedValue({ data: d })
    const { container } = monter('/taches/agenda?vue=semaine')
    await waitFor(() => expect(grille(container)).not.toBeNull())
    const tetes = [...grille(container).querySelectorAll('.semaine-tete > div')].slice(1)
    expect(tetes[0]).toHaveTextContent('lun. 16')
    expect(tetes[0].querySelector('.ag-faites')).toHaveTextContent('3 faites')
    expect(tetes[1].querySelector('.ag-faites')).toBeNull() // mar. 17 = aujourd'hui
    expect(tetes[2].querySelector('.ag-faites')).toBeNull() // mer. 18 : à venir
    expect(container.querySelectorAll('.semaine-tete .ag-faites')).toHaveLength(1)
  })

  it('R3-120 — Semaine au bureau : « Planifier ma semaine » reste dans la barre du haut quand le panneau « À placer » est replié', async () => {
    const { container } = monter('/taches/agenda?vue=semaine')
    await waitFor(() => expect(grille(container)).not.toBeNull())
    const barre = container.querySelector('.ag-barre-haute')
    fireEvent.click(within(barre).getByRole('button', { name: 'Planifier ma semaine' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Planifier ma semaine' })).toBeInTheDocument()
    expect(screen.getByTestId('adresse').textContent).toContain('placer=1')
  })

  it('R3-131 — Semaine : l\'heure courante est écrite UNE fois, dans la gouttière des heures (le Jour garde la sienne)', async () => {
    const { container } = monter('/taches/agenda?vue=semaine')
    await waitFor(() => expect(grille(container)).not.toBeNull())
    const gouttiere = grille(container).querySelectorAll('.agenda-heures .maintenant-gouttiere')
    expect(gouttiere).toHaveLength(1)
    expect(gouttiere[0]).toHaveTextContent('09:41')
  })

  it('R3-132 — iPhone : une tâche de « À placer » choisie, le bandeau COLLANT de la grille dit « Pose « … » : touche un créneau » et offre Annuler ; toucher un bloc posé le DÉPLACE', async () => {
    const { container } = monter()
    await screen.findByRole('button', { name: /Devis Settat/ })
    expect(container.querySelector('.ag-consigne-pose')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /Site web/ }))
    const bandeau = container.querySelector('.ag-principal > .ag-consigne-pose')
    expect(bandeau).toHaveTextContent('Pose « Site web » : touche un créneau')
    // en mode « placer », un bloc déjà posé se DÉPLACE au toucher (son nom le dit) au lieu d'ouvrir sa fiche
    fireEvent.click(within(grille(container)).getByRole('button', { name: /^Déplacer Devis Settat · 10:00 – 11:00$/ }))
    expect(container.querySelector('.ag-principal > .ag-consigne-pose')).toBeNull()
    expect(screen.getByText('Touche un créneau pour déplacer Devis Settat')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Annuler le déplacement' }))
    // « Annuler » du bandeau de pose : la tâche n'est plus choisie
    fireEvent.click(screen.getByRole('button', { name: /Site web/ }))
    fireEvent.click(within(container.querySelector('.ag-principal > .ag-consigne-pose')).getByRole('button', { name: 'Annuler' }))
    expect(container.querySelector('.ag-consigne-pose')).toBeNull()
    expect(screen.getByRole('button', { name: /Site web/ })).toHaveAttribute('aria-pressed', 'false')
    // hors du mode « placer », le bloc ouvre toujours sa fiche (nom inchangé)
    expect(within(grille(container)).getByRole('button', { name: /^Devis Settat/ })).not.toHaveAccessibleName(/Déplacer/)
  })

  it('R3-133 — la bulle d\'un rendez-vous près du bas de l\'écran se RETOURNE vers le haut ; ailleurs elle reste sous le bloc', async () => {
    const mesure = vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect')
    const rect = (top, bottom) => ({ top, bottom, height: bottom - top, left: 0, right: 0, width: 0, x: 0, y: top, toJSON: () => ({}) })
    try {
      mesure.mockImplementation(function mesureBulle() { return this.classList.contains('ag-bulle') ? rect(window.innerHeight - 20, window.innerHeight + 60) : rect(0, 0) })
      const { container } = monter()
      fireEvent.click(await screen.findByRole('button', { name: /^Réunion banque/ }))
      expect(container.querySelector('.ag-bulle')).toHaveClass('vers-haut')
      mesure.mockImplementation(function mesureBulle() { return this.classList.contains('ag-bulle') ? rect(100, 180) : rect(0, 0) })
      fireEvent.click(screen.getByRole('button', { name: /^Réunion banque/ })) // referme
      fireEvent.click(screen.getByRole('button', { name: /^Réunion banque/ })) // rouvre : mesure au milieu de l'écran
      expect(container.querySelector('.ag-bulle')).not.toHaveClass('vers-haut')
    } finally { mesure.mockRestore() }
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
    const dix7 = await screen.findByRole('gridcell', { name: 'Mardi 17 novembre · 2 tâches · échéance' })
    expect(dix7).toHaveAttribute('aria-current', 'date')
    expect(dix7).toHaveAttribute('aria-selected', 'true')
    fireEvent.click(screen.getByRole('gridcell', { name: /^Mercredi 18 novembre/ }))
    expect(screen.getByRole('gridcell', { name: /^Mercredi 18 novembre/ })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByTestId('adresse').textContent).toContain('jour=2026-11-18')
  })

  it('Passe visuelle n° 58 (mineur) — Mois : « Novembre 2026 » et la charge du jour choisi à droite de son titre', async () => {
    const { container } = monter('/taches/agenda?vue=mois')
    await screen.findByRole('gridcell', { name: 'Mardi 17 novembre · 2 tâches · échéance' })
    expect(container.querySelector('.ag-nav b')).toHaveTextContent(/^Novembre 2026$/)
    const tete = container.querySelector('.ag-jour-tete')
    expect(tete.querySelector('b')).toHaveTextContent('Mardi 17 novembre')
    expect(tete.querySelector('.ag-jour-charge')).toHaveTextContent('2 tâches · 1 h 15 sur 3 h')
  })

  it('R2-109 — Mois : les jours non travaillés sont teintés sur TOUTES les semaines, même ceux que la lecture ne sert pas', async () => {
    const d = agenda()
    const vide = { toute_la_journee: [], sans_heure: [], blocs: [], echeances: [], externes: [], ouvre: false, ferie: false }
    d.jours.push({ ...vide, jour: '2026-11-21' }, { ...vide, jour: '2026-11-22' }) // seul ce week-end est servi
    lireAgenda.mockResolvedValue({ data: d })
    monter('/taches/agenda?vue=mois')
    const cellule = async (nom) => (await screen.findByRole('gridcell', { name: new RegExp(`^${nom}`) }))
    expect(await cellule('Samedi 28 novembre')).toHaveClass('repos')
    expect(await cellule('Dimanche 29 novembre')).toHaveClass('repos')
    expect(await cellule('Samedi 7 novembre')).toHaveClass('repos')
    expect(await cellule('Mercredi 25 novembre')).not.toHaveClass('repos')
  })

  it('R2-109 — Mois au bureau : les titres des tâches dans la case du jour (3 au plus, puis « +n »), les points restent pour l\'iPhone', async () => {
    const d = agenda()
    const base = d.jours[0].sans_heure[0]
    d.jours[0].sans_heure.push({ ...base, id: 801, titre: 'Quatrième' }, { ...base, id: 802, titre: 'Cinquième' })
    lireAgenda.mockResolvedValue({ data: d })
    monter('/taches/agenda?vue=mois')
    const mardi = await screen.findByRole('gridcell', { name: /^Mardi 17 novembre/ })
    const titres = mardi.querySelector('.ag-mj-titres')
    expect(titres.querySelectorAll('.t')).toHaveLength(3)
    expect(titres.querySelector('.plus')).toHaveAttribute('data-texte', '+1') // 4 tâches PRÉVUES ce jour-là (bloc, trois sans heure) : 3 montrées
    expect(titres.querySelector('.t')).toHaveAttribute('data-texte', 'Devis Settat')
    expect(mardi.querySelector('.pts')).not.toBeNull() // les points de l'iPhone sont toujours là
  })

  it('couture L7 — Mois : le seul TEXTE d\'une case est son numéro (axe 4.14 « label-content-name-mismatch ») ; titres, « +n » et « · échéance » sont dessinés', async () => {
    const d = agenda()
    const base = d.jours[0].sans_heure[0]
    d.jours[0].sans_heure.push({ ...base, id: 801, titre: 'Quatrième' }, { ...base, id: 802, titre: 'Cinquième' })
    d.jours[0].echeances = [{ ...base, id: 91, titre: 'Payer A' }]
    lireAgenda.mockResolvedValue({ data: d })
    monter('/taches/agenda?vue=mois')
    const mardi = await screen.findByRole('gridcell', { name: /^Mardi 17 novembre/ })
    // le nom lu (« Mardi 17 novembre · … ») contient le seul texte visible, « 17 » : la case se nomme à la voix
    expect(mardi.textContent.trim()).toBe('17')
  })

  it('R3-124 — Mois : une échéance est une MARQUE « · échéance », jamais un titre de plus (la tâche est écrite à son jour prévu)', async () => {
    const d = agenda()
    const base = d.jours[0].sans_heure[0]
    d.jours.push({ ...d.jours[0], jour: '2026-11-19', toute_la_journee: [], sans_heure: [], blocs: [], externes: [],
      echeances: [{ ...base, id: 90, titre: 'Livrer le rapport', jour_prevu: '2026-11-17', echeance: '2026-11-19' }] })
    lireAgenda.mockResolvedValue({ data: d })
    monter('/taches/agenda?vue=mois')
    // jeudi 19 : rien de prévu, une échéance → pas un titre, la marque seule ; l'iPhone : un anneau, pas un point de tâche
    const jeudi = await screen.findByRole('gridcell', { name: 'Jeudi 19 novembre · échéance' })
    expect(jeudi.querySelector('.ag-mj-titres .t')).toBeNull()
    expect(jeudi.querySelector('.ag-mj-ech')).toHaveAttribute('data-texte', '· échéance')
    expect(jeudi.querySelectorAll('.pts i:not(.ech)')).toHaveLength(0)
    expect(jeudi.querySelector('.pts i.ech')).not.toBeNull()
    // mardi 17 : « Dossier subvention » (échéance) n'est PAS un des titres ; sa marque suit les deux tâches prévues
    const mardi = screen.getByRole('gridcell', { name: /^Mardi 17 novembre/ })
    expect([...mardi.querySelectorAll('.ag-mj-titres .t')].map((e) => e.getAttribute('data-texte'))).toEqual(['Devis Settat', 'Timbres'])
    expect(mardi.querySelector('.ag-mj-ech')).toHaveAttribute('data-texte', '· échéance')
  })

  it('R3-124 — Mois : une échéance dont la tâche est déjà prévue ce jour-là n\'est pas marquée deux fois ; plusieurs se comptent', async () => {
    const d = agenda()
    const base = d.jours[0].sans_heure[0]
    d.jours[0].echeances = [{ ...d.jours[0].blocs[0] }, { ...base, id: 91, titre: 'Payer A' }, { ...base, id: 92, titre: 'Payer B' }]
    lireAgenda.mockResolvedValue({ data: d })
    monter('/taches/agenda?vue=mois')
    const mardi = await screen.findByRole('gridcell', { name: /^Mardi 17 novembre/ })
    expect(mardi).toHaveAccessibleName('Mardi 17 novembre · 2 tâches · 2 échéances')
    expect(mardi.querySelector('.ag-mj-ech')).toHaveAttribute('data-texte', '· 2 échéances')
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

describe('R2-107 — la grille : un seul arrêt de Tab, des flèches, aucun créneau sous un bloc', () => {
  const tabulables = (container) => [...container.querySelectorAll('.grille-agenda .ag-creneau-vide')].filter((b) => b.tabIndex === 0)

  it('vue Jour : UN créneau dans l\'ordre de Tab ; ↓ ↑ passent de créneau en créneau et le suivent', async () => {
    const { container } = monter()
    await screen.findByRole('button', { name: /Devis Settat/ })
    expect(tabulables(container)).toHaveLength(1)
    const premier = tabulables(container)[0]
    expect(premier).toHaveAccessibleName('Ajouter à 07:00')
    act(() => premier.focus())
    fireEvent.keyDown(premier, { key: 'ArrowDown' })
    expect(document.activeElement).toHaveAccessibleName('Ajouter à 07:30')
    await waitFor(() => expect(tabulables(container)).toHaveLength(1))
    expect(tabulables(container)[0]).toBe(document.activeElement) // l'arrêt de Tab suit le focus
    fireEvent.keyDown(document.activeElement, { key: 'ArrowUp' })
    expect(document.activeElement).toHaveAccessibleName('Ajouter à 07:00')
  })

  it('vue Semaine : ← → passent d\'un jour à l\'autre à la même heure', async () => {
    const { container } = monter('/taches/agenda?vue=semaine')
    await screen.findByRole('button', { name: 'Ajouter à 09:00 · mar. 17' })
    const mardi = screen.getByRole('button', { name: 'Ajouter à 09:00 · mar. 17' })
    act(() => mardi.focus())
    fireEvent.keyDown(mardi, { key: 'ArrowRight' })
    expect(document.activeElement).toHaveAccessibleName('Ajouter à 09:00 · mer. 18')
    fireEvent.keyDown(document.activeElement, { key: 'ArrowLeft' })
    expect(document.activeElement).toHaveAccessibleName('Ajouter à 09:00 · mar. 17')
    expect(tabulables(container)).toHaveLength(1)
  })

  it('aucun créneau sous un bloc : ni sous Devis Settat (10:00-11:00), ni sous la réunion (11:00-12:00)', async () => {
    monter()
    await screen.findByRole('button', { name: /Devis Settat/ })
    for (const heure of ['10:00', '10:30', '11:00', '11:30']) {
      expect(screen.queryByRole('button', { name: `Ajouter à ${heure}` }), heure).toBeNull()
    }
    expect(screen.getByRole('button', { name: 'Ajouter à 09:30' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ajouter à 12:00' })).toBeInTheDocument()
  })
})

describe('R2-110 — vue Jour au bureau : un en-tête court, la grille tôt', () => {
  it('Vues et navigation sont UNE barre (une ligne au bureau) ; la bande des 7 jours et « Sans heure » ont leur classe de bureau', async () => {
    const { container } = monter()
    await screen.findByRole('button', { name: /Devis Settat/ })
    const barre = container.querySelector('.ag-barre-haute')
    expect(barre).toContainElement(container.querySelector('.ag-vues'))
    expect(barre).toContainElement(container.querySelector('.ag-nav'))
    expect(container.querySelector('.bande-jours')).toHaveClass('ag-bande-jours')
    expect(container.querySelector('section[aria-label="Sans heure"]')).toHaveClass('ag-sans-heure')
  })

  it('un autre jour que le jour courant : ses tâches sans heure sont dans « À placer », groupe « Sans heure »', async () => {
    const d = agenda()
    const base = d.jours[0].sans_heure[0]
    d.jours.push({ ...d.jours[0], jour: '2026-11-18', toute_la_journee: [], blocs: [], echeances: [], externes: [],
      sans_heure: [{ ...base, id: 701, titre: 'Relire le bail', jour_prevu: '2026-11-18' }] })
    lireAgenda.mockResolvedValue({ data: d })
    monter('/taches/agenda?jour=2026-11-18')
    const volet = await screen.findByRole('complementary', { name: 'À placer' })
    const groupe = within(volet).getByRole('group', { name: 'Sans heure (1)' })
    expect(within(groupe).getByRole('button', { name: /Relire le bail/ })).toBeInTheDocument()
  })

  it("le jour courant n'ajoute pas ce groupe : ses tâches sans heure sont déjà dans « Aujourd'hui »", async () => {
    monter()
    const volet = await screen.findByRole('complementary', { name: 'À placer' })
    expect(within(volet).queryByRole('group', { name: /^Sans heure/ })).toBeNull()
  })
})

describe('R2-101 — À venir ne montre pas deux fois la même tâche', () => {
  it('le jour de son échéance, une tâche est une puce « · échéance » et rien d\'autre', async () => {
    monter('/taches/agenda?vue=a-venir')
    const mardi = await screen.findByRole('region', { name: 'Mardi 17 novembre' })
    expect(within(mardi).getAllByText(/Dossier subvention/)).toHaveLength(1)
    expect(within(mardi).getByText('Dossier subvention · échéance')).toBeInTheDocument()
    // les tâches du jour restent des lignes
    expect(within(mardi).getByRole('button', { name: 'Timbres' })).toBeInTheDocument()
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

  it('relecture adverse F4 n° 7 — « Planifier ma semaine » sans rien de lu : « Terminer » reste là et quitte le mode', async () => {
    lireAgenda.mockRejectedValueOnce({ response: { status: 503, data: {} } })
    monter('/taches/agenda?vue=semaine&placer=1')
    expect(await screen.findByText('Pas à jour')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'Planifier ma semaine' })).toBeInTheDocument()
    expect(screen.queryByRole('list', { name: 'Jours de la semaine' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Terminer', exact: true }))
    await waitFor(() => expect(screen.getByTestId('adresse').textContent).not.toContain('placer'))
    expect(screen.getByTestId('adresse').textContent).toContain('vue=semaine')
    expect(await screen.findByRole('heading', { level: 1, name: 'Agenda' })).toBeInTheDocument()
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
