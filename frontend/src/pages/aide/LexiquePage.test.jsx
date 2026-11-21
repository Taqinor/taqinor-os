import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import LexiquePage from './LexiquePage'

/* VX247(d) — glossaire métier statique : ≥15 termes (DoD), recherche simple,
   aucun appel réseau. */

function renderPage() {
  return render(<MemoryRouter><LexiquePage /></MemoryRouter>)
}

describe('LexiquePage (VX247)', () => {
  it('affiche au moins 15 termes du lexique', () => {
    const { container } = renderPage()
    // `<dt>` par terme (liste de définitions) — pas de dépendance à la
    // résolution de rôle ARIA (variable selon les moteurs de test).
    expect(container.querySelectorAll('dt').length).toBeGreaterThanOrEqual(15)
  })

  it('un terme connu (kWc) porte sa définition', () => {
    renderPage()
    expect(screen.getByText(/kWc \(kilowatt-crête\)/)).toBeInTheDocument()
    expect(screen.getByText(/puissance nominale maximale/i)).toBeInTheDocument()
  })

  it('la recherche filtre la liste (aucun appel réseau, purement local)', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.type(screen.getByLabelText('Rechercher un terme du lexique'), 'FEC')
    expect(screen.getByText(/FEC \(fichier des écritures comptables\)/)).toBeInTheDocument()
    expect(screen.queryByText(/^kWc/)).not.toBeInTheDocument()
  })

  it('une recherche sans résultat affiche un message clair (jamais une liste vide silencieuse)', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.type(screen.getByLabelText('Rechercher un terme du lexique'), 'zzz-inexistant')
    expect(screen.getByText(/Aucun terme ne correspond/)).toBeInTheDocument()
  })
})

/* ACAL902 — les termes électriques qu'une commerciale rencontre dans
   l'atelier : chacun a une entrée trouvable et définie sans aucun chiffre. */
describe('LexiquePage — tensions, courant et ratio DC/AC (ACAL902)', () => {
  it.each([
    ['Voc', /^Voc \(tension à vide\)$/],
    ['Vmp', /^Vmp \(/],
    ['Isc', /^Isc \(/],
    ['DC/AC', /^Ratio DC\/AC$/],
  ])('la recherche « %s » rend une entrée définie sans chiffre', async (recherche, motif) => {
    const user = userEvent.setup()
    const { container } = renderPage()
    await user.type(screen.getByLabelText('Rechercher un terme du lexique'), recherche)
    const dt = Array.from(container.querySelectorAll('dt'))
      .find((el) => motif.test(el.textContent))
    expect(dt, `entrée absente : ${recherche}`).toBeTruthy()
    const definition = dt.nextElementSibling?.textContent ?? ''
    expect(definition.trim().length).toBeGreaterThan(0)
    expect(definition).not.toMatch(/\d/)
  })
})

/* CALX396 — les mots que les écrans du CALEPINAGE affichent. Chaque terme
   est présent, la liste reste dans l'ordre alphabétique (collation
   française, accents et casse ignorés), et AUCUNE définition neuve ne porte
   de chiffre : une définition n'affirme jamais une valeur. */
const TERMES_CALEPINAGE = [
  /^Albédo$/, /^Azimut$/, /^Bifacialité$/, /^Calepinage$/, /^Écrêtage$/,
  /^GCR \(/, /^Horizon lointain$/, /^LID \(/, /^Mismatch \(/, /^MPPT \(/,
  /^Ombrière$/, /^P50 \/ P75 \/ P90$/, /^PR \(/, /^PVGIS$/, /^Tilt \(/,
  /^TMY \(/, /^TSRF \(/,
]

describe('LexiquePage — les mots du calepinage (CALX396)', () => {
  const termes = (container) => Array.from(container.querySelectorAll('dt'))

  it('chaque terme du calepinage est présent', () => {
    const { container } = renderPage()
    const mots = termes(container).map((dt) => dt.textContent)
    for (const motif of TERMES_CALEPINAGE) {
      expect(mots.some((mot) => motif.test(mot)), `terme absent : ${motif}`).toBe(true)
    }
  })

  it('la liste reste dans l’ordre alphabétique', () => {
    const { container } = renderPage()
    const mots = termes(container).map((dt) => dt.textContent)
    const collation = new Intl.Collator('fr', { sensitivity: 'base' })
    expect(mots).toEqual([...mots].sort(collation.compare))
  })

  it('aucune définition du calepinage n’affirme une valeur (aucun chiffre)', () => {
    const { container } = renderPage()
    for (const dt of termes(container)) {
      if (!TERMES_CALEPINAGE.some((motif) => motif.test(dt.textContent))) continue
      const definition = dt.nextElementSibling?.textContent ?? ''
      expect(definition.trim().length, `définition vide : ${dt.textContent}`).toBeGreaterThan(0)
      expect(definition, `chiffre dans la définition de ${dt.textContent}`).not.toMatch(/\d/)
    }
  })
})
