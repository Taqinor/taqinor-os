// SPL40/SPL41 — fabrique PARTAGÉE des mocks d'API des goldens du générateur.
//
// Module volontairement minuscule (il n'importe que vitest) : il est appelé
// depuis une fabrique `vi.mock`, et le harnais, lui, importe le magasin Redux
// donc axios — l'importer ici créerait un cycle avec le mock d'axios.
// Chaque entrée de DEFAUTS est la valeur `data` rendue par la fonction ; un
// objet frais est rendu à chaque appel (jamais de référence partagée).
import { vi } from 'vitest'

export const DEFAUTS = {
  crmApi: { getClients: [], getLeads: [], getLead: null },
  stockApi: { getProduits: [] },
  parametresApi: { getProfile: {} },
  ventesApi: {
    getDevisById: {},
    getParametresGammes: {},
    getPrefillSite: {},
    getOffresTaillesDevis: { editable: false },
    lireOverrides: {},
    getPrixApplicable: {},
    patchDevis: {},
    replaceLignesDevis: {},
    createDevisAtomic: { id: 999 },
    patchEtudeParams: {},
    poserOverrides: {},
    regenererOverride: {},
    etudeCiPreview: null,
    economieCiPreview: null,
    postEtudeHorairePreview: null,
  },
  axios: { get: [], post: null, patch: null, put: null, delete: null },
}

const frais = (valeur) => JSON.parse(JSON.stringify(valeur))

/** Module mocké `{ default: { fn: vi.fn(() => Promise.resolve({ data })) } }`. */
export function mockApi(nom, ajouts = {}) {
  const defauts = { ...DEFAUTS[nom], ...ajouts }
  const fonctions = {}
  for (const [fn, data] of Object.entries(defauts)) {
    fonctions[fn] = vi.fn(() => Promise.resolve({ data: frais(data) }))
  }
  return { default: fonctions }
}
