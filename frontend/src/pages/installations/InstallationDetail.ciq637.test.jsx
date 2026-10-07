import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { exempleContrat } from '../../test/fixtures/contractSamples'
import { formatDate } from '../../lib/format'
import { renderInstallationDetail } from '../../test/installationDetailHarness'
import { polyfillResizeObserver } from '../../test/selectNatif'

/* ============================================================================
   CIQ637 — Fiche chantier : niveau de tension, régime sans seuil, section
   82-21 lue du dossier (lecture seule), dérogation motivée, réception
   définitive et signataire nommé.
   Les dossiers du test viennent de l'exemple COMMITTÉ
   `ventes/contract_samples/dossier_8221.json` (check_api_shapes).
   Même mock Select natif que CHT22 (Radix ne s'ouvre pas sous jsdom).
   ========================================================================== */

beforeAll(polyfillResizeObserver)

vi.mock('../../ui', async (importActual) => (
  (await import('../../test/selectNatif')).avecSelectNatif(await importActual())
))

vi.mock('../../features/installations/SignaturePad', () => ({
  default: ({ onChange }) => (
    <button type="button" onClick={() => onChange('data:image/png;base64,AAAA')}>
      Simuler un tracé
    </button>
  ),
}))

const mocks = vi.hoisted(() => ({
  getReglementaire: vi.fn(),
  updateInstallation: vi.fn(),
  prononcerReceptionDefinitive: vi.fn(),
  getInstallation: vi.fn(),
  signerClientChantier: vi.fn(),
}))

vi.mock('../../api/installationsApi', () => ({
  default: {
    getHistorique: () => Promise.resolve({ data: [] }),
    getTypesIntervention: () => Promise.resolve({ data: [] }),
    updateInstallation: (...a) => mocks.updateInstallation(...a),
    prononcerReceptionDefinitive: (...a) => mocks.prononcerReceptionDefinitive(...a),
    getInstallation: (...a) => mocks.getInstallation(...a),
    signerClientChantier: (...a) => mocks.signerClientChantier(...a),
  },
}))

vi.mock('../../api/savApi', async () => (await import('../../test/selectNatif')).savApiMock)
vi.mock('../../api/crmApi', async () => (await import('../../test/selectNatif')).crmApiMock)

vi.mock('../../api/ventesApi', () => ({
  default: {
    getDevisById: () => Promise.resolve({ data: { lignes: [] } }),
    getReglementaire: (...a) => mocks.getReglementaire(...a),
  },
}))

// L'onglet « Jalons & gates » monte ces trois blocs : hors périmètre ici.
vi.mock('./ChantierGateTimeline', () => ({ default: () => null }))
vi.mock('./ChantierChecklist', () => ({ default: () => null }))
vi.mock('../../features/installations/offline/OfflineSyncIndicator', () => ({
  default: () => null,
}))

const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigateMock }
})

import InstallationDetail from './InstallationDetail'
import SignatureLivraisonDialog from './SignatureLivraisonDialog'

const BT = exempleContrat('ventes', 'dossier_8221')
const MT = exempleContrat('ventes', 'dossier_8221', 'exemple_mt')

const renderDetail = renderInstallationDetail

const CHANTIER = {
  id: 701, reference: 'CH-CIQ637-701', statut: 'signe', annule: false,
  client: 12, client_nom: 'Hôtel', devis: 90, devis_reference: 'DEV-CIQ637-0090',
  type_installation: 'industriel', niveau_tension: 'mt',
  niveau_tension_source: 'mesure_visite', puissance_souscrite_kva: '250.00',
  regime_8221: 'accord_raccordement',
}

const ligneDossier = (contrat, extra = {}) => ({
  devis: CHANTIER.devis, statut: 'convention_signee',
  statut_label: 'Convention signée', reference_dossier: 'REF-637',
  ...contrat, ...extra,
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

beforeEach(() => {
  mocks.getReglementaire.mockResolvedValue({ data: { results: [] } })
  mocks.updateInstallation.mockResolvedValue({ data: { id: CHANTIER.id } })
})

describe('InstallationDetail — CIQ637 régime et niveau de tension', () => {
  it('libellés sans seuil et option « À qualifier »', async () => {
    renderDetail(CHANTIER)
    const regime = await screen.findByLabelText('Régime')
    expect(within(regime).getByRole('option', { name: 'À qualifier' })).toBeInTheDocument()
    expect(within(regime).getByRole('option', { name: 'Déclaration' })).toBeInTheDocument()
    expect(within(regime).getByRole('option', { name: 'Autorisation (ministère)' })).toBeInTheDocument()
    expect(regime.textContent).not.toMatch(/11 kW|1 MW|ANRE/)
  })

  it('affiche et édite le niveau de tension et la puissance souscrite avec leur source', async () => {
    const user = userEvent.setup()
    renderDetail(CHANTIER)
    const niveau = await screen.findByLabelText('Niveau de tension')
    expect(niveau).toHaveValue('mt')
    expect(screen.getByText('Source : Mesuré en visite')).toBeInTheDocument()
    const psous = screen.getByLabelText('Puissance souscrite (kVA)')
    expect(psous).toHaveAttribute('step', 'any')
    await user.clear(psous)
    await user.type(psous, '312.5')
    await user.selectOptions(niveau, 'bt')
    await user.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(mocks.updateInstallation).toHaveBeenCalledTimes(1))
    const [, data] = mocks.updateInstallation.mock.calls[0]
    expect(data.niveau_tension).toBe('bt')
    // La valeur tapée part telle quelle, jamais arrondie.
    expect(data.puissance_souscrite_kva).toBe('312.5')
  })

  it('un chantier résidentiel n’affiche pas le niveau de tension', async () => {
    renderDetail({ ...CHANTIER, type_installation: 'residentiel', niveau_tension: null })
    await screen.findByLabelText('Régime')
    expect(screen.queryByLabelText('Niveau de tension')).toBeNull()
  })

  it('enregistrer → rouvrir → enregistrer sans toucher = même PATCH', async () => {
    const user = userEvent.setup()
    const enregistrer = async () => {
      const rendu = renderDetail(CHANTIER)
      await screen.findByLabelText('Régime')
      await user.click(screen.getByRole('button', { name: 'Mettre à jour' }))
      await waitFor(() => expect(mocks.updateInstallation).toHaveBeenCalled())
      return rendu
    }
    const premier = await enregistrer()
    premier.unmount()
    mocks.updateInstallation.mockClear()
    await enregistrer()
    expect(mocks.updateInstallation).toHaveBeenCalledTimes(1)
    const [, data] = mocks.updateInstallation.mock.calls[0]
    // Même charge utile qu'à la première ouverture (le PATCH est idempotent).
    expect(data.niveau_tension).toBe('mt')
    expect(data.puissance_souscrite_kva).toBe('250.00')
    expect(data.regime_8221).toBe('accord_raccordement')
  })
})

describe('InstallationDetail — CIQ637 section 82-21 lue du dossier', () => {
  it('lecture seule : statut, référence, échéance des travaux, lien vers le dossier', async () => {
    mocks.getReglementaire.mockResolvedValue({ data: { results: [ligneDossier(MT)] } })
    const user = userEvent.setup()
    renderDetail(CHANTIER)
    const bloc = await screen.findByTestId('dossier-82-21-lecture')
    expect(bloc).toHaveTextContent('Convention signée')
    expect(bloc).toHaveTextContent('REF-637')
    expect(within(bloc).getByTestId('dossier-echeance-travaux'))
      .toHaveTextContent(formatDate(MT.resume.travaux_limite_le))
    // Les champs saisis à la main disparaissent : le dossier fait foi.
    expect(screen.queryByLabelText('Référence / N° de dossier')).toBeNull()
    await user.click(within(bloc).getByRole('button', { name: 'Ouvrir le dossier réglementaire' }))
    expect(navigateMock).toHaveBeenCalledWith('/ventes/dossiers-reglementaires')
  })

  it('une alerte de modification du matériel figé est visible', async () => {
    mocks.getReglementaire.mockResolvedValue({ data: { results: [ligneDossier(BT)] } })
    renderDetail(CHANTIER)
    const bloc = await screen.findByTestId('dossier-82-21-lecture')
    expect(within(bloc).getByRole('alert')).toHaveTextContent(
      BT.resume.alertes_modification[0].message)
  })

  it('sans dossier, la saisie manuelle reste proposée', async () => {
    renderDetail(CHANTIER)
    expect(await screen.findByLabelText('Référence / N° de dossier')).toBeInTheDocument()
    expect(screen.queryByTestId('dossier-82-21-lecture')).toBeNull()
  })
})

describe('InstallationDetail — CIQ637 dérogation et réception définitive', () => {
  it('un passage refusé demande le motif de dérogation, envoyé au prochain enregistrement', async () => {
    mocks.updateInstallation.mockRejectedValueOnce({
      response: { data: { statut: ['Aucune convention de raccordement signée.'] } },
    })
    const user = userEvent.setup()
    renderDetail(CHANTIER)
    await user.selectOptions(await screen.findByLabelText('Statut'), 'materiel_commande')
    await user.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    const bloc = await screen.findByTestId('ch6-blocked-reasons')
    expect(bloc).toHaveTextContent('Aucune convention de raccordement signée.')

    await user.type(within(bloc).getByLabelText('Motif de dérogation (Directeur)'),
      'Accord écrit du directeur technique')
    await user.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(mocks.updateInstallation).toHaveBeenCalledTimes(2))
    expect(mocks.updateInstallation.mock.calls[1][1].motif_derogation_8221)
      .toBe('Accord écrit du directeur technique')
    // Le premier envoi ne portait aucun motif.
    expect(mocks.updateInstallation.mock.calls[0][1]).not.toHaveProperty('motif_derogation_8221')
  })

  it('le refus de la réception définitive affiche les réserves ouvertes', async () => {
    const detail = 'Réception définitive impossible : réserve(s) non levée(s) : '
      + 'Étiquette manquante ; Peinture à reprendre.'
    mocks.prononcerReceptionDefinitive.mockRejectedValueOnce({ response: { data: { detail } } })
    const user = userEvent.setup()
    renderDetail(CHANTIER)
    await user.click(await screen.findByRole('tab', { name: /Jalons/ }))
    await user.click(await screen.findByRole('button', { name: 'Prononcer la réception définitive' }))
    const refus = await screen.findByTestId('reception-refus')
    expect(refus).toHaveTextContent('Étiquette manquante ; Peinture à reprendre')
    expect(mocks.prononcerReceptionDefinitive).toHaveBeenCalledWith(CHANTIER.id)
  })

  it('une réception définitive prononcée relit le chantier et masque le bouton', async () => {
    mocks.prononcerReceptionDefinitive.mockResolvedValueOnce({ data: {} })
    mocks.getInstallation.mockResolvedValue({
      data: { ...CHANTIER, date_reception_definitive: '2026-12-01' },
    })
    const user = userEvent.setup()
    renderDetail(CHANTIER)
    await user.click(await screen.findByRole('tab', { name: /Jalons/ }))
    await user.click(await screen.findByRole('button', { name: 'Prononcer la réception définitive' }))
    expect(await screen.findByText(/Réception définitive prononcée le/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Prononcer la réception définitive' })).toBeNull()
  })

  it('un chantier résidentiel n’a pas de réception définitive', async () => {
    const user = userEvent.setup()
    renderDetail({ ...CHANTIER, type_installation: 'residentiel' })
    await user.click(await screen.findByRole('tab', { name: /Jalons/ }))
    expect(screen.queryByRole('button', { name: 'Prononcer la réception définitive' })).toBeNull()
  })
})

describe('SignatureLivraisonDialog — CIQ637 signataire nommé', () => {
  it('envoie fonction, société et co-signataire quand ils sont saisis', async () => {
    mocks.signerClientChantier.mockResolvedValue({ data: { id: 42 } })
    const user = userEvent.setup()
    render(
      <SignatureLivraisonDialog open installation={{ id: 42, signe_le: null, signataire_nom: '' }}
        onOpenChange={vi.fn()} onSigned={vi.fn()} />,
    )
    await user.type(screen.getByPlaceholderText(/nom du signataire/i), 'Karim Bennani')
    await user.type(screen.getByLabelText('Fonction du signataire'), 'Directeur technique')
    await user.type(screen.getByLabelText('Société du signataire'), 'Hôtel Atlas')
    await user.type(screen.getByLabelText('Nom du co-signataire'), 'Salma Idrissi')
    await user.click(screen.getByRole('button', { name: 'Simuler un tracé' }))
    await user.click(screen.getByRole('button', { name: /enregistrer la signature/i }))
    await waitFor(() => expect(mocks.signerClientChantier).toHaveBeenCalledTimes(1))
    expect(mocks.signerClientChantier).toHaveBeenCalledWith(42, {
      signature_client: 'data:image/png;base64,AAAA',
      signataire_nom: 'Karim Bennani',
      signataire_fonction: 'Directeur technique',
      signataire_societe: 'Hôtel Atlas',
      cosignataire_nom: 'Salma Idrissi',
    })
  })

  it('reprend le signataire déjà enregistré du chantier', () => {
    render(
      <SignatureLivraisonDialog open
        installation={{
          id: 42, signe_le: '2026-10-01T10:00:00Z', signataire_nom: 'K. Bennani',
          signataire_fonction: 'Directeur', signataire_societe: 'Hôtel Atlas',
        }}
        onOpenChange={vi.fn()} onSigned={vi.fn()} />,
    )
    expect(screen.getByLabelText('Fonction du signataire')).toHaveValue('Directeur')
    expect(screen.getByLabelText('Société du signataire')).toHaveValue('Hôtel Atlas')
  })
})
