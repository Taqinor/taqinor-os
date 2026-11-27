import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

/* ============================================================================
   CAL42 — le comparatif des variantes, prouvé SUR LE CONTRAT.
   ----------------------------------------------------------------------------
   AUCUN MOCK ÉCRIT À LA MAIN (PACT13) : la charge utile est l'exemple committé
   `apps/calepinage/contract_samples/variantes_comparer.json`, le même fichier
   que `scripts/check_api_shapes.py` compare au dictionnaire RÉELLEMENT renvoyé
   par la vue. Un PAYLOAD maison serait une DEUXIÈME source de vérité — c'est
   exactement ce qui a laissé l'écran AO Tableau de bord partir en production
   le 03/08/2026 avec zéro clé sur six concordante, les deux suites vertes.

   Les deux invariants durs :
     1. les ÉCARTS viennent du serveur — aucun calcul d'écran ;
     2. retenir une variante rend l'ANCIENNE non retenue à l'écran, parce que le
        serveur le dit au rechargement.
   ========================================================================== */

const mocks = vi.hoisted(() => ({
  comparer: vi.fn(), retenirVariante: vi.fn(),
  // CALX37
  layout: vi.fn(), creerVariante: vi.fn(), dupliquerVariante: vi.fn(),
  // ACAL109
  modifierVariante: vi.fn(), supprimerVariante: vi.fn(),
  // ACAL113
  simulerVariante: vi.fn(), resultatJob: vi.fn(),
}))

vi.mock('../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      comparer: mocks.comparer, retenirVariante: mocks.retenirVariante,
      layout: mocks.layout, creerVariante: mocks.creerVariante,
      dupliquerVariante: mocks.dupliquerVariante,
      modifierVariante: mocks.modifierVariante,
      supprimerVariante: mocks.supprimerVariante,
      simulerVariante: mocks.simulerVariante,
    },
    moteur: { resultat: mocks.resultatJob },
  },
}))

import VariantesCompare from './VariantesCompare'
import { exempleContrat } from '../../test/fixtures/contractSamples'

const CONTRAT = exempleContrat('calepinage', 'variantes_comparer')
const CONTRAT_UNE_SEULE = exempleContrat('calepinage', 'variantes_comparer', 'exemple_vide')

const RETENUE = CONTRAT.lignes.find((l) => l.est_retenue)
// ACAL978 — la conception courante (`courante: true`) n'est pas une variante.
const AUTRE = CONTRAT.lignes.find((l) => !l.est_retenue && l.simulee && !l.courante)
const NON_SIMULEE = CONTRAT.lignes.find((l) => !l.simulee)

const rendre = (props = {}) => render(
  <MemoryRouter initialEntries={['/calepinage/1/variantes']}>
    <Routes>
      <Route path="/calepinage/:id/variantes" element={<VariantesCompare {...props} />} />
    </Routes>
  </MemoryRouter>,
)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.comparer.mockResolvedValue({ data: CONTRAT })
  mocks.retenirVariante.mockResolvedValue({ data: {} })
})

describe('VariantesCompare (CAL42)', () => {
  it('le contrat committé porte bien les trois cas que l’écran doit rendre', () => {
    // Garde de la fixture elle-même : si le contrat change de forme, ce test
    // dit POURQUOI les suivants cassent, au lieu d'échouer sur un symptôme.
    expect(RETENUE).toBeTruthy()
    expect(AUTRE).toBeTruthy()
    expect(NON_SIMULEE).toBeTruthy()
    expect(RETENUE.ecart_modules).toBe(0)
    expect(NON_SIMULEE.ecart_p50_kwh).toBeNull()
  })

  it('charge le comparatif du calepinage de l’URL', async () => {
    rendre()
    await waitFor(() => expect(mocks.comparer).toHaveBeenCalledWith('1'))
  })

  it('rend UNE COLONNE PAR VARIANTE, avec son libellé', async () => {
    rendre()
    const tableau = await screen.findByTestId('cal-tableau-variantes')
    for (const ligne of CONTRAT.lignes) {
      expect(within(tableau).getAllByText(ligne.nom).length).toBeGreaterThan(0)
    }
  })

  it('modules, kWc, orientation et marges viennent des clés du contrat', async () => {
    rendre()
    await screen.findByTestId('cal-tableau-variantes')
    expect(screen.getByTestId(`cal-modules-${RETENUE.id}`))
      .toHaveTextContent(String(RETENUE.total_modules))
    expect(screen.getByTestId(`cal-kwc-${RETENUE.id}`))
      .toHaveTextContent(String(RETENUE.kwc).replace('.', ','))
    expect(screen.getByTestId(`cal-orientation-${RETENUE.id}`))
      .toHaveTextContent(RETENUE.orientation.orientation_module)
    expect(screen.getByTestId(`cal-marges-${RETENUE.id}`))
      .toHaveTextContent(RETENUE.marges.rangee_critique)
  })

  it('LES ÉCARTS SONT CEUX DU SERVEUR — jamais recalculés à l’écran', async () => {
    rendre()
    await screen.findByTestId('cal-tableau-variantes')
    // La retenue porte un écart MESURÉ, nul par construction : « 0 », pas « — ».
    expect(screen.getByTestId(`cal-ecart_modules-${RETENUE.id}`)).toHaveTextContent('0')
    // L'autre variante porte l'écart SIGNÉ du contrat (−2 modules ici).
    const signe = AUTRE.ecart_modules < 0 ? '−' : '+'
    expect(screen.getByTestId(`cal-ecart_modules-${AUTRE.id}`))
      .toHaveTextContent(`${signe}${Math.abs(AUTRE.ecart_modules)}`)
  })

  it('une variante NON SIMULÉE est dite « non simulée » — jamais « 0 kWh »', async () => {
    rendre()
    await screen.findByTestId('cal-tableau-variantes')
    expect(screen.getByTestId(`cal-p50-${NON_SIMULEE.id}`)).toHaveTextContent('non simulée')
    expect(screen.getByTestId(`cal-pr-${NON_SIMULEE.id}`)).toHaveTextContent('non simulée')
    expect(screen.getByTestId(`cal-p50-${NON_SIMULEE.id}`)).not.toHaveTextContent('0')
  })

  it('une marge NON MESURÉE (`null`) ne s’affiche pas comme « au ras »', async () => {
    rendre()
    await screen.findByTestId('cal-tableau-variantes')
    expect(RETENUE.marges.bande_min_cm).toBeNull()
    // La bande absente ne produit aucun « 0 cm » : seule la marge mesurée sort.
    expect(screen.getByTestId(`cal-marges-${RETENUE.id}`)).not.toHaveTextContent('bande')
  })

  it('« Retenir » appelle le serveur puis RECHARGE — l’ancienne retenue perd son badge', async () => {
    rendre()
    await screen.findByTestId('cal-tableau-variantes')
    expect(screen.getByTestId(`cal-retenue-${RETENUE.id}`)).toBeInTheDocument()

    // Le serveur bascule : au rechargement, c'est AUTRE qui est retenue.
    const apresBascule = {
      ...CONTRAT,
      retenue_id: AUTRE.id,
      lignes: CONTRAT.lignes.map((l) => ({ ...l, est_retenue: l.id === AUTRE.id })),
    }
    mocks.comparer.mockResolvedValue({ data: apresBascule })

    const cellule = screen.getByTestId(`cal-ecart_modules-${AUTRE.id}`).closest('table')
    const boutons = within(cellule).getAllByRole('button', { name: 'Retenir' })
    fireEvent.click(boutons[0])

    await waitFor(() => expect(mocks.retenirVariante).toHaveBeenCalledWith('1', AUTRE.id, { suppressErrorToast: true }))
    await waitFor(() => expect(screen.getByTestId(`cal-retenue-${AUTRE.id}`)).toBeInTheDocument())
    expect(screen.queryByTestId(`cal-retenue-${RETENUE.id}`)).not.toBeInTheDocument()
  })

  it('T4-X5-014 — après « Retenir », l’atelier entier relit la conception (Documents, devis) : onRecharger, une fois', async () => {
    const onRecharger = vi.fn().mockResolvedValue(undefined)
    rendre({ onRecharger })
    await screen.findByTestId('cal-tableau-variantes')
    const cellule = screen.getByTestId(`cal-ecart_modules-${AUTRE.id}`).closest('table')
    fireEvent.click(within(cellule).getAllByRole('button', { name: 'Retenir' })[0])
    await waitFor(() => expect(onRecharger).toHaveBeenCalledTimes(1))
  })

  it('T4-X5-014 — un refus de « Retenir » ne relit pas l’atelier', async () => {
    mocks.retenirVariante.mockRejectedValue({ response: { status: 409, data: { variante: 'Refus.' } } })
    const onRecharger = vi.fn()
    rendre({ onRecharger })
    await screen.findByTestId('cal-tableau-variantes')
    fireEvent.click(screen.getAllByRole('button', { name: 'Retenir' })[0])
    await screen.findByRole('alert')
    expect(onRecharger).not.toHaveBeenCalled()
  })

  it('un refus de « Retenir » s’affiche tel quel, et la retenue ne bouge pas', async () => {
    // ACAL279 — la forme RÉELLE du handler : `{approbation: [msg], error: {…}}`.
    mocks.retenirVariante.mockRejectedValue({
      response: { status: 400, data: {
        approbation: ['Approbation exigée : faites approuver la conception avant de la retenir.'],
        error: { code: 'validation_error', message: 'Requête invalide.', fields: {}, request_id: 'r-1' },
      } },
    })
    rendre()
    await screen.findByTestId('cal-tableau-variantes')
    fireEvent.click(screen.getAllByRole('button', { name: 'Retenir' })[0])
    const alerte = await screen.findByRole('alert')
    expect(alerte).toHaveTextContent('Approbation exigée')
    expect(alerte).not.toHaveTextContent('Impossible de retenir cette variante')
    expect(screen.getByTestId(`cal-retenue-${RETENUE.id}`)).toBeInTheDocument()
  })

  // T4-X9-010 — 409 sur « Retenir » (verdict électrique bloquant) : rien ne changeait là où l'on avait cliqué, le refus
  // s'écrivait tout en haut, hors de la vue, avec la clé interne « (terre.justification_continuite) », sans chemin.
  it('T4-X9-010 — le refus se dit À CÔTÉ du bouton cliqué, sans clé interne, avec le lien vers l’étape Électrique', async () => {
    const detail = 'Cette variante ne peut pas être retenue : verdict électrique bloquant — prise de terre non fournie au '
      + 'marché : la justification de continuité de la terre existante reste à cocher (terre.justification_continuite)'
    mocks.retenirVariante.mockRejectedValue({ response: { status: 409, data: { detail } } })
    rendre()
    await screen.findByTestId('cal-tableau-variantes')
    const cellule = screen.getByTestId(`cal-ecart_modules-${AUTRE.id}`).closest('table')
    fireEvent.click(within(cellule).getAllByRole('button', { name: 'Retenir' })[0])
    const pres = await screen.findByTestId(`cal-variante-refus-${AUTRE.id}`)
    expect(pres).toHaveAttribute('role', 'alert')
    expect(pres).toHaveTextContent('la justification de continuité de la terre existante reste à cocher')
    expect(pres).not.toHaveTextContent('terre.justification_continuite')
    const lien = within(pres).getByRole('link', { name: 'Ouvrir l’étape Électrique' })
    expect(lien.getAttribute('href')).toContain('onglet=decisions-electriques')
    expect(screen.getAllByRole('alert')).toHaveLength(1) // plus de copie en haut de l'onglet
    // T4-X9-010 — le toast global répétait la clé interne : l'appel le coupe, le refus n'est dit qu'une fois.
    expect(mocks.retenirVariante).toHaveBeenCalledWith('1', AUTRE.id, { suppressErrorToast: true })
  })

  // R6-N2 — « Retenir » sur une variante JAMAIS simulée : permis, mais dit avant le geste et après (la conception passait de
  // 8 panneaux 5,68 kWc à 9 · 6,39 sans un mot).
  it('R6-N2 — une variante non simulée porte son avertissement AVANT « Retenir », les simulées non', async () => {
    rendre()
    await screen.findByTestId('cal-tableau-variantes')
    const avant = screen.getByTestId(`cal-variante-sans-simulation-${NON_SIMULEE.id}`)
    expect(avant).toHaveTextContent('Non simulée')
    expect(avant).toHaveTextContent('estimation de l’atelier')
    expect(avant).toHaveTextContent('Simulation à refaire')
    expect(screen.queryByTestId(`cal-variante-sans-simulation-${AUTRE.id}`)).not.toBeInTheDocument()
    expect(screen.queryByTestId('cal-variante-retenue-sans-simulation')).not.toBeInTheDocument()
  })

  // Les lignes RELUES après « Retenir » de NON_SIMULEE : `perimee` = la simulation du calepinage servie périmée (ligne
  // `courante`), `simulee` = la variante retenue a (ou non) sa propre simulation.
  const apresRetenirNonSimulee = ({ perimee, simulee = false }) => ({
    ...CONTRAT,
    retenue_id: NON_SIMULEE.id,
    lignes: CONTRAT.lignes.map((l) => (l.courante
      ? { ...l, simulation_perimee: perimee }
      : { ...l, est_retenue: l.id === NON_SIMULEE.id, ...(l.id === NON_SIMULEE.id ? { simulee } : {}) })),
  })
  const retenirNonSimulee = async () => {
    rendre()
    await screen.findByTestId('cal-tableau-variantes')
    const cellule = screen.getByTestId(`cal-ecart_modules-${NON_SIMULEE.id}`).closest('table')
    const rangee = within(cellule).getByTestId(`cal-variante-sans-simulation-${NON_SIMULEE.id}`).closest('td')
    fireEvent.click(within(rangee).getByRole('button', { name: 'Retenir' }))
    return screen.findByTestId('cal-variante-retenue-sans-simulation')
  }

  it('R6-N2 — après « Retenir » d’une variante non simulée, la simulation servie périmée : estimation dite, « conception précédente » ne vaut plus', async () => {
    mocks.comparer.mockResolvedValue({ data: CONTRAT })
    mocks.comparer.mockResolvedValueOnce({ data: CONTRAT }).mockResolvedValue({ data: apresRetenirNonSimulee({ perimee: true }) })
    const apres = await retenirNonSimulee()
    expect(apres).toHaveTextContent(NON_SIMULEE.nom)
    expect(apres).toHaveTextContent('retenue sans simulation propre')
    expect(apres).toHaveTextContent('estimation de l’atelier')
    expect(apres).toHaveTextContent('la simulation de la conception précédente ne s’applique plus')
    expect(apres).not.toHaveTextContent('ancienne retenue')
    expect(mocks.retenirVariante).toHaveBeenCalledWith('1', NON_SIMULEE.id, { suppressErrorToast: true })
  })

  // Cas (a) aucune variante retenue avant / (b) variante dupliquée de la conception, jamais modifiée : le serveur sert la
  // simulation du calepinage toujours en vigueur — la phrase ne dit ni « précédente » ni « estimation ».
  it('R6-N2 — simulation du calepinage toujours en vigueur (aucune retenue avant, ou copie inchangée) : rien n’est affirmé sur la précédente', async () => {
    mocks.comparer.mockResolvedValueOnce({ data: CONTRAT }).mockResolvedValue({ data: apresRetenirNonSimulee({ perimee: false }) })
    const apres = await retenirNonSimulee()
    expect(apres).toHaveTextContent('retenue sans simulation propre')
    expect(apres).not.toHaveTextContent('précédente')
    expect(apres).not.toHaveTextContent('estimation')
    expect(apres).not.toHaveTextContent('Simulation à refaire')
  })

  it('R6-N2 — la carte suit les lignes relues : elle disparaît dès que la variante retenue est simulée', async () => {
    mocks.comparer.mockResolvedValueOnce({ data: CONTRAT }).mockResolvedValue({ data: apresRetenirNonSimulee({ perimee: true }) })
    mocks.simulerVariante.mockResolvedValue({ data: { job_id: 8, variante_id: NON_SIMULEE.id } })
    mocks.resultatJob.mockResolvedValue({ data: { job_id: 8, statut: 'done', resultat: {} } })
    await retenirNonSimulee()
    // le serveur sert désormais la variante retenue SIMULÉE
    mocks.comparer.mockResolvedValue({ data: apresRetenirNonSimulee({ perimee: false, simulee: true }) })
    fireEvent.click(screen.getByTestId(`cal-variante-simuler-${NON_SIMULEE.id}`))
    await waitFor(() => expect(screen.queryByTestId('cal-variante-retenue-sans-simulation')).not.toBeInTheDocument())
    expect(screen.getByTestId(`cal-retenue-${NON_SIMULEE.id}`)).toBeInTheDocument()
  })

  it('R6-N2 — retenir une variante SIMULÉE ne pose aucune phrase « sans simulation »', async () => {
    rendre()
    await screen.findByTestId('cal-tableau-variantes')
    const cellule = screen.getByTestId(`cal-ecart_modules-${AUTRE.id}`).closest('table')
    const rangee = within(cellule).getByTestId(`cal-variante-dupliquer-${AUTRE.id}`).closest('td')
    fireEvent.click(within(rangee).getByRole('button', { name: 'Retenir' }))
    await waitFor(() => expect(mocks.retenirVariante).toHaveBeenCalledWith('1', AUTRE.id, { suppressErrorToast: true }))
    expect(screen.queryByTestId('cal-variante-retenue-sans-simulation')).not.toBeInTheDocument()
  })

  it('la vue CÔTE À CÔTE compare deux variantes, écarts serveur inclus', async () => {
    rendre()
    const bloc = await screen.findByTestId('cal-cote-a-cote')
    expect(within(bloc).getByLabelText('Variante de gauche')).toBeInTheDocument()
    expect(within(bloc).getByLabelText('Variante de droite')).toBeInTheDocument()
    expect(within(bloc).getAllByText('Écart P50 / retenue').length).toBe(2)
    expect(within(bloc).getAllByText('Plan').length).toBe(2)
  })

  it('l’OMBRAGE affiché est le poste de perte publié, AVEC sa source', async () => {
    const shading = RETENUE.production.pertes_dominantes.find((p) => p.poste === 'shading')
    expect(shading, 'le contrat ne publie plus de poste `shading`').toBeTruthy()
    rendre()
    const bloc = await screen.findByTestId('cal-cote-a-cote')
    expect(within(bloc).getAllByText(new RegExp(shading.source)).length).toBeGreaterThan(0)
  })

  it('ACAL978 — une variante + la courante : deux colonnes, la courante n’offre que « Ouvrir dans l’atelier »', async () => {
    mocks.comparer.mockResolvedValue({ data: CONTRAT_UNE_SEULE })
    rendre()
    const tableau = await screen.findByTestId('cal-tableau-variantes')
    const courante = CONTRAT_UNE_SEULE.lignes[0]
    const seule = CONTRAT_UNE_SEULE.lignes[1]
    expect(courante.courante).toBe(true)
    expect(courante.id).toBeNull()
    expect(within(tableau).getAllByText(courante.nom).length).toBeGreaterThan(0)
    expect(within(tableau).getAllByText(seule.nom).length).toBeGreaterThan(0)
    // La courante : un seul geste, aucune décision sur une variante.
    const lien = screen.getByTestId('acal978-ouvrir-atelier')
    expect(lien).toHaveAttribute('href', '/calepinage/1')
    expect(lien).toHaveTextContent('Ouvrir dans l’atelier')
    expect(screen.queryByTestId('cal-variante-renommer-null')).toBeNull()
    expect(screen.queryByTestId('cal-variante-supprimer-null')).toBeNull()
    expect(screen.queryByTestId('cal-variante-dupliquer-null')).toBeNull()
    expect(screen.queryByTestId('cal-variante-simuler-null')).toBeNull()
    // Côte à côte la propose, et les écarts sont ceux du serveur.
    expect(screen.getByTestId('cal-cote-a-cote')).toBeInTheDocument()
    expect(screen.getByTestId('cal-ecart_modules-courante')).toHaveTextContent('0')
    expect(screen.getByTestId(`cal-ecart_modules-${seule.id}`)).toHaveTextContent('0')
    // Une variante existe : le bouton ne dit plus « Créer une première ».
    expect(screen.getByTestId('cal-variante-nouvelle'))
      .toHaveTextContent('Nouvelle variante depuis la conception courante')
  })

  it('ACAL978 — la courante seule : rien à comparer côte à côte', async () => {
    mocks.comparer.mockResolvedValue({
      data: { ...CONTRAT_UNE_SEULE, retenue_id: null, lignes: [CONTRAT_UNE_SEULE.lignes[0]] },
    })
    rendre()
    expect(await screen.findByTestId('cal-cote-a-cote-vide')).toBeInTheDocument()
    expect(screen.getByTestId('cal-variantes-vide')).toBeInTheDocument()
    expect(screen.getByTestId('cal-variante-nouvelle'))
      .toHaveTextContent('Créer une variante depuis la conception courante')
  })

  it('une erreur de chargement s’affiche telle quelle', async () => {
    mocks.comparer.mockRejectedValue({ response: { data: { detail: 'Accès refusé.' } } })
    rendre()
    expect(await screen.findByRole('alert')).toHaveTextContent('Accès refusé.')
  })
})

/* ============================================================================
   CALX37 — CRÉER ET DUPLIQUER UNE VARIANTE.
   ----------------------------------------------------------------------------
   Un nom vide est refusé CÔTÉ ÉCRAN avant tout appel réseau ; créer puis
   dupliquer produit deux lignes DISTINCTES dans le comparatif (rechargé
   depuis le serveur) ; retenir l'une des deux dé-retient l'autre — le MÊME
   invariant du service que pour les variantes semées autrement.
   ========================================================================== */
describe('VariantesCompare (CALX37) — créer et dupliquer', () => {
  it('un nom vide est refusé AVANT tout appel réseau', async () => {
    rendre()
    fireEvent.click(await screen.findByTestId('cal-variante-nouvelle'))
    fireEvent.click(screen.getByTestId('cal-variante-confirmer'))

    expect(screen.getByTestId('cal-variante-nom-erreur')).toHaveTextContent('obligatoire')
    expect(mocks.layout).not.toHaveBeenCalled()
    expect(mocks.creerVariante).not.toHaveBeenCalled()
  })

  it('« Nouvelle variante depuis la conception courante » relit la conception puis crée', async () => {
    mocks.layout.mockResolvedValue({ data: { roof_layout: { zones: [{ id: 'a' }] } } })
    mocks.creerVariante.mockResolvedValue({ data: { id: 99, nom: 'Ma nouvelle variante' } })
    rendre()
    await screen.findByTestId('cal-tableau-variantes')

    fireEvent.click(screen.getByTestId('cal-variante-nouvelle'))
    fireEvent.change(screen.getByTestId('cal-variante-nom'), { target: { value: 'Ma nouvelle variante' } })
    fireEvent.click(screen.getByTestId('cal-variante-confirmer'))

    await waitFor(() => expect(mocks.layout).toHaveBeenCalledWith('1'))
    await waitFor(() => expect(mocks.creerVariante).toHaveBeenCalledWith('1', {
      nom: 'Ma nouvelle variante', roof_layout: { zones: [{ id: 'a' }] },
    }))
    // Le formulaire se ferme et le comparatif est rechargé (2 appels : montage + après création).
    await waitFor(() => expect(mocks.comparer).toHaveBeenCalledTimes(2))
    expect(screen.queryByTestId('cal-variante-formulaire')).not.toBeInTheDocument()
  })

  it('« Dupliquer cette variante » compose GET + POST avec le nom saisi', async () => {
    mocks.dupliquerVariante.mockResolvedValue({ data: { id: 98, nom: 'Copie retenue' } })
    rendre()
    await screen.findByTestId('cal-tableau-variantes')

    fireEvent.click(screen.getByTestId(`cal-variante-dupliquer-${RETENUE.id}`))
    fireEvent.change(screen.getByTestId('cal-variante-nom'), { target: { value: 'Copie retenue' } })
    fireEvent.click(screen.getByTestId('cal-variante-confirmer'))

    await waitFor(() => expect(mocks.dupliquerVariante)
      .toHaveBeenCalledWith('1', RETENUE.id, 'Copie retenue'))
    await waitFor(() => expect(mocks.comparer).toHaveBeenCalledTimes(2))
  })

  it('créer PUIS dupliquer produit deux lignes distinctes dans le comparatif', async () => {
    mocks.layout.mockResolvedValue({ data: { roof_layout: {} } })
    const NEUVE = { ...RETENUE, id: 201, nom: 'Neuve', est_retenue: false, ecart_modules: -1 }
    const COPIE = { ...RETENUE, id: 202, nom: 'Copie', est_retenue: false, ecart_modules: -1 }
    mocks.creerVariante.mockResolvedValue({ data: NEUVE })
    mocks.dupliquerVariante.mockResolvedValue({ data: COPIE })

    rendre()
    await screen.findByTestId('cal-tableau-variantes')

    // 1. Créer.
    fireEvent.click(screen.getByTestId('cal-variante-nouvelle'))
    fireEvent.change(screen.getByTestId('cal-variante-nom'), { target: { value: 'Neuve' } })
    mocks.comparer.mockResolvedValueOnce({ data: { ...CONTRAT, lignes: [...CONTRAT.lignes, NEUVE] } })
    fireEvent.click(screen.getByTestId('cal-variante-confirmer'))
    expect(await screen.findByTestId('cal-variante-dupliquer-201')).toBeInTheDocument()

    // 2. Dupliquer la variante retenue.
    mocks.comparer.mockResolvedValueOnce({
      data: { ...CONTRAT, lignes: [...CONTRAT.lignes, NEUVE, COPIE] },
    })
    fireEvent.click(screen.getByTestId(`cal-variante-dupliquer-${RETENUE.id}`))
    fireEvent.change(screen.getByTestId('cal-variante-nom'), { target: { value: 'Copie' } })
    fireEvent.click(screen.getByTestId('cal-variante-confirmer'))

    // Deux lignes DISTINCTES neuves, chacune avec son propre identifiant.
    expect(await screen.findByTestId('cal-variante-dupliquer-202')).toBeInTheDocument()
    expect(screen.getByTestId('cal-variante-dupliquer-201')).toBeInTheDocument()
  })

  it('retenir une variante créée dé-retient l’ancienne — même invariant du service', async () => {
    const NEUVE = { ...RETENUE, id: 301, nom: 'Neuve', est_retenue: false, ecart_modules: -1 }
    mocks.layout.mockResolvedValue({ data: { roof_layout: {} } })
    mocks.creerVariante.mockResolvedValue({ data: NEUVE })
    mocks.comparer.mockResolvedValueOnce({ data: CONTRAT })
    mocks.comparer.mockResolvedValueOnce({ data: { ...CONTRAT, lignes: [...CONTRAT.lignes, NEUVE] } })
    rendre()
    await screen.findByTestId('cal-tableau-variantes')

    fireEvent.click(screen.getByTestId('cal-variante-nouvelle'))
    fireEvent.change(screen.getByTestId('cal-variante-nom'), { target: { value: 'Neuve' } })
    fireEvent.click(screen.getByTestId('cal-variante-confirmer'))
    await screen.findByTestId('cal-variante-dupliquer-301')

    // Retenir la variante neuve : le serveur bascule, l'ancienne perd son badge.
    mocks.comparer.mockResolvedValueOnce({
      data: {
        ...CONTRAT,
        lignes: [...CONTRAT.lignes.map((l) => ({ ...l, est_retenue: false })),
          { ...NEUVE, est_retenue: true }],
      },
    })
    const ligneNeuve = screen.getByTestId('cal-variante-dupliquer-301').closest('td')
    fireEvent.click(within(ligneNeuve).getByRole('button', { name: 'Retenir' }))

    await waitFor(() => expect(mocks.retenirVariante).toHaveBeenCalledWith('1', 301, { suppressErrorToast: true }))
    await waitFor(() => expect(screen.getByTestId('cal-retenue-301')).toBeInTheDocument())
    expect(screen.queryByTestId(`cal-retenue-${RETENUE.id}`)).not.toBeInTheDocument()
  })
})

/* ============================================================================
   ACAL109 — état vide, renommer, supprimer, et la copie sans `resultat`.
   ========================================================================== */
describe('VariantesCompare (ACAL109)', () => {
  it('état vide : bouton de création depuis la conception', async () => {
    mocks.comparer.mockResolvedValue({ data: { ...CONTRAT, lignes: [], retenue_id: null } })
    mocks.layout.mockResolvedValue({ data: { roof_layout: { zones: [{ id: 'z' }] } } })
    mocks.creerVariante.mockResolvedValue({ data: { id: 5, nom: 'QA-ACAL-A' } })
    rendre()

    const bouton = await screen.findByTestId('cal-variante-nouvelle')
    expect(bouton).toHaveTextContent('Créer une variante depuis la conception courante')
    expect(screen.getByTestId('cal-variantes-vide')).toBeInTheDocument()
    fireEvent.click(bouton)
    fireEvent.change(screen.getByTestId('cal-variante-nom'), { target: { value: 'QA-ACAL-A' } })
    fireEvent.click(screen.getByTestId('cal-variante-confirmer'))
    await waitFor(() => expect(mocks.creerVariante).toHaveBeenCalledWith('1', {
      nom: 'QA-ACAL-A', roof_layout: { zones: [{ id: 'z' }] },
    }))
    expect(mocks.layout).toHaveBeenCalledWith('1')
  })

  it('Renommer appelle PATCH', async () => {
    mocks.modifierVariante.mockResolvedValue({ data: { id: AUTRE.id, nom: 'Nouveau nom' } })
    rendre()
    await screen.findByTestId('cal-tableau-variantes')

    fireEvent.click(screen.getByTestId(`cal-variante-renommer-${AUTRE.id}`))
    expect(screen.getByTestId('cal-variante-nom')).toHaveValue(AUTRE.nom)
    fireEvent.change(screen.getByTestId('cal-variante-nom'), { target: { value: 'Nouveau nom' } })
    fireEvent.click(screen.getByTestId('cal-variante-confirmer'))

    await waitFor(() => expect(mocks.modifierVariante)
      .toHaveBeenCalledWith('1', AUTRE.id, { nom: 'Nouveau nom' }))
    await waitFor(() => expect(mocks.comparer).toHaveBeenCalledTimes(2))
  })

  it('Supprimer la retenue affiche le refus serveur', async () => {
    const refus = `« ${RETENUE.nom} » est la variante RETENUE : retenez-en une autre avant de la supprimer.`
    mocks.supprimerVariante.mockRejectedValue({ response: { status: 400, data: { retenue: refus } } })
    rendre()
    await screen.findByTestId('cal-tableau-variantes')

    fireEvent.click(screen.getByTestId(`cal-variante-supprimer-${RETENUE.id}`))
    expect(mocks.supprimerVariante).not.toHaveBeenCalled()
    fireEvent.click(screen.getByTestId(`cal-variante-supprimer-confirmer-${RETENUE.id}`))

    await waitFor(() => expect(mocks.supprimerVariante).toHaveBeenCalledWith('1', RETENUE.id))
    expect(await screen.findByText(refus)).toBeInTheDocument()
  })

  it('dupliquer n’envoie pas resultat', async () => {
    const { corpsDeCopieVariante } = await vi.importActual('../../api/calepinageApi')
    const corps = corpsDeCopieVariante(
      { nom: 'A', roof_layout: { zones: [] }, resultat: { production: { p50: 1 } } }, '')
    expect(corps).toEqual({ nom: 'A (copie)', roof_layout: { zones: [] } })
    expect('resultat' in corps).toBe(false)
  })
})

/* ============================================================================
   ACAL113 — « Simuler cette variante » et les badges de fraîcheur / source.
   ========================================================================== */
describe('VariantesCompare (ACAL113)', () => {
  it('Simuler cette variante poste variante_id', async () => {
    mocks.simulerVariante.mockResolvedValue({ data: { job_id: 7, variante_id: AUTRE.id } })
    mocks.resultatJob.mockResolvedValue({ data: { job_id: 7, statut: 'done', resultat: {} } })
    rendre()
    await screen.findByTestId('cal-tableau-variantes')

    fireEvent.click(screen.getByTestId(`cal-variante-simuler-${AUTRE.id}`))
    await waitFor(() => expect(mocks.simulerVariante).toHaveBeenCalledWith('1', AUTRE.id))
    await waitFor(() => expect(mocks.resultatJob).toHaveBeenCalledWith(7))
  })

  it('badge périmée et mesures du dessin', async () => {
    const lignes = CONTRAT.lignes.map((l) => {
      if (l.id === AUTRE.id) return { ...l, simulation_perimee: true }
      if (l.id === NON_SIMULEE.id) return { ...l, simulee: false, source_mesures: 'conception' }
      return l
    })
    mocks.comparer.mockResolvedValue({ data: { ...CONTRAT, lignes } })
    rendre()
    await screen.findByTestId('cal-tableau-variantes')

    expect(screen.getAllByTestId(`cal-badge-perimee-${AUTRE.id}`)[0])
      .toHaveTextContent('simulation périmée')
    expect(screen.getAllByTestId(`cal-badge-dessin-${NON_SIMULEE.id}`)[0])
      .toHaveTextContent('mesures du dessin')
    expect(screen.queryByTestId(`cal-badge-perimee-${RETENUE.id}`)).toBeNull()
  })
})

/* ============================================================================
   ACAL600 — la ligne « Module » (ACAL595 : `lignes[].module`), et « à re-poser ».
   ========================================================================== */
describe('VariantesCompare (ACAL600) — ligne Module', () => {
  it('ligne Module : B, mixte, —', async () => {
    const B = CONTRAT.lignes.find((l) => l.module && !l.module.mixte
      && l !== AUTRE && l !== NON_SIMULEE)
    expect(B, 'le contrat sert un module complet sur une ligne').toBeTruthy()
    const lignes = CONTRAT.lignes.map((l) => {
      if (l.id === AUTRE.id) return { ...l, module: { mixte: true } }
      if (l.id === NON_SIMULEE.id) {
        return { ...l, module: null, nom: `${l.nom} — à re-poser` }
      }
      return l
    })
    mocks.comparer.mockResolvedValue({ data: { ...CONTRAT, lignes } })
    rendre()
    await screen.findByTestId('cal-tableau-variantes')

    const cellule = (l) => screen.getByTestId(`cal-module-${l.courante ? 'courante' : l.id}`)
    expect(cellule(B)).toHaveTextContent(B.module.libelle)
    expect(cellule(B)).toHaveTextContent('580 Wc')
    expect(cellule(AUTRE)).toHaveTextContent('mixte')
    expect(cellule(NON_SIMULEE)).toHaveTextContent('—')
    expect(cellule(NON_SIMULEE))
      .toHaveTextContent('À re-poser dans l’atelier : les cotes du module diffèrent')
    expect(cellule(B)).not.toHaveTextContent('re-poser')
  })
})

/* ACAL884 — les hypothèses comparées, servies (`hypotheses`, ACAL883).
   Mutant : ignorer `identiques` ⇒ échec. */
describe('VariantesCompare — hypothèses comparées (ACAL884)', () => {
  const servirHypotheses = (hypotheses) => mocks.comparer.mockResolvedValue({ data: { ...CONTRAT, hypotheses } })

  it('identiques ⇒ ligne « mêmes hypothèses »', async () => {
    servirHypotheses({ ...CONTRAT.hypotheses, identiques: true, differences: [] })
    rendre()
    expect(await screen.findByTestId('acal884-identiques'))
      .toHaveTextContent('Mêmes hypothèses de pertes et de météo pour toutes les variantes comparées')
    expect(screen.queryByText('Hypothèses différentes :')).toBeNull()
  })

  it('différences ⇒ liste nommée, valeurs servies, non simulées comptées', async () => {
    rendre()
    const bloc = await screen.findByTestId('cal-variantes-hypotheses')
    expect(within(bloc).getByText('Hypothèses différentes :')).toBeInTheDocument()
    const [d] = CONTRAT.hypotheses.differences
    const ligne = within(bloc).getByTestId(`acal884-difference-${d.cle}`)
    expect(ligne).toHaveTextContent(d.libelle)
    for (const [id, v] of Object.entries(d.valeurs)) {
      expect(ligne).toHaveTextContent(`${v} chez ${CONTRAT.lignes.find((l) => String(l.id) === id).nom}`)
    }
    expect(within(bloc).getByTestId('acal884-non-simulees'))
      .toHaveTextContent(`${CONTRAT.lignes.filter((l) => !l.simulee).length} variante(s) non comparée(s)`)
  })

  it('null ⇒ rien', async () => {
    servirHypotheses(exempleContrat('calepinage', 'variantes_comparer', 'exemple_vide').hypotheses)
    rendre()
    await screen.findByTestId('cal-tableau-variantes')
    expect(screen.queryByTestId('cal-variantes-hypotheses')).toBeNull()
  })
})

/* ACAL878 — chaque rangée de chiffres du comparatif porte son « ? » (registre).
   Mutant : retirer une entrée de la famille ⇒ la garde d'ACAL872 échoue. */
describe('VariantesCompare — « ? » du comparatif (ACAL878)', () => {
  it('chaque colonne de chiffres porte un « ? »', async () => {
    rendre()
    const tableau = await screen.findByTestId('cal-tableau-variantes')
    const grandeurs = [...tableau.querySelectorAll('th [data-grandeur]')].map((b) => b.getAttribute('data-grandeur'))
    expect(grandeurs).toEqual(['comparatif.modules', 'comparatif.kwc', 'comparatif.ecart', 'comparatif.ecart', 'comparatif.p50_kwh'])
  })
})
