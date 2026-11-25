// AGEN12 — bandeau « La conception a changé » de l'écran devis. Les réponses
// mockées sont celles du contrat committé `conception_lead.json` (PACT10).
// Nouveau fichier car : composant neuf.
//
// Run : npx vitest run src/pages/ventes/generator/BandeauConception.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import { documentContrat, exempleContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/ventesApi', () => ({
  default: { getConceptionLead: vi.fn(), mettreAJourConception: vi.fn(), reviserDevis: vi.fn() },
}))

import ventesApi from '../../../api/ventesApi'
import BandeauConception from './BandeauConception'

const CONCEPTION = exempleContrat('ventes', 'conception_lead')
const MISE_A_JOUR = documentContrat('ventes', 'conception_lead').mettre_a_jour_conception.reponse
const LISTE = CONCEPTION.brouillons_a_mettre_a_jour[0]
const ECART = CONCEPTION.ecart_devis[0]
const panneaux = (q) => [{ id: 1, designation: 'Panneau Canadian Solar 710W', quantite: String(q), variante: '' }]

function rendre(devis, onMisAJour = vi.fn()) {
  const vue = render(<MemoryRouter><BandeauConception devis={devis} onMisAJour={onMisAJour} /></MemoryRouter>)
  return { ...vue, onMisAJour }
}

beforeEach(() => {
  vi.clearAllMocks()
  ventesApi.getConceptionLead.mockResolvedValue({ data: CONCEPTION })
  ventesApi.mettreAJourConception.mockResolvedValue({ data: MISE_A_JOUR })
})

describe('AGEN12 — bandeau « La conception a changé »', () => {
  it('brouillon retouché : le bandeau, « Mettre à jour », puis ce qui est appliqué et ce qui ne l’est pas', async () => {
    const devis = { id: LISTE.devis, reference: LISTE.reference, statut: 'brouillon', lead: CONCEPTION.lead,
      lignes: panneaux(8) }
    const { onMisAJour } = rendre(devis)
    const bandeau = await screen.findByTestId('bandeau-conception')
    const cible = CONCEPTION.valeurs[CONCEPTION.option_retenue].nb_panneaux.valeur
    expect(bandeau.textContent).toContain(`La conception de ce lead a changé : panneaux 8 → ${cible}`)
    expect(bandeau.textContent).toContain(LISTE.motif)
    await act(async () => { fireEvent.click(screen.getByTestId('bandeau-conception-mettre-a-jour')) })
    expect(ventesApi.mettreAJourConception).toHaveBeenCalledWith(LISTE.devis)
    expect(onMisAJour).toHaveBeenCalled()
    const resultat = await screen.findByTestId('bandeau-conception-resultat')
    expect(resultat.textContent).toContain('Brouillon mis à jour sur la conception du lead.')
    expect(screen.getByTestId('bandeau-conception-non-appliquees').textContent)
      .toContain(MISE_A_JOUR.non_appliquees[0].raison)
  })

  it('brouillon intact (non listé) : aucun bandeau', async () => {
    const { container } = rendre({ id: 999, reference: 'DEV-X', statut: 'brouillon', lead: CONCEPTION.lead,
      lignes: panneaux(8) })
    await waitFor(() => expect(ventesApi.getConceptionLead).toHaveBeenCalledWith(CONCEPTION.lead))
    await act(async () => {})
    expect(container.textContent).toBe('')
  })

  it('devis envoyé dont la conception a bougé : « Réviser le devis », jamais « Mettre à jour »', async () => {
    rendre({ id: 14, reference: ECART.devis_ref, statut: 'envoye', lead: CONCEPTION.lead, lignes: panneaux(14) })
    const bandeau = await screen.findByTestId('bandeau-conception-envoye')
    expect(bandeau.textContent).toContain(`${ECART.valeur} ${ECART.devis} → ${ECART.conception}`)
    expect(screen.getByTestId('bandeau-conception-reviser').textContent).toBe('Réviser le devis')
    expect(screen.queryByTestId('bandeau-conception-mettre-a-jour')).toBeNull()
  })

  it('sans lead : rien n’est demandé', () => {
    const { container } = rendre({ id: 5, reference: 'DEV-Y', statut: 'brouillon', lead: null, lignes: [] })
    expect(container.textContent).toBe('')
    expect(ventesApi.getConceptionLead).not.toHaveBeenCalled()
  })
})
