import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, cleanup, waitFor, within, act, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'
import { formatNumber } from '../../lib/format'

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
import { reprendreSimulationAuto } from '../../features/calepinage/production/simulationAuto'
import { choisirPaletteAcces, couleurAccesActive, solarAccessColorRGB } from '@rooflib/shadingEngine'

const CTX = exempleContrat('calepinage', 'calepinage_design_context')
const CTX_VIDE = exempleContrat('calepinage', 'calepinage_design_context',
  'exemple_vide')

beforeEach(() => {
  vi.clearAllMocks()
  reinitialiserBoot()
})
afterEach(() => {
  cleanup(); vi.clearAllMocks()
  // ACAL1731 — l'étape où l'on s'arrête est mémorisée par calepinage : aucune fuite d'un cas au suivant.
  try {
    Object.keys(window.localStorage).filter((k) => k.startsWith('calepinage.etape.'))
      .forEach((k) => window.localStorage.removeItem(k))
  } catch { /* stockage refusé : rien à nettoyer */ }
})

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
      // ACAL1331 — l'origine de la cible servie (ici le devis lié) : l'atelier la dit à la pose.
      origineCible: CTX.cible.source,
      // T4-X8-012 (une cible) — la même source dans les mots de la carte « Cible — panneaux ».
      libelleOrigineCible: 'Devis lié',
      libelleApresOrigineCible: 'le devis lié',
      // ACAL1951 — le devis lié et l'option servie : l'atelier les NOMME dans sa note (« 7 au devis DEV-… (option avec batterie) »).
      referenceDevis: CTX.calepinage.devis_lie.reference,
      optionCible: CTX.cible.option,
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
        CTX.geometrie.empreinte_document, { suppressErrorToast: true })) // T4-U4-027 — l'écran dit lui-même les refus
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

  /* ACAL1987 (D-ACAL-90 renversée) — UN SEUL déclencheur : le serveur. Un enregistrement qui crée une version ne
     fait plus POSTer `simuler/` au navigateur : il LIT l'état servi (`simulation_automatique` de `GET resultat/`),
     sans toast, et retient le job du serveur pour l'onglet Production. */
  it('ACAL1987 — version créée ⇒ AUCUN POST simuler du navigateur ; il lit l’état servi, sans toast', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel.mockResolvedValue(
      { data: { inchange: false, version: 4 } })
    calepinageApi.calepinages.envoyerImage.mockResolvedValue({ data: {} })
    const enCours = exempleContrat('calepinage', 'calepinage_resultat', 'exemple_vide')
    calepinageApi.calepinages.resultat.mockResolvedValue({
      data: { ...enCours, simulation_automatique: { en_cours: true, job_id: 274, manquants: [] } } })
    snapshot.mockReturnValue('data:image/png;base64,aGk=')

    rendreCalepinage(CTX.calepinage.id)
    await userEvent.click(await screen.findByRole('button',
      { name: /Enregistrer le calepinage/ }))

    await waitFor(() => expect(calepinageApi.calepinages.resultat)
      .toHaveBeenCalledWith(String(CTX.calepinage.id)))
    expect(calepinageApi.calepinages.simuler).not.toHaveBeenCalled()
    expect(toastInfo).not.toHaveBeenCalled()
    // Le job du SERVEUR est retenu pour l'onglet Production (une seule reprise).
    await act(async () => {}) // laisse la lecture résolue écrire la table
    expect(reprendreSimulationAuto(CTX.calepinage.id)).toEqual({ jobId: 274 })
  })

  it('ACAL1275 — « Générer le devis » sur une conception inchangée : aucun toast « Aucun changement » ; « Enregistrer » le garde', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel.mockResolvedValue(
      { data: { inchange: true, version: null } })
    calepinageApi.calepinages.genererDevis.mockResolvedValue(
      { data: { devis: 43, reference: 'DEV-2611-0043', deduplique: false } })
    calepinageApi.calepinages.get.mockResolvedValue(reponseContrat('calepinage', 'calepinage_detail', 'exemple_vide'))

    rendreCalepinage(CTX.calepinage.id, '?onglet=documents')
    await screen.findByTestId('cal-generer-devis', {}, { timeout: 15_000 })
    await waitFor(() => expect(screen.getByTestId('cal-generer-devis')).toBeEnabled())
    await userEvent.click(screen.getByTestId('cal-generer-devis'))

    expect(await screen.findByTestId('cal-devis-cree', {}, { timeout: 10_000 })).toHaveTextContent('DEV-2611-0043')
    expect(calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel).toHaveBeenCalledTimes(1)
    expect(toastInfo).not.toHaveBeenCalledWith('Aucun changement')

    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer le calepinage/ }))
    await waitFor(() => expect(toastInfo).toHaveBeenCalledWith('Aucun changement'))
  })

  it('ACAL1437 — à Documents, le clic de la barre déclenche la génération (même route que le bloc)', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel.mockResolvedValue(
      { data: { inchange: true, version: null } })
    calepinageApi.calepinages.genererDevis.mockResolvedValue(
      { data: { devis: 43, reference: 'DEV-2611-0043', deduplique: false } })
    calepinageApi.calepinages.get.mockResolvedValue(reponseContrat('calepinage', 'calepinage_detail', 'exemple_vide'))

    rendreCalepinage(CTX.calepinage.id, '?onglet=documents')
    await screen.findByTestId('cal-generer-devis', {}, { timeout: 15_000 })
    await waitFor(() => expect(screen.getByTestId('cal-generer-devis')).toBeEnabled())
    await userEvent.click(screen.getByTestId('cal-generer-devis-haut'))

    expect(await screen.findByTestId('cal-devis-cree', {}, { timeout: 10_000 })).toHaveTextContent('DEV-2611-0043')
    expect(calepinageApi.calepinages.genererDevis).toHaveBeenCalledTimes(1)
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

  /* ACAL1905 — un enregistrement dont la réponse n'est pas revenue (délai dépassé) : le serveur a pu l'écrire. L'écran
     RELIT l'empreinte (`GET layout/`) : changée ⇒ « Enregistré » (aucun message de coupure, le jeton suivant est la
     nouvelle empreinte) ; inchangée ⇒ le message de coupure d'avant (rien n'est écrit : réessayez). */
  it('ACAL1905 — délai dépassé mais écriture faite : l’écran relit l’empreinte et dit « Enregistré »', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    const nouvelle = 'c'.repeat(64)
    calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel
      .mockRejectedValue({ code: 'ECONNABORTED', message: 'timeout of 20000ms exceeded' })
    serializeLayout.mockReturnValue(LAYOUT)
    calepinageApi.calepinages.layout.mockResolvedValue({ data: { empreinte_document: nouvelle, roof_layout: LAYOUT } })

    rendreCalepinage(CTX.calepinage.id)
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer le calepinage/ }))

    await screen.findByText(/Enregistré à \d{2}:\d{2}/)
    expect(calepinageApi.calepinages.layout).toHaveBeenCalledWith(String(CTX.calepinage.id))
    expect(screen.queryByTestId('cal-erreur-enregistrement')).toBeNull()
    expect(screen.queryByText(/Le serveur n’a pas répondu/)).toBeNull()
  })

  /* Critique de la vague C : une empreinte changée par QUELQU'UN D'AUTRE (autre onglet, collègue) n'est pas notre réussite.
     Le document relu diffère de celui envoyé : rien n'est dit « enregistré », le message de coupure reste. */
  it('ACAL1905 — délai dépassé et empreinte changée par un autre : jamais « Enregistré »', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    serializeLayout.mockReturnValue(LAYOUT)
    calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel
      .mockRejectedValue({ code: 'ECONNABORTED', message: 'timeout of 20000ms exceeded' })
    calepinageApi.calepinages.layout.mockResolvedValue({
      data: { empreinte_document: 'd'.repeat(64), roof_layout: { ...LAYOUT, result: { panels: 99 } } },
    })

    rendreCalepinage(CTX.calepinage.id)
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer le calepinage/ }))

    expect(await screen.findByTestId('cal-erreur-enregistrement', {}, { timeout: 8000 }))
      .toHaveTextContent('Le serveur n’a pas répondu')
    expect(screen.queryByText(/Enregistré à \d{2}:\d{2}/)).toBeNull()
  }, 15000)

  it('ACAL1905 — délai dépassé et rien d’écrit (empreinte inchangée) : le message de coupure reste, on peut réessayer', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel
      .mockRejectedValue({ code: 'ECONNABORTED', message: 'timeout of 20000ms exceeded' })
    calepinageApi.calepinages.layout.mockResolvedValue({ data: { empreinte_document: CTX.geometrie.empreinte_document } })

    rendreCalepinage(CTX.calepinage.id)
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer le calepinage/ }))

    expect(await screen.findByTestId('cal-erreur-enregistrement', {}, { timeout: 8000 }))
      .toHaveTextContent('Le serveur n’a pas répondu')
    // (le boot lit aussi `layout/` : au moins les trois relectures de l'écran s'y ajoutent)
    expect(calepinageApi.calepinages.layout.mock.calls.length).toBeGreaterThanOrEqual(3)
  }, 15000)

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
    // T4-U4-027 — la phrase SERVIE, une fois, en entier (plus de seconde phrase locale dans le même bandeau)…
    expect(banniere).toHaveTextContent(conflit.detail)
    expect(document.body.textContent.split(conflit.detail).length - 1).toBe(1)
    expect(banniere).not.toHaveTextContent('(onglet, autre navigateur)')
    // … aucun toast global en plus (l'écran gère le refus), et la barre dit le refus, jamais « Enregistré ».
    expect(calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel.mock.calls[0][3]).toEqual({ suppressErrorToast: true })
    expect(screen.getByTestId('cal-etat-enregistrement')).toHaveTextContent('Non enregistré : modifié ailleurs')
    expect(screen.queryByText(/Enregistré à/)).toBeNull()
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
      // T4-X8-010 — le bouton dit ce qu'il fait, et le fait : CE brouillon est effacé, le bandeau ne revient pas pour lui.
      expect(screen.getByTestId('cal-brouillon-ignorer')).toHaveTextContent(/^Effacer ce brouillon$/)
      await userEvent.click(screen.getByTestId('cal-brouillon-ignorer'))
      expect(screen.queryByTestId('cal-brouillon-bandeau')).toBeNull()
      expect(initRoofToolPro8).toHaveBeenCalledTimes(1)
      expect(window.localStorage.getItem(cle)).toBeNull()
      cleanup(); reinitialiserBoot()
      const boots = initRoofToolPro8.mock.calls.length
      rendreCalepinage(CTX.calepinage.id)
      await waitFor(() => expect(initRoofToolPro8.mock.calls.length).toBeGreaterThan(boots))
      expect(screen.queryByTestId('cal-brouillon-bandeau')).toBeNull()
      // Un brouillon PLUS RÉCENT (nouveaux gestes) relève le bandeau.
      cleanup(); reinitialiserBoot()
      window.localStorage.setItem(cle, JSON.stringify({ layout: { version: 2, zones: [{ id: 'neuf' }] }, horodatage: '2026-10-05T10:00:00.000Z' }))
      rendreCalepinage(CTX.calepinage.id)
      expect(await screen.findByTestId('cal-brouillon-bandeau')).toBeTruthy()
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

  /* Relecture M1 — le bandeau « Site non localisé » imprime le site que le SERVEUR prendra
     (`calepinage.site_de_repli`) ; un client sans lead n'a pas de `client_ville` : avant, le
     bandeau disait « refusé » alors que le serveur calculait sur la ville de l'adresse. */
  it.each([
    ['Casablanca (ville de référence)', /sinon le calcul se fait sur Casablanca \(ville de référence\)\./],
    [null, /sinon le calcul est refusé\./],
  ])('site non localisé : le bandeau dit ce que fera le serveur (%s)', async (siteDeRepli, attendu) => {
    initRoofToolPro8.mockImplementation((options) => { options?.suiviSite?.ecouter?.(null) })
    calepinageApi.calepinages.designContext.mockResolvedValue({ data: {
      ...CTX_VIDE, carte: CTX.carte,
      calepinage: { ...CTX_VIDE.calepinage, client_ville: '', site_de_repli: siteDeRepli },
    } })

    rendreCalepinage(CTX_VIDE.calepinage.id)

    expect(await screen.findByText(attendu)).toBeInTheDocument()
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

      // ACAL1661 — une VRAIE retouche suit un geste de l'utilisateur ; sans geste, l'outil qui se règle seul n'est pas une modification
      fireEvent.pointerDown(document.body)
      serializeLayout.mockReturnValue({ ...LAYOUT, result: { panels: 9 } })
      await waitFor(() => expect(screen.getByTestId('cal-etat-enregistrement'))
        .toHaveTextContent('Modifications non enregistrées'), { timeout: 5000 })

      await userEvent.click(bouton)
      await waitFor(() => expect(screen.getByTestId('cal-etat-enregistrement'))
        .toHaveTextContent(/Enregistré à \d{2}:\d{2}/))
    })

    it('T4-U4-015 — l’heure lue est l’heure SERVEUR de la version enregistrée, la même dans la session et à la réouverture', async () => {
      // La version servie a été enregistrée à 16:10 (heure serveur) ; la réponse de l'enregistrement arrive à 16:20 (en-tête
      // `Date`). Un renvoi à l'identique (« Aucun changement ») n'écrit aucune version : la barre et les Documents disent
      // 16:10 — comme à la réouverture —, jamais l'heure du clic.
      const jour = new Date()
      const a = (h, m) => new Date(jour.getFullYear(), jour.getMonth(), jour.getDate(), h, m).toISOString()
      calepinageApi.calepinages.designContext.mockResolvedValue(
        reponseContrat('calepinage', 'calepinage_design_context'))
      calepinageApi.calepinages.get.mockResolvedValue({ data: { versions: { derniere_le: a(16, 10) } } })
      calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel.mockResolvedValue(
        { data: { inchange: true, version: null }, headers: { date: a(16, 20) } })
      bootHydrate()
      rendreCalepinage(CTX.calepinage.id)
      await waitFor(() => expect(screen.getByTestId('cal-etat-enregistrement')).toHaveTextContent('Enregistré à 16:10'))
      await userEvent.click(screen.getByRole('button', { name: /Enregistrer le calepinage/ }))
      await waitFor(() => expect(calepinageApi.calepinages.get.mock.calls.length).toBeGreaterThan(1))
      await waitFor(() => expect(screen.getByTestId('cal-etat-enregistrement')).toHaveTextContent('Enregistré à 16:10'))
      expect(screen.getByTestId('cal-etat-enregistrement')).not.toHaveTextContent('16:20')
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

      // T4-X8-013 — sans simulation fraîche, la production est « — » : jamais une seconde estimation (≈ … estimation).
      it('document sérialisé ⇒ panneaux et kWc ; sans simulation fraîche, production « — »', async () => {
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
        expect(texte('cal-resume-production')).toBe('—')

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
    // ACAL1805 — une cible estimée SANS refus n'ouvre plus aucune bande sous le bandeau (la maquette v2 n'en a pas :
    // la cible se lit dans la pilule « Besoin d'après la facture » de l'étape Toit) ; la carte gagne 52 px.
    await screen.findByTestId('cal-coque')
    expect(screen.queryByTestId('acal-cible-estimee')).toBeNull()
    expect(screen.queryByText(/Cible estimée depuis/)).toBeNull()
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
    // T4-X9-013 — sans lead, le refus du moteur (phrase sur « le lead ») n'est plus affiché du tout : ni bande, ni lien.
    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    expect(screen.queryByTestId('acal-cible-estimee')).toBeNull()
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
  // T4-X9-004 (rejeu R5B) — `resultat/` ne sert ici ni la taille de la pose (`pose.kwc`) ni le bloc `conception` : rien ne
  // dit que le chiffre est celui d'un devis portant cette pose ; le chiffrage servi est celui de la CONCEPTION du lead.
  it('chiffrage servi (standard_ville), taille de pose non servie ⇒ la ligne nomme la conception et sa taille, sans second appel design-context', async () => {
    const chiffrage = exempleContrat('ventes', 'chiffrage_conception', 'exemple_ville')
    calepinageApi.calepinages.designContext.mockResolvedValue({
      data: { ...CTX, chiffrage },
    })
    rendreCalepinage(CTX.calepinage.id)
    const ligne = await screen.findByTestId('acal995-devis-annonce')
    expect(ligne.textContent.replace(/\s/g, ' ')).toBe(
      `Conception du lead (71,00 kWc) : ${formatNumber(chiffrage.production_annuelle_kwh.valeur, { decimals: 0 })} kWh/an — `
        .replace(/\s/g, ' ') + 'production standard de la ville')
    expect(ligne).not.toHaveTextContent('Le devis annonce')
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
    // ACAL1905 — l'écran relit d'abord l'empreinte du serveur : inchangée = rien n'a été écrit, la phrase reste.
    calepinageApi.calepinages.layout.mockResolvedValue({ data: { empreinte_document: CTX.geometrie.empreinte_document } })
    rendreCalepinage(CTX.calepinage.id)
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer le calepinage/ }))

    expect(await screen.findByText(/Le serveur n’a pas répondu/, {}, { timeout: 8000 })).toBeInTheDocument()
    window.dispatchEvent(new Event('online'))
    expect(enregistrer).toHaveBeenCalledTimes(1)
  }, 15000)
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
    calepinageApi.calepinages.get.mockResolvedValue(reponseContrat('calepinage', 'calepinage_detail'))
    rendreCalepinage(CTX.calepinage.id)
    const coque = await screen.findByTestId('cal-coque')
    const barre = screen.getByTestId('cal-barre-projet')
    // Le bandeau : « Calepinages », le nom servi (+ ville servie), la ligne lead + facture servie, Guidé | Expert, devis.
    expect(screen.getByTestId('cal-retour-liste')).toHaveTextContent('Calepinages')
    // T4-B4-009 (remplace ACAL1730) : UN nom de l'ouverture à la fin — celui du calepinage (+ ville servie), comme la
    // maquette (« Villa Bennani — Casablanca »), le cartouche du schéma, « Montrer au client » et le plan PDF.
    await waitFor(() => expect(screen.getByTestId('cal-projet-titre').textContent).toBe('Toiture — bâtiment principal — Casablanca'))
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

  // Suites des écrans v2 (24/11) — la carte montrait à Panneaux les cotes, le contour or et l'onduleur (maquettes Main et
  // Électrique seulement) : la coque déclare l'étape au constructeur ; en Expert, aucune (tout comme avant).
  it('la coque déclare au constructeur l’étape montrée ; en Expert, aucune', async () => {
    const etapeAtelier = vi.fn()
    reinitialiserBoot({ etapeAtelier })
    amorcer()
    rendreCalepinage(CTX.calepinage.id)
    await screen.findByTestId('cal-coque')
    await waitFor(() => expect(etapeAtelier).toHaveBeenLastCalledWith('toit'))
    await userEvent.click(screen.getByTestId('cal-etape-panneaux'))
    await waitFor(() => expect(etapeAtelier).toHaveBeenLastCalledWith('panneaux'))
    await userEvent.click(screen.getByTestId('cal-etape-electrique'))
    await waitFor(() => expect(etapeAtelier).toHaveBeenLastCalledWith('electrique'))
    await userEvent.click(within(screen.getByTestId('cal-barre-projet')).getByRole('button', { name: 'Expert' }))
    await waitFor(() => expect(etapeAtelier).toHaveBeenLastCalledWith(null))
  })

  it('ACAL1727 — Résultats et Documents disent « Étape N sur 5 » et leur titre aux lecteurs d’écran, sans tête visible (maquettes v2)', async () => {
    amorcer()
    rendreCalepinage(CTX.calepinage.id)
    await screen.findByTestId('cal-coque')
    await userEvent.click(screen.getByTestId('cal-etape-resultats'))
    const tete = await screen.findByTestId('cal-plein-etape-tete')
    expect(tete).toHaveTextContent('Étape 4 sur 5')
    expect(tete).toHaveTextContent('Les résultats')
    // Maquettes v2 Resultats / Documents : aucune tête ni barre de progression visibles ; le rail porte l'étape active.
    expect(tete).toHaveClass('sr-only')
    expect(within(tete).queryByTestId('cal-progression-etapes')).toBeNull()
    expect(screen.getByTestId('cal-etape-resultats')).toHaveAttribute('aria-current', 'step')
    await userEvent.click(screen.getByTestId('cal-etape-documents'))
    await waitFor(() => expect(screen.getByTestId('cal-plein-etape-tete')).toHaveTextContent('Étape 5 sur 5'))
    expect(screen.getByTestId('cal-plein-etape-tete')).toHaveTextContent('Les documents')
    // Une étape à carte garde sa tête dans le panneau : aucune tête pleine largeur.
    await userEvent.click(screen.getByTestId('cal-etape-toit'))
    await waitFor(() => expect(screen.queryByTestId('cal-plein-etape-tete')).toBeNull())
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
    fireEvent.pointerDown(document.body) // ACAL1661 — le geste de l'utilisateur précède sa retouche
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
    fireEvent.pointerDown(document.body) // ACAL1661 — après un geste, regarder le soleil reste « pas une modification »
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

  it('T4-B4-009 — bandeau : le nom du calepinage, le même de l’ouverture à la fin (jamais le lead) ; la ligne dit la pose SERVIE (panneaux · kWc · onduleur), la même à toute étape et dans les deux modes', async () => {
    amorcer()
    const res = reponseContrat('calepinage', 'calepinage_resultat')
    calepinageApi.calepinages.resultat.mockResolvedValue(res)
    calepinageApi.calepinages.get.mockResolvedValue(reponseContrat('calepinage', 'calepinage_detail'))
    rendreCalepinage(CTX.calepinage.id)
    await screen.findByTestId('cal-coque')
    // Le titre : le nom du calepinage servi (+ ville), dès qu'il est lu — jamais « Calepinage N », jamais le nom du lead
    // qui arrivait ensuite par le détail et faisait CHANGER le bandeau en cours de séance.
    const NOM = 'Toiture — bâtiment principal — Casablanca'
    const vus = new Set()
    const veilleur = new MutationObserver(() => { const t = document.querySelector('[data-testid="cal-projet-titre"]')?.textContent; if (t) vus.add(t) })
    veilleur.observe(document.body, { subtree: true, childList: true, characterData: true })
    await waitFor(() => expect(screen.getByTestId('cal-projet-titre').textContent).toBe(NOM))
    await waitFor(() => expect(calepinageApi.calepinages.get).toHaveBeenCalled())
    const { total_modules: n } = res.data.pose
    const o = res.data.electrique.onduleurs[0]
    const kwc = res.data.pose.kwc.toLocaleString('fr-FR', { minimumFractionDigits: 2 })
    const ligne = `${n} panneaux · ${kwc} kWc · ${o.nombre} onduleur ${o.taille_kw} kW`
    await userEvent.click(screen.getByTestId('cal-etape-toit'))
    await waitFor(() => expect(screen.getByTestId('cal-projet-sous-titre').textContent).toBe(ligne))
    await userEvent.click(screen.getByTestId('cal-etape-documents'))
    await waitFor(() => expect(screen.getByTestId('cal-projet-sous-titre').textContent).toBe(ligne))
    await userEvent.click(within(screen.getByTestId('cal-barre-projet')).getByRole('button', { name: 'Expert' }))
    await waitFor(() => expect(screen.getByTestId('cal-coque')).toHaveAttribute('data-expert', '1'))
    expect(screen.getByTestId('cal-projet-sous-titre').textContent).toBe(ligne)
    expect(screen.getByTestId('cal-projet-titre').textContent).toBe(NOM)
    veilleur.disconnect()
    expect([...vus]).toEqual([NOM])
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

  it('ACAL1835 — tablette (640 à 1 279 px) : plus de tiroir, le panneau d’étape reste le panneau de droite', async () => {
    const avant = window.matchMedia
    const largeur = 1180
    window.matchMedia = (q) => {
      const max = /max-width:\s*(\d+)px/.exec(q)
      return { matches: max ? largeur <= Number(max[1]) : false, media: q, addEventListener() {}, removeEventListener() {} }
    }
    try {
      amorcer()
      rendreCalepinage(CTX.calepinage.id)
      const panneau = await screen.findByTestId('cal-panneau-etape')
      expect(panneau).not.toHaveAttribute('data-tiroir')
      expect(within(panneau).queryByRole('button', { name: 'Agrandir ou réduire le panneau du bas' })).toBeNull()
      expect(await within(panneau).findByTestId('cal-action-etape-suivante')).toHaveTextContent(/\S/)
    } finally { window.matchMedia = avant }
  })

  it('téléphone (< 640 px) : le panneau devient le tiroir du bas, poignée qui l’agrandit ; titre et pied dans le même tiroir', async () => {
    const avant = window.matchMedia
    window.matchMedia = (q) => ({ matches: q === '(max-width: 639px)', media: q, addEventListener() {}, removeEventListener() {} })
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

  it('ACAL1807 — téléphone (< 640 px), guidé : le tiroir s’ouvre RÉDUIT et la feuille lui donne 96 px, la carte garde ≥ 45 % de la hauteur', async () => {
    const avant = window.matchMedia
    window.matchMedia = (q) => ({ matches: q === '(max-width: 639px)', media: q, addEventListener() {}, removeEventListener() {} })
    const { readFileSync } = await import('node:fs')
    const style = document.createElement('style')
    style.textContent = readFileSync(`${globalThis.process.cwd()}/src/styles/calepinage/56-coque-responsive.css`, 'utf8')
    document.head.appendChild(style)
    try {
      amorcer()
      rendreCalepinage(CTX.calepinage.id)
      const panneau = await screen.findByTestId('cal-panneau-etape')
      // Par défaut : réduit (poignée, titre, bouton d'étape) ; la poignée l'ouvre en pleine hauteur et le referme.
      expect(panneau).toHaveAttribute('data-deplie', '0')
      const poignee = within(panneau).getByRole('button', { name: 'Agrandir ou réduire le panneau du bas' })
      expect(within(panneau).getByTestId('cal-panneau-etape-titre').textContent).not.toBe('')
      await userEvent.click(poignee)
      expect(panneau).toHaveAttribute('data-deplie', '1')
      await userEvent.click(poignee)
      expect(panneau).toHaveAttribute('data-deplie', '0')
      // La feuille : sous 640 px, le tiroir réduit du guidé mesure `--cal-tiroir` (96 px) et masque corps + contrôle.
      const mq = [...style.sheet.cssRules].find((r) => r.type === 4 && r.conditionText === '(max-width: 639px)')
      expect(mq, 'bloc téléphone de la feuille').toBeTruthy()
      const regles = [...mq.cssRules]
      const reduit = regles.find((r) => r.selectorText?.endsWith("[data-deplie='0']:not([hidden])") && r.style.height)
      expect(reduit.style.height).toBe('var(--cal-tiroir)')
      const cache = regles.find((r) => r.selectorText?.includes("[data-deplie='0'] :is(") && r.selectorText.includes('cal-panneau-etape-corps'))
      expect(cache.style.display).toBe('none')
      const variable = regles.find((r) => r.selectorText === ".cal-coque[data-expert='0']")
      const tiroir = Number.parseInt(variable.style.getPropertyValue('--cal-tiroir'), 10)
      expect(tiroir).toBe(96)
      // Arithmétique de la revue (390 × 664, bandeau + alertes = 168 px, rail de 64 px) : la carte visible ≥ 45 % de 664.
      expect(664 - 168 - 64 - tiroir).toBeGreaterThanOrEqual(0.45 * 664)
    } finally { style.remove(); window.matchMedia = avant }
  })

  // T4-X8-006 — « Avancé » au téléphone : la feuille du bas s'ouvre (Guidé ET Expert), ses liens se voient, Fermer la referme.
  // Les règles du bloc téléphone sont posées SANS leur @media (jsdom ne lit pas les requêtes de média).
  for (const expert of [false, true]) {
    it(`T4-X8-006 — téléphone, ${expert ? 'Expert' : 'Guidé'} : « Avancé » ouvre la feuille du bas, liens visibles`, async () => {
      const avant = window.matchMedia
      window.matchMedia = (q) => ({ matches: q === '(max-width: 639px)', media: q, addEventListener() {}, removeEventListener() {} })
      const { readFileSync } = await import('node:fs')
      const brut = document.createElement('style')
      brut.textContent = ['50-coque-atelier.css', '56-coque-responsive.css']
        .map((f) => readFileSync(`${globalThis.process.cwd()}/src/styles/calepinage/${f}`, 'utf8')).join('\n')
      document.head.appendChild(brut)
      const tel = [...brut.sheet.cssRules].filter((r) => r.type === 4 && r.conditionText === '(max-width: 639px)')
      const style = document.createElement('style')
      style.textContent = [...brut.sheet.cssRules].filter((r) => r.type !== 4).map((r) => r.cssText)
        .concat(tel.flatMap((m) => [...m.cssRules].map((r) => r.cssText))).join('\n')
      brut.remove()
      document.head.appendChild(style)
      if (expert) window.localStorage.setItem(clef, '1')
      try {
        amorcer()
        rendreCalepinage(CTX.calepinage.id)
        const coque = await screen.findByTestId('cal-coque')
        expect(coque).toHaveAttribute('data-expert', expert ? '1' : '0')
        expect(screen.getByTestId('cal-rail-avance')).toHaveAttribute('aria-expanded', 'false')
        await userEvent.click(screen.getByTestId('cal-rail-avance'))
        const feuille = await screen.findByRole('dialog', { name: 'Avancé' })
        expect(screen.getByTestId('cal-rail-avance')).toHaveAttribute('aria-expanded', 'true')
        for (const nom of ['Montrer au client', 'Relevé de visite', 'Photos du site']) {
          expect(within(feuille).getByRole('link', { name: nom })).toBeVisible()
        }
        // La feuille du bas : posée sur toute la largeur, au-dessus de la barre des étapes, coins hauts arrondis.
        const regle = tel.flatMap((m) => [...m.cssRules])
          .find((r) => r.selectorText === ".cal-coque[data-feuille='1'] .cal-coque-avance:not([hidden])")
        expect(regle?.style.bottom).toBe('var(--cal-rail-bas)')
        expect(regle?.style.left).toMatch(/^0(px)?$/)
        await userEvent.click(within(feuille).getByRole('button', { name: 'Fermer' }))
        await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Avancé' })).toBeNull())
      } finally { style.remove(); window.matchMedia = avant }
    })
  }

  it('ACAL1809 — le bandeau porte l’entrée de la visite : « Relevé » au doigt, « Montrer au client » à la souris, jamais les deux', async () => {
    const avant = window.matchMedia
    const poser = (doigt) => {
      window.matchMedia = (q) => ({ matches: doigt && q === '(pointer: coarse)', media: q, addEventListener() {}, removeEventListener() {} })
    }
    try {
      for (const [doigt, testid, absent, fin] of [[true, 'cal-barre-releve', 'cal-barre-montrer-client', 'releve'],
        [false, 'cal-barre-montrer-client', 'cal-barre-releve', 'client']]) {
        poser(doigt)
        amorcer()
        rendreCalepinage(CTX.calepinage.id)
        const entree = await screen.findByTestId(testid)
        expect(within(screen.getByTestId('cal-barre-projet')).getByTestId(testid)).toBe(entree)
        expect(entree.getAttribute('href')).toBe(`/calepinage/${CTX.calepinage.id}/${fin}`)
        expect(entree.textContent).toMatch(/\S/)
        expect(screen.queryByTestId(absent)).toBeNull()
        cleanup()
      }
    } finally { window.matchMedia = avant }
  })

  it('ACAL1801 — la carte est le décor : le toit se cadre dans la zone LIBRE, marges = boîtes du bandeau, du rail, du panneau et de la barre d’outils', async () => {
    const cadrerToit = vi.fn(() => true)
    reinitialiserBoot({ cadrerToit, appliquerVue: vi.fn() })
    // Les boîtes de la maquette v2 Main à 1 440 × 900 : carte plein écran, pièces flottantes à 16 px.
    const BOITES = {
      'rp9-map': [0, 0, 1440, 900], 'cal-barre-projet': [16, 16, 1424, 72], 'cal-rail-etapes': [16, 88, 92, 884],
      'rp9-studio-inspecteur': [1040, 88, 1424, 884], 'cal-barre-outils-carte': [330, 816, 760, 872],
    }
    const avant = Element.prototype.getBoundingClientRect
    Element.prototype.getBoundingClientRect = function boite() {
      const b = BOITES[this.id] ?? BOITES[this.getAttribute('data-testid')]
      if (!b) return avant.call(this)
      const [left, top, right, bottom] = b
      return { left, top, right, bottom, x: left, y: top, width: right - left, height: bottom - top }
    }
    try {
      amorcer()
      rendreCalepinage(CTX.calepinage.id)
      await screen.findByTestId('cal-coque')
      await userEvent.click(screen.getByTestId('cal-etape-toit'))
      await screen.findByTestId('cal-barre-outils-carte', {}, { timeout: 5000 })
      await waitFor(() => expect(cadrerToit).toHaveBeenCalledWith({
        zoomMax: 22, basPx: 56 + 28, margesPx: { haut: 72, gauche: 92, droite: 400, bas: 84 },
      }), { timeout: 6000 })
    } finally { Element.prototype.getBoundingClientRect = avant }
  }, 15000)

  describe('feuilles de la coque v2 chargées dans le DOM de test (ACAL1800, ACAL1801, ACAL1617)', () => {
    let style
    beforeEach(async () => {
      const { readFileSync } = await import('node:fs')
      style = document.createElement('style')
      style.textContent = ['roofbuilder.css', 'calepinage/49-jetons-v2.css', 'calepinage/50-coque-atelier.css',
        'calepinage/51-etape-toit.css', 'calepinage/56-coque-responsive.css']
        .map((f) => readFileSync(`${globalThis.process.cwd()}/src/styles/${f}`, 'utf8')).join('\n')
      document.head.appendChild(style)
    })
    afterEach(() => { style.remove(); document.documentElement.classList.remove('dark') })
    // Les règles de la COQUE FLOTTANTE (@media (min-width: 640px) — bureau, et tablette depuis ACAL1835 qui n'en
    // précise que les mesures dans son propre bloc) lues dans la feuille chargée (jsdom n'évalue pas @media) :
    // la dernière règle qui vise l'élément et déclare la propriété (ordre de la feuille).
    const auBureau = (el, prop, bureau = true) => {
      const regles = bureau ? [...style.sheet.cssRules].filter((r) => r.media && r.conditionText === '(min-width: 640px)')
        .flatMap((m) => [...m.cssRules]) : [...style.sheet.cssRules].filter((r) => r.selectorText)
      let valeur = ''
      for (const r of regles) {
        let vise = false
        try { vise = el.matches(r.selectorText) } catch { vise = false }
        if (vise && r.style.getPropertyValue(prop)) valeur = r.style.getPropertyValue(prop)
      }
      return valeur
    }

    it('ACAL1800 : les jetons v2 se lisent sur la coque rendue, en clair puis en sombre', async () => {
      amorcer()
      rendreCalepinage(CTX.calepinage.id)
      const coque = await screen.findByTestId('cal-coque')
      expect(getComputedStyle(coque).getPropertyValue('--cal-papier').trim()).toBe('rgb(245 244 240)') // #f5f4f0, écrit en rgb() dans la feuille
      expect(getComputedStyle(coque).getPropertyValue('--cal-actif').trim()).toBe('rgb(12 19 53)') // #0c1335
      document.documentElement.classList.add('dark')
      expect(getComputedStyle(coque).getPropertyValue('--cal-papier').trim()).toBe('rgb(10 15 42)') // #0a0f2a
      expect(getComputedStyle(coque).getPropertyValue('--cal-actif').trim()).toBe('rgb(226 181 74)') // #e2b54a
    })

    it('ACAL1801 : au bureau, carte plein écran sous le bandeau, le rail et le panneau qui flottent ; papier et pièces opaques sans carte', async () => {
      amorcer()
      rendreCalepinage(CTX.calepinage.id)
      const coque = await screen.findByTestId('cal-coque')
      const carte = screen.getByTestId('rp9-map-wrap')
      const barre = screen.getByTestId('cal-barre-projet')
      const rail = screen.getByTestId('cal-rail-etapes')
      const panneau = screen.getByTestId('cal-panneau-etape')
      expect(auBureau(carte, 'position')).toBe('fixed')
      expect(auBureau(carte, 'inset')).toBe('0px')
      expect(auBureau(coque, 'padding')).toBe('16px')
      expect(auBureau(barre, 'border-radius')).toBe('var(--cal-rayon-piece)')
      expect(auBureau(barre, 'background')).toBe('var(--cal-flottante)')
      expect(auBureau(rail, 'border-radius')).toBe('var(--cal-rayon-panneau)')
      expect(auBureau(panneau, 'border-radius')).toBe('var(--cal-rayon-panneau)')
      expect(auBureau(panneau, 'box-shadow')).toBe('var(--cal-ombre-panneau)')
      expect(getComputedStyle(rail).width).toBe('76px')
      expect(getComputedStyle(panneau).width).toBe('384px')
      // Le calque « sur la carte » reste dans la zone libre (débord de la marge commune seulement).
      expect(auBureau(document.querySelector('.cal-coque-sur-carte'), 'inset')).toBe('-16px')
      // Étape sans carte (Résultats) : papier, pièces opaques, carte non posée en décor.
      await userEvent.click(screen.getByTestId('cal-etape-resultats'))
      await waitFor(() => expect(coque).toHaveAttribute('data-cadre', 'plein'))
      expect(getComputedStyle(coque).background).toContain('--cal-papier')
      expect(auBureau(barre, 'background')).toBe('')
      expect(getComputedStyle(barre).background).toContain('--cal-surface')
      expect(auBureau(carte, 'position')).toBe('')
      // Expert : la carte reste dans le centre (rangées du constructeur sous la carte).
      await userEvent.click(screen.getByTestId('cal-etape-toit'))
      await userEvent.click(within(barre).getByRole('button', { name: 'Expert' }))
      await waitFor(() => expect(coque).toHaveAttribute('data-expert', '1'))
      expect(auBureau(carte, 'position')).toBe('')
    })

    it('ACAL1802 : bleu nuit sur tout état actif, l’or sur la SEULE action suivante, un seul style « choisi » ; Expert compris', async () => {
      amorcer()
      rendreCalepinage(CTX.calepinage.id)
      const coque = await screen.findByTestId('cal-coque')
      await userEvent.click(screen.getByTestId('cal-etape-toit'))
      const pied = await screen.findByTestId('cal-action-etape-suivante')
      const cs = (el) => getComputedStyle(el)
      const etape = screen.getByTestId('cal-etape-toit')
      expect(etape).toHaveAttribute('aria-current', 'step')
      expect(cs(etape).background).toContain('--cal-actif')
      expect(cs(etape).color).toContain('--cal-actif-texte')
      expect(cs(etape).boxShadow).not.toContain('--primary')
      expect(cs(screen.getByTestId('cal-generer-devis-haut')).background).toContain('--cal-marine')
      expect(cs(screen.getByTestId('cal-generer-devis-haut')).borderRadius).toBe('var(--cal-rayon-bouton)')
      // Le bouton enfoncé du constructeur et une tuile choisie, posés dans la coque rendue.
      const poser = (html) => { const t = document.createElement('div'); t.innerHTML = html; coque.appendChild(t); return t.firstChild }
      const rp9 = poser('<button class="rp9-btn" aria-pressed="true">Obstacle polygonal</button>')
      expect(cs(rp9).background).toContain('--cal-actif')
      expect(cs(rp9).borderRadius).toBe('var(--cal-rayon-bouton)')
      expect(cs(poser('<input class="rp9-input">')).borderRadius).toBe('var(--cal-rayon-champ)')
      const tuile = poser('<button class="cal-tuile" aria-pressed="true">2 pans</button>')
      // (jsdom ne rend pas une couleur de bordure en var() : la règle qui s'applique est lue dans la feuille chargée)
      expect(auBureau(tuile, 'border-color', false)).toBe('var(--cal-choisi-filet)')
      expect(auBureau(tuile, 'border-width', false)).toBe('2px')
      expect(cs(tuile).background).toContain('--cal-choisi-fond')
      expect(cs(tuile).boxShadow, 'plus de liseré doré sur la tuile choisie').not.toContain('--primary')
      // UN seul aplat doré à l'écran : le bouton d'étape.
      const dores = () => [...coque.querySelectorAll('button')]
        .filter((b) => !b.closest('[hidden]') && cs(b).background.includes('--cal-action'))
      expect(dores()).toEqual([pied])
      // Expert : aucun bouton d'étape, donc aucun aplat doré ; l'étape active reste bleu nuit.
      await userEvent.click(within(screen.getByTestId('cal-barre-projet')).getByRole('button', { name: 'Expert' }))
      await waitFor(() => expect(coque).toHaveAttribute('data-expert', '1'))
      expect(dores()).toEqual([])
      expect(cs(screen.getByTestId('cal-etape-toit')).background).toContain('--cal-actif')
    })

    it('ACAL1804 : barre d’outils, pile de zoom, pilule de chiffres et bulle de consigne au langage v2 (étape Toit)', async () => {
      amorcer()
      rendreCalepinage(CTX.calepinage.id)
      const coque = await screen.findByTestId('cal-coque')
      await userEvent.click(screen.getByTestId('cal-etape-toit'))
      const outils = await screen.findByTestId('cal-barre-outils-carte')
      // La pilule n'a pas de chiffres dans ce harnais (aucune surface tracée) : celle de l'écran, posée telle qu'il la rend.
      const pilule = document.createElement('div')
      pilule.className = 'cal-carte-flottante cal-sur-carte-resume'
      pilule.setAttribute('data-testid', 'cal-sur-carte-resume')
      coque.querySelector('.cal-coque-sur-carte').appendChild(pilule)
      const cs = (el) => getComputedStyle(el)
      const zoomHote = document.createElement('div')
      zoomHote.className = 'maplibregl-ctrl-top-right'
      zoomHote.innerHTML = '<div class="maplibregl-ctrl maplibregl-ctrl-group"><button class="maplibregl-ctrl-zoom-in"></button></div>'
      screen.getByTestId('rp9-map-wrap').appendChild(zoomHote)
      const zoom = zoomHote.firstChild
      // Barre d'outils : 56 px, rayon 18, ombre de la barre, à 28 px du bas au bureau ; outils 44 × 44.
      expect(cs(outils).height).toBe('56px')
      expect(cs(outils).borderRadius).toBe('var(--cal-rayon-outils)')
      expect(cs(outils).boxShadow).toBe('var(--cal-ombre-outils)')
      expect(cs(outils).background).toContain('--cal-flottante-dense')
      expect(auBureau(outils, 'bottom')).toBe('28px')
      for (const b of outils.querySelectorAll('.cal-outil-carte')) {
        expect([cs(b).width, cs(b).height]).toEqual(['44px', '44px'])
      }
      // Pile de zoom : rayon 14 (le haut, collé au plein écran en guidé), blanc 90 % flouté, ombre flottante.
      expect(cs(zoom).borderRadius).toContain('var(--cal-rayon-pile)')
      expect(cs(zoom).boxShadow).toBe('var(--cal-ombre-flottante)')
      expect(cs(zoom).background).toContain('--cal-flottante-dense')
      // Pilule : rayon 16, blanc 90 %, 62 px, à 16 px du rail et du bandeau.
      expect(cs(pilule).borderRadius).toBe('var(--cal-rayon-piece)')
      expect(cs(pilule).boxShadow).toBe('var(--cal-ombre-flottante)')
      expect(cs(pilule).height).toBe('62px')
      expect([auBureau(pilule, 'top'), auBureau(pilule, 'left')]).toEqual(['16px', '16px'])
      // Bulle de consigne : bleu nuit, texte clair, ombre flottante ; la pilule se pose après elle.
      const bulle = document.createElement('div')
      bulle.className = 'cal-toit-bulle'
      bulle.innerHTML = '<p class="cal-toit-bulle-titre">Contour tracé</p>'
      coque.querySelector('.cal-coque-sur-carte').appendChild(bulle)
      expect(cs(bulle).background).toContain('--cal-bulle')
      expect(cs(bulle).color).toBe('var(--cal-bulle-titre)')
      expect(cs(bulle).boxShadow).toBe('var(--cal-ombre-flottante)')
      expect(cs(bulle).borderRadius).toBe('var(--cal-rayon-piece)')
      expect(auBureau(pilule, 'left'), '16 + 296 (bulle) + 16').toBe('calc(328px)')
    })

    it('ACAL1617 : Expert, étape Résultats — le panneau prend la largeur utile, la carte passe dessous ; Toit garde 384 px', async () => {
      amorcer()
      rendreCalepinage(CTX.calepinage.id)
      const coque = await screen.findByTestId('cal-coque')
      await userEvent.click(within(screen.getByTestId('cal-barre-projet')).getByRole('button', { name: 'Expert' }))
      await waitFor(() => expect(coque).toHaveAttribute('data-expert', '1'))
      const panneau = screen.getByTestId('cal-panneau-etape')
      const centre = document.querySelector('.cal-coque-centre')
      expect(auBureau(panneau, 'flex')).toBe('')
      await userEvent.click(screen.getByTestId('cal-etape-resultats'))
      await waitFor(() => expect(coque).toHaveAttribute('data-etape', 'resultats'))
      expect(coque).toHaveAttribute('data-cadre', 'carte')
      expect(auBureau(panneau, 'flex')).toBe('1 1 auto')
      expect(auBureau(panneau, 'width')).toBe('auto')
      expect(auBureau(centre, 'position')).toBe('absolute')
      expect(document.getElementById('rp9-map')).not.toBeNull()
    })
  })
})
