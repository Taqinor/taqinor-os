import { createElement } from 'react'
import { vi } from 'vitest'

/* EDC (gardes CI) — doubles de module PARTAGÉS des tests de l'Édition complète.

   Les tests EDC1-EDC11 (générateur embarqué + panneau du cockpit lead)
   recopiaient mot pour mot les fabriques `vi.mock` des vieux tests du
   générateur : `scripts/check_duplicats_litteraux.py` (ACAL345) les refusait
   (≥ 6 lignes identiques dans deux fichiers). Ils les prennent désormais d'ici,
   depuis la fabrique (hissée) :

     vi.mock('../../api/ventesApi', async () =>
       (await import('../../test/mocksApiDevis.js')).ventesApiMock())

   Ce module n'importe AUCUN `api/*` : une fabrique de `vi.mock` qui l'importe
   ne peut donc pas boucler sur le module qu'elle est en train de simuler.
   Mêmes valeurs par défaut que les copies d'origine : aucun réseau, réponses
   stables ; un test qui veut autre chose le pose dans son `beforeEach`. */

const vide = () => Promise.resolve({ data: {} })

// Clients / leads : listes vides, lead introuvable.
export function crmApiMock(extra = {}) {
  return {
    default: {
      getClients: vi.fn(() => Promise.resolve({ data: [] })),
      getLeads: vi.fn(() => Promise.resolve({ data: [] })),
      getLead: vi.fn(() => Promise.resolve({ data: null })),
      ...extra,
    },
  }
}

// Catalogue vide (les tests posent leurs produits dans `beforeEach`).
export function stockApiMock(extra = {}) {
  return { default: { getProduits: vi.fn(() => Promise.resolve({ data: [] })), ...extra } }
}

export function parametresApiMock() {
  return { default: { getProfile: vi.fn(vide) } }
}

// ventesApi du GÉNÉRATEUR embarqué : tout ce que `DevisGenerator` appelle.
// `getDevisById`, `replaceLignesDevis`… sont posés par chaque test.
export function ventesApiMock(extra = {}) {
  return {
    default: {
      getDevisById: vi.fn(),
      getParametresGammes: vi.fn(vide),
      getPrefillSite: vi.fn(vide),
      getOffresTaillesDevis: vi.fn(() => Promise.resolve({ data: { editable: false } })),
      lireOverrides: vi.fn(vide),
      getPrixApplicable: vi.fn(() => Promise.resolve({ data: null })),
      patchDevis: vi.fn(),
      replaceLignesDevis: vi.fn(),
      createDevisAtomic: vi.fn(),
      patchEtudeParams: vi.fn(),
      poserOverrides: vi.fn(),
      regenererOverride: vi.fn(),
      ...extra,
    },
  }
}

// ventesApi du PANNEAU du cockpit lead (`LeadDevisPanel`, générateur mocké).
export function ventesApiPanneauMock() {
  return {
    default: {
      getDevisById: vi.fn(),
      // Aperçu jamais résolu : seul le passage de phase est sous test.
      getProposalPdf: vi.fn(() => new Promise(() => {})),
      reviserDevis: vi.fn(),
      // CIQ127 — le devis automatique C&I part au serveur.
      creerDevisAuto: vi.fn(),
      getParametresGammes: vi.fn(vide),
    },
  }
}

// API « tout répond » : chaque méthode lue est un `vi.fn` qui résout
// `{ data: {} }` (ou `reponse()`) ; le test pose seulement les réponses qui comptent.
export function apiAutoMock(reponse = () => Promise.resolve({ data: {} })) {
  const fns = {}
  return {
    default: new Proxy(fns, {
      get(cible, cle) {
        if (typeof cle !== 'string' || cle === 'then' || cle === '__esModule') return undefined
        if (!cible[cle]) cible[cle] = vi.fn(reponse)
        return cible[cle]
      },
    }),
  }
}

// Props reçues par le DERNIER rendu du générateur simulé : le test joue le rôle
// de `DevisGenerator` et appelle les rappels du contrat EDC (onEnregistre /
// onVoirPdf / onDirtyChange). Même instance côté fabrique et côté test (le
// module est mis en cache une seule fois par fichier de test).
export const generateur = { props: null }

// Remplace `DevisGenerator` dans les tests du panneau : une coquille
// `generateur-monte` dont `enfants(props)` fixe le contenu (défaut : « editId=… »,
// lu par plusieurs tests).
export function generateurSimule(enfants = (props) => `editId=${String(props.editId)}`) {
  return {
    default: (props) => {
      generateur.props = props
      return createElement('div', { 'data-testid': 'generateur-monte' }, enfants(props))
    },
  }
}
