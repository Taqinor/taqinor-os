import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ExportQR, {
  champsAControler, construireLignesExport, envelopperTexte, MAX_CARACTERES_LIGNE,
} from './ExportQR'

/* AOF107 (2/3) — le « Done = » exige : l'export ne contient AUCUN mot de la
   liste sans confirmation explicite, rendu lisible à 1 000 px de large. Les
   fonctions DOM (`svgVersPng`/presse-papiers) ne sont volontairement PAS
   exercées ici — même discipline que `svgToPng.test.mjs` (AOF75) : seule la
   logique PURE (retour à la ligne, numérotation, garde de vocabulaire) est
   testée au niveau composant/unitaire, le rendu canvas réel n'est pas
   reproductible en jsdom. */

describe('envelopperTexte — retour à la ligne pur', () => {
  it('ne coupe jamais un mot : la coupe se fait à l’espace', () => {
    const lignes = envelopperTexte('Le grand rectangle non coté est-il confirmé néant ?', 20)
    for (const ligne of lignes) expect(ligne.length).toBeLessThanOrEqual(24) // tolère un mot isolé un peu long
    expect(lignes.join(' ')).toBe('Le grand rectangle non coté est-il confirmé néant ?')
  })

  it('un texte court tient sur une seule ligne', () => {
    expect(envelopperTexte('Néant confirmé.', MAX_CARACTERES_LIGNE)).toEqual(['Néant confirmé.'])
  })

  it('un texte vide rend une ligne vide (jamais un tableau vide)', () => {
    expect(envelopperTexte('')).toEqual([''])
    expect(envelopperTexte(null)).toEqual([''])
  })
})

describe('construireLignesExport — liste NUMÉROTÉE par repère', () => {
  it('numérote chaque question avec son repère', () => {
    const lignes = construireLignesExport([
      { repere: 'A', texte: 'Néant confirmé ?' },
      { repere: 'B', texte: 'Cage mesurée ou déduite ?' },
    ], 200)
    expect(lignes).toEqual([
      '1. Repère A — Néant confirmé ?',
      '2. Repère B — Cage mesurée ou déduite ?',
    ])
  })
})

describe('champsAControler — seul le TEXTE de la question est exporté', () => {
  it('nomme chaque champ par son repère, ignore réponse/décision (non exportées)', () => {
    const champs = champsAControler([
      { repere: 'F', texte: 'Le client confirme-t-il ?', reponse: 'Oui, client confirme.' },
    ])
    expect(Object.keys(champs)).toEqual(['Repère F'])
    expect(champs['Repère F']).toBe('Le client confirme-t-il ?')
  })
})

describe('ExportQR — garde de vocabulaire AVANT export', () => {
  it('active les actions d’export quand le vocabulaire est propre', () => {
    render(<ExportQR questions={[{ repere: 'A', texte: 'Le rectangle est-il confirmé néant ?' }]} />)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Générer l’aperçu' })).toBeEnabled()
  })

  it('BLOQUE l’export et cite le mot fautif + sa formulation de remplacement', () => {
    render(<ExportQR questions={[{ repere: 'F', texte: 'Le client confirme-t-il le relevé ?' }]} date="27/07/2026" />)
    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByText('« client »')).toBeInTheDocument()
    expect(screen.getByText(/décision d’études du 27\/07\/2026/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Générer l’aperçu' })).toBeDisabled()
  })

  it('la confirmation EXPLICITE (case cochée) lève le blocage', async () => {
    const user = userEvent.setup()
    render(<ExportQR questions={[{ repere: 'F', texte: 'Quel est le prix d’achat retenu ?' }]} />)
    expect(screen.getByRole('button', { name: 'Générer l’aperçu' })).toBeDisabled()
    await user.click(screen.getByRole('checkbox', { name: /vérifié le vocabulaire/i }))
    expect(screen.getByRole('button', { name: 'Générer l’aperçu' })).toBeEnabled()
  })

  it('un mot BLOQUANT (« marge ») n’a AUCUNE formulation de remplacement proposée', () => {
    render(<ExportQR questions={[{ repere: 'A', texte: 'La marge est confortable.' }]} />)
    expect(screen.getByText(/à retirer \(aucune formulation de remplacement\)/)).toBeInTheDocument()
  })
})
