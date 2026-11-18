import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { annulerGeste, lireAgenda, modifierTache, planifierTache } from '../../../api/tachesApi'
import Agenda from '../../../pages/taches/Agenda'
import VoletAPlacer from './VoletAPlacer'

vi.mock('../../../api/tachesApi', async (importOriginal) => ({
  ...(await importOriginal()),
  lireAgenda: vi.fn(),
  planifierTache: vi.fn(),
  modifierTache: vi.fn(),
  annulerGeste: vi.fn(),
  terminerTache: vi.fn(),
  rouvrirTache: vi.fn(),
}))

/* TCH105 — le volet « À placer » (groupes, durées, choix d'une tâche) et « Placer à une heure » :
   toucher la tâche puis le créneau appelle `taches/{id}/planifier/` (jour + heure), sans relire
   l'agenda ; la durée se règle par pas de 15 min (Maj+↓) ou 30 min · 1 h · 2 h. */

const AUJOURDHUI = '2026-11-17'
const agenda = () => structuredClone(exempleContrat('taches', 'agenda'))
const aPlacer = () => agenda().a_placer // « Site web », reportée 3 fois (motif) → À revoir
const mesProjets = () => agenda().mes_projets // Équipe : « Préparer formation » (45 min)

function aujourdhuiEnPlus() {
  return { ...aPlacer()[0], id: 51, titre: 'Confirmer le stand', motif: null, jour_prevu: AUJOURDHUI,
    estimation_minutes: 30, explication: "échéance aujourd'hui" }
}

describe('TCH105 — VoletAPlacer', () => {
  it('trois groupes comptés, durées, Mes projets replié puis « ● projet (n) »', () => {
    render(<VoletAPlacer aPlacer={[aujourdhuiEnPlus(), ...aPlacer()]} mesProjets={mesProjets()}
      aujourdhui={AUJOURDHUI} onChoisir={vi.fn()} />)
    expect(screen.getByRole('heading', { name: 'À placer · 3' })).toBeInTheDocument()
    const jour = screen.getByRole('group', { name: "Aujourd'hui (1)" })
    expect(within(jour).getByRole('button', { name: /Confirmer le stand/ })).toHaveTextContent('30 min')
    expect(within(screen.getByRole('group', { name: 'À revoir (1)' })).getByRole('button', { name: /Site web/ }))
      .toHaveTextContent('reportée 3 fois')
    const projets = screen.getByRole('group', { name: 'Mes projets (1)' })
    expect(within(projets).queryByRole('button', { name: /Préparer formation/ })).toBeNull()
    fireEvent.click(within(projets).getByRole('button', { name: /Mes projets/ }))
    expect(screen.getByText('● Équipe (1)')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Préparer formation/ })).toHaveTextContent('45 min')
  })

  it('toucher choisit (une seule), la consigne nomme la tâche, « Annuler la sélection » libère', () => {
    const onChoisir = vi.fn()
    const { rerender } = render(<VoletAPlacer aPlacer={aPlacer()} aujourdhui={AUJOURDHUI} onChoisir={onChoisir} />)
    fireEvent.click(screen.getByRole('button', { name: /Site web/ }))
    expect(onChoisir).toHaveBeenCalledWith(expect.objectContaining({ id: 50 }))
    rerender(<VoletAPlacer aPlacer={aPlacer()} aujourdhui={AUJOURDHUI} choisie={50} onChoisir={onChoisir} />)
    expect(screen.getByRole('button', { name: /Site web/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('status')).toHaveTextContent('Touche un créneau pour Site web')
    fireEvent.click(screen.getByRole('button', { name: 'Annuler la sélection' }))
    expect(onChoisir).toHaveBeenLastCalledWith(null)
  })

  it('vide : « Tout est placé »', () => {
    render(<VoletAPlacer aPlacer={[]} aujourdhui={AUJOURDHUI} onChoisir={vi.fn()} />)
    expect(screen.getByText('Tout est placé')).toBeInTheDocument()
  })
})

describe('TCH105 — Placer à une heure, dans l\'Agenda', () => {
  const monter = () => render(
    <MemoryRouter initialEntries={['/taches/agenda']}>
      <Routes>
        <Route path="/taches/agenda" element={<Agenda aujourdhui={AUJOURDHUI} maintenant={new Date(2026, 10, 17, 9, 41)} />} />
      </Routes>
    </MemoryRouter>,
  )
  const placee = (lockVersion = 7, champs = {}) => ({
    data: { tache: { ...aPlacer()[0], jour_prevu: AUJOURDHUI, heure_debut: '11:00', lock_version: lockVersion, ...champs },
      geste_id: 99 },
  })

  beforeEach(() => {
    lireAgenda.mockResolvedValue({ data: agenda() })
    planifierTache.mockResolvedValue(placee())
    modifierTache.mockImplementation((id, corps) => Promise.resolve(placee(8, { estimation_minutes: corps.estimation_minutes })))
    annulerGeste.mockResolvedValue({ data: { restaurees: [], conflits: [], deja: false } })
  })
  afterEach(() => { vi.clearAllMocks() })

  it('la tâche puis le créneau : `planifier/` avec le jour et l\'heure, sans relire l\'agenda', async () => {
    const { container } = monter()
    fireEvent.click(await screen.findByRole('button', { name: /Site web/ }))
    expect(screen.queryByRole('button', { name: 'Ajouter à 11:00' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Placer à 11:00' }))
    await waitFor(() => expect(planifierTache).toHaveBeenCalledWith(50, {
      jour_prevu: AUJOURDHUI, heure_debut: '11:00', moment: '', quelque_jour: false, lock_version: 6,
    }))
    const grille = container.querySelector('.grille-agenda')
    expect(within(grille).getByRole('button', { name: /Site web/ }).closest('.bloc')).toHaveClass('choisi')
    expect(screen.queryByRole('group', { name: 'À revoir (1)' })).toBeNull() // sortie d'« À placer »
    expect(screen.getByRole('heading', { name: 'À placer · 1' })).toBeInTheDocument() // reste Mes projets
    expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Placée à 11:00')
    expect(lireAgenda).toHaveBeenCalledTimes(1)
  })

  it('la durée par pas de 15 (Maj+↓) puis 1 h, avec la version rendue', async () => {
    monter()
    fireEvent.click(await screen.findByRole('button', { name: /Site web/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Placer à 11:00' }))
    const duree = await screen.findByRole('group', { name: 'Durée de Site web' })
    fireEvent.keyDown(window, { key: 'ArrowDown', shiftKey: true })
    await waitFor(() => expect(modifierTache).toHaveBeenCalledWith(50, { estimation_minutes: 45, lock_version: 7 }))
    await waitFor(() => expect(within(duree).getByText('45 min')).toBeInTheDocument())
    fireEvent.click(within(duree).getByRole('radio', { name: '1 h' }))
    await waitFor(() => expect(modifierTache).toHaveBeenLastCalledWith(50, { estimation_minutes: 60, lock_version: 8 }))
    expect(within(duree).getByRole('radio', { name: '1 h' })).toHaveAttribute('aria-checked', 'true')
  })

  it('un refus du serveur remet la tâche dans « À placer » et le dit', async () => {
    planifierTache.mockRejectedValue({ response: { status: 409, data: { detail: 'Modifiée ailleurs.', code: 'conflit_version' } } })
    monter()
    fireEvent.click(await screen.findByRole('button', { name: /Site web/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Placer à 11:00' }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(within(screen.getByRole('complementary', { name: 'À placer' })).getByRole('button', { name: /Site web/ }))
      .toBeInTheDocument()
  })

  it('« Annuler » de la durée défait la pose par le geste', async () => {
    monter()
    fireEvent.click(await screen.findByRole('button', { name: /Site web/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Placer à 11:00' }))
    const duree = await screen.findByRole('group', { name: 'Durée de Site web' })
    fireEvent.click(within(duree).getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(annulerGeste).toHaveBeenCalledWith(99))
    expect(await within(screen.getByRole('complementary', { name: 'À placer' })).findByRole('button', { name: /Site web/ }))
      .toBeInTheDocument()
  })
})
