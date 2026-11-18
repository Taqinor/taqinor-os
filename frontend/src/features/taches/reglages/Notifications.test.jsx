import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../../test/fixtures/contractSamples'
import {
  lireReglages, lireReglagesSociete, modifierReglages, modifierReglagesSociete, poserPreference,
} from '../../../api/tachesApi'
import Reglages from '../../../pages/taches/Reglages'
import { reinitialiserGestes } from '../lib/gestes'
import Notifications from './Notifications'

vi.mock('../../../api/tachesApi', async (importOriginal) => ({
  ...(await importOriginal()),
  lireReglages: vi.fn(),
  modifierReglages: vi.fn(),
  poserPreference: vi.fn(),
  lireReglagesSociete: vi.fn(),
  modifierReglagesSociete: vi.fn(),
  listerAgendasExternes: vi.fn().mockResolvedValue({ data: { results: [] } }),
  listerJetons: vi.fn().mockResolvedValue({ data: { results: [] } }),
}))

/* TCH160 — Réglages → Notifications et coupe-circuit de l'administrateur. Le client est mocké sur les
   échantillons `reglages.json` et `reglages_societe.json` ; un « serveur » en mémoire garde l'objet pour
   prouver « enregistrer → rouvrir → enregistrer sans toucher » (critère 2 du plan). */

const exemple = (nom) => structuredClone(exempleContrat('taches', nom))
const erreur400 = (corps) => Object.assign(new Error('400'), { response: { status: 400, data: corps } })
const COUPE = 'Messages et rappels de Tâches dans la société'

let serveur
let societe

function monter(url = '/taches/reglages/notifications') {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/taches/reglages/:rubrique?" element={<Reglages />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  serveur = exemple('reglages')
  societe = exemple('reglages_societe')
  lireReglages.mockImplementation(async () => ({ data: structuredClone(serveur) }))
  modifierReglages.mockImplementation(async (corps) => { Object.assign(serveur, corps); return { data: structuredClone(serveur) } })
  poserPreference.mockImplementation(async ({ cle, valeur }) => { serveur.sollicitations[cle] = valeur; return { data: {} } })
  lireReglagesSociete.mockImplementation(async () => ({ data: structuredClone(societe) }))
  modifierReglagesSociete.mockImplementation(async (corps) => { Object.assign(societe, corps); return { data: structuredClone(societe) } })
})
afterEach(() => { vi.clearAllMocks(); reinitialiserGestes() })

describe('TCH160 — Notifications', () => {
  it('rend les heures de l\'échantillon, l\'heure limite et la fenêtre de la société', async () => {
    monter()
    expect(await screen.findByRole('switch', { name: 'Plan du matin' })).toBeChecked()
    expect(screen.getByLabelText('Heure : Plan du matin')).toHaveValue('08:30')
    expect(screen.getByLabelText('Heure : Message de 15 h')).toHaveValue('15:00')
    expect(screen.getByLabelText('Heure : Bilan du soir')).toHaveValue('18:00')
    expect(screen.getByLabelText('Heure : Heure limite')).toHaveValue('20:00')
    expect(screen.getByRole('combobox', { name: 'Revue de la semaine' })).toHaveValue('auto')
    expect(screen.getByText('dernier jour travaillé')).toBeInTheDocument()
    expect(screen.getByText('Après cette heure, plus aucun message. Un rappel que tu as posé sonne toujours.')).toBeInTheDocument()
    expect(screen.getByText('Heures de travail de la société : 08:30 à 19:00. Hors de ces heures, un message est sauté, jamais envoyé plus tard.')).toBeInTheDocument()
    expect(screen.getByRole('switch', { name: 'Montrer le titre sur l\'écran verrouillé' })).not.toBeChecked()
  })

  it('« off » : l\'interrupteur éteint dit Éteint, le rallumer rend l\'heure par défaut', async () => {
    monter()
    await userEvent.click(await screen.findByRole('switch', { name: 'Message de 15 h' }))
    expect(poserPreference).toHaveBeenCalledWith({ cle: 'relance_jour', valeur: 'off' })
    const eteint = await screen.findByRole('switch', { name: 'Message de 15 h', checked: false })
    expect(screen.queryByLabelText('Heure : Message de 15 h')).toBeNull()
    expect(within(eteint.closest('.es-reglage')).getByText('Éteint')).toBeInTheDocument()
    await userEvent.click(eteint)
    expect(poserPreference).toHaveBeenLastCalledWith({ cle: 'relance_jour', valeur: '15:00' })
    expect(await screen.findByLabelText('Heure : Message de 15 h')).toHaveValue('15:00')
  })

  it('enregistrer → rouvrir → enregistrer sans toucher : l\'objet serveur ne bouge pas', async () => {
    const premier = monter()
    const champ = await screen.findByLabelText('Heure : Plan du matin')
    fireEvent.change(champ, { target: { value: '07:45' } })
    fireEvent.blur(champ)
    await waitFor(() => expect(poserPreference).toHaveBeenCalledWith({ cle: 'heure_matin', valeur: '07:45' }))
    const apres = structuredClone(serveur)
    expect(apres.sollicitations.heure_matin).toBe('07:45')
    premier.unmount()

    monter()
    const rouvert = await screen.findByLabelText('Heure : Plan du matin')
    expect(rouvert).toHaveValue('07:45')
    fireEvent.focus(rouvert)
    fireEvent.blur(rouvert)
    expect(poserPreference).toHaveBeenCalledTimes(1)
    expect(serveur).toEqual(apres)
  })

  it('une erreur du serveur s\'affiche sous le champ fautif et garde la valeur', async () => {
    poserPreference.mockRejectedValueOnce(erreur400({ valeur: ['Heure attendue (HH:MM).'] }))
    monter()
    const champ = await screen.findByLabelText('Heure : Heure limite')
    fireEvent.change(champ, { target: { value: '19:00' } })
    fireEvent.blur(champ)
    const alerte = await screen.findByRole('alert')
    expect(alerte).toHaveTextContent('Heure attendue (HH:MM).')
    expect(alerte.previousElementSibling).toContainElement(champ)
    expect(serveur.sollicitations.heure_limite).toBe('20:00')
  })

  it('la revue se règle sur un jour, « Éteinte » envoie off', async () => {
    monter()
    const revue = await screen.findByRole('combobox', { name: 'Revue de la semaine' })
    await userEvent.selectOptions(revue, 'Vendredi')
    expect(poserPreference).toHaveBeenCalledWith({ cle: 'revue_semaine', valeur: 4 })
    await userEvent.selectOptions(revue, 'Éteinte')
    expect(poserPreference).toHaveBeenLastCalledWith({ cle: 'revue_semaine', valeur: 'off' })
  })

  it('une sollicitation en pause se dit, « Réactiver » la retire par PATCH reglages/', async () => {
    monter()
    expect(await screen.findByText('Plan du matin : 14 de suite sans être ouverts')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Réactiver' }))
    expect(modifierReglages).toHaveBeenCalledWith({ pauses_sollicitations: [] })
    await waitFor(() => expect(screen.queryByText(/de suite sans être ouverts/)).toBeNull())
    expect(serveur.pauses_sollicitations).toEqual([])
  })

  it('le titre sur l\'écran verrouillé est un réglage direct', async () => {
    monter()
    await userEvent.click(await screen.findByRole('switch', { name: 'Montrer le titre sur l\'écran verrouillé' }))
    expect(modifierReglages).toHaveBeenCalledWith({ titres_notifications: true })
  })

  it('sans réglages lus, rien n\'est rendu', () => {
    const { container } = render(<Notifications reglages={null} onReglage={vi.fn()} />)
    expect(container).toBeEmptyDOMElement()
  })
})

describe('TCH160 — coupe-circuit de l\'administrateur', () => {
  it('l\'interrupteur n\'est rendu que si est_admin, et la route n\'est même pas frappée sinon', async () => {
    monter('/taches/reglages/avance')
    await screen.findByRole('switch', { name: 'Messages sans délai' })
    expect(screen.queryByRole('switch', { name: COUPE })).toBeNull()
    expect(lireReglagesSociete).not.toHaveBeenCalled()
  })

  it('administrateur : rendu allumé ; couper demande confirmation puis écrit ; Annuler rallume', async () => {
    serveur.est_admin = true
    monter('/taches/reglages/avance')
    const interrupteur = await screen.findByRole('switch', { name: COUPE })
    expect(interrupteur).toBeChecked()
    expect(screen.getByText(/Éteint : plus aucun message ni rappel de Tâches n'est envoyé dans la société/)).toBeInTheDocument()
    await userEvent.click(interrupteur)
    const dialogue = await screen.findByRole('dialog', { name: 'Couper tous les messages et rappels de Tâches pour la société ?' })
    expect(modifierReglagesSociete).not.toHaveBeenCalled()
    await userEvent.click(within(dialogue).getByRole('button', { name: 'Couper' }))
    expect(modifierReglagesSociete).toHaveBeenCalledWith({ balayage_actif: false })
    expect(await screen.findByRole('switch', { name: COUPE, checked: false })).toBeInTheDocument()
  })

  it('coupé : le bandeau dit depuis quand, Rallumer rallume ; rouvrir ne change pas l\'objet serveur', async () => {
    serveur.est_admin = true
    societe = { balayage_actif: false, modifie_par: 7, modifie_le: '2026-11-17T10:05:00+01:00' }
    const avant = structuredClone(societe)
    const premier = monter('/taches/reglages/avance')
    expect(await screen.findByText('Messages et rappels de Tâches coupés pour la société depuis le 17/11 à 10:05.')).toBeInTheDocument()
    premier.unmount()
    monter('/taches/reglages/avance')
    await screen.findByText(/coupés pour la société depuis le 17\/11 à 10:05/)
    expect(modifierReglagesSociete).not.toHaveBeenCalled()
    expect(societe).toEqual(avant)
    await userEvent.click(screen.getByRole('button', { name: 'Rallumer' }))
    expect(modifierReglagesSociete).toHaveBeenCalledWith({ balayage_actif: true })
    await waitFor(() => expect(screen.queryByText(/coupés pour la société/)).toBeNull())
  })

  it('un refus du serveur s\'affiche sous l\'interrupteur et garde l\'état', async () => {
    serveur.est_admin = true
    modifierReglagesSociete.mockRejectedValueOnce(erreur400({ balayage_actif: ['Valeur inconnue.'] }))
    monter('/taches/reglages/avance')
    await userEvent.click(await screen.findByRole('switch', { name: COUPE }))
    await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Couper' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Valeur inconnue.')
    expect(screen.getByRole('switch', { name: COUPE })).toBeChecked()
  })
})
