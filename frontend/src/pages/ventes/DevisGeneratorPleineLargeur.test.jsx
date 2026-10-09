// EDC2 — l'Édition complète prend toute la largeur : la racine du générateur
// est le conteneur interrogé (`gen-root`), le rail récapitulatif ne porte plus
// AUCUNE classe `lg:` (sa visibilité suit `@container gen`, index.css bloc
// EDC2) et le total condensé du pied n'est plus masqué par `lg:hidden`.
//
// Écran RÉEL rendu (embarqué et pleine page), API mockées.
// Run : npx vitest run src/pages/ventes/DevisGeneratorPleineLargeur.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'

import {
  DEVIS_INSTALLATION, renderGenerateurEdition, renderGenerateurPage, preparerApisGenerateur,
} from '../../test/generateurEmbarque'

// EDC (gardes CI) : fabriques partagées — src/test/mocksApiDevis.js.
vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiMock())

import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'

beforeEach(() => preparerApisGenerateur({
  stockApi, ventesApi, produits: [], devis: DEVIS_INSTALLATION,
}))

function verifierRail(container) {
  const racine = container.querySelector('.gen-root')
  expect(racine).not.toBeNull()
  const rail = container.querySelector('aside.gen-summary-rail')
  expect(rail).not.toBeNull()
  // Plus aucune classe `lg:` ni `hidden` : la container query décide seule.
  const classes = [...rail.classList]
  expect(classes.filter((c) => c.startsWith('lg:'))).toEqual([])
  expect(classes).not.toContain('hidden')
  // Plus de `top: var(--header-h, 64px)` en ligne (64 px d'un en-tête absent).
  expect(rail.getAttribute('style')).toBeNull()
  // Le rail est bien DANS la racine interrogée (un conteneur ne s'interroge
  // pas lui-même : le rail doit en être un descendant).
  expect(racine.contains(rail)).toBe(true)
  // Total condensé du pied : piloté par `gen-ttc-condense`, plus par lg:hidden.
  const condense = container.querySelector('.gen-actions-sticky .gen-ttc-condense')
  expect(condense).not.toBeNull()
  expect(condense.classList.contains('lg:hidden')).toBe(false)
}

describe('EDC2 — racine gen-root, rail sans classe lg:', () => {
  it('embarqué (Édition complète du panneau) : gen-root + gen-embedded, rail piloté par container query', async () => {
    const { container } = renderGenerateurEdition()
    await waitFor(() => expect(ventesApi.getDevisById).toHaveBeenCalledWith(42))
    await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    const racine = container.querySelector('.gen-root')
    expect(racine.classList.contains('gen-embedded')).toBe(true)
    verifierRail(container)
  })

  it('pleine page (?edit=) : gen-root + gen-page, rail piloté par container query', async () => {
    const { container } = renderGenerateurPage()
    await waitFor(() => expect(ventesApi.getDevisById).toHaveBeenCalledWith('42'))
    await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    const racine = container.querySelector('.gen-root')
    expect(racine.classList.contains('gen-page')).toBe(true)
    verifierRail(container)
  })

  it('table des lignes : largeurs fixes sur les colonnes numériques, Désignation/Produit flexibles', async () => {
    const { container } = renderGenerateurEdition()
    await screen.findByDisplayValue('Installation')
    const entetes = [...container.querySelectorAll('table.lines-table thead th')]
    const largeur = (texte) => entetes.find((th) => th.textContent.trim() === texte)?.style.width
    expect(largeur('Qté')).toBe('96px')
    expect(largeur('Prix Unit. TTC')).toBe('128px')
    expect(largeur('TVA %')).toBe('72px')
    expect(largeur('Total TTC')).toBe('128px')
    expect(largeur('Option')).toBe('56px')
    expect(largeur('Ordre')).toBe('72px')
    expect(entetes.at(-1).style.width).toBe('40px')
    const designation = entetes.find((th) => th.textContent.trim() === 'Désignation')
    expect(designation.style.width).toBe('')
    expect(designation.style.minWidth).toBe('160px')
  })
})
