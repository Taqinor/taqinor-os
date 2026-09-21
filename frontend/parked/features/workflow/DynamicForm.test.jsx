import { describe, it, expect, beforeAll } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { champVisible, champsFormulaireManquants } from './workflow'
import DynamicForm from './DynamicForm'

/* NTWFL12 -- rendu generique d'un formulaire dynamique : logique pure
   (visibilite/completude) puis un smoke render (champ requis bloquant,
   champ conditionnel, section repetable a N occurrences). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}

      unobserve() {}

      disconnect() {}
    }
  }
  if (typeof window.matchMedia === 'undefined') {
    window.matchMedia = () => ({
      matches: false,
      addListener() {},
      removeListener() {},
      addEventListener() {},
      removeEventListener() {},
    })
  }
})

describe('workflow.js -- formulaires dynamiques (NTWFL12)', () => {
  describe('champVisible', () => {
    it('toujours visible sans condition', () => {
      expect(champVisible('x', {}, {})).toBe(true)
    })

    it('respecte visible_si', () => {
      const regles = { justificatif: { visible_si: { field: 'type', operator: 'eq', value: 'exceptionnel' } } }
      expect(champVisible('justificatif', regles, { type: 'standard' })).toBe(false)
      expect(champVisible('justificatif', regles, { type: 'exceptionnel' })).toBe(true)
    })
  })

  describe('champsFormulaireManquants', () => {
    it('liste les champs requis absents', () => {
      const schema = [
        { nom: 'motif', type: 'texte', requis: true },
        { nom: 'commentaire', type: 'texte', requis: false },
      ]
      expect(champsFormulaireManquants(schema, {}, {})).toEqual(['motif'])
      expect(champsFormulaireManquants(schema, {}, { motif: 'X' })).toEqual([])
    })

    it('ignore un champ requis mais MASQUE (conditionnel)', () => {
      const schema = [
        { nom: 'type', type: 'choix', requis: true },
        { nom: 'justificatif', type: 'texte', requis: true },
      ]
      const regles = { justificatif: { visible_si: { field: 'type', operator: 'eq', value: 'exceptionnel' } } }
      expect(champsFormulaireManquants(schema, regles, { type: 'standard' })).toEqual([])
    })

    it('ignore les sections (pas de valeur directe)', () => {
      const schema = [{ nom: 'lignes', type: 'section', requis: true, repetable: true }]
      expect(champsFormulaireManquants(schema, {}, {})).toEqual([])
    })
  })
})

function monter(props) {
  return render(
    <ThemeProvider>
      <DynamicForm {...props} />
    </ThemeProvider>,
  )
}

describe('DynamicForm -- rendu (NTWFL12)', () => {
  it('affiche un champ requis manquant', () => {
    monter({
      schema: [{ nom: 'motif', type: 'texte', requis: true }],
      champsConditionnels: {},
      valeurs: {},
      onChange: () => {},
    })
    expect(screen.getByTestId('df-champs-manquants')).toBeTruthy()
  })

  it('un champ rempli fait disparaitre l\'avertissement', () => {
    monter({
      schema: [{ nom: 'motif', type: 'texte', requis: true }],
      champsConditionnels: {},
      valeurs: { motif: 'Congé' },
      onChange: () => {},
    })
    expect(screen.queryByTestId('df-champs-manquants')).toBeNull()
  })

  it('un champ conditionnel masque ne s\'affiche pas', () => {
    monter({
      schema: [
        { nom: 'type', type: 'texte' },
        { nom: 'justificatif', type: 'texte', requis: true },
      ],
      champsConditionnels: {
        justificatif: { visible_si: { field: 'type', operator: 'eq', value: 'exceptionnel' } },
      },
      valeurs: { type: 'standard' },
      onChange: () => {},
    })
    expect(screen.queryByTestId('df-champ-justificatif')).toBeNull()
  })

  it('une section repetable ajoute des lignes', () => {
    let valeurs = { lignes: [] }
    const onChange = (nom, v) => { valeurs = { ...valeurs, [nom]: v } }
    const { rerender } = monter({
      schema: [{ nom: 'lignes', type: 'section', repetable: true }],
      champsConditionnels: {},
      valeurs,
      onChange,
    })
    fireEvent.click(screen.getByTestId('df-section-lignes-ajouter'))
    expect(valeurs.lignes).toHaveLength(1)
    rerender(
      <ThemeProvider>
        <DynamicForm
          schema={[{ nom: 'lignes', type: 'section', repetable: true }]}
          champsConditionnels={{}}
          valeurs={valeurs}
          onChange={onChange}
        />
      </ThemeProvider>,
    )
    expect(screen.getByTestId('df-section-lignes-ligne-0')).toBeTruthy()
  })
})
