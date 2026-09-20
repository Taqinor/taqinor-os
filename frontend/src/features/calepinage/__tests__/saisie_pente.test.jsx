import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ============================================================================
   CAL58 — LES TROIS MODES DONNENT LA MÊME PENTE, ET DISENT D'OÙ ELLE VIENT.
   ----------------------------------------------------------------------------
   La promesse de la tâche est chiffrée : « les trois modes donnent la même
   pente à 0,1° près sur un cas de test ». Ce fichier CONFRONTE les trois sur
   le même toit (30°), puis vérifie la règle fondateur du dépôt : aucune
   conversion n'arrondit ni ne refuse une saisie.
   ========================================================================== */

const layout = vi.fn()
const enregistrerLayout = vi.fn()
vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      layout: (...a) => layout(...a),
      enregistrerLayoutCalepinage: (...a) => enregistrerLayout(...a),
    },
  },
}))

const {
  default: SaisiePente, penteDepuisDegres, penteDepuisPourcentage,
  penteDepuisCotes, pourcentageDepuisPente, penteRetenue,
} = await import('../SaisiePente')

beforeEach(() => {
  vi.clearAllMocks()
  layout.mockResolvedValue({ data: { roof_layout: {} } })
})
afterEach(() => { cleanup() })

/* ── 1. LE CAS DE TEST : le MÊME toit, par les trois chemins ───────────── */

describe('CAL58 — un toit à 30°, saisi de trois façons', () => {
  // tan(30°) = 0,57735… : 57,735 % de pente, ou 5,7735 m de faîtage sur 10 m
  // de portée. Trois mesures du MÊME toit.
  const ATTENDU = 30

  it('les trois modes convergent à 0,1° près', () => {
    expect(penteDepuisDegres(30)).toBeCloseTo(ATTENDU, 1)
    expect(penteDepuisPourcentage(57.735)).toBeCloseTo(ATTENDU, 1)
    expect(penteDepuisCotes(10, 5.7735)).toBeCloseTo(ATTENDU, 1)

    const ecarts = [
      penteDepuisDegres(30), penteDepuisPourcentage(57.735),
      penteDepuisCotes(10, 5.7735),
    ]
    expect(Math.max(...ecarts) - Math.min(...ecarts)).toBeLessThan(0.1)
  })

  it('la réciproque boucle : 30° ⇒ 57,7 % ⇒ 30°', () => {
    const pct = pourcentageDepuisPente(30)
    expect(pct).toBeCloseTo(57.735, 2)
    expect(penteDepuisPourcentage(pct)).toBeCloseTo(30, 10)
  })

  it('100 % vaut exactement 45° — le repère des couvreurs', () => {
    expect(penteDepuisPourcentage(100)).toBeCloseTo(45, 10)
  })
})

describe('CAL58 — aucune conversion n’arrondit ni ne refuse une saisie', () => {
  it('une pente hors des puces historiques passe telle quelle', () => {
    // 2° et 62,4° sont hors du curseur 5-45° de l'écran de devis : ici, aucun
    // snap, aucun refus.
    expect(penteDepuisDegres(2)).toBe(2)
    expect(penteDepuisDegres(62.4)).toBe(62.4)
    expect(penteDepuisDegres('3.7')).toBe(3.7)
  })

  it('la valeur rendue n’est pas arrondie : elle garde ses décimales', () => {
    const exacte = penteDepuisPourcentage(57.735)
    expect(exacte).not.toBe(30)          // ce n'est pas exactement 30
    expect(Math.abs(exacte - 30)).toBeLessThan(0.001)
    // Et surtout : la valeur n'a pas été ramenée à un dixième.
    expect(String(exacte).length).toBeGreaterThan(4)
  })

  it('une contre-pente (pourcentage négatif) est acceptée, pas refusée', () => {
    expect(penteDepuisPourcentage(-57.735)).toBeCloseTo(-30, 1)
  })
})

describe('CAL58 — l’inconnu reste inconnu : jamais un 0° de remplissage', () => {
  it('sans saisie, aucune pente', () => {
    expect(penteDepuisDegres('')).toBeNull()
    expect(penteDepuisPourcentage(null)).toBeNull()
    expect(penteDepuisCotes(null, 4)).toBeNull()
    expect(penteRetenue('degres', {})).toBeNull()
  })

  it('une portée nulle ne produit pas une pente', () => {
    expect(penteDepuisCotes(0, 5)).toBeNull()
  })

  it('le mode ACTIF tranche — deux modes remplis ne se moyennent pas', () => {
    const saisie = { degres: '10', pourcentage: '100' }
    expect(penteRetenue('degres', saisie).degres).toBe(10)
    expect(penteRetenue('pourcentage', saisie).degres).toBeCloseTo(45, 10)
  })
})

/* ── 2. L'ÉCRAN : la valeur affiche TOUJOURS d'où elle vient ───────────── */

const rendre = (props = {}) => render(
  <MemoryRouter><SaisiePente calepinageId={7} {...props} /></MemoryRouter>,
)

describe('CAL58 — l’écran', () => {
  it('affiche la pente ET sa provenance, mode par mode', async () => {
    rendre()
    await screen.findByTestId('cal-pente')

    fireEvent.change(screen.getByLabelText(/Pente \(°\)/), { target: { value: '30' } })
    expect(screen.getByTestId('cal-pente-valeur')).toHaveTextContent('30.0')
    expect(screen.getByTestId('cal-pente-source')).toHaveTextContent('degrés')

    fireEvent.click(screen.getByTestId('cal-pente-mode-pourcentage'))
    fireEvent.change(screen.getByLabelText(/Pente \(%\)/), { target: { value: '57.735' } })
    expect(screen.getByTestId('cal-pente-valeur')).toHaveTextContent('30.0')
    expect(screen.getByTestId('cal-pente-source')).toHaveTextContent('pourcentage')

    fireEvent.click(screen.getByTestId('cal-pente-mode-cotes'))
    fireEvent.change(screen.getByLabelText(/Portée/), { target: { value: '10' } })
    fireEvent.change(screen.getByLabelText(/Hauteur de faîtage/), { target: { value: '5.7735' } })
    expect(screen.getByTestId('cal-pente-valeur')).toHaveTextContent('30.0')
    expect(screen.getByTestId('cal-pente-source')).toHaveTextContent('cotes')
  })

  it('sans mesure : « — » et « aucune pente mesurée », jamais 0°', async () => {
    rendre()
    await screen.findByTestId('cal-pente')
    expect(screen.getByTestId('cal-pente-valeur')).toHaveTextContent('—')
    expect(screen.getByTestId('cal-pente-valeur')).not.toHaveTextContent('0')
    expect(screen.getByTestId('cal-pente-source')).toHaveTextContent('aucune pente mesurée')
  })

  it('les champs n’imposent ni pas ni borne (jamais de snap)', async () => {
    rendre()
    await screen.findByTestId('cal-pente')
    const champ = screen.getByLabelText(/Pente \(°\)/)
    expect(champ).toHaveAttribute('step', 'any')
    expect(champ).not.toHaveAttribute('min')
    expect(champ).not.toHaveAttribute('max')
  })

  it('enregistre la valeur EXACTE, pas son arrondi d’affichage', async () => {
    enregistrerLayout.mockResolvedValue({ data: {} })
    rendre()
    await screen.findByTestId('cal-pente')

    fireEvent.click(screen.getByTestId('cal-pente-mode-pourcentage'))
    fireEvent.change(screen.getByLabelText(/Pente \(%\)/), { target: { value: '57.735' } })
    fireEvent.click(screen.getByTestId('cal-pente-enregistrer'))

    await waitFor(() => expect(enregistrerLayout).toHaveBeenCalledTimes(1))
    const [, document] = enregistrerLayout.mock.calls[0]
    expect(document.penteSource).toBe('pourcentage')
    expect(document.penteDeg).not.toBe(30)          // pas l'arrondi
    expect(document.penteDeg).toBeCloseTo(30, 3)
  })

  it('sans pente mesurée, rien n’est enregistré — surtout pas un 0°', async () => {
    rendre()
    await screen.findByTestId('cal-pente')
    fireEvent.click(screen.getByTestId('cal-pente-enregistrer'))
    expect(enregistrerLayout).not.toHaveBeenCalled()
    expect(screen.getByTestId('cal-pente-message'))
      .toHaveTextContent('toiture plate')
  })

  it('RELIT la pente déjà enregistrée dans la conception', async () => {
    layout.mockResolvedValue({
      data: { roof_layout: { penteDeg: 22.5, penteSource: 'degres' } },
    })
    rendre()
    expect(await screen.findByLabelText(/Pente \(°\)/)).toHaveValue(22.5)
    expect(screen.getByTestId('cal-pente-valeur')).toHaveTextContent('22.5')
  })
})

describe('CAL58 — l’écran est ATTEIGNABLE', () => {
  it('le module déclare la route `/calepinage/:id/pente` avec ses rôles', async () => {
    const { default: config } = await import('../module.config.jsx')
    const route = config.routes.find((r) => r.path === '/calepinage/:id/pente')
    expect(route, 'route de saisie de pente absente du module').toBeTruthy()
    expect(Array.isArray(route.roles) && route.roles.length > 0).toBe(true)
  })
})
