import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

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

const REPONSE_VIDE = {
  calepinage: 1,
  pertes: [],
  total_pct: null,
  postes_non_sources: [],
  simulable: false,
  motif_non_simulable: 'Aucun poste de perte n’est renseigné : le module '
    + 'passe TOUJOURS à PVGIS la somme explicite de ses postes et ne '
    + 'suppose jamais une perte par défaut.',
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
