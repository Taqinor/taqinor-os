import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { lireAgenda, planifierTache, trancherTache } from '../../../api/tachesApi'
import Agenda from '../../../pages/taches/Agenda'
import PlanifierSemaine from './PlanifierSemaine'

vi.mock('../../../api/tachesApi', async (importOriginal) => ({
  ...(await importOriginal()),
  lireAgenda: vi.fn(),
  planifierTache: vi.fn(),
  trancherTache: vi.fn(),
  annulerGeste: vi.fn(),
  modifierTache: vi.fn(),
  terminerTache: vi.fn(),
  rouvrirTache: vi.fn(),
}))

/* TCH106 — Planifier ma semaine (`?placer=1`) : sept lignes de jour + « À placer » avec « Mes
   projets » déplié ; toucher une tâche puis un jour la pose (`planifier/`, sans heure) SANS ouvrir
   de fiche ; ← → vont d'un jour à l'autre ; jour passé non posable ; **Terminer**. */

const AUJOURDHUI = '2026-11-17'
const agenda = () => structuredClone(exempleContrat('taches', 'agenda'))
const SEMAINE = ['2026-11-16', '2026-11-17', '2026-11-18', '2026-11-19', '2026-11-20', '2026-11-21', '2026-11-22']

/** R4-01 — la charge qu'`agenda/` sert à un jour à venir sans rien à faire (capacité 240, aucun rendez-vous). */
const LIBRE = { taches: 0, restantes_minutes: 0, sans_duree: 0, capacite_minutes: 240, rendez_vous_minutes: 0, disponible_minutes: 240, deborde_minutes: 0 }

function septJours() {
  const servis = Object.fromEntries(agenda().jours.map((j) => [j.jour, j]))
  return SEMAINE.map((iso) => servis[iso] ?? {
    jour: iso, ouvre: !['2026-11-21', '2026-11-22'].includes(iso), ferie: false,
    toute_la_journee: [], sans_heure: [], blocs: [], echeances: [], externes: [], faites_nb: 0, rendez_vous_minutes: 0,
    charge: iso < AUJOURDHUI ? null : { ...LIBRE },
  })
}

/** La semaine telle qu'`agenda/` la sert (sept jours, chacun sa charge). */
const semaineServie = () => ({ ...agenda(), jours: septJours() })

describe('TCH106 — PlanifierSemaine', () => {
  const monter = (props = {}) => render(
    <PlanifierSemaine jours={septJours()} aujourdhui={AUJOURDHUI} aPlacer={agenda().a_placer}
      mesProjets={agenda().mes_projets} onChoisir={vi.fn()} onPoser={vi.fn()} onOuvrirJour={vi.fn()}
      onTerminer={vi.fn()} {...props} />,
  )

  it('sept lignes : passé non posable, compte et durée du jour, non travaillé ; Mes projets déplié', () => {
    monter()
    const jours = screen.getByRole('list', { name: 'Jours de la semaine' })
    expect(within(jours).getAllByRole('listitem')).toHaveLength(7)
    expect(within(jours).getByRole('button', { name: 'lun. 16 · passé · 0 faite' })).toBeDisabled()
    expect(within(jours).getByRole('button', { name: 'mar. 17 · 2 tâches · 1 h 15 sur 3 h' })).toHaveAttribute('aria-current', 'date')
    expect(within(jours).getByRole('button', { name: 'dim. 22 · non travaillé' })).toBeEnabled()
    expect(screen.getByRole('button', { name: /Préparer formation/ })).toBeInTheDocument()
    expect(screen.getByText('● Équipe (1)')).toBeInTheDocument()
  })

  it('R3-122 — sept colonnes sur UNE rangée : un week-end vide est étroit (72 px), un week-end qui porte une tâche garde une colonne entière', () => {
    const colonne = (conteneur) => conteneur.querySelector('.ag-jours').style.getPropertyValue('--ag-jours-colonnes')
    const ouvre = 'minmax(0, 1fr)'
    const etroit = 'minmax(72px, 0.6fr)'
    const vide = monter()
    expect(colonne(vide.container)).toBe([ouvre, ouvre, ouvre, ouvre, ouvre, etroit, etroit].join(' '))
    vide.unmount()
    const jours = septJours()
    jours[5] = { ...jours[5], sans_heure: [{ ...agenda().jours[0].sans_heure[0], id: 701, titre: 'Mise en service', jour_prevu: '2026-11-21' }] }
    const charge = monter({ jours })
    expect(colonne(charge.container)).toBe([ouvre, ouvre, ouvre, ouvre, ouvre, ouvre, etroit].join(' '))
  })

  it('R3-134 — un jour sans rien de prévu dit « Libre · 4 h » (plus « 0 tâche · 0 min pour 4 h »), « sur » et non « pour » quand il y a des tâches', () => {
    monter({ capacite: 240 })
    expect(screen.getByRole('button', { name: 'jeu. 19 · Libre · 4 h' })).toBeEnabled()
    expect(screen.queryByText(/0 tâche · 0 min/)).toBeNull()
    expect(screen.getByRole('button', { name: 'mar. 17 · 2 tâches · 1 h 15 sur 3 h' })).toBeInTheDocument()
  })

  it('R3-134 — le rendez-vous qui réduit la capacité est écrit sous le jour ; le nom du jour ne change pas (il est la DESCRIPTION)', () => {
    monter({ capacite: 240 })
    // mar. 17 : 240 min de capacité − 60 min de rendez-vous servis (`rendez_vous_minutes`) = « sur 3 h »
    const mardi = screen.getByRole('button', { name: 'mar. 17 · 2 tâches · 1 h 15 sur 3 h' })
    const rdv = mardi.querySelector('.ag-pj-rdv')
    expect(rdv).toHaveTextContent('Rendez-vous : 1 h')
    expect(mardi).toHaveAttribute('aria-describedby', rdv.id)
    // un jour sans rendez-vous n'en dit rien
    expect(screen.getByRole('button', { name: 'jeu. 19 · Libre · 4 h' }).querySelector('.ag-pj-rdv')).toBeNull()
  })

  it('R2-102 — un jour passé dit les tâches FINIES ce jour-là (`faites_nb` servi), pas celles qui y étaient prévues', () => {
    const jours = septJours()
    jours[0] = { ...jours[0], faites_nb: 3 }
    monter({ jours })
    expect(screen.getByRole('button', { name: 'lun. 16 · passé · 3 faites' })).toBeDisabled()
  })

  it('R2-114 — un jour trop chargé le DIT sur sa ligne : « 7 h 30 sur 4 h · 3 h 30 de trop » (et pas seulement un segment orange)', () => {
    const jours = septJours()
    const base = agenda().jours[0].sans_heure[0]
    // R4-01 — la charge SERVIE dit le débordement (le serveur a compté la tâche de 7 h 30 contre 4 h)
    jours[4] = {
      ...jours[4], sans_heure: [{ ...base, id: 501, titre: 'Gros chantier', estimation_minutes: 450 }],
      charge: { ...LIBRE, taches: 1, restantes_minutes: 450, deborde_minutes: 210 },
    }
    monter({ jours, capacite: 240 })
    const vendredi = screen.getByRole('button', { name: 'ven. 20 · 1 tâche · 7 h 30 sur 4 h · 3 h 30 de trop' })
    expect(vendredi.querySelector('.n')).toHaveTextContent('3 h 30 de trop')
    // un jour dans la capacité ne dit rien de plus
    expect(screen.getByRole('button', { name: 'mar. 17 · 2 tâches · 1 h 15 sur 3 h' })).toBeInTheDocument()
  })

  it('une tâche choisie se pose sur le jour touché ; sans choix, le jour s\'ouvre', () => {
    const onPoser = vi.fn()
    const onOuvrirJour = vi.fn()
    const { rerender } = monter({ onPoser, onOuvrirJour })
    fireEvent.click(screen.getByRole('button', { name: 'jeu. 19 · Libre · 4 h' }))
    expect(onOuvrirJour).toHaveBeenCalledWith('2026-11-19')
    const formation = agenda().mes_projets[0].items[0]
    rerender(<PlanifierSemaine jours={septJours()} aujourdhui={AUJOURDHUI} aPlacer={agenda().a_placer}
      mesProjets={agenda().mes_projets} choisie={formation} onChoisir={vi.fn()} onPoser={onPoser}
      onOuvrirJour={onOuvrirJour} onTerminer={vi.fn()} />)
    expect(screen.getByRole('status')).toHaveTextContent('Touche un jour pour placer Préparer formation')
    fireEvent.click(screen.getByRole('button', { name: 'jeu. 19 · Libre · 4 h · placer Préparer formation' }))
    expect(onPoser).toHaveBeenCalledWith(formation, '2026-11-19')
  })

  it('R4-01 — « {n} tâches · {h} sur {cap} » est LA charge servie du jour (`jours[].charge`), jamais recomptée ; non servie : le nombre de tâches seul', () => {
    const jours = septJours()
    // le serveur dit 1 tâche de 2 h (une faite ou un « Ce soir » ne compte pas) : l'écran le croit, il ne refait pas la somme
    jours[1] = { ...jours[1], charge: { ...jours[1].charge, taches: 1, restantes_minutes: 120, disponible_minutes: 360 } }
    jours[3] = { ...jours[3], charge: undefined, sans_heure: [{ ...agenda().jours[0].sans_heure[0], id: 801, jour_prevu: '2026-11-19' }] }
    monter({ jours })
    const liste = screen.getByRole('list', { name: 'Jours de la semaine' })
    expect(within(liste).getByRole('button', { name: 'mar. 17 · 1 tâche · 2 h sur 6 h' }).querySelector('.ag-charge')).not.toBeNull()
    const jeudi = within(liste).getByRole('button', { name: 'jeu. 19 · 1 tâche' })
    expect(jeudi.querySelector('.ag-charge')).toBeNull()
  })

  it('Raccord F2 — chaque jour porte ses cartes (colonnes du bureau), décor muet : le nom du jour reste celui du bouton', () => {
    monter()
    const mardi = screen.getByRole('button', { name: 'mar. 17 · 2 tâches · 1 h 15 sur 3 h' })
    const cartes = mardi.querySelector('.ag-pj-cartes')
    expect(cartes).toHaveAttribute('aria-hidden', 'true')
    expect(cartes.querySelectorAll('.ag-carte')).toHaveLength(2)
    expect(screen.getByRole('button', { name: 'dim. 22 · non travaillé' }).closest('.ag-pj-place')).toHaveClass('repos')
  })

  it('R2-105 — iPhone : tâche choisie, la vue monte sur les jours ; posée ou annulée, elle revient sur le volet', () => {
    const defile = vi.fn()
    const avant = Element.prototype.scrollIntoView
    Element.prototype.scrollIntoView = defile
    try {
      const formation = agenda().mes_projets[0].items[0]
      const { rerender } = monter()
      expect(defile).not.toHaveBeenCalled()
      const avecChoix = (choisie) => (
        <PlanifierSemaine jours={septJours()} aujourdhui={AUJOURDHUI} aPlacer={agenda().a_placer}
          mesProjets={agenda().mes_projets} choisie={choisie} onChoisir={vi.fn()} onPoser={vi.fn()}
          onOuvrirJour={vi.fn()} onTerminer={vi.fn()} />)
      rerender(avecChoix(formation))
      expect(defile).toHaveBeenCalledTimes(1)
      expect(defile.mock.contexts[0]).toHaveClass('ag-jours')
      rerender(avecChoix(null))
      expect(defile).toHaveBeenCalledTimes(2)
      expect(defile.mock.contexts[1]).toHaveClass('ag-aside')
      rerender(avecChoix(null))
      expect(defile).toHaveBeenCalledTimes(2)
    } finally { Element.prototype.scrollIntoView = avant }
  })

  it("R2-105 — l'aide du volet dit « Touche une tâche, puis un jour. » sur iPhone", () => {
    const { container } = monter()
    expect(container.querySelector('.ag-aside-pied .mobile-seul')).toHaveTextContent('Touche une tâche, puis un jour.')
    expect(container.querySelector('.ag-aside-pied .bureau-seul')).toHaveTextContent('Glisse une tâche sur un jour')
  })

  it('tâche choisie : → et ← vont d\'un jour posable à l\'autre (le passé est sauté)', () => {
    monter({ choisie: agenda().mes_projets[0].items[0] })
    fireEvent.keyDown(window, { key: 'ArrowRight' })
    expect(document.activeElement).toHaveAccessibleName(/^mar\. 17/)
    fireEvent.keyDown(window, { key: 'ArrowRight' })
    expect(document.activeElement).toHaveAccessibleName(/^mer\. 18/)
    fireEvent.keyDown(window, { key: 'ArrowLeft' })
    expect(document.activeElement).toHaveAccessibleName(/^mar\. 17/)
  })
})

describe('TCH106 — Planifier ma semaine dans l\'Agenda (`?placer=1`)', () => {
  function Adresse() {
    return <output data-testid="adresse">{useLocation().search}</output>
  }
  const monter = () => render(
    <MemoryRouter initialEntries={['/taches/agenda?placer=1']}>
      <Routes>
        <Route path="/taches/agenda"
          element={<><Agenda aujourdhui={AUJOURDHUI} maintenant={new Date(2026, 10, 17, 9, 41)} /><Adresse /></>} />
      </Routes>
    </MemoryRouter>,
  )

  beforeEach(() => {
    lireAgenda.mockResolvedValue({ data: semaineServie() })
    planifierTache.mockImplementation((id, corps) => Promise.resolve({
      data: { tache: { ...agenda().mes_projets[0].items[0], ...corps, lock_version: 3 }, geste_id: 7 },
    }))
  })
  afterEach(() => { vi.clearAllMocks() })

  it('Passe visuelle n° 6 — pendant le chargement, aucun chiffre : ni « 0 tâche », ni « passé · 0 faite », ni « Tout est placé »', async () => {
    let servir
    lireAgenda.mockReturnValue(new Promise((resoudre) => { servir = resoudre }))
    monter()
    expect(await screen.findByRole('heading', { level: 1, name: 'Planifier ma semaine' })).toBeInTheDocument()
    await waitFor(() => expect(lireAgenda).toHaveBeenCalled())
    expect(screen.queryByRole('list', { name: 'Jours de la semaine' })).toBeNull()
    expect(screen.queryByText(/0 tâche|0 faite/)).toBeNull()
    expect(screen.queryByText('Tout est placé')).toBeNull()
    servir({ data: agenda() })
    expect(await screen.findByRole('button', { name: /^mar\. 17 · 2 tâches · 1 h 15/ })).toBeInTheDocument()
  })

  const monterLe = (url, aujourdhui, maintenant) => render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/taches/agenda"
          element={<><Agenda aujourdhui={aujourdhui} maintenant={maintenant} /><Adresse /></>} />
      </Routes>
    </MemoryRouter>,
  )
  const appel = () => lireAgenda.mock.calls.at(-1)[0]

  it('R2-103 — le vendredi, le mode s\'ouvre sur la semaine SUIVANTE (23 – 29 novembre), jamais la semaine qui finit', async () => {
    monterLe('/taches/agenda?vue=semaine&placer=1', '2026-11-20', new Date(2026, 10, 20, 10, 0))
    await waitFor(() => expect(lireAgenda).toHaveBeenCalled())
    expect(appel()).toEqual({ du: '2026-11-23', au: '2026-11-29', vue: 'semaine' })
    expect(await screen.findByText('23 – 29 nov.')).toBeInTheDocument()
    // les sept jours sont à venir : aucun « passé », tous posables
    expect(await screen.findByRole('button', { name: /^lun\. 23 · / })).toBeEnabled()
    expect(screen.queryByText(/passé/)).toBeNull()
  })

  it('R2-103 — le jeudi à partir de 15 h la semaine suivante, avant 15 h et du lundi au mercredi la semaine en cours', async () => {
    const cas = [['2026-11-19', new Date(2026, 10, 19, 15, 0), '2026-11-23'], ['2026-11-19', new Date(2026, 10, 19, 14, 59), '2026-11-16'],
      ['2026-11-16', new Date(2026, 10, 16, 18, 0), '2026-11-16'], ['2026-11-22', new Date(2026, 10, 22, 9, 0), '2026-11-23']]
    for (const [iso, horloge, du] of cas) {
      lireAgenda.mockClear()
      const { unmount } = monterLe('/taches/agenda?placer=1', iso, horloge)
      await waitFor(() => expect(lireAgenda).toHaveBeenCalled())
      expect(appel().du).toBe(du)
      unmount()
    }
  })

  it('R2-103 — ‹ › changent de semaine dans le mode ; un jour donné dans l\'adresse est respecté', async () => {
    monterLe('/taches/agenda?placer=1', '2026-11-20', new Date(2026, 10, 20, 10, 0))
    fireEvent.click(await screen.findByRole('button', { name: 'Semaine précédente' }))
    await waitFor(() => expect(appel().du).toBe('2026-11-16'))
    expect(await screen.findByRole('button', { name: /^lun\. 16 · passé/ })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Semaine suivante' }))
    fireEvent.click(screen.getByRole('button', { name: 'Semaine suivante' }))
    await waitFor(() => expect(appel().du).toBe('2026-11-30'))
    lireAgenda.mockClear()
    monterLe('/taches/agenda?placer=1&jour=2026-11-18', '2026-11-20', new Date(2026, 10, 20, 10, 0))
    await waitFor(() => expect(lireAgenda).toHaveBeenCalled())
    expect(appel().du).toBe('2026-11-16')
  })

  it('R2-103 — « Planifier ma semaine » est dans le ⋯ de l\'Agenda', async () => {
    monterLe('/taches/agenda', AUJOURDHUI, new Date(2026, 10, 17, 9, 41))
    await screen.findByRole('button', { name: /Devis Settat/ })
    fireEvent.pointerDown(screen.getByRole('button', { name: "Plus d'actions" }), { button: 0, ctrlKey: false })
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Planifier ma semaine' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Planifier ma semaine' })).toBeInTheDocument()
    expect(screen.getByTestId('adresse').textContent).toContain('placer=1')
  })

  it('Passe visuelle n° 37 — un mode (agenda-semaine-planifier.html) : pas de bande « Jour · Semaine · Mois », ni barre d\'ajout (R2-103 : seules les flèches ‹ › changent de semaine)', async () => {
    const { container } = monter()
    expect(await screen.findByRole('button', { name: /^mar\. 17 · 2 tâches/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Semaine précédente' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Semaine suivante' })).toBeInTheDocument()
    expect(container.querySelector('.ag-nav')).toBeNull()
    expect(container.querySelector('.saisie-bureau')).toBeNull()
    expect(container.querySelector('.ag-planifier-tete')).toContainElement(screen.getByRole('button', { name: 'Terminer' }))
  })

  it('R3-123 — la semaine est dite UNE fois, « ‹ 16 – 22 nov. › » sur une rangée, et pas de sur-titre qui la répète', async () => {
    const { container } = monter()
    expect(await screen.findByRole('button', { name: /^mar\. 17 · 2 tâches/ })).toBeInTheDocument()
    const nav = container.querySelector('.ag-plan-nav')
    expect([...nav.children].map((e) => e.getAttribute('aria-label') ?? e.textContent))
      .toEqual(['Semaine précédente', '16 – 22 nov.', 'Semaine suivante'])
    expect(screen.queryByText('16 – 22 novembre')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Semaine suivante' }))
    expect(await screen.findByText('23 – 29 nov.')).toBeInTheDocument()
    // une semaine à cheval sur deux mois dit les deux
    fireEvent.click(screen.getByRole('button', { name: 'Semaine suivante' }))
    expect(await screen.findByText('30 nov. – 6 déc.')).toBeInTheDocument()
  })

  it('R3-123 — iPhone : Planifier ma semaine est un écran ENFANT de l\'Agenda (« ‹ Agenda » remplace ☰) ; au bureau rien de tel', async () => {
    const matchMedia = window.matchMedia
    window.matchMedia = (requete) => ({
      matches: requete.includes('max-width: 767px'), media: requete, addEventListener: () => {}, removeEventListener: () => {},
      addListener: () => {}, removeListener: () => {},
    })
    try {
      const { container, unmount } = monter()
      await screen.findByRole('button', { name: /^mar\. 17 · 2 tâches/ })
      const retour = container.querySelector('.entete-retour')
      expect(retour).toHaveTextContent('Agenda')
      fireEvent.click(retour)
      expect(await screen.findByRole('heading', { level: 1, name: 'Agenda' })).toBeInTheDocument()
      expect(screen.getByTestId('adresse').textContent).not.toContain('placer=')
      unmount()
    } finally { window.matchMedia = matchMedia }
    const bureau = monter()
    await screen.findByRole('button', { name: /^mar\. 17 · 2 tâches/ })
    expect(bureau.container.querySelector('.entete-retour')).toBeNull()
  })

  it('R2-106 — poser sur un jour une tâche « À revoir » (reportée 3 fois) la DÉCIDE : `trancher/` avec le jour, jamais `planifier/`', async () => {
    trancherTache.mockResolvedValue({ data: { tache: { ...agenda().a_placer[0], jour_prevu: '2026-11-19', lock_version: 7 }, geste_id: 8 } })
    monter()
    expect(await screen.findByRole('heading', { level: 1, name: 'Planifier ma semaine' })).toBeInTheDocument()
    fireEvent.click(await screen.findByRole('button', { name: /Site web/ }))
    fireEvent.click(screen.getByRole('button', { name: /^jeu\. 19 · .* · placer Site web$/ }))
    await waitFor(() => expect(trancherTache).toHaveBeenCalledWith(50, { choix: 'jour', jour: '2026-11-19' }))
    expect(planifierTache).not.toHaveBeenCalled()
    // la tâche sort d'« À revoir » ET prend sa place dans le jour
    expect(await screen.findByRole('button', { name: /^jeu\. 19 · 1 tâche/ })).toHaveClass('nouveau')
    expect(screen.queryByRole('group', { name: 'À revoir (1)' })).toBeNull()
    expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Placée jeu. 19')
  })

  it('pose une tâche sur un jour sans ouvrir de fiche, puis Terminer', async () => {
    const { container } = monter()
    expect(await screen.findByRole('heading', { level: 1, name: 'Planifier ma semaine' })).toBeInTheDocument()
    await waitFor(() => expect(lireAgenda).toHaveBeenCalledWith({ du: '2026-11-16', au: '2026-11-22', vue: 'semaine' }))
    fireEvent.click(await screen.findByRole('button', { name: /Préparer formation/ }))
    fireEvent.click(screen.getByRole('button', { name: /^jeu\. 19 · .* · placer Préparer formation$/ }))
    await waitFor(() => expect(planifierTache).toHaveBeenCalledWith(30, {
      jour_prevu: '2026-11-19', heure_debut: null, moment: '', quelque_jour: false, lock_version: 2,
    }))
    // R4-01 — la charge SERVIE du jeudi (Libre · 4 h) suit la pose (+ 45 min), sans relecture ni recompte
    const jeudi = await screen.findByRole('button', { name: /^jeu\. 19 · 1 tâche · 45 min sur 4 h$/ })
    expect(jeudi).toHaveClass('nouveau')
    // la puce de la pose (iPhone) et la carte de la colonne (bureau, Raccord F2) portent la tâche posée
    expect(jeudi.querySelector('.ag-pj-ajout')).toHaveTextContent('Préparer formation')
    expect(jeudi.querySelector('.ag-pj-cartes')).toHaveTextContent('Préparer formation')
    expect(screen.queryByRole('button', { name: /Préparer formation/, pressed: false })).toBeNull()
    expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Placée jeu. 19')
    // aucune fiche ouverte, aucune relecture de l'agenda
    expect(container.querySelector('[data-fiche]')).toBeNull()
    expect(screen.getByTestId('adresse').textContent).not.toContain('tache=')
    expect(lireAgenda).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: 'Terminer' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Agenda' })).toBeInTheDocument()
    expect(screen.getByTestId('adresse').textContent).not.toContain('placer=')
  })
})
