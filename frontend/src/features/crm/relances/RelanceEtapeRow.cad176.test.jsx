// CAD176 — la touche e-mail rend un texte ET dit à qui il s'adresse.
// Avant : `TexteDeTouche` affichait le texte sans jamais dire son destinataire
// (le contrat `relance_etape_v2` ne servait pas `lead_email`) — le bouton
// « E-mail » ouvrait le texte sans adresse ni lien `mailto:`.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import RelanceEtapeRow from './RelanceEtapeRow'

vi.mock('../../../lib/toast', () => ({ toastInfo: vi.fn(), toastSuccess: vi.fn(), toastError: vi.fn() }))

vi.mock('../../../api/crmApi', () => ({
  default: {
    getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })),
    getRelanceEtapeMessage: vi.fn(),
    whatsappRelanceEtape: vi.fn(),
    enregistrerPieceRecue: vi.fn(),
  },
}))

import crmApi from '../../../api/crmApi'

// Touches COMMITTÉES du contrat `relance_etape_v2.json` (PACT10) — jamais un
// objet retapé à la main. `exemple.results[0]` porte `lead_email` renseigné ;
// `exemple_pii_masquee.results[0]` le porte masqué (chaîne vide).
const AVEC_EMAIL = exempleContrat('crm', 'relance_etape_v2').results[0]
const EMAIL_MASQUE = exempleContrat('crm', 'relance_etape_v2', 'exemple_pii_masquee').results[0]
const MESSAGE = exempleContrat('crm', 'relance_etape_message')

afterEach(() => { cleanup(); vi.clearAllMocks() })

function noop() {}

function ligne(etape) {
  return render(
    <RelanceEtapeRow
      etape={etape} onFait={noop} onSauter={noop} onReporter={noop}
      onOuvrirMessage={noop}
    />,
  )
}

describe('CAD176 — le panneau e-mail affiche un texte et l’adresse', () => {
  it('une touche e-mail avec adresse montre l’adresse à côté du texte', async () => {
    crmApi.getRelanceEtapeMessage.mockResolvedValue({ data: MESSAGE })
    ligne({ ...AVEC_EMAIL, canal: 'email', template_cle: 'relance_email_j10' })
    fireEvent.click(screen.getByRole('button', { name: /^E-mail$/ }))
    expect(await screen.findByTestId('texte-touche-contenu')).toHaveTextContent(MESSAGE.message)
    expect(screen.getByTestId('texte-touche-destinataire'))
      .toHaveTextContent(AVEC_EMAIL.lead_email)
  })

  it('une adresse masquée ou absente le dit, jamais un silence', async () => {
    crmApi.getRelanceEtapeMessage.mockResolvedValue({ data: MESSAGE })
    ligne({ ...EMAIL_MASQUE, canal: 'email', template_cle: 'relance_email_j10' })
    fireEvent.click(screen.getByRole('button', { name: /^E-mail$/ }))
    expect(await screen.findByTestId('texte-touche-destinataire'))
      .toHaveTextContent('aucune adresse e-mail sur la fiche')
  })
})
