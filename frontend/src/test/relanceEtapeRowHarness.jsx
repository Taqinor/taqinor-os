import { vi } from 'vitest'
import { render } from '@testing-library/react'
import RelanceEtapeRow from '../features/crm/relances/RelanceEtapeRow'

/* Banc COMMUN des suites `RelanceEtapeRow.*.test.jsx` (ENF19) : toasts et
   `crmApi` neutralisés une fois pour toutes (importer ce module AVANT le
   composant), rendu d'une ligne de touche. */
vi.mock('../lib/toast', () => ({ toastInfo: vi.fn(), toastSuccess: vi.fn(), toastError: vi.fn() }))
vi.mock('../api/crmApi', () => ({
  default: {
    getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })),
    getRelanceEtapeMessage: vi.fn(),
    whatsappRelanceEtape: vi.fn(),
    enregistrerPieceRecue: vi.fn(),
  },
}))

export function noop() {}

export function ligne(etape, props = {}) {
  return render(
    <RelanceEtapeRow
      etape={etape} onFait={noop} onSauter={noop} onReporter={noop}
      onOuvrirMessage={noop} {...props}
    />,
  )
}
