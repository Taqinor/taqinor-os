// CAD48 — le champ « Relance le » ment sur ce qu'il fait : sur un lead à
// cadence active, un PATCH de `relance_date` n'ajoute pas un rappel — il
// déplace la PROCHAINE touche ET tout le reste du plan
// (`reporter_prochaine_touche`). Ce test prouve que la mention n'apparaît
// QUE quand une cadence est réellement active (au moins une étape encore
// `a_faire`), lue via `crmApi.getRelanceEtapesLead` (même appel que
// `CadenceFrise`) — jamais un texte affiché sans vérité serveur derrière.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { initState } from '../draftCore'
import SectionPipeline from './SectionPipeline'
// Étapes RÉALISTES (mêmes champs que le serveur, exemple COMMITTÉ) plutôt
// que des objets minimaux : `CadenceFrise` (rendue à côté, même leadId, même
// `crmApi.getRelanceEtapesLead`) lit `due_at`/`canal`/`cadence`/`ordre` — un
// objet tronqué la ferait planter pour une raison SANS RAPPORT avec ce test.
import { exempleContrat } from '../../../../test/fixtures/contractSamples'

vi.mock('../../../../api/crmApi', () => ({
  default: {
    initialiserRelance: vi.fn(),
    arreterCadence: vi.fn(),
    getRelanceEtapesLead: vi.fn(),
    getCanaux: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))

import crmApi from '../../../../api/crmApi'

const ETAPE_MODELE = exempleContrat('crm', 'relance_etape_v2').results[0]

afterEach(() => { cleanup(); vi.clearAllMocks() })

const REF_DATA = { users: [], tagOptions: [], motifOptions: [] }

function renderSection(over = {}) {
  const state = initState({ lead: { id: 77, ...over }, mode: 'edit' })
  return render(
    <SectionPipeline state={state} setField={vi.fn()} errors={{}} refData={REF_DATA} />,
  )
}

describe('SectionPipeline — CAD48 (« Relance le » dit la vérité)', () => {
  it('sur un lead à cadence active (une étape encore a_faire), la mention est affichée', async () => {
    crmApi.getRelanceEtapesLead.mockResolvedValue({
      data: {
        count: 2,
        results: [
          { ...ETAPE_MODELE, id: 1, statut: 'fait' },
          { ...ETAPE_MODELE, id: 2, statut: 'a_faire' },
        ],
      },
    })
    renderSection()
    expect(await screen.findByTestId('cad48-relance-le-note')).toBeInTheDocument()
  })

  it('sur un lead sans cadence (aucune étape a_faire), la mention n\'est PAS affichée', async () => {
    crmApi.getRelanceEtapesLead.mockResolvedValue({
      data: { count: 1, results: [{ ...ETAPE_MODELE, id: 1, statut: 'fait' }] },
    })
    renderSection()
    await waitFor(() => expect(crmApi.getRelanceEtapesLead).toHaveBeenCalledWith(77))
    expect(screen.queryByTestId('cad48-relance-le-note')).not.toBeInTheDocument()
  })

  it('sur un lead sans AUCUN plan de relance (liste vide), la mention n\'est PAS affichée', async () => {
    crmApi.getRelanceEtapesLead.mockResolvedValue({ data: { count: 0, results: [] } })
    renderSection()
    await waitFor(() => expect(crmApi.getRelanceEtapesLead).toHaveBeenCalledWith(77))
    expect(screen.queryByTestId('cad48-relance-le-note')).not.toBeInTheDocument()
  })

  it('en création (aucun leadId), aucun appel réseau et aucune mention', () => {
    crmApi.getRelanceEtapesLead.mockResolvedValue({ data: { count: 0, results: [] } })
    const state = initState({ mode: 'create' })
    render(<SectionPipeline state={state} setField={vi.fn()} errors={{}} refData={REF_DATA} />)
    expect(crmApi.getRelanceEtapesLead).not.toHaveBeenCalled()
    expect(screen.queryByTestId('cad48-relance-le-note')).not.toBeInTheDocument()
  })
})
