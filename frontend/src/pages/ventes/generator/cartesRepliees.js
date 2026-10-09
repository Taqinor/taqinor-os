// EDC9 — CARTES D'ÉTUDE REPLIABLES en Édition complète (fondateur 09/10/2026 :
// « l'ouvrier doit descendre trop loin pour voir la fin »).
// ---------------------------------------------------------------------------
// En Édition complète, « Aperçu de la Simulation » et « Surcharges (registre) »
// sont REPLIÉES PAR DÉFAUT (on y vient corriger des lignes, pas relire
// l'étude) ; jamais masquées : leur en-tête reste, un clic les déplie. Les
// lignes, l'argent et l'échéancier ne sont JAMAIS repliables (NN/g : pas
// d'accordéon pour le contenu principal).
//
// L'état est mémorisé PAR UTILISATEUR dans `localStorage` (clé unique
// `devis:edition:cartes-repliees`, une entrée par id d'utilisateur : deux
// vendeurs sur le même poste gardent chacun leur choix). Stockage indisponible
// (navigation privée, quota) : on retombe sur le défaut, sans erreur.
import { useCallback, useState } from 'react'
import { useSelector } from 'react-redux'

export const CLE_CARTES_REPLIEES = 'devis:edition:cartes-repliees'

/** Défaut : les deux cartes d'étude repliées. */
export const CARTES_REPLIEES_DEFAUT = Object.freeze({ simulation: true, surcharges: true })

const cleUtilisateur = (userId) => (userId == null ? '_' : String(userId))

function lireTout() {
  try {
    const brut = window.localStorage.getItem(CLE_CARTES_REPLIEES)
    const valeur = brut ? JSON.parse(brut) : null
    return valeur && typeof valeur === 'object' && !Array.isArray(valeur) ? valeur : {}
  } catch {
    return {}
  }
}

/** État replié des cartes pour un utilisateur (défaut complété, booléens seuls). */
export function lireCartesRepliees(userId) {
  const propre = lireTout()[cleUtilisateur(userId)] || {}
  const etat = { ...CARTES_REPLIEES_DEFAUT }
  for (const carte of Object.keys(CARTES_REPLIEES_DEFAUT)) {
    if (typeof propre[carte] === 'boolean') etat[carte] = propre[carte]
  }
  return etat
}

function ecrireCartesRepliees(userId, etat) {
  try {
    const tout = lireTout()
    tout[cleUtilisateur(userId)] = etat
    window.localStorage.setItem(CLE_CARTES_REPLIEES, JSON.stringify(tout))
  } catch {
    /* stockage indisponible : le choix vaut pour la session seulement */
  }
}

/**
 * `[etat, basculer]` — `etat.simulation` / `etat.surcharges` (vrai = repliée),
 * `basculer('simulation')` inverse une carte et mémorise le choix.
 */
export function useCartesRepliees() {
  const userId = useSelector((s) => s.auth?.user?.id ?? null)
  const [etat, setEtat] = useState(() => lireCartesRepliees(userId))
  const basculer = useCallback((carte) => {
    const apres = { ...etat, [carte]: !etat[carte] }
    setEtat(apres)
    ecrireCartesRepliees(userId, apres)
  }, [etat, userId])
  return [etat, basculer]
}
