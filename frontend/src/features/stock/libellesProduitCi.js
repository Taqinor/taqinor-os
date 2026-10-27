// CCAT5 — libellés de la fiche produit pour l'usage C&I : fonctions PURES
// (aucun état, aucun appel réseau), sorties de ProduitForm.jsx pour ne pas
// grossir ce fichier. Les vocabulaires viennent du serveur ; ici seulement le
// texte affiché.
import { roleLabel } from '../ventes/solar.js'

// Rôles C&I dont le « prix fixe » est un prix PAR ONDULEUR (coffrets).
// source-choix: core.product_roles.ROLES_CI_BAREME_COFFRET
const ROLES_COFFRET_BAREME = ['coffret_dc', 'coffret_ac']

export const estCoffretBaremeCi = (roleCi) => ROLES_COFFRET_BAREME.includes(roleCi)

const AIDE_TARIF_RESIDENTIEL =
  'Si renseignés, la composition du devis cote cette ligne : fixe + par-panneau '
  + '× nb panneaux (HT), à la place du prix de vente. Laisser vide = prix de vente classique.'

/** Libellés du bloc « Tarification forfaitaire (composition) » : coffret C&I →
 * « par onduleur » (le prix fixe se multiplie par le nombre d'onduleurs),
 * sinon la formulation résidentielle (partie fixe + par panneau). */
export function libellesTarifForfaitaire(roleCi) {
  if (estCoffretBaremeCi(roleCi)) {
    return {
      fixe: 'Prix par onduleur (DH HT)',
      panneau: 'Prix par panneau (DH HT)',
      aide: "Coffret C&I : prix par onduleur × nombre d'onduleurs + prix par panneau "
        + '× nombre de panneaux, à la place du prix de vente.',
    }
  }
  return { fixe: 'Partie fixe (DH HT)', panneau: 'Par panneau (DH HT)', aide: AIDE_TARIF_RESIDENTIEL }
}

/** Libellé français d'un rôle de devis (les choix serveur sont `(rôle, rôle)`). */
export const libelleRoleDevis = (role) => roleLabel(role)

/** Indication « Rôle effectif : … » sous le sélecteur (`produit` null = création). */
export function aideRoleEffectif(produit) {
  if (!produit?.role_devis_effectif) return null
  const source = produit.role_devis_source ? ` (${produit.role_devis_source})` : ''
  return `Rôle effectif : ${libelleRoleDevis(produit.role_devis_effectif)}${source}`
}

/** Ligne d'aide des rôles qui servent aussi l'option « avec batterie » C&I. */
export function aideOptionBatterieCi(roleDevis) {
  return roleDevis === 'onduleur_hybride' || roleDevis === 'batterie'
    ? "Sert aussi l'option « avec batterie » des devis C&I (fiche : plage de tension batterie, capacité utile, tension nominale)."
    : null
}

/** Texte d'aide complet sous « Rôle de devis » (`undefined` = aucune aide). */
export const aideRoleDevis = (produit, roleDevis) =>
  [aideRoleEffectif(produit), aideOptionBatterieCi(roleDevis)].filter(Boolean).join(' · ') || undefined
