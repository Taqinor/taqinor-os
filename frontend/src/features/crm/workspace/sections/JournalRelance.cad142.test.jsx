// CAD142 (round 2, 23/09/2026) — « Le Journal du plan de relance ne
// mentionne jamais les visites, que la Frise affiche juste à côté. » La
// preuve d'origine du constat était fausse (`planifier_visite` ne
// journalise rien — `apps/visites/services.py:258`) et le Journal reste
// borné au plan de relance par sa spec (`JournalRelance.jsx`). Version
// minimale retenue par le round 2 : une touche close par l'issue
// « Visite acceptée » porte déjà ce libellé comme `cause` d'une ligne
// `touche_faite` — aucun nouveau type de ligne. Ce test le prouve avec une
// charge utile de MÊME FORME que le contrat committé
// (`apps/crm/contract_samples/journal_relance.json`), une seule ligne
// remplacée.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { exempleContrat } from '../../../../test/fixtures/contractSamples'
import JournalRelance from './JournalRelance'

const MODELE = exempleContrat('crm', 'journal_relance')

vi.mock('../../../../api/crmApi', () => ({
  default: { getJournalRelance: vi.fn() },
}))

import crmApi from '../../../../api/crmApi'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('JournalRelance — CAD142 (« Visite acceptée » comme cause d\'une touche faite)', () => {
  it('une touche close par « Visite acceptée » le montre dans le Journal', async () => {
    crmApi.getJournalRelance.mockResolvedValue({
      data: {
        ...MODELE,
        lignes: [
          {
            quand: '2026-09-10T09:00:00Z',
            type: 'touche_faite',
            titre: 'Touche « Débrief visite » (Appel, cadence apres_devis) faite',
            cause: 'Visite acceptée',
            par: 'meryem',
          },
        ],
      },
    })
    render(<JournalRelance leadId={1489} />)

    const ligne = await screen.findByTestId('journal-ligne')
    expect(ligne.dataset.type).toBe('touche_faite')
    expect(ligne).toHaveTextContent('Visite acceptée')
  })
})
