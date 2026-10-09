import { vi } from 'vitest'

/* Doublures partagées des tests de « Ma journée » : la fiche monte TOUS les
   panneaux terrain (F5-F19), chacun appelle son endpoint au montage — même
   stub « rejet gracieux » partout (check_duplicats_litteraux). */

const rejet = () => Promise.reject(new Error('non mocké'))

export function panneauxRejetes() {
  return {
    getPreparation: vi.fn(rejet),
    getPhotos: vi.fn(rejet),
    getSerials: vi.fn(rejet),
    getConsommation: vi.fn(rejet),
    getMemos: vi.fn(rejet),
    getReserves: vi.fn(rejet),
    getSafety: vi.fn(rejet),
    getToolReturn: vi.fn(rejet),
    getCode: vi.fn(rejet),
    compteRenduUrl: vi.fn(() => ''),
  }
}

// `toast` vient de `ui/Toaster` : c'est CE module qu'il faut doubler.
export const toastMock = {
  success: vi.fn(), error: vi.fn(), info: vi.fn(), message: vi.fn(),
}
export const toasterMock = { toast: toastMock, Toaster: () => null, default: () => null }
