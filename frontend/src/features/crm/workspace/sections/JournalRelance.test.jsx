// RLC2 — le panneau « Ce qui s'est passé » du plan de relance : UNE liste
// chronologique où chaque ligne dit sa CAUSE, et l'état courant en une phrase.
// Charge utile = l'exemple COMMITTÉ `apps/crm/contract_samples/journal_relance.json`
// (PACT10), jamais un objet retapé à la main.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import {
  exempleContrat, reponseContrat,
} from '../../../../test/fixtures/contractSamples'

vi.mock('../../../../api/crmApi', () => ({
  default: { getJournalRelance: vi.fn() },
}))

import crmApi from '../../../../api/crmApi'
import JournalRelance from './JournalRelance'

const JOURNAL = exempleContrat('crm', 'journal_relance')

beforeEach(() => {
  crmApi.getJournalRelance.mockResolvedValue(
    reponseContrat('crm', 'journal_relance'))
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('RLC2 JournalRelance', () => {
  it('charge le journal du lead et affiche l\'état courant en une phrase', async () => {
    render(<JournalRelance leadId={1489} />)
    await waitFor(() => expect(crmApi.getJournalRelance).toHaveBeenCalledWith(1489))
    expect(await screen.findByTestId('journal-etat'))
      .toHaveTextContent(JOURNAL.etat.phrase)
  })

  it('rend TOUTES les lignes, dans l\'ORDRE servi, chacune typée', async () => {
    render(<JournalRelance leadId={1489} />)
    const lignes = await screen.findAllByTestId('journal-ligne')
    expect(lignes).toHaveLength(JOURNAL.lignes.length)
    expect(lignes.map((li) => li.dataset.type))
      .toEqual(JOURNAL.lignes.map((l) => l.type))
  })

  it('chaque ligne dit sa CAUSE quand le serveur la connaît', async () => {
    render(<JournalRelance leadId={1489} />)
    await screen.findAllByTestId('journal-ligne')
    const avecCause = JOURNAL.lignes.filter((l) => l.cause)
    expect(avecCause.length).toBeGreaterThan(0)
    for (const ligne of avecCause) {
      const rendue = screen.getAllByTestId('journal-ligne')
        .find((li) => li.dataset.type === ligne.type
          && li.textContent.includes(ligne.titre))
      expect(rendue).toBeTruthy()
      expect(rendue.textContent).toContain(ligne.cause)
    }
  })

  it('un geste du MOTEUR n\'affiche aucun nom d\'humain (CKP1)', async () => {
    const moteur = JOURNAL.lignes.find(
      (l) => l.type === 'touche_annulee' && l.par === '')
    expect(moteur).toBeTruthy()
    render(<JournalRelance leadId={1489} />)
    await screen.findAllByTestId('journal-ligne')
    const rendue = screen.getAllByTestId('journal-ligne')
      .find((li) => li.dataset.type === 'touche_annulee')
    expect(rendue.textContent).toContain(moteur.cause)
    // Le nom qui figure sur les lignes HUMAINES du même journal n'apparaît pas
    // sur celle-ci : un retrait moteur ne porte le nom de personne.
    const humaine = JOURNAL.lignes.find((l) => l.par)
    expect(humaine).toBeTruthy()
    expect(rendue.textContent).not.toContain(humaine.par)
  })

  it('un plan vierge le DIT, sans inventer de ligne', async () => {
    crmApi.getJournalRelance.mockResolvedValue(
      reponseContrat('crm', 'journal_relance', 'exemple_vide'))
    render(<JournalRelance leadId={1490} />)
    expect(await screen.findByText(/Rien ne s’est encore passé/))
      .toBeInTheDocument()
    expect(screen.queryAllByTestId('journal-ligne')).toHaveLength(0)
  })

  it('ne charge rien sans leadId (mode création)', () => {
    render(<JournalRelance leadId={null} />)
    expect(crmApi.getJournalRelance).not.toHaveBeenCalled()
  })

  it('panne serveur : un état lisible, jamais un plantage de la fiche', async () => {
    crmApi.getJournalRelance.mockRejectedValue(new Error('boom'))
    render(<JournalRelance leadId={1489} />)
    expect(await screen.findByText(/Journal du plan de relance indisponible/))
      .toBeInTheDocument()
  })

  it('crmApi.getJournalRelance absente du mock (suites existantes) : repli silencieux', async () => {
    const original = crmApi.getJournalRelance
    delete crmApi.getJournalRelance
    render(<JournalRelance leadId={1489} />)
    expect(await screen.findByText(/Journal du plan de relance indisponible/))
      .toBeInTheDocument()
    crmApi.getJournalRelance = original
  })

  it('recharge quand reloadToken change (après un geste de relance)', async () => {
    const { rerender } = render(<JournalRelance leadId={1489} reloadToken={0} />)
    await waitFor(() => expect(crmApi.getJournalRelance).toHaveBeenCalledTimes(1))
    rerender(<JournalRelance leadId={1489} reloadToken={1} />)
    await waitFor(() => expect(crmApi.getJournalRelance).toHaveBeenCalledTimes(2))
  })
})
