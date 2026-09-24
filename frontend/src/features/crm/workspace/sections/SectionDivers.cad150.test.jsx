// CAD150 — T3 : les champs captés par le site étaient figés en lecture seule,
// même VIDES. Décision fondateur du 21/09/2026 : TOUJOURS éditables, mais une
// valeur venue du site s'affiche « à confirmer » et n'est jamais écrasée sans
// un geste explicite. Charge utile = le contrat COMMITTÉ
// `apps/crm/contract_samples/lead_provenance_site.json` (PACT10).
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { initState } from '../draftCore'
import SectionDivers from './SectionDivers'
import SectionEnergie from './SectionEnergie'
import SectionPipeline from './SectionPipeline'
import { documentContrat } from '../../../../test/fixtures/contractSamples'

vi.mock('../../../../components/CustomFieldsInput', () => ({ default: () => null }))
vi.mock('../../../../api/crmApi', () => ({
  default: {
    getRelanceEtapesLead: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    getCanaux: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))

const CONTRAT = documentContrat('crm', 'lead_provenance_site')

afterEach(() => { cleanup(); vi.clearAllMocks() })

function rendre(Section, lead) {
  const setField = vi.fn()
  const state = initState({ lead: { ...lead }, mode: 'edit' })
  render(<Section state={state} setField={setField} errors={{}} refData={{}} />)
  return setField
}

describe('CAD150 — champs captés par le site, toujours éditables', () => {
  it('un champ VIDE est directement saisissable (lead Meta, walk-in, appel)', () => {
    const setField = rendre(SectionDivers, CONTRAT.exemple_sans_site)
    fireEvent.change(screen.getByLabelText("Statut d'occupation"), { target: { value: 'locataire' } })
    expect(setField).toHaveBeenCalledWith('ownership', 'locataire')
  })

  it('un champ RENSEIGNÉ par le site s’affiche « à confirmer » et n’écrase rien sans geste', () => {
    const setField = rendre(SectionDivers, CONTRAT.exemple)
    const bloc = screen.getByTestId('champ-site-ownership')
    expect(bloc).toHaveTextContent(CONTRAT.exemple.provenance_site.ownership.valeur)
    expect(bloc).toHaveTextContent('à confirmer')
    // Aucun contrôle éditable tant que la commerciale ne l'a pas demandé.
    expect(screen.queryByRole('combobox', { name: "Statut d'occupation" })).toBeNull()
    expect(setField).not.toHaveBeenCalled()
    // La provenance est dite sous le champ.
    expect(screen.getAllByText(/Saisie sur le site le/).length).toBeGreaterThan(0)
    // Le geste explicite rend le champ modifiable.
    fireEvent.click(screen.getByRole('button', { name: "Modifier « Statut d'occupation »" }))
    fireEvent.change(screen.getByRole('combobox', { name: "Statut d'occupation" }),
      { target: { value: 'locataire' } })
    expect(setField).toHaveBeenCalledWith('ownership', 'locataire')
  })

  it('après écrasement : le contrôle est libre, la provenance reste lisible', () => {
    rendre(SectionDivers, CONTRAT.exemple_ecrasee)
    expect(screen.queryByTestId('champ-site-ownership')).toBeNull()
    expect(screen.getByRole('combobox', { name: "Statut d'occupation" })).toHaveValue('locataire')
    expect(screen.getByText(/modifiée depuis sur la fiche/)).toBeInTheDocument()
  })

  it('le distributeur (profil énergétique) se saisit quand il manque', () => {
    const setField = rendre(SectionEnergie, CONTRAT.exemple)
    fireEvent.change(screen.getByRole('combobox', { name: "Distributeur d'électricité" }),
      { target: { value: CONTRAT.exemple_ecrasee.distributeur } })
    expect(setField).toHaveBeenCalledWith('distributeur', CONTRAT.exemple_ecrasee.distributeur)
  })

  it('la préférence de contact a enfin son contrôle (Suivi commercial)', () => {
    const setField = vi.fn()
    const state = initState({ mode: 'create' })
    render(<SectionPipeline state={state} setField={setField} errors={{}} refData={{}} />)
    fireEvent.change(screen.getByRole('combobox', { name: 'Préférence de contact' }),
      { target: { value: 'whatsapp_only' } })
    expect(setField).toHaveBeenCalledWith('contact_preference', 'whatsapp_only')
  })
})
