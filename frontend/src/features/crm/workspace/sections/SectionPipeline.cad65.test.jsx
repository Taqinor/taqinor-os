// CAD65 — la civilité est une DONNÉE du lead (facultative), plus un « M. »
// codé en dur dans les textes. Choix et corps = le contrat COMMITTÉ
// `apps/crm/contract_samples/lead_civilite.json` (PACT10) — jamais retapés.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { documentContrat } from '../../../../test/fixtures/contractSamples'
import { initState, SECTION_FIELDS, TRACKED_KEYS, buildCreateDefaults } from '../draftCore'
import fieldLabels from '../fieldLabels'
import SectionPipeline from './SectionPipeline'

vi.mock('../../../../api/crmApi', () => ({
  default: {
    initialiserRelance: vi.fn(),
    arreterCadence: vi.fn(),
    getRelanceEtapesLead: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
    getCanaux: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))

const CONTRAT = documentContrat('crm', 'lead_civilite')
const REF_DATA = { users: [], tagOptions: [], motifOptions: [] }

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderSection(lead = {}, errors = {}) {
  const setField = vi.fn()
  const state = initState({ lead: { id: 77, ...lead }, mode: 'edit' })
  render(<SectionPipeline state={state} setField={setField} errors={errors} refData={REF_DATA} />)
  return setField
}

describe('CAD65 — le champ Civilité du Suivi commercial', () => {
  it('propose exactement les choix du serveur, plus « non renseignée »', () => {
    renderSection()
    const select = screen.getByLabelText('Civilité')
    const valeurs = [...select.querySelectorAll('option')].map((o) => o.value)
    expect(valeurs).toEqual(['', ...Object.keys(CONTRAT.choix)])
    // Vide par défaut : salutation neutre, jamais « M. » présélectionné.
    expect(select).toHaveValue('')
  })

  it('le choix part dans le corps du contrat', async () => {
    const user = userEvent.setup()
    const setField = renderSection()
    await user.selectOptions(screen.getByLabelText('Civilité'), CONTRAT.corps.civilite)
    expect(setField).toHaveBeenCalledWith('civilite', CONTRAT.corps.civilite)
  })

  it('la valeur relue du serveur est affichée', () => {
    renderSection({ civilite: CONTRAT.exemple.civilite })
    expect(screen.getByLabelText('Civilité')).toHaveValue(CONTRAT.exemple.civilite)
  })

  it('un refus serveur s’affiche SOUS le champ', () => {
    renderSection({}, { civilite: 'Choix invalide.' })
    expect(screen.getByLabelText('Civilité')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByText('Choix invalide.')).toBeTruthy()
  })

  it('le champ est suivi, rangé au Suivi commercial, vide à la création et libellé', () => {
    expect(TRACKED_KEYS).toContain('civilite')
    expect(SECTION_FIELDS.pipeline).toContain('civilite')
    expect(buildCreateDefaults().civilite).toBe('')
    expect(fieldLabels.civilite).toEqual(
      { label: 'Civilité', section: 'pipeline', inputId: 'lf-civilite' })
  })
})
