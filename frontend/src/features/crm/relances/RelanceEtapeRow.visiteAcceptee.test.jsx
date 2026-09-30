// VISCAD6 — « la visite technique devient une étape du suivi commercial » :
// (a) le panneau de coaching « Proposer la visite » se rend pour toute
// touche 'apres_devis' actionnable (compact ET cockpit — jamais seulement
// compact), avec son CTA qui ouvre la modale de planification ; (b) l'issue
// « Visite acceptée » du mini-formulaire Fait ouvre la MÊME modale juste
// après confirmation.
import {
  describe, it, expect, vi, afterEach,
} from 'vitest'
import {
  render, screen, cleanup, fireEvent, waitFor,
} from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import RelanceEtapeRow from './RelanceEtapeRow'

// ETAPES[1] du contrat committé `relance_etape_v2.json` : cadence
// 'apres_devis', canal 'whatsapp', lead 1490 — jamais un objet retapé.
const ETAPE_APRES_DEVIS = exempleContrat('crm', 'relance_etape_v2').results[1]

vi.mock('../../../api/crmApi', () => ({
  default: {
    getAssignableUsers: vi.fn(() => Promise.resolve({ data: [] })),
    getMessageVisite: vi.fn(() => Promise.resolve({
      data: { corps_fr: 'Bonjour, quand vous convient-il pour la visite ?', corps_darija: '' },
    })),
    planifierVisiteLead: vi.fn(),
  },
}))
vi.mock('../../../lib/toast', () => ({ toastInfo: vi.fn(), toastSuccess: vi.fn() }))

import crmApi from '../../../api/crmApi'
import { toastInfo } from '../../../lib/toast'

function noop() {}

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('VISCAD6 — panneau « Proposer la visite » (apres_devis uniquement)', () => {
  it('se rend pour une touche apres_devis actionnable, replié par défaut', () => {
    render(
      <RelanceEtapeRow
        etape={ETAPE_APRES_DEVIS} onFait={noop} onSauter={noop} onReporter={noop} onOuvrirMessage={noop}
      />,
    )
    const panneau = screen.getByTestId('panneau-proposer-visite')
    expect(panneau).toBeInTheDocument()
    // Replié : le détail (script, signaux, CTA) n'est PAS dans le DOM tant
    // que le panneau n'est pas ouvert (repliable, pas juste masqué en CSS).
    expect(screen.queryByText('Client d\'accord → Planifier la visite')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /Proposer la visite/ }))
    expect(screen.getByText('Client d\'accord → Planifier la visite')).toBeInTheDocument()
  })

  it('ABSENT pour une cadence autre que apres_devis (contact/réveil/générique)', () => {
    render(
      <RelanceEtapeRow
        etape={{ ...ETAPE_APRES_DEVIS, cadence: 'contact' }}
        onFait={noop} onSauter={noop} onReporter={noop} onOuvrirMessage={noop}
      />,
    )
    expect(screen.queryByTestId('panneau-proposer-visite')).toBeNull()
  })

  it('ABSENT sur une ligne readOnly (rien à proposer sur une ligne qui se lit seulement)', () => {
    render(
      <RelanceEtapeRow
        etape={ETAPE_APRES_DEVIS} onFait={noop} onSauter={noop} onReporter={noop} onOuvrirMessage={noop}
        readOnly
      />,
    )
    expect(screen.queryByTestId('panneau-proposer-visite')).toBeNull()
  })

  it('se rend AUSSI en mode compact (frise de la fiche lead) — jamais seulement en mode cockpit', () => {
    render(
      <RelanceEtapeRow
        etape={ETAPE_APRES_DEVIS} onFait={noop} onSauter={noop} onReporter={noop} onOuvrirMessage={noop}
        compact
      />,
    )
    expect(screen.getByTestId('panneau-proposer-visite')).toBeInTheDocument()
  })

  it('le CTA « Client d\'accord » ouvre la modale de planification', async () => {
    render(
      <RelanceEtapeRow
        etape={ETAPE_APRES_DEVIS} onFait={noop} onSauter={noop} onReporter={noop} onOuvrirMessage={noop}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /Proposer la visite/ }))
    fireEvent.click(screen.getByText('Client d\'accord → Planifier la visite'))
    expect(await screen.findByText('Planifier la visite technique')).toBeInTheDocument()
  })

  it('signaux d\'achat toujours affichés, quelle que soit la phase', () => {
    render(
      <RelanceEtapeRow
        etape={ETAPE_APRES_DEVIS} onFait={noop} onSauter={noop} onReporter={noop} onOuvrirMessage={noop}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /Proposer la visite/ }))
    expect(screen.getByText(/Signaux d'achat = proposez tout de suite/)).toBeInTheDocument()
    expect(screen.getByText(/jamais par un débat au téléphone/)).toBeInTheDocument()
  })
})

describe('VISCAD6 — issue « Visite acceptée » du mini-formulaire Fait', () => {
  it('apparaît comme réponse possible pour une touche apres_devis', () => {
    render(
      <RelanceEtapeRow
        etape={ETAPE_APRES_DEVIS} onFait={noop} onSauter={noop} onReporter={noop} onOuvrirMessage={noop}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    expect(screen.getByRole('button', { name: 'Visite acceptée' })).toBeInTheDocument()
  })

  // SUIVI-BLOCAGE (30/09/2026) — la modale s'ouvre AVANT tout enregistrement
  // (la ligne est encore montée : elle ne peut plus disparaître sous la
  // modale). Deux sorties : « Date pas encore fixée » envoie la réponse seule
  // (le serveur pose « Planifier la visite ») ; une date saisie envoie la
  // planification AVEC la touche (`etape`) — c'est le serveur qui la clôt.
  it('choisie puis confirmée : ouvre la modale SANS rien envoyer ; « Date pas encore fixée » envoie l\'issue exacte', async () => {
    const onFait = vi.fn(() => Promise.resolve({}))
    render(
      <RelanceEtapeRow
        etape={ETAPE_APRES_DEVIS} onFait={onFait} onSauter={noop} onReporter={noop} onOuvrirMessage={noop}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Visite acceptée' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    expect(await screen.findByText('Planifier la visite technique')).toBeInTheDocument()
    expect(onFait).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Date pas encore fixée' }))
    await waitFor(() => expect(onFait).toHaveBeenCalledWith(
      ETAPE_APRES_DEVIS.id, { outcome: 'visite_acceptee' }))
    // Jamais un message de « prochaine touche » inventé côté écran ({} ne
    // porte pas `prochaine_touche`).
    expect(toastInfo).not.toHaveBeenCalled()
  })

  it('date saisie : la planification part AVEC la touche (`etape`), jamais un second « Fait »', async () => {
    const onFait = vi.fn(() => Promise.resolve({}))
    const onVisiteChanged = vi.fn()
    crmApi.planifierVisiteLead.mockResolvedValue({ data: { visite: { id: 9 }, prochaine_touche: null } })
    render(
      <RelanceEtapeRow
        etape={ETAPE_APRES_DEVIS} onFait={onFait} onSauter={noop} onReporter={noop} onOuvrirMessage={noop}
        onVisiteChanged={onVisiteChanged}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Visite acceptée' }))
    fireEvent.change(screen.getByPlaceholderText('Note (optionnelle)'), { target: { value: 'OK pour jeudi' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    expect(await screen.findByText('Planifier la visite technique')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText(/Date prévue/), { target: { value: '2099-03-05' } })
    fireEvent.click(screen.getByRole('button', { name: 'Planifier la visite' }))
    await waitFor(() => expect(crmApi.planifierVisiteLead).toHaveBeenCalledWith(
      ETAPE_APRES_DEVIS.lead,
      { date_prevue: '2099-03-05', etape: ETAPE_APRES_DEVIS.id, note_etape: 'OK pour jeudi' }))
    await waitFor(() => expect(onVisiteChanged).toHaveBeenCalled())
    expect(onFait).not.toHaveBeenCalled()
  })

  it('une AUTRE issue (ex. le client a répondu) n\'ouvre PAS la modale', async () => {
    const onFait = vi.fn(() => Promise.resolve({}))
    render(
      <RelanceEtapeRow
        etape={ETAPE_APRES_DEVIS} onFait={onFait} onSauter={noop} onReporter={noop} onOuvrirMessage={noop}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Le client a répondu' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(onFait).toHaveBeenCalled())
    await waitFor(() => expect(screen.queryByText('Planifier la visite technique')).toBeNull())
  })
})
