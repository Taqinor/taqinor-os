// AGR527 — « Proposer le texte » sur la tâche de playbook qui porte une
// `cle_message` (contrat partagé `lead_playbook.json`, AGR507/AGR526) : le
// clic ouvre `MessageVisiteDialog` avec CETTE clé ; une tâche sans clé n'a pas
// de bouton. Mock importé de l'échantillon du contrat — jamais inventé.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import api from '../../../api/axios'
import PlaybookChecklistPanel from './PlaybookChecklistPanel'

vi.mock('../../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))
vi.mock('../../../features/crm/relances/MessageVisiteDialog', () => ({
  default: ({ cle, open }) => (open ? <div data-testid="message-visite-dialog">{cle}</div> : null),
}))

const liste = exempleContrat('crm', 'lead_playbook', 'exemple_liste')

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('AGR527 — PlaybookChecklistPanel : « Proposer le texte »', () => {
  it('une tâche avec cle_message porte le bouton ; le clic ouvre la modale avec cette clé', async () => {
    api.get.mockResolvedValue({ data: [liste[0]] })
    render(<PlaybookChecklistPanel leadId={1512} />)
    const bouton = await screen.findByRole('button', { name: 'Proposer le texte' })
    expect(screen.queryByTestId('message-visite-dialog')).toBeNull()
    fireEvent.click(bouton)
    expect(screen.getByTestId('message-visite-dialog').textContent).toBe('dossier_fda')
    // Cocher la tâche reste un geste séparé : aucun POST au clic.
    expect(api.post).not.toHaveBeenCalled()
  })

  it('une tâche sans cle_message n’a pas de bouton', async () => {
    api.get.mockResolvedValue({ data: [liste[2]] })
    render(<PlaybookChecklistPanel leadId={1512} />)
    await waitFor(() => expect(screen.getByText(liste[2].tache_libelle)).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: 'Proposer le texte' })).toBeNull()
  })
})
