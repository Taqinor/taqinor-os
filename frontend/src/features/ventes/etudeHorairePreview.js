// CJ2b — pont entre le générateur de devis (résidentiel) et l'endpoint moteur
// horaire (CJ2a, `POST /ventes/etude-horaire/preview/`). Fonctions PURES
// (construireCorpsPreview / etiquetteSource / lignesAffichables — testables
// sous `node --test`, voir etudeHorairePreview.test.mjs) + UN hook React qui
// les enchaîne avec l'appel réseau debouncé/annulable.
//
// RÈGLES D'HONNÊTETÉ (fondateur, absolues — voir CLAUDE.md rule #4 / DC9) :
//   1. Quand `batterie_disponible` est faux, AUCUN chiffre « avec batterie »
//      n'est affiché — jamais un 0, jamais un tiret qui se ferait passer pour
//      une mesure. `lignesAffichables` les efface elle-même en défense de
//      profondeur, même si le serveur les avait déjà mis à `null`.
//   2. Tout chiffre dérivé d'une consommation ESTIMÉE (une seule ou deux
//      factures répétées sur 12 mois) porte l'étiquette « estimation » —
//      `etiquetteSource` le décide depuis `etude.source_consommation`.
//   3. `avertissements` du serveur sont montrés tels quels (jamais réécrits).
//   4. Une donnée manquante est OMISE avec une explication FR courte, jamais
//      comblée par une valeur inventée.
import { useEffect, useState } from 'react'
import { useDebouncedValue } from '../../lib/debounce'
import ventesApi from '../../api/ventesApi'
// CJ2b — les fonctions PURES vivent à côté, sans aucun import, pour rester
// exécutables sous `node --test` (voir l'en-tête de ce module-là).
export {
  construireCorpsPreview, etiquetteSource, lignesAffichables,
  verdictBatteriePourTaille,
  libelleTranche, falaiseAffichable, glitchAnnuel, balayageStockageAffichable,
  estimationConsoAffichable, LIBELLES_MOIS,
} from './etudeHorairePreviewPur'

/**
 * Hook React : appelle l'aperçu moteur horaire, débondi ~500 ms, annulable en
 * vol (même patron que LeadDevisPanel.jsx — race token `cancelled` +
 * AbortController). `corps` vient de `construireCorpsPreview` ; `null` =
 * rien à demander (aucun appel réseau, `donnees` reste `null`). Ne lève
 * JAMAIS et ne laisse jamais un résultat PÉRIMÉ à l'écran : `donnees` est
 * effacé au tout début de chaque nouvel appel, avant la réponse.
 */
export function useEtudeHorairePreview(corps) {
  const corpsKey = corps ? JSON.stringify(corps) : null
  const debouncedKey = useDebouncedValue(corpsKey, 500)
  const [donnees, setDonnees] = useState(null)
  const [chargement, setChargement] = useState(false)
  const [erreur, setErreur] = useState(null)
  // U3-MOTEUR (29/08/2026) — LA CLÉ DU CORPS QUI A PRODUIT `donnees`. Sans
  // elle, un appelant ne peut pas savoir SI la réponse qu'il lit décrit encore
  // ce qu'il a sous les yeux : une réponse DÉJÀ EN VOL au moment d'une
  // nouvelle saisie arrive après, parfaitement valide, mais pour l'ANCIENNE
  // facture. Le générateur s'en servait pour préremplir le nombre de panneaux
  // — un chiffre RÉEL posé pour un AUTRE profil (incident reproduit par
  // DevisGeneratorRecalculerDimensionnementGuard : facture 1200 → 3000
  // laissait 9 panneaux). L'appelant compare, et attend sa propre réponse.
  const [corpsServi, setCorpsServi] = useState(null)

  useEffect(() => {
    if (!debouncedKey) {
      // UNE seule dérogation par bloc : la règle ne signale que le PREMIER
      // setState, et une par ligne déclencherait `reportUnusedDisableDirectives`.
      // eslint-disable-next-line react-hooks/set-state-in-effect -- reflète l'absence d'ancrage
      setDonnees(null)
      setCorpsServi(null)
      setChargement(false)
      setErreur(null)
      return undefined
    }
    // Dégradation silencieuse : méthode absente (mock de test partiel, build
    // en cours de déploiement) — jamais un crash de l'écran générateur.
    if (typeof ventesApi.postEtudeHorairePreview !== 'function') return undefined
    let body
    try { body = JSON.parse(debouncedKey) } catch { body = null }
    if (!body) return undefined

    let cancelled = false
    const controller = new AbortController()
    // La dérogation du bloc ci-dessus couvre DÉJÀ tout cet effet (la règle ne
    // signale que son premier setState) : en poser une seconde ici la
    // rendrait « inutile » (`reportUnusedDisableDirectives`).
    // Jamais de résultat périmé pendant le recalcul : on efface avant l'appel.
    setChargement(true)
    setErreur(null)
    setDonnees(null)
    setCorpsServi(null)
    ventesApi.postEtudeHorairePreview(body, { signal: controller.signal })
      .then((res) => {
        if (cancelled) return
        setDonnees(res.data)
        setCorpsServi(debouncedKey)
      })
      .catch((err) => {
        if (cancelled) return
        if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return
        setErreur("Aperçu du moteur horaire indisponible pour le moment.")
      })
      .finally(() => { if (!cancelled) setChargement(false) })
    return () => { cancelled = true; controller.abort() }
  }, [debouncedKey])

  return { donnees, chargement, erreur, corpsServi }
}
