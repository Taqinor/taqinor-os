import { describe, it, expect, vi } from 'vitest'
import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SuggestionsPanel from './SuggestionsPanel'

/* AOF100 — le « Done = » exige :
   1. la boucle suggestion → question → recalcul est cliquable de bout en
      bout (« Appliquer » et « Poser la question au client » relaient EXACTEMENT
      la suggestion serveur, sans rien réécrire) ;
   2. les suggestions appliquées passent en historique (et perdent leurs
      actions) ;
   3. aucune suggestion n'est écrite en dur côté front (tout vient des props). */

const SUGGESTION_ALLEE = {
  code: 'ALLEE_GRATUITE',
  titre: 'élargir les allées à 1,94 m sans perdre un module (maintenance offerte)',
  gain_modules: 0,
  gain_kwc: 0,
  cout_qualitatif: 'aucun — le compte est identique jusqu’à 1,94 m',
  confiance: 'HAUTE',
  patch_entree: [['allee_m', '1.94']],
  question_a_poser: 'Souhaitez-vous des allées de maintenance de 1,94 m ? Elles ne coûtent aucun module.',
}

const SUGGESTION_ARBITRAGE = {
  code: 'ARBITRER_F',
  titre: "faire arbitrer l'emprise F (provenance PLAN)",
  gain_modules: 8,
  gain_kwc: 2.5,
  cout_qualitatif: 'une confirmation de relevé — impact chiffré des deux côtés : retirée -2, confirmée +8',
  confiance: 'MOYENNE',
  patch_entree: [['confirmer', 'F']],
  question_a_poser: "L'emprise F est-elle réellement présente ? Impact chiffré : +8 modules si confirmée néant.",
}

describe('SuggestionsPanel — cartes actionnables (AOF100)', () => {
  it('rend le titre, le gain chiffré et la condition EXACTEMENT tels que fournis par le serveur', () => {
    const { container } = render(<SuggestionsPanel suggestions={[SUGGESTION_ARBITRAGE]} />)
    expect(screen.getByText(SUGGESTION_ARBITRAGE.titre)).toBeInTheDocument()

    const carte = container.querySelector('[data-suggestion="ARBITRER_F"]')
    expect(carte.textContent).toContain('+8 module')
    expect(carte.textContent).toContain('soit +2.50 kWc')
    expect(carte.textContent).toContain(SUGGESTION_ARBITRAGE.cout_qualitatif)

    // Le chiffre est bien celui du SERVEUR (`gain_modules`), jamais recalculé.
    expect(container.querySelector('[data-ao-compte="8"]')).not.toBeNull()
  })

  it('« Appliquer » relaie la suggestion COMPLÈTE (patch_entree inclus), sans rien recalculer côté front', async () => {
    const user = userEvent.setup()
    const onAppliquer = vi.fn()
    render(<SuggestionsPanel suggestions={[SUGGESTION_ARBITRAGE]} onAppliquer={onAppliquer} />)
    await user.click(screen.getByRole('button', { name: 'Appliquer' }))
    expect(onAppliquer).toHaveBeenCalledWith(SUGGESTION_ARBITRAGE)
  })

  it('« Poser la question au client » relaie la suggestion (impact déjà pré-rempli dans `question_a_poser`)', async () => {
    const user = userEvent.setup()
    const onPoserQuestion = vi.fn()
    render(<SuggestionsPanel suggestions={[SUGGESTION_ARBITRAGE]} onPoserQuestion={onPoserQuestion} />)
    await user.click(screen.getByRole('button', { name: 'Poser la question au client' }))
    expect(onPoserQuestion).toHaveBeenCalledWith(SUGGESTION_ARBITRAGE)
  })

  it('désactive les actions de la carte EN COURS d’application, sans bloquer les autres', () => {
    render(
      <SuggestionsPanel
        suggestions={[SUGGESTION_ALLEE, SUGGESTION_ARBITRAGE]}
        enCours="ALLEE_GRATUITE"
      />,
    )
    const cartes = screen.getAllByRole('button', { name: 'Appliquer' })
    expect(cartes[0]).toBeDisabled() // ALLEE_GRATUITE
    expect(cartes[1]).toBeEnabled() // ARBITRER_F
  })

  it('affiche un état vide quand le moteur ne propose rien', () => {
    render(<SuggestionsPanel suggestions={[]} />)
    expect(screen.getByText('Aucune suggestion en attente')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Appliquer' })).not.toBeInTheDocument()
  })
})

describe('SuggestionsPanel — historique des suggestions appliquées', () => {
  it('une suggestion du HISTORIQUE quitte la liste actionnable et perd ses boutons', () => {
    const { container } = render(
      <SuggestionsPanel
        suggestions={[SUGGESTION_ALLEE, SUGGESTION_ARBITRAGE]}
        historique={[{ code: 'ALLEE_GRATUITE', titre: SUGGESTION_ALLEE.titre, gain_modules: 0 }]}
      />,
    )
    // Une seule carte actionnable reste (ARBITRER_F) — ALLEE_GRATUITE est en historique.
    expect(screen.getAllByRole('button', { name: 'Appliquer' })).toHaveLength(1)
    const carteHistorique = container.querySelector('[data-suggestion="ALLEE_GRATUITE"]')
    expect(carteHistorique.getAttribute('data-suggestion-appliquee')).toBe('true')
    expect(carteHistorique.textContent).toContain('Appliquée')
    expect(carteHistorique.querySelector('button')).toBeNull() // aucune action sur une carte appliquée
  })

  it('la boucle appliquer → historique est cliquable de bout en bout (simulation du parent)', async () => {
    const user = userEvent.setup()
    function Parent() {
      const [historique, setHistorique] = useState([])
      return (
        <SuggestionsPanel
          suggestions={[SUGGESTION_ARBITRAGE]}
          historique={historique}
          onAppliquer={(s) => setHistorique((h) => [
            ...h, { code: s.code, titre: s.titre, gain_modules: s.gain_modules },
          ])}
        />
      )
    }
    const { container } = render(<Parent />)
    expect(screen.getByRole('button', { name: 'Appliquer' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Appliquer' }))
    expect(screen.queryByRole('button', { name: 'Appliquer' })).not.toBeInTheDocument()
    expect(container.querySelector('[data-suggestion="ARBITRER_F"]').getAttribute('data-suggestion-appliquee')).toBe('true')
  })
})
