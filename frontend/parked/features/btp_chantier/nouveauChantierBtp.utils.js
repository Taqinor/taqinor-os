/* ============================================================================
   NTCON23 — helpers PURS de l'assistant « Créer un chantier BTP » : brouillon
   local (reprise après abandon) et lots types suggérés.

   Aucun composant ici (règle `react-refresh/only-export-components`).
   TOUTE lecture/écriture `localStorage` est protégée : navigation privée,
   site data bloqué ou capture de vignette peuvent la faire échouer — l'écran
   doit rester fonctionnel sans brouillon.
   ========================================================================== */

export const BROUILLON_CLE = 'btp-nouveau-chantier-brouillon'

/* Corps d'état classiques d'un chantier TCE — SUGGESTION éditable, jamais
   imposée (le fondateur ou le conducteur de travaux décide de ses lots). */
export const LOTS_TYPES_DEFAUT = [
  'Gros-œuvre', 'Électricité', 'Plomberie', 'CVC', 'Finitions',
]

export function lotSuggere(nom) {
  return {
    nom,
    interne: true,
    sous_traitant: '',
    date_debut_prevue: '',
    date_fin_prevue: '',
  }
}

export function lotsSuggeres() {
  return LOTS_TYPES_DEFAUT.map(lotSuggere)
}

export function brouillonVide() {
  return {
    chantier: '',
    lots: [],
    ppspsTitre: '',
    ppspsDocumentGedId: '',
    checklistParDefaut: true,
  }
}

export function chargerBrouillon() {
  try {
    const brut = window.localStorage.getItem(BROUILLON_CLE)
    if (!brut) return brouillonVide()
    const parse = JSON.parse(brut)
    if (!parse || typeof parse !== 'object') return brouillonVide()
    return { ...brouillonVide(), ...parse, lots: Array.isArray(parse.lots) ? parse.lots : [] }
  } catch {
    return brouillonVide()
  }
}

export function enregistrerBrouillon(brouillon) {
  try {
    window.localStorage.setItem(BROUILLON_CLE, JSON.stringify(brouillon))
    return true
  } catch {
    return false
  }
}

export function effacerBrouillon() {
  try {
    window.localStorage.removeItem(BROUILLON_CLE)
    return true
  } catch {
    return false
  }
}
