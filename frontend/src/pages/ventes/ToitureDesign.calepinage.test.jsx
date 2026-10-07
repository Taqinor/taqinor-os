import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   CAL37 — MODE `calepinage` de l'atelier 3D : le MÊME builder, un troisième
   mode. Ce que ce fichier prouve :

   1. `/calepinage/:id` boote le builder sur UN SEUL appel (`design-context`),
      hydrate depuis le calepinage et enregistre par `POST …/layout/` ;
   2. la cible peut être ABSENTE (`cible: null`, `exemple_vide` du contrat) —
      l'écran l'écrit « non renseignée » et n'invente AUCUNE puissance ;
   3. le mode DEVIS ne bouge pas : monté dans ce même harnais, il ne frappe
      AUCUNE route calepinage (garde de non-régression demandée par CAL37).

   PACT13 — les charges utiles viennent des exemples COMMITTÉS
   (`apps/calepinage/contract_samples/calepinage_design_context.json` et son
   jumeau ventes), jamais d'un objet tapé à la main : si le serveur change de
   forme, ce test casse tout seul.
   ========================================================================== */

// CALX27 — le bandeau « lecture seule » de l'atelier lit `useHasPermission`
// (store Redux) : ce test rend la page sans Provider, on fige le droit à faux.
vi.mock('../../hooks/useHasPermission', () => ({ useHasPermission: () => false }))

import '../../test/toitureDesignHarnessCalepinage'
import {
  initRoofToolPro8, rendreCalepinage, rendreDevis, reinitialiserBoot, reinitialiserBootMinimal,
  LAYOUT, snapshot, apiBuilder,
} from '../../test/toitureDesignHarness'
import ventesApi from '../../api/ventesApi'
import calepinageApi from '../../api/calepinageApi'
import { toastInfo } from '../../lib/toast'

const CTX = exempleContrat('calepinage', 'calepinage_design_context')
const CTX_VIDE = exempleContrat('calepinage', 'calepinage_design_context',
  'exemple_vide')

beforeEach(() => {
  vi.clearAllMocks()
  reinitialiserBoot()
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ToitureDesign — mode calepinage (CAL37)', () => {
  it('boote sur UN SEUL appel design-context et hydrate depuis le calepinage', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))

    rendreCalepinage(CTX.calepinage.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(calepinageApi.calepinages.designContext).toHaveBeenCalledTimes(1)
    expect(calepinageApi.calepinages.designContext)
      .toHaveBeenCalledWith(String(CTX.calepinage.id))
    // Aucun contexte de DEVIS n'est exigé : le mode calepinage ne frappe
    // jamais la porte ventes (décision fondateur D3).
    expect(ventesApi.getDevisDesignContext).not.toHaveBeenCalled()

    const options = initRoofToolPro8.mock.calls[0][0]
    expect(options.maptilerKey).toBe(CTX.carte.maptilerKey)
    expect(options.hydrate.lead).toBeUndefined()
    expect(options.hydrate.devis).toEqual({
      // Un calepinage N'EST PAS un devis : `id` reste nul.
      id: null,
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
      // Ce calepinage-là porte un devis lié : sa cible EST une cible vendue,
      // et l'atelier se comporte alors exactement comme en mode devis.
      cibleVendue: true,
      fullName: CTX.calepinage.titre,
    })

    expect(await screen.findByRole('heading', { level: 1 }))
      .toHaveTextContent(CTX.calepinage.titre)
    expect(screen.queryByTestId('pv20-lecture-seule')).toBeNull()
    // Le bouton du flux LEAD n'existe jamais ici.
    expect(screen.queryByRole('button',
      { name: /^Générer le devis$/ })).toBeNull()
  })

  it('enregistre la conception par POST layout, puis envoie l’aperçu', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel.mockResolvedValue(
      { data: { inchange: false, version: 3 } })
    calepinageApi.calepinages.envoyerImage.mockResolvedValue({ data: {} })
    snapshot.mockReturnValue('data:image/png;base64,aGk=')

    rendreCalepinage(CTX.calepinage.id)
    const bouton = await screen.findByRole('button',
      { name: /Enregistrer le calepinage/ })
    await userEvent.click(bouton)

    await waitFor(() => expect(calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel)
      .toHaveBeenCalledWith(String(CTX.calepinage.id), LAYOUT,
        CTX.geometrie.empreinte_document))
    await waitFor(() => expect(calepinageApi.calepinages.envoyerImage)
      .toHaveBeenCalledTimes(1))
    expect(calepinageApi.calepinages.envoyerImage.mock.calls[0][0])
      .toBe(String(CTX.calepinage.id))
    expect(calepinageApi.calepinages.envoyerImage.mock.calls[0][1])
      .toBeInstanceOf(FormData)
    // Aucune écriture ventes : le devis n'est pas touché par un enregistrement.
    expect(ventesApi.syncDevisLayout).not.toHaveBeenCalled()
  })

  /* ACAL87 — un aperçu vide (snapshot null) n'est JAMAIS téléversé, et l'écran
     le dit ; un téléversement en échec n'est plus avalé. */
  it('snapshot null → aucun POST roof-image, message affiché', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel.mockResolvedValue(
      { data: { inchange: false, version: 5 } })
    snapshot.mockResolvedValue(null)

    rendreCalepinage(CTX.calepinage.id)
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer le calepinage/ }))

    expect(await screen.findByTestId('apercu-3d-avertissement'))
      .toHaveTextContent('Aperçu 3D non capturé')
    expect(calepinageApi.calepinages.envoyerImage).not.toHaveBeenCalled()
  })

  it('téléversement de l’aperçu en échec → dit, jamais avalé', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel.mockResolvedValue(
      { data: { inchange: false, version: 5 } })
    snapshot.mockResolvedValue('data:image/png;base64,aGk=')
    calepinageApi.calepinages.envoyerImage.mockRejectedValue(new Error('réseau'))

    rendreCalepinage(CTX.calepinage.id)
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer le calepinage/ }))

    expect(await screen.findByTestId('apercu-3d-avertissement'))
      .toHaveTextContent('Aperçu 3D non envoyé')
    expect(calepinageApi.calepinages.envoyerImage).toHaveBeenCalledTimes(1)
  })

  it('conception inchangée : on le DIT, et aucune image n’est envoyée', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel.mockResolvedValue(
      { data: { inchange: true, version: null } })
    snapshot.mockReturnValue('data:image/png;base64,aGk=')

    rendreCalepinage(CTX.calepinage.id)
    await userEvent.click(await screen.findByRole('button',
      { name: /Enregistrer le calepinage/ }))

    await waitFor(() => expect(toastInfo).toHaveBeenCalledWith('Aucun changement'))
    expect(calepinageApi.calepinages.envoyerImage).not.toHaveBeenCalled()
  })

  it('refus 400 : le message du SERVEUR s’affiche, jamais un texte fabriqué', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel.mockRejectedValue({
      response: {
        status: 400,
        data: { roof_layout: 'Conception manquante ou invalide : le corps attendu est le document de conception.' },
      },
    })

    rendreCalepinage(CTX.calepinage.id)
    await userEvent.click(await screen.findByRole('button',
      { name: /Enregistrer le calepinage/ }))

    expect(await screen.findByTestId('cal-erreur-enregistrement'))
      .toHaveTextContent('Conception manquante ou invalide')
  })

  it('409 roof_layout : le motif serveur est affiché', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    // ACAL44 — la forme RÉELLE du 409 de verrou (VerrouilleRefuse) :
    // `{roof_layout: [motif]}`, jamais `{detail}` (sinon faux vert).
    calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel.mockRejectedValue({
      response: { status: 409, data: { roof_layout: ['Devis accepté : révisez-le'] } },
    })

    rendreCalepinage(CTX.calepinage.id)
    await userEvent.click(await screen.findByRole('button',
      { name: /Enregistrer le calepinage/ }))

    expect(await screen.findByTestId('cal-conflit-lecture-seule'))
      .toHaveTextContent('Devis accepté : révisez-le')
  })

  /* ACAL23 — le jeton If-Match de l'écriture complète, et le 409
     « modifiée ailleurs » distinct du verrou. */
  it('le POST porte If-Match lu au boot', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    const jetonApres = 'b'.repeat(64)
    calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel
      .mockResolvedValueOnce({ data: { inchange: true, version: null, empreinte_document: jetonApres } })
      .mockResolvedValueOnce({ data: { inchange: true, version: null, empreinte_document: jetonApres } })
    // ACAL83 — après l'écriture, design-context est relu : il sert le MÊME
    // jeton que la réponse 2xx (empreinte du document désormais stocké).
    calepinageApi.calepinages.designContext
      .mockResolvedValueOnce(reponseContrat('calepinage', 'calepinage_design_context'))
      .mockResolvedValue({
        data: { ...CTX, geometrie: { ...CTX.geometrie, empreinte_document: jetonApres } },
      })
    expect(CTX.geometrie.empreinte_document).toBeTruthy()

    rendreCalepinage(CTX.calepinage.id)
    const bouton = await screen.findByRole('button', { name: /Enregistrer le calepinage/ })
    await userEvent.click(bouton)
    await waitFor(() => expect(calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel)
      .toHaveBeenCalledTimes(1))
    expect(calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel.mock.calls[0][2])
      .toBe(CTX.geometrie.empreinte_document)
    // Le jeton suivant est celui RENDU par la réponse 2xx, jamais celui du boot.
    await waitFor(() => expect(bouton).not.toBeDisabled())
    await userEvent.click(bouton)
    await waitFor(() => expect(calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel)
      .toHaveBeenCalledTimes(2))
    expect(calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel.mock.calls[1][2])
      .toBe(jetonApres)
  })

  it('409 document_modifie → bannière Recharger, pas le conflit verrou', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    const conflit = exempleContrat('calepinage', 'calepinage_layout_section',
      'exemple_conflit_409')
    calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel.mockRejectedValue({
      response: { status: 409, data: conflit },
    })

    rendreCalepinage(CTX.calepinage.id)
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer le calepinage/ }))

    const banniere = await screen.findByTestId('cal-document-modifie')
    expect(banniere).toHaveTextContent(/modifiée ailleurs/)
    expect(banniere).toHaveTextContent(conflit.detail)
    expect(screen.getByTestId('cal-document-modifie-recharger')).toHaveTextContent('Recharger')
    expect(screen.queryByTestId('cal-conflit-lecture-seule')).toBeNull()
    expect(calepinageApi.calepinages.envoyerImage).not.toHaveBeenCalled()
  })

  it('409 verrou → le conflit lecture seule porte le message du serveur, pas la bannière', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel.mockRejectedValue({
      response: { status: 409, data: { roof_layout: ['Ce calepinage est verrouillé : son devis lié a été envoyé.'] } },
    })

    rendreCalepinage(CTX.calepinage.id)
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer le calepinage/ }))

    expect(await screen.findByTestId('cal-conflit-lecture-seule'))
      .toHaveTextContent('Ce calepinage est verrouillé')
    expect(screen.queryByTestId('cal-document-modifie')).toBeNull()
  })

  /* ACAL83 — design-context est RELU après chaque enregistrement réussi :
     la note « calepinage automatique — à vérifier » s'éteint sans F5. */
  it('après enregistrement, la bannière calepinage automatique disparaît', async () => {
    const auto = {
      ...CTX,
      geometrie: {
        ...CTX.geometrie,
        roof_layout: { ...CTX.geometrie.roof_layout, _origine_calepinage: 'contour_client' },
      },
    }
    expect(CTX.geometrie.roof_layout?._origine_calepinage).toBeUndefined()
    // Ce que le serveur sert APRÈS l'enregistrement : la conception du
    // commercial (des pans), sans l'estampille du semis automatique.
    const apres = {
      ...CTX,
      geometrie: {
        ...CTX.geometrie,
        roof_layout: {
          ...CTX.geometrie.roof_layout,
          zones: [{ id: 'z1', vertices: [[0, 0], [10, 0], [10, 6], [0, 6]] }],
        },
      },
    }
    calepinageApi.calepinages.designContext
      .mockResolvedValueOnce({ data: auto })
      .mockResolvedValue({ data: apres })
    calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel.mockResolvedValue(
      { data: { inchange: false, version: 4 } })

    rendreCalepinage(CTX.calepinage.id)
    expect(await screen.findByTestId('rp9-calepinage-auto-note')).toBeTruthy()

    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer le calepinage/ }))

    await waitFor(() => expect(calepinageApi.calepinages.designContext).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(screen.queryByTestId('rp9-calepinage-auto-note')).toBeNull())
  })

  /* ACAL84 — brouillon local : rien en lecture seule ; jamais bloquant. */
  it('lecture seule → aucun brouillon (le gestionnaire ne démarre pas)', async () => {
    const espion = vi.spyOn(window, 'setInterval')
    try {
      calepinageApi.calepinages.designContext.mockResolvedValue({
        data: { ...CTX, modifiable: false, raison_lecture_seule: 'Devis accepté.' },
      })
      rendreCalepinage(CTX.calepinage.id)
      await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
      await screen.findByTestId('pv20-lecture-seule')
      const sondages = espion.mock.calls.filter(([, ms]) => ms === 4000)
      expect(sondages).toHaveLength(0)
      expect(Object.keys(window.localStorage)
        .filter((k) => k.startsWith('calepinage_brouillon'))).toEqual([])
    } finally {
      espion.mockRestore()
    }
  })

  it('modifiable → le gestionnaire de brouillon démarre (témoin du test précédent)', async () => {
    const espion = vi.spyOn(window, 'setInterval')
    try {
      calepinageApi.calepinages.designContext.mockResolvedValue(
        reponseContrat('calepinage', 'calepinage_design_context'))
      // ACAL85 — comme le constructeur réel : l'hydratation se termine APRÈS
      // `onApiReady`, et le brouillon ne démarre qu'une fois la scène hydratée.
      initRoofToolPro8.mockImplementation((options) => {
        options?.onApiReady?.(apiBuilder())
        options?.onHydrationTerminee?.()
      })
      rendreCalepinage(CTX.calepinage.id)
      await waitFor(() => expect(espion.mock.calls.some(([, ms]) => ms === 4000)).toBe(true))
    } finally {
      espion.mockRestore()
    }
  })

  it('brouillon trouvé → l’atelier boote SANS attendre le choix, clé = empreinte serveur', async () => {
    const cle = `calepinage_brouillon:${CTX.calepinage.id}:anonyme:${CTX.geometrie.empreinte_document}`
    const orpheline = `calepinage_brouillon:${CTX.calepinage.id}:anonyme:${'0'.repeat(64)}`
    window.localStorage.setItem(cle, JSON.stringify({
      layout: { version: 2, zones: [{ id: 'brouillon' }] }, horodatage: '2026-10-05T09:00:00.000Z',
    }))
    window.localStorage.setItem(orpheline, JSON.stringify({
      layout: { version: 2, zones: [] }, horodatage: '2026-10-01T09:00:00.000Z',
    }))
    try {
      calepinageApi.calepinages.designContext.mockResolvedValue(
        reponseContrat('calepinage', 'calepinage_design_context'))
      rendreCalepinage(CTX.calepinage.id)
      expect(await screen.findByTestId('cal-brouillon-bandeau')).toBeTruthy()
      // Non bloquant : le constructeur a booté sur la conception SERVEUR.
      await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalledTimes(1))
      expect(initRoofToolPro8.mock.calls[0][0].hydrate.devis.geometrie.roof_layout)
        .toEqual(CTX.geometrie.roof_layout)
      // La clé périmée est purgée à l'ouverture, la courante reste.
      expect(window.localStorage.getItem(orpheline)).toBeNull()
      expect(window.localStorage.getItem(cle)).not.toBeNull()
      await userEvent.click(screen.getByTestId('cal-brouillon-ignorer'))
      expect(screen.queryByTestId('cal-brouillon-bandeau')).toBeNull()
      expect(initRoofToolPro8).toHaveBeenCalledTimes(1)
    } finally {
      window.localStorage.removeItem(cle)
      window.localStorage.removeItem(orpheline)
    }
  })

  it('cible absente : « non renseignée », jamais une puissance inventée', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context', 'exemple_vide'))

    rendreCalepinage(CTX_VIDE.calepinage.id)

    // Le contrat sert `carte.available: false` sur l'exemple vide : le builder
    // ne boote pas, et l'écran DIT pourquoi au lieu d'afficher une carte morte.
    expect(await screen.findByRole('alert'))
      .toHaveTextContent(/clé MapTiler/)
    expect(initRoofToolPro8).not.toHaveBeenCalled()
    // Les avertissements SERVEUR sont affichés tels quels.
    expect(screen.getByTestId('pv20-avertissements'))
      .toHaveTextContent(CTX_VIDE.avertissements[0])
  })

  it('cible nulle avec une carte disponible : le panneau écrit « non renseignée »', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue({
      data: {
        ...CTX_VIDE,
        carte: CTX.carte,
      },
    })

    rendreCalepinage(CTX_VIDE.calepinage.id)

    expect(await screen.findByTestId('cal-cible-panneaux'))
      .toHaveTextContent('non renseignée')
    const options = initRoofToolPro8.mock.calls[0][0]
    // AUCUN chiffre n'est fabriqué pour le builder.
    expect(options.hydrate.devis.cible).toEqual({
      panneaux: null, panel_watt: null, scenario: null,
    })
    // `outline: []` n'est pas un polygone : on ne l'envoie pas.
    expect(options.hydrate.devis.geometrie.roof_outline).toBeNull()
  })

  /* ──────────────────────────────────────────────────────────────────────
     RÉGRESSION (constat en production, 20/09/2026) — `/calepinage/<id>` né
     d'un LEAD restait figé : « Surface : — », recommandation « — », aucune
     requête de rendement, alors que `/ventes/devis/<id>/design` ouvrait le
     MÊME toit du MÊME lead en quelques secondes. Deux causes, l'une ici :
     l'écran envoyait au builder une cible entièrement nulle SANS dire qu'il
     n'y a aucune vente derrière ce document — et le builder lit alors
     « cible vendue de ZÉRO panneau » (L2, incident DEV-202608-0016) et
     refuse de poser quoi que ce soit. Le contrat dit pourtant l'inverse :
     « LA CIBLE N'EST JAMAIS INVENTÉE », `cible: null` = pas de cible.
     ────────────────────────────────────────────────────────────────────── */
  it('calepinage né d’un lead : le builder reçoit un centre, le tracé client et AUCUNE cible vendue', async () => {
    const CTX_LEAD = exempleContrat('calepinage', 'calepinage_design_context',
      'exemple_sans_devis')
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context',
        'exemple_sans_devis'))

    rendreCalepinage(CTX_LEAD.calepinage.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    const options = initRoofToolPro8.mock.calls[0][0]
    // Le CENTRE : sans l'épingle du lead, la carte démarre au niveau Maroc et
    // rien ne s'affiche jamais.
    expect(options.hydrate.devis.geometrie.roof_point)
      .toEqual(CTX_LEAD.geometrie.pin)
    // LE PAN VIENT DU TRACÉ CLIENT : c'est ce contour, et lui seul, que
    // `hydrateFromDevis` referme en zone active (aucun re-tracé manuel).
    expect(options.hydrate.devis.geometrie.roof_outline)
      .toEqual(CTX_LEAD.geometrie.outline)
    expect(options.referenceContour).toEqual(CTX_LEAD.geometrie.contour_client)
    // AUCUN chiffre inventé…
    expect(options.hydrate.devis.cible).toEqual({
      panneaux: null, panel_watt: null, scenario: null,
    })
    // …mais le silence est QUALIFIÉ : rien n'a été vendu, donc l'optimiseur
    // travaille librement au lieu de se figer sur une cible de zéro.
    expect(options.hydrate.devis.cibleVendue).toBe(false)
  })

  /* RÉGRESSION (même constat du 20/09/2026, seconde moitié) — la barre de
     recherche d'adresse restait VIDE en mode calepinage, alors que le mode
     devis l'ouvre pré-remplie depuis le contexte (`bootDevis`, PV23bis) : le
     commercial devait retaper une adresse que le serveur connaît déjà. */
  it('la barre d’adresse part pré-remplie depuis le contexte, comme en mode devis', async () => {
    const CTX_LEAD = exempleContrat('calepinage', 'calepinage_design_context',
      'exemple_sans_devis')
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context',
        'exemple_sans_devis'))

    rendreCalepinage(CTX_LEAD.calepinage.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    const attendue = [CTX_LEAD.calepinage.client_adresse,
      CTX_LEAD.calepinage.client_ville].filter(Boolean).join(', ')
    expect(attendue).not.toBe('')
    await waitFor(() => expect(document.getElementById('rp9-address').value)
      .toBe(attendue))
  })

  it('adresse inconnue : la barre reste vide (aucune adresse inventée)', async () => {
    // L'exemple vide sert `carte.available: false` (le builder ne booterait
    // pas) : on lui rend la carte du premier exemple pour n'observer QUE
    // l'adresse.
    calepinageApi.calepinages.designContext.mockResolvedValue({
      data: { ...CTX_VIDE, carte: CTX.carte },
    })

    rendreCalepinage(CTX_VIDE.calepinage.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(document.getElementById('rp9-address').value).toBe('')
  })

  it('lecture seule : la raison du serveur s’affiche et le bouton disparaît', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue({
      data: {
        ...CTX,
        modifiable: false,
        raison_lecture_seule: 'Le devis lié est déjà parti chez le client.',
      },
    })

    rendreCalepinage(CTX.calepinage.id)

    expect(await screen.findByTestId('pv20-lecture-seule'))
      .toHaveTextContent('Le devis lié est déjà parti chez le client.')
    expect(screen.queryByRole('button',
      { name: /Enregistrer le calepinage/ })).toBeNull()
    // Le panneau du module reste monté : consulter une conception figée est
    // exactement ce que la lecture seule doit permettre.
    expect(screen.getByTestId('cal-atelier-panneaux')).toBeTruthy()
  })
})

describe('ToitureDesign — teinte par chaîne (ACAL286)', () => {
  it('le boot calepinage pousse l’affectation servie (payload = contrat committé)', async () => {
    const setAffectationChaines = vi.fn()
    reinitialiserBootMinimal({ setAffectationChaines })
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.resultat.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_resultat'))

    rendreCalepinage(CTX.calepinage.id)

    await waitFor(() => expect(setAffectationChaines).toHaveBeenCalled())
    expect(calepinageApi.calepinages.resultat)
      .toHaveBeenCalledWith(String(CTX.calepinage.id))
    const [lignes, mode] = setAffectationChaines.mock.calls[0]
    expect(lignes)
      .toEqual(exempleContrat('calepinage', 'calepinage_resultat').electrique.affectation)
    expect(lignes[0].couleur_chaine).toBeTruthy()
    expect(mode).toBe('chaine')
  })

  it('résultat illisible : la teinte est éteinte (null), l’écran ne casse pas', async () => {
    const setAffectationChaines = vi.fn()
    reinitialiserBootMinimal({ setAffectationChaines })
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.resultat.mockRejectedValue(new Error('réseau'))

    rendreCalepinage(CTX.calepinage.id)

    await waitFor(() => expect(setAffectationChaines).toHaveBeenCalledWith(null, 'chaine'))
  })
})

describe('ToitureDesign — la route devis ouvre le calepinage lié (ACAL37, D-ACAL-1)', () => {
  it('passe par le calepinage lié, jamais par le contexte devis', async () => {
    calepinageApi.calepinages.depuisModele.mockResolvedValue(
      { data: { id: CTX.calepinage.id } })
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))

    rendreDevis(CTX.calepinage.devis_lie.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(calepinageApi.calepinages.depuisModele)
      .toHaveBeenCalledWith({ devis_id: CTX.calepinage.devis_lie.id })
    expect(ventesApi.getDevisDesignContext).not.toHaveBeenCalled()
    // Les panneaux du module ET son bouton d'enregistrement sont là.
    expect(await screen.findByTestId('cal-atelier-panneaux')).toBeInTheDocument()
    expect(screen.getByTestId('cal-enregistrer-calepinage')).toBeInTheDocument()
  })
})

/* ACAL192 (D-ACAL-13) — GPS du lead corrigé après le tracé. Les contextes viennent du
   contrat committé (`exemple_derive_a_decider`) ; « automatique » est la MÊME charge dont
   seul `derive.etat` change (l'état D-QJR5-15 d'une épingle qui suit le lead). */
describe('ToitureDesign — dérive du GPS du lead (ACAL192)', () => {
  const CTX_DERIVE = exempleContrat('calepinage', 'calepinage_design_context',
    'exemple_derive_a_decider')
  const ctxAutomatique = () => {
    const ctx = structuredClone(CTX_DERIVE)
    ctx.geometrie.derive.etat = 'automatique'
    return ctx
  }

  it('affiche la bannière de dérive et appelle recentrer', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue({ data: CTX_DERIVE })
    rendreCalepinage(CTX_DERIVE.calepinage.id)

    const banniere = await screen.findByTestId('acal-derive-repere')
    expect(banniere).toHaveTextContent('Le GPS du lead a été corrigé (≈ 780 m).')
    // « a_decider » : rien n'est recentré d'office.
    expect(calepinageApi.calepinages.recentrerSurLead).not.toHaveBeenCalled()

    await userEvent.click(screen.getByTestId('acal-derive-recentrer'))
    await waitFor(() => expect(calepinageApi.calepinages.recentrerSurLead)
      .toHaveBeenCalledWith(String(CTX_DERIVE.calepinage.id)))
    expect(calepinageApi.calepinages.garderRepere).not.toHaveBeenCalled()
  })

  it('« Garder ce repère » appelle garder-repere, jamais recentrer', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue({ data: CTX_DERIVE })
    rendreCalepinage(CTX_DERIVE.calepinage.id)

    await userEvent.click(await screen.findByTestId('acal-derive-garder'))
    await waitFor(() => expect(calepinageApi.calepinages.garderRepere)
      .toHaveBeenCalledWith(String(CTX_DERIVE.calepinage.id)))
    expect(calepinageApi.calepinages.recentrerSurLead).not.toHaveBeenCalled()
  })

  it('un refus serveur (calepinage verrouillé) s’affiche en français', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue({ data: CTX_DERIVE })
    calepinageApi.calepinages.recentrerSurLead.mockRejectedValue({
      response: { status: 409, data: { calepinage: ['Calepinage verrouillé : devis envoyé.'] } },
    })
    rendreCalepinage(CTX_DERIVE.calepinage.id)

    await userEvent.click(await screen.findByTestId('acal-derive-recentrer'))
    expect(await screen.findByTestId('acal-derive-erreur'))
      .toHaveTextContent('Calepinage verrouillé : devis envoyé.')
  })

  it('recentre automatiquement quand derive.etat est automatique', async () => {
    calepinageApi.calepinages.designContext
      .mockResolvedValueOnce({ data: ctxAutomatique() })
      .mockResolvedValueOnce(reponseContrat('calepinage', 'calepinage_design_context'))
    // `clearAllMocks` ne remet pas les implémentations : on repose un succès explicite.
    calepinageApi.calepinages.recentrerSurLead.mockResolvedValue({ data: {} })
    rendreCalepinage(CTX_DERIVE.calepinage.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(calepinageApi.calepinages.recentrerSurLead).toHaveBeenCalledTimes(1)
    expect(calepinageApi.calepinages.recentrerSurLead)
      .toHaveBeenCalledWith(String(CTX_DERIVE.calepinage.id))
    // Le contexte est RELU après le recentrage : le constructeur boote dessus.
    expect(calepinageApi.calepinages.designContext).toHaveBeenCalledTimes(2)
    expect(initRoofToolPro8.mock.calls[0][0].hydrate.devis.geometrie.roof_point)
      .toEqual(CTX.geometrie.pin)
    expect(screen.queryByTestId('acal-derive-repere')).toBeNull()
  })

  it('« aucune » : ni bannière ni recentrage', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    rendreCalepinage(CTX.calepinage.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(screen.queryByTestId('acal-derive-repere')).toBeNull()
    expect(calepinageApi.calepinages.recentrerSurLead).not.toHaveBeenCalled()
  })
})

/* ACAL195 — une cible ESTIMÉE (source 'lead' | 'factures', ACAL194) n'est PAS une
   cible vendue : elle part comme point de départ modifiable. Contextes du contrat
   committé (`exemple_cible_lead`, `exemple_cible_refus`, `exemple`). */
describe('ToitureDesign — cible estimée vs cible vendue (ACAL195)', () => {
  it('une cible source factures ne pose pas cibleVendue et passe panneaux', async () => {
    const ctx = exempleContrat('calepinage', 'calepinage_design_context',
      'exemple_cible_lead')
    calepinageApi.calepinages.designContext.mockResolvedValue({ data: ctx })
    rendreCalepinage(ctx.calepinage.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    const payload = initRoofToolPro8.mock.calls[0][0].hydrate.devis
    expect(ctx.cible.source).toBe('factures')
    expect(payload.cibleVendue).toBe(false)
    expect(payload.cible.panneaux).toBe(ctx.cible.panneaux)
    expect(payload.cible.panel_watt).toBe(ctx.cible.panel_watt)
    expect(await screen.findByTestId('acal-cible-estimee')).toHaveTextContent(
      `Cible estimée depuis les factures du lead : ${ctx.cible.panneaux} panneaux (non vendue)`)
  })

  it('une cible source devis garde cibleVendue true', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    rendreCalepinage(CTX.calepinage.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(CTX.cible.source).toBe('devis')
    expect(initRoofToolPro8.mock.calls[0][0].hydrate.devis.cibleVendue).toBe(true)
    expect(screen.queryByTestId('acal-cible-estimee')).toBeNull()
  })

  it('cible.refus est affiché tel quel, rien n’est imposé', async () => {
    const ctx = exempleContrat('calepinage', 'calepinage_design_context',
      'exemple_cible_refus')
    calepinageApi.calepinages.designContext.mockResolvedValue({ data: ctx })
    rendreCalepinage(ctx.calepinage.id)

    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    const payload = initRoofToolPro8.mock.calls[0][0].hydrate.devis
    expect(payload.cibleVendue).toBe(false)
    expect(payload.cible.panneaux).toBeNull()
    expect(await screen.findByTestId('acal-cible-estimee'))
      .toHaveTextContent(ctx.cible.refus)
  })
})

describe('ToitureDesign — le fond photo charge le fichier par son URL servie (ACAL201)', () => {
  const PHOTOS = exempleContrat('calepinage', 'calepinage_photos').photos

  afterEach(() => { vi.unstubAllEnvs() })

  it('le fond photo utilise l’URL relative servie', async () => {
    const poserFond = vi.fn(() => ({ ok: true }))
    const photo = PHOTOS[0]
    reinitialiserBootMinimal({
      fondDuDocument: vi.fn(() => ({ kind: 'photo', photoSiteId: photo.id })),
      motifFondRefuse: vi.fn(() => null),
      poserFond,
    })
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.photos.mockResolvedValue({ data: { photos: PHOTOS } })

    rendreCalepinage(CTX.calepinage.id)

    await waitFor(() => expect(poserFond).toHaveBeenCalled())
    // VITE_API_URL vide : le chemin relatif du proxy, tel quel (même origine).
    expect(photo.url.startsWith('/api/django/calepinage/')).toBe(true)
    expect(poserFond.mock.calls[0][1].url).toBe(photo.url)
  })

  it('une origine d’API posée préfixe le chemin relatif', async () => {
    vi.stubEnv('VITE_API_URL', 'https://api.exemple.test')
    const poserFond = vi.fn(() => ({ ok: true }))
    const photo = PHOTOS[0]
    reinitialiserBootMinimal({
      fondDuDocument: vi.fn(() => ({ kind: 'photo', photoSiteId: photo.id })),
      motifFondRefuse: vi.fn(() => null),
      poserFond,
    })
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.photos.mockResolvedValue({ data: { photos: PHOTOS } })

    rendreCalepinage(CTX.calepinage.id)

    await waitFor(() => expect(poserFond).toHaveBeenCalled())
    expect(poserFond.mock.calls[0][1].url)
      .toBe(`https://api.exemple.test${photo.url}`)
  })
})
