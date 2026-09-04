import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import ForecastView, { RENDER_CAP } from './ForecastView'

/* CRX36 — plafond de RENDU par colonne sur la vue Prévision (parité APX9 /
   KanbanView). La colonne « Non daté » est le pire cas : elle ramasse TOUS
   les leads sans `date_cloture_prevue`, donc potentiellement le portefeuille
   entier, et montait jusqu'ici d'un seul bloc — chaque carte avec ses
   écouteurs de glisser.

   Comme `KanbanView.apx9.test.mjs`, l'invariant central est qu'aucun appel
   RÉSEAU n'est en jeu : « Charger plus » ne fait que découper une liste déjà
   en mémoire. On le prouve en ne fournissant AUCUN prop de chargement et en
   vérifiant que le compteur d'en-tête annonce toujours le TOTAL réel. */

vi.mock('./LeadCard', () => ({
  default: ({ lead }) => <div data-testid={`lead-${lead.id}`}>{lead.nom}</div>,
}))

afterEach(() => { cleanup(); vi.clearAllMocks() })

const SURPLUS = 7
const TOTAL = RENDER_CAP + SURPLUS

// Tous SANS date de clôture : ils atterrissent dans « Non daté ».
const leadsNonDates = Array.from({ length: TOTAL }, (_, i) => ({
  id: i + 1,
  nom: `Lead ${i + 1}`,
  stage: 'NEW',
  perdu: false,
  date_cloture_prevue: null,
  devis: [],
}))

const cartesRendues = () => screen.queryAllByTestId(/^lead-/)

describe('CRX36 — plafond de rendu de la vue Prévision', () => {
  it('ne monte que RENDER_CAP cartes dans la colonne « Non daté »', () => {
    render(<ForecastView leads={leadsNonDates} />)
    expect(cartesRendues()).toHaveLength(RENDER_CAP)
  })

  it('propose « Charger plus » avec le nombre exact de restants', () => {
    render(<ForecastView leads={leadsNonDates} />)
    expect(screen.getByRole('button', { name: `Charger plus (${SURPLUS} restants)` }))
      .toBeTruthy()
  })

  it("le compteur d'en-tête annonce le TOTAL réel, pas ce qui est monté", () => {
    render(<ForecastView leads={leadsNonDates} />)
    expect(screen.getByText(String(TOTAL))).toBeTruthy()
  })

  it('« Charger plus » monte la suite et le bouton disparaît', () => {
    render(<ForecastView leads={leadsNonDates} />)
    fireEvent.click(screen.getByRole('button', { name: /Charger plus/ }))
    expect(cartesRendues()).toHaveLength(TOTAL)
    expect(screen.queryByRole('button', { name: /Charger plus/ })).toBeNull()
  })

  it("une colonne sous le plafond n'affiche aucun bouton", () => {
    render(<ForecastView leads={leadsNonDates.slice(0, 3)} />)
    expect(cartesRendues()).toHaveLength(3)
    expect(screen.queryByRole('button', { name: /Charger plus/ })).toBeNull()
  })

  it('le singulier est respecté quand il ne reste qu’un lead', () => {
    render(<ForecastView leads={leadsNonDates.slice(0, RENDER_CAP + 1)} />)
    expect(screen.getByRole('button', { name: 'Charger plus (1 restant)' }))
      .toBeTruthy()
  })
})
