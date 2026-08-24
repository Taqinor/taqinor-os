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
    // PV75 — devis complet (etude_params.simulation.pr), lu EN PARALLÈLE du
    // design-context pour l'étude bancable ; par défaut aucune étude rangée
    // (payload sans `etude_params`) pour que les tests existants (écrits avant
    // PV75) restent inchangés.
    getDevisById: vi.fn(() => Promise.resolve({ data: {} })),
    syncDevisLayout: vi.fn(),
    shareLinkDevis: vi.fn(),
    whatsappPreviewDevis: vi.fn(),
    reviserDevis: vi.fn(),
  },
}))
// MODE AO — le MÊME écran ouvert sur une AFFAIRE d'appel d'offres. Deux appels
// seulement : le contexte agrégé (contrat `apps/ao/contract_samples/
// ao_design_context.json`) et la persistance du layout.
vi.mock('../../api/aoApi', () => ({
  default: {
    affaires: {
      designContext: vi.fn(),
      enregistrerLayout: vi.fn(),
    },
  },
}))
vi.mock('../../lib/toast', () => ({ toastInfo: vi.fn() }))
// L2 — la confirmation « le calepinage diverge du devis » passe par le
// provider racine, absent de ce harnais : on répond OUI d'office, le flux
// PV21 (resynchroniser puis livrer) reste le comportement testé ici.
vi.mock('../../providers/confirm-context', () => ({
  useConfirm: () => () => Promise.resolve(true),
}))
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
import aoApi from '../../api/aoApi'
import { toastInfo } from '../../lib/toast'
import ToitureDesign from './ToitureDesign'

const CTX = exempleContrat('ventes', 'devis_design_context')
const CTX_RO = exempleContrat('ventes', 'devis_design_context',
  'exemple_lecture_seule')
const CTX_AO = exempleContrat('ao', 'ao_design_context')
const CTX_AO_RO = exempleContrat('ao', 'ao_design_context',
  'exemple_lecture_seule')

function rendreAo(id) {
  return render(
    <MemoryRouter initialEntries={[`/ao/affaires/${id}/design`]}>
      <Routes>
        <Route path="/ao/affaires/:id/design"
          element={<ToitureDesign mode="ao" />} />
      </Routes>
    </MemoryRouter>,
  )
}

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
      // PV23bis — le builder connaît déjà ces deux champs (hydrateFromDevis) :
      // le contexte serveur les porte, cette projection ne doit plus les taire.
      phone: CTX.devis.client_telephone,
      city: CTX.devis.client_ville,
    })
    // PV75 — aucune étude bancable rangée sur le devis (mock par défaut) : la
    // fenêtre de production ne reçoit rien à afficher en plus.
    expect(options.bankable).toBeNull()

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
    // PV23bis — la barre d'adresse est pré-remplie depuis adresse+ville du
    // devis (même geste que le mode lead, GOLDEN plus bas) : elle donne à la
    // carte un point de départ tant qu'aucun repère n'est encore posé.
    expect(document.getElementById('rp9-address').value)
      .toBe(`${CTX.devis.client_adresse}, ${CTX.devis.client_ville}`)
  })

  // Correction fondateur 24/08 — le backend (PV17 + repli GPS) porte déjà le
  // pin ou son absence dans `geometrie.pin` : sans lui, l'écran le DIT.
  it('correction 24/08 — sans aucune position (geometrie.pin=null) : message discret affiché', async () => {
    const ctxSansPin = {
      data: {
        ...exempleContrat('ventes', 'devis_design_context'),
        geometrie: { source: 'none', roof_layout: null, pin: null, outline: [] },
      },
    }
    ventesApi.getDevisDesignContext.mockResolvedValue(ctxSansPin)

    rendreDevis(CTX.devis.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(await screen.findByTestId('pv-sans-gps')).toHaveTextContent(
      'Pas de position GPS sur la fiche')
  })

  it('fondateur 18/08 — bouton Fermer (X) en haut à droite referme la fenêtre (retour SPA)', async () => {
    ventesApi.getDevisDesignContext.mockResolvedValue(
      reponseContrat('ventes', 'devis_design_context'))

    rendreDevis(CTX.devis.id)

    const fermer = await screen.findByRole('button', { name: 'Fermer la conception 3D' })
    expect(fermer).toBeInstanceOf(HTMLButtonElement)
    await userEvent.click(fermer)
    // `navigate(-1)` : on referme exactement comme le geste qui a ouvert cet
    // écran (lead, liste des devis, générateur…) l'a amené — jamais une
    // cible en dur.
    expect(navigateMock).toHaveBeenCalledWith(-1)
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

  it('PV75 — étude bancable rangée : projette pr → `options.bankable`', async () => {
    ventesApi.getDevisDesignContext.mockResolvedValue(
      reponseContrat('ventes', 'devis_design_context'))
    ventesApi.getDevisById.mockResolvedValueOnce({
      data: {
        etude_params: {
          simulation: {
            pr: {
              p50_kwh: 71800, p90_kwh: 58300, performance_ratio: 0.812,
              loss_breakdown: { temperature: 8.0, soiling: 3.0, shading: 4.2 },
            },
          },
        },
      },
    })

    rendreDevis(CTX.devis.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(ventesApi.getDevisById).toHaveBeenCalledWith(String(CTX.devis.id))
    const options = initRoofToolPro8.mock.calls[0][0]
    expect(options.bankable).toEqual({
      p50_kwh: 71800, p90_kwh: 58300, performance_ratio: 0.812,
      loss_breakdown: { temperature: 8.0, soiling: 3.0, shading: 4.2 },
    })
  })

  it('PV75 — devis complet indisponible (erreur réseau) : boot inchangé, `bankable` null', async () => {
    ventesApi.getDevisDesignContext.mockResolvedValue(
      reponseContrat('ventes', 'devis_design_context'))
    ventesApi.getDevisById.mockRejectedValueOnce(new Error('réseau'))

    rendreDevis(CTX.devis.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    const options = initRoofToolPro8.mock.calls[0][0]
    expect(options.bankable).toBeNull()
    // Le boot n'est jamais bloqué par l'échec de cet appel best-effort.
    expect(screen.queryByTestId('pv20-lecture-seule')).toBeNull()
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
    // PV86 — le bouton WhatsApp ouvre un choix (proposition / PDF seul) au
    // lieu de naviguer directement.
    await userEvent.click(screen.getByRole('button', { name: 'WhatsApp' }))
    expect(screen.getByRole('link', { name: 'Envoyer le lien de la proposition' }))
      .toHaveAttribute('href', 'https://wa.me/212600000000?text=x')
    expect(screen.getByDisplayValue('https://taqinor.ma/proposition/tok'))
      .toBeInTheDocument()
    // Aucun devis n'a été recréé.
    expect(ventesApi.reviserDevis).not.toHaveBeenCalled()
  })

  it('même calepinage : « Aucun changement », rien n\'est envoyé ni livré', async () => {
    // PV86 — le lien client est désormais frappé DÈS LE CHARGEMENT (best-
    // effort, indépendant du bouton) : on neutralise CET appel-là pour que
    // ce test reste concentré sur le flux d'enregistrement — aucun panneau
    // de livraison n'apparaît tant que le calepinage n'a pas changé.
    ventesApi.shareLinkDevis.mockRejectedValueOnce(new Error('reseau'))
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
    // Un seul appel : celui du CHARGEMENT (lien permanent, PV86) — le flux
    // « Aucun changement » n'en déclenche pas de second.
    expect(ventesApi.shareLinkDevis).toHaveBeenCalledTimes(1)
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

/* PV86 — trois demandes fondateur sur l'écran de conception : (1) le bloc
   facture disparaît en mode devis (dimensionnement imposé par le devis, la
   facture y est redondante) ; (2) le lien client vit EN PERMANENCE en bas de
   page, frappé dès le chargement — pas seulement après un enregistrement ;
   (3) le bouton WhatsApp du panneau ouvre un choix entre le lien de la
   proposition et le PDF seul (même numéro, texte différent). */
describe('ToitureDesign — PV86 : lien client permanent + choix WhatsApp', () => {
  it('bloc facture retiré en mode devis (le dimensionnement vient du devis, pas de la facture)', async () => {
    ventesApi.getDevisDesignContext.mockResolvedValue(
      reponseContrat('ventes', 'devis_design_context'))
    // Neutralise le lien permanent (hors sujet de ce test).
    ventesApi.shareLinkDevis.mockRejectedValueOnce(new Error('reseau'))

    rendreDevis(CTX.devis.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(screen.queryByLabelText(/Facture d'électricité/)).toBeNull()
    // Les deux ids que le builder interroge via `$()` (roofPro11/dom.ts) sont
    // gardés partout (`?.`) : absents du DOM, ils ne cassent pas l'init.
    expect(document.getElementById('rp9-bill')).toBeNull()
    expect(document.getElementById('rp9-bill-kwh')).toBeNull()
  })

  it('au chargement, frappe shareLinkDevis et affiche le panneau de livraison SANS enregistrement', async () => {
    ventesApi.getDevisDesignContext.mockResolvedValue(
      reponseContrat('ventes', 'devis_design_context'))
    ventesApi.shareLinkDevis.mockResolvedValueOnce({
      data: { token: 'tok-boot', path: '/proposition/tok-boot' },
    })
    ventesApi.whatsappPreviewDevis.mockResolvedValueOnce({
      data: { wa_url: 'https://wa.me/212600000000?text=boot', phone: '0600000000' },
    })

    rendreDevis(CTX.devis.id)

    await waitFor(() => expect(ventesApi.shareLinkDevis)
      .toHaveBeenCalledWith(String(CTX.devis.id)))
    expect(await screen.findByText('Prêt à envoyer')).toBeInTheDocument()
    expect(screen.getByDisplayValue('https://taqinor.ma/proposition/tok-boot'))
      .toBeInTheDocument()
    // Rien n'a été enregistré : le bouton d'action reste, LUI AUSSI, affiché
    // (le panneau de livraison est un bloc séparé, jamais un remplacement).
    expect(screen.getByRole('button', { name: /Enregistrer la conception/ }))
      .toBeInTheDocument()
    expect(ventesApi.syncDevisLayout).not.toHaveBeenCalled()
  })

  it('échec réseau au chargement du lien : aucun panneau, pas d\'erreur bloquante', async () => {
    ventesApi.getDevisDesignContext.mockResolvedValue(
      reponseContrat('ventes', 'devis_design_context'))
    ventesApi.shareLinkDevis.mockRejectedValueOnce(new Error('reseau'))

    rendreDevis(CTX.devis.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(screen.queryByText('Prêt à envoyer')).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('clic WhatsApp : deux choix — lien de la proposition vs PDF seul, même numéro', async () => {
    ventesApi.getDevisDesignContext.mockResolvedValue(
      reponseContrat('ventes', 'devis_design_context'))
    ventesApi.shareLinkDevis.mockResolvedValueOnce({
      data: { token: 'tok42', path: '/proposition/tok42' },
    })
    ventesApi.whatsappPreviewDevis.mockResolvedValueOnce({
      data: { wa_url: 'https://wa.me/212600000000?text=proposition', phone: '0600000000' },
    })

    rendreDevis(CTX.devis.id)

    const boutonWa = await screen.findByRole('button', { name: 'WhatsApp' })
    await userEvent.click(boutonWa)

    const choixProposition = screen.getByRole('link', { name: 'Envoyer le lien de la proposition' })
    expect(choixProposition).toHaveAttribute(
      'href', 'https://wa.me/212600000000?text=proposition')

    const choixPdf = screen.getByRole('link', { name: 'Envoyer le PDF seul' })
    const hrefPdf = choixPdf.getAttribute('href')
    // Même numéro que le premier choix (relu depuis le lien déjà validé) —
    // seul le TEXTE change.
    expect(hrefPdf.startsWith('https://wa.me/212600000000?text=')).toBe(true)
    const texte = decodeURIComponent(hrefPdf.split('text=')[1])
    expect(texte).toContain(`${window.location.origin}/api/django/public/proposal/tok42/pdf/`)
    expect(texte).toContain(CTX.devis.reference)
  })
})

/* MODE AO — les MÊMES outils pour les ventes et pour les appels d'offres.
   L'écran s'ouvre sur une AFFAIRE, hydraté par la géométrie AO déjà relevée.
   PACT13 : la charge utile vient de l'exemple COMMITTÉ
   `apps/ao/contract_samples/ao_design_context.json` — le même fichier que le
   test backend `apps/ao/tests/test_ao_design_context.py` compare à la réponse
   RÉELLE du serveur. Une divergence de forme casse les deux tests, pas la
   production. */
describe('ToitureDesign — mode ao (atelier 3D d’une affaire)', () => {
  it('boote sur UN SEUL appel design-context et hydrate le builder depuis l’affaire', async () => {
    aoApi.affaires.designContext.mockResolvedValue({ data: CTX_AO })

    rendreAo(CTX_AO.affaire.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    // UN SEUL appel : rien n'est complété par une requête annexe (ni la config
    // carte — la clé MapTiler vient du contexte), et aucun appel VENTES.
    expect(aoApi.affaires.designContext).toHaveBeenCalledTimes(1)
    expect(aoApi.affaires.designContext)
      .toHaveBeenCalledWith(String(CTX_AO.affaire.id))
    expect(api.get).not.toHaveBeenCalled()
    expect(ventesApi.getDevisDesignContext).not.toHaveBeenCalled()
    expect(ventesApi.shareLinkDevis).not.toHaveBeenCalled()

    const options = initRoofToolPro8.mock.calls[0][0]
    expect(options.maptilerKey).toBe(CTX_AO.carte.maptilerKey)
    // La géométrie AO passe par le créneau `hydrate.devis` du builder (celui
    // de la « géométrie déjà dessinée + cible imposée ») — jamais `hydrate.lead`.
    expect(options.hydrate.lead).toBeUndefined()
    expect(options.hydrate.devis).toEqual({
      id: null,
      geometrie: {
        roof_layout: CTX_AO.geometrie.roof_layout,
        roof_point: CTX_AO.geometrie.pin,
        roof_outline: CTX_AO.geometrie.outline,
      },
      cible: {
        panneaux: CTX_AO.cible.panneaux,
        panel_watt: CTX_AO.cible.panel_watt,
        scenario: null,
      },
      fullName: CTX_AO.affaire.objet,
    })

    // L'en-tête porte NOTRE référence d'affaire + son objet, servis par le contexte.
    expect(await screen.findByRole('heading', { level: 1 }))
      .toHaveTextContent(CTX_AO.affaire.reference)
    expect(screen.getByRole('heading', { level: 1 }))
      .toHaveTextContent(CTX_AO.affaire.objet)
    // Aucun geste du monde DEVIS ne s'affiche ici.
    expect(screen.queryByRole('button',
      { name: /Générer le devis & envoyer au client/ })).toBeNull()
    expect(screen.queryByRole('button',
      { name: /Enregistrer la conception/ })).toBeNull()
    // Le bloc facture (mode lead) est absent : la cible vient de l'engagement.
    expect(screen.queryByLabelText(/Facture d'électricité/)).toBeNull()
  })

  it('lecture seule : motif du SERVEUR, aucun bouton d’enregistrement, aucun lien mort', async () => {
    aoApi.affaires.designContext.mockResolvedValue({ data: CTX_AO_RO })

    rendreAo(CTX_AO_RO.affaire.id)

    const bandeau = await screen.findByTestId('pv20-lecture-seule')
    expect(bandeau).toHaveTextContent(CTX_AO_RO.raison_lecture_seule)
    // La visionneuse plein écran est une route DEVIS : pas de lien mort ici.
    expect(screen.queryByRole('link', { name: 'Voir en 3D' })).toBeNull()
    expect(screen.queryByTestId('ao-enregistrer-calepinage')).toBeNull()
    // Le designer boote quand même (consultation du calepinage remis).
    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    // Les avertissements du serveur sont rendus, pas inventés.
    for (const a of CTX_AO_RO.avertissements) {
      expect(screen.getByTestId('pv20-avertissements')).toHaveTextContent(a)
    }
  })

  it('affaire introuvable : message FR, aucun boot du builder', async () => {
    aoApi.affaires.designContext.mockRejectedValue({ response: { status: 404 } })

    rendreAo(999)

    expect(await screen.findByRole('alert')).toHaveTextContent('Affaire introuvable.')
    expect(initRoofToolPro8).not.toHaveBeenCalled()
  })

  it('enregistre le calepinage sérialisé sur l’affaire, sans toucher au devis', async () => {
    aoApi.affaires.designContext.mockResolvedValue({ data: CTX_AO })
    aoApi.affaires.enregistrerLayout.mockResolvedValue({ data: { roof_layout: LAYOUT } })

    rendreAo(CTX_AO.affaire.id)
    const bouton = await screen.findByRole('button',
      { name: /Enregistrer le calepinage/ })
    await userEvent.click(bouton)

    await waitFor(() => expect(aoApi.affaires.enregistrerLayout)
      .toHaveBeenCalledWith(String(CTX_AO.affaire.id), LAYOUT))
    // Aucun devis n'est créé, resynchronisé ni livré depuis cet écran.
    expect(api.post).not.toHaveBeenCalled()
    expect(ventesApi.syncDevisLayout).not.toHaveBeenCalled()
    expect(await screen.findByText(/Calepinage enregistré sur l’affaire/))
      .toBeInTheDocument()
  })

  it('409 dossier déposé : bandeau de lecture seule avec le motif du serveur', async () => {
    aoApi.affaires.designContext.mockResolvedValue({ data: CTX_AO })
    aoApi.affaires.enregistrerLayout.mockRejectedValue({
      response: {
        status: 409,
        data: { detail: 'Affaire « Déposé » : le calepinage ne se modifie plus.' },
      },
    })

    rendreAo(CTX_AO.affaire.id)
    await userEvent.click(await screen.findByRole('button',
      { name: /Enregistrer le calepinage/ }))

    const bandeau = await screen.findByTestId('ao-conflit-lecture-seule')
    expect(bandeau).toHaveTextContent('le calepinage ne se modifie plus')
    // Le geste « Réviser (v2) » appartient au monde DEVIS : jamais proposé ici.
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
    // Une épingle publique existe déjà : pas de message GPS.
    expect(screen.queryByTestId('pv-sans-gps')).toBeNull()
  })
})

// ── Correction fondateur 24/08 — repli GPS de la fiche lead ────────────────
describe('ToitureDesign — mode lead : repli GPS de la fiche (correction 24/08)', () => {
  it('sans roof_point mais avec gps_lat/gps_lng : hydrate.lead.roof_point vient du GPS de la fiche', async () => {
    const lead = {
      id: 89, nom: 'Bennani', prenom: 'Amine', ville: 'Marrakech',
      telephone: '0611111111', roof_point: null, roof_outline: null,
      gps_lat: '31.629472', gps_lng: '-8.008889',
    }
    api.get.mockImplementation((url) => {
      if (url.startsWith('/crm/leads/')) return Promise.resolve({ data: lead })
      if (url === '/ventes/roof-config/') {
        return Promise.resolve({ data: { available: true, maptilerKey: 'k-lead' } })
      }
      return Promise.reject(new Error(`URL inattendue ${url}`))
    })

    render(
      <MemoryRouter initialEntries={['/devis-design/89']}>
        <Routes>
          <Route path="/devis-design/:id" element={<ToitureDesign />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    const options = initRoofToolPro8.mock.calls[0][0]
    expect(options.hydrate.lead.roof_point).toEqual({ lat: 31.629472, lng: -8.008889 })
    // Une position réelle existe (via le GPS) : pas de message « sans GPS ».
    expect(screen.queryByTestId('pv-sans-gps')).toBeNull()
  })

  it('sans roof_point ni GPS : la carte reste au niveau Maroc, message discret affiché', async () => {
    const lead = {
      id: 90, nom: 'Idrissi', prenom: 'Sara', ville: '',
      telephone: '', roof_point: null, roof_outline: null,
      gps_lat: null, gps_lng: null,
    }
    api.get.mockImplementation((url) => {
      if (url.startsWith('/crm/leads/')) return Promise.resolve({ data: lead })
      if (url === '/ventes/roof-config/') {
        return Promise.resolve({ data: { available: true, maptilerKey: 'k-lead' } })
      }
      return Promise.reject(new Error(`URL inattendue ${url}`))
    })

    render(
      <MemoryRouter initialEntries={['/devis-design/90']}>
        <Routes>
          <Route path="/devis-design/:id" element={<ToitureDesign />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    const options = initRoofToolPro8.mock.calls[0][0]
    expect(options.hydrate.lead.roof_point).toBeNull()
    expect(await screen.findByTestId('pv-sans-gps')).toHaveTextContent(
      'Pas de position GPS sur la fiche')
  })
})
