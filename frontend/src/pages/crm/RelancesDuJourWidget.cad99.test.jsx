import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* CAD99 — « cadences échues à clore » (moitié écran de CAD75) : la liste des
   dossiers dont la dernière touche est en retard et que PERSONNE n'a clos,
   servie par `GET relance-etapes/cadences-echues/?jours=` (sélecteur
   `cadences_echues_a_clore`). Lecture seule : aucun geste de cet écran ne clôt
   une cadence. Charge utile = l'exemple COMMITTÉ
   (`apps/crm/contract_samples/cadences_echues.json`, PACT10). */
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

const ECHUES = exempleContrat('crm', 'cadences_echues')
const LIGNE = ECHUES.results[0]

const naviguer = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => ({
  ...(await importOriginal()),
  useNavigate: () => naviguer,
}))

vi.mock('../../api/crmApi', () => ({
  default: {
    getRelanceEtapesDues: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
    getCadencesEchues: vi.fn(),
    marquerRelanceEtapeFait: vi.fn(),
    marquerRelanceEtapeSautee: vi.fn(),
    reporterRelanceEtape: vi.fn(),
    annulerRelanceEtape: vi.fn(),
    arreterCadence: vi.fn(),
    getRelanceEtapeMessage: vi.fn(),
    whatsappRelanceEtape: vi.fn(),
  },
}))

import crmApi from '../../api/crmApi'
import RelancesDuJourWidget from './RelancesDuJourWidget'

beforeEach(() => {
  crmApi.getCadencesEchues.mockResolvedValue(reponseContrat('crm', 'cadences_echues'))
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

function mount() {
  return render(
    <MemoryRouter>
      <RelancesDuJourWidget />
    </MemoryRouter>,
  )
}

describe('RelancesDuJourWidget — CAD99 « cadences échues à clore »', () => {
  it('la section apparaît dès que le sélecteur renvoie au moins un lead (seuil affiché, envoyé)', async () => {
    mount()
    await waitFor(() => expect(crmApi.getCadencesEchues).toHaveBeenCalledWith({ jours: 7 }))
    expect(await screen.findByTestId('cad99-cadences-echues')).toBeInTheDocument()
    fireEvent.click(screen.getByText('1 cadence échue à clore'))
    expect(await screen.findByText(LIGNE.lead)).toBeInTheDocument()
    expect(screen.getByLabelText('Retard de plus de (jours)')).toHaveValue(7)
    expect(screen.getByText(new RegExp(`en retard de ${LIGNE.jours_de_retard} j`))).toBeInTheDocument()
  })

  it('aucun geste de cet écran ne clôt une cadence : une ligne ouvre la fiche, rien d’autre', async () => {
    mount()
    fireEvent.click(await screen.findByText('1 cadence échue à clore'))
    fireEvent.click(await screen.findByText(LIGNE.lead))
    expect(naviguer).toHaveBeenCalledWith(`/crm/leads?lead=${LIGNE.lead_id}`)
    // Les SEULS boutons de la section : le compteur (déplier) et la ligne
    // (ouvrir la fiche) — aucun geste de clôture.
    const section = screen.getByTestId('cad99-cadences-echues')
    const boutons = within(section).getAllByRole('button')
    expect(boutons).toHaveLength(2)
    expect(within(section).queryByRole('button', { name: /^(clore|clôturer|arrêter|passer au froid)/i }))
      .not.toBeInTheDocument()
    expect(crmApi.arreterCadence).not.toHaveBeenCalled()
    expect(crmApi.marquerRelanceEtapeFait).not.toHaveBeenCalled()
    expect(crmApi.marquerRelanceEtapeSautee).not.toHaveBeenCalled()
  })

  it('changer le seuil relit la liste avec le seuil AFFICHÉ', async () => {
    mount()
    fireEvent.click(await screen.findByText('1 cadence échue à clore'))
    fireEvent.change(screen.getByLabelText('Retard de plus de (jours)'), { target: { value: '14' } })
    await waitFor(() => expect(crmApi.getCadencesEchues).toHaveBeenCalledWith({ jours: 14 }))
  })

  it('aucune cadence échue : aucune section', async () => {
    crmApi.getCadencesEchues.mockResolvedValue(reponseContrat('crm', 'cadences_echues', 'exemple_vide'))
    mount()
    await waitFor(() => expect(crmApi.getCadencesEchues).toHaveBeenCalled())
    expect(screen.queryByTestId('cad99-cadences-echues')).not.toBeInTheDocument()
  })
})
