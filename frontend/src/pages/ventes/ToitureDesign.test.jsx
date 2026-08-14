import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

/* PV20 — MODE DEVIS de l'écran de conception 3D.

   PACT13 : la charge utile n'est PAS tapée à la main. Elle vient de l'exemple
   COMMITTÉ dans l'app (`apps/ventes/contract_samples/devis_design_context.json`),
   le même fichier que `scripts/check_api_shapes.py` compare au dictionnaire
   RÉELLEMENT renvoyé par `selectors.contexte_conception_devis`. Si le serveur
   change de forme, l'exemple change et ce test casse tout seul.

   Le mode LEAD est verrouillé par un test GOLDEN (dernier bloc) : il doit
   rester strictement inchangé — même appels, même hydratation, même bouton. */

vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))
vi.mock('../../api/ventesApi', () => ({
  default: {
    getDevisDesignContext: vi.fn(),
    syncDevisLayout: vi.fn(),
    shareLinkDevis: vi.fn(),
    whatsappPreviewDevis: vi.fn(),
    reviserDevis: vi.fn(),
  },
}))
vi.mock('../../lib/toast', () => ({ toastInfo: vi.fn() }))
const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigateMock }
})

// Le builder est stubé : il expose seulement l'API que la page consomme
// (`serializeLayout` / `snapshot`), posée via `onApiReady` comme en vrai.
const LAYOUT = { version: 2, zones: [{ id: 'z1' }] }
const serializeLayout = vi.fn(() => LAYOUT)
const snapshot = vi.fn(() => null)
const initRoofToolPro8 = vi.fn((options) => {
  options?.onApiReady?.({ serializeLayout, snapshot })
})
vi.mock('@roofbuilder', () => ({ initRoofToolPro8: (...a) => initRoofToolPro8(...a) }))

import userEvent from '@testing-library/user-event'
import api from '../../api/axios'
import ventesApi from '../../api/ventesApi'
import { toastInfo } from '../../lib/toast'
import ToitureDesign from './ToitureDesign'

const CTX = exempleContrat('ventes', 'devis_design_context')
const CTX_RO = exempleContrat('ventes', 'devis_design_context',
  'exemple_lecture_seule')

function rendreDevis(id) {
  return render(
    <MemoryRouter initialEntries={[`/ventes/devis/${id}/design`]}>
      <Routes>
        <Route path="/ventes/devis/:id/design"
          element={<ToitureDesign mode="devis" />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  delete window.__taqinorRoofBooted
  serializeLayout.mockReturnValue(LAYOUT)
  snapshot.mockReturnValue(null)
  initRoofToolPro8.mockImplementation((options) => {
    options?.onApiReady?.({ serializeLayout, snapshot })
  })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ToitureDesign — mode devis (PV20)', () => {
  it('boote sur UN SEUL appel design-context et hydrate le builder depuis le devis', async () => {
    ventesApi.getDevisDesignContext.mockResolvedValue(
      reponseContrat('ventes', 'devis_design_context'))

    rendreDevis(CTX.devis.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    // UN SEUL appel : rien n'est complété par une requête annexe (ni le lead,
    // ni la config carte — la clé MapTiler vient du contexte).
    expect(ventesApi.getDevisDesignContext).toHaveBeenCalledTimes(1)
    expect(ventesApi.getDevisDesignContext)
      .toHaveBeenCalledWith(String(CTX.devis.id))
    expect(api.get).not.toHaveBeenCalled()

    const options = initRoofToolPro8.mock.calls[0][0]
    expect(options.maptilerKey).toBe(CTX.carte.maptilerKey)
    // `hydrate.devis` (PV19) et NON `hydrate.lead` : le devis fait foi.
    expect(options.hydrate.lead).toBeUndefined()
    expect(options.hydrate.devis).toEqual({
      id: CTX.devis.id,
      geometrie: {
        roof_layout: CTX.geometrie.roof_layout,
        roof_point: CTX.geometrie.pin,
        roof_outline: CTX.geometrie.outline,
      },
      cible: {
        panneaux: CTX.cible.panneaux,
        panel_watt: CTX.cible.panel_watt,
        scenario: CTX.cible.scenario,
      },
      fullName: CTX.devis.client_nom,
    })

    // L'en-tête porte la référence + le client SERVIS par le contexte.
    expect(await screen.findByRole('heading', { level: 1 }))
      .toHaveTextContent(CTX.devis.reference)
    expect(screen.getByRole('heading', { level: 1 }))
      .toHaveTextContent(CTX.devis.client_nom)
    // Modifiable : aucun bandeau de lecture seule.
    expect(screen.queryByTestId('pv20-lecture-seule')).toBeNull()
    // Le bouton du flux LEAD n'existe jamais ici : on ne recrée pas un devis.
    expect(screen.queryByRole('button',
      { name: /Générer le devis & envoyer au client/ })).toBeNull()
  })

  it('lecture seule : le MOTIF vient du serveur et le CTA renvoie vers la 3D', async () => {
    ventesApi.getDevisDesignContext.mockResolvedValue(
      reponseContrat('ventes', 'devis_design_context', 'exemple_lecture_seule'))

    rendreDevis(CTX_RO.devis.id)

    const bandeau = await screen.findByTestId('pv20-lecture-seule')
    // Le motif est affiché TEL QUEL — jamais rédigé côté écran.
    expect(bandeau).toHaveTextContent(CTX_RO.raison_lecture_seule)
    const cta = screen.getByRole('link', { name: 'Voir en 3D' })
    expect(cta).toHaveAttribute('href', `/ventes/devis/${CTX_RO.devis.id}/3d`)
    // Le designer boote quand même (consultation), sans action d'enregistrement.
    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(screen.queryByRole('button',
      { name: /Générer le devis & envoyer au client/ })).toBeNull()
    // Les avertissements du serveur sont rendus, pas inventés.
    for (const a of CTX_RO.avertissements) {
      expect(screen.getByTestId('pv20-avertissements')).toHaveTextContent(a)
    }
  })

  it('devis introuvable : message FR, aucun boot du builder', async () => {
    ventesApi.getDevisDesignContext.mockRejectedValue({ response: { status: 404 } })

    rendreDevis(999)

    expect(await screen.findByRole('alert')).toHaveTextContent('Devis introuvable.')
    expect(initRoofToolPro8).not.toHaveBeenCalled()
  })
})

/* PV21 — la boucle de finalisation du mode devis : resynchronisation des lignes
   sur le calepinage, « aucun changement », et le geste « Réviser (v2) » quand le
   client a déjà la version sous les yeux. */
describe('ToitureDesign — PV21 : enregistrer la conception', () => {
  async function ouvrirModifiable() {
    ventesApi.getDevisDesignContext.mockResolvedValue(
      reponseContrat('ventes', 'devis_design_context'))
    rendreDevis(CTX.devis.id)
    return screen.findByRole('button', { name: /Enregistrer la conception/ })
  }

  it('resynchronise les lignes, envoie la 3D et ouvre le bloc de livraison', async () => {
    snapshot.mockReturnValue('data:image/png;base64,QUJD')
    ventesApi.syncDevisLayout.mockResolvedValue({
      data: {
        inchange: false, panneaux: 24, kwc: 17.04, scenario: 'reseau',
        batterie: false, lignes_modifiees: 1, avertissements: [],
      },
    })
    ventesApi.shareLinkDevis.mockResolvedValue({ data: { token: 'tok', path: '/proposition/tok' } })
    ventesApi.whatsappPreviewDevis.mockResolvedValue({
      data: { wa_url: 'https://wa.me/212600000000?text=x', preview: true },
    })
    api.post.mockResolvedValue({ data: {} })

    const bouton = await ouvrirModifiable()
    await userEvent.click(bouton)

    await waitFor(() => expect(ventesApi.syncDevisLayout).toHaveBeenCalled())
    // Le layout envoyé est celui SÉRIALISÉ par le builder, sous l'enveloppe
    // `{layout}` que le serveur déballe.
    expect(ventesApi.syncDevisLayout).toHaveBeenCalledWith(
      String(CTX.devis.id), { layout: LAYOUT })
    // Instantané 3D poussé sur le MÊME devis (best-effort, patron du flux lead).
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      `/ventes/devis/${CTX.devis.id}/roof-image/`, expect.any(FormData)))
    // Livraison : lien tokenisé + aperçu WhatsApp LECTURE SEULE (aucun
    // marquage « envoyé »).
    expect(await screen.findByText('Prêt à envoyer')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'WhatsApp' }))
      .toHaveAttribute('href', 'https://wa.me/212600000000?text=x')
    expect(screen.getByDisplayValue('https://taqinor.ma/proposition/tok'))
      .toBeInTheDocument()
    // Aucun devis n'a été recréé.
    expect(ventesApi.reviserDevis).not.toHaveBeenCalled()
  })

  it('même calepinage : « Aucun changement », rien n\'est envoyé ni livré', async () => {
    ventesApi.syncDevisLayout.mockResolvedValue({
      data: {
        inchange: true, panneaux: 24, kwc: 17.04, scenario: 'reseau',
        batterie: false, lignes_modifiees: 0, avertissements: [],
      },
    })

    const bouton = await ouvrirModifiable()
    await userEvent.click(bouton)

    await waitFor(() => expect(toastInfo).toHaveBeenCalledWith('Aucun changement'))
    expect(api.post).not.toHaveBeenCalled()
    expect(ventesApi.shareLinkDevis).not.toHaveBeenCalled()
    expect(screen.queryByText('Prêt à envoyer')).toBeNull()
  })

  it('409 révisable : encart « Réviser (v2) » → nouvelle version puis sa conception', async () => {
    ventesApi.syncDevisLayout.mockRejectedValue({
      response: {
        status: 409,
        data: {
          detail: 'Devis déjà envoyé au client — créez une révision (v2).',
          revision_possible: true,
        },
      },
    })
    ventesApi.reviserDevis.mockResolvedValue({ data: { id: 777, reference: 'DEV-2026-777' } })

    const bouton = await ouvrirModifiable()
    await userEvent.click(bouton)

    const encart = await screen.findByTestId('pv21-reviser')
    // Le motif affiché est celui du SERVEUR, jamais rédigé côté écran.
    expect(encart).toHaveTextContent('Devis déjà envoyé au client — créez une révision (v2).')

    await userEvent.click(screen.getByRole('button', { name: 'Réviser (v2)' }))
    await waitFor(() => expect(ventesApi.reviserDevis)
      .toHaveBeenCalledWith(String(CTX.devis.id)))
    expect(navigateMock).toHaveBeenCalledWith('/ventes/devis/777/design')
  })

  it('409 document clos : bandeau de lecture seule, aucune révision proposée', async () => {
    ventesApi.syncDevisLayout.mockRejectedValue({
      response: {
        status: 409,
        data: {
          detail: 'Devis accepté — aucune révision de calepinage possible.',
          revision_possible: false,
        },
      },
    })

    const bouton = await ouvrirModifiable()
    await userEvent.click(bouton)

    const bandeau = await screen.findByTestId('pv21-conflit-lecture-seule')
    expect(bandeau).toHaveTextContent('Devis accepté — aucune révision de calepinage possible.')
    expect(screen.queryByTestId('pv21-reviser')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Réviser (v2)' })).toBeNull()
  })
})

describe('ToitureDesign — mode lead GOLDEN (inchangé par PV20)', () => {
  it('charge le lead + la config carte et hydrate `hydrate.lead`', async () => {
    const lead = {
      id: 88, nom: 'Alaoui', prenom: 'Youssef', ville: 'Casablanca',
      telephone: '0600000000', roof_point: { lat: 33.5, lng: -7.6 },
      roof_outline: [[33.5, -7.6]], bill_kwh: 7200,
    }
    api.get.mockImplementation((url) => {
      if (url.startsWith('/crm/leads/')) return Promise.resolve({ data: lead })
      if (url === '/ventes/roof-config/') {
        return Promise.resolve({ data: { available: true, maptilerKey: 'k-lead' } })
      }
      return Promise.reject(new Error(`URL inattendue ${url}`))
    })

    render(
      <MemoryRouter initialEntries={['/devis-design/88']}>
        <Routes>
          <Route path="/devis-design/:id" element={<ToitureDesign />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(api.get).toHaveBeenCalledWith('/crm/leads/88/')
    expect(api.get).toHaveBeenCalledWith('/ventes/roof-config/')
    // Le mode lead n'appelle JAMAIS design-context.
    expect(ventesApi.getDevisDesignContext).not.toHaveBeenCalled()

    const options = initRoofToolPro8.mock.calls[0][0]
    expect(options.maptilerKey).toBe('k-lead')
    expect(options.hydrate.devis).toBeUndefined()
    expect(options.hydrate.lead).toEqual({
      roof_point: lead.roof_point,
      roof_outline: lead.roof_outline,
      bill_kwh: 7200,
      fullName: 'Alaoui Youssef',
      phone: '0600000000',
      city: 'Casablanca',
    })

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Lead 88')
    expect(screen.getByRole('button',
      { name: /Générer le devis & envoyer au client/ })).toBeInTheDocument()
    expect(screen.queryByTestId('pv20-lecture-seule')).toBeNull()
  })
})
