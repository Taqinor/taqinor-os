import { useCallback, useEffect, useState } from 'react'
import { formatNumber } from '../../../../../../lib/format'
import { totalPose } from '../../../../surfacePose'

/* ============================================================================
   ÉTAPE « PANNEAUX » — LA LECTURE DU CONSTRUCTEUR (22/11).
   ----------------------------------------------------------------------------
   Le script du toit (`roof-tool-pro11.ts`) écrit ses chiffres dans le DOM que
   React lui a rendu (ids `rp9-*`) et n'expose aucun état. L'écran de l'étape
   RE-PRÉSENTE ces contrôles : il les LIT ici (jamais un nombre recalculé, jamais
   une valeur inventée : une valeur absente reste `null`) et leur RENVOIE les
   gestes (clic sur le vrai bouton, valeur + événement sur le vrai champ). Les
   éléments `rp9-*` ne sont jamais démontés ni rendus conditionnellement : ils
   restent la source de vérité, l'écran n'est qu'une autre présentation.
   ========================================================================== */

/** Plafond du besoin accepté par le constructeur (`clampNeeded`, optimizer.ts) : « le plus de panneaux ». */
export const BESOIN_MAX = 400

const $ = (id) => document.getElementById(id)
const texteDe = (id) => ($(id)?.textContent ?? '').replace(/\s+/g, ' ').trim()
const absent = (t) => !t || t === '—'
/** Le premier entier d'un texte (« 12 × 580 W » → 12), `null` s'il n'y en a pas. */
const entierDe = (texte) => {
  const m = /\d[\d\s]*/.exec(texte ?? '')
  return m ? Number(m[0].replace(/\D/g, '')) : null
}
const valeurOuNull = (t) => (absent(t) ? null : t)

/** Les chiffres de la carte « Recommandation » du constructeur (`rp9-reco-*`). */
function lireFigures() {
  const panneaux = texteDe('rp9-reco-panels')
  const apres = /×\s*(\d[\d\s]*)\s*W/.exec(panneaux)
  const prod = valeurOuNull(texteDe('rp9-reco-prod'))
  const couverture = valeurOuNull(texteDe('rp9-reco-cover'))
  return {
    panneaux: absent(panneaux) ? null : entierDe(panneaux),
    watt: apres ? Number(apres[1].replace(/\D/g, '')) : null,
    kwc: valeurOuNull(texteDe('rp9-reco-kwc')),
    production: prod ? prod.replace(/\s*kWh\s*\/\s*an/, ' kWh / an') : null,
    productionKwh: prod && /kWh/i.test(prod) ? entierDe(prod) : null, // M5 — la phrase de raison porte des kWc, pas des kWh
    couverture,
    couverturePct: couverture ? entierDe(couverture) : null,
    // T4-X9-006 — la phrase des deux tailles, dite par le constructeur sous ses cartes (`tailleConception.ts`), ou `null`.
    tailles: valeurOuNull(texteDe('rp9-reco-tailles')),
  }
}

/** La pose que la carte du constructeur AFFICHE (`{ panneaux, kwc }`), ou `null` tant qu'elle n'affirme rien (« — »). */
function lirePoseVivante() {
  const { panneaux, kwc } = lireFigures()
  return panneaux == null ? null : { panneaux, kwc }
}

/** La pose affichée, SUIVIE : relue à chaque changement du texte de la carte (changement de module, retrait, remplissage).
    `actif` faux ⇒ `null` (l'en-tête garde alors la pose servie). Sert l'en-tête du projet tant que la scène est modifiée. */
/* T4-U4-016 / T4-U4-024 — avec le constructeur, la pose se lit sur SON DOCUMENT (`totalPose` : pans tracés + champs au
   sol + ombrières — la carte « Recommandation » ne compte que les pans), relu toutes les 1,5 s et à chaque changement de
   la carte : la barre suit le document, pas seulement après un rechargement. Sans constructeur : la carte, comme avant. */
const PERIODE_DOCUMENT_MS = 1500
function lirePoseDocument(builderApi) {
  let layout = null
  try { layout = builderApi.serializeLayout() ?? null } catch { layout = null }
  const total = totalPose(layout)
  if (!total) return null
  return { panneaux: total.panneaux, kwc: total.kwc == null ? null : `${formatNumber(total.kwc, { decimals: 2, locale: 'fr' })} kWc` }
}

export function usePoseVivante(actif, builderApi = null) {
  const parDocument = typeof builderApi?.serializeLayout === 'function'
  const lire = useCallback(() => (parDocument ? lirePoseDocument(builderApi) : lirePoseVivante()), [parDocument, builderApi])
  const [pose, setPose] = useState(() => (actif ? lire() : null))
  useEffect(() => {
    if (!actif) return undefined
    const relire = () => setPose((avant) => {
      const suivante = lire()
      return JSON.stringify(suivante) === JSON.stringify(avant) ? avant : suivante
    })
    relire()
    const observateur = new MutationObserver(relire)
    for (const id of ['rp9-reco-panels', 'rp9-reco-kwc']) {
      const element = $(id)
      if (element) observateur.observe(element, { childList: true, characterData: true, subtree: true })
    }
    const minuteur = parDocument ? window.setInterval(relire, PERIODE_DOCUMENT_MS) : null
    return () => {
      observateur.disconnect()
      if (minuteur != null) window.clearInterval(minuteur)
    }
  }, [actif, lire, parDocument])
  return actif ? pose : null
}

function lireBesoin() {
  const champ = $('rp9-need-input')
  if (!champ) return null
  const note = texteDe('rp9-need-note')
  // « … seuls 55 tiennent … » (besoin > ce qui tient) ou « on pose ce qui tient (55) » (aucune cible) — optimizer.ts ;
  // T4-X8-012 — « … le plus de panneaux possible : 9 posés. » (affichageErp.ts::noteLePlus).
  const tiennent = /(\d[\d\s]*)\s+tiennent/.exec(note) ?? /ce qui tient \((\d[\d\s]*)\)/.exec(note)
    ?? /possible : (\d[\d\s]*) posés/.exec(note)
  // T4-X8-012 — sur « le plus de panneaux », le champ AFFICHE le besoin de la facture et le script le marque
  // `data-le-plus="1"` (affichageErp.ts::peindreChampBesoin) : le choix reste le plafond, jamais ce nombre affiché.
  const lePlus = champ.dataset?.lePlus === '1'
  return {
    valeur: lePlus ? BESOIN_MAX : entierDe(champ.value),
    editable: !champ.disabled,
    note,
    tiennent: tiennent ? Number(tiennent[1].replace(/\D/g, '')) : null,
    // ACAL1331 — la taille posée d'elle-même sur un calepinage vierge, dite par le script (tailleAuto.ts::noteTailleAuto).
    auto: note.startsWith('Posé d’après '),
  }
}

const presse = (el) => el?.getAttribute('aria-pressed') === 'true'

function lireModule() {
  const liste = $('rp9-pan-module-select')
  const erreur = $('rp9-pan-module-erreur')
  return {
    present: !!liste,
    options: liste ? Array.from(liste.options).map((o) => ({
      valeur: o.value, libelle: (o.textContent ?? '').trim(), grise: o.disabled,
    })) : [],
    valeur: liste?.value ?? '',
    mention: texteDe('rp9-pan-module-mention'),
    erreur: erreur && !erreur.hidden ? (erreur.textContent ?? '').trim() : '',
  }
}

/** L'avis d'ombrage du constructeur (`shadingUi.ts`) : seulement quand il propose de retirer des modules. */
function lireOmbre() {
  const zone = $('rp9-solar-access')
  // ACAL1532 — l'obstacle (`data-ombre-de`) et, SANS seuil réglé, la perte annuelle (`data-ombre-perte`) sont PUBLIÉS par
  // le script (jamais parsés dans le texte) ; sans seuil il n'y a pas de proposition, mais l'ombre se dit quand même.
  const de = zone?.dataset?.ombreDe || null
  const perte = Number(zone?.dataset?.ombrePerte) >= 1 ? Number(zone.dataset.ombrePerte) : null
  const bouton = $('rp9-solar-access-apply')
  const texte = texteDe('rp9-solar-access')
  const retirer = bouton ? /retirer les (\d+) module/.exec(texte) : null
  if (retirer) {
    return { n: Number(retirer[1]), origine: texte.includes('seuil de ce dossier') ? 'dossier' : 'societe', de, perte: null }
  }
  return perte ? { n: 0, origine: null, de, perte } : null
}

function lireSoleil() {
  const heure = $('rp9-sun-hour')
  const saisons = Array.from(document.querySelectorAll('[data-sun-season]'))
  const lecture = $('rp9-sun-play-day')
  const carte = $('rp9-heatmap-toggle')
  const borne = (attr, defaut) => {
    const n = Number(heure?.getAttribute(attr))
    return Number.isFinite(n) && heure?.getAttribute(attr) ? n : defaut
  }
  return {
    heure: heure ? entierDe(heure.value) : null,
    min: borne('min', 6),
    max: borne('max', 18),
    date: $('rp9-sun-date')?.value ?? '',
    saison: saisons.find(presse)?.dataset.sunSeason ?? null,
    lecture: lecture ? { active: presse(lecture) } : null,
    carte: carte ? { active: presse(carte) } : null,
  }
}

/** Le sens de pose posé : `portrait` | `landscape` | `auto`, ou `null` (pose mixte). */
function lireOrientation() {
  const puces = Array.from(document.querySelectorAll('[data-orient]'))
  return puces.find(presse)?.dataset.orient ?? null
}

/** La pose actuelle est-elle « tout ce qui tient » ? Le plafond du besoin, ou la pose égale à ce que
    le script dit tenir, ou aucun besoin à dériver (le script pose alors tout ce qui tient). LU, jamais déduit
    du nombre posé seul. */
export function poseMax(besoin, figures) {
  if (!besoin || !(figures?.panneaux > 0)) return false
  if (besoin.valeur >= BESOIN_MAX) return true
  if (besoin.tiennent != null && figures.panneaux === besoin.tiennent) return true
  return !besoin.valeur && !besoin.editable
}

/** Une lecture complète du constructeur, avec la mémoire de « Le plus de panneaux » (ses chiffres ne se
    lisent que le temps où il est posé). */
export function lireConstructeur(avant = null) {
  const besoin = lireBesoin()
  const figures = lireFigures()
  const max = poseMax(besoin, figures)
  const memoire = { max: max ? figures : (avant?.memoire?.max ?? null) }
  return {
    besoin, figures, max, memoire,
    module: lireModule(),
    orientation: lireOrientation(),
    ombre: lireOmbre(),
    soleil: lireSoleil(),
  }
}

/** La lecture + de quoi la rafraîchir tout de suite (après un geste) ; sinon ~2,5 fois par seconde :
    le script écrit des valeurs (`.value`) que le DOM ne signale pas. */
export function useConstructeur(delai = 400) {
  const [etat, setEtat] = useState(() => lireConstructeur())
  const rafraichir = useCallback(() => {
    setEtat((avant) => {
      const suivant = lireConstructeur(avant)
      return JSON.stringify(suivant) === JSON.stringify(avant) ? avant : suivant
    })
  }, [])
  useEffect(() => {
    const id = window.setInterval(rafraichir, delai)
    return () => window.clearInterval(id)
  }, [delai, rafraichir])
  return [etat, rafraichir]
}

const cliquer = (selecteur) => {
  const el = document.querySelector(selecteur)
  if (!el || el.disabled) return false
  el.click()
  return true
}

const poserEtDire = (el, valeur, evenement) => {
  el.value = String(valeur)
  el.dispatchEvent(new Event(evenement, { bubbles: true }))
}

/** Les gestes de l'écran, renvoyés aux VRAIS contrôles du constructeur. */
export const gestes = {
  orientation: (sens) => cliquer(`[data-orient="${sens}"]`),
  saison: (saison) => cliquer(`[data-sun-season="${saison}"]`),
  lecture: () => cliquer('#rp9-sun-play-day'),
  carteSoleil: () => cliquer('#rp9-heatmap-toggle'),
  retirerOmbre: () => cliquer('#rp9-solar-access-apply'),
  besoin: (n) => {
    const champ = $('rp9-need-input')
    if (!champ || champ.disabled) return false
    poserEtDire(champ, n, 'input')
    return true
  },
  /** T4-X7-012 (décision du 25/11 : « Add a button ») — un panneau de moins sur le pan : le besoin ramené à la pose
      AFFICHÉE − 1, par le même `setNeeded` du script que « Un de moins » de l'Expert (`rp9-need-minus`) ; c'est le
      script qui choisit quel panneau part. Depuis la pose (et non depuis le champ) : sur « le plus de panneaux » le
      champ affiche le besoin de la facture (T4-X8-012), « − » y laissait la pose inchangée quand ce besoin dépasse ce
      qui tient. Le script ne descend jamais sous 1 (`clampNeeded`). */
  retirerUnPanneau: (pose) => (Number.isInteger(pose) && pose >= 2 ? gestes.besoin(pose - 1) : false),
  heure: (h) => {
    const champ = $('rp9-sun-hour')
    if (!champ) return false
    poserEtDire(champ, h, 'input')
    return true
  },
  module: (valeur) => {
    const liste = $('rp9-pan-module-select')
    if (!liste) return false
    poserEtDire(liste, valeur, 'change')
    return true
  },
}
