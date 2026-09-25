// VISCAD6-B — décision fondateur du 24/09/2026 : « Après l'appel il n'y a
// plus rien à faire, sauf organiser la visite. » L'issue « Visite acceptée »
// (déjà proposée sur le suivi de proposition, VISCAD6) s'ÉLARGIT aux
// cadences `contact`, `reveil` et au filet `generique` — même issue SERVEUR
// (`LeadActivity.OUTCOMES`), jamais une nouvelle valeur inventée ici, même
// modale de planification PARTAGÉE (`PlanifierVisiteModal`).
//
// Étapes de départ = le contrat COMMITTÉ `relance_etape_v2.json` (PACT10) :
// `exemple.results[0]` (appel de prise de contact) et
// `exemple_generique.results[0]` (barreau générique) — jamais un objet
// retapé à la main.
import {
  describe, it, expect, vi, afterEach,
} from 'vitest'
import {
  render, screen, cleanup, fireEvent, waitFor,
} from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import RelanceEtapeRow from './RelanceEtapeRow'

const ETAPE_CONTACT = exempleContrat('crm', 'relance_etape_v2').results[0]
const [ETAPE_GENERIQUE] = exempleContrat('crm', 'relance_etape_v2', 'exemple_generique').results

vi.mock('../../../api/crmApi', () => ({
  default: {
    getAssignableUsers: vi.fn(() => Promise.resolve({ data: [] })),
    getMessageVisite: vi.fn(() => Promise.resolve({
      data: { corps_fr: 'Bonjour, quand vous convient-il pour la visite ?', corps_darija: '' },
    })),
    getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))
vi.mock('../../../lib/toast', () => ({ toastInfo: vi.fn(), toastSuccess: vi.fn() }))

function noop() {}

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('VISCAD6-B — « Visite acceptée » proposée dès la prise de contact (cadence `contact`)', () => {
  it('apparaît comme réponse possible sur une touche `contact`', () => {
    expect(ETAPE_CONTACT.cadence).toBe('contact')
    render(
      <RelanceEtapeRow
        etape={ETAPE_CONTACT} onFait={noop} onSauter={noop} onReporter={noop} onOuvrirMessage={noop}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    expect(screen.getByRole('button', { name: 'Visite acceptée' })).toBeInTheDocument()
    // Les réponses existantes restent TOUTES là (jamais un remplacement).
    expect(screen.getByRole('button', { name: 'Client joint' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Pas de réponse' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'À rappeler le…' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Refus' })).toBeInTheDocument()
  })

  it('choisie puis confirmée : envoie l’issue serveur exacte ET ouvre la modale de planification (même modale que VISCAD6)', async () => {
    const onFait = vi.fn(() => Promise.resolve({}))
    render(
      <RelanceEtapeRow
        etape={ETAPE_CONTACT} onFait={onFait} onSauter={noop} onReporter={noop} onOuvrirMessage={noop}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Visite acceptée' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(onFait).toHaveBeenCalledWith(
      ETAPE_CONTACT.id, { outcome: 'visite_acceptee' }))
    expect(await screen.findByText('Planifier la visite technique')).toBeInTheDocument()
  })
})

describe('VISCAD6-B — « Visite acceptée » proposée sur le filet générique', () => {
  it('apparaît comme réponse possible sur une touche `generique`', () => {
    expect(ETAPE_GENERIQUE.cadence).toBe('generique')
    render(
      <RelanceEtapeRow
        etape={ETAPE_GENERIQUE} onFait={noop} onSauter={noop} onReporter={noop} onOuvrirMessage={noop}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    expect(screen.getByRole('button', { name: 'Visite acceptée' })).toBeInTheDocument()
    // « Fait — passer à la suite » reste la réponse par défaut du filet (ce
    // libellé PARTICULIER n'est pas l'étape « devis parti » — E2, VISCAD6-B).
    expect(screen.getByRole('button', { name: 'Fait — passer à la suite' })).toBeInTheDocument()
  })

  it('choisie puis confirmée : envoie l’issue serveur exacte ET ouvre la modale de planification', async () => {
    const onFait = vi.fn(() => Promise.resolve({}))
    render(
      <RelanceEtapeRow
        etape={ETAPE_GENERIQUE} onFait={onFait} onSauter={noop} onReporter={noop} onOuvrirMessage={noop}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Visite acceptée' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(onFait).toHaveBeenCalledWith(
      ETAPE_GENERIQUE.id, { outcome: 'visite_acceptee' }))
    expect(await screen.findByText('Planifier la visite technique')).toBeInTheDocument()
  })
})

describe('VISCAD6-B — « Visite acceptée » proposée sur le réveil', () => {
  it('apparaît comme réponse possible sur une touche `reveil`, ouvre la modale une fois confirmée', async () => {
    const etapeReveil = { ...ETAPE_CONTACT, cadence: 'reveil', ordre: 1, libelle: 'Réveil J30' }
    const onFait = vi.fn(() => Promise.resolve({}))
    render(
      <RelanceEtapeRow
        etape={etapeReveil} onFait={onFait} onSauter={noop} onReporter={noop} onOuvrirMessage={noop}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    expect(screen.getByRole('button', { name: 'Visite acceptée' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Visite acceptée' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(onFait).toHaveBeenCalledWith(
      etapeReveil.id, { outcome: 'visite_acceptee' }))
    expect(await screen.findByText('Planifier la visite technique')).toBeInTheDocument()
  })
})

// Réalignement (fondateur 24/09/2026) — cadence `contact` : avant cette
// décision, LA QUESTION DE CADENCE (`QUESTIONS.contact.reponses`,
// `RelanceEtapeRow.jsx`) ne comptait que 4 réponses (Client joint / Pas de
// réponse / À rappeler le… / Refus) ; « Visite acceptée » en fait désormais
// 5. Aucun test de ce dossier ne figeait ce compte avant ce correctif
// (recherché : aucun `toHaveLength`/liste de boutons exhaustive sur la
// cadence `contact` dans `RelanceEtapeRow.test.jsx` ni les autres suites de
// ce dossier) — rien à réaligner, ce test-ci EST le nouveau repère : sur une
// touche `contact` non-appel (jamais brouillée par Répondeur/Occupé, réservés
// au canal appel), le panneau « Fait » porte EXACTEMENT ces 5 réponses de
// cadence, plus « Plus tard » et « Ne plus me contacter » (réponses du
// CLIENT, ajoutées EN DERNIER — CAD-A, jamais un remplacement).
describe('VISCAD6-B — réalignement du compte de réponses (contact, 24/09/2026)', () => {
  it('une touche `contact` (canal whatsapp) porte exactement les 5 réponses de cadence + les 2 réponses client', () => {
    const etapeWhatsapp = { ...ETAPE_CONTACT, canal: 'whatsapp' }
    render(
      <RelanceEtapeRow
        etape={etapeWhatsapp} onFait={noop} onSauter={noop} onReporter={noop} onOuvrirMessage={noop}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    const panneau = screen.getByRole('group', { name: 'Résultat de la touche ?' })
    const labels = ['Client joint', 'Visite acceptée', 'Pas de réponse', 'À rappeler le…', 'Refus',
      'Plus tard — pas maintenant', 'Ne plus me contacter']
    for (const label of labels) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
    expect(panneau.querySelectorAll('button')).toHaveLength(labels.length)
  })
})
