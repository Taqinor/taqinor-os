import { useCallback, useEffect, useState } from 'react'
import calepinageApi from '../../api/calepinageApi'

/* ============================================================================
   ACAL24 (C-ACAL-044) — LE DOCUMENT DU CALEPINAGE, LU UNE FOIS, JAMAIS INVENTÉ.
   ----------------------------------------------------------------------------
   Constat : Horizon, Terrain, Ombrière et Pente relisaient chacun le document
   (`const [layout, setLayout] = useState(null)` + GET au montage) avec
   `.catch(() => setLayout(null))` — un GET en échec laissait un document
   VIDE, puis « Enregistrer » postait ce document réduit à sa seule clé : tout
   le reste de la conception était écrasé (portes ATL-G1-04 / SIT-03).

   Ce hook est l'UNIQUE lecture :
     { etat: 'chargement' | 'ok' | 'erreur', document, empreinte, recharger }
   * `ok` seulement quand le serveur a répondu : `document` est alors l'objet
     lu (jamais `null`) et `empreinte` son jeton d'écriture (empreinte
     « document », contrat `calepinage_layout_section.json`) ;
   * un échec de lecture donne `erreur` — jamais un document vide : l'écran
     désactive ses boutons d'enregistrement et le dit ;
   * `appliquerSection(cle, valeur, empreinte)` reporte localement une section
     que l'écran vient d'écrire (document et jeton restent alignés).

   `ecrireSection` est l'UNIQUE écriture d'un onglet : `POST layout/section/`
   `{cle, valeur, base_empreinte}` (jamais le document entier), puis la clé est
   poussée dans l'atelier vivant (`documentVivant.appliquerSection`) pour que
   « Enregistrer le calepinage » ne la republie pas dans son état d'avant.
   ========================================================================== */

export const MESSAGE_ILLISIBLE = 'Conception illisible : rien n’est enregistré.'

/** `true` si `x` est un objet « document » (ni `null`, ni tableau). */
function estDocument(x) {
  return x !== null && typeof x === 'object' && !Array.isArray(x)
}

const CHARGEMENT = { etat: 'chargement', document: null, empreinte: null }
const ILLISIBLE = { etat: 'erreur', document: null, empreinte: null }

export default function useDocumentCalepinage(calepinageId, { actif = true } = {}) {
  const [essai, setEssai] = useState(0)
  const cle = `${calepinageId ?? ''}|${essai}`
  // La lecture porte la clé (calepinage + essai) qui l'a produite : une lecture
  // d'un autre essai vaut « chargement » — sans setState dans l'effet.
  const [lecture, setLecture] = useState({ cle: null, ...CHARGEMENT })

  useEffect(() => {
    if (!actif || !calepinageId) return undefined
    let annule = false
    // `then` : un échec SYNCHRONE de l'appel est aussi une lecture en échec.
    Promise.resolve()
      .then(() => calepinageApi.calepinages.layout(calepinageId))
      .then((res) => {
        if (annule) return
        const donnees = res?.data
        if (!estDocument(donnees)) {
          setLecture({ cle, ...ILLISIBLE })
          return
        }
        const brut = donnees.roof_layout
        setLecture({
          cle,
          etat: 'ok',
          document: estDocument(brut) ? brut : {},
          // ACAL360 — un document vide n'a pas d'empreinte : son jeton est ''.
          empreinte: donnees.empreinte_document ?? '',
        })
      })
      .catch(() => {
        if (!annule) setLecture({ cle, ...ILLISIBLE })
      })
    return () => { annule = true }
  }, [calepinageId, actif, cle])

  const recharger = useCallback(() => setEssai((n) => n + 1), [])

  const appliquerSection = useCallback((cleSection, valeur, empreinte) => {
    setLecture((courant) => (courant.etat !== 'ok' ? courant : {
      ...courant,
      document: { ...courant.document, [cleSection]: valeur },
      empreinte: empreinte ?? courant.empreinte,
    }))
  }, [])

  let courant = lecture.cle === cle ? lecture : CHARGEMENT
  if (actif && !calepinageId) courant = ILLISIBLE
  return {
    etat: courant.etat,
    document: courant.document,
    empreinte: courant.empreinte,
    // Change à CHAQUE lecture serveur (jamais à une application locale) : un
    // écran s'en sert pour n'hydrater sa saisie qu'une fois par lecture.
    generation: cle,
    recharger,
    appliquerSection,
  }
}

/**
 * Écrit UNE section du document par `layout/section/`.
 *
 * Le jeton est celui de l'atelier vivant quand il existe (il a pu avancer
 * depuis la lecture de l'onglet), sinon celui de la lecture. Rend
 * `{ ok: true, empreinte }` ou `{ ok: false, conflit, motif }` ; un 409 est un
 * `conflit` (le document a changé ailleurs : l'appelant relit).
 */
export async function ecrireSection({
  calepinageId, cle, valeur, empreinte, documentVivant = null,
}) {
  const base = documentVivant?.empreinte || empreinte
  // `''` = jeton d'un document encore vide (ACAL360) ; `null` = jamais lu.
  if (base == null) {
    return { ok: false, conflit: false, motif: MESSAGE_ILLISIBLE }
  }
  try {
    const res = await calepinageApi.calepinages.enregistrerSectionLayout(calepinageId, {
      cle, valeur, base_empreinte: base,
    })
    const apres = res?.data?.empreinte_document ?? null
    if (documentVivant?.appliquerSection) {
      documentVivant.appliquerSection(cle, valeur, apres)
    }
    return { ok: true, empreinte: apres }
  } catch (e) {
    const conflit = e?.response?.status === 409
    const detail = e?.response?.data?.detail
    return { ok: false, conflit, motif: typeof detail === 'string' ? detail : '' }
  }
}
