import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { toast } from '../../../ui'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import { formatMAD } from '../../../lib/format'
import { exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'

/* WIR280/WIR279 (XACC19) — États financiers PARAMÉTRABLES : le modèle, la
   validation de formule et l'évaluation existaient côté services sans AUCUN
   écran. La charge utile de `evaluer/` reprend EXACTEMENT le contrat committé
   (`apps/compta/contract_samples/etat_personnalise_evaluer.json`, WIR279) via
   `exempleContrat`/`reponseContrat` (PACT10/13, patron maison) — jamais un
   objet recopié à la main : une ligne « titre » porte un `valeurs` VIDE
   (jamais des zéros), et si le serveur change de forme, l'exemple committé
   change et ce test casse tout seul.

   `ListShell`/`DataTable` rend deux fois la même ligne (repli desktop +
   cartes mobile) : les requêtes sur la liste sont scopées à
   `[data-dt-table]` (même patron que `EmpruntsPage.test.jsx`). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  remove: vi.fn(),
  evaluer: vi.fn(),
  budgets: vi.fn(),
}))

vi.mock('../../../api/comptaApi', () => ({
  default: {
    etatsPersonnalises: { list: mocks.list, create: mocks.create, remove: mocks.remove, evaluer: mocks.evaluer },
    budgets: { list: mocks.budgets },
  },
}))

import EtatsPersonnalisesPage from './EtatsPersonnalisesPage.jsx'

// Contrat committé WIR279 — lu depuis le fichier réel, jamais recopié.
const EVALUATION = exempleContrat('compta', 'etat_personnalise_evaluer')
const [COLONNE_A, COLONNE_B] = EVALUATION.colonnes
const LIGNE_TITRE = EVALUATION.lignes.find((l) => l.type_ligne === 'titre')
const [LIGNE_CA, LIGNE_RESULTAT] = EVALUATION.lignes.filter((l) => l.type_ligne === 'total')

// `formatMAD` insère un espace fine insécable (Intl fr-FR) entre les groupes
// de milliers ; le normaliseur de texte par défaut de testing-library ne
// l'applique qu'au texte du DOM, pas à la chaîne de requête — comparer sans
// AUCUN espace des deux côtés rend le matcher robuste au type d'espace
// (même patron que `EmpruntsPage.test.jsx`).
function matchMontant(valeurDecimale) {
  const cible = formatMAD(valeurDecimale).replace(/\s/g, '')
  return (contenu) => (contenu || '').replace(/\s/g, '') === cible
}

// La liste (hors `evaluer/`) n'a pas de contrat_sample dédié : forme dérivée
// de `EtatPersonnaliseSerializer` (id/libelle/description/lignes/colonnes),
// alignée sur l'état évalué ci-dessus pour rester cohérente d'un bout à
// l'autre du test.
const ETAT = {
  id: EVALUATION.etat, libelle: EVALUATION.libelle, description: 'CPC simplifié',
  lignes: [
    { id: LIGNE_TITRE.id, ordre: 0, libelle: LIGNE_TITRE.libelle, type_ligne: 'titre', formule: '' },
    { id: LIGNE_CA.id, ordre: 1, libelle: LIGNE_CA.libelle, type_ligne: 'total', formule: '+70' },
  ],
  colonnes: [
    {
      id: COLONNE_A.id, ordre: 0, libelle: COLONNE_A.libelle, type_colonne: COLONNE_A.type_colonne,
      date_debut: '2026-01-01', date_fin: '2026-12-31', budget: null,
    },
  ],
  created_by: 1, date_creation: '2026-01-01T09:00:00Z',
}

function mount() {
  return render(
    <MemoryRouter>
      <ThemeProvider><EtatsPersonnalisesPage /></ThemeProvider>
    </MemoryRouter>,
  )
}

async function tableDesktop(container) {
  await waitFor(() => expect(container.querySelector('[data-dt-table]')).toBeTruthy())
  return within(container.querySelector('[data-dt-table]'))
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: [ETAT] })
  mocks.budgets.mockResolvedValue({ data: [] })
  mocks.create.mockResolvedValue({ data: { id: 6 } })
  mocks.remove.mockResolvedValue({ data: {} })
  mocks.evaluer.mockResolvedValue(reponseContrat('compta', 'etat_personnalise_evaluer'))
})

describe('EtatsPersonnalisesPage — liste (WIR280)', () => {
  it('affiche la liste des états personnalisés', async () => {
    const { container } = mount()
    const table = await tableDesktop(container)
    expect(await table.findByText('Compte de résultat simplifié')).toBeInTheDocument()
  })
})

describe('EtatsPersonnalisesPage — constructeur lignes/formules (WIR280/WIR279)', () => {
  it('crée un état avec une ligne à formule et une colonne période', async () => {
    const user = userEvent.setup()
    const { container } = mount()
    await tableDesktop(container)

    await user.click(screen.getByRole('button', { name: 'Nouvel état' }))
    // Le libellé de l'état est `required` (astérisque aria-hidden posé par
    // `Label` — inclus dans le textContent brut, pas dans le nom accessible) :
    // requête en préfixe plutôt qu'une égalité exacte.
    await user.type(screen.getByLabelText(/^Libellé/, { selector: '#etat-libelle' }), 'Bilan simplifié')
    await user.type(screen.getByLabelText('Libellé', { selector: '#ligne-libelle-0' }), 'ACTIF')
    await user.selectOptions(screen.getByLabelText('Type', { selector: '#ligne-type-0' }), 'total')
    await user.type(screen.getByLabelText(/Formule/), '+21,+22')
    await user.type(screen.getByLabelText('Libellé', { selector: '#colonne-libelle-0' }), '2027')

    await user.click(screen.getByRole('button', { name: "Enregistrer l'état" }))

    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith({
      libelle: 'Bilan simplifié',
      description: '',
      lignes: [{ ordre: 0, libelle: 'ACTIF', type_ligne: 'total', formule: '+21,+22' }],
      colonnes: [{ ordre: 0, libelle: '2027', type_colonne: 'periode', date_debut: null, date_fin: null, budget: null }],
    }))
  })
})

describe('EtatsPersonnalisesPage — rendu évalué + export (WIR280/WIR279)', () => {
  it('évalue un état et rend EXACTEMENT le contrat committé (titre sans valeur)', async () => {
    const user = userEvent.setup()
    const { container } = mount()
    const table = await tableDesktop(container)
    await table.findByText('Compte de résultat simplifié')

    await user.click(table.getByRole('button', { name: 'Évaluer' }))

    await waitFor(() => expect(mocks.evaluer).toHaveBeenCalledWith(EVALUATION.etat))
    expect(await screen.findByText(LIGNE_CA.libelle)).toBeInTheDocument()
    // Colonnes dynamiques = celles renvoyées par le serveur.
    expect(screen.getByRole('columnheader', { name: COLONNE_A.libelle })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: COLONNE_B.libelle })).toBeInTheDocument()
    // Montants EXACTS du contrat, comparés au rendu RÉEL de `formatMAD`.
    expect(screen.getByText(matchMontant(LIGNE_CA.valeurs[COLONNE_A.id])))
      .toBeInTheDocument()
    expect(screen.getByText(matchMontant(LIGNE_RESULTAT.valeurs[COLONNE_B.id])))
      .toBeInTheDocument()
    // La ligne « titre » n'affiche AUCUNE valeur — jamais un 0 inventé.
    const ligneTitre = screen.getByText(LIGNE_TITRE.libelle).closest('tr')
    within(ligneTitre).getAllByRole('cell').slice(1).forEach((cell) => {
      expect(cell).toHaveTextContent('')
    })
  })

  it('exporte le rendu évalué en CSV (ComptaTable)', async () => {
    const user = userEvent.setup()
    const { container } = mount()
    const table = await tableDesktop(container)
    await table.findByText('Compte de résultat simplifié')

    await user.click(table.getByRole('button', { name: 'Évaluer' }))
    await screen.findByText(LIGNE_CA.libelle)

    expect(screen.getByRole('button', { name: 'Exporter CSV' })).toBeInTheDocument()
  })
})

describe('EtatsPersonnalisesPage — suppression (WIR280)', () => {
  it('supprime un état', async () => {
    const user = userEvent.setup()
    const { container } = mount()
    const table = await tableDesktop(container)
    await table.findByText('Compte de résultat simplifié')

    await user.click(table.getByRole('button', { name: 'Supprimer' }))

    await waitFor(() => expect(mocks.remove).toHaveBeenCalledWith(ETAT.id))
  })
})

describe('EtatsPersonnalisesPage — formule illégale (WIR280/WIR279)', () => {
  it('affiche le message FR d’une formule invalide en toast (400, FormuleEtatInvalideError) plutôt que de planter', async () => {
    const user = userEvent.setup()
    // Miroir de EtatPersonnaliseViewSet.evaluer : une formule illégale rend
    // {'detail': str(exc)} en 400 — jamais un 500 (selectors.
    // FormuleEtatInvalideError est une exception MÉTIER, pas une
    // ValidationError Django).
    mocks.evaluer.mockRejectedValueOnce({
      response: { data: { detail: "Terme invalide : « +XY » n'est pas un préfixe de compte reconnu." } },
    })
    const erreur = vi.spyOn(toast, 'error')
    const { container } = mount()
    const table = await tableDesktop(container)
    await table.findByText('Compte de résultat simplifié')

    await user.click(table.getByRole('button', { name: 'Évaluer' }))

    await waitFor(() => expect(erreur).toHaveBeenCalledWith(
      "Terme invalide : « +XY » n'est pas un préfixe de compte reconnu.",
    ))
  })
})
