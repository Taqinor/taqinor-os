// D-ACAL-169 (fondateur, 26/11/2026 : « always use 715w everywhere, and have somewhere
// in the stock to show the default used pannels ») — CE QUE LE GÉNÉRATEUR FAIT du panneau
// par défaut de la société. Contrat : backend/django_core/apps/stock/contract_samples/
// panneau_par_defaut.json (lecture) et apps/ventes/contract_samples/devis_composition.json
// (clé `panneau_par_defaut` de la réponse de composition). Aucun prix ici.
//
// Règle : le défaut ne sert qu'au DÉPART d'un devis NEUF et jamais à un devis rouvert ;
// ce que le vendeur tape gagne toujours ; sans défaut désigné, l'écran est celui d'hier.
import { useEffect, useState } from 'react'
import stockApi from '../../../api/stockApi'

const DESIGNE = 'designe'
const AUCUN = 'aucun'
const REFUSE = 'refuse'

/** Le résumé du stock quand il désigne un panneau UTILISABLE (`source: 'designe'`, puissance lue), sinon null. */
export const panneauDefautUtilisable = (resume) => (
  resume && resume.source === DESIGNE && Number(resume.pmax_wc) > 0 ? resume : null
)

/**
 * La composition serveur doit-elle choisir SON wattage ? Oui tant que l'écran est resté sur
 * le défaut de la société (rien de tapé, rien relu d'un devis ou du moteur) : le serveur
 * applique alors sa propre règle — wattage ET produit de la même source. Un wattage fixé
 * (tapé, d'un devis, du moteur) est toujours envoyé tel quel.
 */
export const laisserLeServeurChoisirLeWatt = (resume, panelWFixe) => (
  Boolean(panneauDefautUtilisable(resume)) && !panelWFixe
)

/**
 * La phrase discrète sous le champ « Puissance Panneau » : le nom du défaut quand l'écran est
 * sur SA puissance ; le motif du stock (phrase française affichable telle quelle) quand un
 * panneau est désigné mais inutilisable. Rien quand aucun défaut n'est désigné.
 * @returns {{ton: 'info'|'alerte', texte: string}|null}
 */
export function indicationPanneauDefaut(resume, panelW) {
  const utilisable = panneauDefautUtilisable(resume)
  if (utilisable) {
    return Number(panelW) === Number(utilisable.pmax_wc) && utilisable.nom
      ? { ton: 'info', texte: `Panneau par défaut : ${utilisable.nom}` }
      : null
  }
  if (resume && resume.source !== AUCUN && resume.source !== DESIGNE && resume.motif) {
    return { ton: 'alerte', texte: String(resume.motif) }
  }
  return null
}

/** Le motif quand la COMPOSITION n'a pas pu retenir le panneau désigné (`source: 'refuse'`), sinon null. */
export const motifRefusComposition = (data) => {
  const p = data?.panneau_par_defaut
  return p && p.source === REFUSE && p.motif ? String(p.motif) : null
}

/**
 * Lit UNE fois le panneau par défaut à l'ouverture d'un devis NEUF et pose sa puissance de
 * départ (`PANNEAU_DEFAUT_LU` — le reducer refuse dès qu'un wattage est déjà fixé). Un devis
 * rouvert (`editId`) ne lit rien. Un échec de lecture n'affiche rien et ne bloque rien.
 * @returns {object|null} le résumé servi, pour l'indication et la composition.
 */
export function usePanneauParDefautDepart({ editId, dispatchSizing }) {
  const [resume, setResume] = useState(null)
  useEffect(() => {
    if (editId) return undefined
    let vivant = true
    Promise.resolve()
      .then(() => stockApi.getPanneauParDefaut())
      .then((r) => {
        const d = r?.data
        if (!vivant || !d || typeof d.source !== 'string') return
        setResume(d)
        const utilisable = panneauDefautUtilisable(d)
        if (utilisable) dispatchSizing({ type: 'PANNEAU_DEFAUT_LU', pmaxWc: utilisable.pmax_wc })
      })
      .catch(() => {})
    return () => { vivant = false }
  }, [editId, dispatchSizing])
  return resume
}
