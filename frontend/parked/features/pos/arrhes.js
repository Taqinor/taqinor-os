// NTRET5 — Arrhes / acompte sur commande comptoir (article en rupture de
// stock ou sur-mesure). Logique PURE de l'écran caisse : calcul du solde
// restant, validation du montant d'arrhes saisi, état « remise bloquée ».
// Les appels réseau (POST .../arrhes/, .../solde-arrhes/,
// .../remettre-marchandise/) restent dans CaisseScreen.jsx / posApi.js —
// aucune I/O ici, comme pos.js.

// Solde restant à régler avant remise de marchandise — 0 si la vente n'a
// jamais eu d'arrhes (`montant_arrhes` absent) : ce n'est alors pas une vente
// suivie par ce mécanisme, donc rien n'est dû AU TITRE DES ARRHES (à
// distinguer du prix total, non concerné ici).
export function soldeRestant(vente) {
  if (vente?.montant_arrhes == null) return 0
  const total = Number(vente?.total_ttc) || 0
  const arrhes = Number(vente?.montant_arrhes) || 0
  return Math.round((total - arrhes) * 100) / 100
}

export function estEnAttenteSolde(vente) {
  return vente?.statut === 'en_attente_solde'
}

// La marchandise ne peut être remise que si `marchandise_remise` est déjà
// vrai (solde réglé — `encaisser_solde_arrhes` côté serveur — ou override
// admin journalisé). Jamais déduit côté client d'un simple calcul de solde.
export function marchandiseBloquee(vente) {
  return estEnAttenteSolde(vente) && !vente?.marchandise_remise
}

// Un montant d'arrhes valide : positif, et STRICTEMENT inférieur au total
// (sinon c'est un encaissement complet classique, pas des arrhes).
export function arrhesValides(total, montantArrhes) {
  const t = Number(total) || 0
  const a = Number(montantArrhes) || 0
  return a > 0 && a < t
}

// Libellé du bandeau d'état affiché sur la vente en attente de solde.
export function libelleEtatArrhes(vente) {
  if (!estEnAttenteSolde(vente)) return null
  const solde = soldeRestant(vente)
  if (vente?.marchandise_remise) {
    return `Marchandise remise — solde de ${solde.toFixed(2)} DH encore dû.`
  }
  return `En attente de solde — ${solde.toFixed(2)} DH restant avant remise.`
}
