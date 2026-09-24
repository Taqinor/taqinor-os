// CAD159 — [TRANCHÉ 21/09/2026] champs du site TOUJOURS éditables, jamais
// reposés. Un champ renseigné par le site affiche sa PROVENANCE, reste
// MODIFIABLE, et n'apparaît pas dans la liste des questions à poser (il se
// confirme). Charge utile = le contrat COMMITTÉ
// `apps/crm/contract_samples/lead_provenance_site.json` (PACT10).
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { champsSiteAPoser, initState } from '../draftCore'
import SectionDivers from './SectionDivers'
import { documentContrat } from '../../../../test/fixtures/contractSamples'

vi.mock('../../../../components/CustomFieldsInput', () => ({ default: () => null }))

const CONTRAT = documentContrat('crm', 'lead_provenance_site')
const RENSEIGNES = Object.keys(CONTRAT.exemple.provenance_site) // ownership, roof_age

afterEach(() => { cleanup(); vi.clearAllMocks() })

function rendre(lead) {
  const setField = vi.fn()
  const state = initState({ lead: { ...lead }, mode: 'edit' })
  render(<SectionDivers state={state} setField={setField} errors={{}} />)
  return { setField, state }
}

describe('CAD159 — champs du site : provenance visible, modifiables, jamais reposés', () => {
  it('la provenance de chaque champ renseigné par le site est affichée', () => {
    rendre(CONTRAT.exemple)
    for (const champ of RENSEIGNES) {
      const { valeur } = CONTRAT.exemple.provenance_site[champ]
      expect(screen.getByTestId(`champ-site-${champ}`)).toHaveTextContent(valeur)
    }
    expect(screen.getAllByText(/Saisie sur le site le /)).toHaveLength(RENSEIGNES.length)
  })

  it('un champ renseigné par le site RESTE modifiable (geste explicite)', () => {
    const { setField } = rendre(CONTRAT.exemple)
    fireEvent.click(screen.getByRole('button', { name: 'Modifier « Âge de la toiture (ans) »' }))
    const champ = screen.getByLabelText('Âge de la toiture (ans)')
    expect(champ).toBeEnabled()
    fireEvent.change(champ, { target: { value: '15' } })
    expect(setField).toHaveBeenCalledWith('roof_age', '15')
  })

  it('un champ renseigné n’apparaît PAS dans la liste des questions à poser', () => {
    const { state } = rendre(CONTRAT.exemple)
    const aPoser = champsSiteAPoser(state)
    for (const champ of RENSEIGNES) expect(aPoser).not.toContain(champ)
    // Les champs vides, eux, restent des questions.
    expect(aPoser).toContain('distributeur')
    const liste = screen.getByTestId('qualification-a-demander')
    expect(liste).not.toHaveTextContent("Statut d'occupation")
    expect(liste).not.toHaveTextContent('Âge de la toiture')
    expect(liste).toHaveTextContent('Horizon du projet')
  })

  it('un lead hors site : tout est à demander, rien n’est « à confirmer »', () => {
    rendre(CONTRAT.exemple_sans_site)
    expect(screen.queryByText('à confirmer')).toBeNull()
    expect(screen.getByTestId('qualification-a-demander')).toHaveTextContent("Statut d'occupation")
  })
})
