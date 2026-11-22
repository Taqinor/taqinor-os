/* ACAL872 — la GARDE du « ? » (`Pourquoi`) et le composant lui-même.
   Le registre est lu sur le système de fichiers (`data/explications.json`,
   comme `reponseContrat`) : (a) toute `cle="…"` d'un `<Pourquoi` du module est
   au registre ; (b) dans un écran CÂBLÉ (un onglet de `ecrans[]` dont au moins
   une grandeur est déjà montée), chaque entrée de cet écran est montée ;
   (c) la garde de rendu `chiffresSansGrandeur` nomme tout chiffre sans « ? »
   ni dérogation motivée — chaque écran câblé l'appelle dans son propre test. */
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { createElement } from 'react'
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { fichierContrat, reponseContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { explications: vi.fn() } },
}))

import calepinageApi from '../../../api/calepinageApi'
import Pourquoi from './Pourquoi'
import { chiffresSansGrandeur, remplirPhrase } from './useExplications'

const REGISTRE = JSON.parse(readFileSync(
  join(fichierContrat('calepinage', 'x'), '..', '..', 'data', 'explications.json'), 'utf8')).entrees
const MODULE = join(import.meta.dirname, '..')
const SOURCES = readdirSync(MODULE, { recursive: true })
  .filter((f) => /\.jsx?$/.test(f) && !/\.test\./.test(f))
  .map((f) => readFileSync(join(MODULE, f), 'utf8'))
const montees = SOURCES.flatMap((s) => [...s.matchAll(/<Pourquoi\b[^>]*\bcle="([^"]+)"/g)].map((m) => m[1]))

afterEach(cleanup)

describe('ACAL872 — garde du registre', () => {
  it('(a) toute clé montée est au registre', () => {
    const connues = new Set(REGISTRE.map((e) => e.cle))
    expect(montees.filter((c) => !connues.has(c))).toEqual([])
  })

  it('(b) dans un écran câblé, chaque grandeur du registre est montée', () => {
    const ecranDe = (c) => REGISTRE.find((e) => e.cle === c)?.ecrans ?? []
    const cables = new Set(montees.flatMap(ecranDe))
    const oubliees = REGISTRE
      .filter((e) => (e.ecrans ?? []).some((o) => cables.has(o)) && !montees.includes(e.cle))
      .map((e) => e.cle)
    expect(oubliees).toEqual([])
  })
})

describe('ACAL872 — garde de rendu (c)', () => {
  const tuile = (label) => `<div class="card"><span>${label}</span>`
    + '<div class="stat-value-solidify">1 234 kWh</div></div>'

  it('une tuile Stat sans « ? » est nommée par son texte', () => {
    document.body.innerHTML = tuile('Production')
    expect(chiffresSansGrandeur(document.body)).toEqual(['1 234 kWh'])
  })

  it('une tuile avec son « ? » ou une dérogation motivée passe', () => {
    document.body.innerHTML = tuile('<button data-grandeur="production.p50_kwh"></button>')
      + tuile('<span data-sans-grandeur="compteur de modules, sans unité physique"></span>')
    expect(chiffresSansGrandeur(document.body)).toEqual([])
  })

  it('une dérogation vide (sans raison) ne compte pas', () => {
    document.body.innerHTML = tuile('<span data-sans-grandeur=""></span>')
    expect(chiffresSansGrandeur(document.body)).toEqual(['1 234 kWh'])
  })
})

describe('ACAL872 — la bulle', () => {
  const servir = () => calepinageApi.calepinages.explications
    .mockResolvedValue(reponseContrat('calepinage', 'calepinage_explications'))
  const resultat = reponseContrat('calepinage', 'calepinage_resultat').data
  // Fichier `.js` (nom imposé) : pas de JSX, `createElement`.
  const rendre = (props) => render(createElement(MemoryRouter, null, createElement(Pourquoi, props)))

  it('dit la phrase avec les valeurs servies, le geste et le lexique', async () => {
    servir()
    rendre({ cle: 'production.p50_kwh', valeurs: resultat })
    const bouton = screen.getByRole('button', { name: 'Pourquoi ce chiffre ?' })
    expect(bouton).toHaveAttribute('data-grandeur', 'production.p50_kwh')
    expect(bouton.className).toContain('size-11')
    await userEvent.click(bouton)
    const entree = REGISTRE.find((e) => e.cle === 'production.p50_kwh')
    // Le séparateur de milliers est une espace fine : la comparaison normalise les blancs.
    const attendue = remplirPhrase(entree, resultat).replace(/\s+/g, ' ')
    expect(await screen.findByText(attendue)).toBeInTheDocument()
    expect(attendue).toContain('8,64 kWc')
    expect(screen.getByText(entree.geste)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Voir le lexique complet/ })).toHaveAttribute('href', '/aide/lexique')
  })

  it('une valeur absente s’écrit « valeur non publiée », jamais 0', () => {
    const entree = REGISTRE.find((e) => e.cle === 'production.p50_kwh')
    const phrase = remplirPhrase(entree, { production: { total: { kwc: null } } })
    expect(phrase).toContain('valeur non publiée')
    expect(phrase).not.toMatch(/\b0 kWh/)
  })

  it('une clé absente du registre ne rend rien', async () => {
    servir()
    const { container } = rendre({ cle: 'inconnue.nulle_part' })
    await vi.waitFor(() => expect(container).toBeEmptyDOMElement())
  })
})
