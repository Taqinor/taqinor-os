import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { lireAgenda, planifierTache } from '../../../api/tachesApi'
import Agenda from '../../../pages/taches/Agenda'
import PlanifierSemaine from './PlanifierSemaine'

vi.mock('../../../api/tachesApi', async (importOriginal) => ({
  ...(await importOriginal()),
  lireAgenda: vi.fn(),
  planifierTache: vi.fn(),
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

function septJours() {
  const servis = Object.fromEntries(agenda().jours.map((j) => [j.jour, j]))
  return SEMAINE.map((iso) => servis[iso] ?? {
    jour: iso, ouvre: !['2026-11-21', '2026-11-22'].includes(iso), ferie: false,
    toute_la_journee: [], sans_heure: [], blocs: [], echeances: [], externes: [], faites_nb: 0,
  })
}

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
    expect(within(jours).getByRole('button', { name: 'mar. 17 · 2 tâches · 1 h 15' })).toHaveAttribute('aria-current', 'date')
    expect(within(jours).getByRole('button', { name: 'dim. 22 · non travaillé' })).toBeEnabled()
    expect(screen.getByRole('button', { name: /Préparer formation/ })).toBeInTheDocument()
    expect(screen.getByText('● Équipe (1)')).toBeInTheDocument()
  })

  it('R2-102 — un jour passé dit les tâches FINIES ce jour-là (`faites_nb` servi), pas celles qui y étaient prévues', () => {
    const jours = septJours()
    jours[0] = { ...jours[0], faites_nb: 3 }
    monter({ jours })
    expect(screen.getByRole('button', { name: 'lun. 16 · passé · 3 faites' })).toBeDisabled()
  })

  it('une tâche choisie se pose sur le jour touché ; sans choix, le jour s\'ouvre', () => {
    const onPoser = vi.fn()
    const onOuvrirJour = vi.fn()
    const { rerender } = monter({ onPoser, onOuvrirJour })
    fireEvent.click(screen.getByRole('button', { name: 'jeu. 19 · 0 tâche' }))
    expect(onOuvrirJour).toHaveBeenCalledWith('2026-11-19')
    const formation = agenda().mes_projets[0].items[0]
    rerender(<PlanifierSemaine jours={septJours()} aujourdhui={AUJOURDHUI} aPlacer={agenda().a_placer}
      mesProjets={agenda().mes_projets} choisie={formation} onChoisir={vi.fn()} onPoser={onPoser}
      onOuvrirJour={onOuvrirJour} onTerminer={vi.fn()} />)
    expect(screen.getByRole('status')).toHaveTextContent('Touche un jour pour placer Préparer formation')
    fireEvent.click(screen.getByRole('button', { name: 'jeu. 19 · 0 tâche · placer Préparer formation' }))
    expect(onPoser).toHaveBeenCalledWith(formation, '2026-11-19')
  })

  it('Raccord F2 — « {n} tâches · {h} pour {cap} » seulement si la capacité du jour est servie', () => {
    monter({ capacite: 420 })
    const liste = screen.getByRole('list', { name: 'Jours de la semaine' })
    expect(within(liste).getByRole('button', { name: 'mar. 17 · 2 tâches · 1 h 15 pour 6 h' })).toBeInTheDocument()
    expect(within(liste).getByRole('button', { name: 'mar. 17 · 2 tâches · 1 h 15 pour 6 h' }).querySelector('.ag-charge')).not.toBeNull()
  })

  it('Raccord F2 — chaque jour porte ses cartes (colonnes du bureau), décor muet : le nom du jour reste celui du bouton', () => {
    monter()
    const mardi = screen.getByRole('button', { name: 'mar. 17 · 2 tâches · 1 h 15' })
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
    lireAgenda.mockResolvedValue({ data: agenda() })
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
    expect(await screen.findByText('23 – 29 novembre')).toBeInTheDocument()
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

  it('pose une tâche sur un jour sans ouvrir de fiche, puis Terminer', async () => {
    const { container } = monter()
    expect(await screen.findByRole('heading', { level: 1, name: 'Planifier ma semaine' })).toBeInTheDocument()
    await waitFor(() => expect(lireAgenda).toHaveBeenCalledWith({ du: '2026-11-16', au: '2026-11-22', vue: 'semaine' }))
    fireEvent.click(await screen.findByRole('button', { name: /Préparer formation/ }))
    fireEvent.click(screen.getByRole('button', { name: /^jeu\. 19 · .* · placer Préparer formation$/ }))
    await waitFor(() => expect(planifierTache).toHaveBeenCalledWith(30, {
      jour_prevu: '2026-11-19', heure_debut: null, moment: '', quelque_jour: false, lock_version: 2,
    }))
    const jeudi = await screen.findByRole('button', { name: /^jeu\. 19 · 1 tâche · 45 min pour 4 h$/ })
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
