import { describe, it, expect, beforeAll, vi } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import NouvelleToitureWizard from './NouvelleToitureWizard'

/* AOF78 — le contrat testé ici est celui du POINT DE CRÉATION UNIQUE :
   les trois portes produisent le MÊME objet Toiture et ouvrent le MÊME éditeur,
   elles se cumulent, et aucune n'est définitive. */

beforeAll(() => {
  if (typeof window.matchMedia !== 'function') {
    window.matchMedia = (query) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    })
  }
})

async function creerAvec(portesACocher) {
  const onCreer = vi.fn()
  const user = userEvent.setup()
  render(<NouvelleToitureWizard open onOpenChange={() => {}} onCreer={onCreer} />)
  await user.type(screen.getByLabelText('Nom de la toiture'), 'Toiture A')
  for (const cle of portesACocher) {
    await user.click(document.querySelector(`[data-ao-porte="${cle}"]`))
  }
  await user.click(screen.getByRole('button', { name: /Ouvrir l'atelier/i }))
  return onCreer
}

describe('NouvelleToitureWizard (AOF78)', () => {
  it('la porte « importer un plan » produit une toiture de l’atelier unique', async () => {
    const onCreer = await creerAvec(['import'])
    expect(onCreer).toHaveBeenCalledTimes(1)
    const toiture = onCreer.mock.calls[0][0]
    expect(toiture.editeur).toBe('atelier-toiture')
    expect(toiture.portes).toEqual(['import'])
  })

  it('la porte « tracer » produit une toiture de l’atelier unique', async () => {
    const onCreer = await creerAvec(['trace'])
    const toiture = onCreer.mock.calls[0][0]
    expect(toiture.editeur).toBe('atelier-toiture')
    expect(toiture.portes).toEqual(['trace'])
  })

  it('la porte « reprendre depuis la carte » produit une toiture de l’atelier unique', async () => {
    const onCreer = await creerAvec(['carte'])
    const toiture = onCreer.mock.calls[0][0]
    expect(toiture.editeur).toBe('atelier-toiture')
    expect(toiture.portes).toEqual(['carte'])
  })

  it('aucune duplication d’éditeur : les trois branches donnent le même objet aux portes près', async () => {
    const objets = []
    for (const cle of ['import', 'trace', 'carte']) {
      // Chaque branche est rendue seule : sans ce démontage, les trois modales
      // coexisteraient dans le même test et les requêtes deviendraient ambiguës.
      cleanup()
      const onCreer = await creerAvec([cle])
      const { portes, ...reste } = onCreer.mock.calls[0][0]
      expect(portes).toEqual([cle])
      objets.push(reste)
    }
    expect(objets[1]).toEqual(objets[0])
    expect(objets[2]).toEqual(objets[0])
  })

  it('les portes sont CUMULABLES (plan importé + tracé)', async () => {
    const onCreer = await creerAvec(['import', 'trace'])
    expect(onCreer.mock.calls[0][0].portes).toEqual(['import', 'trace'])
  })

  it('le choix de porte n’est JAMAIS définitif : on peut décocher', async () => {
    const user = userEvent.setup()
    const onCreer = vi.fn()
    render(<NouvelleToitureWizard open onOpenChange={() => {}} onCreer={onCreer} />)
    await user.type(screen.getByLabelText('Nom de la toiture'), 'Toiture B')
    const bouton = document.querySelector('[data-ao-porte="carte"]')
    await user.click(bouton)
    expect(bouton.getAttribute('aria-pressed')).toBe('true')
    await user.click(bouton)
    expect(bouton.getAttribute('aria-pressed')).toBe('false')
    await user.click(screen.getByRole('button', { name: /Ouvrir l'atelier/i }))
    expect(onCreer.mock.calls[0][0].portes).toEqual([])
  })

  it('le panneau d’une porte est injecté, jamais importé par le wizard', async () => {
    const user = userEvent.setup()
    render(
      <NouvelleToitureWizard
        open
        onOpenChange={() => {}}
        onCreer={() => {}}
        panneaux={{ trace: <p>Panneau de tracé</p> }}
      />,
    )
    expect(screen.queryByText('Panneau de tracé')).toBeNull()
    await user.click(document.querySelector('[data-ao-porte="trace"]'))
    expect(screen.getByText('Panneau de tracé')).toBeTruthy()
  })

  it('sans nom, la création est impossible', () => {
    render(<NouvelleToitureWizard open onOpenChange={() => {}} onCreer={() => {}} />)
    expect(screen.getByRole('button', { name: /Ouvrir l'atelier/i })).toBeDisabled()
  })
})
