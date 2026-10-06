import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

/* ============================================================================
   CALX18 — L'ÉDITEUR DES POSTES DE PERTES.
   ----------------------------------------------------------------------------
   CE QUE CE TEST TIENT :
     * une ligne par poste du catalogue SERVI — le poste mensuel (« salissure »)
       en DOUZE champs, les autres en un pourcentage + une source ;
     * un poste ENTAMÉ (un pourcentage tapé) sans source est REFUSÉ avant tout
       envoi réseau, le champ pointé — règle fondateur du 08/09/2026 ;
     * le refus 400 du serveur (qui NOMME son champ) atterrit SOUS le même
       poste ;
     * le total affiché est celui des SEULS postes saisis, avec la mention
       exacte exigée par la tâche.
   ========================================================================== */

const CATALOGUE_TEST = [
  { poste: 'iam', libelle: 'Incidence (IAM)',
    reference: 'PVsyst — array and system losses', mensuel: false },
  { poste: 'salissure', libelle: 'Salissure',
    reference: 'PVsyst — soiling loss', mensuel: true },
  { poste: 'onduleur', libelle: 'Rendement onduleur',
    reference: 'PVsyst — inverter loss', mensuel: false },
]

/* ACAL136 — les réponses viennent de `contract_samples/calepinage_pertes.json`
   (jamais écrites à la main) ; le catalogue (clé servie par la vue, absente de
   l'échantillon) est celui du test. */
const CONTRAT = exempleContrat('calepinage', 'calepinage_pertes')
const CONTRAT_VIDE = exempleContrat('calepinage', 'calepinage_pertes', 'exemple_non_simulable')

const REPONSE_VIDE = {
  ...CONTRAT_VIDE,
  postes: [],
  catalogue: CATALOGUE_TEST,
}

const pertes = vi.fn()
const enregistrerPertes = vi.fn()
vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      pertes: (...a) => pertes(...a),
      enregistrerPertes: (...a) => enregistrerPertes(...a),
    },
  },
}))

const { default: PanneauPertes } = await import('./PanneauPertes')

const rendre = () => render(
  <MemoryRouter><PanneauPertes calepinageId={1} /></MemoryRouter>,
)

const champPct = (poste) => screen.getByTestId(`cal-pertes-champ-${poste}`).querySelector('input')
const champSource = (poste) => screen.getByTestId(`cal-pertes-source-${poste}`).querySelector('select')

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

describe('CALX18 — une ligne par poste du catalogue servi', () => {
  it('monte une ligne par poste, la salissure en douze champs mensuels', async () => {
    pertes.mockResolvedValue({ data: REPONSE_VIDE })
    rendre()

    for (const item of CATALOGUE_TEST) {
      expect(await screen.findByTestId(`cal-pertes-poste-${item.poste}`)).toBeInTheDocument()
    }
    expect(champPct('iam')).toBeInTheDocument()
    expect(champSource('iam')).toBeInTheDocument()
    for (let i = 0; i < 12; i += 1) {
      expect(screen.getByTestId(`cal-pertes-salissure-mois-${i}`)).toBeInTheDocument()
    }
    // Aucun pas, aucune borne : la saisie n'est jamais snappée ni refusée.
    expect(champPct('iam')).toHaveAttribute('step', 'any')
  })
})

describe('CALX18 — un poste sans source est refusé AVANT tout envoi', () => {
  it('pointe le champ fautif et n’appelle jamais le serveur', async () => {
    pertes.mockResolvedValue({ data: REPONSE_VIDE })
    rendre()
    await screen.findByTestId('cal-pertes-poste-iam')

    fireEvent.change(champPct('iam'), { target: { value: '3.5' } })
    // Aucune source choisie pour « iam ».
    fireEvent.click(screen.getByTestId('cal-pertes-enregistrer'))

    const erreur = await screen.findByTestId('cal-pertes-erreur-iam')
    expect(erreur).toHaveTextContent('source')
    expect(screen.getByTestId('cal-pertes-bandeau')).toHaveTextContent('Incidence (IAM)')
    expect(screen.getByTestId('cal-pertes-bandeau').querySelector('a[href="#cal-pertes-iam"]'))
      .toBeTruthy()
    expect(enregistrerPertes).not.toHaveBeenCalled()
  })
})

describe('CALX18 — le refus 400 du serveur atterrit SOUS le bon poste', () => {
  it('un poste valide envoyé, refusé par le serveur, porte son message', async () => {
    pertes.mockResolvedValue({ data: REPONSE_VIDE })
    enregistrerPertes.mockRejectedValue({
      response: { data: { iam: ['Le pourcentage du poste « iam » est illisible.'] } },
    })
    rendre()
    await screen.findByTestId('cal-pertes-poste-iam')

    fireEvent.change(champPct('iam'), { target: { value: '3.5' } })
    fireEvent.change(champSource('iam'), { target: { value: 'pvgis' } })
    fireEvent.click(screen.getByTestId('cal-pertes-enregistrer'))

    expect(await screen.findByTestId('cal-pertes-erreur-iam'))
      .toHaveTextContent('illisible')
    expect(enregistrerPertes).toHaveBeenCalledTimes(1)
  })
})

describe('CALX18 — le total est celui des postes SAISIS, avec sa mention', () => {
  it('additionne les postes saisis et affiche la mention exacte', async () => {
    pertes.mockResolvedValue({ data: REPONSE_VIDE })
    rendre()
    await screen.findByTestId('cal-pertes-poste-iam')

    fireEvent.change(champPct('iam'), { target: { value: '2' } })
    fireEvent.change(champSource('iam'), { target: { value: 'pvgis' } })
    fireEvent.change(champPct('onduleur'), { target: { value: '2.5' } })
    fireEvent.change(champSource('onduleur'), { target: { value: 'fiche' } })
    // « salissure » reste vide : le total ne le compte pas.

    await waitFor(() => {
      expect(screen.getByTestId('cal-pertes-total')).toHaveTextContent('4.50 %')
    })
    expect(screen.getByTestId('cal-pertes-mention')).toHaveTextContent(
      'ces postes ne sont plus transmis à PVGIS : la chaîne de pertes les '
      + 'applique un à un (lot 3) ; un poste devenu calculable par la chaîne '
      + 'y sera écarté et le dira',
    )
  })
})

/* ACAL136 — le statut de chaque poste, le forçage signé, et l'aller-retour qui
   ne perd rien (poste hors catalogue, source null, références). */
describe('ACAL136 — statuts, forçage signé, aller-retour sans perte', () => {
  // Le catalogue du test ne connaît que `salissure` ; chaque autre poste du
  // contrat est « hors catalogue » — il doit survivre à l'enregistrement.
  const reponse = (extra = []) => ({
    data: {
      ...CONTRAT,
      postes: [...CONTRAT.postes, ...extra],
      catalogue: [CATALOGUE_TEST[1]],
    },
  })
  const attendu = (p) => {
    const poste = {
      poste: p.poste, libelle: p.libelle, pct: p.pct, source: p.source,
      reference: p.reference ?? '', mensuel: p.mensuel,
    }
    if (p.force) { poste.force = true; poste.motif_force = p.motif_force }
    return poste
  }

  it('aller-retour : hors catalogue et source null conservés', async () => {
    const neige = {
      mensuel: null, force: false, motif_force: '', etape: null, raison: '',
      poste: 'neige', libelle: 'Neige', pct: 1.5, source: null, reference: null, statut: 'non_source',
    }
    pertes.mockResolvedValue(reponse([neige]))
    enregistrerPertes.mockResolvedValue({ data: { ...CONTRAT, postes: CONTRAT.postes } })
    rendre()
    await screen.findByTestId('cal-pertes-poste-neige')

    fireEvent.click(screen.getByTestId('cal-pertes-enregistrer'))

    await waitFor(() => expect(enregistrerPertes).toHaveBeenCalledTimes(1))
    expect(screen.queryByTestId('cal-pertes-bandeau')).toBeNull()
    expect(enregistrerPertes.mock.calls[0][1]).toEqual({
      postes: [...CONTRAT.postes, neige].map(attendu),
    })
  })

  it('étape calculante en lecture seule', async () => {
    pertes.mockResolvedValue(reponse())
    rendre()
    await screen.findByTestId('cal-pertes-poste-temperature')

    expect(screen.getByTestId('acal136-statut-temperature')).toHaveTextContent(
      "Calculé par l'étape Thermique — votre saisie n'est pas appliquée",
    )
    expect(champPct('temperature')).toBeDisabled()
    expect(champSource('temperature')).toBeDisabled()
    expect(screen.getByTestId('acal136-forcer-temperature')).toBeInTheDocument()
    // Un poste appliqué reste éditable.
    expect(champPct('soiling')).not.toBeDisabled()
  })

  it('forcer exige un motif', async () => {
    pertes.mockResolvedValue(reponse())
    enregistrerPertes.mockResolvedValue({ data: { ...CONTRAT } })
    rendre()
    await screen.findByTestId('cal-pertes-poste-temperature')

    fireEvent.click(screen.getByTestId('acal136-forcer-temperature'))
    // Forcé : la ligne redevient éditable, mais le motif est obligatoire.
    expect(champPct('temperature')).not.toBeDisabled()
    fireEvent.click(screen.getByTestId('cal-pertes-enregistrer'))
    expect(await screen.findByTestId('cal-pertes-erreur-temperature')).toHaveTextContent('motif')
    expect(enregistrerPertes).not.toHaveBeenCalled()

    fireEvent.change(
      screen.getByTestId('acal136-motif-temperature').querySelector('input'),
      { target: { value: 'Mesure sur site du 12/03' } },
    )
    fireEvent.click(screen.getByTestId('cal-pertes-enregistrer'))

    await waitFor(() => expect(enregistrerPertes).toHaveBeenCalledTimes(1))
    const envoye = enregistrerPertes.mock.calls[0][1].postes.find((p) => p.poste === 'temperature')
    expect(envoye).toMatchObject({
      force: true, motif_force: 'Mesure sur site du 12/03', source: 'fiche', pct: 8,
    })
  })

  it('remplace le réglage société affiché', async () => {
    pertes.mockResolvedValue(reponse())
    rendre()
    await screen.findByTestId('cal-pertes-poste-wiring')

    expect(screen.getByTestId('acal136-statut-wiring'))
      .toHaveTextContent(/Remplace le réglage société \(2 %\)/)
  })

  it('hors chaîne : la raison servie est affichée', async () => {
    pertes.mockResolvedValue(reponse())
    rendre()
    await screen.findByTestId('cal-pertes-poste-degradation')

    expect(screen.getByTestId('acal136-statut-degradation'))
      .toHaveTextContent("Hors chaîne : N'agit pas sur la production de l'année 1.")
  })

  it('une ligne éditée sans source reste refusée, une ligne intacte à source null passe', async () => {
    pertes.mockResolvedValue(reponse())
    rendre()
    await screen.findByTestId('cal-pertes-poste-availability')

    // `availability` : source null servie — intacte, aucun refus.
    fireEvent.click(screen.getByTestId('cal-pertes-enregistrer'))
    await waitFor(() => expect(enregistrerPertes).toHaveBeenCalledTimes(1))
    expect(screen.queryByTestId('cal-pertes-erreur-availability')).toBeNull()

    // Éditée : le pourcentage change, toujours sans source → refus nommé.
    enregistrerPertes.mockClear()
    fireEvent.change(champPct('availability'), { target: { value: '2' } })
    fireEvent.click(screen.getByTestId('cal-pertes-enregistrer'))
    expect(await screen.findByTestId('cal-pertes-erreur-availability')).toHaveTextContent('source')
    expect(enregistrerPertes).not.toHaveBeenCalled()
  })
})
