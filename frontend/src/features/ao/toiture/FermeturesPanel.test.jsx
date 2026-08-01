import { describe, it, expect, vi } from 'vitest'
import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import FermeturesPanel from './FermeturesPanel'

/* AOF86 — on rejoue les fermetures d'un relevé réel avec LEURS tolérances
   (0,02 / 0,05 / 0,25), on vérifie que le calepinage est BLOQUÉ tant qu'une
   chaîne reste en écart non arbitré, et que le motif d'acceptation est persisté
   et visible. */

const RELEVE = [
  {
    id: 'c1',
    nom: 'Façade sud',
    tolerance: 0.02,
    coteMesuree: 25.62,
    segments: [
      { id: 'a1', libelle: 'A', valeur: 4.1 },
      { id: 'a2', libelle: 'B', valeur: 8.82 },
      { id: 'a3', libelle: 'C', valeur: 12.7 },
    ],
  },
  {
    id: 'c2',
    nom: 'Longueur bâtiment',
    tolerance: 0.05,
    coteMesuree: 51.1,
    segments: [
      { id: 'b1', libelle: 'Corps', valeur: 42.28 },
      { id: 'b2', libelle: 'Cage', valeur: 8.82 },
    ],
  },
  {
    id: 'c3',
    nom: 'Développé arc',
    tolerance: 0.25,
    coteMesuree: 68.05,
    segments: [
      { id: 'd1', libelle: 'T1', valeur: 22.6 },
      { id: 'd2', libelle: 'T2', valeur: 22.75 },
      { id: 'd3', libelle: 'T3', valeur: 22.4 },
    ],
  },
]

// Harnais : le panneau est contrôlé — l'atelier détient les chaînes.
function Harnais({ initial = RELEVE, onCalepiner = () => {}, espion }) {
  const [chaines, setChaines] = useState(initial)
  return (
    <FermeturesPanel
      chaines={chaines}
      onChaines={(suivantes) => {
        espion?.(suivantes)
        setChaines(suivantes)
      }}
      onCalepiner={onCalepiner}
    />
  )
}

const ligne = (id) => document.querySelector(`[data-ao-fermeture="${id}"]`)
const statut = (id) => ligne(id).getAttribute('data-ao-fermeture-statut')
const residu = (id) => document.querySelector(`[data-ao-fermeture-residu="${id}"]`).textContent

describe('FermeturesPanel (AOF86)', () => {
  it('rejoue les fermetures du relevé à l’identique, chacune avec SA tolérance', () => {
    render(<Harnais />)
    // 4,10 + 8,82 + 12,70 = 25,62 → referme à 0 dans une tolérance de 2 cm.
    expect(statut('c1')).toBe('OK')
    expect(residu('c1')).toBe('0.000')
    // 42,28 + 8,82 = 51,10 → referme dans une tolérance de 5 cm.
    expect(statut('c2')).toBe('OK')
    expect(residu('c2')).toBe('0.000')
    // 22,60 + 22,75 + 22,40 = 67,75 pour 68,05 mesurés → 30 cm d'écart, au-delà
    // des 25 cm tolérés sur un développé d'arc.
    expect(statut('c3')).toBe('ECART')
    expect(residu('c3')).toBe('0.300')
    expect(
      document.querySelector('[data-ao-fermeture-residu-pct="c3"]').textContent,
    ).toBe('0.44 %')
  })

  it('BLOQUE le calepinage tant qu’une chaîne est en écart non arbitré, en la NOMMANT', () => {
    const onCalepiner = vi.fn()
    render(<Harnais onCalepiner={onCalepiner} />)
    const bouton = screen.getByRole('button', { name: 'Passer au calepinage' })
    expect(bouton).toBeDisabled()
    const verrou = document.querySelector('[data-ao-fermetures-verrou]')
    expect(verrou.textContent).toMatch(/Développé arc/)
    expect(verrou.textContent).toMatch(/écart non arbitré/)
    expect(onCalepiner).not.toHaveBeenCalled()
  })

  it('« compenser au prorata » montre l’AVANT/APRÈS puis referme la chaîne', async () => {
    const user = userEvent.setup()
    render(<Harnais />)
    await user.click(document.querySelector('[data-ao-fermeture-prorata="c3"]'))

    const apercu = document.querySelector('[data-ao-fermeture-apercu]')
    expect(apercu).toBeTruthy()
    expect(apercu.textContent).toMatch(/22\.600/) // avant
    expect(apercu.textContent).toMatch(/22\.700/) // après

    await user.click(document.querySelector('[data-ao-fermeture-appliquer]'))
    expect(statut('c3')).toBe('OK')
    expect(residu('c3')).toBe('0.000')
    expect(screen.getByRole('button', { name: 'Passer au calepinage' })).toBeEnabled()
  })

  it('l’acceptation exige un motif ÉCRIT, qui est ensuite persisté et visible', async () => {
    const user = userEvent.setup()
    const espion = vi.fn()
    render(<Harnais espion={espion} />)

    const accepter = document.querySelector('[data-ao-fermeture-accepter="c3"]')
    expect(accepter).toBeDisabled() // pas de motif → pas d'acceptation

    await user.type(
      screen.getByLabelText("Motif d'acceptation de l'écart"),
      'Muret de joint non mesurable au relevé — à lever à l’exécution.',
    )
    expect(accepter).toBeEnabled()
    await user.click(accepter)

    const persistee = espion.mock.calls.at(-1)[0].find((c) => c.id === 'c3')
    expect(persistee.arbitrage.type).toBe('accepte')
    expect(persistee.arbitrage.motif).toMatch(/Muret de joint/)
    expect(persistee.arbitrage.horodatage).toBeTruthy()

    // Le motif reste VISIBLE en permanence, et le calepinage se débloque.
    expect(document.querySelector('[data-ao-fermeture-motif="c3"]').textContent).toMatch(
      /Muret de joint/,
    )
    expect(screen.getByRole('button', { name: 'Passer au calepinage' })).toBeEnabled()
    // La chaîne reste en ÉCART : on a arbitré, on n'a pas menti sur le relevé.
    expect(statut('c3')).toBe('ECART')
  })

  it('le calepinage ne part que lorsque toutes les chaînes sont arbitrées', async () => {
    const user = userEvent.setup()
    const onCalepiner = vi.fn()
    render(<Harnais onCalepiner={onCalepiner} />)
    await user.click(document.querySelector('[data-ao-fermeture-prorata="c3"]'))
    await user.click(document.querySelector('[data-ao-fermeture-appliquer]'))
    await user.click(screen.getByRole('button', { name: 'Passer au calepinage' }))
    expect(onCalepiner).toHaveBeenCalledTimes(1)
  })
})
