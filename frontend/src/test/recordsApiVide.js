import { vi } from 'vitest'

/* Objet `vi.mock('…/api/recordsApi')` des rails contexte (ENF19) : activités et
   pièces jointes vides. Usage :
     vi.mock('…/api/recordsApi', async () => (await import('…/test/recordsApiVide')).recordsApiVide()) */
export function recordsApiVide() {
  return {
    default: {
      getActivities: vi.fn(() => Promise.resolve({ data: [] })),
      getAttachments: vi.fn(() => Promise.resolve({ data: [] })),
    },
  }
}
