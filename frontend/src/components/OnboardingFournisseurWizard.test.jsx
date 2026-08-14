import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { ThemeProvider } from '../design/ThemeProvider.jsx'

/* ============================================================================
   NTP2P29 — wizard d'onboarding fournisseur guidé.
   CRITÈRE D'ACCEPTATION : un dossier partiellement rempli affiche sa
   progression et BLOQUE le passage à l'étape récapitulatif.
   Vérifie aussi : l'étape 1 lit l'identité légale du référentiel, l'étape 2
   montre un statut PAR document, et un dossier complet débloque l'étape 3.
   ========================================================================== */

vi.mock('../api/stockApi', () => ({
  default: {
    getOnboardingFournisseur: vi.fn(),
    createDossierOnboarding: vi.fn(),
    createDocumentFournisseur: vi.fn(),
    televerserDocumentFournisseur: vi.fn(),
    validerDossierOnboarding: vi.fn(),
  },
}))

import stockApi from '../api/stockApi'
import OnboardingFournisseurWizard from './OnboardingFournisseurWizard.jsx'

const FOURNISSEUR = {
  id: 7, nom: 'SolarImport', ice: '001234567000012',
  identifiant_fiscal: '12345678', rc: 'RC-4455', rib: '',
}

const REQUIS = [
  'rc', 'attestation_fiscale', 'attestation_cnss', 'rib_certifie', 'assurance',
]

function reponse({ recus = [], expires = [], statut = 'En attente' } = {}) {
  const manquants = REQUIS.filter((t) => !recus.includes(t))
  return {
    data: {
      dossier: {
        id: 3, fournisseur: 7, statut: 'en_attente', statut_display: statut,
        documents: recus.map((t, i) => ({ id: i + 1, type_document: t })),
      },
      obligatoire: false,
      progression: {
        requis: REQUIS, recus, manquants, expires,
        progression_pct: Math.round(recus.length / REQUIS.length * 100),
        complet: manquants.length === 0,
      },
    },
  }
}

function renderWizard() {
  return render(
    <ThemeProvider>
      <OnboardingFournisseurWizard fournisseur={FOURNISSEUR} />
    </ThemeProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('OnboardingFournisseurWizard (NTP2P29)', () => {
  it('étape 1 — affiche l’identité légale du référentiel', async () => {
    stockApi.getOnboardingFournisseur.mockResolvedValue(reponse())
    renderWizard()
    expect(await screen.findByText('001234567000012')).toBeTruthy()
    expect(screen.getByText('RC-4455')).toBeTruthy()
    // Un champ vide est annoncé comme tel, jamais masqué.
    expect(screen.getByText('non renseigné')).toBeTruthy()
  })

  it('affiche la progression et bloque le récapitulatif si incomplet', async () => {
    stockApi.getOnboardingFournisseur.mockResolvedValue(
      reponse({ recus: ['rc', 'attestation_cnss'] }))
    renderWizard()

    const progression = await screen.findByTestId('onboarding-progression')
    expect(progression.textContent).toContain('2/5')

    // Étape 1 → 2 autorisé.
    fireEvent.click(screen.getByTestId('onboarding-suivant'))
    await waitFor(() =>
      expect(screen.getByTestId('onboarding-piece-rc')).toBeTruthy())

    // Étape 2 → 3 BLOQUÉ tant que des pièces manquent.
    expect(screen.getByTestId('onboarding-suivant')).toBeDisabled()
    expect(screen.getByText(/Récapitulatif accessible une fois/i)).toBeTruthy()
  })

  it('étape 2 — un statut par document', async () => {
    stockApi.getOnboardingFournisseur.mockResolvedValue(
      reponse({ recus: ['rc'], expires: ['assurance'] }))
    renderWizard()
    await screen.findByTestId('onboarding-progression')
    fireEvent.click(screen.getByTestId('onboarding-suivant'))

    const rc = await screen.findByTestId('onboarding-piece-rc')
    expect(rc.textContent).toContain('reçue')
    expect(screen.getByTestId('onboarding-piece-assurance').textContent)
      .toContain('expirée')
    expect(screen.getByTestId('onboarding-piece-rib_certifie').textContent)
      .toContain('manquante')
  })

  it('un dossier complet débloque le récapitulatif et la soumission', async () => {
    stockApi.getOnboardingFournisseur.mockResolvedValue(
      reponse({ recus: REQUIS }))
    stockApi.validerDossierOnboarding.mockResolvedValue({ data: {} })
    renderWizard()

    const progression = await screen.findByTestId('onboarding-progression')
    expect(progression.textContent).toContain('100%')

    fireEvent.click(screen.getByTestId('onboarding-suivant'))
    await waitFor(() =>
      expect(screen.getByTestId('onboarding-piece-rc')).toBeTruthy())
    expect(screen.getByTestId('onboarding-suivant')).not.toBeDisabled()

    fireEvent.click(screen.getByTestId('onboarding-suivant'))
    const bouton = await screen.findByRole(
      'button', { name: /Soumettre pour validation/i })
    expect(bouton).not.toBeDisabled()
    fireEvent.click(bouton)
    await waitFor(() =>
      expect(stockApi.validerDossierOnboarding).toHaveBeenCalledWith(
        3, { valider: true }))
  })

  it('propose d’ouvrir un dossier quand il n’en existe aucun', async () => {
    stockApi.getOnboardingFournisseur.mockResolvedValue({
      data: { dossier: null, obligatoire: false, progression: { requis: REQUIS, recus: [], manquants: REQUIS, expires: [], progression_pct: 0, complet: false } },
    })
    stockApi.createDossierOnboarding.mockResolvedValue({ data: { id: 9 } })
    renderWizard()

    const bouton = await screen.findByRole(
      'button', { name: /Ouvrir un dossier/i })
    fireEvent.click(bouton)
    await waitFor(() =>
      expect(stockApi.createDossierOnboarding).toHaveBeenCalledWith(
        { fournisseur: 7 }))
  })
})
