// CCAT5 — libellés de la fiche produit pour l'usage C&I : fonctions PURES
// (aucun état, aucun appel réseau), sorties de ProduitForm.jsx pour ne pas
// grossir ce fichier. Les vocabulaires viennent du serveur ; ici seulement le
// texte affiché.
import { useEffect } from 'react'
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

/* CCAT12 — motif d'exclusion servi par `etat_ci.motif_exclusion` → id DOM du
   champ de ProduitForm à remplir. Quand le motif en nomme plusieurs, le PREMIER
   cité dans le texte l'emporte. */
const CHAMPS_MOTIF_CI = [
  [/prix (?:de vente )?(?:non saisi|à renseigner)/, 'pf-vente'],
  [/fiche onduleur absente|puissance AC/, 'pf-ft-ackw'],
  [/phase|monophasé \/ triphasé/, 'pf-ft-phases'],
  [/plage de tension batterie/, 'pf-ft-bat-vmin'],
  [/capacité utile/, 'pf-ft-kwhutil'],
  [/tension nominale/, 'pf-ft-vnom'],
  [/Pmax/, 'pf-ft-pmax'],
  [/entrées MPPT/, 'pf-ft-nmppt'],
  [/MPPT — tension mini/, 'pf-ft-mpptmin'],
  [/MPPT — tension maxi/, 'pf-ft-mpptmax'],
  [/tension DC maximale/, 'pf-ft-vmax'],
  [/courant maxi par MPPT/, 'pf-ft-imax'],
  [/rendement européen/, 'pf-ft-rend'],
  [/garantie constructeur/, 'pf-gar-txt'],
]

/** Id du champ de ProduitForm qui corrige `motif` (`null` = motif inconnu). */
export function champCibleMotif(motif) {
  const texte = String(motif ?? '')
  let meilleur = null
  for (const [motifRe, id] of CHAMPS_MOTIF_CI) {
    const pos = texte.search(motifRe)
    if (pos >= 0 && (meilleur === null || pos < meilleur.pos)) meilleur = { pos, id }
  }
  return meilleur ? meilleur.id : null
}

/** CCAT12 — à l'ouverture, défile jusqu'au champ `champId` (ouvre le <details>
 * qui le contient) et le focalise ; attend qu'il existe (fiche chargée en
 * asynchrone), ~5 s au plus. `null` = rien à faire. */
export function useChampInitial(champId) {
  useEffect(() => {
    if (!champId) return undefined
    let essais = 0
    const viser = () => {
      const el = document.getElementById(champId)
      if (!el) return false
      el.closest('details')?.setAttribute('open', '')
      el.scrollIntoView?.({ block: 'center' })
      el.focus?.()
      return true
    }
    if (viser()) return undefined
    const t = setInterval(() => { if (viser() || ++essais >= 50) clearInterval(t) }, 100)
    return () => clearInterval(t)
  }, [champId])
}
