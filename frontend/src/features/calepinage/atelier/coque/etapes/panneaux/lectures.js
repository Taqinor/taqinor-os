// Étapes Toit et Panneaux, vue « Montrer au client » — LES LECTURES SERVIES PARTAGÉES (GET seulement).
// Une lecture en vol est PARTAGÉE (jamais deux `design-context` simultanés pour le même calepinage : sous charge, les
// doublons poussaient la lecture de l'atelier au-delà des 20 s du client et la 3D ne démarrait plus — H2, 22/11) ;
// une réponse reste servie quelques secondes (passer de Toit à Panneaux relit la même) ; un échec n'est jamais gardé.
// Trois états honnêtes : « chargement » (rien n'est affirmé), « echec » (dit, avec « réessayer »), « ok ».
import { useCallback, useEffect, useState } from 'react'
import calepinageApi from '../../../../../../api/calepinageApi'
import { cibleFactures } from './sources'

const DUREE_MS = 15000

const LECTEURS = {
  contexte: (id) => calepinageApi.calepinages.designContext(id),
  resultat: (id) => calepinageApi.calepinages.resultat(id),
  document: (id) => calepinageApi.calepinages.layout(id),
  // H3 — la taille tirée des factures, lue À PART du design-context (son dimensionnement coûtait ~1,9 s à chaque
  // ouverture de l'atelier) : `GET cible-factures/` → `{ cible_factures }`.
  cible: (id) => calepinageApi.calepinages.cibleFactures(id),
}

const memoire = new Map()

/** La lecture servie `nature` du calepinage `id` (promesse des données), partagée tant qu'elle est en vol ou fraîche. */
export function lireServi(nature, id) {
  const cle = `${nature}|${id}`
  const vue = memoire.get(cle)
  if (vue && (vue.enVol || Date.now() - vue.le < DUREE_MS)) return vue.promesse
  const entree = { enVol: true, le: 0, promesse: null }
  entree.promesse = Promise.resolve()
    .then(() => LECTEURS[nature](id))
    .then((res) => {
      entree.enVol = false
      entree.le = Date.now()
      return res?.data ?? null
    }, (err) => {
      if (memoire.get(cle) === entree) memoire.delete(cle)
      throw err
    })
  memoire.set(cle, entree)
  return entree.promesse
}

/** Oublie toutes les lectures gardées (tests ; « réessayer » oublie la sienne). */
export function oublierLecturesServies(nature = null, id = null) {
  if (nature == null) memoire.clear()
  else memoire.delete(`${nature}|${id}`)
}

/**
 * La lecture `nature` en trois états : `{ etat: 'chargement' | 'echec' | 'ok', donnees, reessayer }`.
 * `servi` (la même donnée déjà chargée par l'atelier, `ecranProps.contexte`) prime : aucune lecture n'est alors faite.
 */
export function useLectureServie(nature, id, { servi = null, actif = true } = {}) {
  const [essai, setEssai] = useState(0)
  const [lecture, setLecture] = useState({ cle: null, etat: 'chargement', donnees: null })
  const cle = `${nature}|${id ?? ''}|${essai}`
  const lire = actif && servi == null && id != null && id !== ''
  useEffect(() => {
    if (!lire) return undefined
    let vivant = true
    lireServi(nature, id).then(
      (donnees) => { if (vivant) setLecture({ cle, etat: 'ok', donnees }) },
      () => { if (vivant) setLecture({ cle, etat: 'echec', donnees: null }) },
    )
    return () => { vivant = false }
  }, [lire, nature, id, cle])
  const reessayer = useCallback(() => {
    oublierLecturesServies(nature, id)
    setEssai((n) => n + 1)
  }, [nature, id])
  if (servi != null) return { etat: 'ok', donnees: servi, reessayer }
  if (lecture.cle !== cle) return { etat: 'chargement', donnees: null, reessayer }
  return { etat: lecture.etat, donnees: lecture.donnees, reessayer }
}

/**
 * LA taille tirée des factures, UN accesseur pour l'étape Toit (puce « Besoin d'après la facture ») et l'étape
 * Panneaux (« Couvrir la facture ») : `{ etat, cible, motif, leadId, reessayer }`. `cible` n'a de sens qu'en
 * `etat === 'ok'` (`null` = le lead n'a pas de facture exploitable) ; en chargement ou en échec, rien n'est affirmé.
 */
export function useCibleFactures(calepinageId, servi = null) {
  // Le motif et le lead viennent du design-context (déjà chargé par l'atelier : `servi`) ; la taille, de sa
  // lecture à part (H3). L'état est celui des DEUX : chargement tant que l'une manque, échec dès que l'une échoue.
  const contexte = useLectureServie('contexte', calepinageId, { servi })
  const taille = useLectureServie('cible', calepinageId)
  const etat = [contexte.etat, taille.etat].includes('echec') ? 'echec'
    : (contexte.etat === 'ok' && taille.etat === 'ok' ? 'ok' : 'chargement')
  const { reessayer: relireContexte, etat: etatContexte } = contexte
  const { reessayer: relireTaille, etat: etatTaille } = taille
  const reessayer = useCallback(() => {
    if (etatContexte === 'echec') relireContexte()
    if (etatTaille !== 'ok') relireTaille()
  }, [etatContexte, etatTaille, relireContexte, relireTaille])
  return {
    etat,
    cible: etat === 'ok' ? cibleFactures(taille.donnees) : null,
    motif: contexte.etat === 'ok' ? (contexte.donnees?.consommation_lead?.motif || '') : '',
    leadId: contexte.donnees?.calepinage?.lead ?? null,
    reessayer,
  }
}
