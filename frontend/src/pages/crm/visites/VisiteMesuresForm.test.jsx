// VT10 — le formulaire de mesures n'avale/ne rejette JAMAIS un nombre tapé
// (règle maison), et affiche l'erreur SERVEUR sous le champ fautif exact
// (PATCH .../mesures/ -> 400 {erreurs:{champ:message}}).
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const { patchVisiteMesures } = vi.hoisted(() => ({ patchVisiteMesures: vi.fn() }))
vi.mock('../../../api/crmApi', () => ({
  default: { patchVisiteMesures: (...a) => patchVisiteMesures(...a) },
}))

import VisiteMesuresForm from './VisiteMesuresForm'

beforeEach(() => { vi.clearAllMocks() })

describe('VisiteMesuresForm — VT10', () => {
  it('accepte un nombre décimal tapé caractère par caractère sans le rejeter (step="any", noValidate)', async () => {
    const user = userEvent.setup()
    render(
      <VisiteMesuresForm visiteId={7} categorie="toiture" libelle="Toiture" valeurs={{}} onSaved={() => {}} />,
    )
    const input = screen.getByLabelText(/Longueur de la zone utile/i)
    // Une saisie décimale progressive (« 1 » puis « 2 » puis « , » puis « 5 »)
    // ne doit JAMAIS être tronquée ou rejetée par le champ.
    await user.type(input, '12.5')
    expect(input).toHaveValue(12.5)
    expect(input).toHaveAttribute('step', 'any')
    expect(input.closest('form')).toHaveAttribute('novalidate')
  })

  it('affiche l’erreur SERVEUR sous le champ fautif exact, jamais un message générique', async () => {
    patchVisiteMesures.mockRejectedValue({
      response: { data: { erreurs: { pente_deg: 'La pente doit être comprise entre 0 et 90°.' } } },
    })
    const user = userEvent.setup()
    render(
      <VisiteMesuresForm visiteId={7} categorie="toiture" libelle="Toiture" valeurs={{ pente_deg: 15 }} onSaved={() => {}} />,
    )
    await user.click(screen.getByRole('button', { name: /enregistrer les mesures/i }))
    expect(await screen.findByText('La pente doit être comprise entre 0 et 90°.')).toBeInTheDocument()
  })

  it('categorie sans schéma (general) ne rend rien — jamais un formulaire vide inventé', () => {
    const { container } = render(
      <VisiteMesuresForm visiteId={7} categorie="general" libelle="Général" valeurs={{}} onSaved={() => {}} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('lectureSeule désactive les champs et masque le bouton d’enregistrement', () => {
    render(
      <VisiteMesuresForm visiteId={7} categorie="toiture" libelle="Toiture" valeurs={{}} lectureSeule onSaved={() => {}} />,
    )
    expect(screen.getByLabelText(/Longueur de la zone utile/i)).toBeDisabled()
    expect(screen.queryByRole('button', { name: /enregistrer les mesures/i })).not.toBeInTheDocument()
  })
})
