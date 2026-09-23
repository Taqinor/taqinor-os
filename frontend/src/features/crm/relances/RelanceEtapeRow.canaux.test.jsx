// Lane CAD-ROW3 — la ligne de touche : canaux, langues, messages. Étapes de
// départ = les touches du contrat COMMITTÉ `relance_etape_v2.json` (PACT10),
// jamais un objet retapé à la main.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import RelanceEtapeRow from './RelanceEtapeRow'

vi.mock('../../../lib/toast', () => ({ toastInfo: vi.fn(), toastSuccess: vi.fn(), toastError: vi.fn() }))

vi.mock('../../../api/crmApi', () => ({
  default: {
    getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })),
    getRelanceEtapeMessage: vi.fn(),
    whatsappRelanceEtape: vi.fn(),
  },
}))

const TOUCHES = exempleContrat('crm', 'relance_etape_v2').results
const ETAPE_APPEL = TOUCHES.find((t) => t.canal === 'appel')

afterEach(() => { cleanup(); vi.clearAllMocks() })

function noop() {}

function ligne(etape, props = {}) {
  return render(
    <RelanceEtapeRow
      etape={etape} onFait={noop} onSauter={noop} onReporter={noop}
      onOuvrirMessage={noop} {...props}
    />,
  )
}

describe('CAD63 — la réponse « ne parle que darija » sur la touche', () => {
  it('cochée, elle part AVEC la réponse et pose la langue sur la fiche', async () => {
    const onFait = vi.fn(() => Promise.resolve({}))
    ligne(ETAPE_APPEL, { onFait })
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Pas de réponse' }))
    fireEvent.click(screen.getByRole('checkbox', { name: /ne parle que darija/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(onFait).toHaveBeenCalledWith(
      ETAPE_APPEL.id, { outcome: 'non_joint', langue: 'darija' }))
  })

  it('jamais cochée d’office, et absente pour un lead déjà en darija', () => {
    const { unmount } = ligne(ETAPE_APPEL)
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    expect(screen.getByRole('checkbox', { name: /ne parle que darija/ })).not.toBeChecked()
    unmount()
    ligne({ ...ETAPE_APPEL, lead_langue: 'darija' })
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    expect(screen.queryByTestId('ne-parle-que-darija')).not.toBeInTheDocument()
  })

  it('un refus serveur sur la langue s’affiche SOUS la case, avec le message exact', async () => {
    const erreur = { response: { status: 400, data: { erreurs: { langue: '« Langue du message » : « xx » n’est pas une langue de relance.' } } } }
    const onFait = vi.fn(() => Promise.reject(erreur))
    ligne(ETAPE_APPEL, { onFait })
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Pas de réponse' }))
    fireEvent.click(screen.getByRole('checkbox', { name: /ne parle que darija/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    expect(await screen.findByTestId('erreur-langue')).toHaveTextContent('« Langue du message »')
  })
})
