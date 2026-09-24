// CAD158 — « Votre facture, c'est pour un mois ou pour deux ? ». Décision
// fondateur du 21/09/2026 (Q24) : une facture bimestrielle est ramenée au
// mois AU MOMENT DE LA SAISIE, aucun champ « périodicité » n'est stocké, et la
// valeur normalisée est affichée. Montants = le contrat COMMITTÉ
// `apps/crm/contract_samples/lead_facture_periodicite.json` (PACT10) — le
// même exemple que le serveur affirme (`services.facture_au_mois`).
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { factureAuMois, initState } from '../draftCore'
import SectionEnergie from './SectionEnergie'
import { documentContrat } from '../../../../test/fixtures/contractSamples'

const CONTRAT = documentContrat('crm', 'lead_facture_periodicite')

afterEach(() => { cleanup(); vi.clearAllMocks() })

function rendre(lead = { id: 5 }) {
  const setField = vi.fn()
  const state = initState({ lead, mode: 'edit' })
  const vue = render(<SectionEnergie state={state} setField={setField} errors={{}} />)
  return { setField, vue }
}

describe('CAD158 — la facture est enregistrée au mois', () => {
  it('la règle pure est celle du serveur (même exemple de contrat)', () => {
    expect(factureAuMois(CONTRAT.corps.facture_hiver, CONTRAT.corps.facture_periodicite))
      .toBe(CONTRAT.exemple.facture_hiver)
    expect(factureAuMois('1301', 'bimestrielle')).toBe('650.50')
    expect(factureAuMois('', 'bimestrielle')).toBe('')
  })

  it('une facture de deux mois part AU MOIS', () => {
    const { setField } = rendre()
    fireEvent.change(screen.getByLabelText('La facture couvre'),
      { target: { value: CONTRAT.corps.facture_periodicite } })
    fireEvent.change(document.getElementById('lf-facture-hiver'),
      { target: { value: CONTRAT.corps.facture_hiver } })
    expect(setField).toHaveBeenCalledWith('facture_hiver', CONTRAT.exemple.facture_hiver)
    // La commerciale voit ce qu'elle a tapé (le montant de la facture).
    expect(document.getElementById('lf-facture-hiver')).toHaveValue(Number(CONTRAT.corps.facture_hiver))
  })

  it('la valeur normalisée est affichée sous le champ', () => {
    rendre({ id: 5, facture_hiver: CONTRAT.exemple.facture_hiver })
    fireEvent.change(screen.getByLabelText('La facture couvre'),
      { target: { value: 'bimestrielle' } })
    expect(screen.getByText(`Enregistré au mois : ${CONTRAT.exemple.facture_hiver} MAD/mois`))
      .toBeInTheDocument()
  })

  it('sur une facture d’un mois, rien ne change (comportement historique)', () => {
    const { setField } = rendre()
    fireEvent.change(document.getElementById('lf-facture-hiver'), { target: { value: '650' } })
    expect(setField).toHaveBeenCalledWith('facture_hiver', '650')
  })
})
