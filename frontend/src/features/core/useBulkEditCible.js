import { useCallback, useEffect, useState } from 'react'
import coreApi from '../../api/coreApi'

/* ============================================================================
   PACT118 — accès GÉNÉRIQUE à l'édition en masse du socle (FG389).
   ----------------------------------------------------------------------------
   CONSTAT À DOUBLE FACE, à ne pas confondre :
     (a) le moteur générique existe et est testé (`core/bulk_edit.py`) ;
     (c) aucune app ne l'avait JAMAIS branché — `register_bulk_target`
         n'était appelé que depuis les tests du socle, donc le catalogue
         `GET core/bulk-edit/targets/` était VIDE en production.
   Pendant ce temps, quatre écrans avaient résolu le besoin autrement, chacun
   avec SON endpoint de mise à jour en masse.

   Ce hook est la moitié frontend du branchement : il lit le catalogue réel,
   dit si une cible donnée est disponible et, le cas échéant, applique un
   changement. Il est réservé aux listes qui n'ont PAS déjà leur propre
   endpoint — les quatre existants ne sont pas retouchés.

   Contrat : rien n'est inventé côté client. La liste blanche des champs vient
   du serveur (`champs`), l'écriture est bornée au queryset scopé société du
   fournisseur de la cible, et une cible absente du catalogue rend simplement
   `disponible === false` (l'écran n'affiche alors aucune action — jamais un
   bouton qui échouerait en 404).
   ========================================================================== */

/** Normalise le catalogue renvoyé par le socle (tableau à plat). */
export function normaliserCibles(data) {
  if (!Array.isArray(data)) return []
  return data.filter((c) => c && typeof c === 'object' && c.name)
}

/** Retrouve une cible par son nom logique (ex. `cpq.offre-groupee`). */
export function trouverCible(cibles, nom) {
  return normaliserCibles(cibles).find((c) => c.name === nom) || null
}

/**
 * useBulkEditCible — expose l'édition en masse d'UNE cible enregistrée.
 *
 * @param {string} nom  nom logique de la cible (ex. `cpq.offre-groupee`)
 * @returns {{
 *   disponible: boolean, libelle: string, champs: string[],
 *   chargement: boolean, erreur: string,
 *   appliquer: (ids: Array, changes: object) => Promise<number>,
 *   enCours: boolean,
 * }}
 */
export function useBulkEditCible(nom) {
  const [cible, setCible] = useState(null)
  const [chargement, setChargement] = useState(true)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  useEffect(() => {
    let vivant = true
    coreApi.bulkEdit.targets()
      .then((res) => {
        if (!vivant) return
        setCible(trouverCible(res?.data, nom))
        setErreur('')
      })
      .catch(() => {
        if (!vivant) return
        // Catalogue indisponible : la cible est simplement absente. L'écran
        // n'affiche aucune action de masse plutôt qu'une action cassée.
        setCible(null)
        setErreur('Catalogue d’édition en masse indisponible.')
      })
      .finally(() => { if (vivant) setChargement(false) })
    return () => { vivant = false }
  }, [nom])

  const appliquer = useCallback(async (ids, changes) => {
    const liste = Array.isArray(ids) ? ids : []
    if (liste.length === 0 || !changes || Object.keys(changes).length === 0) {
      return 0
    }
    setEnCours(true)
    try {
      const res = await coreApi.bulkEdit.appliquer(nom, liste, changes)
      const n = res?.data?.modifies
      return Number.isFinite(n) ? n : 0
    } finally {
      setEnCours(false)
    }
  }, [nom])

  return {
    disponible: cible !== null,
    libelle: cible?.label || '',
    champs: Array.isArray(cible?.fields) ? cible.fields : [],
    chargement,
    erreur,
    appliquer,
    enCours,
  }
}

export default useBulkEditCible
