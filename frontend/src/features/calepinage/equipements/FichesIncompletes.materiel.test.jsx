import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

/* ============================================================================
   ACAL264 — LE PANNEAU AFFICHE LE MATÉRIEL RÉELLEMENT UTILISÉ PAR LE CALCUL.
   ----------------------------------------------------------------------------
   Les familles du panneau sont celles du DEVIS (`equipements/`) ; le calcul,
   lui, utilise le matériel RÉSOLU servi par `GET entree-electrique/`
   (`materiel`). Les deux charges utiles viennent des CONTRATS COMMITTÉS —
   jamais d'un objet écrit à la main pour la forme.
   ========================================================================== */

const AGREGAT = exempleContrat('calepinage', 'calepinage_equipements')
const ENTREE = exempleContrat('calepinage', 'calepinage_entree_electrique')

const equipements = vi.fn()
const entreeElectrique = vi.fn()
vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      equipements: (...a) => equipements(...a),
      entreeElectrique: (...a) => entreeElectrique(...a),
    },
  },
}))

const { default: FichesIncompletes } = await import('./FichesIncompletes')

const rendre = () => render(
  <MemoryRouter><FichesIncompletes calepinageId={7} /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

describe('ACAL264 — matériel utilisé par le calcul', () => {
  it('affiche le module et l’onduleur RÉSOLUS, avec leur provenance', async () => {
    equipements.mockResolvedValue({ data: AGREGAT })
    entreeElectrique.mockResolvedValue({ data: ENTREE })
    rendre()

    expect(await screen.findByTestId('cal-fiches-materiel-calcul')).toBeInTheDocument()
    expect(entreeElectrique).toHaveBeenCalledWith(7)
    const module = screen.getByTestId('cal-fiches-materiel-module')
    expect(module).toHaveTextContent(ENTREE.materiel.module.designation)
    expect(module).toHaveTextContent('désigné dans l’entrée électrique')
    const onduleur = screen.getByTestId('cal-fiches-materiel-onduleur')
    expect(onduleur).toHaveTextContent(ENTREE.materiel.onduleur.designation)
    expect(onduleur).toHaveTextContent('ligne du devis lié')
    expect(screen.getByTestId('cal-fiches-materiel-optimiseur')).toHaveTextContent('aucun')
  })

  it('signale l’écart quand le calcul n’utilise pas le module du devis', async () => {
    const agregat = {
      ...AGREGAT,
      panneau: { ...AGREGAT.panneau, produit: 1, designation: 'Module du devis' },
    }
    const entree = {
      ...ENTREE,
      materiel: {
        ...ENTREE.materiel,
        module: { ...ENTREE.materiel.module, produit_id: 2, designation: 'Module posé' },
      },
    }
    equipements.mockResolvedValue({ data: agregat })
    entreeElectrique.mockResolvedValue({ data: entree })
    rendre()

    const ecart = await screen.findByTestId('cal-fiches-ecart-module')
    expect(ecart).toHaveTextContent('Module posé')
    expect(ecart).toHaveTextContent('Module du devis')
  })

  it('aucun écart affiché quand le calcul utilise le module du devis', async () => {
    const agregat = { ...AGREGAT, panneau: { ...AGREGAT.panneau, produit: 5 } }
    const entree = {
      ...ENTREE,
      materiel: { ...ENTREE.materiel, module: { ...ENTREE.materiel.module, produit_id: 5 } },
    }
    equipements.mockResolvedValue({ data: agregat })
    entreeElectrique.mockResolvedValue({ data: entree })
    rendre()

    expect(await screen.findByTestId('cal-fiches-materiel-calcul')).toBeInTheDocument()
    expect(screen.queryByTestId('cal-fiches-ecart-module')).toBeNull()
  })

  it('un pan sans fiche est nommé avec la fiche utilisée', async () => {
    equipements.mockResolvedValue({ data: AGREGAT })
    entreeElectrique.mockResolvedValue({ data: ENTREE })
    rendre()

    const [a, b] = ENTREE.materiel.modules_par_pan
    expect(await screen.findByTestId(`cal-fiches-module-pan-${a.pan}`)).toHaveTextContent(a.designation)
    expect(screen.getByTestId(`cal-fiches-module-pan-${a.pan}`)).not.toHaveTextContent('sans fiche')
    const ligne = screen.getByTestId(`cal-fiches-module-pan-${b.pan}`)
    expect(ligne).toHaveTextContent(`Pan ${b.pan}`)
    expect(ligne).toHaveTextContent(b.designation)
    expect(ligne).toHaveTextContent('sans fiche : chaîné avec la fiche du module par défaut')
  })

  it('un champ mono-module n’ajoute aucune ligne par pan', async () => {
    const [a] = ENTREE.materiel.modules_par_pan
    equipements.mockResolvedValue({ data: AGREGAT })
    entreeElectrique.mockResolvedValue({
      data: { ...ENTREE, materiel: { ...ENTREE.materiel, modules_par_pan: [a] } },
    })
    rendre()

    expect(await screen.findByTestId('cal-fiches-materiel-calcul')).toBeInTheDocument()
    expect(screen.queryByTestId('cal-fiches-modules-par-pan')).toBeNull()
  })

  it('un échec de lecture du matériel n’éteint pas le panneau', async () => {
    equipements.mockResolvedValue({ data: AGREGAT })
    entreeElectrique.mockRejectedValue(new Error('réseau'))
    rendre()

    expect(await screen.findByTestId('cal-fiches-incompletes')).toBeInTheDocument()
    expect(screen.queryByTestId('cal-fiches-materiel-calcul')).toBeNull()
  })
})
