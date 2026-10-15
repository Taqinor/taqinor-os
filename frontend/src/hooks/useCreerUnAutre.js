import { useState } from 'react'

/* « Créer un autre » (VX92) : préférence persistée par utilisateur/poste
   (localStorage), défaut OFF. Un salon = 10 leads/clients/produits créés
   d'affilée ; sans ce toggle chaque création coûte un cycle fermer/rouvrir.
   Un seul endroit — le stockage indisponible (navigation privée, quota) ne
   casse jamais le formulaire. */

export function lireCreerUnAutre(cle) {
  try {
    return window.localStorage.getItem(cle) === '1'
  } catch {
    return false
  }
}

export function ecrireCreerUnAutre(cle, valeur, avertir = false) {
  try {
    window.localStorage.setItem(cle, valeur ? '1' : '0')
  } catch {
    // localStorage indisponible : confort non mémorisé (no-op, ou avertissement).
    if (avertir) {
      console.warn('Préférence « créer un autre » non mémorisée : stockage indisponible.')
    }
  }
}

/** [creerUnAutre, changer] — `actif` : la préférence ne s'applique qu'à la création. */
export function useCreerUnAutre(cle, actif, { avertir = false } = {}) {
  const [valeur, setValeur] = useState(() => actif && lireCreerUnAutre(cle))
  const changer = (v) => { setValeur(v); ecrireCreerUnAutre(cle, v, avertir) }
  return [valeur, changer]
}
