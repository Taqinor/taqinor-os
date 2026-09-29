// VT10 — le formulaire de mesures n'avale/ne rejette JAMAIS un nombre tapé
// (règle maison), et affiche l'erreur SERVEUR sous le champ fautif exact
// (PATCH .../mesures/ -> 400 {erreurs:{champ:message}}).
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const { patchVisiteMesures } = vi.hoisted(() => ({ patchVisiteMesures: vi.fn() }))
vi.mock('../../api/visitesApi', () => ({
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

  // ERR-QAH-VISITES-COUVERTURE-ENUM-SANS-AFFORDANCE — « Type de couverture »
  // et « État de la couverture » étaient des champs texte libres qui
  // n'acceptaient que des codes internes (400 sur « Tuile »/« Bon état »,
  // sans jamais montrer les valeurs permises). Ils rendent désormais des
  // listes (role combobox, comme « Orientation »), plus jamais des textbox.
  it('« Type de couverture » et « État de la couverture » rendent des listes, plus des champs texte libres', () => {
    render(
      <VisiteMesuresForm visiteId={7} categorie="toiture" libelle="Toiture" valeurs={{}} onSaved={() => {}} />,
    )
    expect(screen.getByLabelText('Type de couverture')).toHaveAttribute('role', 'combobox')
    expect(screen.getByLabelText('État de la couverture')).toHaveAttribute('role', 'combobox')
    expect(screen.queryByRole('textbox', { name: 'Type de couverture' })).not.toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: 'État de la couverture' })).not.toBeInTheDocument()
  })

  it('« Type de couverture » propose exactement les codes serveur (Tuile, Tôle, Bac acier, Béton, Fibrociment, Autre)', async () => {
    const user = userEvent.setup()
    render(
      <VisiteMesuresForm visiteId={7} categorie="toiture" libelle="Toiture" valeurs={{}} onSaved={() => {}} />,
    )
    await user.click(screen.getByLabelText('Type de couverture'))
    for (const libelle of ['Tuile', 'Tôle', 'Bac acier', 'Béton', 'Fibrociment', 'Autre']) {
      expect(await screen.findByRole('option', { name: libelle })).toBeInTheDocument()
    }
  })

  it('« État de la couverture » propose exactement Bon/Moyen/Mauvais', async () => {
    const user = userEvent.setup()
    render(
      <VisiteMesuresForm visiteId={7} categorie="toiture" libelle="Toiture" valeurs={{}} onSaved={() => {}} />,
    )
    await user.click(screen.getByLabelText('État de la couverture'))
    for (const libelle of ['Bon', 'Moyen', 'Mauvais']) {
      expect(await screen.findByRole('option', { name: libelle })).toBeInTheDocument()
    }
  })
})
