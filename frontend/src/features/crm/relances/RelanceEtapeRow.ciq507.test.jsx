// CIQ507 — une touche e-mail montre l'OBJET, ouvre la messagerie (lien
// `mailto:` construit par le serveur, CIQ506) et rappelle de joindre le PDF.
// Aucun envoi, aucun POST `whatsapp/` : la touche reste à faire jusqu'à « Fait ».
// Les charges utiles viennent des exemples COMMITTÉS du contrat (PACT10) :
// `relance_etape_v2.json` (`exemple_fixe_email`, la touche) et
// `relance_etape_message.json` (`exemple_email_societe`, le rendu).
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import RelanceEtapeRow from './RelanceEtapeRow'

const API = vi.hoisted(() => ({
  getRelanceEtapeMessage: vi.fn(),
  whatsappRelanceEtape: vi.fn(),
  getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })),
}))
vi.mock('../../../api/crmApi', () => ({ default: API }))
vi.mock('../../../lib/toast', () => ({ toastInfo: vi.fn() }))

const crmApi = API

const TOUCHE_EMAIL = exempleContrat('crm', 'relance_etape_v2', 'exemple_fixe_email').results[0]
const TOUCHE_WHATSAPP = exempleContrat('crm', 'relance_etape_v2').results
  .find((t) => t.canal === 'whatsapp')
const RENDU_EMAIL = exempleContrat('crm', 'relance_etape_message', 'exemple_email_societe')
const RENDU_SANS_ADRESSE = exempleContrat('crm', 'relance_etape_message', 'exemple_societe_absente')

afterEach(() => { cleanup(); vi.clearAllMocks() })

// Gestes inertes : ces tests ne vérifient QUE le panneau du texte.
const GESTES_INERTES = {
  onFait: () => {}, onSauter: () => {}, onReporter: () => {}, onOuvrirMessage: () => {},
}

const ligne = (etape) => render(<RelanceEtapeRow etape={etape} {...GESTES_INERTES} />)

async function ouvrirTexte(rendu) {
  crmApi.getRelanceEtapeMessage.mockResolvedValue({ data: rendu })
  fireEvent.click(screen.getByRole('button', { name: /^E-mail$/ }))
  await screen.findByTestId('texte-touche-contenu')
}

describe('CIQ507 — touche e-mail : objet, messagerie, rappel du PDF', () => {
  it('montre l’objet, le bouton « Ouvrir dans la messagerie » et la ligne PDF', async () => {
    ligne(TOUCHE_EMAIL)
    await ouvrirTexte(RENDU_EMAIL)
    expect(screen.getByTestId('texte-touche-objet')).toHaveTextContent(RENDU_EMAIL.objet)
    const lien = screen.getByTestId('ouvrir-messagerie')
    expect(lien).toHaveTextContent('Ouvrir dans la messagerie')
    expect(lien).toHaveAttribute('href', RENDU_EMAIL.mailto_url)
    expect(screen.getByTestId('texte-touche-pdf'))
      .toHaveTextContent('Joignez le PDF de la proposition avant d’envoyer')
  })

  it('la phrase canal_adapte s’affiche sous le libellé', () => {
    ligne(TOUCHE_EMAIL)
    expect(TOUCHE_EMAIL.canal_adapte).toBeTruthy()
    expect(screen.getByTestId('canal-adapte')).toHaveTextContent(TOUCHE_EMAIL.canal_adapte)
  })

  it('le bouton est absent quand mailto_url vaut null', async () => {
    ligne(TOUCHE_EMAIL)
    await ouvrirTexte({ ...RENDU_SANS_ADRESSE, objet: RENDU_EMAIL.objet, mailto_url: null })
    expect(screen.queryByTestId('ouvrir-messagerie')).not.toBeInTheDocument()
    // L'objet et le rappel du PDF restent affichés.
    expect(screen.getByTestId('texte-touche-objet')).toBeInTheDocument()
    expect(screen.getByTestId('texte-touche-pdf')).toBeInTheDocument()
  })

  it('le clic n’envoie aucun POST', async () => {
    ligne(TOUCHE_EMAIL)
    await ouvrirTexte(RENDU_EMAIL)
    const lien = screen.getByTestId('ouvrir-messagerie')
    // jsdom ne navigue pas vers un `mailto:` : on empêche l'action par défaut.
    lien.addEventListener('click', (e) => e.preventDefault())
    fireEvent.click(lien)
    expect(crmApi.whatsappRelanceEtape).not.toHaveBeenCalled()
    expect(crmApi.getRelanceEtapeMessage).toHaveBeenCalledTimes(1)
  })

  it('« Copier » copie l’objet et le corps', async () => {
    const ecrire = vi.fn(() => Promise.resolve())
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: ecrire }, configurable: true })
    ligne(TOUCHE_EMAIL)
    await ouvrirTexte(RENDU_EMAIL)
    fireEvent.click(screen.getByRole('button', { name: /Copier/ }))
    await waitFor(() => expect(ecrire).toHaveBeenCalledWith(
      `Objet : ${RENDU_EMAIL.objet}\n\n${RENDU_EMAIL.message}`))
  })

  it('une touche WhatsApp rend exactement l’écran actuel (ni objet, ni messagerie)', () => {
    ligne(TOUCHE_WHATSAPP)
    expect(screen.queryByTestId('texte-touche-objet')).not.toBeInTheDocument()
    expect(screen.queryByTestId('ouvrir-messagerie')).not.toBeInTheDocument()
    expect(screen.queryByTestId('texte-touche-pdf')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /WhatsApp/ })).toBeInTheDocument()
  })
})
