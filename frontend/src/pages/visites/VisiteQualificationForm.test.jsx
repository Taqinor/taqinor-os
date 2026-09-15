// VISITE-QUALIF — l'étape « Qualification client » de fin de visite terrain :
// les 6 questions à un tap montrent TOUJOURS leur défaut pré-sélectionné, le
// « Quoi changer ? » n'est requis que si le devis ne convient pas (garde
// client + erreur SERVEUR toutes deux sous le champ fautif, jamais un message
// générique), l'enregistrement poste le payload EXACT du contrat, et la
// visite non modifiable (validée) rend un résumé texte au lieu des chips.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const { qualifierVisite } = vi.hoisted(() => ({ qualifierVisite: vi.fn() }))
vi.mock('../../api/visitesApi', () => ({
  default: { qualifierVisite: (...a) => qualifierVisite(...a) },
}))

import VisiteQualificationForm from './VisiteQualificationForm'

const PAYLOAD_DEFAUT = {
  temperature: 'tiede',
  devis: 'convient',
  devis_details: '',
  decideur: 'seul',
  frein: 'aucun',
  declencheur: 'economies',
  rappel: 'demain_matin',
  conseil_closing: '',
}

beforeEach(() => { vi.clearAllMocks() })

describe('VisiteQualificationForm — VISITE-QUALIF', () => {
  it('affiche les 6 questions avec leur DÉFAUT déjà pré-sélectionné au montage', () => {
    render(<VisiteQualificationForm visiteId={7} qualification={null} onSaved={() => {}} />)
    expect(screen.getByRole('button', { name: 'Tiède' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Chaud — prêt à signer' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('button', { name: 'Le devis convient' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Seul' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Aucun' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Les économies' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Demain matin' })).toHaveAttribute('aria-pressed', 'true')
    // Le champ conditionnel « Quoi changer ? » n'apparaît PAS tant que le
    // devis convient (défaut) — jamais un champ requis inutilement affiché.
    expect(screen.queryByLabelText(/quoi changer/i)).not.toBeInTheDocument()
  })

  it('« Enregistrer » poste EXACTEMENT le payload par défaut quand rien n’a été touché', async () => {
    qualifierVisite.mockResolvedValue({ data: { id: 7, qualification: PAYLOAD_DEFAUT } })
    const user = userEvent.setup()
    const onSaved = vi.fn()
    render(<VisiteQualificationForm visiteId={7} qualification={null} onSaved={onSaved} />)
    await user.click(screen.getByRole('button', { name: /enregistrer la qualification/i }))
    expect(qualifierVisite).toHaveBeenCalledWith(7, PAYLOAD_DEFAUT)
    expect(await screen.findByRole('button', { name: /enregistrer la qualification/i })).not.toBeDisabled()
    expect(onSaved).toHaveBeenCalledWith({ id: 7, qualification: PAYLOAD_DEFAUT })
  })

  it('choisir « À modifier » exige « Quoi changer ? » — garde CLIENT sous le champ, aucun appel réseau', async () => {
    const user = userEvent.setup()
    render(<VisiteQualificationForm visiteId={7} qualification={null} onSaved={() => {}} />)
    await user.click(screen.getByRole('button', { name: /modifier/i }))
    expect(screen.getByLabelText(/quoi changer/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /enregistrer la qualification/i }))
    expect(await screen.findByText('Précisez ce qu’il faut changer.')).toBeInTheDocument()
    expect(qualifierVisite).not.toHaveBeenCalled()
  })

  it('« Quoi changer ? » rempli passe dans le payload devis_details, poste bien', async () => {
    qualifierVisite.mockResolvedValue({ data: { id: 7 } })
    const user = userEvent.setup()
    render(<VisiteQualificationForm visiteId={7} qualification={null} onSaved={() => {}} />)
    await user.click(screen.getByRole('button', { name: /modifier/i }))
    await user.type(screen.getByLabelText(/quoi changer/i), 'Ajouter une batterie')
    await user.click(screen.getByRole('button', { name: /enregistrer la qualification/i }))
    expect(qualifierVisite).toHaveBeenCalledWith(7, {
      ...PAYLOAD_DEFAUT,
      devis: 'a_modifier',
      devis_details: 'Ajouter une batterie',
    })
  })

  it('erreur SERVEUR (400 par champ) affichée sous le champ fautif exact, jamais un message générique', async () => {
    qualifierVisite.mockRejectedValue({
      response: { data: { frein: 'Choix de frein invalide.' } },
    })
    const user = userEvent.setup()
    render(<VisiteQualificationForm visiteId={7} qualification={null} onSaved={() => {}} />)
    await user.click(screen.getByRole('button', { name: /enregistrer la qualification/i }))
    expect(await screen.findByText('Choix de frein invalide.')).toBeInTheDocument()
  })

  it('lectureSeule (visite validée) rend un résumé texte, jamais les chips interactives', () => {
    render(
      <VisiteQualificationForm
        visiteId={7}
        lectureSeule
        qualification={{
          temperature: 'chaud', devis: 'convient', devis_details: '', decideur: 'seul',
          frein: 'prix', declencheur: 'economies', rappel: 'cette_semaine', conseil_closing: 'Aime la marque Deye.',
        }}
        onSaved={() => {}}
      />,
    )
    expect(screen.getByText('Chaud — prêt à signer')).toBeInTheDocument()
    expect(screen.getByText('Aime la marque Deye.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /enregistrer la qualification/i })).not.toBeInTheDocument()
    expect(screen.queryAllByRole('button')).toHaveLength(0)
  })

  it('lectureSeule sans qualification enregistrée affiche un texte de repli, jamais un cadre vide', () => {
    render(<VisiteQualificationForm visiteId={7} lectureSeule qualification={null} onSaved={() => {}} />)
    expect(screen.getByText('Qualification non renseignée.')).toBeInTheDocument()
  })
})
