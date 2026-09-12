/* NTESG19 — assistant « Créer un objectif de trajectoire ».
 *
 * Ce que le test PROUVE :
 *   - aucune SAISIE LIBRE : le code vient d'une liste servie par le serveur ;
 *   - le DOUBLON d'objectif actif est refusé AVANT l'appel serveur, avec un
 *     message qui NOMME l'année en conflit (critère d'acceptation) ;
 *   - l'aperçu de trajectoire est une interpolation des DEUX points saisis —
 *     aucune valeur inventée ;
 *   - une société sans indicateur le DIT au lieu d'ouvrir une saisie libre ;
 *   - l'erreur serveur est affichée.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

const { codesDisponibles, creerObjectif, navigate } = vi.hoisted(() => ({
  codesDisponibles: vi.fn(),
  creerObjectif: vi.fn(),
  navigate: vi.fn(),
}))

vi.mock('../../api/esgApi', () => ({
  default: {
    objectifs: { codesDisponibles, create: creerObjectif },
  },
}))
vi.mock('react-router-dom', async () => {
  const reel = await vi.importActual('react-router-dom')
  return { ...reel, useNavigate: () => navigate }
})

import WizardObjectifTrajectoire from './WizardObjectifTrajectoire'
import { trajectoireLineaire } from './trajectoireLineaire'

const CODES = [
  {
    code: 'ENV-CO2', libelle: 'Émissions de CO2', pilier: 'environnement',
    unite: 'tCO2e', objectifs_actifs: [2030],
  },
  {
    code: 'SOC-FORM', libelle: 'Heures de formation', pilier: 'social',
    unite: 'h', objectifs_actifs: [],
  },
]

function monter() {
  return render(
    <ThemeProvider>
      <MemoryRouter>
        <WizardObjectifTrajectoire />
      </MemoryRouter>
    </ThemeProvider>,
  )
}

async function allerEtape2(user, code = 'SOC-FORM') {
  await screen.findByTestId('esg-wizard-suggestions')
  await user.click(screen.getByRole('button', { name: new RegExp(code) }))
  await user.click(screen.getByTestId('esg-wizard-suivant-1'))
}

async function remplir(user, { ref = '100', anneeRef = '2024',
  cible = '50', anneeCible = '2028' } = {}) {
  const champRef = screen.getByLabelText('Valeur de référence')
  const champAnneeRef = screen.getByLabelText('Année de référence')
  const champCible = screen.getByLabelText('Valeur cible')
  const champAnneeCible = screen.getByLabelText('Année cible')
  await user.clear(champRef); await user.type(champRef, ref)
  await user.clear(champAnneeRef); await user.type(champAnneeRef, anneeRef)
  await user.clear(champCible); await user.type(champCible, cible)
  await user.clear(champAnneeCible); await user.type(champAnneeCible, anneeCible)
}

describe('NTESG19 — assistant objectif de trajectoire', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    codesDisponibles.mockResolvedValue({ data: CODES })
    creerObjectif.mockResolvedValue({ data: { id: 9 } })
  })

  // ── pure fonction d'aperçu ───────────────────────────────────────────
  it('interpole la trajectoire entre les deux points saisis', () => {
    const points = trajectoireLineaire({
      anneeReference: 2024, valeurReference: 100,
      anneeCible: 2028, valeurCible: 50,
    })
    expect(points).toHaveLength(5)
    expect(points[0]).toEqual({ annee: 2024, valeur: 100 })
    expect(points[4]).toEqual({ annee: 2028, valeur: 50 })
    expect(points[2].valeur).toBe(75)
  })

  it('ne produit aucun point si les années sont incohérentes', () => {
    expect(trajectoireLineaire({
      anneeReference: 2028, valeurReference: 100,
      anneeCible: 2024, valeurCible: 50,
    })).toEqual([])
  })

  // ── écran ────────────────────────────────────────────────────────────
  it('propose les codes du serveur, jamais une saisie libre', async () => {
    monter()
    await screen.findByTestId('esg-wizard-suggestions')
    expect(screen.getByRole('button', { name: /ENV-CO2/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /SOC-FORM/ })).toBeInTheDocument()
    // Le champ de recherche FILTRE, il ne crée rien.
    expect(screen.getByLabelText('Rechercher un indicateur'))
      .toHaveValue('')
    expect(screen.getByTestId('esg-wizard-suivant-1')).toBeDisabled()
  })

  it('filtre les suggestions', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByTestId('esg-wizard-suggestions')
    await user.type(screen.getByLabelText('Rechercher un indicateur'), 'form')
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /ENV-CO2/ })).toBeNull()
    })
    expect(screen.getByRole('button', { name: /SOC-FORM/ })).toBeInTheDocument()
  })

  it('refuse un DOUBLON d’objectif actif en nommant l’année', async () => {
    const user = userEvent.setup()
    monter()
    await allerEtape2(user, 'ENV-CO2')
    await remplir(user, { anneeCible: '2030' })

    const conflit = await screen.findByTestId('esg-wizard-conflit')
    expect(conflit).toHaveTextContent('2030')
    expect(conflit).toHaveTextContent('ENV-CO2')
    expect(screen.getByTestId('esg-wizard-suivant-2')).toBeDisabled()
    expect(creerObjectif).not.toHaveBeenCalled()
  })

  it('accepte une autre année cible sur le même indicateur', async () => {
    const user = userEvent.setup()
    monter()
    await allerEtape2(user, 'ENV-CO2')
    await remplir(user, { anneeCible: '2035' })
    await waitFor(() => {
      expect(screen.getByTestId('esg-wizard-suivant-2')).not.toBeDisabled()
    })
    expect(screen.queryByTestId('esg-wizard-conflit')).toBeNull()
  })

  it('refuse une année cible antérieure à la référence', async () => {
    const user = userEvent.setup()
    monter()
    await allerEtape2(user)
    await remplir(user, { anneeRef: '2028', anneeCible: '2024' })
    expect(await screen.findByTestId('esg-wizard-annees')).toBeInTheDocument()
    expect(screen.getByTestId('esg-wizard-suivant-2')).toBeDisabled()
  })

  it('affiche l’aperçu puis crée l’objectif', async () => {
    const user = userEvent.setup()
    monter()
    await allerEtape2(user)
    await remplir(user)
    expect(await screen.findByTestId('esg-wizard-apercu')).toBeInTheDocument()

    await user.click(screen.getByTestId('esg-wizard-suivant-2'))
    expect(await screen.findByTestId('esg-wizard-confirmation'))
      .toBeInTheDocument()
    await user.click(screen.getByTestId('esg-wizard-creer'))

    await waitFor(() => expect(creerObjectif).toHaveBeenCalledTimes(1))
    expect(creerObjectif.mock.calls[0][0]).toMatchObject({
      indicateur_code: 'SOC-FORM',
      valeur_reference: 100,
      annee_reference: 2024,
      valeur_cible: 50,
      annee_cible: 2028,
      actif: true,
    })
  })

  it('dit clairement qu’aucun indicateur n’existe', async () => {
    codesDisponibles.mockResolvedValue({ data: [] })
    monter()
    expect(await screen.findByTestId('esg-wizard-aucun-code'))
      .toHaveTextContent(/inexistant|QHSE/i)
    expect(screen.queryByLabelText('Rechercher un indicateur')).toBeNull()
  })

  it('affiche l’erreur du serveur', async () => {
    creerObjectif.mockRejectedValue({
      response: {
        status: 400,
        data: { indicateur_code: ['Un objectif existe déjà.'] },
      },
    })
    const user = userEvent.setup()
    monter()
    await allerEtape2(user)
    await remplir(user)
    await user.click(screen.getByTestId('esg-wizard-suivant-2'))
    await user.click(await screen.findByTestId('esg-wizard-creer'))
    expect(await screen.findByTestId('esg-wizard-erreur')).toBeInTheDocument()
  })
})
