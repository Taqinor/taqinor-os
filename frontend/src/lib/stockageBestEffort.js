// ENF15 — écriture/suppression de stockage navigateur « best-effort » : navigation privée,
// quota plein ou stockage bloqué ne doivent JAMAIS bloquer l'écran (préférence d'affichage,
// miroir de brouillon, repli de section…). Un seul endroit décide que cet échec est non
// fatal et le dit par le retour (`false`) au lieu d'un `catch {}` vide recopié partout.
// Valeurs BRUTES (chaînes) : pour du JSON avec éviction sur quota, voir `lib/safeStorage.js`.

function stockage(type) {
  return type === 'session' ? window.sessionStorage : window.localStorage
}

/** `true` si l'écriture a réussi, `false` si le stockage est indisponible ou plein. */
export function ecrireStockage(type, cle, valeur) {
  try {
    stockage(type).setItem(cle, valeur)
    return true
  } catch {
    return false
  }
}

/** `true` si la suppression a réussi, `false` si le stockage est indisponible. */
export function retirerStockage(type, cle) {
  try {
    stockage(type).removeItem(cle)
    return true
  } catch {
    return false
  }
}
