import { describe, it, expect } from 'vitest'
import {
  cockpitProfile,
  leadsARelancer,
  devisQuiExpirent,
  ticketsAujourdhui,
  ticketsUrgents,
  ticketsSlaEnRetard,
} from './Dashboard.jsx'

/* VX27 — Cockpit du matin : layout par rôle + bandeau « aujourd'hui ».
   On teste les fonctions PURES qui décident CE QUE chaque rôle voit (le
   « rendu conditionnel » du composant est piloté par cockpitProfile) et les
   dérivations de signaux du jour — sans monter le composant ni le store. */

// Date fixe pour des comparaisons déterministes.
const NOW = new Date('2026-07-11T09:00:00')

describe('cockpitProfile — classification de rôle (VX27)', () => {
  it('directeur/admin → vue macro', () => {
    expect(cockpitProfile({ roleNom: 'Directeur' })).toBe('directeur')
    expect(cockpitProfile({ roleNom: 'Gérant' })).toBe('directeur')
    expect(cockpitProfile({ roleTier: 'admin', roleNom: 'Peu importe' })).toBe('directeur')
  })
  it('commercial → cockpit ventes', () => {
    expect(cockpitProfile({ roleNom: 'Commercial' })).toBe('commercial')
    expect(cockpitProfile({ roleNom: 'Commercial responsable' })).toBe('commercial')
    expect(cockpitProfile({ roleNom: 'Chargé de vente' })).toBe('commercial')
  })
  it('SAV/technicien → cockpit terrain', () => {
    expect(cockpitProfile({ roleNom: 'Technicien SAV' })).toBe('sav')
    expect(cockpitProfile({ roleNom: 'Support après-vente' })).toBe('sav')
  })
  it('rôle inconnu ou vide → directeur (repli macro, comportement historique)', () => {
    expect(cockpitProfile({ roleNom: null })).toBe('directeur')
    expect(cockpitProfile({})).toBe('directeur')
    expect(cockpitProfile({ roleNom: 'Magasinier' })).toBe('directeur')
  })
  it('admin l’emporte sur un libellé « commercial »', () => {
    expect(cockpitProfile({ roleTier: 'admin', roleNom: 'Commercial' })).toBe('directeur')
  })
})

describe('leadsARelancer (VX27)', () => {
  const leads = [
    { id: 1, nom: 'A', owner: 7, relance_date: '2026-07-10' }, // hier → à relancer
    { id: 2, nom: 'B', owner: 7, relance_date: '2026-07-11' }, // aujourd'hui → à relancer
    { id: 3, nom: 'C', owner: 7, relance_date: '2026-07-20' }, // futur → non
    { id: 4, nom: 'D', owner: 7, relance_date: null },         // pas de relance → non
    { id: 5, nom: 'E', owner: 9, relance_date: '2026-07-01' }, // autre owner
    { id: 6, nom: 'F', owner: 7, relance_date: '2026-07-01', perdu: true }, // perdu → non
    { id: 7, nom: 'G', owner: 7, relance_date: '2026-07-01', is_archived: true }, // archivé → non
  ]
  it('retient les relances dues ou dépassées, non perdues/archivées', () => {
    const r = leadsARelancer(leads, { now: NOW }).map((l) => l.id)
    expect(r).toEqual([1, 2, 5])
  })
  it('scope à « mes » leads quand ownerId est fourni', () => {
    const r = leadsARelancer(leads, { ownerId: 7, now: NOW }).map((l) => l.id)
    expect(r).toEqual([1, 2])
  })
  it('liste vide / nulle ne casse pas', () => {
    expect(leadsARelancer(null, { now: NOW })).toEqual([])
    expect(leadsARelancer([], { now: NOW })).toEqual([])
  })
})

describe('devisQuiExpirent (VX27)', () => {
  const devis = [
    { id: 1, statut: 'envoye', date_validite: '2026-07-12' },   // ≤7j → oui
    { id: 2, statut: 'brouillon', date_validite: '2026-07-11' },// aujourd'hui → oui
    { id: 3, statut: 'envoye', date_validite: '2026-07-25' },   // >7j → non
    { id: 4, statut: 'accepte', date_validite: '2026-07-12' },  // clôturé → non
    { id: 5, statut: 'envoye', date_validite: null },           // sans date → non
    { id: 6, statut: 'envoye', date_validite: '2026-07-01' },   // déjà expiré → non
  ]
  it('retient les devis ouverts expirant dans la fenêtre de N jours', () => {
    const r = devisQuiExpirent(devis, { days: 7, now: NOW }).map((d) => d.id)
    expect(r).toEqual([1, 2])
  })
})

describe('tickets SAV — signaux terrain (VX27)', () => {
  const tickets = [
    { id: 1, statut: 'nouveau', priorite: 'urgente', date_ouverture: '2026-07-08' },
    { id: 2, statut: 'en_cours', priorite: 'haute', date_ouverture: '2026-07-11' },
    { id: 3, statut: 'cloture', priorite: 'urgente', date_ouverture: '2026-06-01' },
    { id: 4, statut: 'planifie', priorite: 'normale', date_ouverture: '2026-07-11' },
    { id: 5, statut: 'nouveau', priorite: 'urgente', date_ouverture: '2026-07-08', annule: true },
  ]
  it('ticketsAujourdhui = ouverts non annulés', () => {
    expect(ticketsAujourdhui(tickets).map((t) => t.id)).toEqual([1, 2, 4])
  })
  it('ticketsUrgents = haute/urgente ouverts non annulés', () => {
    expect(ticketsUrgents(tickets).map((t) => t.id)).toEqual([1, 2])
  })
  it('ticketsSlaEnRetard = niveau SLA « late »', () => {
    // #1 urgente ouverte depuis 3 j (seuil urgente = 2 j) → late.
    const r = ticketsSlaEnRetard(tickets, NOW).map((t) => t.id)
    expect(r).toContain(1)
    // #3 clôturé, #5 annulé → jamais late.
    expect(r).not.toContain(3)
    expect(r).not.toContain(5)
  })
})
