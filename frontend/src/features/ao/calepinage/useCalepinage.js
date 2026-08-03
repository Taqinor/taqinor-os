import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import aoApi from '../../../api/aoApi'
import { useDebouncedValue } from '../../../lib/debounce'

/* ============================================================================
   AOF94 — `useCalepinage` : le cycle « paramètre → calcul SERVEUR → résultat »
   et l'état PÉRIMÉ honnête.
   ----------------------------------------------------------------------------
   RECÂBLAGE DU 03/08/2026 — CE QUI A CHANGÉ, ET POURQUOI.
   Ce hook appelait `/ao/calepinages/<id>/`, une ressource que le serveur n'a
   JAMAIS servie et n'a jamais prévu de servir : il n'existe aucun modèle
   `Calepinage`. L'atelier ne pouvait donc rien afficher, même avec un
   identifiant valide. Le calepinage est modélisé côté serveur comme un CALCUL
   SANS ÉTAT sur une TOITURE, et ce qui se persiste est une `VarianteCalepinage`.

   Les routes RÉELLES (`apps/ao/calepinage_urls.py`), et elles seules :
     • `POST /ao/calepinage/calculer/`        → 200 (résultat) ou 202 (trop gros)
     • `POST /ao/calepinage/lancer/`          → 202 { id, statut, progress_pct… }
     • `GET  /ao/calepinage/resultat/<job>/`  → suivi + résultat du job

   Le hook est donc piloté par un **toitureId**, jamais par un `calepinageId`.
   Corps envoyé : `{ toiture, params }` — `params` est le dict de preset
   (`apps/ao/calepinage_io.parametres_vers_document`). Omis, le serveur applique
   l'instantané `ToitureAO.parametres_calepinage`. **`company` n'est jamais
   envoyé** (règle multi-tenant : le serveur la résout depuis l'utilisateur).

   SYNCHRONE OU TÂCHE DE FOND — LE SERVEUR DÉCIDE, PAS NOUS.
   `CalculerCalepinageView` chiffre le coût AVANT de calculer et répond **202**
   avec la consigne `/lancer/` quand le travail dépasse son budget synchrone.
   Le hook obéit à ce 202 : il relaie vers `lancer`, puis sonde
   `resultat/<job_id>/` et publie la progression que le job porte
   (`progress_pct`) — jamais une progression inventée ici.

   RÈGLE ARCHITECTURALE DE LA LANE : **aucun chiffre métier n'est calculé côté
   front.** Le moteur (`core/calepinage/`) est la seule autorité ; l'atelier
   n'est qu'un émetteur de paramètres et un afficheur de résultats.

   L'invariant unique de ce hook :
       **le résultat affiché est PÉRIMÉ dès qu'il n'a pas été produit par les
       paramètres courants** — `perime = (clé des paramètres courants) !==
       (clé des paramètres qui ont produit `resultat`)`.
   Ce n'est PAS « une requête est en vol » (qui laisse une fenêtre d'un rendu
   où l'ancien chiffre repasse pour courant) : c'est une comparaison d'états.

   Réponses périmées : chaque envoi incrémente un numéro de séquence ; toute
   réponse dont le numéro n'est plus le dernier est IGNORÉE (pas de setState,
   donc **pas de chiffre fantôme** quand une requête est doublée, qu'un sondage
   traîne ou que le composant est démonté).

   La garde de code qui interdit l'arithmétique de comptage dans `features/ao/`
   vit dans `useCalepinage.test.jsx`.
   ========================================================================== */

const DELAI_DEBOUNCE_MS = 350
//: Rythme de sondage du job de fond. Le serveur ne pousse rien (pas de
//: WebSocket sur cette route) : on relit `resultat/<job>/`, qui est bon marché.
const INTERVALLE_SONDAGE_MS = 1500
//: Plafond de sondages (≈ 5 min au rythme ci-dessus). Un job qui n'aboutit
//: jamais doit le DIRE, pas laisser un spinner tourner pour l'éternité.
const SONDAGES_MAX = 200

const STATUT_TERMINE = 'done'
const STATUT_ECHOUE = 'failed'

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

/* L'ERREUR SERVEUR S'AFFICHE TELLE QUELLE.
   Les quatre formes que cette API produit vraiment :
     • `{detail: "…"}`                      — 202 hors budget, 404, 501 local ;
     • `{entree: ["…"]}` / `{params: […]}`  — 400 NOMMÉ (`_erreur`, sérialiseur) ;
     • `{calepinage: ["…"], controle, repere}` — contrôle AOF51 en échec ;
     • `{statut: ["…"]}`                    — 409 sur une variante périmée.
   Ne lire que `detail` (l'ancien code) transformait les trois dernières en un
   message générique : le champ fautif — la seule information utile — était
   jeté. On les recompose ici « champ : motif », sans rien réécrire. */
function messageErreur(err, repli) {
  const charge = err?.response?.data
  if (typeof charge === 'string' && charge.trim()) return charge.trim()
  if (charge && typeof charge === 'object') {
    if (typeof charge.detail === 'string' && charge.detail) return charge.detail
    const morceaux = []
    for (const [champ, valeur] of Object.entries(charge)) {
      for (const brut of (Array.isArray(valeur) ? valeur : [valeur])) {
        if (typeof brut !== 'string' || !brut) continue
        morceaux.push(champ === 'detail' ? brut : `${champ} : ${brut}`)
      }
    }
    if (morceaux.length > 0) return morceaux.join(' — ')
  }
  return err?.message || repli
}

const attendre = (ms) => new Promise((resolve) => { setTimeout(resolve, ms) })

/**
 * Pilote UN calcul de calepinage sur une toiture.
 *
 * @param {number|string} toitureId   Toiture à calepiner (`ToitureAO.id`).
 * @param {object|null} parametres    Dict de preset envoyé en `params`
 *                                    (`null` → instantané serveur de la toiture).
 * @param {object} [options]
 * @param {number} [options.delai]      Anti-rebond avant recalcul (ms).
 * @param {number} [options.sondage]    Rythme de sondage du job de fond (ms).
 * @param {number} [options.sondagesMax] Plafond de sondages avant abandon.
 * @returns {{
 *   resultat: object|null, perime: boolean, enVol: boolean,
 *   chargementInitial: boolean, erreur: string|null,
 *   progression: {statut: string, pct: number}|null,
 *   recalculer: () => Promise<object|null>,
 * }}
 */
export default function useCalepinage(toitureId, parametres, options = {}) {
  const delai = options.delai ?? DELAI_DEBOUNCE_MS
  const sondage = options.sondage ?? INTERVALLE_SONDAGE_MS
  const sondagesMax = options.sondagesMax ?? SONDAGES_MAX

  const cle = useMemo(() => cleParametres(parametres), [parametres])
  const cleDebouncee = useDebouncedValue(cle, delai)

  // Refs : lus au moment de l'envoi, jamais comme dépendances d'effet.
  const parametresRef = useRef(parametres)
  const cleRef = useRef(cle)

  const seqRef = useRef(0)
  const monteRef = useRef(true)
  const idChargeRef = useRef(null)

  const [etat, setEtat] = useState({ resultat: null, cleAffichee: null })
  // Miroir en ref de la clé affichée : lue par l'effet de calcul SANS devenir
  // une dépendance (elle relancerait l'effet qu'elle doit arbitrer).
  const cleAfficheeRef = useRef(null)

  const [enVol, setEnVol] = useState(false)
  const [erreur, setErreur] = useState(null)
  const [progression, setProgression] = useState(null)
  const [chargementInitial, setChargementInitial] = useState(Boolean(toitureId))

  // Les refs ne sont JAMAIS écrites pendant le rendu (accès interdit —
  // react-hooks/refs) : cet effet, sans tableau de dépendances, les
  // resynchronise après CHAQUE rendu, avant l'effet de calcul ci-dessous
  // (les hooks s'exécutent dans leur ordre de déclaration).
  useEffect(() => {
    parametresRef.current = parametres
    cleRef.current = cle
    cleAfficheeRef.current = etat.cleAffichee
  })

  useEffect(() => {
    monteRef.current = true
    return () => { monteRef.current = false }
  }, [])

  // Un envoi n'est « encore le bon » que s'il est toujours le dernier ET que le
  // composant est monté : c'est la garantie « aucun chiffre fantôme ».
  const courant = useCallback((seq) => monteRef.current && seq === seqRef.current, [])

  /* Le chemin ASYNCHRONE, décidé par le serveur (202 sur `calculer`).
     On relaie le MÊME corps vers `lancer`, puis on sonde le job. La
     progression publiée est celle que le job porte — jamais une estimation. */
  const suivreJob = useCallback(async (corps, seq) => {
    const lance = await aoApi.calepinage.lancer(corps)
    const jobId = lance?.data?.id
    if (!jobId) {
      throw new Error('Le serveur a accepté le calcul sans rendre '
        + "d'identifiant de tâche : impossible d'en suivre l'issue.")
    }
    for (let tour = 0; tour < sondagesMax; tour += 1) {
      if (!courant(seq)) return null
      const suivi = await aoApi.calepinage.resultat(jobId)
      const job = suivi?.data || {}
      if (courant(seq)) {
        setProgression({ statut: job.statut, pct: job.progress_pct ?? 0 })
      }
      if (job.statut === STATUT_ECHOUE) {
        throw new Error(job.message_erreur
          || 'Le calcul de calepinage a échoué sans motif publié.')
      }
      if (job.statut === STATUT_TERMINE) return job.resultat ?? null
      await attendre(sondage)
    }
    throw new Error("Le calcul de calepinage n'a pas abouti dans le temps "
      + 'imparti — il tourne toujours côté serveur, rouvrez l’atelier plus tard.')
  }, [courant, sondage, sondagesMax])

  /* Envoi UNIQUE. `calculer` répond 200 (résultat) ou 202 (hors budget) ; le
     202 n'est PAS une erreur — c'est la consigne d'emprunter la tâche de fond. */
  const envoyer = useCallback(async (corps, cleCible) => {
    const seq = seqRef.current + 1
    seqRef.current = seq
    setEnVol(true)
    setErreur(null)
    setProgression(null)
    try {
      const reponse = await aoApi.calepinage.calculer(corps)
      let charge = reponse?.data ?? null
      if (reponse?.status === 202) {
        charge = await suivreJob(corps, seq)
      }
      if (!courant(seq)) return null
      setEtat({ resultat: charge, cleAffichee: cleCible })
      return charge
    } catch (err) {
      if (!courant(seq)) return null
      setErreur(messageErreur(err, 'Calcul impossible — le résultat affiché '
        + 'reste celui des paramètres précédents.'))
      return null
    } finally {
      if (courant(seq)) {
        setEnVol(false)
        setProgression(null)
        setChargementInitial(false)
      }
    }
  }, [courant, suivreJob])

  // Corps d'appel : `{toiture}` seul quand aucun paramètre n'est piloté par
  // l'écran — le serveur applique alors l'instantané de la toiture. JAMAIS de
  // `company` (le serveur la résout depuis l'utilisateur authentifié).
  const corpsDe = useCallback((params) => (
    params && typeof params === 'object' && Object.keys(params).length > 0
      ? { toiture: toitureId, params }
      : { toiture: toitureId }
  ), [toitureId])

  useEffect(() => {
    if (!toitureId) return
    // Toiture NEUVE : on repart de zéro. Garder l'ancien résultat en le
    // présentant comme celui de la nouvelle toiture serait le mensonge que
    // tout ce hook existe pour interdire.
    if (idChargeRef.current !== toitureId) {
      idChargeRef.current = toitureId
      cleAfficheeRef.current = null
      setEtat({ resultat: null, cleAffichee: null })
      setChargementInitial(true)
      envoyer(corpsDe(parametresRef.current), cleRef.current)
      return
    }
    // Rien à recalculer si l'affichage courant a DÉJÀ été produit par ces
    // paramètres (cas typique : les tiroirs se recalent sur un jeu déjà rendu).
    if (cleDebouncee === cleAfficheeRef.current) return
    envoyer(corpsDe(parametresRef.current), cleRef.current)
    // `cleDebouncee` est la dépendance réelle : c'est elle qui porte le rythme
    // de recalcul (anti-rebond), pas l'objet `parametres`.
  }, [toitureId, cleDebouncee, corpsDe, envoyer])

  // Calcul immédiat (bouton « Recalculer », court-circuite l'anti-rebond).
  const recalculer = useCallback(() => {
    if (!toitureId) return Promise.resolve(null)
    return envoyer(corpsDe(parametresRef.current), cleRef.current)
  }, [toitureId, corpsDe, envoyer])

  // L'invariant : périmé = « pas produit par les paramètres courants ».
  const perime = etat.cleAffichee !== cle

  return {
    resultat: etat.resultat,
    perime,
    enVol,
    chargementInitial,
    erreur,
    progression,
    recalculer,
  }
}
