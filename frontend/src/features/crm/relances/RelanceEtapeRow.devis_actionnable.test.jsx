// VISCAD6-B (E2, fondateur 24/09/2026) — l'étape de filet « devis parti »
// sort du texte inerte : deux actions la rendent ACTIONNABLE (« Créer le
// devis » ; 17/11/2026 : « Planifier la visite » n'est plus un bouton — la
// réponse « Visite d'abord » l'ouvre ET close l'étape), et l'étiquette « Fait » dit honnêtement
// son effet serveur réel (CAD17 « jamais un effet caché ») — cocher FAIT
// cette étape SANS issue vaut « devis parti » côté serveur
// (`touche_envoi_devis`, `apps/crm/services.py`) : le lead passe « Devis
// envoyé », le suivi de proposition démarre. Ni l'issue envoyée (`{}`,
// AUCUN `outcome`) ni le contrat ne changent — seule l'étiquette le dit.
//
// Étape de départ = le premier résultat du contrat COMMITTÉ
// `relance_etape_v2.json` (`exemple_generique`), SEUL le libellé changé pour
// les deux chaînes EXACTES de `apps.crm.services.FILET_JOINT_LIBELLE` /
// `_FILET_JOINT_LIBELLE_ANCIEN` — jamais un objet retapé de zéro (PACT10).
import {
  describe, it, expect, vi, afterEach,
} from 'vitest'
import {
  render, screen, cleanup, fireEvent, waitFor,
} from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import RelanceEtapeRow from './RelanceEtapeRow'

const [BARREAU] = exempleContrat('crm', 'relance_etape_v2', 'exemple_generique').results
const ETAPE_DEVIS = { ...BARREAU, libelle: 'Préparer et envoyer le devis (ou fixer un rappel)' }
const ETAPE_DEVIS_ANCIEN_LIBELLE = {
  ...BARREAU, libelle: 'Prochaine étape — envoyer le devis ou fixer un rappel',
}

vi.mock('../../../api/crmApi', () => ({
  default: {
    getAssignableUsers: vi.fn(() => Promise.resolve({ data: [] })),
    getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))
vi.mock('../../../lib/toast', () => ({ toastInfo: vi.fn(), toastSuccess: vi.fn() }))

function noop() {}

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe.each([
  ['libellé actuel', ETAPE_DEVIS],
  ['ancien libellé — leads créés avant le renommage', ETAPE_DEVIS_ANCIEN_LIBELLE],
])('VISCAD6-B — étape « devis parti » (%s)', (_nom, etapeDevis) => {
  it('« Créer le devis » est proposé à côté des boutons existants ; « Planifier la visite » n’est plus un bouton', () => {
    render(
      <RelanceEtapeRow
        etape={etapeDevis} onFait={noop} onSauter={noop} onReporter={noop} onOuvrirMessage={noop}
      />,
    )
    expect(screen.getByRole('link', { name: 'Créer le devis' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Planifier la visite' })).not.toBeInTheDocument()
    // Les boutons EXISTANTS restent tous là (jamais un remplacement).
    expect(screen.getByRole('button', { name: /Appeler/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Fait$/ })).toBeInTheDocument()
    // SUIVI-PARCOURS (30/09/2026) — une TÂCHE ne se « saute » pas : ses
    // réponses couvrent tous les cas (devis envoyé, visite d'abord, à
    // rappeler, client refuse, ne plus contacter).
    expect(screen.queryByRole('button', { name: /Sauter/ })).not.toBeInTheDocument()
  })

  it('« Créer le devis » navigue vers /ventes/devis/nouveau?lead=<id> (même chemin que LeadWorkspace.jsx:959)', () => {
    const navigate = vi.fn()
    render(
      <RelanceEtapeRow
        etape={etapeDevis} onFait={noop} onSauter={noop} onReporter={noop} onOuvrirMessage={noop}
        navigate={navigate}
      />,
    )
    fireEvent.click(screen.getByRole('link', { name: 'Créer le devis' }))
    expect(navigate).toHaveBeenCalledWith(`/ventes/devis/nouveau?lead=${etapeDevis.lead}`)
  })

  it('« Visite d’abord » ouvre la MÊME modale que l’issue « Visite acceptée » (VISCAD6/E1), avant tout envoi', async () => {
    const onFait = vi.fn(() => Promise.resolve({}))
    render(
      <RelanceEtapeRow
        etape={etapeDevis} onFait={onFait} onSauter={noop} onReporter={noop} onOuvrirMessage={noop}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Visite d’abord' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    expect(await screen.findByText('Planifier la visite technique')).toBeInTheDocument()
    expect(onFait).not.toHaveBeenCalled()
  })

  it('une visite déjà prévue sur le lead : « Visite d’abord » n’est plus proposée', () => {
    render(
      <RelanceEtapeRow
        etape={{ ...etapeDevis, visite_prevue_le: '2099-01-05' }} onFait={noop} onSauter={noop}
        onReporter={noop} onOuvrirMessage={noop}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    expect(screen.getByRole('button', { name: 'Devis envoyé — passer à la suite' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Visite d’abord' })).not.toBeInTheDocument()
  })

  it('« Fait » propose « Devis envoyé — passer à la suite » (jamais « Fait — passer à la suite »)', () => {
    render(
      <RelanceEtapeRow
        etape={etapeDevis} onFait={noop} onSauter={noop} onReporter={noop} onOuvrirMessage={noop}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    expect(screen.getByRole('button', { name: 'Devis envoyé — passer à la suite' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Fait — passer à la suite' })).not.toBeInTheDocument()
  })

  it('confirmée : l’issue envoyée reste EXACTEMENT celle du contrat — aucun `outcome` (CAD17, jamais un effet caché DANS l’issue)', async () => {
    const onFait = vi.fn(() => Promise.resolve({}))
    render(
      <RelanceEtapeRow
        etape={etapeDevis} onFait={onFait} onSauter={noop} onReporter={noop} onOuvrirMessage={noop}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Devis envoyé — passer à la suite' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(onFait).toHaveBeenCalledWith(etapeDevis.id, {}))
  })
})

describe('VISCAD6-B — une AUTRE étape générique garde son texte inerte', () => {
  it('« Premier rappel » (barreau ordinaire) ne montre ni « Créer le devis » ni « Planifier la visite », garde « Fait — passer à la suite »', () => {
    expect(BARREAU.libelle).toBe('Premier rappel')
    render(
      <RelanceEtapeRow
        etape={BARREAU} onFait={noop} onSauter={noop} onReporter={noop} onOuvrirMessage={noop}
      />,
    )
    expect(screen.queryByRole('link', { name: 'Créer le devis' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Planifier la visite' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    expect(screen.getByRole('button', { name: 'Fait — passer à la suite' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Devis envoyé — passer à la suite' })).not.toBeInTheDocument()
  })
})
