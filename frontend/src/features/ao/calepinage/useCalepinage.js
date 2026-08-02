import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import aoApi from '../../../api/aoApi'
import { useDebouncedValue } from '../../../lib/debounce'

/* ============================================================================
   AOF94 — `useCalepinage` : le cycle « paramètre → recalcul SERVEUR → résultat »
   et l'état PÉRIMÉ honnête.
   ----------------------------------------------------------------------------
   RÈGLE ARCHITECTURALE DE LA LANE : **aucun chiffre métier n'est calculé côté
   front.** Le moteur (`core/calepinage/`) est la seule autorité ; l'atelier
   n'est qu'un émetteur de paramètres et un afficheur de résultats.

   Le piège que ce hook ferme est CONNU et a déjà coûté une planche entière au
   dossier FRDISI, côté serveur (le piège `end_rive`) : deux chiffres tirés de
   deux états différents, présentés comme cohérents. Côté client, la forme
   qu'il prend est plus insidieuse — pendant qu'un recalcul vole, l'écran
   continue d'afficher l'ANCIEN compte comme s'il était courant, et un
   livrable produit à cet instant se contredit lui-même.

   D'où l'invariant unique de ce hook :
       **le résultat affiché est PÉRIMÉ dès qu'il n'a pas été produit par les
       paramètres courants** — `perime = (clé des paramètres courants) !==
       (clé des paramètres qui ont produit `resultat`)`.
   Ce n'est PAS « une requête est en vol » (qui laisse une fenêtre d'un rendu
   où l'ancien chiffre repasse pour courant, entre la fin du debounce et le
   départ de la requête) : c'est une comparaison d'états, sans fenêtre.

   Réponses périmées : chaque envoi incrémente un numéro de séquence ; toute
   réponse dont le numéro n'est plus le dernier est IGNORÉE (pas de setState,
   donc **pas de chiffre fantôme** quand une requête est doublée ou que le
   composant est démonté).

   La garde de code qui interdit l'arithmétique de comptage dans
   `features/ao/` vit dans `useCalepinage.test.jsx` — sans elle, la règle
   ci-dessus n'est qu'un vœu : le premier développeur qui veut « juste un
   aperçu réactif » ajoute un compteur local et l'écran se remet à mentir.
   ========================================================================== */

const DELAI_DEBOUNCE_MS = 350

// Tri RÉCURSIF des clés : l'ordre de saisie ne doit pas provoquer de recalcul.
// (Le raccourci `JSON.stringify(obj, clesTriees)` serait un piège : le tableau
// de remplacement s'applique à TOUS les niveaux et amputerait les objets
// imbriqués — deux jeux de paramètres différents auraient la même clé.)
function trierProfond(valeur) {
  if (Array.isArray(valeur)) return valeur.map(trierProfond)
  if (valeur && typeof valeur === 'object') {
    const trie = {}
    for (const nom of Object.keys(valeur).sort()) trie[nom] = trierProfond(valeur[nom])
    return trie
  }
  return valeur
}

// Clé stable d'un jeu de paramètres : comparateur d'ÉTAT, jamais une valeur.
function cleParametres(parametres) {
  if (!parametres || typeof parametres !== 'object') return String(parametres ?? '')
  try {
    return JSON.stringify(trierProfond(parametres))
  } catch {
    return String(parametres)
  }
}

const messageErreur = (err, repli) => err?.response?.data?.detail || repli

/**
 * @param {number|string} calepinageId  Calepinage serveur à piloter.
 * @param {object} parametres           Paramètres d'entrée courants (tiroirs).
 * @param {object} [options]
 * @param {number} [options.delai]      Anti-rebond avant recalcul (ms).
 * @returns {{
 *   plan: object|null, resultat: object|null, suggestions: Array,
 *   parametresServeur: object|null, perime: boolean, enVol: boolean,
 *   chargementInitial: boolean, erreur: string|null,
 *   recalculer: () => Promise<object|null>,
 *   appliquer: (patchEntree: object) => Promise<object|null>,
 * }}
 */
export default function useCalepinage(calepinageId, parametres, options = {}) {
  const delai = options.delai ?? DELAI_DEBOUNCE_MS

  const cle = useMemo(() => cleParametres(parametres), [parametres])
  const cleDebouncee = useDebouncedValue(cle, delai)

  // Refs : lus au moment de l'envoi, jamais comme dépendances d'effet.
  const parametresRef = useRef(parametres)
  const cleRef = useRef(cle)

  const seqRef = useRef(0)
  const monteRef = useRef(true)
  const idChargeRef = useRef(null)

  const [etat, setEtat] = useState({
    plan: null,
    resultat: null,
    suggestions: [],
    parametresServeur: null,
    cleAffichee: null,
  })
  // Miroir en ref de la clé affichée : lue par l'effet de recalcul SANS
  // devenir une dépendance (elle relancerait l'effet qu'elle doit arbitrer).
  const cleAfficheeRef = useRef(null)

  // Les refs ne sont JAMAIS écrites pendant le rendu (accès interdit —
  // react-hooks/refs) : cet effet, sans tableau de dépendances, les
  // resynchronise après CHAQUE rendu, avant l'effet de recalcul ci-dessous
  // (les hooks s'exécutent dans leur ordre de déclaration) afin qu'il lise
  // toujours la valeur la plus fraîche.
  useEffect(() => {
    parametresRef.current = parametres
    cleRef.current = cle
    cleAfficheeRef.current = etat.cleAffichee
  })

  const [enVol, setEnVol] = useState(false)
  const [erreur, setErreur] = useState(null)
  const [chargementInitial, setChargementInitial] = useState(Boolean(calepinageId))

  useEffect(() => {
    monteRef.current = true
    return () => { monteRef.current = false }
  }, [])

  // Envoi UNIQUE : toute réponse dont le numéro de séquence a été dépassé est
  // jetée — c'est la garantie « aucun chiffre fantôme ».
  const envoyer = useCallback(async (appel, cleCible) => {
    const seq = seqRef.current + 1
    seqRef.current = seq
    setEnVol(true)
    setErreur(null)
    try {
      const res = await appel()
      if (!monteRef.current || seq !== seqRef.current) return null
      const charge = res?.data || {}
      setEtat({
        plan: charge.plan ?? null,
        resultat: charge.resultat ?? null,
        suggestions: Array.isArray(charge.suggestions) ? charge.suggestions : [],
        parametresServeur: charge.parametres ?? null,
        // Le serveur fait FOI sur les paramètres qui ont produit ce résultat :
        // quand il les renvoie, ce sont EUX qui datent l'affichage (une
        // recommandation appliquée peut changer plus que ce qu'on a envoyé).
        cleAffichee: charge.parametres ? cleParametres(charge.parametres) : cleCible,
      })
      return charge
    } catch (err) {
      if (!monteRef.current || seq !== seqRef.current) return null
      setErreur(messageErreur(err, 'Recalcul impossible — le résultat affiché reste celui des paramètres précédents.'))
      return null
    } finally {
      if (monteRef.current && seq === seqRef.current) {
        setEnVol(false)
        setChargementInitial(false)
      }
    }
  }, [])

  useEffect(() => {
    if (!calepinageId) return
    const cible = cleRef.current
    if (idChargeRef.current !== calepinageId) {
      idChargeRef.current = calepinageId
      setChargementInitial(true)
      envoyer(() => aoApi.calepinages.get(calepinageId), cible)
      return
    }
    // Rien à recalculer si l'affichage courant a DÉJÀ été produit par ces
    // paramètres (cas typique : les tiroirs se recalent sur les paramètres
    // renvoyés par le serveur après une recommandation appliquée).
    if (cleDebouncee === cleAfficheeRef.current) return
    envoyer(() => aoApi.calepinages.calculer(calepinageId, parametresRef.current), cible)
    // `cleDebouncee` est la dépendance réelle : c'est elle qui porte le
    // rythme de recalcul (anti-rebond), pas l'objet `parametres`.
  }, [calepinageId, cleDebouncee, envoyer])

  // Recalcul immédiat (bouton « Recalculer », court-circuite l'anti-rebond).
  const recalculer = useCallback(() => {
    if (!calepinageId) return Promise.resolve(null)
    return envoyer(() => aoApi.calepinages.calculer(calepinageId, parametresRef.current), cleRef.current)
  }, [calepinageId, envoyer])

  // AOF100 — application d'une recommandation : le `patch_entree` est REJOUÉ
  // par le moteur (jamais un gain estimé côté front). La réponse porte les
  // paramètres retenus par le serveur, que l'appelant recopie dans ses tiroirs.
  const appliquer = useCallback((patchEntree) => {
    if (!calepinageId) return Promise.resolve(null)
    const corps = { ...parametresRef.current, patch_entree: patchEntree }
    return envoyer(() => aoApi.calepinages.calculer(calepinageId, corps), cleParametres(corps))
  }, [calepinageId, envoyer])

  // L'invariant : périmé = « pas produit par les paramètres courants ».
  const perime = etat.cleAffichee !== cle

  return {
    plan: etat.plan,
    resultat: etat.resultat,
    suggestions: etat.suggestions,
    parametresServeur: etat.parametresServeur,
    perime,
    enVol,
    chargementInitial,
    erreur,
    recalculer,
    appliquer,
  }
}
