import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, within, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import process from 'node:process'

/* PACT49 — Rapport des dérogations de crédit (NTCRD26) ajouté sous la file de
   traitement (workflow WIR55, préservé).

   Le critère « l'export contient exactement les colonnes documentées côté
   serveur » n'est pas vérifié contre une liste retapée ici : ce test LIT le
   `header` de `views.rapport_derogations_view` dans le fichier serveur — même
   esprit que `test/contratServeur.js` (PACT13) — et exige l'égalité stricte,
   ordre compris, avec les en-têtes rendus. Renommer une colonne d'un seul côté
   fait rougir ce test. Les charges utiles reprennent le dictionnaire réel de
   `selectors.rapport_derogations`. */

function racineDepot() {
  let dossier = resolve(process.cwd())
  for (let i = 0; i < 6; i += 1) {
    if (existsSync(join(dossier, 'backend', 'django_core'))) return dossier
    dossier = dirname(dossier)
  }
  throw new Error(`Racine du dépôt introuvable depuis ${process.cwd()}`)
}

function colonnesServeur() {
  const source = readFileSync(
    join(racineDepot(), 'backend', 'django_core', 'apps', 'credit', 'views.py'),
    'utf8',
  )
  const bloc = source.slice(source.indexOf('def rapport_derogations_view'))
  const liste = bloc.match(/header = \[([\s\S]*?)\]/)
  if (!liste) throw new Error('`header` introuvable dans rapport_derogations_view')
  return [...liste[1].matchAll(/'([^']+)'/g)].map((m) => m[1])
}

vi.mock('../../api/creditApi', () => ({
  default: {
    getDerogations: vi.fn(),
    approuverDerogation: vi.fn(),
    rejeterDerogation: vi.fn(),
    getRapportDerogations: vi.fn(),
    exportRapportDerogations: vi.fn(),
  },
}))

import creditApi from '../../api/creditApi'
import DerogationsPage from './DerogationsPage'

const DEMANDES = [
  {
    id: 3, client: 7, devis: null, montant_demande: '120000.00',
    motif: 'Chantier stratégique', statut: 'en_attente', demandeur: 2,
    approuvee_par: null, date_decision: null, valide_jusqu_au: null,
    date_creation: '2026-07-01T09:00:00Z', est_valide: false,
  },
]

const RAPPORT = {
  lignes: [
    {
      id: 3, client_id: 7, montant_demande: '120000.00', statut: 'approuvee',
      demandeur: 'sami', decideur: 'reda',
      date_creation: '2026-07-01T09:00:00Z',
      date_decision: '2026-07-01T15:30:00Z', delai_traitement_h: 6.5,
    },
    {
      id: 4, client_id: 9, montant_demande: '50000.00', statut: 'en_attente',
      demandeur: 'sami', decideur: null,
      date_creation: '2026-07-03T09:00:00Z', date_decision: null,
      delai_traitement_h: null,
    },
  ],
  nb_approuvees: 1,
  delai_traitement_moyen_h: 6.5,
}

const monter = () => render(
  <MemoryRouter><DerogationsPage /></MemoryRouter>,
)

beforeEach(() => {
  vi.clearAllMocks()
  creditApi.getDerogations.mockResolvedValue({ data: DEMANDES })
  creditApi.getRapportDerogations.mockResolvedValue({ data: RAPPORT })
  creditApi.exportRapportDerogations.mockResolvedValue({
    data: new Blob(['x'], { type: 'text/csv' }),
  })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('DerogationsPage — rapport agrégé (PACT49)', () => {
  it('rend EXACTEMENT les colonnes documentées côté serveur, dans le même ordre', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByTestId('credit-derogations')

    await user.click(screen.getByRole('button', { name: 'Calculer le rapport' }))

    const resultat = await screen.findByTestId('credit-derogations-rapport-resultat')
    const entetes = within(resultat)
      .getAllByRole('columnheader')
      .map((th) => th.textContent)
    expect(entetes).toEqual(colonnesServeur())
  })

  it('affiche le délai de traitement en heures et la synthèse de période', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByTestId('credit-derogations')

    // `input[type=date]` : la frappe caractère par caractère n'a pas de sens
    // sous jsdom — on pose la valeur ISO comme le navigateur le ferait.
    fireEvent.change(screen.getByLabelText('Du'), { target: { value: '2026-07-01' } })
    fireEvent.change(screen.getByLabelText('Au'), { target: { value: '2026-07-31' } })
    await user.click(screen.getByRole('button', { name: 'Calculer le rapport' }))

    const resultat = await screen.findByTestId('credit-derogations-rapport-resultat')
    expect(within(resultat).getByText(/2 dérogation\(s\)/)).toBeInTheDocument()
    expect(within(resultat).getByText(/6.5 h/)).toBeInTheDocument()
    // La période saisie part telle quelle au serveur (bornes ISO).
    expect(creditApi.getRapportDerogations).toHaveBeenCalledWith({
      date_debut: '2026-07-01', date_fin: '2026-07-31',
    })
  })

  it('exporte le rapport dans les deux formats servis par le serveur', async () => {
    const user = userEvent.setup()
    URL.createObjectURL = vi.fn(() => 'blob:mock')
    URL.revokeObjectURL = vi.fn()
    const clic = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    monter()
    await screen.findByTestId('credit-derogations')
    await user.click(screen.getByRole('button', { name: 'Calculer le rapport' }))
    await screen.findByTestId('credit-derogations-rapport-resultat')

    await user.click(screen.getByRole('button', { name: 'Exporter (.xlsx)' }))
    await user.click(screen.getByRole('button', { name: 'Exporter (.csv)' }))

    expect(creditApi.exportRapportDerogations).toHaveBeenNthCalledWith(
      1, { date_debut: undefined, date_fin: undefined }, 'xlsx')
    expect(creditApi.exportRapportDerogations).toHaveBeenNthCalledWith(
      2, { date_debut: undefined, date_fin: undefined }, 'csv')
    expect(clic).toHaveBeenCalledTimes(2)
    clic.mockRestore()
  })

  it('préserve le workflow existant : approuver une demande en attente', async () => {
    const user = userEvent.setup()
    creditApi.approuverDerogation.mockResolvedValue({ data: {} })
    monter()
    await screen.findByTestId('credit-derogations')

    await user.click(screen.getByRole('button', { name: 'Approuver' }))
    expect(creditApi.approuverDerogation).toHaveBeenCalledWith(3)
  })
})
