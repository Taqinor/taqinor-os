// AFAC — fabriques de mocks partagées par les tests des écrans Ventes (relevé,
// relances, formulaire facture) : un seul endroit au lieu de blocs `vi.mock`
// recopiés (garde duplicats littéraux). Usage :
//   vi.mock('../../hooks/useHasPermission', async () => (await import('../../test/mocksVentesEcrans.js')).permissionsRefusees())
import { vi } from 'vitest'

// Hooks de permission : aucun droit (évite le store Redux dans les tests d'écran).
export const permissionsRefusees = () => ({
  useHasPermission: () => false,
  useHasRole: () => false,
  useIsAdmin: () => false,
  useIsAdminOrResponsable: () => false,
})

// `ui/confirm` : toasts espions + confirmation toujours acceptée.
export const confirmAccepte = () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  useConfirmDialog: () => ({
    confirm: () => Promise.resolve(true),
    confirmDelete: () => Promise.resolve(true),
  }),
})

// `api/axios` nu (get/post/patch espions).
export const axiosNu = () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } })

// `ventesApi` de l'écran Encaissements (liste vide + import de relevé).
export const ventesApiPaiements = () => ({
  default: {
    getPaiements: vi.fn().mockResolvedValue({ data: [] }),
    importReleveDryRun: vi.fn(),
    importReleveCommit: vi.fn(),
    rejeterPaiement: vi.fn(),
  },
})

// `ventesApi` / `stockApi` minimaux du formulaire facture (aucun BC, aucun produit).
export const ventesApiFormFacture = () => ({
  default: {
    getBonsCommande: vi.fn().mockResolvedValue({ data: { count: 0, next: null, results: [] } }),
    getFacture: vi.fn().mockResolvedValue({ data: {} }),
  },
})
export const stockApiVide = () => ({
  default: { getProduits: vi.fn().mockResolvedValue({ data: { results: [], next: null } }) },
})

// `parametresApi` réel + `getProfile` espionné (profil société posé par l'écran testé).
// Usage : vi.mock('../../api/parametresApi', async (importOriginal) =>
//   (await import('../../test/mocksVentesEcrans.js')).parametresApiProfil(await importOriginal(), {}))
export const parametresApiProfil = (actual, profil = {}) => ({
  ...actual,
  default: {
    ...actual.default,
    getProfile: vi.fn(() => Promise.resolve({ data: profil })),
  },
})

// `uxviewsApi` : aucune vue sauvegardée ; `creee` = réponse de createSavedView.
export const uxviewsApiVide = (creee = {}) => ({
  default: {
    listSavedViews: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    createSavedView: vi.fn(() => Promise.resolve({ data: creee })),
    updateSavedView: vi.fn(() => Promise.resolve({ data: {} })),
    deleteSavedView: vi.fn(() => Promise.resolve({})),
  },
})

// `ventesSlice` réel dont `fetchDevis` ne fait rien (la liste est pilotée par le store du test).
export const ventesSliceSansFetch = (actual) => ({
  ...actual, fetchDevis: () => ({ type: 'ventes/fetchDevis/noop' }),
})

// `crmApi` réel + `getMotifsPerte` vide.
export const crmApiMotifsPerteVide = (actual) => ({
  ...actual,
  default: { ...actual.default, getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })) },
})

// VNT76-78 — gestes d'une facture de la vente (panneau de vente du lead) :
// espions nus, chaque test fournit sa réponse depuis les contrats committés.
export const gestesFactureVente = () => ({
  emettreFacture: vi.fn(), whatsappFacture: vi.fn(), envoyerEmailFacture: vi.fn(),
  recuPdfPaiement: vi.fn(), genererPdfFacture: vi.fn(), telechargerPdfFacture: vi.fn(),
  getFacture: vi.fn(), enregistrerPaiement: vi.fn(), arrondiCaisseFacture: vi.fn(),
  annulerFacture: vi.fn(), supprimerFacture: vi.fn(), montantTrancheFacture: vi.fn(),
  prixNegocie: vi.fn(), demanderSignatureAvenant: vi.fn(),
})

// `utils/pdfBlob` réel dont l'ouverture du PDF ne fait rien (espion).
export const pdfBlobSansOuverture = (actual) => ({ ...actual, openPdfBlob: vi.fn() })
