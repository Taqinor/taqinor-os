import { describe, it, expect } from 'vitest'
import reducer, { loadChatHistory } from '../features/ia/store/iaSlice'

describe('iaSlice - loadChatHistory.fulfilled', () => {
  const etat = () => reducer(undefined, { type: '@@init' })

  it('charge une vraie liste de messages', () => {
    const liste = [{ role: 'user', content: 'salut' }]
    const s = reducer(etat(), loadChatHistory.fulfilled(liste, 'rid'))
    expect(s.messages).toEqual(liste)
  })

  it('ignore une reponse non-liste (HTML du repli SPA) au lieu de planter', () => {
    const s = reducer(etat(), loadChatHistory.fulfilled('<!doctype html><html></html>', 'rid'))
    expect(Array.isArray(s.messages)).toBe(true)
    expect(s.messages).toEqual([])
  })

  // COP-F1 — le contrat `historique` : `cartes` est rejoué tel quel, une
  // proposition rechargée est inactive (son jeton a vécu).
  it('rejoue les cartes de l\'historique ; une proposition rechargee est expiree', () => {
    const liste = [
      { role: 'user', content: 'envoie le devis' },
      {
        role: 'agent', content: 'Voici.',
        cartes: [
          { type: 'proposition', action_key: 'a', libelle: 'A', apercu: 'Envoyer ?', confirm_token: 't', expire_dans_s: 300 },
          { type: 'resultat', action_key: 'b', libelle: 'B', carte: null, donnees: { reference: 'R' } },
        ],
      },
    ]
    const s = reducer(etat(), loadChatHistory.fulfilled(liste, 'rid'))
    expect(s.messages[1].cartes[0].etat).toBe('expiree')
    expect(s.messages[1].cartes[1].donnees.reference).toBe('R')
  })

  it('une carte touche rechargee perd sa proposition (carte-echo) : plus de « Enregistrer » d\'hier', () => {
    const proposition = { geste: 'fait', libelle: 'L', effet: 'E', corps: { outcome: 'non_joint' } }
    const liste = [{
      role: 'agent', content: 'Voici.',
      cartes: [{ type: 'resultat', action_key: 'crm.suivi.proposer_reponse', libelle: 'P', carte: 'touche',
        donnees: { touche: { id: 412 }, proposition, proposition_refus: null } }],
    }]
    const s = reducer(etat(), loadChatHistory.fulfilled(liste, 'rid'))
    expect(s.messages[0].cartes[0].donnees.proposition).toBeNull()
    expect(s.messages[0].cartes[0].donnees.touche.id).toBe(412)
    // L'historique reçu n'est pas modifié en place.
    expect(liste[0].cartes[0].donnees.proposition).toEqual(proposition)
  })

  it('n\'ecrase JAMAIS une conversation deja en cours (cartes locales, question envoyee pendant le chargement)', () => {
    const encours = { ...etat(), messages: [{ role: 'user', content: 'plus recent' }] }
    const s = reducer(encours, loadChatHistory.fulfilled([{ role: 'user', content: 'ancien' }], 'rid'))
    expect(s.messages).toEqual([{ role: 'user', content: 'plus recent' }])
  })
})
