import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* CAD100 (moitié écran de CAD87) — les deux tableaux de `mesure_cadence`
   (taux de joint par touche × heure × jour × canal, signatures par nombre
   de touches consommées) rendus TELS QUELS sur « Suivi des relances »,
   en LECTURE SEULE. Charge utile = l'exemple COMMITTÉ
   (`apps/crm/contract_samples/mesure_cadence.json`, PACT10). */
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

const MESURE = exempleContrat('crm', 'mesure_cadence')

const isAdminOrResponsableMock = vi.fn(() => false)
vi.mock('../../hooks/useHasPermission', () => ({
  useIsAdminOrResponsable: () => isAdminOrResponsableMock(),
}))
vi.mock('react-redux', () => ({
  useSelector: (sel) => sel({ auth: { user: { id: 42 } } }),
}))

vi.mock('../../api/crmApi', () => ({
  default: {
    getRelanceEtapesSuivi: vi.fn(() => Promise.resolve({
      data: { results: [], resume: { a_faire: 0, en_retard: 0, fait: 0, sautee: 0, annulee: 0 } },
    })),
    getAssignableUsers: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    marquerRelanceEtapeFait: vi.fn(),
    marquerRelanceEtapeSautee: vi.fn(),
    reporterRelanceEtape: vi.fn(),
    getRelanceEtapeMessage: vi.fn(),
    whatsappRelanceEtape: vi.fn(),
    getMesureCadence: vi.fn(),
  },
}))

import crmApi from '../../api/crmApi'
import RelancesSuiviPage from './RelancesSuiviPage'

beforeEach(() => {
  isAdminOrResponsableMock.mockReturnValue(false)
  crmApi.getMesureCadence.mockResolvedValue(reponseContrat('crm', 'mesure_cadence'))
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

function mount() {
  return render(
    <MemoryRouter>
      <RelancesSuiviPage />
    </MemoryRouter>,
  )
}

describe('RelancesSuiviPage — CAD100 (KPI touche × heure × jour × canal)', () => {
  it('rend les deux tableaux à partir de la réponse serveur, telle quelle', async () => {
    mount()
    const panneau = await screen.findByTestId('mesure-cadence-panel')
    const premierCreneau = MESURE.taux_joint_par_creneau[0]
    expect(within(panneau).getByText(`${premierCreneau.taux_joint_pct} %`)).toBeInTheDocument()
    expect(within(panneau).getByText('WhatsApp')).toBeInTheDocument()
    // index 1 (touches=5, signatures=3) : « 3 » n'entre en collision avec
    // AUCUNE autre cellule exacte du panneau (contrairement à « 1 », qui est
    // aussi l'ordre de la première touche) — getByText exige l'unicité.
    const distribution = MESURE.signatures_par_touches_consommees[1]
    expect(within(panneau).getByText(String(distribution.signatures))).toBeInTheDocument()
  })

  it('rien n\'y est modifiable (lecture seule : aucun input/select dans le panneau)', async () => {
    mount()
    const panneau = await screen.findByTestId('mesure-cadence-panel')
    expect(panneau.querySelectorAll('input, select, button')).toHaveLength(0)
  })

  it('un dénominateur nul reste `null` côté écran : jamais un 0 % fabriqué', async () => {
    crmApi.getMesureCadence.mockResolvedValue({
      data: {
        ...MESURE,
        taux_joint_par_creneau: [{ ...MESURE.taux_joint_par_creneau[0], closes: 0, joints: 0, taux_joint_pct: null }],
      },
    })
    mount()
    const panneau = await screen.findByTestId('mesure-cadence-panel')
    expect(within(panneau).getByText('—')).toBeInTheDocument()
  })

  it('crmApi.getMesureCadence absente du mock (suites existantes) : repli silencieux, jamais un plantage', async () => {
    const original = crmApi.getMesureCadence
    delete crmApi.getMesureCadence
    expect(() => mount()).not.toThrow()
    await waitFor(() => expect(
      screen.getByText(/Mesure de la cadence indisponible/),
    ).toBeInTheDocument())
    crmApi.getMesureCadence = original
  })
})
