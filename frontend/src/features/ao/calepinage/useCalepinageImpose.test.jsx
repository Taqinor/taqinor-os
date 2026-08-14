import { describe, it, expect, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import useCalepinageImpose from './useCalepinageImpose'
import resultatReel from './resultatReel.fixture'

/* ============================================================================
   PV31 — `useCalepinageImpose` : le brouillon local du mode « rangées
   imposées par l'utilisateur ».
   ----------------------------------------------------------------------------
   Ce hook ne parle JAMAIS au réseau lui-même : il pousse un patch de
   paramètres via `majParametres` (le MÊME que les tiroirs de
   `CalepinageStudio`), et c'est `useCalepinage` qui recalcule côté serveur.
   Ces tests mockent donc `majParametres` — pas d'axios ici — et vérifient
   la FORME du patch envoyé, jamais un chiffre inventé.

   La charge utile vient de `resultatReel.fixture.js` (capturée du moteur du
   dépôt) : deux rangées, `y0` 0.8003 et 6.9503, même kit
   AO-TABLE-PORTRAIT — jamais une fixture écrite à la main.
   ========================================================================== */

const KIT = 'AO-TABLE-PORTRAIT'
const SEED = [[0.8003, KIT], [6.9503, KIT]]

function monter(resultat = resultatReel, toitureId = 7) {
  const majParametres = vi.fn()
  const rendu = renderHook(
    ({ r, id }) => useCalepinageImpose({ resultat: r, majParametres, toitureId: id }),
    { initialProps: { r: resultat, id: toitureId } },
  )
  return { ...rendu, majParametres }
}

describe('useCalepinageImpose (PV31) — inactif tant qu’aucun geste n’a eu lieu', () => {
  it('affiche les rangées SERVEUR sans jamais appeler majParametres', () => {
    const { result, majParametres } = monter()
    expect(result.current.actif).toBe(false)
    expect(result.current.draft).toBeNull()
    expect(result.current.lignesAffichees).toEqual(SEED)
    expect(majParametres).not.toHaveBeenCalled()
  })
})

describe('useCalepinageImpose (PV31) — seed au PREMIER geste', () => {
  it('glisser une rangée amorce le brouillon depuis resultat.rangees', () => {
    const { result, majParametres } = monter()
    act(() => result.current.commencerGlisser(0))
    expect(result.current.actif).toBe(true)
    expect(result.current.draft).toEqual(SEED)
    expect(result.current.selection).toBe(0)
    // Amorcer le brouillon n'est pas encore un geste APPLIQUÉ.
    expect(majParametres).not.toHaveBeenCalled()
  })

  it('ajouter une rangée amorce aussi le brouillon (même seed)', () => {
    const { result } = monter()
    act(() => result.current.ajouterRangee(3.5))
    expect(result.current.draft).toEqual([[0.8003, KIT], [3.5, KIT], [6.9503, KIT]])
  })
})

describe('useCalepinageImpose (PV31) — glisser une rangée', () => {
  it('un glissé COMPLET envoie mode_pose + rangees_imposees via majParametres', () => {
    const { result, majParametres } = monter()
    act(() => result.current.commencerGlisser(0))
    act(() => result.current.deplacerVers(2.5))
    act(() => result.current.validerGlisser())

    const attendu = [[2.5, KIT], [6.9503, KIT]]
    expect(majParametres).toHaveBeenCalledWith({
      mode_pose: 'rangees_imposees_utilisateur',
      rangees_imposees: attendu,
    })
    expect(result.current.draft).toEqual(attendu)
  })

  it('un clic SANS déplacement sélectionne mais n’envoie rien (jamais un geste inventé)', () => {
    const { result, majParametres } = monter()
    act(() => result.current.commencerGlisser(1))
    act(() => result.current.validerGlisser())
    expect(result.current.selection).toBe(1)
    expect(majParametres).not.toHaveBeenCalled()
  })

  it('annulerGlisser efface l’aperçu sans rien appliquer', () => {
    const { result, majParametres } = monter()
    act(() => result.current.commencerGlisser(0))
    act(() => result.current.deplacerVers(2.5))
    act(() => result.current.annulerGlisser())
    expect(result.current.yPropose).toBeNull()
    act(() => result.current.validerGlisser())
    expect(majParametres).not.toHaveBeenCalled()
  })
})

describe('useCalepinageImpose (PV31) — ajouter / supprimer', () => {
  it('ajoute une rangée : reprend le kit voisin, trie par y0, envoie le patch', () => {
    const { result, majParametres } = monter()
    act(() => result.current.ajouterRangee(3.5))
    const attendu = [[0.8003, KIT], [3.5, KIT], [6.9503, KIT]]
    expect(result.current.draft).toEqual(attendu)
    expect(majParametres).toHaveBeenLastCalledWith({
      mode_pose: 'rangees_imposees_utilisateur',
      rangees_imposees: attendu,
    })
  })

  it('supprime la rangée SÉLECTIONNÉE, jamais une autre', () => {
    const { result, majParametres } = monter()
    act(() => result.current.commencerGlisser(0)) // seed + sélectionne la rangée 0
    act(() => result.current.supprimerSelection())
    expect(result.current.draft).toEqual([[6.9503, KIT]])
    expect(result.current.selection).toBeNull()
    expect(majParametres).toHaveBeenLastCalledWith({
      mode_pose: 'rangees_imposees_utilisateur',
      rangees_imposees: [[6.9503, KIT]],
    })
  })

  it('supprimer sans sélection ne fait rien', () => {
    const { result, majParametres } = monter()
    act(() => result.current.supprimerSelection())
    expect(majParametres).not.toHaveBeenCalled()
    expect(result.current.actif).toBe(false)
  })
})

describe('useCalepinageImpose (PV31) — annuler / rétablir', () => {
  it('annuler revient EXACTEMENT au brouillon précédent, rétablir au suivant', () => {
    const { result, majParametres } = monter()
    act(() => result.current.ajouterRangee(3.5))
    const apresAjout = result.current.draft

    act(() => result.current.annuler())
    expect(result.current.draft).toEqual(SEED)
    expect(result.current.peutAnnuler).toBe(false)
    expect(result.current.peutRefaire).toBe(true)

    act(() => result.current.refaire())
    expect(result.current.draft).toEqual(apresAjout)
    expect(result.current.peutRefaire).toBe(false)

    // ajout, annuler, rétablir : trois patchs envoyés au serveur.
    expect(majParametres).toHaveBeenCalledTimes(3)
  })

  it('annuler sans historique ne fait rien', () => {
    const { result, majParametres } = monter()
    act(() => result.current.annuler())
    expect(majParametres).not.toHaveBeenCalled()
  })
})

describe('useCalepinageImpose (PV32) — isDraftDirty et sortie', () => {
  it('isDraftDirty : faux avant tout geste, vrai après un geste APPLIQUÉ', () => {
    const { result } = monter()
    expect(result.current.isDraftDirty).toBe(false)
    act(() => result.current.commencerGlisser(0)) // seed seul : pas encore « modifié »
    expect(result.current.isDraftDirty).toBe(false)
    act(() => result.current.ajouterRangee(3.5))
    expect(result.current.isDraftDirty).toBe(true)
  })

  it('« Revenir au calcul optimal » retire mode_pose ET rangees_imposees (pas de fantôme)', () => {
    const { result, majParametres } = monter()
    act(() => result.current.ajouterRangee(3.5))
    act(() => result.current.quitter())
    expect(result.current.actif).toBe(false)
    expect(result.current.draft).toBeNull()
    expect(result.current.isDraftDirty).toBe(false)
    expect(majParametres).toHaveBeenLastCalledWith({
      mode_pose: undefined,
      rangees_imposees: undefined,
    })
    // Les bandes affichées retombent sur celles du dernier résultat serveur.
    expect(result.current.lignesAffichees).toEqual(SEED)
  })
})

describe('useCalepinageImpose (PV31) — une toiture NEUVE réinitialise le brouillon', () => {
  it('change de toiture -> le brouillon en cours est abandonné', () => {
    const { result, rerender } = monter()
    act(() => result.current.ajouterRangee(3.5))
    expect(result.current.actif).toBe(true)

    rerender({ r: null, id: 9 })
    expect(result.current.actif).toBe(false)
    expect(result.current.draft).toBeNull()
  })
})
