import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { Dialog, DialogContent, DialogTitle, DialogDescription } from './Dialog'
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogTitle,
  AlertDialogDescription,
} from './AlertDialog'

/* Régression iPhone. Un modal haut, centré par `-translate-y-1/2`, débordait HORS
   de l'écran sur iPhone (haut + bas rognés → boutons Annuler/Confirmer/Enregistrer
   inaccessibles). Le correctif = plafond de hauteur au viewport réel (100dvh) +
   défilement interne. AlertDialog avait justement reperdu ces classes lors d'une
   évolution ; ce garde-fou empêche les DEUX modals de régresser à nouveau.
   (Le vrai rendu visuel est, lui, vérifié par e2e/mobile.spec.js au format iPhone.) */
describe('Modals — sûreté viewport mobile (anti-débordement iPhone)', () => {
  it('DialogContent plafonne la hauteur au viewport et défile en interne', () => {
    render(
      <Dialog defaultOpen>
        <DialogContent>
          <DialogTitle>Titre</DialogTitle>
          <DialogDescription>Description</DialogDescription>
          <p>Contenu</p>
        </DialogContent>
      </Dialog>,
    )
    const content = screen.getByRole('dialog')
    expect(content.className).toContain('max-h-[calc(100dvh-2rem)]')
    expect(content.className).toContain('overflow-y-auto')
  })

  it('AlertDialogContent plafonne aussi la hauteur (même correctif que Dialog)', () => {
    render(
      <AlertDialog defaultOpen>
        <AlertDialogContent>
          <AlertDialogTitle>Confirmer</AlertDialogTitle>
          <AlertDialogDescription>Êtes-vous sûr ?</AlertDialogDescription>
        </AlertDialogContent>
      </AlertDialog>,
    )
    const content = screen.getByRole('alertdialog')
    expect(content.className).toContain('max-h-[calc(100dvh-2rem)]')
    expect(content.className).toContain('overflow-y-auto')
  })

  // VX175(c) — le shell `.modal` (raw CSS, utilisé par les modales fait-main
  // hors Dialog/AlertDialog, ex. LeadForm) était le SEUL bloc 100vh du
  // fichier sans repli 100dvh : bas de modale rogné sous la barre d'adresse
  // dynamique mobile. On vérifie la source CSS directement (pas de rendu —
  // `.modal` n'est pas un composant React, juste une classe posée sur un
  // shell brut).
  it('.modal (CSS brut) porte la paire 100vh → 100dvh sur max-height', () => {
    const here = dirname(fileURLToPath(import.meta.url))
    const css = readFileSync(join(here, '..', 'index.css'), 'utf8')
    const start = css.indexOf('.modal {')
    const rule = css.slice(start, css.indexOf('}', start))
    expect(rule).toContain('max-height: calc(100vh - 48px);')
    expect(rule).toContain('max-height: calc(100dvh - 48px);')
  })
})
