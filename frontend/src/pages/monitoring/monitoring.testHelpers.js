/* Harnais partagé des tests de pages monitoring (ACAL345 — pas de copie). */
import { vi } from 'vitest'

/** installationsApi mocké : une installation supervisée (INST-2026-001). */
export const installationsApiAmrani = () => ({
  default: {
    getInstallations: vi.fn(() => Promise.resolve({
      data: [{ id: 11, reference: 'INST-2026-001', client_nom: 'Amrani' }],
    })),
  },
})
