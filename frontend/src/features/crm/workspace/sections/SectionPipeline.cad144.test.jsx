// CAD144 — coopérative / comité industriel : un contact SECONDAIRE (nom +
// téléphone) sur la fiche, sans aucune automatisation. Valeurs = le contrat
// COMMITTÉ `apps/crm/contract_samples/lead_contact_secondaire.json` (PACT10),
// jamais un objet retapé.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { initState } from '../draftCore'
import SectionPipeline from './SectionPipeline'
import { documentContrat } from '../../../../test/fixtures/contractSamples'

vi.mock('../../../../api/crmApi', () => ({
  default: {
    initialiserRelance: vi.fn(),
    arreterCadence: vi.fn(),
    getRelanceEtapesLead: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    getCanaux: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))

const CONTRAT = documentContrat('crm', 'lead_contact_secondaire')
const REF_DATA = { users: [], tagOptions: [], motifOptions: [] }

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderSection(lead, setField = vi.fn()) {
  // Mode CRÉATION : les champs du Suivi commercial sont rendus sans la frise
  // (aucun appel réseau à orchestrer) — le bloc CAD144 est le même.
  const state = { ...initState({ mode: 'create' }), server: { ...lead } }
  render(<SectionPipeline state={state} setField={setField} errors={{}} refData={REF_DATA} />)
  return setField
}

describe('SectionPipeline — CAD144 (contact secondaire)', () => {
  it('affiche le nom et le téléphone servis par le serveur', () => {
    renderSection(CONTRAT.exemple)
    expect(screen.getByLabelText('Contact secondaire (nom)'))
      .toHaveValue(CONTRAT.exemple.contact_secondaire_nom)
    expect(screen.getByLabelText('Contact secondaire (téléphone)'))
      .toHaveValue(CONTRAT.exemple.contact_secondaire_telephone)
    // Dit, noir sur blanc, qu'aucune relance ne part vers lui.
    expect(screen.getByTestId('contact-secondaire'))
      .toHaveTextContent('Aucune relance automatique')
  })

  it('la saisie part par les clés du CORPS du contrat', () => {
    const setField = renderSection({})
    fireEvent.change(screen.getByLabelText('Contact secondaire (nom)'),
      { target: { value: CONTRAT.corps.contact_secondaire_nom } })
    fireEvent.change(screen.getByLabelText('Contact secondaire (téléphone)'),
      { target: { value: CONTRAT.corps.contact_secondaire_telephone } })
    expect(setField).toHaveBeenCalledWith(
      'contact_secondaire_nom', CONTRAT.corps.contact_secondaire_nom)
    expect(setField).toHaveBeenCalledWith(
      'contact_secondaire_telephone', CONTRAT.corps.contact_secondaire_telephone)
  })

  it('sans droit PII : le téléphone est verrouillé, le nom reste visible', () => {
    renderSection(CONTRAT.exemple_pii_masquee)
    expect(screen.getByLabelText('Contact secondaire (téléphone)')).toBeDisabled()
    expect(screen.getByLabelText('Contact secondaire (nom)'))
      .toHaveValue(CONTRAT.exemple_pii_masquee.contact_secondaire_nom)
  })
})
