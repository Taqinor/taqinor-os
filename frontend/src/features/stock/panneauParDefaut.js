import { useEffect, useState } from 'react'
import stockApi from '../../api/stockApi'

/* D-ACAL-169 (fondateur, 26/11/2026) — LE panneau par défaut de la société.
   Contrat partagé : backend/django_core/apps/stock/contract_samples/panneau_par_defaut.json.
   Aucun prix ici. */

/** Le droit que le serveur exige pour désigner / retirer (apps/stock/views/panneau_par_defaut.py). */
export const DROIT_PANNEAU_PAR_DEFAUT = 'catalogue_prix_modifier'

/** Un résumé servi (cinq clés, `source` texte), pas une réponse d'un autre état. */
export const estResumePanneau = (resume) => Boolean(resume) && typeof resume === 'object'
  && !Array.isArray(resume) && typeof resume.source === 'string'

/** D-ACAL-169 (rejeu) — un produit EST désigné mais n'est pas utilisable (archivé, sans prix, plus un panneau,
 *  watt du nom ≠ watt de la fiche) : toute source servie autre que `designe` et `aucun`. Le motif servi le nomme. */
export const panneauDefautInutilisable = (resume) => estResumePanneau(resume)
  && resume.source !== 'designe' && resume.source !== 'aucun'

/** Le libellé unique de cet état : ligne du catalogue, pastille de la ligne, pastille de la fiche. */
export const LIBELLE_DEFAUT_INUTILISABLE = 'Panneau par défaut non utilisable'

/** Le résumé servi par `GET stock/panneau-par-defaut/`, relu à la demande.
 *  Un échec de lecture garde la dernière réponse (une aide, jamais un verrou). */
export function usePanneauParDefaut() {
  const [resume, setResume] = useState(null)
  const [version, setVersion] = useState(0)
  useEffect(() => {
    let vivant = true
    Promise.resolve()
      .then(() => stockApi.getPanneauParDefaut())
      .then((r) => { if (vivant && estResumePanneau(r?.data)) setResume(r.data) })
      .catch(() => {})
    return () => { vivant = false }
  }, [version])
  return [resume, () => setVersion((v) => v + 1)]
}
