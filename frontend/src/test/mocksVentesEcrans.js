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
