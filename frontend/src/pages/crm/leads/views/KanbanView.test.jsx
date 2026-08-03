import { describe, it, expect } from 'vitest'

describe('KanbanView · StageMover — SUPPRIMÉ (ordre fondateur 2026-08-02)', () => {
  // « Ne la cache pas, supprime-la complètement. » Le sélecteur d'étape par
  // carte (J140/L151/LB3/LB4) n'existe plus — ni exporté, ni rendu, ni stylé.
  // Chemins restants : glisser-déposer (garde LB4 + recul confirmé round 4)
  // et la pilule d'étape de la fenêtre du lead.
  // La moitié SOURCE du contrat (aucune balise <StageMover>, aucun export,
  // aucun câblage inlineSaveAvecUndo, aucune classe kb-stage-mover) vit dans
  // RenderCap.apx9.test.mjs — un test node:test peut lire le source, pas un
  // test vitest (URL de transformeur non-file).
  it("n'est plus exporté par le module", async () => {
    const mod = await import('./KanbanView')
    expect(mod.StageMover).toBeUndefined()
    // Le module garde ses exports légitimes.
    expect(mod.STAGE_PROBABILITY).toBeTruthy()
    expect(mod.default).toBeTypeOf('function')
  })
})
