import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { annulerGeste, lireAgenda, modifierTache, planifierTache, trancherTache } from '../../../api/tachesApi'
import Agenda from '../../../pages/taches/Agenda'
import VoletAPlacer from './VoletAPlacer'

vi.mock('../../../api/tachesApi', async (importOriginal) => ({
  ...(await importOriginal()),
  lireAgenda: vi.fn(),
  planifierTache: vi.fn(),
  trancherTache: vi.fn(),
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

  it('R4 couture — une tâche SANS durée n\'affiche aucune durée (jamais « 30 min » inventé)', () => {
    const sans = { ...aujourdhuiEnPlus(), id: 52, titre: 'Appeler le fournisseur', estimation_minutes: null }
    render(<VoletAPlacer aPlacer={[sans, { ...aujourdhuiEnPlus(), id: 53, titre: 'Durée nulle', estimation_minutes: 0 }]}
      aujourdhui={AUJOURDHUI} onChoisir={vi.fn()} />)
    const ligne = screen.getByRole('button', { name: /Appeler le fournisseur/ })
    expect(ligne).not.toHaveTextContent('min')
    expect(ligne.querySelector('.d')).toBeNull()
    expect(screen.getByRole('button', { name: /Durée nulle/ })).not.toHaveTextContent('min')
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

  it('R2-105 — l\'aide du pied a deux phrases : « Glisse » au bureau, « Touche une tâche, puis un créneau » sur iPhone', () => {
    const { container } = render(<VoletAPlacer aPlacer={aPlacer()} aujourdhui={AUJOURDHUI} onChoisir={vi.fn()} />)
    expect(container.querySelector('.ag-aside-pied .bureau-seul')).toHaveTextContent('Glisse une tâche sur un créneau')
    expect(container.querySelector('.ag-aside-pied .mobile-seul')).toHaveTextContent('Touche une tâche, puis un créneau.')
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
    data: { tache: { ...aPlacer()[0], jour_prevu: AUJOURDHUI, heure_debut: '14:00', lock_version: lockVersion, ...champs },
      geste_id: 99 },
  })

  beforeEach(() => {
    lireAgenda.mockResolvedValue({ data: agenda() })
    planifierTache.mockResolvedValue(placee())
    trancherTache.mockResolvedValue({ data: { tache: { ...aPlacer()[0], jour_prevu: AUJOURDHUI, lock_version: 7 }, geste_id: 98 } })
    modifierTache.mockImplementation((id, corps) => Promise.resolve(placee(8, { estimation_minutes: corps.estimation_minutes })))
    annulerGeste.mockResolvedValue({ data: { restaurees: [], conflits: [], deja: false } })
  })
  afterEach(() => { vi.clearAllMocks() })

  it('la tâche puis le créneau : `planifier/` avec le jour et l\'heure, sans relire l\'agenda', async () => {
    const { container } = monter()
    fireEvent.click(await screen.findByRole('button', { name: /Site web/ }))
    expect(screen.queryByRole('button', { name: 'Ajouter à 14:00' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Placer à 14:00' }))
    // R2-106 — « Site web » est reportée 3 fois (À revoir) : la poser la DÉCIDE (`trancher/`), puis l'heure
    await waitFor(() => expect(trancherTache).toHaveBeenCalledWith(50, { choix: 'jour', jour: AUJOURDHUI }))
    await waitFor(() => expect(planifierTache).toHaveBeenCalledWith(50, {
      jour_prevu: AUJOURDHUI, heure_debut: '14:00', moment: '', quelque_jour: false, lock_version: 7,
    }))
    const grille = container.querySelector('.grille-agenda')
    expect(within(grille).getByRole('button', { name: /Site web/ }).closest('.bloc')).toHaveClass('choisi')
    expect(screen.queryByRole('group', { name: 'À revoir (1)' })).toBeNull() // sortie d'« À placer »
    expect(screen.getByRole('heading', { name: 'À placer · 1' })).toBeInTheDocument() // reste Mes projets
    expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Placée à 14:00')
    expect(lireAgenda).toHaveBeenCalledTimes(1)
  })

  it('R3-120 — le glisser : AUCUN rendu pendant le glisser (le navigateur annule un glisser dont la page bouge), les créneaux acceptent le dépôt, le dépôt pose la tâche', async () => {
    const { container } = monter()
    const ligne = await screen.findByRole('button', { name: /Site web/ })
    const donnees = { setData: vi.fn(), effectAllowed: '' }
    fireEvent.dragStart(ligne, { dataTransfer: donnees })
    expect(donnees.setData).toHaveBeenCalledWith('text/plain', '50')
    // aucun changement à l'écran : ni consigne ajoutée au-dessus de la liste, ni état pressé, ni créneaux « Placer à »
    expect(ligne).toHaveAttribute('aria-pressed', 'false')
    expect(container.querySelector('.ag-consigne')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Placer à 14:00' })).toBeNull()
    // le créneau accepte le dépôt (dragover annulé), se surligne sans rendu, puis le dépôt pose la tâche
    const creneau = screen.getByRole('button', { name: 'Ajouter à 14:00' })
    expect(fireEvent.dragOver(creneau, { dataTransfer: donnees })).toBe(false)
    fireEvent.dragEnter(creneau, { dataTransfer: donnees })
    expect(creneau).toHaveAttribute('data-survol', 'oui')
    fireEvent.drop(creneau, { dataTransfer: donnees })
    expect(creneau).not.toHaveAttribute('data-survol')
    await waitFor(() => expect(trancherTache).toHaveBeenCalledWith(50, { choix: 'jour', jour: AUJOURDHUI }))
    await waitFor(() => expect(planifierTache).toHaveBeenCalledWith(50, expect.objectContaining({ jour_prevu: AUJOURDHUI, heure_debut: '14:00' })))
  })

  it('R3-120 — un glisser abandonné (dragend sans dépôt) : un dépôt venu d\'ailleurs ne pose rien', async () => {
    monter()
    const ligne = await screen.findByRole('button', { name: /Site web/ })
    fireEvent.dragStart(ligne, { dataTransfer: { setData: vi.fn(), effectAllowed: '' } })
    fireEvent.dragEnd(ligne)
    fireEvent.drop(screen.getByRole('button', { name: 'Ajouter à 14:00' }))
    expect(trancherTache).not.toHaveBeenCalled()
    expect(planifierTache).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /Site web/ })).toHaveAttribute('aria-pressed', 'false')
  })

  it('R2-105 — iPhone : choisir une tâche ramène la vue sur la grille, près de la ligne « maintenant »', async () => {
    const defile = vi.fn()
    const avant = Element.prototype.scrollIntoView
    Element.prototype.scrollIntoView = defile
    try {
      monter()
      fireEvent.click(await screen.findByRole('button', { name: /Site web/ }))
      await waitFor(() => expect(defile).toHaveBeenCalledTimes(1))
      expect(defile.mock.contexts[0]).toHaveClass('maintenant')
      expect(defile.mock.calls[0][0]).toMatchObject({ block: 'center' })
    } finally { Element.prototype.scrollIntoView = avant }
  })

  it('R2-105 — « Déplacer » reprend la tâche posée : un autre créneau la déplace, sans fiche ni relecture', async () => {
    const { container } = monter()
    fireEvent.click(await screen.findByRole('button', { name: /Site web/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Placer à 14:00' }))
    const duree = await screen.findByRole('group', { name: 'Durée de Site web' })
    fireEvent.click(within(duree).getByRole('button', { name: 'Déplacer' }))
    expect(screen.queryByRole('group', { name: 'Durée de Site web' })).toBeNull()
    expect(screen.getByText('Touche un créneau pour déplacer Site web')).toBeInTheDocument()
    planifierTache.mockResolvedValue(placee(8, { heure_debut: '15:00' }))
    fireEvent.click(screen.getByRole('button', { name: 'Placer à 15:00' }))
    await waitFor(() => expect(planifierTache).toHaveBeenLastCalledWith(50, {
      jour_prevu: AUJOURDHUI, heure_debut: '15:00', moment: '', quelque_jour: false, lock_version: 7,
    }))
    const grille = container.querySelector('.grille-agenda')
    expect(grille.querySelectorAll('[data-bloc="50"]')).toHaveLength(1)
    expect(within(grille).getByRole('button', { name: /Site web/ }).closest('.bloc').style.top).not.toBe('')
    expect(lireAgenda).toHaveBeenCalledTimes(1)
  })

  it('la durée par pas de 15 (Maj+↓) puis 1 h, avec la version rendue', async () => {
    monter()
    fireEvent.click(await screen.findByRole('button', { name: /Site web/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Placer à 14:00' }))
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
    fireEvent.click(screen.getByRole('button', { name: 'Placer à 14:00' }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(within(screen.getByRole('complementary', { name: 'À placer' })).getByRole('button', { name: /Site web/ }))
      .toBeInTheDocument()
  })

  it('R2-106 — « Annuler » défait la pose ET la décision (deux gestes, le dernier d\'abord)', async () => {
    monter()
    fireEvent.click(await screen.findByRole('button', { name: /Site web/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Placer à 14:00' }))
    const duree = await screen.findByRole('group', { name: 'Durée de Site web' })
    fireEvent.click(within(duree).getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(annulerGeste).toHaveBeenCalledTimes(2))
    expect(annulerGeste.mock.calls.map((a) => a[0])).toEqual([99, 98])
  })

  it('R2-106 — la pose échoue après la décision : la décision est défaite, la tâche reste dans « À placer »', async () => {
    planifierTache.mockRejectedValue({ response: { status: 500, data: {} } })
    monter()
    fireEvent.click(await screen.findByRole('button', { name: /Site web/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Placer à 14:00' }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    await waitFor(() => expect(annulerGeste).toHaveBeenCalledWith(98))
  })

  it('« Annuler » de la durée défait la pose par le geste', async () => {
    monter()
    fireEvent.click(await screen.findByRole('button', { name: /Site web/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Placer à 14:00' }))
    const duree = await screen.findByRole('group', { name: 'Durée de Site web' })
    fireEvent.click(within(duree).getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(annulerGeste).toHaveBeenCalledWith(99))
    expect(await within(screen.getByRole('complementary', { name: 'À placer' })).findByRole('button', { name: /Site web/ }))
      .toBeInTheDocument()
  })
})
