import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import process from 'node:process'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../test/fixtures/contractSamples'
import { reinitialiserGestes } from '../../features/taches/lib/gestes'
import {
  ajouterAgendaExterne, exporterMesDonnees, lireReglages, listerAgendasExternes, modifierAgendaExterne,
  listerJetons, modifierReglages, rafraichirAgendaExterne, retirerAgendaExterne, toutEffacer,
} from '../../api/tachesApi'
import Reglages from './Reglages'

vi.mock('../../api/tachesApi', async (importOriginal) => ({
  ...(await importOriginal()),
  lireReglages: vi.fn(),
  modifierReglages: vi.fn(),
  exporterMesDonnees: vi.fn(),
  toutEffacer: vi.fn(),
  listerAgendasExternes: vi.fn(),
  listerJetons: vi.fn(),
  ajouterAgendaExterne: vi.fn(),
  modifierAgendaExterne: vi.fn(),
  rafraichirAgendaExterne: vi.fn(),
  retirerAgendaExterne: vi.fn(),
}))

/* TCH108 — Réglages (cœur) : rubriques, Vie privée MOT POUR MOT (relue dans textes.md §6), Mes données
   (Exporter, Tout effacer EFFACER), Avancé (messages sans délai, agendas externes). Contrats :
   reglages.json, agendas_externes.json, agenda_externe.json, mes_donnees.json, tout_effacer.json. */

const exemple = (nom) => structuredClone(exempleContrat('taches', nom))
const erreur400 = (corps) => Object.assign(new Error('400'), { response: { status: 400, data: corps } })

function Lieu() {
  return <span data-testid="lieu">{useLocation().pathname}</span>
}

function monter(url = '/taches/reglages') {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/taches/reglages/:rubrique?" element={<Reglages />} />
        <Route path="*" element={<Lieu />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  lireReglages.mockResolvedValue({ data: exemple('reglages') })
  listerAgendasExternes.mockResolvedValue({ data: exemple('agendas_externes') })
  listerJetons.mockResolvedValue({ data: exemple('jetons_liste') })
})
afterEach(() => { vi.clearAllMocks(); reinitialiserGestes() })

function paragraphesDeLaReference() {
  const source = readFileSync(resolve(process.cwd(), '..', 'docs', 'taches', 'reference', 'textes.md'), 'utf8')
  const bloc = source.slice(source.indexOf('## 6. Réglages → Vie privée'), source.indexOf('Sous le texte : interrupteur'))
  const lignes = bloc.split(/\r?\n/).filter((l) => l.startsWith('>')).map((l) => l.replace(/^>\s?/, ''))
  const paragraphes = []
  let courant = []
  for (const ligne of lignes) {
    if (ligne.trim() === '') { if (courant.length) paragraphes.push(courant.join(' ')); courant = [] } else courant.push(ligne.trim())
  }
  if (courant.length) paragraphes.push(courant.join(' '))
  return paragraphes.map((p) => p.replaceAll('**', ''))
}

describe('TCH108 — Réglages', () => {
  it('liste les rubriques construites avec leur résumé, et ouvre celle qu\'on touche', async () => {
    monter()
    const liste = await screen.findByRole('list')
    const lignes = within(liste).getAllByRole('listitem')
    expect(lignes.map((l) => l.querySelector('b').textContent)).toEqual(['Notifications', 'Mon iPhone', 'Vie privée', 'Mes données', 'Avancé'])
    expect(within(liste).getByText('Ce qui part au Copilote, qui peut lire')).toBeInTheDocument()
    expect(within(liste).getByText('Exporter, tout effacer')).toBeInTheDocument()
    await userEvent.click(within(liste).getByRole('button', { name: /Avancé/ }))
    expect(await screen.findByRole('switch', { name: 'Messages sans délai' })).toBeInTheDocument()
  })

  it('/reglages/iphone?etape=calendrier ouvre l\'étape calendrier : « Mes agendas » et « Adresse de l\'agenda » rendus', async () => {
    monter('/taches/reglages/iphone?etape=calendrier')
    expect(await screen.findByRole('heading', { name: 'Mes agendas' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /^Adresse de l'agenda/ })).toBeInTheDocument()
  })

  it('Avancé ne porte plus « Mes agendas » (il vit dans Mon iPhone)', async () => {
    monter('/taches/reglages/avance')
    await screen.findByRole('switch', { name: 'Messages sans délai' })
    expect(screen.queryByRole('heading', { name: 'Mes agendas' })).toBeNull()
  })

  it('Vie privée : le texte est celui de la référence, mot pour mot', async () => {
    const { container } = monter('/taches/reglages/vie-privee')
    await screen.findByRole('switch', { name: 'Comprendre mon rythme' })
    const attendus = paragraphesDeLaReference()
    expect(attendus.length).toBeGreaterThanOrEqual(10)
    const verite = container.querySelector('.es-verite')
    const rendus = [verite.querySelector('h2'), ...verite.querySelectorAll('p')].map((n) => n.textContent.replace(/\s+/g, ' ').trim())
    expect(rendus).toEqual(attendus)
  })

  it('Vie privée : « Comprendre mon rythme » est lu, se bascule et le lien mène à Mes données', async () => {
    modifierReglages.mockResolvedValue({ data: {} })
    monter('/taches/reglages/vie-privee')
    const interrupteur = await screen.findByRole('switch', { name: 'Comprendre mon rythme' })
    expect(interrupteur).toBeChecked()
    await userEvent.click(interrupteur)
    expect(modifierReglages).toHaveBeenCalledWith({ comprendre_mon_rythme: false })
    expect(await screen.findByRole('switch', { name: 'Comprendre mon rythme', checked: false })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Mes données' }))
    expect(await screen.findByRole('button', { name: 'Tout effacer' })).toBeInTheDocument()
  })

  it('un réglage refusé garde son état et dit pourquoi sous lui', async () => {
    modifierReglages.mockRejectedValue(erreur400({ messages_sans_delai: ['Non modifiable ici.'] }))
    monter('/taches/reglages/avance')
    const interrupteur = await screen.findByRole('switch', { name: 'Messages sans délai' })
    await userEvent.click(interrupteur)
    expect(await screen.findByRole('alert')).toHaveTextContent('Non modifiable ici.')
    expect(screen.getByRole('switch', { name: 'Messages sans délai' })).not.toBeChecked()
  })

  it('Mes données : Exporter lit le fichier ; Tout effacer exige EFFACER puis revient à Aujourd\'hui', async () => {
    exporterMesDonnees.mockResolvedValue({ data: exemple('mes_donnees') })
    toutEffacer.mockResolvedValue({ data: exemple('tout_effacer') })
    URL.createObjectURL = vi.fn(() => 'blob:x')
    URL.revokeObjectURL = vi.fn()
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    monter('/taches/reglages/donnees')
    await userEvent.click(await screen.findByRole('button', { name: 'Exporter mes données (fichier JSON)' }))
    expect(exporterMesDonnees).toHaveBeenCalledTimes(1)
    expect(URL.createObjectURL).toHaveBeenCalledTimes(1)

    await userEvent.click(screen.getByRole('button', { name: 'Tout effacer' }))
    const dialogue = await screen.findByRole('dialog', { name: 'Tout effacer ?' })
    expect(within(dialogue).getByText(/Tes tâches, projets, réglages et jetons de cette société/)).toBeInTheDocument()
    await userEvent.type(within(dialogue).getByRole('textbox', { name: 'Confirmation' }), 'effacer')
    await userEvent.click(within(dialogue).getByRole('button', { name: 'Tout effacer' }))
    expect(await within(dialogue).findByRole('alert')).toHaveTextContent('Tape EFFACER pour confirmer.')
    expect(toutEffacer).not.toHaveBeenCalled()

    await userEvent.clear(within(dialogue).getByRole('textbox', { name: 'Confirmation' }))
    await userEvent.type(within(dialogue).getByRole('textbox', { name: 'Confirmation' }), 'EFFACER')
    await userEvent.click(within(dialogue).getByRole('button', { name: 'Tout effacer' }))
    expect(toutEffacer).toHaveBeenCalledWith({ confirmation: 'EFFACER' })
    expect(await screen.findByTestId('lieu')).toHaveTextContent('/taches/aujourdhui')
  })

  it('Mon iPhone : les agendas (étape 2) sont listés avec leur état lisible ; Avancé : « Messages sans délai » se pose', async () => {
    modifierReglages.mockResolvedValue({ data: {} })
    monter('/taches/reglages/iphone')
    await userEvent.click(await screen.findByRole('button', { name: /Voir tes tâches dans le Calendrier/ }))
    expect(await screen.findByText('Microsoft 365 · outlook.office365.com')).toBeInTheDocument()
    expect(screen.getByText('À jour à 09:05.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Avancé/ }))
    await userEvent.click(await screen.findByRole('switch', { name: 'Messages sans délai' }))
    expect(modifierReglages).toHaveBeenCalledWith({ messages_sans_delai: true })
    expect(await screen.findByRole('switch', { name: 'Messages sans délai', checked: true })).toBeInTheDocument()
  })

  it('Mon iPhone : ajouter un agenda, refus d\'une adresse sous le champ, rafraîchir, masquer et retirer', async () => {
    const refus = { ...exemple('agenda_externe'), id: 3, libelle: 'Bureau', hote: 'agenda.example', dernier_etat: 'illisible' }
    ajouterAgendaExterne.mockRejectedValueOnce(erreur400({ url: ['3 agendas au plus.'] }))
    ajouterAgendaExterne.mockResolvedValueOnce({ data: refus })
    rafraichirAgendaExterne.mockResolvedValue({ data: { ...exemple('agenda_externe'), dernier_etat: 'injoignable' } })
    modifierAgendaExterne.mockResolvedValue({ data: { ...exemple('agenda_externe'), actif: false } })
    retirerAgendaExterne.mockResolvedValue({ data: null })
    monter('/taches/reglages/iphone')
    await userEvent.click(await screen.findByRole('button', { name: /Voir tes tâches dans le Calendrier/ }))
    await screen.findByText('Microsoft 365 · outlook.office365.com')

    const adresse = screen.getByRole('textbox', { name: "Adresse de l'agenda (https://… ou webcal://…)" })
    await userEvent.type(adresse, 'https://agenda.example/a.ics')
    await userEvent.click(screen.getByRole('button', { name: 'Ajouter' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('3 agendas au plus.')
    expect(adresse).toHaveValue('https://agenda.example/a.ics')
    await userEvent.click(screen.getByRole('button', { name: 'Ajouter' }))
    expect(ajouterAgendaExterne).toHaveBeenLastCalledWith({ url: 'https://agenda.example/a.ics', libelle: '' })
    expect(await screen.findByText('Bureau · agenda.example')).toBeInTheDocument()
    expect(screen.getByText("Agenda illisible : ce n'est pas une adresse de calendrier (.ics).")).toBeInTheDocument()

    await userEvent.click(screen.getAllByRole('button', { name: 'Rafraîchir' })[0])
    expect(rafraichirAgendaExterne).toHaveBeenCalledWith(2)
    expect(await screen.findByText("Agenda injoignable pour l'instant.")).toBeInTheDocument()

    await userEvent.click(screen.getByRole('switch', { name: 'Afficher Microsoft 365' }))
    expect(modifierAgendaExterne).toHaveBeenCalledWith(2, { actif: false })

    await userEvent.click(screen.getAllByRole('button', { name: 'Retirer' })[0])
    const dialogue = await screen.findByRole('dialog', { name: 'Retirer « Microsoft 365 » ?' })
    expect(within(dialogue).getByText(/Ses rendez-vous disparaissent de Tâches ; ton agenda n'est pas touché\./)).toBeInTheDocument()
    await userEvent.click(within(dialogue).getByRole('button', { name: 'Retirer' }))
    expect(retirerAgendaExterne).toHaveBeenCalledWith(2)
    expect(screen.queryByText('Microsoft 365 · outlook.office365.com')).toBeNull()
  })

  it('un échec de lecture dit « Pas à jour » et garde la liste des rubriques', async () => {
    lireReglages.mockRejectedValueOnce(new Error('Network Error'))
    monter()
    expect(await screen.findByText('Pas à jour')).toBeInTheDocument()
    expect(screen.getByRole('list')).toBeInTheDocument()
  })
})
