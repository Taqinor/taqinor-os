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
    toute_la_journee: [], sans_heure: [], blocs: [], echeances: [], externes: [],
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
    expect(within(liste).getByRole('button', { name: 'mar. 17 · 2 tâches · 1 h 15 pour 7 h' })).toBeInTheDocument()
    expect(within(liste).getByRole('button', { name: 'mar. 17 · 2 tâches · 1 h 15 pour 7 h' }).querySelector('.ag-charge')).not.toBeNull()
  })

  it('Raccord F2 — chaque jour porte ses cartes (colonnes du bureau), décor muet : le nom du jour reste celui du bouton', () => {
    monter()
    const mardi = screen.getByRole('button', { name: 'mar. 17 · 2 tâches · 1 h 15' })
    const cartes = mardi.querySelector('.ag-pj-cartes')
    expect(cartes).toHaveAttribute('aria-hidden', 'true')
    expect(cartes.querySelectorAll('.ag-carte')).toHaveLength(2)
    expect(screen.getByRole('button', { name: 'dim. 22 · non travaillé' }).closest('.ag-pj-place')).toHaveClass('repos')
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
