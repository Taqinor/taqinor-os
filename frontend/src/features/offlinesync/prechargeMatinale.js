// NTMOB28 — Pré-chargement PROACTIF de la tournée du jour.
//
// Au démarrage matinal de l'app (réseau présent + créneau matinal), on remplit
// silencieusement le cache de LECTURE (NTMOB27) avec les interventions/chantiers
// planifiés aujourd'hui, pour qu'ils soient consultables hors-ligne dès le
// départ en tournée — sans que le technicien ait à ouvrir quoi que ce soit.
//
// Rien de nouveau côté serveur : on réutilise la liste DÉJÀ exposée par
// « Ma journée » (`installations/interventions/ma-tournee/`). Une seule fois par
// jour et par appareil ; hors-ligne ou l'après-midi, c'est un NO-OP.
// Logique pure et injectable (aucun React, aucun import réseau ici).

export const FLAG_KEY = 'taqinor.prechargementTournee'
/** Créneau « matinal » : avant midi (le départ en tournée se fait le matin). */
export const HEURE_LIMITE = 12

function storage() {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null
  } catch {
    return null
  }
}

export function dernierPrechargement() {
  try {
    return storage()?.getItem(FLAG_KEY) || null
  } catch {
    return null
  }
}

export function marquerPrecharge(jour) {
  try {
    storage()?.setItem(FLAG_KEY, jour)
  } catch { /* stockage indisponible : on repréchargera au prochain démarrage */ }
}

/**
 * doitPrecharger — décision PURE, testable sans réseau ni horloge réelle.
 * Vrai seulement si : en ligne, avant `HEURE_LIMITE`, et pas déjà fait pour ce
 * jour sur cet appareil.
 */
export function doitPrecharger({ enLigne, heure, jour, dejaFait }) {
  if (!enLigne) return false
  if (heure >= HEURE_LIMITE) return false
  return dejaFait !== jour
}

/**
 * prechargerTournee — remplit le cache de lecture avec la tournée du jour ET
 * chaque intervention prise isolément (c'est la fiche que le technicien ouvrira
 * sur place). Toute erreur est AVALÉE : un pré-chargement est un confort, il ne
 * doit jamais faire échouer un démarrage d'app.
 * @returns le nombre de fiches mises en cache.
 */
export async function prechargerTournee({ chargerTournee, cache, jour, now = Date.now() }) {
  try {
    const reponse = await chargerTournee(jour)
    const stops = reponse?.data?.stops ?? []
    await cache.put('tournee', jour, stops, now)
    for (const stop of stops) {
      await cache.put('intervention', stop.id, stop, now)
    }
    marquerPrecharge(jour)
    return stops.length
  } catch {
    return 0
  }
}
