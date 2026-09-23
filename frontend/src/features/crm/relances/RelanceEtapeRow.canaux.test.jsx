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

import crmApi from '../../../api/crmApi'

const TOUCHES = exempleContrat('crm', 'relance_etape_v2').results
const ETAPE_APPEL = TOUCHES.find((t) => t.canal === 'appel')
const ETAPE_WHATSAPP = TOUCHES.find((t) => t.canal === 'whatsapp')
const MESSAGE = exempleContrat('crm', 'relance_etape_message')

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

describe('CAD78 — le script d’appel du fondateur est ENFIN affiché', () => {
  it('sur une touche d’appel scriptée, le script est visible sans modale et sans POST /whatsapp/', async () => {
    crmApi.getRelanceEtapeMessage.mockResolvedValue({ data: MESSAGE })
    const onOuvrirMessage = vi.fn()
    ligne(ETAPE_APPEL, { onOuvrirMessage })
    // La bulle est AU-DESSUS du bouton « Appeler », repliée par défaut.
    const bascule = screen.getByRole('button', { name: /Script d’appel/ })
    expect(bascule).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(bascule)
    expect(await screen.findByTestId('texte-touche-contenu')).toHaveTextContent(MESSAGE.message)
    // Lecture pure : le GET du rendu, jamais le POST qui journalise.
    expect(crmApi.getRelanceEtapeMessage).toHaveBeenCalledWith(ETAPE_APPEL.id)
    expect(crmApi.whatsappRelanceEtape).not.toHaveBeenCalled()
    expect(onOuvrirMessage).not.toHaveBeenCalled()
    // Le bouton « Appeler » reste là, à côté du script.
    expect(screen.getByRole('button', { name: /Appeler/ })).toBeInTheDocument()
  })

  it('une touche d’appel sans gabarit n’a pas de bulle de script', () => {
    ligne({ ...ETAPE_APPEL, template_cle: '' })
    expect(screen.queryByTestId('texte-touche')).not.toBeInTheDocument()
  })

  it('sur une touche e-mail, le bouton ne dit plus « WhatsApp » et n’ouvre plus la modale', async () => {
    crmApi.getRelanceEtapeMessage.mockResolvedValue({ data: MESSAGE })
    const onOuvrirMessage = vi.fn()
    ligne({ ...ETAPE_WHATSAPP, canal: 'email' }, { onOuvrirMessage })
    expect(screen.queryByRole('button', { name: /WhatsApp/ })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /^E-mail$/ }))
    expect(await screen.findByTestId('texte-touche-contenu')).toHaveTextContent(MESSAGE.message)
    expect(onOuvrirMessage).not.toHaveBeenCalled()
    expect(crmApi.whatsappRelanceEtape).not.toHaveBeenCalled()
  })

  it('une touche WhatsApp garde son bouton WhatsApp (la modale d’aperçu)', () => {
    const onOuvrirMessage = vi.fn()
    ligne(ETAPE_WHATSAPP, { onOuvrirMessage })
    fireEvent.click(screen.getByRole('button', { name: /WhatsApp/ }))
    expect(onOuvrirMessage).toHaveBeenCalledWith(ETAPE_WHATSAPP)
  })
})
