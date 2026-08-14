import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

/* ============================================================================
   PV31 — `useCalepinageImpose` : le BROUILLON local du mode « rangées
   imposées par l'utilisateur ».
   ----------------------------------------------------------------------------
   CE QUE CE HOOK FAIT, ET RIEN DE PLUS.
   Le mode `rangees_imposees_utilisateur` traverse déjà l'API SANS nouvel
   endpoint (PV30, backend) : `calculer`/`lancer` portent `params.mode_pose` +
   `params.rangees_imposees` (`[[y0, code_kit], …]`), et
   `calepinage_io.parametres_vers_document` les fait entrer dans le document
   du contrat. Ce hook ne fait qu'ORCHESTRER l'ÉDITION de cette liste côté
   écran : il tient un BROUILLON local (`[[y0, kit], …]`), le pousse à chaque
   geste via `majParametres` — donc à travers le MÊME anti-rebond/garde de
   séquence que `useCalepinage` — et laisse le SERVEUR recalculer et publier
   le plan RÉEL (`PlanLayer` ne dessine jamais une géométrie inventée ici).

   AUCUN CHIFFRE MÉTIER N'EST DÉRIVÉ ICI (AOF94) : ce hook ne lit que `y0` et
   `kit`, deux champs déjà nommés par `resultat.rangees`
   (`apps/ao/calepinage_io.resultat_vers_json` : la liste À PLAT des rangées
   de tous les plans — exactement l'union de `resultat.plans[].rangees` que le
   serveur construit lui-même), et ne les réarrange qu'en LISTE ([y0, kit]),
   jamais en compte ni en somme.

   SEEDING — « au premier geste », pas avant. Le brouillon vaut `null`
   (mode INACTIF) tant qu'aucun geste n'a eu lieu : l'écran affiche alors les
   rangées du dernier résultat SERVEUR (calculées normalement). Au premier
   geste (glisser/ajouter/supprimer), `assurerBrouillon` COPIE ces rangées
   dans le brouillon, puis applique le geste par-dessus — jamais un brouillon
   vide qui ferait disparaître les rangées existantes à l'écran.

   UNDO/REDO — deux piles de SNAPSHOTS du brouillon (pas des deltas) : simple,
   et suffisant pour la taille d'une liste de rangées.

   400 DU SERVEUR — ce hook NE REGARDE PAS l'erreur de `useCalepinage` : le
   brouillon reste ce que l'utilisateur a posé, qu'un geste ait réussi ou non
   côté serveur. C'est `CalepinageStudio` qui affiche le message d'erreur
   (déjà le cas, AOF94) pendant que le brouillon garde la main.
   ========================================================================== */

const MODE_POSE_IMPOSE = 'rangees_imposees_utilisateur'

// `resultat.rangees` : la liste À PLAT que le serveur construit lui-même
// (`[rangee for plan in plans for rangee in plan['rangees']]`,
// `calepinage_io.resultat_vers_json`) — LECTURE de deux champs nommés, aucune
// grandeur dérivée.
function lignesDuResultat(resultat) {
  const brut = Array.isArray(resultat?.rangees) ? resultat.rangees : []
  return brut
    .map((ligne) => [ligne.y0, ligne.kit])
    .sort((a, b) => a[0] - b[0])
}

/**
 * @param {object|null} resultat        Dernier résultat SERVEUR (`useCalepinage`).
 * @param {Function} majParametres      Le patch de paramètres de `CalepinageStudio`
 *                                      (fusion, puis recalcul serveur via `useCalepinage`).
 * @param {number|string} [toitureId]   Réinitialise le brouillon quand la toiture change.
 */
export default function useCalepinageImpose({ resultat, majParametres, toitureId }) {
  const [draft, setDraft] = useState(null)
  const [selection, setSelection] = useState(null)
  const [yPropose, setYPropose] = useState(null)
  const [modifie, setModifie] = useState(false)
  const [pileAnnuler, setPileAnnuler] = useState([])
  const [pileRefaire, setPileRefaire] = useState([])
  // Index en cours de glissé — lu de façon SYNCHRONE dans les gestionnaires de
  // pointeur (pointerdown/pointermove/pointerup peuvent se succéder plus vite
  // qu'un rendu) ; `null` = aucun glissé en cours.
  const glisseRef = useRef(null)

  // Toiture NEUVE : le brouillon appartenait à l'ancienne — on ne le traîne
  // pas d'une toiture à l'autre (même principe que `useCalepinage` : un
  // changement de toiture repart de zéro). Le garde par réf (comme
  // `idChargeRef` dans `useCalepinage`) évite un `setState` inconditionnel à
  // CHAQUE rendu de l'effet — il ne s'exécute QUE quand `toitureId` a
  // VRAIMENT changé depuis le montage.
  const toitureChargeeRef = useRef(toitureId)
  useEffect(() => {
    if (toitureChargeeRef.current === toitureId) return
    toitureChargeeRef.current = toitureId
    setDraft(null)
    setSelection(null)
    setYPropose(null)
    setModifie(false)
    setPileAnnuler([])
    setPileRefaire([])
    glisseRef.current = null
  }, [toitureId])

  const actif = draft !== null

  const envoyer = useCallback((lignes) => {
    majParametres({ mode_pose: MODE_POSE_IMPOSE, rangees_imposees: lignes })
  }, [majParametres])

  // Amorce le brouillon au PREMIER geste. Renvoie la valeur directement (pas
  // de lecture d'état juste après un `setState`, qui ne serait pas encore
  // visible) : chaque appelant peut l'utiliser tout de suite.
  const assurerBrouillon = useCallback(() => {
    if (draft !== null) return draft
    const seed = lignesDuResultat(resultat)
    setDraft(seed)
    return seed
  }, [draft, resultat])

  const appliquer = useCallback((suivant, precedent) => {
    setPileAnnuler((pile) => [...pile, precedent])
    setPileRefaire([])
    setModifie(true)
    setDraft(suivant)
    envoyer(suivant)
  }, [envoyer])

  // ── Glisser une rangée existante vers une nouvelle ordonnée ───────────────
  const commencerGlisser = useCallback((index) => {
    assurerBrouillon()
    glisseRef.current = index
    setSelection(index)
  }, [assurerBrouillon])

  const deplacerVers = useCallback((y) => {
    if (glisseRef.current === null || !Number.isFinite(y)) return
    setYPropose(y)
  }, [])

  const annulerGlisser = useCallback(() => {
    glisseRef.current = null
    setYPropose(null)
  }, [])

  const validerGlisser = useCallback(() => {
    const index = glisseRef.current
    glisseRef.current = null
    setYPropose(null)
    // Un clic SANS déplacement (pas de `deplacerVers` entre-temps) ne pose
    // rien : c'est une SÉLECTION, pas un glissé.
    if (index === null || !Number.isFinite(yPropose)) return
    const precedent = draft ?? []
    if (index >= precedent.length) return
    const suivant = precedent.map((ligne, i) => (i === index ? [yPropose, ligne[1]] : ligne))
    appliquer(suivant, precedent)
  }, [draft, yPropose, appliquer])

  // ── Ajouter / supprimer ────────────────────────────────────────────────
  const ajouterRangee = useCallback((y, kitCode) => {
    if (!Number.isFinite(y)) return
    const precedent = assurerBrouillon()
    // Aucun kit choisi explicitement : on reprend celui de la rangée la plus
    // proche du brouillon — jamais une valeur inventée sans référence.
    const kit = kitCode || precedent[precedent.length - 1]?.[1] || precedent[0]?.[1]
    if (!kit) return
    const suivant = [...precedent, [y, kit]].sort((a, b) => a[0] - b[0])
    appliquer(suivant, precedent)
  }, [assurerBrouillon, appliquer])

  const supprimerSelection = useCallback(() => {
    if (selection === null) return
    const precedent = assurerBrouillon()
    if (selection >= precedent.length) {
      setSelection(null)
      return
    }
    const suivant = precedent.filter((_ligne, i) => i !== selection)
    setSelection(null)
    appliquer(suivant, precedent)
  }, [selection, assurerBrouillon, appliquer])

  // ── Annuler / rétablir ─────────────────────────────────────────────────
  const annuler = useCallback(() => {
    if (pileAnnuler.length === 0) return
    const precedent = pileAnnuler[pileAnnuler.length - 1]
    setPileAnnuler((pile) => pile.slice(0, -1))
    setPileRefaire((pile) => [...pile, draft ?? []])
    setSelection(null)
    setDraft(precedent)
    envoyer(precedent)
  }, [pileAnnuler, draft, envoyer])

  const refaire = useCallback(() => {
    if (pileRefaire.length === 0) return
    const suivant = pileRefaire[pileRefaire.length - 1]
    setPileRefaire((pile) => pile.slice(0, -1))
    setPileAnnuler((pile) => [...pile, draft ?? []])
    setSelection(null)
    setDraft(suivant)
    envoyer(suivant)
  }, [pileRefaire, draft, envoyer])

  // ── Quitter : « Revenir au calcul optimal » ───────────────────────────
  const quitter = useCallback(() => {
    setDraft(null)
    setSelection(null)
    setYPropose(null)
    setModifie(false)
    setPileAnnuler([])
    setPileRefaire([])
    glisseRef.current = null
    // Les deux clés sont retirées (jamais `null`, qui resterait une VALEUR de
    // paramètre) : `CalepinageStudio.majParametres` supprime toute clé du
    // patch qui vaut `undefined`, si bien que le prochain appel n'envoie plus
    // ni `mode_pose` ni `rangees_imposees` — le serveur retombe alors sur le
    // preset enregistré de la toiture, l'optimum prouvé.
    majParametres({ mode_pose: undefined, rangees_imposees: undefined })
  }, [majParametres])

  // Rangées affichées : le brouillon une fois actif, sinon celles du dernier
  // résultat serveur — jamais un tableau vide qui ferait disparaître les
  // bandes d'accroche avant le premier geste.
  const lignesAffichees = useMemo(
    () => (draft !== null ? draft : lignesDuResultat(resultat)),
    [draft, resultat],
  )

  return {
    actif,
    draft,
    lignesAffichees,
    selection,
    yPropose,
    // « Divergent » = au moins un geste a été committé depuis le dernier
    // seed/sortie — sert au garde-fou de confirmation avant de perdre des
    // rangées imposées non enregistrées (PV32).
    isDraftDirty: actif && modifie,
    peutAnnuler: pileAnnuler.length > 0,
    peutRefaire: pileRefaire.length > 0,
    selectionner: setSelection,
    commencerGlisser,
    deplacerVers,
    annulerGlisser,
    validerGlisser,
    ajouterRangee,
    supprimerSelection,
    annuler,
    refaire,
    quitter,
  }
}
