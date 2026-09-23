import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'

/* Lane CAD-ROW3 — la modale d'aperçu du message d'une touche (canaux,
   langues, messages). Charges utiles = les exemples COMMITTÉS
   `apps/crm/contract_samples/relance_etape_message.json` (le rendu) et
   `relance_etape_v2.json` (la touche) — jamais un objet retapé à la main
   (PACT10). */
import { exempleContrat } from '../../../test/fixtures/contractSamples'

const TOUCHES = exempleContrat('crm', 'relance_etape_v2').results
// La touche WhatsApp du contrat (lead en français).
const ETAPE = TOUCHES.find((t) => t.canal === 'whatsapp')
const MESSAGE = exempleContrat('crm', 'relance_etape_message')
const MESSAGE_DARIJA = exempleContrat('crm', 'relance_etape_message', 'exemple_darija')

vi.mock('../../../api/crmApi', () => ({
  default: {
    getRelanceEtapeMessage: vi.fn(),
    getRelanceEtapeMessageLangue: vi.fn(),
    whatsappRelanceEtape: vi.fn(),
    whatsappRelanceEtapeLangue: vi.fn(),
    definirLangueRelanceEtape: vi.fn(),
  },
}))

import crmApi from '../../../api/crmApi'
import ToucheMessageDialog from './ToucheMessageDialog'

beforeEach(() => {
  crmApi.getRelanceEtapeMessage.mockResolvedValue({ data: MESSAGE })
  crmApi.getRelanceEtapeMessageLangue.mockResolvedValue({ data: MESSAGE_DARIJA })
  crmApi.whatsappRelanceEtape.mockResolvedValue({ data: { ...MESSAGE, etape: ETAPE } })
  crmApi.whatsappRelanceEtapeLangue.mockResolvedValue({ data: { ...MESSAGE_DARIJA, etape: ETAPE } })
  crmApi.definirLangueRelanceEtape.mockResolvedValue({ data: { ...ETAPE, lead_langue: 'darija' } })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('CAD63 — changer la langue au moment utile', () => {
  it('le basculeur recharge le texte dans l’autre langue, sans toucher la fiche', async () => {
    render(<ToucheMessageDialog etape={ETAPE} open onOpenChange={() => {}} />)
    expect(await screen.findByText(MESSAGE.message)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'FR' })).toHaveAttribute('aria-pressed', 'true')

    fireEvent.click(screen.getByRole('button', { name: 'Darija' }))
    await waitFor(() => expect(crmApi.getRelanceEtapeMessageLangue)
      .toHaveBeenCalledWith(ETAPE.id, { cle: undefined, langue: 'darija' }))
    expect(await screen.findByText(MESSAGE_DARIJA.message)).toBeInTheDocument()
    // Basculer l'aperçu n'enregistre rien : seule la confirmation le fait.
    expect(crmApi.definirLangueRelanceEtape).not.toHaveBeenCalled()
  })

  it('« C’est sa langue » enregistre la darija sur la fiche (confirmation explicite)', async () => {
    const onLangueEnregistree = vi.fn()
    render(
      <ToucheMessageDialog
        etape={ETAPE} open onOpenChange={() => {}} onLangueEnregistree={onLangueEnregistree}
      />,
    )
    await screen.findByText(MESSAGE.message)
    // Aucune proposition tant que la langue affichée est celle de la fiche.
    expect(screen.queryByTestId('enregistrer-langue-client')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Darija' }))
    await screen.findByText(MESSAGE_DARIJA.message)
    fireEvent.click(screen.getByTestId('enregistrer-langue-client'))
    await waitFor(() => expect(crmApi.definirLangueRelanceEtape)
      .toHaveBeenCalledWith(ETAPE.id, 'darija'))
    await waitFor(() => expect(onLangueEnregistree).toHaveBeenCalledWith(ETAPE.id, 'darija'))
  })

  it('« Ouvrir WhatsApp » après bascule : le serveur vérifie le rendu dans la langue choisie', async () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => {})
    render(<ToucheMessageDialog etape={ETAPE} open onOpenChange={() => {}} />)
    await screen.findByText(MESSAGE.message)
    fireEvent.click(screen.getByRole('button', { name: 'Darija' }))
    await screen.findByText(MESSAGE_DARIJA.message)
    fireEvent.click(screen.getByRole('button', { name: /Ouvrir WhatsApp/ }))
    expect(openSpy).toHaveBeenCalledWith(MESSAGE_DARIJA.wa_url, '_blank', 'noopener')
    await waitFor(() => expect(crmApi.whatsappRelanceEtapeLangue)
      .toHaveBeenCalledWith(ETAPE.id, 'darija'))
    expect(crmApi.whatsappRelanceEtape).not.toHaveBeenCalled()
    openSpy.mockRestore()
  })
})

describe('CAD69 — les crochets ne partent jamais tels quels', () => {
  const CROCHETS = exempleContrat('crm', 'relance_etape_message', 'exemple_crochets')

  it('un texte contenant […] affiche l’avertissement et désactive « Ouvrir WhatsApp »', async () => {
    crmApi.getRelanceEtapeMessage.mockResolvedValue({ data: CROCHETS })
    render(<ToucheMessageDialog etape={ETAPE} open onOpenChange={() => {}} />)
    await screen.findByText(CROCHETS.message)
    const bandeau = screen.getByTestId('crochets-a-completer')
    expect(bandeau).toHaveTextContent('[jour], [heure]')
    expect(screen.getByRole('button', { name: /Ouvrir WhatsApp/ })).toBeDisabled()
    // Le texte reste copiable pour être complété dans la conversation.
    expect(screen.getByRole('button', { name: /Copier/ })).not.toBeDisabled()
  })

  it('la conversation s’ouvre SANS texte pré-rempli (jamais un crochet envoyé)', async () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => {})
    crmApi.getRelanceEtapeMessage.mockResolvedValue({ data: CROCHETS })
    render(<ToucheMessageDialog etape={ETAPE} open onOpenChange={() => {}} />)
    await screen.findByText(CROCHETS.message)
    fireEvent.click(screen.getByRole('button', { name: /Ouvrir la conversation/ }))
    const url = openSpy.mock.calls[0][0]
    expect(url).toBe(CROCHETS.wa_url.split('?text=')[0])
    expect(url).not.toContain('%5B')
    await waitFor(() => expect(crmApi.whatsappRelanceEtape).toHaveBeenCalledWith(ETAPE.id))
    openSpy.mockRestore()
  })

  it('sans crochet : aucun bandeau, « Ouvrir WhatsApp » actif', async () => {
    render(<ToucheMessageDialog etape={ETAPE} open onOpenChange={() => {}} />)
    await screen.findByText(MESSAGE.message)
    expect(screen.queryByTestId('crochets-a-completer')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Ouvrir WhatsApp/ })).not.toBeDisabled()
  })
})

describe('CAD70 — sans catalogue Réalisations, le J4 le dit et guide', () => {
  const SANS_PREUVE = exempleContrat('crm', 'relance_etape_message', 'exemple_preuve_manquante')
  const ETAPE_J4 = TOUCHES.find((t) => t.template_cle === 'j4_preuve')

  it('catalogue vide : le CTA WhatsApp est remplacé par le message d’aide', async () => {
    crmApi.getRelanceEtapeMessage.mockResolvedValue({ data: SANS_PREUVE })
    render(<ToucheMessageDialog etape={ETAPE_J4} open onOpenChange={() => {}} />)
    const aide = await screen.findByTestId('preuve-manquante')
    expect(aide).toHaveTextContent('Aucune réalisation publiée : choisissez-en une ou passez cette touche.')
    expect(aide.querySelector('a')).toHaveAttribute('href', '/parametres')
    expect(screen.queryByRole('button', { name: /Ouvrir WhatsApp/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Copier/ })).not.toBeInTheDocument()
    // La phrase orpheline n'est jamais proposée.
    expect(screen.queryByText(SANS_PREUVE.message)).not.toBeInTheDocument()
  })

  it('catalogue rempli : le texte complet est proposé et part', async () => {
    render(<ToucheMessageDialog etape={ETAPE_J4} open onOpenChange={() => {}} />)
    expect(await screen.findByText(MESSAGE.message)).toBeInTheDocument()
    expect(screen.queryByTestId('preuve-manquante')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Ouvrir WhatsApp/ })).not.toBeDisabled()
  })
})

describe('CAD78 — une touche e-mail n’est jamais présentée comme un WhatsApp', () => {
  it('titre « E-mail », aucun CTA WhatsApp, le texte reste copiable', async () => {
    render(<ToucheMessageDialog etape={{ ...ETAPE, canal: 'email' }} open onOpenChange={() => {}} />)
    await screen.findByText(MESSAGE.message)
    expect(screen.getByRole('heading', { name: /^E-mail — / })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Ouvrir WhatsApp/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Copier/ })).toBeInTheDocument()
  })
})

describe('CAD79 — le « vocal » ne part plus en texte écrit', () => {
  const VOCAL = exempleContrat('crm', 'relance_etape_message', 'exemple_vocal')

  it('le CTA et l’intitulé disent « note vocale », le texte est un script à lire', async () => {
    crmApi.getRelanceEtapeMessage.mockResolvedValue({ data: VOCAL })
    render(<ToucheMessageDialog etape={ETAPE} open onOpenChange={() => {}} />)
    await screen.findByText(VOCAL.message)
    expect(screen.getByRole('heading', { name: /^Note vocale — / })).toBeInTheDocument()
    expect(screen.getByTestId('script-vocal')).toHaveTextContent('Script à lire en note vocale')
    expect(screen.getByRole('button', { name: /Enregistrer une note vocale/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Ouvrir WhatsApp/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Copier/ })).not.toBeDisabled()
  })

  it('le texte n’est PAS pré-rempli dans le lien ouvert', async () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => {})
    crmApi.getRelanceEtapeMessage.mockResolvedValue({ data: VOCAL })
    render(<ToucheMessageDialog etape={ETAPE} open onOpenChange={() => {}} />)
    await screen.findByText(VOCAL.message)
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer une note vocale/ }))
    const url = openSpy.mock.calls[0][0]
    expect(url).toBe(VOCAL.wa_url)
    expect(url).not.toContain('?text=')
    await waitFor(() => expect(crmApi.whatsappRelanceEtape).toHaveBeenCalledWith(ETAPE.id))
    openSpy.mockRestore()
  })
})

describe('CAD64 — le repli de langue est VISIBLE', () => {
  const REPLI = exempleContrat('crm', 'relance_etape_message', 'exemple_repli_langue')

  it('texte absent dans la langue du client : l’aperçu le dit, en nommant la langue', async () => {
    crmApi.getRelanceEtapeMessage.mockResolvedValue({ data: REPLI })
    render(<ToucheMessageDialog etape={ETAPE} open onOpenChange={() => {}} />)
    const bloc = await screen.findByText(REPLI.message)
    expect(screen.getByTestId('repli-langue'))
      .toHaveTextContent('Ce texte n’existe pas encore en arabe : c’est la version française qui partira.')
    // La version française partie en repli se lit de gauche à droite.
    expect(bloc).toHaveAttribute('dir', 'auto')
    expect(bloc).toHaveAttribute('lang', 'fr')
  })

  it('un lead darija dont la clé n’a pas de darija : « pas encore en darija »', async () => {
    const OMISE = exempleContrat('crm', 'relance_etape_message', 'exemple_phrase_omise')
    crmApi.getRelanceEtapeMessage.mockResolvedValue({ data: OMISE })
    render(<ToucheMessageDialog etape={ETAPE} open onOpenChange={() => {}} />)
    await screen.findByText(OMISE.message)
    expect(screen.getByTestId('repli-langue')).toHaveTextContent('pas encore en darija')
  })

  it('texte présent dans la langue demandée : aucun avertissement', async () => {
    crmApi.getRelanceEtapeMessage.mockResolvedValue({ data: MESSAGE_DARIJA })
    render(<ToucheMessageDialog etape={ETAPE} open onOpenChange={() => {}} />)
    const bloc = await screen.findByText(MESSAGE_DARIJA.message)
    expect(screen.queryByTestId('repli-langue')).not.toBeInTheDocument()
    expect(bloc).toHaveAttribute('dir', 'rtl')
  })
})
