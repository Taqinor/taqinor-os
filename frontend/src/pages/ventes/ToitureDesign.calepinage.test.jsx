import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, cleanup, waitFor, within } from '@testing-library/react'
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
  LAYOUT, snapshot, apiBuilder, serializeLayout,
} from '../../test/toitureDesignHarness'
import ventesApi from '../../api/ventesApi'
import calepinageApi from '../../api/calepinageApi'
import { toastInfo } from '../../lib/toast'
import { choisirPaletteAcces, couleurAccesActive, solarAccessColorRGB } from '@rooflib/shadingEngine'

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
      // ACAL777 — la facture mensuelle du lead servie (ACAL776), repli d'affichage des cartes.
      factureMensuelleMad: CTX.consommation_lead.facture_mensuelle_mad,
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

  /* ACAL398 — un enregistrement qui crée une version relance la simulation
     toute seule (UN POST sans `forcer`) ; inchangé → aucun appel ; refus 409
     → aucun toast (la phrase est reprise par l'onglet Production). */
  it('ACAL398 — version créée ⇒ UN POST simuler sans forcer ; refus 409 ⇒ aucun toast', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel.mockResolvedValue(
      { data: { inchange: false, version: 4 } })
    calepinageApi.calepinages.envoyerImage.mockResolvedValue({ data: {} })
    calepinageApi.calepinages.simuler.mockRejectedValue(
      { response: { status: 409, data: { detail: 'Mode météo non choisi.' } } })
    snapshot.mockReturnValue('data:image/png;base64,aGk=')

    rendreCalepinage(CTX.calepinage.id)
    await userEvent.click(await screen.findByRole('button',
      { name: /Enregistrer le calepinage/ }))

    await waitFor(() => expect(calepinageApi.calepinages.simuler).toHaveBeenCalledTimes(1))
    // Acceptation ACAL490 : le pont axios toastait le 409 — l'appel part SILENCIEUX.
    expect(calepinageApi.calepinages.simuler).toHaveBeenCalledWith(String(CTX.calepinage.id), { silencieux: true })
    expect(toastInfo).not.toHaveBeenCalled()
  })

  it('ACAL398 — conception inchangée ⇒ aucun appel simuler', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel.mockResolvedValue(
      { data: { inchange: true, version: null } })

    rendreCalepinage(CTX.calepinage.id)
    await userEvent.click(await screen.findByRole('button',
      { name: /Enregistrer le calepinage/ }))

    await waitFor(() => expect(toastInfo).toHaveBeenCalledWith('Aucun changement'))
    expect(calepinageApi.calepinages.simuler).not.toHaveBeenCalled()
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
    // Coque (22/11) : scène propre après l'écriture ⇒ « Enregistré à HH:MM » seul ; une retouche
    // ramène le bouton (le bandeau n'enregistre jamais tout seul).
    await screen.findByText(/Enregistré à \d{2}:\d{2}/)
    serializeLayout.mockReturnValue({ ...LAYOUT, result: { panels: 9 } })
    const rebouton = await screen.findByRole('button', { name: /Enregistrer le calepinage/ }, { timeout: 5000 })
    await waitFor(() => expect(rebouton).not.toBeDisabled())
    await userEvent.click(rebouton)
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

  /* ACAL994 — le chiffrage SERVI (économie, état, option) arrive à l'atelier à l'ouverture, puis relu après
     « Enregistrer » : la carte Économies et le Total passent à la valeur du serveur. Absent ⇒ `null`, jamais inventé. */
  it('ACAL994 — le chiffrage servi part à l’ouverture ; absent ⇒ null (l’atelier dit « estimation »)', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue({ data: CTX })
    rendreCalepinage(CTX.calepinage.id)
    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(initRoofToolPro8.mock.calls[0][0].chiffrage.economie_annee1_mad)
      .toEqual({ valeur: 7420, unite: 'MAD', source: 'devis', etat: 'servi', option: 'sans_batterie' })
    cleanup(); vi.clearAllMocks(); reinitialiserBoot()
    const { chiffrage: _retire, ...sansChiffrage } = CTX
    calepinageApi.calepinages.designContext.mockResolvedValue({ data: sansChiffrage })
    rendreCalepinage(CTX.calepinage.id)
    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(initRoofToolPro8.mock.calls[0][0].chiffrage).toBeNull()
  })

  it('ACAL994 — après enregistrement, le chiffrage RELU est poussé à l’atelier (la valeur servie remplace l’estimation)', async () => {
    const majChiffrage = vi.fn()
    reinitialiserBoot({ majChiffrage })
    // R2-13 — le compte du devis RELU (`cible.panneaux`, source « devis ») voyage avec le chiffrage.
    const apres = {
      ...CTX,
      cible: { ...CTX.cible, panneaux: CTX.cible.panneaux + 2 },
      chiffrage: { ...CTX.chiffrage, economie_annee1_mad: { ...CTX.chiffrage.economie_annee1_mad, valeur: 8123 } },
    }
    const avant = { ...CTX, chiffrage: { ...CTX.chiffrage, economie_annee1_mad: { ...CTX.chiffrage.economie_annee1_mad, etat: 'non_servi', valeur: null } } }
    calepinageApi.calepinages.designContext.mockResolvedValueOnce({ data: avant }).mockResolvedValue({ data: apres })
    calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel.mockResolvedValue(
      { data: { inchange: false, version: 4 } })
    rendreCalepinage(CTX.calepinage.id)
    expect(CTX.cible.source).toBe('devis')
    await waitFor(() => expect(majChiffrage).toHaveBeenCalledWith(avant.chiffrage, CTX.cible.panneaux))
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer le calepinage/ }))
    await waitFor(() => expect(majChiffrage).toHaveBeenLastCalledWith(apres.chiffrage, CTX.cible.panneaux + 2))
  })

  it('R2-13 — cible tirée des factures (pas d’un devis) : aucun compte « au devis » transmis', async () => {
    const majChiffrage = vi.fn()
    reinitialiserBoot({ majChiffrage })
    calepinageApi.calepinages.designContext.mockResolvedValue(
      { data: { ...CTX, cible: { ...CTX.cible, source: 'factures' } } })
    rendreCalepinage(CTX.calepinage.id)
    await waitFor(() => expect(majChiffrage).toHaveBeenCalledWith(CTX.chiffrage ?? null, null))
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

  /* ACAL399 — barre d'enregistrement collée en bas : indicateur d'état + bouton. */
  describe('ACAL399 — barre d’enregistrement', () => {
    const bootHydrate = () => initRoofToolPro8.mockImplementation((options) => {
      options?.onApiReady?.(apiBuilder())
      options?.onHydrationTerminee?.()
    })

    it('scène modifiée ⇒ « Modifications non enregistrées » ; après enregistrement ⇒ « Enregistré à HH:MM »', async () => {
      calepinageApi.calepinages.designContext.mockResolvedValue(
        reponseContrat('calepinage', 'calepinage_design_context'))
      calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel.mockResolvedValue(
        { data: { inchange: false, version: 5 } })
      calepinageApi.calepinages.envoyerImage.mockResolvedValue({ data: {} })
      bootHydrate()

      rendreCalepinage(CTX.calepinage.id)
      const bouton = await screen.findByRole('button', { name: /Enregistrer le calepinage/ })
      await waitFor(() => expect(serializeLayout).toHaveBeenCalled())
      expect(screen.queryByTestId('cal-etat-enregistrement')).toBeNull()

      serializeLayout.mockReturnValue({ ...LAYOUT, result: { panels: 9 } })
      await waitFor(() => expect(screen.getByTestId('cal-etat-enregistrement'))
        .toHaveTextContent('Modifications non enregistrées'), { timeout: 5000 })

      await userEvent.click(bouton)
      await waitFor(() => expect(screen.getByTestId('cal-etat-enregistrement'))
        .toHaveTextContent(/Enregistré à \d{2}:\d{2}/))
    })

    it('lecture seule ⇒ pas de barre', async () => {
      calepinageApi.calepinages.designContext.mockResolvedValue({
        data: { ...CTX, modifiable: false, raison_lecture_seule: 'Figé.' },
      })
      rendreCalepinage(CTX.calepinage.id)
      await screen.findByTestId('pv20-lecture-seule')
      expect(screen.queryByTestId('cal-enregistrer-calepinage')).toBeNull()
      expect(screen.queryByTestId('cal-etat-enregistrement')).toBeNull()
    })

    /* ACAL401 — barre de résumé vivante : les trois chiffres sont lus sur le document
       sérialisé (`result` de l'exemple COMMITTÉ roof_layout_v2), « — » quand absents. */
    describe('résumé vivant (ACAL401)', () => {
      const RESULT = exempleContrat('calepinage', 'roof_layout_v2.schema').result
      const texte = (id) => screen.getByTestId(id).textContent.replace(/\s+/g, ' ')

      it('document sérialisé ⇒ panneaux, kWc et production « estimation »', async () => {
        calepinageApi.calepinages.designContext.mockResolvedValue(
          reponseContrat('calepinage', 'calepinage_design_context'))
        calepinageApi.calepinages.resultat.mockResolvedValue(
          reponseContrat('calepinage', 'calepinage_resultat', 'exemple_perime'))
        serializeLayout.mockReturnValue({ ...LAYOUT, result: RESULT })
        bootHydrate()
        rendreCalepinage(CTX.calepinage.id)

        await waitFor(() => expect(texte('cal-resume-panneaux')).toContain(`${RESULT.panels} panneaux`),
          { timeout: 3000 })
        expect(texte('cal-resume-kwc')).toMatch(/14,40 kWc/)
        expect(texte('cal-resume-production')).toMatch(/≈ 18 771 kWh\/an \(estimation\)/)

        serializeLayout.mockReturnValue({ ...LAYOUT, result: { ...RESULT, panels: 19 } })
        await waitFor(() => expect(texte('cal-resume-panneaux')).toContain('19 panneaux'),
          { timeout: 3000 })
      })

      it('résultat frais ⇒ « P50 … (simulation) »', async () => {
        const frais = exempleContrat('calepinage', 'calepinage_resultat')
        calepinageApi.calepinages.designContext.mockResolvedValue(
          reponseContrat('calepinage', 'calepinage_design_context'))
        calepinageApi.calepinages.resultat.mockResolvedValue({ data: frais })
        serializeLayout.mockReturnValue({ ...LAYOUT, result: RESULT })
        bootHydrate()
        rendreCalepinage(CTX.calepinage.id)

        await waitFor(() => expect(texte('cal-resume-production'))
          .toMatch(/P50 13 000 kWh\/an \(simulation\)/))
      })

      it('chiffre absent ⇒ « — », jamais 0', async () => {
        calepinageApi.calepinages.designContext.mockResolvedValue(
          reponseContrat('calepinage', 'calepinage_design_context'))
        calepinageApi.calepinages.resultat.mockResolvedValue(
          reponseContrat('calepinage', 'calepinage_resultat', 'exemple_perime'))
        serializeLayout.mockReturnValue({ ...LAYOUT, result: {} })
        bootHydrate()
        rendreCalepinage(CTX.calepinage.id)

        await screen.findByTestId('cal-resume-panneaux')
        expect(texte('cal-resume-panneaux')).toBe('—')
        expect(texte('cal-resume-kwc')).toBe('—')
        expect(texte('cal-resume-production')).toBe('—')
      })
    })
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

  // ACAL955 — « Enregistrer » précède « Générer le devis » (ordre du DOM,
  // donc du clavier et des lecteurs d'écran) : la barre d'enregistrement
  // précède le bloc `AtelierPanneaux`, qui porte le bouton « Générer ».
  it('la barre « Enregistrer » précède le bloc qui porte « Générer le devis »', async () => {
    calepinageApi.calepinages.depuisModele.mockResolvedValue(
      { data: { id: CTX.calepinage.id } })
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))

    rendreDevis(CTX.calepinage.devis_lie.id)

    const panneaux = await screen.findByTestId('cal-atelier-panneaux')
    const barre = screen.getByTestId('cal-enregistrer-calepinage')
    expect(barre.compareDocumentPosition(panneaux) & Node.DOCUMENT_POSITION_FOLLOWING)
      .toBeTruthy()
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

  it('ACAL965 — le refus s’affiche UNE fois avec « Ouvrir la fiche du lead » vers la fiche ; sans lead, pas de lien', async () => {
    const ctx = exempleContrat('calepinage', 'calepinage_design_context', 'exemple_cible_refus')
    calepinageApi.calepinages.designContext.mockResolvedValue({ data: ctx })
    rendreCalepinage(ctx.calepinage.id)
    const bloc = await screen.findByTestId('acal-cible-estimee')
    expect(screen.getAllByText(ctx.cible.refus, { exact: false })).toHaveLength(1)
    expect(screen.getByRole('link', { name: 'Ouvrir la fiche du lead' }))
      .toHaveAttribute('href', `/crm/leads/${ctx.calepinage.lead}`)
    expect(bloc).toContainElement(screen.getByRole('link', { name: 'Ouvrir la fiche du lead' }))
    cleanup(); vi.clearAllMocks(); reinitialiserBoot()
    const sansLead = { ...ctx, calepinage: { ...ctx.calepinage, lead: null } }
    calepinageApi.calepinages.designContext.mockResolvedValue({ data: sansLead })
    rendreCalepinage(ctx.calepinage.id)
    await screen.findByTestId('acal-cible-estimee')
    expect(screen.queryByRole('link', { name: 'Ouvrir la fiche du lead' })).toBeNull()
  })

  it('R2-15 / R2-01 — la toiture déclarée sur le lead est AFFICHÉE avec « Voir la fiche du lead » ; rien quand il ne dit rien', async () => {
    const ctx = exempleContrat('calepinage', 'calepinage_design_context')
    calepinageApi.calepinages.designContext.mockResolvedValue({ data: ctx })
    rendreCalepinage(ctx.calepinage.id)
    const ligne = await screen.findByTestId('acal-toiture-lead')
    expect(ligne).toHaveTextContent('Le lead déclare : toiture · tuiles · 60 m² disponibles · pente 25° · sud-ouest')
    expect(ligne).toContainElement(screen.getByRole('link', { name: 'Voir la fiche du lead' }))
    expect(screen.getByRole('link', { name: 'Voir la fiche du lead' })).toHaveAttribute('href', `/crm/leads/${ctx.calepinage.lead}`)
    // Rien n'est prérempli : le payload du constructeur ne porte aucune valeur du lead.
    expect(JSON.stringify(initRoofToolPro8.mock.calls[0][0].hydrate.devis)).not.toContain('Sud-Ouest')
    cleanup(); vi.clearAllMocks(); reinitialiserBoot()
    const muet = exempleContrat('calepinage', 'calepinage_design_context', 'exemple_vide').toiture_lead
    calepinageApi.calepinages.designContext.mockResolvedValue({ data: { ...ctx, toiture_lead: muet } })
    rendreCalepinage(ctx.calepinage.id)
    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(screen.queryByTestId('acal-toiture-lead')).toBeNull()
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

describe('ACAL546 — « Comparer les poses » monté en mode calepinage, sans montant', () => {
  it('le bloc comparatif est monté : sans en-tête Économies, attribut data-sans-montant posé', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    rendreCalepinage(CTX.calepinage.id)
    await screen.findByRole('heading', { level: 1 })
    expect(screen.getByText('Comparer les poses')).toBeInTheDocument()
    const bloc = document.getElementById('rp9-compare-wrap')
    expect(bloc).not.toBeNull()
    expect(bloc.getAttribute('data-sans-montant')).toBe('1')
    expect(bloc.querySelector('#rp9-compare')).not.toBeNull()
    expect(bloc.querySelector('#rp9-matrix-filter')).not.toBeNull()
    expect(bloc.textContent).not.toMatch(/MAD|Économies/)
    expect(bloc.querySelectorAll('thead th')).toHaveLength(5)
  })
})

describe('REP-995 — le bandeau de provenance reçoit le chiffrage servi par design-context', () => {
  it('chiffrage servi (standard_ville) ⇒ la ligne « Le devis annonce » s’affiche, sans second appel design-context', async () => {
    const chiffrage = exempleContrat('ventes', 'chiffrage_conception', 'exemple_ville')
    calepinageApi.calepinages.designContext.mockResolvedValue({
      data: { ...CTX, chiffrage },
    })
    rendreCalepinage(CTX.calepinage.id)
    const ligne = await screen.findByTestId('acal995-devis-annonce')
    expect(ligne).toHaveTextContent('Le devis annonce')
    expect(calepinageApi.calepinages.designContext).toHaveBeenCalledTimes(1)
  })

  it('aucun chiffrage servi ⇒ aucune ligne', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    rendreCalepinage(CTX.calepinage.id)
    await screen.findByRole('heading', { level: 1 })
    expect(screen.queryByTestId('acal995-devis-annonce')).toBeNull()
  })
})

describe('ACAL868 — le bouton de l’étape suivante dans la barre fixe', () => {
  const clef = 'calepinage.mode_expert.anonyme'
  afterEach(() => { try { window.localStorage.removeItem(clef) } catch { /* ignoré */ } })

  it('guidé : la barre porte « Poser les panneaux » ; le clic ouvre l’étape Panneaux, puis « Raccorder les panneaux »', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    rendreCalepinage(CTX.calepinage.id)
    const bouton = await screen.findByTestId('cal-action-etape-suivante')
    expect(bouton).toHaveTextContent('Poser les panneaux')
    // Coque (22/11) : le bouton de l'étape suivante est au PIED du panneau d'étape (un seul par étape).
    expect(bouton.closest('#rp9-studio-inspecteur')).not.toBeNull()
    expect(screen.getAllByTestId('cal-action-etape-suivante')).toHaveLength(1)
    await userEvent.click(bouton)
    await waitFor(() => expect(screen.getByTestId('cal-action-etape-suivante')).toHaveTextContent('Raccorder les panneaux'))
  })

  it('mode expert : la barre garde le seul enregistrement', async () => {
    window.localStorage.setItem(clef, '1')
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    rendreCalepinage(CTX.calepinage.id)
    await screen.findByRole('button', { name: /Enregistrer le calepinage/ })
    expect(screen.queryByTestId('cal-action-etape-suivante')).toBeNull()
  })
})

describe('ACAL869 — le panneau « Personnaliser la disposition » en mode guidé', () => {
  const clef = 'calepinage.mode_expert.anonyme'
  afterEach(() => { try { window.localStorage.removeItem(clef) } catch { /* ignoré */ } })
  // ACAL876 — les « ? » d'explication (`commun/Pourquoi`, `data-grandeur`) posés sur les compteurs de pose ne sont
  // pas des gestes de disposition : ils sont hors du compte.
  const boutonsDeBase = () => [...document.querySelectorAll('#rp9-layout-panel button:not([data-grandeur])')]
    .filter((b) => !b.closest('#rp9-layout-avance'))

  it('guidé : 5 boutons visibles hors du volet, les autres rangés dans « Réglages avancés » replié', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    rendreCalepinage(CTX.calepinage.id)
    await screen.findByRole('button', { name: /Enregistrer le calepinage/ })
    expect(boutonsDeBase().map((b) => b.id).sort()).toEqual(
      ['rp9-layout-clear-sel', 'rp9-layout-fill', 'rp9-layout-redo', 'rp9-layout-select', 'rp9-layout-undo'])
    const volet = document.getElementById('rp9-layout-avance')
    expect(volet.open).toBe(false)
    expect(volet.querySelector('summary')).toHaveTextContent('Réglages avancés')
    // aucun id rp9-* retiré : les autres boutons restent dans le DOM, repliés (8 + « Ajouter un panneau » du placement libre, caché).
    expect(volet.querySelectorAll('button')).toHaveLength(9)
  })

  it('mode expert : le volet est ouvert d’office', async () => {
    window.localStorage.setItem(clef, '1')
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    rendreCalepinage(CTX.calepinage.id)
    await screen.findByRole('button', { name: /Enregistrer le calepinage/ })
    await waitFor(() => expect(document.getElementById('rp9-layout-avance').open).toBe(true))
  })
})

describe('ACAL945 — enregistrer hors ligne sans mentir', () => {
  const amorcer = () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.envoyerImage.mockResolvedValue({ data: {} })
  }

  it('réseau coupé : « Pas de réseau — enregistré sur ce téléphone », jamais « erreur 0 » ; `online` ⇒ UN seul second appel, même empreinte', async () => {
    amorcer()
    const enregistrer = calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel
    enregistrer.mockRejectedValueOnce({ code: 'ERR_NETWORK', message: 'Network Error' })
    enregistrer.mockResolvedValue({ data: { inchange: false, version: 6, empreinte_document: 'E9' } })
    rendreCalepinage(CTX.calepinage.id)
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer le calepinage/ }))

    expect(await screen.findByText(/Pas de réseau — enregistré sur ce téléphone, envoi automatique au retour du réseau\./)).toBeInTheDocument()
    expect(screen.queryByText(/erreur 0/)).toBeNull()
    expect(enregistrer).toHaveBeenCalledTimes(1)

    window.dispatchEvent(new Event('online'))
    await waitFor(() => expect(enregistrer).toHaveBeenCalledTimes(2))
    expect(enregistrer.mock.calls[1]).toEqual(enregistrer.mock.calls[0]) // même document, même empreinte
    window.dispatchEvent(new Event('online'))
    await waitFor(() => expect(screen.getByText(/enregistrée au retour du réseau/)).toBeInTheDocument())
    expect(enregistrer).toHaveBeenCalledTimes(2) // rejoué UNE fois
  })

  it('délai dépassé (ECONNABORTED) : rien n’est rejoué, la phrase dit que le serveur n’a pas répondu', async () => {
    amorcer()
    const enregistrer = calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel
    enregistrer.mockRejectedValue({ code: 'ECONNABORTED', message: 'timeout' })
    rendreCalepinage(CTX.calepinage.id)
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer le calepinage/ }))

    expect(await screen.findByText(/Le serveur n’a pas répondu/)).toBeInTheDocument()
    window.dispatchEvent(new Event('online'))
    expect(enregistrer).toHaveBeenCalledTimes(1)
  })
})

/* Coque (maquettes 22/11, Main / Resultats / Tablette) — l'atelier plein écran : bandeau du projet,
   rail des cinq étapes + « Avancé », carte au centre, panneau d'étape à droite ; les étapes pleines
   (Résultats, Documents) masquent carte et panneau SANS les démonter ; l'expert rend l'ancien inspecteur. */
describe('Coque — l’atelier plein écran (maquette Main)', () => {
  const clef = 'calepinage.mode_expert.anonyme'
  afterEach(() => { try { window.localStorage.removeItem(clef) } catch { /* ignoré */ } })
  const amorcer = () => calepinageApi.calepinages.designContext.mockResolvedValue(
    reponseContrat('calepinage', 'calepinage_design_context'))

  it('bandeau, rail, carte et panneau dans l’ordre de la maquette, aux libellés de la maquette', async () => {
    amorcer()
    rendreCalepinage(CTX.calepinage.id)
    const coque = await screen.findByTestId('cal-coque')
    const barre = screen.getByTestId('cal-barre-projet')
    // Le bandeau : « Calepinages », le nom servi (+ ville servie), la ligne lead + facture servie, Guidé | Expert, devis.
    expect(screen.getByTestId('cal-retour-liste')).toHaveTextContent('Calepinages')
    expect(screen.getByTestId('cal-projet-titre')).toHaveTextContent(CTX.calepinage.titre)
    expect(screen.getByTestId('cal-projet-titre')).toHaveTextContent(CTX.calepinage.client_ville)
    expect(screen.getByTestId('cal-projet-sous-titre')).toHaveTextContent(/^Lead · facture 900 MAD \/ mois$/)
    const mode = within(barre).getByRole('group', { name: 'Mode' })
    expect(within(mode).getAllByRole('button').map((b) => b.textContent)).toEqual(['Guidé', 'Expert'])
    expect(within(mode).getByRole('button', { name: 'Guidé' })).toHaveAttribute('aria-pressed', 'true')
    // Un devis lié (contrat) : le bouton doré dit « Resynchroniser le devis ».
    expect(screen.getByTestId('cal-generer-devis-haut')).toHaveTextContent('Resynchroniser le devis')
    // Le rail : 5 étapes empilées puis « Avancé » ; Toit en cours.
    const rail = screen.getByTestId('cal-rail-etapes')
    expect([...rail.querySelectorAll('button')].map((b) => b.querySelector('.cal-rail-libelle')?.textContent))
      .toEqual(['Toit', 'Panneaux', 'Électrique', 'Résultats', 'Documents', 'Avancé'])
    expect(screen.getByTestId('cal-etape-toit')).toHaveAttribute('aria-current', 'step')
    // L'ordre des zones : bandeau, rail, centre (carte), panneau.
    const zones = [barre, rail, document.getElementById('rp9-studio-scene'), screen.getByTestId('cal-panneau-etape')]
    for (let i = 1; i < zones.length; i += 1) {
      expect(zones[i - 1].compareDocumentPosition(zones[i]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    }
    // Le panneau : « Étape 1 sur 5 » au-dessus de « Le toit », pied doré « Poser les panneaux ».
    expect(screen.getByText('Étape 1 sur 5')).toBeTruthy()
    expect(screen.getByTestId('cal-panneau-etape-titre')).toHaveTextContent('Le toit')
    expect(await screen.findByTestId('cal-action-etape-suivante')).toHaveTextContent('Poser les panneaux')
    expect(coque).toHaveAttribute('data-cadre', 'carte')
  })

  it('Résultats : carte et panneau masqués (jamais démontés), la carte revient sur Toit et se recale (resize)', async () => {
    amorcer()
    rendreCalepinage(CTX.calepinage.id)
    await screen.findByTestId('cal-coque')
    const carte = document.getElementById('rp9-map')
    await userEvent.click(screen.getByTestId('cal-etape-resultats'))
    await waitFor(() => expect(screen.getByTestId('cal-coque')).toHaveAttribute('data-cadre', 'plein'))
    expect(document.getElementById('rp9-map')).toBe(carte)
    expect(document.getElementById('rp9-studio-scene').hidden).toBe(true)
    expect(screen.getByTestId('cal-panneau-etape').hidden).toBe(true)
    // Le panneau d'étape et ses groupes du constructeur restent montés.
    expect(document.getElementById('rp9-config')).not.toBeNull()
    expect(document.getElementById('rp9-layout-window')).not.toBeNull()
    const redimensionne = vi.fn()
    window.addEventListener('resize', redimensionne)
    try {
      await userEvent.click(screen.getByTestId('cal-etape-toit'))
      await waitFor(() => expect(document.getElementById('rp9-studio-scene').hidden).toBe(false))
      await waitFor(() => expect(redimensionne).toHaveBeenCalled())
      expect(document.getElementById('rp9-map')).toBe(carte)
    } finally { window.removeEventListener('resize', redimensionne) }
  })

  it('Expert : l’ancien inspecteur (onglets) est déplié, aucun bouton « suivant » ; Avancé le déplie en guidé', async () => {
    amorcer()
    rendreCalepinage(CTX.calepinage.id)
    await screen.findByTestId('cal-atelier-panneaux')
    const avance = screen.getByTestId('cal-atelier-panneaux').closest('.cal-coque-avance')
    expect(avance.hidden).toBe(true)
    await userEvent.click(screen.getByTestId('cal-rail-avance'))
    expect(avance.hidden).toBe(false)
    expect(screen.getByTestId('cal-rail-avance')).toHaveAttribute('aria-expanded', 'true')
    await userEvent.click(within(screen.getByTestId('cal-barre-projet')).getByRole('button', { name: 'Expert' }))
    await waitFor(() => expect(screen.getByTestId('cal-mode-expert')).toBeChecked())
    expect(screen.getByTestId('cal-rail-onglets')).toBeTruthy()
    expect(screen.queryByTestId('cal-action-etape-suivante')).toBeNull()
    expect(screen.getByTestId('cal-coque')).toHaveAttribute('data-expert', '1')
  })

  it('« N à régler » sous une étape : lu sur le parcours servi, absent sans manque', async () => {
    amorcer()
    calepinageApi.calepinages.parcours.mockResolvedValue(reponseContrat('calepinage', 'calepinage_parcours_guide'))
    rendreCalepinage(CTX.calepinage.id)
    // contrat : un manque « bloquant » × 2 et un « info » sur Résultats ⇒ « 2 à régler » sous Résultats seul.
    await waitFor(() => expect(screen.getByTestId('cal-etape-resultats')).toHaveTextContent('2 à régler'))
    expect(screen.getByTestId('cal-etape-toit')).not.toHaveTextContent('à régler')
  })

  it('« Avancé » (guidé) : une feuille à part par-dessus l’écran, l’écran guidé intact dessous ; Fermer la referme', async () => {
    amorcer()
    rendreCalepinage(CTX.calepinage.id)
    const coque = await screen.findByTestId('cal-coque')
    const titre = screen.getByTestId('cal-panneau-etape-titre').textContent
    const groupes = () => [...document.querySelectorAll('.cal-coque-groupe')].map((g) => g.hidden)
    const groupesAvant = groupes()
    await userEvent.click(screen.getByTestId('cal-rail-avance'))
    const feuille = await screen.findByRole('dialog', { name: 'Avancé' })
    expect(feuille).toHaveClass('cal-coque-avance')
    expect(coque).toHaveAttribute('data-feuille', '1')
    // L'écran guidé n'est pas touché : pas de bascule vers l'ancienne disposition, même titre d'étape.
    expect(coque).toHaveAttribute('data-avance', '0')
    expect(screen.getByTestId('cal-panneau-etape-titre').textContent).toBe(titre)
    expect(groupes(), 'les groupes du constructeur ne changent pas d’état').toEqual(groupesAvant)
    await userEvent.click(within(feuille).getByRole('button', { name: 'Fermer' }))
    expect(screen.getByTestId('cal-atelier-panneaux').closest('.cal-coque-avance').hidden).toBe(true)
    expect(coque).not.toHaveAttribute('data-feuille')
  })

  it('H7 — la feuille « Avancé » se referme quand on la quitte : lien suivi (CAL221), clic dehors, Échap', async () => {
    amorcer()
    rendreCalepinage(CTX.calepinage.id)
    const coque = await screen.findByTestId('cal-coque')
    const ouvrir = async () => {
      await userEvent.click(screen.getByTestId('cal-rail-avance'))
      await waitFor(() => expect(coque).toHaveAttribute('data-feuille', '1'))
    }
    // « Comparer les variantes » ouvre un autre écran : la feuille ne reste pas par-dessus (« Retenir » masqué avant).
    await ouvrir()
    await userEvent.click(screen.getByTestId('cal-lien-variantes'))
    await waitFor(() => expect(coque).not.toHaveAttribute('data-feuille'))
    expect(screen.queryByRole('dialog', { name: 'Avancé' })).toBeNull()
    // Un clic hors de la feuille (la carte) la referme ; un clic DANS la feuille, non.
    await ouvrir()
    await userEvent.click(within(screen.getByRole('dialog', { name: 'Avancé' })).getByRole('heading', { name: 'Avancé' }))
    expect(coque).toHaveAttribute('data-feuille', '1')
    await userEvent.click(document.getElementById('rp9-map'))
    await waitFor(() => expect(coque).not.toHaveAttribute('data-feuille'))
    await ouvrir()
    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(coque).not.toHaveAttribute('data-feuille'))
  })

  it('scène propre déjà enregistrée : « ✓ Enregistré … » seul, comme la maquette ; modifiée : le bouton revient', async () => {
    amorcer()
    calepinageApi.calepinages.get.mockResolvedValue({ data: { versions: { derniere_le: new Date().toISOString() } } })
    rendreCalepinage(CTX.calepinage.id)
    const barre = await screen.findByTestId('cal-enregistrer-calepinage')
    await waitFor(() => expect(within(barre).getByTestId('cal-etat-enregistrement'))
      .toHaveTextContent(/^Enregistré à \d{2}:\d{2}$/))
    // Aucun « Enregistrer le calepinage » LU à l'écran : l'état porte le geste (nom accessible « … à nouveau »).
    expect(barre.textContent).not.toMatch(/Enregistrer le calepinage/)
    const geste = within(barre).getByRole('button', { name: /Enregistrer le calepinage à nouveau/ })
    expect(geste).toContainElement(within(barre).getByTestId('cal-etat-enregistrement'))
    serializeLayout.mockReturnValue({ ...LAYOUT, result: { panels: 9 } })
    await waitFor(() => expect(within(barre).getByTestId('cal-etat-enregistrement'))
      .toHaveTextContent('Modifications non enregistrées'), { timeout: 5000 })
    expect(within(barre).getByRole('button', { name: 'Enregistrer le calepinage' })).toBeVisible()
  })

  it('H1 — chaque étape à carte s’ouvre en Plan, toit cadré (Toit, Panneaux, Électrique), jamais une étape pleine ; caméra seule', async () => {
    const cadrerToit = vi.fn(() => true)
    const appliquerVue = vi.fn()
    reinitialiserBoot({ cadrerToit, appliquerVue })
    amorcer()
    calepinageApi.calepinages.get.mockResolvedValue({ data: { versions: { derniere_le: new Date().toISOString() } } })
    rendreCalepinage(CTX.calepinage.id)
    await screen.findByTestId('cal-coque')
    await waitFor(() => expect(cadrerToit).toHaveBeenCalled())
    expect(cadrerToit).toHaveBeenCalledWith({ zoomMax: 22, basPx: 0 })
    for (const etape of ['panneaux', 'electrique']) {
      cadrerToit.mockClear(); appliquerVue.mockClear()
      await userEvent.click(screen.getByTestId(`cal-etape-${etape}`))
      await waitFor(() => expect(appliquerVue, etape).toHaveBeenCalledWith('dessus'))
      await waitFor(() => expect(cadrerToit, etape).toHaveBeenCalled())
    }
    await userEvent.click(screen.getByTestId('cal-etape-resultats'))
    await waitFor(() => expect(document.getElementById('rp9-studio-scene').hidden).toBe(true))
    cadrerToit.mockClear(); appliquerVue.mockClear()
    await new Promise((r) => { setTimeout(r, 1700) })
    expect(cadrerToit, 'étape pleine : la carte est masquée, rien n’est cadré').not.toHaveBeenCalled()
    await userEvent.click(screen.getByTestId('cal-etape-toit'))
    await waitFor(() => expect(cadrerToit).toHaveBeenCalled())
    expect(appliquerVue).toHaveBeenCalledWith('dessus')
    // Caméra seule : la barre reste « Enregistré », aucun brouillon serveur écrit.
    expect(screen.getByTestId('cal-etat-enregistrement')).toHaveTextContent(/^Enregistré/)
    expect(calepinageApi.calepinages.envoyerBrouillon).not.toHaveBeenCalled()
  })

  it('H1 — une vue CHOISIE par l’utilisateur (Avancé › 3/4) n’est plus remplacée par Plan aux étapes suivantes ; le cadrage, si', async () => {
    const cadrerToit = vi.fn(() => true)
    const appliquerVue = vi.fn()
    reinitialiserBoot({ cadrerToit, appliquerVue })
    amorcer()
    rendreCalepinage(CTX.calepinage.id)
    await screen.findByTestId('cal-coque')
    await userEvent.click(screen.getByTestId('cal-rail-avance'))
    await userEvent.click(await screen.findByTestId('cal-vue-trois-quarts'))
    await userEvent.click(screen.getByTestId('cal-etape-panneaux'))
    // (l'étape Toit, démontée, pose encore sa propre vue d'entrée : on ne juge que la coque, après l'entrée sur Panneaux)
    appliquerVue.mockClear(); cadrerToit.mockClear()
    await waitFor(() => expect(cadrerToit).toHaveBeenCalled(), { timeout: 5000 })
    expect(appliquerVue).not.toHaveBeenCalledWith('dessus')
  })

  it('H1 — regarder le soleil (instant de scène sérialisé) n’est PAS une modification : ni « non enregistrées », ni brouillon', async () => {
    amorcer()
    calepinageApi.calepinages.get.mockResolvedValue({ data: { versions: { derniere_le: new Date().toISOString() } } })
    serializeLayout.mockReturnValue({ ...LAYOUT, scene: { sunDay: 355, sunHour: 12 } })
    rendreCalepinage(CTX.calepinage.id)
    const barre = await screen.findByTestId('cal-enregistrer-calepinage')
    await waitFor(() => expect(within(barre).getByTestId('cal-etat-enregistrement')).toHaveTextContent(/^Enregistré/))
    // Été, 15 h (ce que le lecteur du soleil écrit dans `scene`) : on attend plus d'un tic de brouillon (4 s) et de sondage (1,5 s).
    serializeLayout.mockReturnValue({ ...LAYOUT, scene: { sunDay: 172, sunHour: 15 } })
    await new Promise((r) => { setTimeout(r, 5500) })
    expect(within(barre).getByTestId('cal-etat-enregistrement')).toHaveTextContent(/^Enregistré/)
    expect(calepinageApi.calepinages.envoyerBrouillon).not.toHaveBeenCalled()
    // Témoin : une VRAIE modification du document, elle, se voit toujours.
    serializeLayout.mockReturnValue({ ...LAYOUT, scene: { sunDay: 172, sunHour: 15 }, result: { panels: 9 } })
    await waitFor(() => expect(within(barre).getByTestId('cal-etat-enregistrement'))
      .toHaveTextContent('Modifications non enregistrées'), { timeout: 5000 })
  }, 20000)

  it('H1 — lecture de démarrage sans réponse (délai de 20 s dépassé) : relancée UNE fois, l’atelier démarre sans erreur', async () => {
    calepinageApi.calepinages.designContext
      .mockRejectedValueOnce(Object.assign(new Error('timeout of 20000ms exceeded'), { code: 'ECONNABORTED' }))
      .mockResolvedValue(reponseContrat('calepinage', 'calepinage_design_context'))
    rendreCalepinage(CTX.calepinage.id)
    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(calepinageApi.calepinages.designContext).toHaveBeenCalledTimes(2)
    expect(screen.queryByTestId('cal-erreur-chargement')).toBeNull()
  })

  it('H1 — chargement raté (design-context 504) : rien ne peut être enregistré ni mis en brouillon, « Réessayer » est offert', async () => {
    calepinageApi.calepinages.designContext.mockRejectedValue({ response: { status: 504 } })
    rendreCalepinage(CTX.calepinage.id)
    const alerte = await screen.findByTestId('cal-erreur-chargement')
    expect(alerte).toHaveTextContent('Impossible de charger le calepinage — réessayez. Rien n’a été modifié.')
    expect(within(alerte).getByRole('button', { name: 'Réessayer' })).toBeVisible()
    const bouton = within(screen.getByTestId('cal-enregistrer-calepinage')).getAllByRole('button')[0]
    expect(bouton).toBeDisabled()
    await userEvent.click(bouton)
    await new Promise((r) => { setTimeout(r, 1700) })
    expect(screen.queryByText('Modifications non enregistrées')).toBeNull()
    expect(initRoofToolPro8).not.toHaveBeenCalled()
    for (const nom of ['enregistrerLayoutCalepinageConditionnel', 'modifierVariante', 'envoyerBrouillon', 'effacerBrouillon']) {
      const fn = calepinageApi.calepinages[nom]
      if (typeof fn?.mock === 'object') expect(fn, nom).not.toHaveBeenCalled()
    }
  })

  it('H1 — bandeau : à partir d’Électrique, la ligne dit la pose SERVIE (panneaux · kWc), + l’onduleur à Résultats et Documents', async () => {
    amorcer()
    const res = reponseContrat('calepinage', 'calepinage_resultat')
    calepinageApi.calepinages.resultat.mockResolvedValue(res)
    rendreCalepinage(CTX.calepinage.id)
    await screen.findByTestId('cal-coque')
    await userEvent.click(screen.getByTestId('cal-etape-toit'))
    expect(screen.getByTestId('cal-projet-sous-titre')).toHaveTextContent(/^Lead · facture 900 MAD \/ mois$/)
    const { total_modules: n } = res.data.pose
    const o = res.data.electrique.onduleurs[0]
    await userEvent.click(screen.getByTestId('cal-etape-electrique'))
    const kwc = res.data.pose.kwc.toLocaleString('fr-FR', { minimumFractionDigits: 2 })
    await waitFor(() => expect(screen.getByTestId('cal-projet-sous-titre').textContent).toBe(`${n} panneaux · ${kwc} kWc`))
    await userEvent.click(screen.getByTestId('cal-etape-documents'))
    await waitFor(() => expect(screen.getByTestId('cal-projet-sous-titre').textContent)
      .toBe(`${n} panneaux · ${kwc} kWc · ${o.nombre} onduleur ${o.taille_kw} kW`))
  })

  it('H1 — les boutons de zoom de la carte sont nommés en français même quand la carte se monte tard', async () => {
    amorcer()
    rendreCalepinage(CTX.calepinage.id)
    await screen.findByTestId('cal-coque')
    const zoom = document.createElement('button')
    zoom.className = 'maplibregl-ctrl-zoom-in'
    zoom.setAttribute('aria-label', 'Zoom in')
    screen.getByTestId('rp9-map-wrap').appendChild(zoom)
    await waitFor(() => expect(zoom).toHaveAttribute('aria-label', 'Zoomer'))
    expect(zoom).toHaveAttribute('title', 'Zoomer')
  })

  it('F6 — palette d’accès solaire bleu nuit → or posée dès le boot (toute étape, Expert compris)', async () => {
    choisirPaletteAcces('site')
    amorcer()
    rendreCalepinage(CTX.calepinage.id)
    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    // 0 % d'accès = #1f3b73 (rampe de la maquette), plus le rouge du site public.
    expect(couleurAccesActive(0)).toEqual({ r: 0x1f / 255, g: 0x3b / 255, b: 0x73 / 255 })
    expect(couleurAccesActive(0)).not.toEqual(solarAccessColorRGB(0))
  })

  it('Documents : sans enregistrement dans la session, « Faits à partir de la version enregistrée à HH:MM » lit la version servie', async () => {
    amorcer()
    calepinageApi.calepinages.get.mockResolvedValue({ data: { versions: { derniere_le: '2026-11-21T14:41:00' } } })
    rendreCalepinage(CTX.calepinage.id)
    await screen.findByTestId('cal-coque')
    await userEvent.click(screen.getByTestId('cal-etape-documents'))
    expect(await screen.findByText('Faits à partir de la version enregistrée à 14:41.', {}, { timeout: 5000 })).toBeTruthy()
  })

  it('tablette (< 1 280 px) : le panneau devient le tiroir du bas, poignée qui l’agrandit ; titre et pied dans le même tiroir', async () => {
    const avant = window.matchMedia
    window.matchMedia = (q) => ({ matches: q === '(max-width: 1279px)', media: q, addEventListener() {}, removeEventListener() {} })
    try {
      amorcer()
      rendreCalepinage(CTX.calepinage.id)
      const panneau = await screen.findByTestId('cal-panneau-etape')
      expect(panneau).toHaveAttribute('data-tiroir', '1')
      expect(panneau).toHaveAttribute('data-deplie', '0')
      const poignee = within(panneau).getByRole('button', { name: 'Agrandir ou réduire le panneau du bas' })
      expect(poignee).toHaveAttribute('aria-expanded', 'false')
      await userEvent.click(poignee)
      expect(panneau).toHaveAttribute('data-deplie', '1')
      // (l'étape ouverte dépend du parcours servi : on vérifie la forme, pas l'étape)
      expect(within(panneau).getByTestId('cal-panneau-etape-titre').textContent).not.toBe('')
      expect(await within(panneau).findByTestId('cal-action-etape-suivante')).toHaveTextContent(/\S/)
      // Les groupes du constructeur restent dans le même panneau (jamais remontés ailleurs).
      expect(panneau.contains(document.getElementById('rp9-config'))).toBe(true)
    } finally { window.matchMedia = avant }
  })
})
