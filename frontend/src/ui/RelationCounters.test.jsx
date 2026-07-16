import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { RelationCounters } from './RelationCounters'

/* VX159/VX250 — RelationCounters : « 3 devis · 1 facture impayée · 2 tickets
   SAV » en tête de fiche, UN SEUL composant consommé à l'identique par les 4
   fiches 360° + le détail Devis/Facture. Composant 100% présentation : ne
   décide jamais quoi compter, ne fait jamais d'appel réseau. Nombre + libellé
   forment UN SEUL nœud texte (« 3 devis ») — jamais un nombre nu isolé qui
   collisionnerait avec un total déjà affiché ailleurs sur le même écran
   (ex. un <Stat> existant montrant la même valeur). */

afterEach(() => { cleanup() })

function renderIn(ui) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('RelationCounters (VX159/VX250)', () => {
  it('rend rien quand tous les compteurs sont à 0 (jamais un bandeau vide)', () => {
    const { container } = renderIn(
      <RelationCounters counters={[{ label: 'devis', count: 0 }, { label: 'factures', count: 0 }]} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('omet UNIQUEMENT les compteurs à 0, garde les autres', () => {
    renderIn(
      <RelationCounters counters={[
        { label: 'devis', count: 3, to: '/ventes/devis?q=Client' },
        { label: 'chantiers', count: 0 },
        { label: 'tickets SAV', count: 2, to: '/sav?q=Client' },
      ]}
      />,
    )
    expect(screen.getByText('3 devis')).toBeInTheDocument()
    expect(screen.getByText('2 tickets SAV')).toBeInTheDocument()
    expect(screen.queryByText(/chantiers/)).not.toBeInTheDocument()
  })

  it('un compteur avec `to` est un lien cliquable vers la liste', () => {
    renderIn(
      <RelationCounters counters={[{ label: 'devis', count: 3, to: '/ventes/devis?q=Client' }]} />,
    )
    const link = screen.getByRole('link', { name: '3 devis' })
    expect(link).toHaveAttribute('href', '/ventes/devis?q=Client')
  })

  it('un compteur SANS `to` reste du texte statique — jamais un lien mort', () => {
    renderIn(<RelationCounters counters={[{ label: 'chantiers', count: 1 }]} />)
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    expect(screen.getByText('1 chantiers')).toBeInTheDocument()
  })

  it('counters absent/undefined ne casse jamais (repli tableau vide)', () => {
    const { container } = renderIn(<RelationCounters />)
    expect(container).toBeEmptyDOMElement()
  })

  it('nombre + libellé forment UN SEUL nœud texte (jamais un nombre nu isolé qui collisionnerait avec un total affiché ailleurs)', () => {
    renderIn(<RelationCounters counters={[{ label: 'devis', count: 3 }]} />)
    // Un total « 3 » nu isolé ailleurs sur l'écran (ex. un <Stat>) ne doit
    // JAMAIS matcher accidentellement ce compteur.
    expect(screen.queryByText('3')).not.toBeInTheDocument()
    expect(screen.getByText('3 devis')).toBeInTheDocument()
  })
})
