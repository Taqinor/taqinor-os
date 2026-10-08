// ADEV9 (C-ADEV-003) — la carte de synthèse « Envoyés » de la liste compte une
// installation révisée UNE fois : la V1 remplacée (`is_active: false`) n'est
// plus en jeu. Exécute le VRAI `useDevisListSynthese` (renderHook), pas une
// regex sur le source. Test-du-test : retirer le filtre `devisEnJeu` de
// `syntheseParStatut` ⇒ count 2, le test échoue.
import { describe, it, expect } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useDevisListSynthese, syntheseParStatut } from './devisListHelpers.js'

const effStatutOf = (d) => d.statut

describe('ADEV9 — synthèse de la liste sur les devis en jeu', () => {
  const v1 = { id: 1, statut: 'envoye', is_active: false, total_affiche: 100 }
  const v2 = { id: 2, statut: 'envoye', is_active: true, total_affiche: 100 }

  it('[V1 inactive, V2 active] ⇒ Envoyés compte 1', () => {
    const { result } = renderHook(() => useDevisListSynthese([v1, v2], effStatutOf))
    expect(result.current.summary.envoye).toEqual({ count: 1, total: 100 })
  })

  it('un devis sans révision (ou sans champ is_active) compte comme avant', () => {
    const ancien = { id: 3, statut: 'envoye', total_affiche: 50 }
    expect(syntheseParStatut([v2, ancien], effStatutOf).envoye).toEqual({ count: 2, total: 150 })
  })
})
