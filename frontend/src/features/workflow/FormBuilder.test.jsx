import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { deplacerChamp } from './workflow'

/* NTWFL14 -- editeur de formulaire visuel : logique pure (reordonnancement)
   puis smoke render (glisser un type depuis la palette, marquer requis,
   previsualisation reflete le rendu DynamicForm reel). */

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

describe('FormBuilder.js -- deplacerChamp (logique pure)', () => {
  it('deplace un champ vers un index cible', () => {
    const schema = [{ nom: 'A' }, { nom: 'B' }, { nom: 'C' }]
    const next = deplacerChamp(schema, 0, 2)
    expect(next.map((c) => c.nom)).toEqual(['B', 'C', 'A'])
  })

  it('ne fait rien si source === cible', () => {
    const schema = [{ nom: 'A' }, { nom: 'B' }]
    expect(deplacerChamp(schema, 1, 1).map((c) => c.nom)).toEqual(['A', 'B'])
  })

  it('est defensif sur une entree non-tableau', () => {
    expect(deplacerChamp(undefined, 0, 1)).toEqual([])
  })
})

const formulairesGet = vi.fn()
const formulairesCreate = vi.fn()
const formulairesUpdate = vi.fn()

vi.mock('../../api/coreApi', () => ({
  default: {
    formulaires: {
      get: (...a) => formulairesGet(...a),
      create: (...a) => formulairesCreate(...a),
      update: (...a) => formulairesUpdate(...a),
    },
  },
}))

import FormBuilder from './FormBuilder'

function monter(id = 'nouveau') {
  return render(
    <MemoryRouter initialEntries={[`/workflow/formulaires/${id}`]}>
      <ThemeProvider>
        <Routes>
          <Route path="/workflow/formulaires/:id" element={<FormBuilder />} />
        </Routes>
      </ThemeProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  formulairesCreate.mockResolvedValue({ data: { id: 1 } })
  formulairesUpdate.mockResolvedValue({ data: {} })
})

function dropTypeSurCanevas(type) {
  const data = {}
  const dataTransfer = {
    setData: (k, v) => { data[k] = v },
    getData: (k) => data[k] || '',
  }
  fireEvent.dragStart(screen.getByTestId(`fb-palette-${type}`), { dataTransfer })
  fireEvent.drop(screen.getByTestId('fb-canevas'), { dataTransfer })
}

describe('FormBuilder -- rendu (NTWFL14)', () => {
  it('glisser un type depuis la palette ajoute un champ au canevas', () => {
    monter()
    dropTypeSurCanevas('texte')
    expect(screen.getByTestId('fb-champ-0')).toBeTruthy()
  })

  it('marquer un champ requis se reflete dans la previsualisation', async () => {
    const user = userEvent.setup()
    monter()
    dropTypeSurCanevas('texte')
    await user.click(screen.getByTestId('fb-champ-0-requis'))
    expect(await screen.findByTestId('df-champs-manquants')).toBeTruthy()
  })

  it('un champ conditionnel se construit via un picker (SANS ecrire de JSON)', () => {
    monter()
    dropTypeSurCanevas('choix') // champ 0 : declencheur
    dropTypeSurCanevas('texte') // champ 1 : conditionnel

    // Le champ 1 (2e ajoute) voit le champ 0 comme declencheur possible --
    // un SELECT structure, jamais un champ texte libre attendant du JSON.
    expect(screen.getByTestId('fb-champ-1-condition-champ')).toBeTruthy()
    expect(screen.queryByTestId('fb-champ-1-condition-valeur')).toBeNull() // pas encore choisi
  })

  it('un champ section repetable ajoute une section repetable a l\'apercu', () => {
    monter()
    dropTypeSurCanevas('section')
    const apercu = screen.getByTestId('fb-apercu')
    expect(apercu.querySelector('[data-testid^="df-section-"]')).toBeTruthy()
  })

  it('enregistrer une creation appelle formulaires.create', async () => {
    const user = userEvent.setup()
    monter()
    dropTypeSurCanevas('texte')
    await user.click(screen.getByTestId('fb-save'))
    await waitFor(() => expect(formulairesCreate).toHaveBeenCalled())
  })
})

describe('FormBuilder -- edition d\'un formulaire existant', () => {
  it('charge le schema existant', async () => {
    formulairesGet.mockResolvedValue({
      data: { nom: 'F1', schema: [{ nom: 'Motif', type: 'texte', requis: true }] },
    })
    monter('5')
    await waitFor(() => expect(formulairesGet).toHaveBeenCalledWith('5'))
    expect(await screen.findByTestId('fb-champ-0')).toBeTruthy()
  })
})
