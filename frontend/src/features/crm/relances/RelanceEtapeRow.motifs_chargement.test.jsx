import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

/* Vérification réelle du 30/09/2026 (fenêtre « Appeler » de la fiche, mobile) :
   sur « Perdu — clore le dossier », l'écran disait « Aucun motif de perte n’est
   paramétré » PENDANT la lecture des motifs — la société en avait douze. Le
   message ne doit apparaître qu'après la réponse du serveur, et seulement si
   elle est vide. */

let resoudreMotifs
vi.mock('../../../api/crmApi', () => ({
  default: {
    getAssignableUsers: vi.fn(() => Promise.resolve({ data: [] })),
    getMotifsPerte: vi.fn(() => new Promise((resolve) => { resoudreMotifs = resolve })),
    getPanneauAppel: vi.fn(() => Promise.reject(new Error('indisponible'))),
    getRelanceEtapeMessage: vi.fn(() => Promise.resolve({ data: { message: 'x', langue: 'fr' } })),
  },
}))
vi.mock('../../../lib/toast', () => ({ toastInfo: vi.fn(), toastSuccess: vi.fn() }))

import crmApi from '../../../api/crmApi'
import RelanceEtapeRow from './RelanceEtapeRow'

// La 2e touche de l'exemple générique est l'étape « Décider la suite » (tâche).
const [, DECIDER] = exempleContrat('crm', 'relance_etape_v2', 'exemple_generique').results
const noop = () => {}

afterEach(() => { cleanup(); vi.clearAllMocks() })

async function ouvrirPerdu() {
  render(
    <RelanceEtapeRow etape={{ ...DECIDER, statut: 'a_faire', overdue: false }} onFait={noop}
      onSauter={noop} onReporter={noop} onOuvrirMessage={noop} />,
  )
  fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Perdu — clore le dossier' }))
  // La lecture part dans une micro-tâche : on attend que le serveur (mocké)
  // ait été appelé — sa réponse, elle, reste en attente.
  await waitFor(() => expect(crmApi.getMotifsPerte).toHaveBeenCalled())
}

describe('RelanceEtapeRow — motifs de perte en cours de lecture', () => {
  it('pendant la lecture : la liste est vide SANS le message « Aucun motif » ; puis les motifs arrivent', async () => {
    await ouvrirPerdu()
    expect(screen.getByLabelText('Motif de perte (obligatoire)')).toBeInTheDocument()
    expect(screen.queryByTestId('motif-perte-aucun')).not.toBeInTheDocument()
    resoudreMotifs({ data: { results: [
      { id: 1, nom: 'Prix', archived: false }, { id: 2, nom: 'Ancien', archived: true },
    ] } })
    await waitFor(() => expect(screen.getByRole('option', { name: 'Prix' })).toBeInTheDocument())
    expect(screen.queryByRole('option', { name: 'Ancien' })).not.toBeInTheDocument()
    expect(screen.queryByTestId('motif-perte-aucun')).not.toBeInTheDocument()
  })

  it('réponse vide : le message « Aucun motif de perte n’est paramétré » apparaît, une fois la lecture faite', async () => {
    await ouvrirPerdu()
    expect(screen.queryByTestId('motif-perte-aucun')).not.toBeInTheDocument()
    resoudreMotifs({ data: { results: [] } })
    expect(await screen.findByTestId('motif-perte-aucun')).toBeInTheDocument()
  })
})
