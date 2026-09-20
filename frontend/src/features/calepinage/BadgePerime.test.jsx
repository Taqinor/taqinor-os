import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { exempleContrat } from '../../test/fixtures/contractSamples'
import BadgePerime, { estPerime } from './BadgePerime'

/* ============================================================================
   CAL188 — LE BADGE, NOURRI PAR LE CONTRAT COMMITTÉ, PAS PAR UN MOCK ÉCRIT
   À LA MAIN.
   ----------------------------------------------------------------------------
   `calepinage_detail.json` (CAL17/CAL189) publie `layout_stale`/
   `layout_nb_panneaux` — `false`/`12` dans l'exemple, `null`/`null` dans
   `exemple_vide` (sans devis, la péremption est INCONNUE). Ce test relit ces
   deux vérités du fichier committé, et construit le SEUL cas que le contrat
   ne montre pas encore (`true`) en dérivant l'exemple plutôt qu'en l'inventant.
   ========================================================================== */

const DETAIL = exempleContrat('calepinage', 'calepinage_detail')
const DETAIL_VIDE = exempleContrat('calepinage', 'calepinage_detail',
  'exemple_vide')

afterEach(() => { cleanup() })

describe('CAL188 — estPerime : TRUE strict, jamais une valeur voisine', () => {
  it('le contrat committé porte bien `layout_stale: false` dans son exemple', () => {
    expect(DETAIL.layout_stale).toBe(false)
  })

  it('sans devis (exemple_vide), la péremption est INCONNUE — pas fausse', () => {
    expect(DETAIL_VIDE.layout_stale).toBeNull()
  })

  it('seul `true` strict est périmé', () => {
    expect(estPerime(true)).toBe(true)
    expect(estPerime(false)).toBe(false)
    expect(estPerime(null)).toBe(false)
    expect(estPerime(undefined)).toBe(false)
    // Un « truthy » qui n'est pas le booléen `true` n'est pas une affirmation
    // du serveur — zéro chiffre/état inventé.
    expect(estPerime(1)).toBe(false)
    expect(estPerime('true')).toBe(false)
  })
})

describe('CAL188 — le badge, lu du MÊME champ serveur', () => {
  it('`layout_stale: false` (contrat) : AUCUN badge — à jour n’est pas une alerte', () => {
    render(<BadgePerime layoutStale={DETAIL.layout_stale}
      layoutNbPanneaux={DETAIL.layout_nb_panneaux} />)
    expect(screen.queryByTestId('cal-badge-perime')).toBeNull()
  })

  it('`layout_stale: null` (contrat, exemple_vide) : AUCUN badge — INCONNU n’est pas périmé', () => {
    render(<BadgePerime layoutStale={DETAIL_VIDE.layout_stale}
      layoutNbPanneaux={DETAIL_VIDE.layout_nb_panneaux} />)
    expect(screen.queryByTestId('cal-badge-perime')).toBeNull()
  })

  it('`layout_stale: true` : le badge « Calepinage périmé » apparaît', () => {
    render(<BadgePerime layoutStale layoutNbPanneaux={12} />)
    const badge = screen.getByTestId('cal-badge-perime')
    expect(badge).toHaveTextContent('Calepinage périmé')
    expect(badge.title).toContain('12')
  })

  it('`layout_stale: true` sans compte de panneaux connu : le badge ne l’invente pas', () => {
    render(<BadgePerime layoutStale layoutNbPanneaux={null} />)
    const badge = screen.getByTestId('cal-badge-perime')
    expect(badge.title).not.toMatch(/\d/)
  })
})
