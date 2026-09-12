import { describe, it, expect } from 'vitest'
import { actionsEffet } from './effetActions'

/* NTTRE26 — les actions invalides pour le statut courant sont refusées AVEC
   leur explication (le serveur reste seul juge ; l'assistant l'annonce). */

describe('actionsEffet', () => {
  it('un effet à recevoir en portefeuille est endossable, jamais protestable', () => {
    const { endosser, protet } = actionsEffet(
      { sens: 'recevoir', statut: 'portefeuille' })
    expect(endosser.possible).toBe(true)
    expect(protet.possible).toBe(false)
    expect(protet.raison).toMatch(/IMPAYÉ/)
  })

  it('un effet remis à l’encaissement reste endossable', () => {
    expect(actionsEffet({ sens: 'recevoir', statut: 'remis' }).endosser.possible)
      .toBe(true)
  })

  it('un effet déjà encaissé n’est ni endossable ni protestable', () => {
    const { endosser, protet } = actionsEffet(
      { sens: 'recevoir', statut: 'encaisse' })
    expect(endosser.possible).toBe(false)
    expect(endosser.raison).toMatch(/déjà encaissé/)
    expect(protet.possible).toBe(false)
  })

  it('un effet à PAYER n’est jamais endossable', () => {
    const { endosser } = actionsEffet(
      { sens: 'payer', statut: 'portefeuille' })
    expect(endosser.possible).toBe(false)
    expect(endosser.raison).toMatch(/À RECEVOIR/)
  })

  it('un effet impayé est protestable une seule fois', () => {
    const premier = actionsEffet({ sens: 'recevoir', statut: 'impaye' })
    expect(premier.protet.possible).toBe(true)

    const deuxieme = actionsEffet(
      { sens: 'recevoir', statut: 'impaye', date_protet: '2026-03-10' })
    expect(deuxieme.protet.possible).toBe(false)
    expect(deuxieme.protet.raison).toMatch(/déjà été constaté/)
  })

  it('chaque refus porte une raison non vide', () => {
    for (const statut of ['encaisse', 'paye', 'endosse', 'escompte']) {
      const { endosser, protet } = actionsEffet({ sens: 'recevoir', statut })
      if (!endosser.possible) expect(endosser.raison.length).toBeGreaterThan(0)
      if (!protet.possible) expect(protet.raison.length).toBeGreaterThan(0)
    }
  })
})
