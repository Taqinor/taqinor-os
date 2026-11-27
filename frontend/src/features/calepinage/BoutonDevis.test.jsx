import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { useEffect, useState } from 'react'
import userEvent from '@testing-library/user-event'
import { exempleContrat } from '../../test/fixtures/contractSamples'

/* CAL38 — les TROIS issues du pont vers le devis (création, 422 de
   composition, 409 « devis envoyé »), et la preuve qu'AUCUNE ne fabrique de
   texte côté client : la phrase affichée est celle du corps de réponse.

   PACT13 — l'état du calepinage vient de l'exemple COMMITTÉ
   (`apps/calepinage/contract_samples/calepinage_detail.json`), jamais d'un
   objet tapé à la main. */

vi.mock('../../api/calepinageApi', () => ({
  default: { calepinages: { genererDevis: vi.fn(), syncDevis: vi.fn(), apercuDevis: vi.fn(), apercuResync: vi.fn() } },
}))
vi.mock('../../api/ventesApi', () => ({
  default: { reviserDevis: vi.fn() },
}))
const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigateMock }
})

import calepinageApi from '../../api/calepinageApi'
import ventesApi from '../../api/ventesApi'
import BoutonDevis, {
  MESSAGE_APERCU_FERME, MESSAGE_APERCU_RELU, MESSAGE_BROUILLON_MIS_A_JOUR, MESSAGE_RIEN_A_CHANGER,
  MESSAGE_VERIFICATION_A_LA_CONFIRMATION,
} from './BoutonDevis'
import { ecouterDevisGenere, oublierIssuesDevis } from './atelier/contexteAtelier'

const DETAIL = exempleContrat('calepinage', 'calepinage_detail')
const DETAIL_VIDE = exempleContrat('calepinage', 'calepinage_detail',
  'exemple_vide')

/* L'agrégat de détail arrive en PROP : il est lu UNE fois par
   `AtelierPanneaux` et descendu ici (une seule lecture, une seule vérité). */
function rendre(props = {}) {
  return render(
    <MemoryRouter>
      <BoutonDevis calepinageId={DETAIL.id} detail={DETAIL} {...props} />
    </MemoryRouter>,
  )
}

// ACAL1402/1414 — l'exemple dit le choix du devis lié (`chiffree` vrai/faux) ; les cas ACAL915/968 partent d'un
// devis sans sélection écrite (`chiffree: null`) : tout est coché à l'ouverture.
const SURFACES_SANS_SELECTION = DETAIL.surfaces_chiffrables.map((s) => ({ ...s, chiffree: null }))
const DETAIL_SANS_SELECTION = { ...DETAIL, surfaces_chiffrables: SURFACES_SANS_SELECTION }

/* ACAL1320 (D-ACAL-73) — « Resynchroniser le devis » lit d'abord l'aperçu servi (contrat
   `calepinage_apercu_resync.json`) puis attend la confirmation ; par défaut, l'exemple committé (un devis
   envoyé qui change). */
const APERCU_RESYNC = exempleContrat('calepinage', 'calepinage_apercu_resync')

async function resynchroniserEtConfirmer() {
  await userEvent.click(await screen.findByTestId('cal-resynchroniser-devis'))
  await userEvent.click(await screen.findByTestId('cal-devis-resync-confirmer'))
}

beforeEach(() => {
  vi.clearAllMocks()
  oublierIssuesDevis() // ACAL1946 — l'issue retenue d'un test ne déborde pas sur le suivant
  calepinageApi.calepinages.apercuResync.mockResolvedValue({ data: APERCU_RESYNC })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

/* ACAL2002 — un seul bouton doré : « Générer le devis » n'est le bouton d'étape v2 que là où il EST l'action de l'étape
   (Documents en Guidé) ; ailleurs il reste à filet (ACAL1802 : l'or sur la seule action suivante). Les jetons du bouton
   doré sont lus par les tests de la coque et du Démarrage rapide. */
describe('ACAL2002 — « Générer le devis » est le bouton doré v2 quand il est l’action de l’étape', () => {
  it('action de l’étape : classes du bouton d’étape ; hors étape : bouton à filet, jamais doré', async () => {
    const vue = rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE, actionEtape: true })
    expect(await screen.findByTestId('cal-generer-devis')).toHaveClass('cal-bouton-or', 'cal-bouton-or-grand')
    vue.unmount()
    rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE })
    expect(await screen.findByTestId('cal-generer-devis')).not.toHaveClass('cal-bouton-or')
  })
})

/* Demande croisée de la lane Documents (24/11) — à l'étape Documents (action de l'étape) les surfaces chiffrées tiennent sur
   UNE ligne qui se déplie (la liste des contrôles ne défile plus dans la carte), et la flèche du bouton doré est un
   pictogramme passé par `fleche`, plus un `::after` de feuille. Ailleurs (Expert) : la forme dépliée d'avant. */
describe('Documents — forme compacte des surfaces et flèche du bouton doré', () => {
  it('action de l’étape : surfaces repliées sur une ligne (la phrase servie), cases dans le dépli ; flèche dans le bouton', async () => {
    const vue = rendre({ detail: DETAIL_SANS_SELECTION, actionEtape: true })
    const repli = screen.getByTestId('cal-devis-surfaces')
    expect(repli.tagName).toBe('DETAILS')
    expect(repli.open).toBe(false)
    const surfaces = DETAIL.surfaces_chiffrables
    expect(within(repli).getByText(/^Le devis chiffre :/)).toHaveTextContent(
      `= ${surfaces.reduce((t, s) => t + s.modules, 0)} modules`)
    expect(within(repli).getAllByRole('checkbox', { hidden: true })).toHaveLength(surfaces.length)
    expect(screen.getByTestId('cal-resynchroniser-devis').querySelector('svg')).not.toBeNull()
    vue.unmount()
    rendre({ detail: DETAIL_SANS_SELECTION })
    expect(screen.queryByTestId('cal-devis-surfaces')).toBeNull()
    expect(screen.getByTestId('cal-resynchroniser-devis').querySelector('svg')).toBeNull()
  })

  it('« Cochez au moins une surface » reste visible, même replié', async () => {
    rendre({ detail: DETAIL_SANS_SELECTION, actionEtape: true })
    for (const c of screen.getAllByRole('checkbox', { hidden: true })) await userEvent.click(c)
    const alerte = screen.getByText('Cochez au moins une surface')
    expect(screen.getByTestId('cal-devis-surfaces').contains(alerte)).toBe(false)
  })
})

// T4-X5-007 — l'écran dit lui-même chaque refus : le toast global est coupé sur generer-devis / sync-devis.
const SANS_TOAST = { suppressErrorToast: true }

/* Lane E9 (T4-X5-010) — avant « Générer le devis », ce que le devis PORTERA (dry-run servi, mot pour mot). */
describe('Lane E9 — le matériel que le devis portera, dit avant le bouton', () => {
  it('par option : module et onduleur servis, puis la phrase de l’écart à la désignation électrique', async () => {
    const apercu = exempleContrat('calepinage', 'calepinage_apercu_devis')
    calepinageApi.calepinages.apercuDevis.mockResolvedValue({ data: apercu })
    rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE })
    const bloc = await screen.findByText('Le devis portera :')
    const zone = bloc.closest('[data-zone="apercu-materiel-devis"]')
    expect(within(zone).getByText('Sans batterie : module Module 710 Wc · onduleur Onduleur réseau 6 kW')).toBeInTheDocument()
    expect(within(zone).getByText('Avec batterie : module Module 710 Wc · onduleur Onduleur hybride 6 kW')).toBeInTheDocument()
    expect(within(zone).getByText(apercu.ecarts[0].message)).toHaveAttribute('role', 'status')
    expect(calepinageApi.calepinages.apercuDevis).toHaveBeenCalledWith(DETAIL_VIDE.id, undefined)
    // Placé AVANT le bouton « Générer le devis ».
    const bouton = screen.getByTestId('cal-generer-devis')
    expect(zone.compareDocumentPosition(bouton) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('lane E9b — le brouillon que le bouton ouvrirait : son matériel et une phrase qui le dit', async () => {
    const brouillon = exempleContrat('calepinage', 'calepinage_apercu_devis', 'exemple_brouillon')
    calepinageApi.calepinages.apercuDevis.mockResolvedValue({ data: brouillon })
    rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE })
    expect(await screen.findByText(`Un devis brouillon existe déjà (${brouillon.reference}) : le bouton l’ouvre.`))
      .toBeInTheDocument()
  })

  it('lane E9b — les surfaces cochées partent avec l’aperçu, comme avec « Générer »', async () => {
    const surfaces = DETAIL.surfaces_chiffrables.map((s) => ({ ...s, chiffree: null }))
    const detail = { ...DETAIL_VIDE, surfaces_chiffrables: surfaces }
    calepinageApi.calepinages.apercuDevis.mockResolvedValue({ data: exempleContrat('calepinage', 'calepinage_apercu_devis') })
    rendre({ calepinageId: detail.id, detail })
    await waitFor(() => expect(calepinageApi.calepinages.apercuDevis).toHaveBeenCalledWith(detail.id, undefined))
    const toit = surfaces.find((s) => s.kind === 'toit')
    await userEvent.click(screen.getByRole('checkbox', { name: new RegExp(toit.libelle) }))
    const restantes = surfaces.filter((s) => s.cle !== toit.cle).map((s) => s.cle).join(',')
    await waitFor(() => expect(calepinageApi.calepinages.apercuDevis)
      .toHaveBeenLastCalledWith(detail.id, { params: { surfaces: restantes } }))
  })

  it('rien ne se compose (refus servi) : rien n’est affirmé', async () => {
    calepinageApi.calepinages.apercuDevis.mockResolvedValue({
      data: exempleContrat('calepinage', 'calepinage_apercu_devis', 'exemple_refus') })
    rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE })
    await screen.findByTestId('cal-generer-devis')
    await waitFor(() => expect(calepinageApi.calepinages.apercuDevis).toHaveBeenCalled())
    expect(screen.queryByText('Le devis portera :')).toBeNull()
  })
})

describe('BoutonDevis (CAL38)', () => {
  it('détail absent (agrégat pas encore lu) : aucun bouton deviné', async () => {
    rendre({ detail: null })
    expect(screen.queryByTestId('cal-bouton-devis')).toBeNull()
  })

  it('sans devis lié : génère, puis la carte « Devis … créé » ouvre le VRAI devis', async () => {
    // `exemple_vide` du contrat : aucun devis, aucune variante.
    calepinageApi.calepinages.genererDevis.mockResolvedValue({
      data: { devis: 42, reference: 'DEV-2609-0042', deduplique: false },
    })

    rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE })
    await userEvent.click(await screen.findByTestId('cal-generer-devis'))

    await waitFor(() => expect(calepinageApi.calepinages.genererDevis)
      .toHaveBeenCalledWith(DETAIL_VIDE.id, {}, SANS_TOAST))
    expect(navigateMock).not.toHaveBeenCalled() // ACAL866 : plus de navigation immédiate
    expect(await screen.findByTestId('cal-devis-cree')).toHaveTextContent('Devis DEV-2609-0042 créé')
    expect(screen.getByTestId('cal-devis-ouvrir')).toHaveAttribute('href', '/ventes/devis?devis=42')
    // Jamais l'autre geste : un calepinage sans devis ne « resynchronise » rien.
    expect(screen.queryByTestId('cal-resynchroniser-devis')).toBeNull()
  })

  it('refus 409 de pré-vol : le message du SERVEUR s’affiche, sous le champ qu’il nomme', async () => {
    const MESSAGE = 'Le catalogue ne porte aucun panneau avec un prix : '
      + 'complétez-le avant de chiffrer.'
    calepinageApi.calepinages.genererDevis.mockRejectedValue({
      response: { status: 409, data: { detail: MESSAGE, errors: [MESSAGE] } },
    })

    rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE })
    await userEvent.click(await screen.findByTestId('cal-generer-devis'))

    const bloc = await screen.findByTestId('cal-devis-refus')
    expect(bloc).toHaveTextContent(MESSAGE)
    // Le champ est NOMMÉ en français ; le message n'est pas réécrit.
    expect(bloc).toHaveTextContent('Devis')
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it('devis lié : resynchronise, et le 409 offre la révision sans rien inventer', async () => {
    const DETAIL_409 = 'Ce devis est déjà parti chez le client : créez une '
      + 'révision pour le modifier.'
    calepinageApi.calepinages.syncDevis.mockRejectedValue({
      response: {
        status: 409,
        data: { detail: DETAIL_409, revision_possible: true },
      },
    })
    ventesApi.reviserDevis.mockResolvedValue({ data: { id: 77 } })

    rendre()
    // L'état SERVEUR décide du geste : un devis lié ⇒ « Resynchroniser ».
    await resynchroniserEtConfirmer()

    const conflit = await screen.findByTestId('cal-devis-conflit')
    expect(conflit).toHaveTextContent(DETAIL_409)
    expect(screen.queryByTestId('cal-devis-refus')).toBeNull()

    await userEvent.click(screen.getByTestId('cal-devis-reviser'))
    await waitFor(() => expect(ventesApi.reviserDevis)
      .toHaveBeenCalledWith(DETAIL.devis.id))
    expect(navigateMock).toHaveBeenCalledWith('/ventes/devis/77/design')
  })

  it('409 sans révision possible : le motif s’affiche, aucun bouton « Réviser »', async () => {
    calepinageApi.calepinages.syncDevis.mockRejectedValue({
      response: {
        status: 409,
        data: { detail: 'Ce devis est clos.', revision_possible: false },
      },
    })

    rendre()
    await resynchroniserEtConfirmer()

    expect(await screen.findByTestId('cal-devis-conflit'))
      .toHaveTextContent('Ce devis est clos.')
    expect(screen.queryByTestId('cal-devis-reviser')).toBeNull()
  })

  it('variantes présentes mais aucune retenue : bouton désactivé ET expliqué', async () => {
    rendre({
      calepinageId: DETAIL_VIDE.id,
      detail: {
        ...DETAIL_VIDE,
        variantes: { total: 3, retenue_id: null, non_simulees: 0 },
      },
    })

    const bouton = await screen.findByTestId('cal-generer-devis')
    expect(bouton).toBeDisabled()
    expect(screen.getByTestId('cal-devis-variante-manquante'))
      .toHaveTextContent('Choisissez d’abord une variante retenue.')
    await userEvent.click(bouton)
    expect(calepinageApi.calepinages.genererDevis).not.toHaveBeenCalled()
  })

  it('une variante EST retenue : le bouton est actif', async () => {
    expect(DETAIL.variantes.retenue_id).toBeTruthy()

    rendre()

    expect(await screen.findByTestId('cal-resynchroniser-devis')).toBeEnabled()
    expect(screen.queryByTestId('cal-devis-variante-manquante')).toBeNull()
  })

  it('lecture seule : aucun bouton d’écriture n’est rendu', async () => {
    rendre({ lectureSeule: true })

    expect(screen.queryByTestId('cal-bouton-devis')).toBeNull()
  })

  // ACAL93 — en lecture seule, « Réviser (v2) » reste OFFERT quand le serveur
  // le dit possible (jamais masqué) ; aucun geste d'écriture n'apparaît.
  it('lecture seule + revision_possible : seul « Réviser (v2) » est offert', async () => {
    ventesApi.reviserDevis.mockResolvedValue({ data: { id: 81, reference: 'DEV-V2' } })
    rendre({ lectureSeule: true, revisionPossible: true })

    const bouton = await screen.findByTestId('cal-devis-reviser-lecture-seule')
    expect(screen.queryByTestId('cal-resynchroniser-devis')).toBeNull()
    expect(screen.queryByTestId('cal-generer-devis')).toBeNull()
    await userEvent.click(bouton)
    await waitFor(() => expect(ventesApi.reviserDevis).toHaveBeenCalledWith(DETAIL.devis.id))
    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith('/ventes/devis/81/design'))
  })

  // T4-X7-016 — le geste nomme la version SUIVANTE (jamais « (v2) » sur une V2) et un échec se dit sous le bouton.
  it('lecture seule : « Réviser (nouvelle version) », et un refus du serveur dit pourquoi sous le bouton', async () => {
    ventesApi.reviserDevis.mockRejectedValue({ response: { status: 409, data: {
      code: 'version_remplacee', detail: 'Ce devis a déjà une version plus récente.',
      successeur: { id: 90, reference: 'DEV-V3' } } } })
    rendre({ lectureSeule: true, revisionPossible: true })

    const bouton = await screen.findByTestId('cal-devis-reviser-lecture-seule')
    expect(bouton).toHaveTextContent('Réviser (nouvelle version)')
    expect(bouton).not.toHaveTextContent('(v2)')
    await userEvent.click(bouton)
    const refus = await screen.findByTestId('cal-devis-reviser-refus')
    expect(refus).toHaveTextContent('Ce devis a déjà une version plus récente.')
    expect(within(refus).getByRole('link', { name: 'Ouvrir DEV-V3' })).toHaveAttribute('href', '/ventes/devis?devis=90')
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it('lecture seule : un échec sans motif nommé dit que rien n’a été créé', async () => {
    ventesApi.reviserDevis.mockRejectedValue({ response: { status: 500, data: {} } })
    rendre({ lectureSeule: true, revisionPossible: true })

    await userEvent.click(await screen.findByTestId('cal-devis-reviser-lecture-seule'))
    expect(await screen.findByTestId('cal-devis-reviser-refus'))
      .toHaveTextContent('La nouvelle version n’a pas été créée')
  })
})

/* ACAL95 — ce que la génération et la resynchro n'ont pas pu faire se LIT
   avant de naviguer ou de recharger. Charges : l'échantillon COMMITTÉ
   `calepinage_publication.json` (PACT13). */
describe('BoutonDevis — retour du serveur (ACAL95)', () => {
  const PUBLICATION = exempleContrat('calepinage', 'calepinage_publication')
  const SYNC = exempleContrat('calepinage', 'calepinage_publication', 'sync_devis')

  it('resynchro : avertissements et lignes ajoutées affichés', async () => {
    const onRecharger = vi.fn()
    const onRelire = vi.fn()
    calepinageApi.calepinages.syncDevis.mockResolvedValue({
      data: { ...SYNC.exemple, lignes_ajoutees: 1 },
    })

    rendre({ onRecharger, onRelire })
    await resynchroniserEtConfirmer()

    const bloc = await screen.findByTestId('cal-devis-avertissements')
    expect(bloc).toHaveTextContent(SYNC.exemple.avertissements[0])
    expect(bloc).toHaveTextContent('1 ligne ajoutée au devis')
    // Le rechargement complet attend « J'ai lu ».
    expect(onRecharger).not.toHaveBeenCalled()
    await userEvent.click(screen.getByTestId('cal-devis-j-ai-lu'))
    await waitFor(() => expect(onRecharger).toHaveBeenCalledTimes(1))
    expect(onRelire).toHaveBeenCalledTimes(1)
  })

  it('génération avec avertissements : pas de navigation immédiate', async () => {
    calepinageApi.calepinages.genererDevis.mockResolvedValue({ data: PUBLICATION })

    rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE })
    await userEvent.click(await screen.findByTestId('cal-generer-devis'))

    const bloc = await screen.findByTestId('cal-devis-avertissements')
    expect(bloc).toHaveTextContent(PUBLICATION.marques_manquantes[0])
    // T4-X7-008 — l'avertissement de composition se lit SUR la carte, hors du repli technicien.
    const alertes = screen.getByTestId('cal-devis-alertes')
    expect(alertes).toHaveTextContent(PUBLICATION.avertissements[0])
    expect(alertes.closest('details')).toBeNull()
    expect(bloc).not.toHaveTextContent(PUBLICATION.avertissements[0])
    expect(navigateMock).not.toHaveBeenCalled()
    expect(screen.getByTestId('cal-devis-ouvrir'))
      .toHaveAttribute('href', `/ventes/devis?devis=${PUBLICATION.devis}`)
    // ACAL866 — la référence servie, et les lignes techniques REPLIÉES.
    expect(screen.getByTestId('cal-devis-cree')).toHaveTextContent(`Devis ${PUBLICATION.reference} créé`)
    const details = screen.getByTestId('cal-devis-details-technicien')
    expect(details.tagName).toBe('DETAILS')
    expect(details).not.toHaveAttribute('open')
    expect(details).toHaveTextContent('Détails pour le technicien')
  })

  it('inchangé : Aucun changement', async () => {
    const onRecharger = vi.fn()
    calepinageApi.calepinages.syncDevis.mockResolvedValue({ data: SYNC.exemple_inchange })

    rendre({ onRecharger })
    await resynchroniserEtConfirmer()

    expect(await screen.findByTestId('cal-devis-avertissements'))
      .toHaveTextContent('Aucun changement')
    expect(onRecharger).not.toHaveBeenCalled()
  })

  it('ACAL866 — génération propre : même carte, aucune navigation vers /design, référence absente ⇒ « Devis créé »', async () => {
    calepinageApi.calepinages.genererDevis.mockResolvedValue({
      data: { ...PUBLICATION, avertissements: [], marques_manquantes: [] },
    })

    rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE })
    await userEvent.click(await screen.findByTestId('cal-generer-devis'))

    expect(await screen.findByTestId('cal-devis-cree')).toHaveTextContent(`Devis ${PUBLICATION.reference} créé`)
    expect(navigateMock).not.toHaveBeenCalled()
    expect(screen.queryByTestId('cal-devis-details-technicien')).toBeNull()
    expect(screen.getByTestId('cal-devis-ouvrir'))
      .toHaveAttribute('href', `/ventes/devis?devis=${PUBLICATION.devis}`)
  })

  it('ACAL866 — référence absente : « Devis créé » sans référence inventée', async () => {
    const { reference: _r, ...sansReference } = PUBLICATION
    calepinageApi.calepinages.genererDevis.mockResolvedValue({
      data: { ...sansReference, avertissements: [], marques_manquantes: [] },
    })
    rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE })
    await userEvent.click(await screen.findByTestId('cal-generer-devis'))
    expect((await screen.findByTestId('cal-devis-cree')).textContent).toMatch(/^Devis créé/)
  })
})

/* ACAL923 — le 409 `confirmation_taille` d'ACAL922 (rien ne dimensionne le
   devis) pose la QUESTION au lieu du cadre « devis figé » ; « Confirmer et
   générer » relance le même geste avec `confirmer_taille: true`. */
describe('BoutonDevis — confirmation de taille (ACAL923)', () => {
  const QUESTION = exempleContrat('calepinage', 'calepinage_publication',
    'exemple_409_confirmation_taille')
  const CORPS = exempleContrat('calepinage', 'calepinage_publication', 'corps_confirmer_taille')

  it('409 confirmation_taille ⇒ question, second POST avec confirmer_taille: true', async () => {
    calepinageApi.calepinages.genererDevis
      .mockRejectedValueOnce({ response: { status: 409, data: QUESTION } })
      .mockResolvedValueOnce({ data: { devis: 43, reference: 'DEV-2611-0043', deduplique: false } })
    rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE })
    await userEvent.click(await screen.findByTestId('cal-generer-devis'))

    const encadre = await screen.findByTestId('cal-devis-confirmation-taille')
    expect(encadre).toHaveTextContent(QUESTION.detail)
    expect(screen.queryByTestId('cal-devis-conflit')).toBeNull()
    expect(within(encadre).getByRole('link', { name: 'Renseigner la facture du lead' }))
      .toHaveAttribute('href', `/crm/leads/${DETAIL_VIDE.lead.id}`)

    await userEvent.click(within(encadre).getByRole('button', { name: 'Confirmer et générer' }))
    await waitFor(() => expect(calepinageApi.calepinages.genererDevis)
      .toHaveBeenLastCalledWith(DETAIL_VIDE.id, CORPS, SANS_TOAST))
    expect(await screen.findByTestId('cal-devis-cree')).toHaveTextContent('Devis DEV-2611-0043 créé')
    expect(screen.queryByTestId('cal-devis-confirmation-taille')).toBeNull()
  })

  // ACAL1738 — lead sans facture : la consigne est dite UNE fois, dans le cadre « Confirmer et générer » (la phrase
  // du serveur et le lien « Renseigner la facture du lead ») ; la sous-ligne du refus ne la répète plus.
  it('ACAL1738 — la consigne n’apparaît qu’une fois', async () => {
    calepinageApi.calepinages.genererDevis.mockRejectedValueOnce({ response: { status: 409, data: QUESTION } })
    const { container } = rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE })
    await userEvent.click(await screen.findByTestId('cal-generer-devis'))
    const encadre = await screen.findByTestId('cal-devis-confirmation-taille')
    expect(encadre).toHaveTextContent(QUESTION.detail)
    expect(container.textContent.match(/renseignez la facture/gi)).toHaveLength(1)
    expect(screen.queryByText(QUESTION.refus)).toBeNull()
  })
})

/* ACAL94 — Générer / Resynchroniser enregistrent d'abord l'ÉCRAN (une seule
   fonction d'enregistrement, prop `enregistrerAvant`) ; un échec n'envoie rien
   et ne recharge rien ; Réviser avertit des retouches non enregistrées sans
   jamais refuser. */
describe('BoutonDevis — enregistrer avant le geste (ACAL94)', () => {
  it('Resynchroniser enregistre l’écran avant sync-devis', async () => {
    const ordre = []
    const enregistrerAvant = vi.fn(async () => { ordre.push('enregistrer'); return true })
    calepinageApi.calepinages.syncDevis.mockImplementation(async () => {
      ordre.push('sync-devis')
      return { data: { inchange: false, lignes_ajoutees: 0, avertissements: [] } }
    })
    const onRecharger = vi.fn(async () => { ordre.push('recharger') })

    rendre({ enregistrerAvant, onRecharger })
    await resynchroniserEtConfirmer()

    await waitFor(() => expect(onRecharger).toHaveBeenCalledTimes(1))
    expect(ordre).toEqual(['enregistrer', 'sync-devis', 'recharger'])
  })

  // ACAL311 (rejeu P5.5) — avant l'hydratation de la scène, l'enregistrement refuserait :
  // le geste attend (bouton inactif) au lieu d'échouer sur « n'a pas pu être enregistrée ».
  it('atelier pas encore hydraté : bouton inactif, rien n’est enregistré', async () => {
    const enregistrerAvant = vi.fn(async () => true)
    const { rerender } = rendre({ enregistrerAvant, atelierPret: false })
    const bouton = await screen.findByTestId('cal-resynchroniser-devis')
    expect(bouton).toBeDisabled()
    await userEvent.click(bouton)
    expect(enregistrerAvant).not.toHaveBeenCalled()
    rerender(
      <MemoryRouter>
        <BoutonDevis calepinageId={DETAIL.id} detail={DETAIL} enregistrerAvant={enregistrerAvant} atelierPret />
      </MemoryRouter>,
    )
    expect(screen.getByTestId('cal-resynchroniser-devis')).toBeEnabled()
  })

  it('échec d’enregistrement : ni sync-devis ni rechargement', async () => {
    const enregistrerAvant = vi.fn(async () => false)
    const onRecharger = vi.fn()

    rendre({ enregistrerAvant, onRecharger })
    await userEvent.click(await screen.findByTestId('cal-resynchroniser-devis'))

    expect(await screen.findByTestId('cal-devis-refus'))
      .toHaveTextContent('n’a pas pu être enregistrée')
    expect(enregistrerAvant).toHaveBeenCalledTimes(1)
    expect(calepinageApi.calepinages.apercuResync).not.toHaveBeenCalled()
    expect(calepinageApi.calepinages.syncDevis).not.toHaveBeenCalled()
    expect(onRecharger).not.toHaveBeenCalled()
  })

  it('Générer enregistre aussi d’abord, et n’appelle rien sur échec', async () => {
    const enregistrerAvant = vi.fn(async () => false)
    rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE, enregistrerAvant })
    await userEvent.click(await screen.findByTestId('cal-generer-devis'))
    await screen.findByTestId('cal-devis-refus')
    expect(calepinageApi.calepinages.genererDevis).not.toHaveBeenCalled()
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it('deux clics rapides : un enregistrement, un POST', async () => {
    // ACON46 — la garde est posée AVANT l'enregistrement préalable (asynchrone).
    let liberer
    const enregistrerAvant = vi.fn(() => new Promise((ok) => { liberer = () => ok(true) }))
    calepinageApi.calepinages.genererDevis.mockResolvedValue({ data: { devis: 77 } })
    rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE, enregistrerAvant })
    const bouton = await screen.findByTestId('cal-generer-devis')
    fireEvent.click(bouton)
    fireEvent.click(bouton)
    liberer()
    await waitFor(() => expect(calepinageApi.calepinages.genererDevis).toHaveBeenCalledTimes(1))
    expect(enregistrerAvant).toHaveBeenCalledTimes(1)
  })

  it('Réviser sur accepté : avertit sans refuser', async () => {
    // ACAL1320 — un devis accepté : le 409 révisable arrive dès l'aperçu (aucune carte à confirmer).
    calepinageApi.calepinages.apercuResync.mockRejectedValue({
      response: {
        status: 409,
        data: { detail: 'Le devis lié est accepté : utilisez « Réviser ».', revision_possible: true },
      },
    })
    let resoudre
    ventesApi.reviserDevis.mockImplementation(() => new Promise((r) => { resoudre = r }))
    const aDesRetouches = vi.fn(() => true)

    rendre({ enregistrerAvant: vi.fn(async () => true), aDesRetouches })
    await userEvent.click(await screen.findByTestId('cal-resynchroniser-devis'))
    await userEvent.click(await screen.findByTestId('cal-devis-reviser'))

    expect(await screen.findByTestId('cal-devis-retouches'))
      .toHaveTextContent('Retouches non enregistrées')
    // Jamais un refus : la révision part quand même.
    await waitFor(() => expect(ventesApi.reviserDevis).toHaveBeenCalledWith(DETAIL.devis.id))
    resoudre({ data: { id: 78 } })
    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith('/ventes/devis/78/design'))
  })
})

/* ACAL171 (D-ACAL-9) — le refus 422 ÉLECTRIQUE et la dérogation. Les corps
   viennent du contrat COMMITTÉ `calepinage_publication_electrique.json`. */
describe('BoutonDevis — verdict électrique (ACAL171)', () => {
  const REFUS = exempleContrat('calepinage', 'calepinage_publication_electrique',
    'exemple_refus_409')
  const DEROGUE = exempleContrat('calepinage', 'calepinage_publication_electrique',
    'exemple_derogue')
  const MANQUANTES = exempleContrat('calepinage', 'calepinage_publication_electrique',
    'exemple_avec_manquantes')
  const CORPS = exempleContrat('calepinage', 'calepinage_publication_electrique',
    'corps_derogation')

  // Le droit `calepinage_approuver` est SERVI par l'agrégat de détail
  // (`permissions.peut_deroger`, contrat calepinage_detail.json).
  const avecDroit = (peutDeroger) => ({
    ...DETAIL_VIDE,
    permissions: { ...DETAIL_VIDE.permissions, peut_deroger: peutDeroger },
  })

  async function refuser(peutDeroger = true) {
    calepinageApi.calepinages.genererDevis.mockRejectedValueOnce({
      response: { status: 409, data: REFUS },
    })
    rendre({ calepinageId: DETAIL_VIDE.id, detail: avecDroit(peutDeroger) })
    await userEvent.click(await screen.findByTestId('cal-generer-devis'))
    return screen.findByTestId('cal-devis-bloquants')
  }

  it('422 électrique liste les bloquants et propose la dérogation', async () => {
    const bloc = await refuser()
    const lignes = screen.getAllByTestId('cal-devis-bloquant')
    expect(lignes).toHaveLength(REFUS.electrique.bloquants.length)
    REFUS.electrique.bloquants.forEach((b, i) => {
      expect(lignes[i]).toHaveTextContent(b.libelle)
      expect(lignes[i]).toHaveTextContent(b.detail)
    })
    expect(bloc).toHaveTextContent(REFUS.detail)
    expect(screen.getByTestId('cal-devis-motif')).toBeInTheDocument()
    expect(screen.getByTestId('cal-devis-passer-outre'))
      .toHaveTextContent('Passer outre et générer')
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it('T4-X5-007 — refus électrique : aucun nom de champ technique, dit UNE fois (le toast global est coupé)', async () => {
    const terre = {
      code: 'TERRE_JUSTIFICATION_MANQUANTE',
      libelle: 'prise de terre non fournie au marché : la justification de continuité de la terre existante reste '
        + 'à cocher (terre.justification_continuite)',
      detail: '',
    }
    calepinageApi.calepinages.genererDevis.mockRejectedValueOnce({
      response: { status: 409, data: { ...REFUS, electrique: { ...REFUS.electrique, bloquants: [terre] } } },
    })
    rendre({ calepinageId: DETAIL_VIDE.id, detail: avecDroit(false) })
    await userEvent.click(await screen.findByTestId('cal-generer-devis'))
    const bloc = await screen.findByTestId('cal-devis-bloquants')
    expect(bloc).toHaveTextContent('reste à cocher')
    expect(bloc).not.toHaveTextContent('terre.justification_continuite')
    expect(calepinageApi.calepinages.genererDevis.mock.calls[0][2]).toEqual({ suppressErrorToast: true })
  })

  it('dérogation sans motif refusée sous le champ', async () => {
    await refuser()
    await userEvent.click(screen.getByTestId('cal-devis-passer-outre'))
    expect(await screen.findByTestId('cal-devis-motif-erreur'))
      .toHaveTextContent('Saisissez le motif de la dérogation.')
    expect(calepinageApi.calepinages.genererDevis).toHaveBeenCalledTimes(1)
  })

  it('renvoi avec derogation_electrique', async () => {
    await refuser()
    calepinageApi.calepinages.genererDevis.mockResolvedValueOnce({ data: DEROGUE })
    const motif = CORPS.derogation_electrique.motif
    await userEvent.type(screen.getByTestId('cal-devis-motif'), motif)
    await userEvent.click(screen.getByTestId('cal-devis-passer-outre'))
    await waitFor(() => expect(calepinageApi.calepinages.genererDevis)
      .toHaveBeenLastCalledWith(DETAIL_VIDE.id, CORPS, SANS_TOAST))
    expect(await screen.findByTestId('cal-devis-ouvrir'))
      .toHaveAttribute('href', `/ventes/devis?devis=${DEROGUE.devis}`)
    expect(screen.queryByTestId('cal-devis-bloquants')).toBeNull()
  })

  it('indéterminé affiché sans blocage', async () => {
    calepinageApi.calepinages.genererDevis.mockResolvedValueOnce({ data: MANQUANTES })
    rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE })
    await userEvent.click(await screen.findByTestId('cal-generer-devis'))
    const bloc = await screen.findByTestId('cal-devis-indetermine')
    for (const m of MANQUANTES.electrique.manquantes) expect(bloc).toHaveTextContent(m)
    // Le devis EST créé : on peut l'ouvrir, rien n'est bloqué.
    expect(screen.getByTestId('cal-devis-ouvrir'))
      .toHaveAttribute('href', `/ventes/devis?devis=${MANQUANTES.devis}`)
    expect(screen.queryByTestId('cal-devis-bloquants')).toBeNull()
  })

  it('ACAL935 : « À compléter : N points » au cadre, jamais « indéterminé »', async () => {
    const evaluation = exempleContrat('calepinage', 'calepinage_publication_electrique',
      'exemple_evaluation')
    const data = { ...MANQUANTES, electrique: { ...evaluation.electrique, points: 16, derogation: null } }
    calepinageApi.calepinages.genererDevis.mockResolvedValueOnce({ data })
    rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE })
    await userEvent.click(await screen.findByTestId('cal-generer-devis'))
    const bloc = await screen.findByTestId('cal-devis-indetermine')
    expect(bloc).toHaveTextContent('À compléter : 16 points')
    expect(bloc).not.toHaveTextContent(/indéterminé/i)
    expect(bloc).not.toHaveTextContent(/conforme/i)
  })

  it('sans calepinage_approuver, pas de bouton Passer outre', async () => {
    await refuser(false)
    expect(screen.queryByTestId('cal-devis-passer-outre')).toBeNull()
    expect(screen.queryByTestId('cal-devis-motif')).toBeNull()
    expect(screen.getByTestId('cal-devis-derogation-reservee'))
      .toHaveTextContent('Dérogation réservée aux approbateurs')
  })

  it('403 serveur sur la dérogation : le message du serveur, mot pour mot', async () => {
    await refuser()
    const MESSAGE = 'Dérogation réservée aux approbateurs (calepinage_approuver)'
    calepinageApi.calepinages.genererDevis.mockRejectedValueOnce({
      response: { status: 403, data: { derogation_electrique: MESSAGE } },
    })
    await userEvent.type(screen.getByTestId('cal-devis-motif'), 'client informé')
    await userEvent.click(screen.getByTestId('cal-devis-passer-outre'))
    expect(await screen.findByTestId('cal-devis-refus')).toHaveTextContent(MESSAGE)
  })
})

describe('Lot 2 critique #32 — champs des portes ACAL116 nommés', () => {
  it('refus 400 {approbation} : le bandeau dit « Approbation »', async () => {
    const MESSAGE = 'Approbation à jour exigée avant de générer ou resynchroniser le devis'
    calepinageApi.calepinages.genererDevis.mockRejectedValue({
      response: { status: 400, data: { approbation: [MESSAGE] } },
    })
    rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE })
    await userEvent.click(await screen.findByTestId('cal-generer-devis'))
    const bloc = await screen.findByTestId('cal-devis-refus')
    expect(within(bloc).getByText('Approbation')).toBeInTheDocument()
    expect(bloc).toHaveTextContent(MESSAGE)
  })
})

describe('ACAL915 — ce que le devis chiffre, dit avant « Générer le devis »', () => {
  it('dès deux surfaces posées, la phrase est lue de l’exemple du contrat', () => {
    rendre({ detail: DETAIL_SANS_SELECTION })
    const surfaces = DETAIL.surfaces_chiffrables
    expect(surfaces.length).toBeGreaterThanOrEqual(2)
    const total = surfaces.reduce((t, s) => t + s.modules, 0)
    const phrase = `Le devis chiffre : ${surfaces.map((s) => `${s.libelle} (${s.modules})`).join(' + ')}`
      + ` = ${total} modules`
    expect(screen.getByTestId('cal-bouton-devis')).toHaveTextContent(phrase)
    expect(total).toBe(DETAIL.layout_nb_panneaux)
  })

  it('une seule surface (ou aucune) : aucune ligne', () => {
    rendre({ detail: { ...DETAIL, surfaces_chiffrables: DETAIL.surfaces_chiffrables.slice(0, 1) } })
    expect(screen.getByTestId('cal-bouton-devis')).not.toHaveTextContent('Le devis chiffre :')
    cleanup()
    rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE })
    expect(screen.getByTestId('cal-bouton-devis')).not.toHaveTextContent('Le devis chiffre :')
  })
})

describe('ACAL968 — une case par surface (toit ET champ au sol), toutes cochées à l’ouverture', () => {
  const SANS_DEVIS = { ...DETAIL_VIDE, surfaces_chiffrables: SURFACES_SANS_SELECTION }
  const CORPS = exempleContrat('calepinage', 'calepinage_publication', 'corps_surfaces_chiffrees')

  it('tout coché : aucun corps ; la décochée est absente du corps', async () => {
    calepinageApi.calepinages.genererDevis.mockResolvedValue({
      data: { devis: 42, reference: 'DEV-2609-0042', deduplique: false },
    })
    rendre({ calepinageId: SANS_DEVIS.id, detail: SANS_DEVIS })
    const cases = screen.getAllByRole('checkbox')
    expect(cases).toHaveLength(DETAIL.surfaces_chiffrables.length)
    cases.forEach((c) => expect(c).toBeChecked())
    const toit = DETAIL.surfaces_chiffrables.find((s) => s.kind === 'toit')
    await userEvent.click(screen.getByRole('checkbox', { name: new RegExp(toit.libelle) }))
    await userEvent.click(screen.getByTestId('cal-generer-devis'))
    await waitFor(() => expect(calepinageApi.calepinages.genererDevis).toHaveBeenCalled())
    const corps = calepinageApi.calepinages.genererDevis.mock.calls[0][1]
    expect(corps.surfaces_chiffrees).toEqual(CORPS.surfaces_chiffrees)
    expect(corps.surfaces_chiffrees).not.toContain(toit.cle)
  })

  it('plus rien de coché : « Générer le devis » désactivé, et dit pourquoi', async () => {
    rendre({ calepinageId: SANS_DEVIS.id, detail: SANS_DEVIS })
    for (const c of screen.getAllByRole('checkbox')) await userEvent.click(c)
    expect(screen.getByTestId('cal-generer-devis')).toBeDisabled()
    expect(screen.getByTestId('cal-bouton-devis')).toHaveTextContent('Cochez au moins une surface')
  })
})

/* Recette R2-17 / R2-22 / R2-23 (nuit du 22/11/2026) — les questions de « Générer » et le
   message d'une resynchronisation refusée. Corps du contrat COMMITTÉ
   `calepinage_publication.json`, jamais tapés à la main. */
describe('BoutonDevis — recette R2 (pose au-delà de la cible, devis existant, resynchro refusée)', () => {
  const POSE = exempleContrat('calepinage', 'calepinage_publication', 'exemple_409_confirmation_taille_pose')
  const EXISTANT = exempleContrat('calepinage', 'calepinage_publication', 'exemple_409_devis_existant')
  const RATTACHER = exempleContrat('calepinage', 'calepinage_publication', 'corps_rattacher_devis')
  const AUTRE = exempleContrat('calepinage', 'calepinage_publication', 'corps_creer_autre_devis')
  const CONFIRMER = exempleContrat('calepinage', 'calepinage_publication', 'corps_confirmer_taille')

  it('R2-17 : la pose au-delà de 2 × la cible pose la MÊME question, « Confirmer » passe', async () => {
    calepinageApi.calepinages.genererDevis
      .mockRejectedValueOnce({ response: { status: 409, data: POSE } })
      .mockResolvedValueOnce({ data: { devis: 75, reference: 'DEV-2611-0075', deduplique: false } })
    rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE })
    await userEvent.click(await screen.findByTestId('cal-generer-devis'))
    const encadre = await screen.findByTestId('cal-devis-confirmation-taille')
    expect(encadre).toHaveTextContent(POSE.detail)
    expect(encadre).toHaveTextContent(POSE.refus)
    await userEvent.click(within(encadre).getByRole('button', { name: 'Confirmer et générer' }))
    await waitFor(() => expect(calepinageApi.calepinages.genererDevis)
      .toHaveBeenLastCalledWith(DETAIL_VIDE.id, CONFIRMER, SANS_TOAST))
    expect(await screen.findByTestId('cal-devis-cree')).toHaveTextContent('Devis DEV-2611-0075 créé')
  })

  it('R2-22 : devis existant ⇒ « Rattacher » envoie son id, le rattachement est DIT (jamais « créé »)', async () => {
    calepinageApi.calepinages.genererDevis
      .mockRejectedValueOnce({ response: { status: 409, data: EXISTANT } })
      .mockResolvedValueOnce({ data: { devis: EXISTANT.devis, reference: EXISTANT.reference, deduplique: true } })
    const onRecharger = vi.fn()
    rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE, onRecharger })
    await userEvent.click(await screen.findByTestId('cal-generer-devis'))
    const question = await screen.findByTestId('cal-devis-existant')
    expect(question).toHaveTextContent(EXISTANT.detail)
    expect(screen.queryByTestId('cal-devis-conflit')).toBeNull()
    expect(within(question).getByRole('link', { name: 'Ouvrir le devis existant' }))
      .toHaveAttribute('href', `/ventes/devis?devis=${EXISTANT.devis}`)
    await userEvent.click(within(question).getByRole('button',
      { name: `Rattacher ce calepinage au devis ${EXISTANT.reference}` }))
    await waitFor(() => expect(calepinageApi.calepinages.genererDevis)
      .toHaveBeenLastCalledWith(DETAIL_VIDE.id, RATTACHER, SANS_TOAST))
    const lu = await screen.findByTestId('cal-devis-avertissements')
    expect(lu).toHaveTextContent(`Calepinage rattaché au devis ${EXISTANT.reference}`)
    expect(screen.queryByTestId('cal-devis-cree')).toBeNull()
    expect(screen.queryByTestId('cal-devis-existant')).toBeNull()
    await userEvent.click(screen.getByTestId('cal-devis-j-ai-lu'))
    expect(onRecharger).toHaveBeenCalledTimes(1)
  })

  it('R2-22 : « Créer un autre devis » envoie creer_autre_devis, puis une question de taille garde ce choix', async () => {
    calepinageApi.calepinages.genererDevis
      .mockRejectedValueOnce({ response: { status: 409, data: EXISTANT } })
      .mockRejectedValueOnce({ response: { status: 409, data: POSE } })
      .mockResolvedValueOnce({ data: { devis: 78, reference: 'DEV-2611-0078', deduplique: false } })
    rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE })
    await userEvent.click(await screen.findByTestId('cal-generer-devis'))
    await userEvent.click(within(await screen.findByTestId('cal-devis-existant'))
      .getByRole('button', { name: 'Créer un autre devis' }))
    await waitFor(() => expect(calepinageApi.calepinages.genererDevis)
      .toHaveBeenLastCalledWith(DETAIL_VIDE.id, AUTRE, SANS_TOAST))
    await userEvent.click(within(await screen.findByTestId('cal-devis-confirmation-taille'))
      .getByRole('button', { name: 'Confirmer et générer' }))
    await waitFor(() => expect(calepinageApi.calepinages.genererDevis)
      .toHaveBeenLastCalledWith(DETAIL_VIDE.id, { ...AUTRE, ...CONFIRMER }, SANS_TOAST))
    expect(await screen.findByTestId('cal-devis-cree')).toHaveTextContent('Devis DEV-2611-0078 créé')
  })

  it('R2-23 / V1-01 : conception enregistrée, devis refusé ⇒ le motif du serveur, sans « envoyé » en dur', async () => {
    const MOTIF = 'Devis accepté : révisez-le'
    const ENVOYE = { ...DETAIL, devis: { ...DETAIL.devis, statut: 'accepte' } }
    // La valeur que l'atelier rend quand la conception est rangée mais la resynchro refusée.
    const enregistrerAvant = vi.fn(async () => ({ enregistre: true, devisModifie: false, motif: MOTIF }))
    rendre({ detail: ENVOYE, enregistrerAvant })
    await userEvent.click(await screen.findByTestId('cal-resynchroniser-devis'))
    const refus = await screen.findByTestId('cal-devis-refus')
    expect(refus).toHaveTextContent(
      `La conception est enregistrée, mais le devis lié ${DETAIL.devis.reference} n’a pas été modifié : ${MOTIF}`)
    expect(refus).not.toHaveTextContent('n’a pas pu être enregistrée')
    expect(calepinageApi.calepinages.apercuResync).not.toHaveBeenCalled()
    expect(calepinageApi.calepinages.syncDevis).not.toHaveBeenCalled()
  })
})

describe('ACAL1705 — le devis lié se rouvre d’un clic, lu sur le calepinage', () => {
  it('après rechargement, « Devis lié : DEV-… » est un lien vers le vrai devis (jamais du texte seul)', () => {
    rendre()
    const lien = screen.getByRole('link', { name: DETAIL.devis.reference })
    expect(lien).toHaveAttribute('href', `/ventes/devis?devis=${DETAIL.devis.id}`)
    expect(lien).toHaveAttribute('data-testid', 'cal-devis-lie-lien')
  })

  it('après un 201, la carte « Devis … créé » est montée avec ses deux gestes', async () => {
    calepinageApi.calepinages.genererDevis.mockResolvedValue({
      data: { devis: 42, reference: 'DEV-2609-0042', deduplique: false },
    })
    rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE })
    await userEvent.click(await screen.findByTestId('cal-generer-devis'))
    const carte = await screen.findByTestId('cal-devis-cree')
    expect(within(carte).getByRole('link', { name: 'Voir le devis' })).toHaveAttribute('href', '/ventes/devis?devis=42')
    expect(within(carte).getByRole('button', { name: 'Revenir à la conception' })).toBeTruthy()
  })

  it('ACAL1957 — un 201 est annoncé à l’atelier de CE calepinage (qui relit son contexte) ; un refus ne l’est pas', async () => {
    const { ecouterDevisGenere } = await import('./atelier/contexteAtelier')
    const relu = vi.fn()
    const arreter = ecouterDevisGenere(DETAIL_VIDE.id, relu)
    try {
      calepinageApi.calepinages.genererDevis.mockRejectedValueOnce({ response: { status: 400, data: { detail: 'Refusé.' } } })
      rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE })
      await userEvent.click(await screen.findByTestId('cal-generer-devis'))
      await screen.findByText('Refusé.')
      expect(relu).not.toHaveBeenCalled()
      calepinageApi.calepinages.genererDevis.mockResolvedValue({ data: { devis: 42, reference: 'DEV-2609-0042' } })
      await userEvent.click(screen.getByTestId('cal-generer-devis'))
      await screen.findByTestId('cal-devis-cree')
      expect(relu).toHaveBeenCalledTimes(1)
    } finally { arreter() }
  })
})

/* ACAL1946 — le résultat de « Générer le devis » est dit dès la réponse, même quand l'écran s'est remonté pendant la
   requête (l'enregistrement préalable relit le contexte : le portail de l'étape Documents se remonte). */
describe('ACAL1946 — le résultat de « Générer le devis » est dit dès la réponse', () => {
  const QUESTION = exempleContrat('calepinage', 'calepinage_publication', 'exemple_409_confirmation_taille')
  it.each([
    ['réponse 201 ⇒ « Devis … créé » dit', (r) => r.ok({ data: { devis: 44, reference: 'DEV-2611-0044' } }),
      'cal-devis-cree', 'Devis DEV-2611-0044 créé'],
    ['409 confirmation_taille ⇒ la question dite', (r) => r.ko({ response: { status: 409, data: QUESTION } }),
      'cal-devis-confirmation-taille', QUESTION.detail],
    ['refus ⇒ le refus nommé', (r) => r.ko({ response: { status: 400, data: { detail: 'Calepinage verrouillé.' } } }),
      'cal-devis-refus', 'Calepinage verrouillé.'],
  ])('%s', async (_cas, repondre, testId, texte) => {
    const attente = {}
    calepinageApi.calepinages.genererDevis.mockImplementation(() => new Promise((ok, ko) => Object.assign(attente, { ok, ko })))
    const premier = rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE })
    await userEvent.click(await screen.findByTestId('cal-generer-devis'))
    await waitFor(() => expect(calepinageApi.calepinages.genererDevis).toHaveBeenCalledTimes(1))
    premier.unmount() // le portail se remonte pendant la requête
    rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE })
    repondre(attente)
    expect(await screen.findByTestId(testId)).toHaveTextContent(texte)
  })
})

/* ACAL1972 — la carte « Devis … créé » à boîte nulle : le 201 relit le contexte de l'atelier (ACAL1957), la coque
   remonte le nœud de son portail ; la carte est rendue DANS le nœud monté, pas dans l'ancien, détaché. */
describe('ACAL1972 — 201 ⇒ la carte est rendue avec sa boîte après le rechargement du contexte', () => {
  function CoqueQuiSeRemonte() {
    const [tour, setTour] = useState(0)
    useEffect(() => ecouterDevisGenere(DETAIL_VIDE.id, () => setTour((t) => t + 1)), [])
    return (
      <MemoryRouter>
        <div key={tour} data-testid={`portail-${tour}`}>
          <BoutonDevis calepinageId={DETAIL_VIDE.id} detail={tour ? DETAIL : DETAIL_VIDE} />
        </div>
      </MemoryRouter>
    )
  }

  it('la carte et « Voir le devis » sont dans le portail remonté', async () => {
    calepinageApi.calepinages.genererDevis.mockResolvedValue({ data: { devis: 44, reference: 'DEV-2611-0044' } })
    render(<CoqueQuiSeRemonte />)
    await userEvent.click(await screen.findByTestId('cal-generer-devis'))
    const carte = await within(await screen.findByTestId('portail-1')).findByTestId('cal-devis-cree')
    expect(carte.isConnected).toBe(true)
    expect(carte).toHaveTextContent('Devis DEV-2611-0044 créé')
    expect(within(carte).getByTestId('cal-devis-ouvrir')).toHaveAttribute('href', '/ventes/devis?devis=44')
  })
})

describe('ACAL1414 — la réouverture relit les surfaces que le devis lié chiffre', () => {
  const toit = DETAIL.surfaces_chiffrables.find((s) => s.kind === 'toit')
  const sol = DETAIL.surfaces_chiffrables.find((s) => s.kind !== 'toit')

  it('chiffree faux ⇒ case décochée, phrase = la seule surface chiffrée', () => {
    expect(toit.chiffree).toBe(false)
    expect(sol.chiffree).toBe(true)
    rendre()
    expect(screen.getByRole('checkbox', { name: new RegExp(toit.libelle) })).not.toBeChecked()
    expect(screen.getByRole('checkbox', { name: new RegExp(sol.libelle) })).toBeChecked()
    expect(screen.getByTestId('cal-bouton-devis')).toHaveTextContent(
      `Le devis chiffre : ${sol.libelle} (${sol.modules}) = ${sol.modules} modules`)
  })

  it('« Resynchroniser le devis » envoie la même sélection', async () => {
    calepinageApi.calepinages.syncDevis.mockResolvedValue({ data: { inchange: true, devis: DETAIL.devis.id } })
    rendre()
    await resynchroniserEtConfirmer()
    await waitFor(() => expect(calepinageApi.calepinages.syncDevis).toHaveBeenCalled())
    expect(calepinageApi.calepinages.syncDevis.mock.calls[0][1].surfaces_chiffrees).toEqual([sol.cle])
    // ACAL1320 — l'aperçu lu avant porte la MÊME sélection.
    expect(calepinageApi.calepinages.apercuResync).toHaveBeenCalledWith(DETAIL.id,
      { params: { surfaces: sol.cle }, suppressErrorToast: true })
  })

  it('le serveur change la sélection : l’écran la relit', () => {
    const { rerender } = rendre({ detail: DETAIL_SANS_SELECTION })
    screen.getAllByRole('checkbox').forEach((c) => expect(c).toBeChecked())
    rerender(
      <MemoryRouter>
        <BoutonDevis calepinageId={DETAIL.id} detail={DETAIL} />
      </MemoryRouter>,
    )
    expect(screen.getByRole('checkbox', { name: new RegExp(toit.libelle) })).not.toBeChecked()
  })
})

/* ACAL1320 (D-ACAL-73 = corriger_dire) — « Resynchroniser le devis » DIT ce qu'il va changer AVANT d'agir ;
   pour un devis envoyé, que le devis reçu par le client sera corrigé ; rien n'est écrit avant la confirmation. */
describe('ACAL1320 — l’aperçu avant « Resynchroniser le devis »', () => {
  const INCHANGE = exempleContrat('calepinage', 'calepinage_apercu_resync', 'exemple_inchange')
  const CAVIARDE = exempleContrat('calepinage', 'calepinage_apercu_resync', 'exemple_sans_lecture_devis')

  it('devis envoyé : la correction est dite, les lignes et totaux servis ; sync-devis seulement après « Corriger »', async () => {
    const onRecharger = vi.fn()
    calepinageApi.calepinages.syncDevis.mockResolvedValue({ data: { inchange: false, avertissements: [] } })
    rendre({ onRecharger })
    await userEvent.click(await screen.findByTestId('cal-resynchroniser-devis'))

    const carte = await screen.findByTestId('cal-devis-resync-apercu')
    expect(screen.getByTestId('cal-devis-resync-statut')).toHaveTextContent(
      `Devis ${APERCU_RESYNC.reference} — Ce devis a déjà été envoyé au client : il sera corrigé sur place. Sa page `
      + 'et son PDF montreront la version corrigée, et la correction sera notée sur le devis.')
    const onduleur = APERCU_RESYNC.changements[1]
    expect(carte).toHaveTextContent(`${onduleur.designation_avant} → ${onduleur.designation_apres}`)
    expect(carte).toHaveTextContent('Total TTC :')
    expect(carte).toHaveTextContent(APERCU_RESYNC.avertissements[0])
    expect(calepinageApi.calepinages.syncDevis).not.toHaveBeenCalled()

    await userEvent.click(within(carte).getByTestId('cal-devis-resync-confirmer'))
    await waitFor(() => expect(calepinageApi.calepinages.syncDevis).toHaveBeenCalledTimes(1))
    // Revue du 26/11 — SEULE la carte confirmée envoie `apercu_confirme` (contrat `corps_confirmation`).
    expect(calepinageApi.calepinages.syncDevis).toHaveBeenCalledWith(DETAIL.id,
      { surfaces_chiffrees: [DETAIL.surfaces_chiffrables.find((s) => s.chiffree).cle],
        ...exempleContrat('calepinage', 'calepinage_apercu_resync', 'corps_confirmation') }, SANS_TOAST)
    expect(screen.queryByTestId('cal-devis-resync-apercu')).toBeNull()
  })

  it('revue — la carte dit que la vérification électrique se fait à la confirmation', async () => {
    rendre()
    await userEvent.click(await screen.findByTestId('cal-resynchroniser-devis'))
    expect(await screen.findByTestId('cal-devis-resync-apercu')).toHaveTextContent(MESSAGE_VERIFICATION_A_LA_CONFIRMATION)
  })

  it('revue — 409 apercu_perime à la confirmation : rien d’écrit, l’aperçu est relu et le dit', async () => {
    const PERIME = exempleContrat('calepinage', 'calepinage_apercu_resync', 'reponse_409_apercu_perime')
    calepinageApi.calepinages.syncDevis.mockRejectedValueOnce({ response: { status: 409, data: PERIME } })
    rendre()
    await resynchroniserEtConfirmer()
    expect(await screen.findByTestId('cal-devis-resync-avis')).toHaveTextContent(MESSAGE_APERCU_RELU)
    expect(calepinageApi.calepinages.apercuResync).toHaveBeenCalledTimes(2)
    expect(calepinageApi.calepinages.syncDevis).toHaveBeenCalledTimes(1)
    expect(screen.getByTestId('cal-devis-resync-apercu')).toBeInTheDocument()
    expect(screen.queryByTestId('cal-devis-conflit')).toBeNull()
  })

  it('revue — une retouche de la scène ferme la carte : rien n’est envoyé, l’écran dit de relancer', async () => {
    let retouchee = false
    rendre({ enregistrerAvant: vi.fn(async () => true), aDesRetouches: () => retouchee })
    await userEvent.click(await screen.findByTestId('cal-resynchroniser-devis'))
    await screen.findByTestId('cal-devis-resync-apercu')
    retouchee = true
    expect(await screen.findByTestId('cal-devis-resync-ferme')).toHaveTextContent(MESSAGE_APERCU_FERME)
    expect(screen.queryByTestId('cal-devis-resync-apercu')).toBeNull()
    expect(calepinageApi.calepinages.syncDevis).not.toHaveBeenCalled()
  })

  it('« Annuler » : la carte se ferme, rien n’est envoyé', async () => {
    rendre()
    await userEvent.click(await screen.findByTestId('cal-resynchroniser-devis'))
    await userEvent.click(await screen.findByTestId('cal-devis-resync-annuler'))
    expect(screen.queryByTestId('cal-devis-resync-apercu')).toBeNull()
    expect(calepinageApi.calepinages.syncDevis).not.toHaveBeenCalled()
  })

  it('rien à changer : la phrase est dite, aucune confirmation demandée, rien n’est envoyé', async () => {
    calepinageApi.calepinages.apercuResync.mockResolvedValue({ data: INCHANGE })
    rendre()
    await userEvent.click(await screen.findByTestId('cal-resynchroniser-devis'))
    expect(await screen.findByTestId('cal-devis-avertissements')).toHaveTextContent(MESSAGE_RIEN_A_CHANGER)
    expect(screen.queryByTestId('cal-devis-resync-confirmer')).toBeNull()
    expect(calepinageApi.calepinages.syncDevis).not.toHaveBeenCalled()
  })

  it('devis accepté : le 409 du serveur (révisable) dès l’aperçu, aucune confirmation, aucun sync-devis', async () => {
    calepinageApi.calepinages.apercuResync.mockRejectedValue({
      response: { status: 409, data: { detail: 'Devis accepté : révisez-le.', revision_possible: true } },
    })
    rendre()
    await userEvent.click(await screen.findByTestId('cal-resynchroniser-devis'))
    expect(await screen.findByTestId('cal-devis-conflit')).toHaveTextContent('Devis accepté : révisez-le.')
    expect(screen.getByTestId('cal-devis-reviser')).toBeInTheDocument()
    expect(screen.queryByTestId('cal-devis-resync-apercu')).toBeNull()
    expect(calepinageApi.calepinages.syncDevis).not.toHaveBeenCalled()
  })

  it('brouillon : « mis à jour » ; sans lecture des devis (montants null) : aucun montant affiché', async () => {
    calepinageApi.calepinages.apercuResync.mockResolvedValue({ data: { ...CAVIARDE, statut: 'brouillon',
      corrige_apres_envoi: false } })
    rendre()
    await userEvent.click(await screen.findByTestId('cal-resynchroniser-devis'))
    const carte = await screen.findByTestId('cal-devis-resync-apercu')
    expect(screen.getByTestId('cal-devis-resync-statut')).toHaveTextContent(MESSAGE_BROUILLON_MIS_A_JOUR)
    expect(screen.getByTestId('cal-devis-resync-statut')).not.toHaveTextContent('Devis DEV')
    expect(carte).toHaveTextContent(`${CAVIARDE.changements[0].designation_apres} : quantité 3 → 2`)
    expect(carte).not.toHaveTextContent('MAD')
    expect(carte).not.toHaveTextContent('Total TTC')
    expect(within(carte).getByTestId('cal-devis-resync-confirmer')).toHaveTextContent('Confirmer et resynchroniser')
  })
})

describe('D-ACAL-106 — « Générer le devis » selon le droit de la route generer-devis (calepinage_gerer)', () => {
  it('Technicien (calepinage_voir + calepinage_releve) : aucun bouton ; avec calepinage_gerer : le bouton', async () => {
    const { Provider } = await import('react-redux')
    const { configureStore } = await import('@reduxjs/toolkit')
    const boutique = (permissions) => configureStore({ reducer: { auth: (s = { role: 'technicien', permissions }) => s } })
    const monter = (permissions) => render(
      <Provider store={boutique(permissions)}>
        <MemoryRouter><BoutonDevis calepinageId={DETAIL_VIDE.id} detail={DETAIL_VIDE} actionEtape /></MemoryRouter>
      </Provider>,
    )
    const { unmount } = monter(['calepinage_voir', 'calepinage_releve'])
    expect(screen.queryByTestId('cal-generer-devis')).toBeNull()
    unmount()
    monter(['calepinage_voir', 'calepinage_gerer'])
    expect(await screen.findByTestId('cal-generer-devis')).toBeInTheDocument()
  })
})

/* Revue ACAL1946 — l'issue retenue a une DURÉE DE VIE : le refus électrique survit lui aussi au remontage du portail ;
   un autre utilisateur du même onglet (même calepinage) ne la lit pas. (Quitter l'atelier l'oublie :
   `atelier/useAtelierBoot.test.js`.) */
describe('Revue ACAL1946 — l’issue retenue : remontage oui, autre utilisateur non', () => {
  const REFUS = exempleContrat('calepinage', 'calepinage_publication_electrique', 'exemple_refus_409')
  const monter = async (id) => {
    const { Provider } = await import('react-redux')
    const { configureStore } = await import('@reduxjs/toolkit')
    const store = configureStore({ reducer: { auth: (s = { role: 'admin', permissions: [], user: { id } }) => s } })
    return render(
      <Provider store={store}>
        <MemoryRouter><BoutonDevis calepinageId={DETAIL_VIDE.id} detail={DETAIL_VIDE} /></MemoryRouter>
      </Provider>,
    )
  }

  it('le refus électrique (bloquage) survit au remontage pendant la requête', async () => {
    const attente = {}
    calepinageApi.calepinages.genererDevis.mockImplementation(() => new Promise((ok, ko) => Object.assign(attente, { ok, ko })))
    const premier = rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE })
    await userEvent.click(await screen.findByTestId('cal-generer-devis'))
    await waitFor(() => expect(calepinageApi.calepinages.genererDevis).toHaveBeenCalledTimes(1))
    premier.unmount()
    rendre({ calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE })
    attente.ko({ response: { status: 409, data: REFUS } })
    expect(await screen.findByTestId('cal-devis-bloquants')).toBeTruthy()
  })

  it('un autre utilisateur (même onglet, même calepinage) ne voit pas « Devis … créé »', async () => {
    calepinageApi.calepinages.genererDevis.mockResolvedValueOnce({ data: { devis: 44, reference: 'DEV-2611-0044' } })
    const a = await monter(7)
    await userEvent.click(await screen.findByTestId('cal-generer-devis'))
    expect(await screen.findByTestId('cal-devis-cree')).toHaveTextContent('Devis DEV-2611-0044 créé')
    a.unmount()
    const b = await monter(8)
    await screen.findByTestId('cal-generer-devis')
    expect(screen.queryByTestId('cal-devis-cree')).toBeNull()
    b.unmount()
    await monter(7) // le même utilisateur, sans quitter l'atelier (remontage) : l'issue est toujours là
    expect(await screen.findByTestId('cal-devis-cree')).toHaveTextContent('Devis DEV-2611-0044 créé')
  })
})
