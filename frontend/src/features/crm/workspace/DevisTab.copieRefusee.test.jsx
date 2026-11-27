import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { initState } from './draftCore'
import DevisTab from './DevisTab'

/* ACAL1243 — sorti de `DevisTab.test.jsx` (fichier gelé, C20) : presse-papier
   refusé APRÈS l'envoi. Même harnais que ce fichier (mêmes mocks d'API, même
   `renderTab`, même `ouvrirEnvoi`), réduit à ce que ce cas lit. */

const { shareLinkDevis } = vi.hoisted(() => ({
  // L5/L-NIV-UI/L-INTPREV — mint/réutilisation du ShareLink (format de POST .../share-link/).
  shareLinkDevis: vi.fn(() => Promise.resolve({
    data: {
      token: 'tok-abc', path: '/proposition/karim/tok-abc',
      token_interne: 'tok-int-xyz', path_interne: '/proposition/karim/tok-int-xyz',
      niveau: 'standard', otp_lecture: false,
    },
  })),
}))
vi.mock('../../../api/ventesApi', async () => ({
  default: {
    apercuFacturerVente: vi.fn(), shareLinkDevis,
    getOffresTaillesDevis: vi.fn(() => Promise.resolve({ data: { editable: false } })),
    reviserDevis: vi.fn(() => Promise.resolve({ data: { id: 99, reference: 'DEV-V2' } })),
    envoyerEmailDevis: vi.fn(() => Promise.resolve({ data: { statut: 'envoye' } })),
    // AGEN12 — la conception servie du lead (aucune par défaut : rien à dire).
    getConceptionLead: vi.fn(() => Promise.reject(new Error('conception_absente'))),
    ...(await import('../../../test/mocksVentesEcrans.js')).gestesFactureVente(),
  },
}))
vi.mock('../../../utils/pdfBlob', async (orig) => (await import('../../../test/mocksVentesEcrans.js')).pdfBlobSansOuverture(await orig()))
vi.mock('../../../api/installationsApi', () => ({ default: { createFromDevis: vi.fn() } }))
vi.mock('../../../api/stockApi', () => ({
  default: { getProduits: vi.fn(() => Promise.resolve({ data: { results: [], count: 0, next: null } })) },
}))
vi.mock('../../../api/crmApi', () => ({
  default: {
    whatsappDevis: vi.fn(() => Promise.resolve({ data: {} })),
    whatsappDevisApercu: vi.fn(),
    noterLead: vi.fn(() => Promise.resolve({ data: {} })),
    updateLead: vi.fn(() => Promise.resolve({ data: {} })),
    getLeadSalleVenteAnalytics: () => Promise.resolve({ data: null }),
  },
}))

beforeAll(() => {
  if (!window.HTMLElement.prototype.scrollIntoView) window.HTMLElement.prototype.scrollIntoView = () => {}
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

const leadState = (leadOverrides = {}) => initState({
  lead: {
    id: 7, nom: 'Karim', telephone: '0612345678', whatsapp: '',
    devis: [], devis_auto: { pret: true, manquants: [], message: null },
    ...leadOverrides,
  },
  mode: 'edit',
})

function renderTab(props = {}) {
  return render(
    <MemoryRouter>
      <DevisTab
        state={leadState()}
        onAction={vi.fn()}
        wa={{ selected: [], langue: 'fr', preview: null }}
        onWaToggle={vi.fn()} onWaLangue={vi.fn()} onWaPreview={vi.fn()} onWaReset={vi.fn()}
        {...props}
      />
    </MemoryRouter>,
  )
}

// ALEA52 — la boîte d'envoi montre les trois canaux d'abord ; « Avancé » replié par défaut.
const ouvrirEnvoi = async (user, { avance = true } = {}) => {
  await user.click(screen.getByRole('button', { name: /Envoyer au client/ }))
  if (avance) await user.click(screen.getByRole('button', { name: /Avancé/ }))
}

describe('L5 — Page client / WhatsApp / Aperçu interne (par devis, via le dialogue d’envoi)', () => {
  const devis1 = {
    id: 1, reference: 'DEV-1', statut: 'envoye', total_ttc: '5000',
    date_creation: '2026-01-01', chantier: null,
  }

  it('ACAL1243 — presse-papier refusé après l’envoi : « Devis envoyé — copiez le lien ci-dessous », lien montré, aucune erreur de lien/connexion même si le rafraîchissement échoue', async () => {
    const user = userEvent.setup()
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn(() => Promise.reject(new Error('NotAllowedError'))) },
      configurable: true, writable: true,
    })
    const onAction = vi.fn(() => Promise.reject(new Error('La connexion a expiré')))
    renderTab({ state: leadState({ devis: [devis1] }), onAction })
    await ouvrirEnvoi(user, { avance: false })
    await user.click(screen.getByRole('button', { name: /Copier le lien/ }))
    expect(await screen.findByTestId('envoi-lien-client'))
      .toHaveValue('https://taqinor.ma/proposition/karim/tok-abc')
    expect(await screen.findByText(/Devis envoyé — copiez le lien ci-dessous/)).toBeInTheDocument()
    await waitFor(() => expect(onAction).toHaveBeenCalledWith('refresh'))
    expect(screen.queryByText(/Lien de la page client indisponible|La connexion a expiré/)).toBeNull()
  })
})
