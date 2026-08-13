import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* PACT118 — le hook d'accès générique au registre d'édition en masse du socle.
   Ce qu'il doit garantir :
     * une cible ABSENTE du catalogue rend `disponible === false` — l'écran
       n'affiche alors aucune action (jamais un bouton qui finirait en 404) ;
     * la liste blanche des champs vient du SERVEUR, jamais du client ;
     * `appliquer` poste exactement { target, ids, changes } et renvoie le
       nombre de lignes modifiées ;
     * un catalogue indisponible dégrade sans jeter.
   Le fichier est en `.test.jsx` (et non `.test.js`) : `vitest.config.js` ne
   collecte que les fichiers `.test.jsx` — un `.test.js` ne serait exécuté par
   AUCUN runner (ni Vitest, ni le `node --test` de la CI, qui ne prend que les
   fichiers `.test.mjs`). */

const targets = vi.fn()
const appliquer = vi.fn()

vi.mock('../../api/coreApi', () => ({
  default: { bulkEdit: { targets: (...a) => targets(...a), appliquer: (...a) => appliquer(...a) } },
}))

import useBulkEditCible, { normaliserCibles, trouverCible } from './useBulkEditCible'

function Sonde({ nom = 'cpq.offre-groupee' }) {
  const masse = useBulkEditCible(nom)
  return (
    <div>
      <span data-testid="dispo">{masse.disponible ? 'oui' : 'non'}</span>
      <span data-testid="libelle">{masse.libelle}</span>
      <span data-testid="champs">{masse.champs.join(',')}</span>
      <span data-testid="erreur">{masse.erreur}</span>
      <button type="button" onClick={() => masse.appliquer([1, 2], { actif: false })}>
        Appliquer
      </button>
      <button type="button" onClick={() => masse.appliquer([], { actif: false })}>
        Appliquer vide
      </button>
    </div>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  targets.mockResolvedValue({
    data: [
      { name: 'cpq.offre-groupee', label: 'Offres groupées', fields: ['actif'] },
      { name: 'cpq.question-configurateur', label: 'Questions', fields: ['actif', 'ordre'] },
    ],
  })
  appliquer.mockResolvedValue({ data: { modifies: 2 } })
})

describe('normaliserCibles / trouverCible (PACT118)', () => {
  it('ignore les entrées malformées et ne jette jamais', () => {
    expect(normaliserCibles(undefined)).toEqual([])
    expect(normaliserCibles(null)).toEqual([])
    expect(normaliserCibles({ results: [] })).toEqual([])
    expect(normaliserCibles([null, 3, { label: 'sans nom' }, { name: 'a' }]))
      .toEqual([{ name: 'a' }])
  })

  it('retrouve une cible par son nom logique, sinon null', () => {
    const cibles = [{ name: 'a', label: 'A', fields: [] }]
    expect(trouverCible(cibles, 'a').label).toBe('A')
    expect(trouverCible(cibles, 'b')).toBeNull()
    expect(trouverCible(undefined, 'a')).toBeNull()
  })
})

describe('useBulkEditCible (PACT118)', () => {
  it('expose la cible et sa liste blanche SERVEUR', async () => {
    render(<Sonde />)
    await waitFor(() => expect(screen.getByTestId('dispo')).toHaveTextContent('oui'))
    expect(screen.getByTestId('libelle')).toHaveTextContent('Offres groupées')
    expect(screen.getByTestId('champs')).toHaveTextContent('actif')
  })

  it("rend `disponible` faux quand la cible n'est pas enregistrée", async () => {
    render(<Sonde nom="pas.enregistree" />)
    await waitFor(() => expect(targets).toHaveBeenCalled())
    expect(screen.getByTestId('dispo')).toHaveTextContent('non')
    expect(screen.getByTestId('champs')).toHaveTextContent('')
  })

  it('poste target + ids + changes au socle', async () => {
    const user = userEvent.setup()
    render(<Sonde />)
    await waitFor(() => expect(screen.getByTestId('dispo')).toHaveTextContent('oui'))
    await user.click(screen.getByRole('button', { name: 'Appliquer' }))
    await waitFor(() => expect(appliquer).toHaveBeenCalledWith(
      'cpq.offre-groupee', [1, 2], { actif: false },
    ))
  })

  it("n'appelle pas le serveur sans identifiant sélectionné", async () => {
    const user = userEvent.setup()
    render(<Sonde />)
    await waitFor(() => expect(screen.getByTestId('dispo')).toHaveTextContent('oui'))
    await user.click(screen.getByRole('button', { name: 'Appliquer vide' }))
    expect(appliquer).not.toHaveBeenCalled()
  })

  it('dégrade sans jeter quand le catalogue est indisponible', async () => {
    targets.mockRejectedValue(new Error('réseau'))
    render(<Sonde />)
    await waitFor(() => expect(targets).toHaveBeenCalled())
    await waitFor(() => expect(screen.getByTestId('dispo')).toHaveTextContent('non'))
    expect(screen.getByTestId('erreur').textContent.length).toBeGreaterThan(0)
  })
})
