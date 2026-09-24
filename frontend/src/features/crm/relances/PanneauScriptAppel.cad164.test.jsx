// CAD164 (PACT10, décision fondateur du 21/09/2026) — « Locataire » existait
// comme motif de perte et `ownership` était capté, mais la commerciale
// n'avait AUCUNE conduite à tenir. Moitié serveur déjà mergée (commit
// 56a322c0, `GET/POST leads/<id>/locataire/`) ; ce fichier verrouille la
// moitié ÉCRAN : les boutons « Créer la fiche du propriétaire » et
// « Propriétaire inconnu » du panneau d'appel, branchés sur le contrat
// `lead_locataire.json` COMMITTÉ — jamais un objet retapé à la main.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import {
  documentContrat, exempleContrat, reponseContrat,
} from '../../../test/fixtures/contractSamples'
import RelanceEtapeRow from './RelanceEtapeRow'

vi.mock('../../../lib/toast', () => ({ toastInfo: vi.fn(), toastSuccess: vi.fn(), toastError: vi.fn() }))

vi.mock('../../../api/crmApi', () => ({
  default: {
    getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })),
    getPanneauAppel: vi.fn(),
    getRelanceEtapeMessage: vi.fn(),
    updateLead: vi.fn(),
    getLeadLocataire: vi.fn(),
    postLeadLocataire: vi.fn(),
  },
}))

import crmApi from '../../../api/crmApi'

const ETAPE_APPEL = exempleContrat('crm', 'relance_etape_v2').results
  .find((t) => t.canal === 'appel')
const PANNEAU = exempleContrat('crm', 'panneau_appel')
// Le client se révèle LOCATAIRE (`ownership`, déjà répondu — le drapeau du
// panneau se lit aussi sur le prefill, patron CAD153 « une question déjà
// répondue n'est jamais reposée »).
const PANNEAU_LOCATAIRE = { ...PANNEAU, prefill: { ...PANNEAU.prefill, ownership: 'locataire' } }
const LOCATAIRE_DOC = documentContrat('crm', 'lead_locataire')

afterEach(() => { cleanup(); vi.clearAllMocks() })

function armer({ panneau = PANNEAU_LOCATAIRE, propose = LOCATAIRE_DOC.exemple } = {}) {
  crmApi.getPanneauAppel.mockResolvedValue({ data: panneau })
  crmApi.getRelanceEtapeMessage.mockResolvedValue(reponseContrat('crm', 'relance_etape_message'))
  crmApi.getLeadLocataire.mockResolvedValue({ data: propose })
}

function noop() {}

function ligne(etape = ETAPE_APPEL, props = {}) {
  return render(
    <RelanceEtapeRow
      etape={etape} onFait={noop} onSauter={noop} onReporter={noop}
      onOuvrirMessage={noop} {...props}
    />,
  )
}

async function ouvrirLocataire() {
  ligne()
  fireEvent.click(screen.getByRole('button', { name: /Script d’appel/ }))
  return screen.findByTestId('flux-locataire')
}

describe('CAD164 — le panneau lit ce que le serveur PROPOSE (GET locataire/)', () => {
  it('client locataire : les deux boutons proposés par le serveur apparaissent', async () => {
    armer()
    const bloc = await ouvrirLocataire()
    await waitFor(() => expect(crmApi.getLeadLocataire).toHaveBeenCalledWith(ETAPE_APPEL.lead))
    expect(bloc).toHaveTextContent('Si le client est locataire')
    expect(await screen.findByRole('button', { name: 'Créer la fiche du propriétaire' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Propriétaire inconnu' })).toBeInTheDocument()
  })

  it('rien de PROPOSÉ (client pas locataire) : aucun bouton, aucun appel GET locataire/', async () => {
    armer({ panneau: PANNEAU })
    ligne()
    fireEvent.click(screen.getByRole('button', { name: /Script d’appel/ }))
    await screen.findByTestId('non-compte')
    expect(screen.queryByTestId('flux-locataire')).not.toBeInTheDocument()
    expect(crmApi.getLeadLocataire).not.toHaveBeenCalled()
  })

  it('propose vide (exemple_pas_locataire) : le bloc informatif reste, aucun bouton', async () => {
    armer({ propose: LOCATAIRE_DOC.exemple_pas_locataire })
    const bloc = await ouvrirLocataire()
    expect(bloc).toHaveTextContent('Si le client est locataire')
    expect(screen.queryByRole('button', { name: 'Créer la fiche du propriétaire' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Propriétaire inconnu' })).not.toBeInTheDocument()
  })
})

describe('CAD164 — « Créer la fiche du propriétaire » (POST locataire/)', () => {
  it('coordonnées saisies → POST {proprietaire: {...}} EXACTEMENT la forme du contrat, message d’issue affiché', async () => {
    armer()
    crmApi.postLeadLocataire.mockResolvedValue(reponseContrat('crm', 'lead_locataire', 'exemple_proprietaire_cree'))
    const onLeadEcrit = vi.fn()
    ligne(ETAPE_APPEL, { onLeadEcrit })
    fireEvent.click(screen.getByRole('button', { name: /Script d’appel/ }))
    await screen.findByRole('button', { name: 'Créer la fiche du propriétaire' })
    const { proprietaire } = LOCATAIRE_DOC.corps_proprietaire
    fireEvent.change(screen.getByPlaceholderText('Nom du propriétaire'), { target: { value: proprietaire.nom } })
    fireEvent.change(screen.getByPlaceholderText('Prénom'), { target: { value: proprietaire.prenom } })
    fireEvent.change(screen.getByPlaceholderText('Téléphone'), { target: { value: proprietaire.telephone } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer la fiche du propriétaire' }))
    await waitFor(() => expect(crmApi.postLeadLocataire).toHaveBeenCalledWith(
      ETAPE_APPEL.lead, { proprietaire }))
    expect(await screen.findByTestId('locataire-issue')).toHaveTextContent('Fiche du propriétaire créée')
    expect(onLeadEcrit).toHaveBeenCalled()
    // Une fois l'issue connue, les boutons ne se reproposent plus.
    expect(screen.queryByRole('button', { name: 'Créer la fiche du propriétaire' })).not.toBeInTheDocument()
  })

  it('un propriétaire déjà connu au même numéro est RELIÉ (200) — le message le dit', async () => {
    armer()
    crmApi.postLeadLocataire.mockResolvedValue({
      data: {
        issue: 'proprietaire_relie',
        lead_proprietaire: { id: 1601, nom: 'Alaoui', prenom: 'Fatima' },
        locataire: { id: 1489, ownership: 'locataire', perdu: false, motif_perte: '' },
      },
    })
    ligne()
    fireEvent.click(screen.getByRole('button', { name: /Script d’appel/ }))
    await screen.findByRole('button', { name: 'Créer la fiche du propriétaire' })
    fireEvent.change(screen.getByPlaceholderText('Nom du propriétaire'), { target: { value: 'Alaoui' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer la fiche du propriétaire' }))
    expect(await screen.findByTestId('locataire-issue')).toHaveTextContent('Propriétaire relié')
  })

  it('le bouton reste désactivé sans nom (refus côté écran, avant même le serveur)', async () => {
    armer()
    ligne()
    fireEvent.click(screen.getByRole('button', { name: /Script d’appel/ }))
    const bouton = await screen.findByRole('button', { name: 'Créer la fiche du propriétaire' })
    expect(bouton).toBeDisabled()
  })

  it('refus serveur (téléphone manquant) : l’erreur NOMME le champ, EXACTEMENT le texte du contrat', async () => {
    armer()
    crmApi.postLeadLocataire.mockRejectedValue({
      response: { status: 400, data: LOCATAIRE_DOC.exemple_erreur_proprietaire },
    })
    ligne()
    fireEvent.click(screen.getByRole('button', { name: /Script d’appel/ }))
    await screen.findByRole('button', { name: 'Créer la fiche du propriétaire' })
    fireEvent.change(screen.getByPlaceholderText('Nom du propriétaire'), { target: { value: 'Tazi' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer la fiche du propriétaire' }))
    expect(await screen.findByTestId('erreur-proprietaire')).toHaveTextContent(
      LOCATAIRE_DOC.exemple_erreur_proprietaire.proprietaire.telephone[0])
  })
})

describe('CAD164 — « Propriétaire inconnu » (POST {proprietaire_inconnu: true})', () => {
  it('clôt la fiche du locataire, motif EXISTANT « Locataire », message d’issue affiché', async () => {
    armer()
    crmApi.postLeadLocataire.mockResolvedValue(reponseContrat('crm', 'lead_locataire', 'exemple_perdu_locataire'))
    ligne()
    fireEvent.click(screen.getByRole('button', { name: /Script d’appel/ }))
    await screen.findByRole('button', { name: 'Propriétaire inconnu' })
    fireEvent.click(screen.getByRole('button', { name: 'Propriétaire inconnu' }))
    await waitFor(() => expect(crmApi.postLeadLocataire).toHaveBeenCalledWith(
      ETAPE_APPEL.lead, { proprietaire_inconnu: true }))
    expect(await screen.findByTestId('locataire-issue')).toHaveTextContent(
      'Fiche du locataire close — motif « Locataire ».')
  })
})

describe('CAD164 — le texte de conduite FLUX_LOCATAIRE n’est jamais réécrit', () => {
  it('la consigne et le repli affichés sont ceux d’appelGuidance.js, mot pour mot', async () => {
    armer()
    const { FLUX_LOCATAIRE } = await import('./appelGuidance')
    const bloc = await ouvrirLocataire()
    expect(bloc).toHaveTextContent(FLUX_LOCATAIRE.consigne)
    expect(bloc).toHaveTextContent(FLUX_LOCATAIRE.sinon)
  })
})
