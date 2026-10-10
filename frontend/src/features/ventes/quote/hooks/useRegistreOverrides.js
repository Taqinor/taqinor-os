// SPL46 — LE REGISTRE DE SURCHARGES DU GÉNÉRATEUR (QJR215/QJR572/QJR574),
// état et gestes déplacés tels quels de DevisGenerator.jsx : `overridesReg`,
// `estAdmin`, saisie du panneau admin, `messageErreurOverrides`,
// `alignerSurRegistre`, `chargerOverrides`, la lecture à l'ouverture,
// `poserOverride`, `regenererOverride`. Corps verbatim ; `ctx` porte, nom par
// nom, ce que le corps lit du composant.
import { useEffect, useState } from 'react'
import { useIsAdmin } from '../../../../hooks/useHasPermission'
import { CHEMINS_AUTORISES, valeursImposees } from '../overrides'
import ventesApi from '../../../../api/ventesApi'
import { FENETRE_REFERENCE_MS } from '../ecranDefauts.js'

export function useRegistreOverrides(ctx) {
  const {
    dispatchSizing, editDevis, captureReferenceJusqua, setRecommendedChoice,
  } = ctx

  const [overridesReg, setOverridesReg] = useState(null)
  // QJR574 (D-QJR5-8) — le panneau BRUT « Surcharges (registre) » (chemin +
  // valeur JSON libre) est réservé aux administrateurs : Scénario, Option
  // recommandée et nombre de panneaux portent déjà la surcharge (QJR572).
  // L'endpoint reste IsResponsableOrAdmin ; le registre est lu pour tous.
  const estAdmin = useIsAdmin()
  const [overridesBusy, setOverridesBusy] = useState(false)
  // Un refus 400 est affiché TEL QUEL (le message FR du serveur, jamais avalé
  // ni remplacé par une phrase générique) — les formes varient selon le refus
  // (`{detail}`, `{chemin: "..."}`, `{chemin: ["..."]}`) : on en extrait la
  // PREMIÈRE valeur textuelle, sans reformuler son contenu.
  const [overridesErreur, setOverridesErreur] = useState(null)
  const [ovChemin, setOvChemin] = useState(CHEMINS_AUTORISES[0])
  const [ovValeur, setOvValeur] = useState('')

  const messageErreurOverrides = (err) => {
    const data = err?.response?.data
    if (data && typeof data === 'object') {
      const brut = Object.values(data)[0]
      const texte = Array.isArray(brut) ? brut[0] : brut
      if (typeof texte === 'string') return texte
    }
    // QJR309 — un refus CLIENT-SIDE de la liste blanche (`ventesApi.
    // poserOverrides`, AVANT tout réseau) est un TypeError NU, sans
    // `.response` : il ne doit JAMAIS être maquillé en refus du serveur — son
    // propre message nomme déjà le chemin fautif (voir `ventesApi.js`),
    // rendu tel quel plutôt que remplacé par la phrase générique ci-dessous.
    if (!err?.response && err instanceof TypeError && typeof err.message === 'string') {
      return err.message
    }
    return 'La surcharge a été refusée par le serveur.'
  }

  // QJR572 — LE REGISTRE GAGNE AU PDF (scenario.py, utils/options.py,
  // builder.py) : à l'arrivée du registre, Scénario, Option recommandée et
  // nombre de panneaux affichent la valeur qu'il IMPOSE, jamais une valeur
  // d'`etude_params` que le document ignore. Transition `REOUVERTURE` (le
  // choix est déjà fait), sans toucher aux autres champs.
  const alignerSurRegistre = (data) => {
    const imp = valeursImposees(data)
    const devis = {}
    if (typeof imp.scenario === 'string') devis.scenario = imp.scenario
    const n = Number.parseInt(imp['taille.nb_panneaux'], 10)
    if (n > 0) devis.panneaux = n
    if (Object.keys(devis).length) dispatchSizing({ type: 'REOUVERTURE', devis })
    if (imp.recommended_option === 'Sans batterie' || imp.recommended_option === 'Avec batterie') {
      setRecommendedChoice(imp.recommended_option)
    }
  }

  const chargerOverrides = (id) => {
    if (!id) return
    ventesApi.lireOverrides(id)
      .then(({ data }) => {
        // QJR581 — hydratation serveur tardive : la référence « rien n'a
        // changé » est re-capturée sur l'état qu'elle pose.
        captureReferenceJusqua.current = Date.now() + FENETRE_REFERENCE_MS
        setOverridesReg(data); alignerSurRegistre(data)
      })
      .catch(() => {})
  }

  // Lecture du registre À L'OUVERTURE d'un devis existant.
  // QJR572 — relu à CHAQUE ouverture d'un devis, jamais à chaque rendu.
  useEffect(() => {
    if (editDevis?.id) chargerOverrides(editDevis.id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editDevis?.id])

  const poserOverride = async () => {
    if (!editDevis?.id || !ovChemin) return
    setOverridesBusy(true)
    setOverridesErreur(null)
    let valeur
    try { valeur = JSON.parse(ovValeur) } catch { valeur = ovValeur }
    try {
      const { data } = await ventesApi.poserOverrides(editDevis.id, {
        [ovChemin]: { valeur },
      })
      setOverridesReg(data)
      setOvValeur('')
    } catch (err) {
      setOverridesErreur(messageErreurOverrides(err))
    } finally {
      setOverridesBusy(false)
    }
  }

  const regenererOverride = async (chemin) => {
    if (!editDevis?.id) return
    setOverridesBusy(true)
    setOverridesErreur(null)
    try {
      const { data } = await ventesApi.regenererOverride(editDevis.id, chemin)
      setOverridesReg(data)
    } catch (err) {
      setOverridesErreur(messageErreurOverrides(err))
    } finally {
      setOverridesBusy(false)
    }
  }

  return {
    overridesReg, setOverridesReg, estAdmin, overridesBusy, overridesErreur, setOverridesErreur,
    ovChemin, setOvChemin, ovValeur, setOvValeur, messageErreurOverrides, poserOverride,
    regenererOverride,
  }
}
