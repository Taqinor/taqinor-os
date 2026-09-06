import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* MRY31 — écran « Suivi des relances ». Charge utile venant de l'exemple
   COMMITTÉ (`apps/crm/contract_samples/relance_etapes_suivi.json`, PACT10),
   jamais un objet retapé à la main : c'est cette deuxième source de vérité
   qui avait laissé passer l'écran AO mort du 03/08/2026 (test vert, écran
   mort). Si le serveur change de forme, l'exemple change et ce test casse
   tout seul. */
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

const DONNEES = exempleContrat('crm', 'relance_etapes_suivi')
const ETAPES = DONNEES.results

// Même patron que `IdentityRail.test.jsx`/`ViewsManagerPopover.test.jsx` :
// on mocke le hook de rôle plutôt que de monter un vrai Provider redux pour
// `useHasRole`. Mock réassignable par test (`.mockReturnValue`).
const isAdminOrResponsableMock = vi.fn(() => false)
vi.mock('../../hooks/useHasPermission', () => ({
  useIsAdminOrResponsable: () => isAdminOrResponsableMock(),
}))

// Même patron que `UsersManagement.test.jsx` : `useSelector` mocké
// directement plutôt qu'un vrai Provider redux (l'écran ne lit que
// `auth.user.id`).
vi.mock('react-redux', () => ({
  useSelector: (sel) => sel({ auth: { user: { id: 42 } } }),
}))

vi.mock('../../api/crmApi', () => ({
  default: {
    getRelanceEtapesSuivi: vi.fn(),
    getAssignableUsers: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    marquerRelanceEtapeFait: vi.fn(() => Promise.resolve({ data: {} })),
    marquerRelanceEtapeSautee: vi.fn(() => Promise.resolve({ data: {} })),
    reporterRelanceEtape: vi.fn(() => Promise.resolve({ data: {} })),
    getRelanceEtapeMessage: vi.fn(),
    whatsappRelanceEtape: vi.fn(),
  },
}))

import crmApi from '../../api/crmApi'
import RelancesSuiviPage from './RelancesSuiviPage'

beforeEach(() => {
  isAdminOrResponsableMock.mockReturnValue(false)
  crmApi.getRelanceEtapesSuivi.mockResolvedValue(reponseContrat('crm', 'relance_etapes_suivi'))
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

function mount() {
  return render(
    <MemoryRouter>
      <RelancesSuiviPage />
    </MemoryRouter>,
  )
}

// Bornes Casablanca — recalculées ICI indépendamment de l'écran (jamais un
// import de son détail interne) pour que le test reste une vraie preuve, pas
// une tautologie — même esprit que `CadenceFrise.mry15.test.jsx` (F3).
function casaISO(d) {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Casablanca' }).format(d)
}
function decalerJours(yyyyMmDd, delta) {
  const [y, m, d] = yyyyMmDd.split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d + delta)).toISOString().slice(0, 10)
}

describe('RelancesSuiviPage (MRY31)', () => {
  it('groupe les touches par jour, affiche le résumé serveur et une touche « Fait » avec son auteur', async () => {
    mount()
    // Onglet « 7 derniers jours » : AUCUN filtrage côté écran (contrairement
    // à l'onglet par défaut « Aujourd'hui + retard », qui compare au jour
    // réel d'exécution) — la seule façon de tester le regroupement/les
    // badges sans dépendre de la date du jour où la CI tourne.
    fireEvent.click(screen.getByRole('tab', { name: '7 derniers jours' }))
    await waitFor(() => expect(screen.getAllByTestId('relance-etape-row')).toHaveLength(2))

    // `resume` vient TEL QUEL du serveur (jamais recompté écran) : 1/0/1/0.
    expect(screen.getByText(/À faire\s*:\s*1/)).toBeInTheDocument()
    expect(screen.getByText(/En retard\s*:\s*0/)).toBeInTheDocument()
    expect(screen.getByText(/Faites\s*:\s*1/)).toBeInTheDocument()
    expect(screen.getByText(/Sautées\s*:\s*0/)).toBeInTheDocument()

    // Les deux étapes du contrat partagent le même `due_date` : UN seul
    // groupe de jour attendu, calculé indépendamment de l'écran.
    const d = new Date(`${ETAPES[0].due_date}T00:00:00`)
    const semaine = new Intl.DateTimeFormat('fr-FR', { weekday: 'long' }).format(d)
    const jour = new Intl.DateTimeFormat('fr-FR', { day: 'numeric' }).format(d)
    const mois = new Intl.DateTimeFormat('fr-FR', { month: 'long' }).format(d)
    expect(screen.getByText(new RegExp(`${semaine} ${jour} ${mois}`, 'i'))).toBeInTheDocument()

    // La touche « fait » (id 412 du contrat) affiche l'auteur du marquage.
    expect(screen.getByText(new RegExp(ETAPES[0].traite_par_nom))).toBeInTheDocument()
  })

  it('« Demain » appelle l\'API avec les bornes de demain (Africa/Casablanca)', async () => {
    mount()
    await waitFor(() => expect(crmApi.getRelanceEtapesSuivi).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('tab', { name: 'Demain' }))
    const today = casaISO(new Date())
    const demain = decalerJours(today, 1)
    await waitFor(() => expect(crmApi.getRelanceEtapesSuivi).toHaveBeenCalledWith(
      expect.objectContaining({ date_debut: demain, date_fin: demain }),
    ))
    // Les lignes « Demain » se lisent seulement (MRY32) : aucun bouton Fait.
    expect(screen.queryByRole('button', { name: /^Fait$/ })).not.toBeInTheDocument()
  })

  it('le filtre Responsable est masqué au rôle normal', async () => {
    isAdminOrResponsableMock.mockReturnValue(false)
    mount()
    await waitFor(() => expect(crmApi.getRelanceEtapesSuivi).toHaveBeenCalled())
    expect(screen.queryByLabelText('Responsable')).not.toBeInTheDocument()
  })

  it('le filtre Responsable est visible aux rôles responsable/admin, par défaut « Moi »', async () => {
    isAdminOrResponsableMock.mockReturnValue(true)
    mount()
    await waitFor(() => expect(screen.getByLabelText('Responsable')).toBeInTheDocument())
    expect(screen.getByText('Moi')).toBeInTheDocument()
  })
})
