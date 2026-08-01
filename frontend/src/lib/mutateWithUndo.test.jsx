import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  mutateWithUndo, assertUndoable, UNDO_REGISTRY, UNDO_KINDS, UNDO_DURATION_MS,
} from './mutateWithUndo'
import * as toastModule from './toast'

/* EZ14 — Undo universel : « appliquer TOUT DE SUITE + inverse à l'annulation ».
   ---------------------------------------------------------------------------
   Le bug de fond que ces tests verrouillent : `toastWithUndo({onCommit})` est
   un COMMIT DIFFÉRÉ (setTimeout 6 s). Sur un board, l'utilisateur navigue, le
   composant se démonte, le timer part avec la page — l'écriture est PERDUE en
   silence alors que l'écran a dit « c'est fait ». `mutateWithUndo` ne peut
   structurellement pas avoir ce défaut : il n'y a jamais rien en attente. */

let undoSpy
let errorSpy

beforeEach(() => {
  vi.useFakeTimers()
  undoSpy = vi.spyOn(toastModule, 'toastWithUndo').mockImplementation(() => 'toast-id')
  errorSpy = vi.spyOn(toastModule, 'toastError').mockImplementation(() => {})
})
afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('mutateWithUndo — anti-commit-différé (le cœur d’EZ14)', () => {
  it('APPLIQUE avant de rendre la main : rien n’attend la fin du toast', async () => {
    const apply = vi.fn().mockResolvedValue(undefined)
    await mutateWithUndo({
      kind: 'lead_tags', message: 'Étiquettes modifiées.', apply, revert: vi.fn(),
    })
    // L'écriture a déjà eu lieu au retour de l'await — aucun timer requis.
    expect(apply).toHaveBeenCalledTimes(1)
  })

  it('naviguer pendant le toast ne perd RIEN (aucun onCommit différé n’est posé)', async () => {
    const apply = vi.fn().mockResolvedValue(undefined)
    await mutateWithUndo({
      kind: 'lead_priorite', message: 'Priorité modifiée.', apply, revert: vi.fn(),
    })
    // Le toast est bien affiché...
    expect(undoSpy).toHaveBeenCalledTimes(1)
    // ... et il ne porte AUCUN `onCommit` : rien ne peut être perdu au démontage.
    expect(undoSpy.mock.calls[0][0]).not.toHaveProperty('onCommit')
    // Même en laissant filer tous les timers, aucune écriture ne s'ajoute.
    vi.advanceTimersByTime(60_000)
    expect(apply).toHaveBeenCalledTimes(1)
  })

  it('« Annuler » exécute l’appel INVERSE (une vraie seconde écriture)', async () => {
    const revert = vi.fn().mockResolvedValue(undefined)
    await mutateWithUndo({
      kind: 'lead_owner', message: 'Responsable modifié.', apply: vi.fn().mockResolvedValue(), revert,
    })
    expect(revert).not.toHaveBeenCalled()   // rien tant qu'on ne clique pas
    await undoSpy.mock.calls[0][0].onUndo()
    expect(revert).toHaveBeenCalledTimes(1)
  })

  it('un échec d’écriture remet l’écran d’aplomb et n’offre AUCUN undo', async () => {
    const rollback = vi.fn()
    const ok = await mutateWithUndo({
      kind: 'lead_stage',
      message: 'Étape modifiée.',
      apply: vi.fn().mockRejectedValue(new Error('réseau')),
      revert: vi.fn(),
      optimistic: vi.fn(),
      rollbackOptimistic: rollback,
    })
    expect(ok).toBe(false)
    expect(rollback).toHaveBeenCalledTimes(1)
    expect(undoSpy).not.toHaveBeenCalled()
    expect(errorSpy).toHaveBeenCalled()
  })

  it('un échec de l’INVERSE est dit à l’utilisateur, jamais avalé', async () => {
    await mutateWithUndo({
      kind: 'lead_archive',
      message: 'Lead archivé.',
      apply: vi.fn().mockResolvedValue(),
      revert: vi.fn().mockRejectedValue(new Error('réseau')),
    })
    await undoSpy.mock.calls[0][0].onUndo()
    expect(errorSpy).toHaveBeenCalledWith("Annulation impossible — vérifiez votre connexion.")
  })

  it('la fenêtre d’annulation est un PARAMÈTRE (@coord NTUX27 duree_undo_toast)', async () => {
    await mutateWithUndo({
      kind: 'lead_canal', message: 'Canal modifié.', apply: vi.fn().mockResolvedValue(), revert: vi.fn(),
    })
    expect(undoSpy.mock.calls[0][0].duration).toBe(UNDO_DURATION_MS)
    undoSpy.mockClear()
    await mutateWithUndo({
      kind: 'lead_canal', message: 'Canal modifié.', apply: vi.fn().mockResolvedValue(), revert: vi.fn(), duration: 12_000,
    })
    expect(undoSpy.mock.calls[0][0].duration).toBe(12_000)
  })
})

describe('mutateWithUndo — le registre FERMÉ', () => {
  it('accepte exactement les genres déclarés', () => {
    for (const k of UNDO_KINDS) expect(assertUndoable(k)).toBe(true)
    expect(UNDO_KINDS.length).toBeGreaterThanOrEqual(6)
  })

  it('REFUSE un genre hors registre (échec bruyant plutôt qu’undo trompeur)', () => {
    expect(() => assertUndoable('lead_montant')).toThrow(/registre fermé/)
    expect(() => assertUndoable('nimporte_quoi')).toThrow(/registre fermé/)
  })

  it('ZÉRO undo sur l’argent, les suppressions dures et les envois', () => {
    // Le registre lui-même ne contient aucun genre d'argent/envoi...
    const interdit = /devis|facture|montant|prix|paiement|total|remise|tva|delete|suppression|envoi|email|whatsapp|pdf/i
    for (const k of UNDO_KINDS) {
      expect(k, `genre interdit dans le registre : ${k}`).not.toMatch(interdit)
      expect(UNDO_REGISTRY[k]).toBeTruthy()
    }
    // ... et la garde refuserait un ajout par distraction.
    expect(() => assertUndoable('facture_statut')).toThrow()
    expect(() => assertUndoable('devis_envoi')).toThrow()
  })

  it('exige `apply` ET `revert` (un undo sans inverse n’est pas un undo)', async () => {
    await expect(mutateWithUndo({
      kind: 'lead_tags', message: 'x', apply: vi.fn(),
    })).rejects.toThrow(/apply.*revert/)
  })
})
