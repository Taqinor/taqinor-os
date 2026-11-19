import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'

/* ============================================================================
   TCH45 — Feuille du bas à crans (spec-7 §10, spec-8 §2 : rayon 20, `--popover` +
   `--shadow-lg`, 260 ms entrée / 180 ms sortie). Deux crans, 50 % et 85 % de la hauteur,
   que la poignée (44 px) fait basculer : « Agrandir la feuille » / « Réduire la feuille ».
   CLAVIER OUVERT : les crans ne valent plus (86 px utiles à 50 %) — la feuille épouse son
   contenu et se pose SUR le clavier (`sur-clavier`, hauteur du clavier lue sur
   `visualViewport`, jetée dans `--tch-clavier-h`). Au bureau (≥ 768 px) la même feuille est
   un dialogue centré (`dialogue-bureau`) ; `variante="popover"` + `ancre` (R2-009 : la saisie) est rendue DANS
   l'ancre, en place dans la page, NON modale et sans voile (`popover-bureau`) ; `variante="panneau"`
   (R2-050 : fiche, bilan, Alléger) est, dès 1024 px, un panneau fixe à droite NON modal (`panneau-bureau`).
   Dialogue modal : focus piégé, Échap ferme (écouté sur `document`, la plus haute seulement — R2-043), le focus
   revient à l'élément qui l'a ouverte.
   Maquettes : docs/taches/maquettes/composants-5.html, composants-6.html.
   ========================================================================== */

const SEUIL_CLAVIER_PX = 120
const FOCALISABLES = 'a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
const CHAMPS = 'input:not([disabled]):not([type="hidden"]), textarea:not([disabled]), select:not([disabled])'

/** R2-043 — vrai si l'élément est rendu (la poignée est `display:none` au bureau : `focus()` y échouait, le focus
 *  restait DERRIÈRE la feuille). `checkVisibility` quand le navigateur l'a, sinon la chaîne des styles calculés. */
function estVisible(el) {
  if (typeof el.checkVisibility === 'function') return el.checkVisibility()
  for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
    const style = window.getComputedStyle(n)
    if (style.display === 'none' || style.visibility === 'hidden') return false
  }
  return true
}

const premierVisible = (racine, selecteur) => [...(racine?.querySelectorAll(selecteur) ?? [])].find(estVisible) ?? null

/** F2 acceptation (P144.3) — une feuille ouverte au clavier peut désigner son action par défaut (`data-focus-initial`) :
 *  Entrée la valide aussitôt. Sinon (R2-043) le premier élément VISIBLE : la poignée sur l'iPhone (aucun clavier qui
 *  surgit), au bureau — poignée cachée — le premier champ, sinon « Fermer ».
 *  Passe visuelle n° 26 — posé d'office sur la poignée, le focus ne dessine pas d'anneau (« poignée discrète »,
 *  ecran-bilan.html) : il chevauchait l'écran du dessous. Tab le rend visible ; une action désignée garde le sien. */
function focusInitial(racine) {
  const voulu = premierVisible(racine, '[data-focus-initial]')
  const poignee = premierVisible(racine, '.poignee')
  // R3-064 — ouverte à la souris ou au doigt, le focus posé d'office ne dessine aucun anneau (le × entouré de bleu du
  // bilan et d'Alléger) ; ouverte au clavier, il le dessine (Entrée valide l'action désignée, Tab montre où l'on est)
  const poser = (el) => { if (derniereModalite === 'clavier') el.focus(); else el.focus({ focusVisible: false }) }
  const champ = premierVisible(racine, CHAMPS) ?? premierVisible(racine, FOCALISABLES)
  if (voulu) poser(voulu)
  else if (poignee) poignee.focus({ focusVisible: false })
  else if (champ) poser(champ)
}

/** R3-060 — fermer ne perd jamais une frappe : le champ où l'on tape est QUITTÉ avant la fermeture, son `onBlur` (qui
 *  enregistre : heure, échéance, titre, notes, « De qui ou de quoi ? »…) part pendant que la feuille est encore montée.
 *  Échap, la croix, le voile et le retour arrière passent tous par là ; sur l'iPhone, toucher la croix ne retire PAS le
 *  focus du champ (un bouton touché ne le prend pas) : sans ce détour, la valeur partait avec la feuille, sans un mot. */
function quitterLeChamp(racine) {
  const ici = typeof document !== 'undefined' ? document.activeElement : null
  if (ici && ici !== document.body && racine?.contains(ici) && typeof ici.blur === 'function') ici.blur()
}

/** Ce qui garde son focus même hors d'une feuille modale : menus et listes (portails Radix), autres dialogues, toast. */
const HORS_PIEGE = '[role="dialog"], [role="alertdialog"], [role="menu"], [role="listbox"], [data-radix-popper-content-wrapper], .toast-place'

/** R2-049 — le dernier geste était-il au clavier ? (lu à l'ouverture d'une feuille) Au doigt ou à la souris, le focus
 *  rendu à la fermeture ne dessine pas d'anneau épais sur le bouton touché (« ⋯ » après Alléger). */
let derniereModalite = 'pointeur'
/** R3-066 — les derniers éléments qui ont reçu le focus (le plus récent en dernier). Un champ `autoFocus` de la feuille
 *  le prend AU MONTAGE, avant que la feuille ne lise son ouvreur — et, ouverte depuis un menu ⋯ (Radix), le menu le lui
 *  reprend aussitôt : la feuille retrouve ici le champ qui l'a demandé, et l'élément focalisé juste avant lui. */
const focusRecents = []
const retenirFocus = (el) => {
  if (!el) return
  focusRecents.push(el)
  if (focusRecents.length > 6) focusRecents.shift()
}
if (typeof document !== 'undefined') {
  document.addEventListener('keydown', () => { derniereModalite = 'clavier' }, true)
  document.addEventListener('pointerdown', () => { derniereModalite = 'pointeur' }, true)
  document.addEventListener('focusin', (e) => { retenirFocus(e.target) }, true)
  // le focus DEMANDÉ et refusé : Chrome annonce la sortie vers le champ (`relatedTarget`), le FocusScope du menu la
  // refuse dans ce même `focusout`, et le champ ne reçoit jamais `focusin`
  document.addEventListener('focusout', (e) => { retenirFocus(e.relatedTarget) }, true)
}

/** Le champ de la feuille qui a demandé le focus à son montage (`autoFocus`), et l'élément focalisé avant lui. */
function champAutoFocus(racine) {
  if (!racine) return { champ: null, avant: null }
  for (let i = focusRecents.length - 1; i >= 0; i -= 1) {
    const el = focusRecents[i]
    if (el !== racine && el?.isConnected && racine.contains(el)) {
      const avant = focusRecents.slice(0, i).reverse().find((x) => x?.isConnected && !racine.contains(x)) ?? null
      return { champ: el, avant }
    }
  }
  return { champ: null, avant: null }
}

/** R2-050 — seuil du panneau à droite (bureau large) : en dessous, la variante `panneau` reste un dialogue/feuille. */
const REQUETE_PANNEAU = '(min-width: 1024px)'

function useLarge(requete) {
  const lire = () => typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia(requete).matches
  const [large, setLarge] = useState(lire)
  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return undefined
    const mq = window.matchMedia(requete)
    const maj = () => setLarge(mq.matches)
    mq.addEventListener?.('change', maj)
    return () => mq.removeEventListener?.('change', maj)
  }, [requete])
  return large
}

/** R2-043 — les feuilles ouvertes, de la plus ancienne à la plus haute : Échap (écouté sur `document`) ne ferme que
 *  la plus haute, même quand le focus est resté derrière elle. */
const pileOuvertes = []

/** Hauteur (px) du clavier virtuel, 0 s'il est fermé ou si `visualViewport` n'existe pas. */
function lireClavier() {
  const vv = typeof window !== 'undefined' ? window.visualViewport : null
  if (!vv) return 0
  const bas = window.innerHeight - vv.height - (vv.offsetTop || 0)
  return bas > SEUIL_CLAVIER_PX ? Math.round(bas) : 0
}

function useClavier(actif) {
  const [clavier, setClavier] = useState(0)
  useEffect(() => {
    const vv = typeof window !== 'undefined' ? window.visualViewport : null
    if (!actif || !vv) return undefined
    const maj = () => setClavier(lireClavier())
    maj()
    vv.addEventListener('resize', maj)
    vv.addEventListener('scroll', maj)
    return () => {
      vv.removeEventListener('resize', maj)
      vv.removeEventListener('scroll', maj)
    }
  }, [actif])
  return actif ? clavier : 0
}

/* ── Vague 2 — la SORTIE des feuilles (spec-8 §2 : 180 ms ; l'entrée, R2-048, est en CSS `@starting-style`) ──────────
   Fermée (ou démontée avec son écran : la fiche), la feuille quittait l'écran d'un coup. React l'a déjà retirée : on
   laisse à sa place, le temps de l'animation, une COPIE inerte (`sortante` : sans rôle, `aria-hidden`, `inert`, sans
   id ni data-*) — le focus est rendu tout de suite, aucun lecteur d'écran ni test ne voit plus de dialogue. La copie
   est posée dans `.tch` sous une copie vide des ancêtres (`.fiche`…) : les règles `.tch .fiche .feuille…` valent
   encore. Seulement si la personne n'a pas demandé moins d'animations ; jamais pour la saisie en place (dans le flux,
   elle ferait sauter la liste). */
const DUREE_SORTIE_MAX_MS = 400

const animerSortie = () => typeof window !== 'undefined' && typeof window.matchMedia === 'function'
  && window.matchMedia('(prefers-reduced-motion: no-preference)').matches

function nettoyerCopie(copie) {
  ;[copie, ...copie.querySelectorAll('*')].forEach((n) => {
    ;[...n.attributes].forEach(({ name }) => {
      if (name === 'id' || name === 'name' || name === 'for' || name === 'role' || name.startsWith('data-')
        || (name.startsWith('aria-') && name !== 'aria-hidden')) n.removeAttribute(name)
    })
  })
  copie.setAttribute('aria-hidden', 'true')
  copie.inert = true
}

function laisserSortir(noeud, voileNoeud, racineTch, chaine) {
  let hote = racineTch
  let tete = null
  chaine.forEach((ancetre) => {
    const vide = ancetre.cloneNode(false)
    nettoyerCopie(vide)
    if (!tete) tete = vide
    hote.appendChild(vide)
    hote = vide
  })
  const copier = (el) => {
    const copie = el.cloneNode(true)
    // la valeur TAPÉE (propriété) n'est pas un attribut : sans elle la copie montrerait le champ d'origine
    const champs = el.querySelectorAll('input, textarea, select')
    copie.querySelectorAll('input, textarea, select').forEach((c, i) => {
      c.value = champs[i]?.value ?? c.value
      if ('checked' in c) c.checked = Boolean(champs[i]?.checked)
    })
    nettoyerCopie(copie)
    copie.classList.add('sortante')
    return copie
  }
  const copies = [voileNoeud, noeud].filter(Boolean).map(copier)
  copies.forEach((c) => hote.appendChild(c))
  let fini = false
  const retirer = () => {
    if (fini) return
    fini = true
    if (tete) tete.remove()
    else copies.forEach((c) => c.remove())
  }
  copies[copies.length - 1]?.addEventListener('animationend', retirer)
  setTimeout(retirer, DUREE_SORTIE_MAX_MS) // filet : une animation qui ne part pas (onglet caché) ne laisse rien
}

function useSortieAnimee(ouverte, enPlace, feuille, voile) {
  const ouverteRendue = useRef(Boolean(ouverte))
  useLayoutEffect(() => { ouverteRendue.current = Boolean(ouverte) })
  const demontee = useRef(false)
  useLayoutEffect(() => {
    demontee.current = false
    return () => { demontee.current = true }
  }, [])
  useLayoutEffect(() => {
    const noeud = feuille.current
    const voileNoeud = voile.current
    const racineTch = noeud?.closest?.('.tch') ?? null
    if (!ouverte || enPlace || !noeud || !racineTch) return undefined
    const chaine = []
    for (let n = noeud.parentElement; n && n !== racineTch; n = n.parentElement) chaine.unshift(n)
    return () => {
      if (!animerSortie()) return
      // lu une fois le rendu posé : fermée, ou démontée avec son écran — jamais quand elle change seulement d'allure
      // (en place ↔ dialogue), ni au double montage du mode strict (la feuille reste alors dans le document)
      queueMicrotask(() => {
        const fermee = demontee.current || !ouverteRendue.current
        if (fermee && !noeud.isConnected && racineTch.isConnected) laisserSortir(noeud, voileNoeud, racineTch, chaine)
      })
    }
  }, [ouverte, enPlace, feuille, voile])
}

/* ── R4-20 — TIRER une feuille du bas vers le bas pour la fermer (le geste de Rappels, Calendrier, Things) ───────────
   La poignée le promet. Le doigt part de la poignée ou de l'en-tête — ou du contenu quand il est défilé tout en haut
   (sinon le geste lui appartient : il défile). La feuille SUIT le doigt (`transform`, sans transition : c'est une
   manipulation directe, permise même quand on a demandé moins d'animations), le voile s'éclaircit d'autant ; lâchée
   au-delà de 30 % de sa hauteur ou d'un jet de plus de 0,5 px/ms, elle se ferme par le même chemin que la croix
   (`fermerSansPerte` : le champ en cours est quitté d'abord, sa frappe gardée — R3-060) ; sinon elle revient. Vers le
   haut, depuis la poignée ou l'en-tête : le cran 85 %. Jamais là où il n'y a pas de poignée VISIBLE (saisie en place,
   panneau et dialogue du bureau), jamais depuis un champ de texte (on y sélectionne), jamais en glissé horizontal.
   Écouteurs natifs `touch*` (`passive: false`) : un `touchmove` annulé dès le premier pixel vers le bas empêche le
   navigateur de prendre le geste pour un défilement (il enverrait `pointercancel` et garderait le doigt). */
const SEUIL_TIRE_FRACTION = 0.3
const SEUIL_TIRE_VITESSE = 0.5 // px/ms
const SEUIL_TIRE_JET_MIN_PX = 24
const SEUIL_DECISION_PX = 6
const SEUIL_CRAN_HAUT_PX = 40
const CHAMPS_TEXTE = 'input, textarea, select, [contenteditable=""], [contenteditable="true"]'

/** Vrai si un élément entre `cible` et la feuille défile et n'est pas tout en haut (le geste vers le bas est le sien). */
function contenuDefile(cible, racine) {
  for (let n = cible; n && n !== racine; n = n.parentElement) {
    if (n.scrollTop > 0 && n.scrollHeight > n.clientHeight) return true
  }
  return false
}

function useTirerPourFermer(feuille, voile, actif, fermerSansPerte, setCran) {
  useEffect(() => {
    const racine = feuille.current
    if (!actif || !racine) return undefined
    let geste = null
    const reduit = () => typeof window.matchMedia === 'function' && !window.matchMedia('(prefers-reduced-motion: no-preference)').matches
    const poser = (dy) => {
      racine.style.transform = dy > 0 ? `translateY(${dy}px)` : ''
      if (voile.current) voile.current.style.opacity = dy > 0 ? String(Math.max(0, 1 - dy / geste.hauteur)) : ''
    }
    const relacher = () => {
      racine.classList.remove('tiree')
      if (reduit()) { poser(0); return }
      // le retour glisse (260 ms), puis la feuille rend la main à ses transitions d'origine
      racine.style.transition = 'transform var(--motion-slow) var(--tch-ease-entree)'
      if (voile.current) voile.current.style.transition = 'opacity var(--motion-slow) var(--ease-standard)'
      const fin = (e) => {
        if (e && e.target !== racine) return
        racine.removeEventListener('transitionend', fin)
        racine.style.transition = ''
        if (voile.current) voile.current.style.transition = ''
      }
      racine.addEventListener('transitionend', fin)
      poser(0)
      if (!racine.style.transform) fin() // rien à faire glisser (jsdom, 0 px) : la main est rendue tout de suite
    }
    const surDebut = (e) => {
      geste = null
      if (e.touches.length !== 1) return
      const cible = e.target instanceof Element ? e.target : null
      const poignee = racine.querySelector(':scope > .poignee')
      // pas de poignée visible (bureau : saisie en place, panneau, dialogue) : pas de geste
      if (!cible || !poignee || !estVisible(poignee)) return
      const parLaTete = Boolean(cible.closest('.poignee, .feuille-entete'))
      if (!parLaTete && (cible.closest(CHAMPS_TEXTE) || contenuDefile(cible, racine))) return
      const t = e.touches[0]
      const hauteur = racine.getBoundingClientRect().height || window.innerHeight * 0.5
      geste = { x: t.clientX, y: t.clientY, dy: 0, parLaTete, hauteur, etat: 'attente', echantillons: [[Date.now(), 0]] }
    }
    const surMouvement = (e) => {
      if (!geste || geste.etat === 'abandon') return
      const t = e.touches[0]
      if (!t) return
      const dx = t.clientX - geste.x
      const dy = t.clientY - geste.y
      if (geste.etat === 'attente') {
        // vers le bas dès le premier pixel : le défilement (rebond compris) ne part pas
        if (dy > 0 && Math.abs(dy) >= Math.abs(dx) && e.cancelable) e.preventDefault()
        if (Math.abs(dx) < SEUIL_DECISION_PX && Math.abs(dy) < SEUIL_DECISION_PX) return
        if (Math.abs(dx) > Math.abs(dy)) { geste.etat = 'abandon'; return }
        if (dy < 0) { geste.etat = geste.parLaTete ? 'haut' : 'abandon'; return }
        geste.etat = 'tire'
        racine.classList.add('tiree')
        racine.style.transition = 'none'
        if (voile.current) voile.current.style.transition = 'none'
      }
      if (e.cancelable) e.preventDefault()
      geste.dy = dy
      geste.echantillons.push([Date.now(), dy])
      if (geste.echantillons.length > 6) geste.echantillons.shift()
      if (geste.etat === 'tire') poser(Math.max(0, dy))
    }
    const surFin = (e) => {
      const g = geste
      geste = null
      if (!g) return
      if (g.etat === 'haut') {
        if (g.dy <= -SEUIL_CRAN_HAUT_PX) setCran('85')
        if (e.cancelable) e.preventDefault()
        return
      }
      if (g.etat !== 'tire') return
      // le relâcher d'un glissé ne « touche » rien dessous (aucun clic de compatibilité)
      if (e.cancelable) e.preventDefault()
      const [[t0, y0]] = g.echantillons.slice(-3)
      const [t1, y1] = g.echantillons[g.echantillons.length - 1]
      const vitesse = t1 > t0 ? (y1 - y0) / (t1 - t0) : 0
      const loin = g.dy > g.hauteur * SEUIL_TIRE_FRACTION
      const jet = vitesse > SEUIL_TIRE_VITESSE && g.dy > SEUIL_TIRE_JET_MIN_PX
      if (e.type === 'touchend' && (loin || jet)) {
        // fermée là où le doigt l'a laissée : l'animation de sortie part de cette position (translate s'ajoute au transform)
        racine.classList.remove('tiree')
        fermerSansPerte()
        return
      }
      relacher()
    }
    racine.addEventListener('touchstart', surDebut, { passive: true })
    racine.addEventListener('touchmove', surMouvement, { passive: false })
    racine.addEventListener('touchend', surFin, { passive: false })
    racine.addEventListener('touchcancel', surFin, { passive: false })
    return () => {
      racine.removeEventListener('touchstart', surDebut)
      racine.removeEventListener('touchmove', surMouvement)
      racine.removeEventListener('touchend', surFin)
      racine.removeEventListener('touchcancel', surFin)
    }
  }, [feuille, voile, actif, fermerSansPerte, setCran])
}

/** Vrai entre `naviguerApresFeuille` et la fermeture de la feuille qu'elle remplace (voir ci-dessous). */
let navigationVoulue = false

/**
 * F2 acceptation (P138.3) — naviguer en fermant une feuille (supprimer un projet → la liste, créer → le projet…).
 * Le `history.back()` qui retire l'entrée de la feuille est ASYNCHRONE : lancé à la fermeture, il annulait la
 * navigation demandée dans le même geste (on revenait sur le projet supprimé : « Ce projet n'existe plus. »). Ici la
 * navigation REMPLACE l'entrée marquée (aucun retour arrière, l'historique reste propre : le retour mène à l'écran
 * d'avant la feuille). Sans feuille ouverte, navigation ordinaire.
 */
// eslint-disable-next-line react-refresh/only-export-components -- helper co-localisé avec l'entrée d'historique qu'il remplace (D-ENF22)
export function naviguerApresFeuille(navigate, vers, options = {}) {
  const marquee = typeof window !== 'undefined' && Boolean(window.history?.state?.tchFeuille)
  if (marquee) navigationVoulue = true
  navigate(vers, marquee ? { ...options, replace: true } : options)
}

/**
 * Raccord F2 — le retour arrière du navigateur (geste de l'iPhone) ferme la feuille au lieu de quitter l'écran :
 * à l'ouverture, une entrée d'historique MARQUÉE est posée (sans changer l'adresse) ; un retour qui la retire ferme
 * la feuille ; une fermeture par la croix, Échap ou le voile retire l'entrée. La pose est différée d'un tour pour
 * que le double montage du mode strict (développement) n'en laisse aucune.
 */
function useRetourFerme(ouverte, historique, onFermer, apres) {
  const fermer = useRef(onFermer)
  useEffect(() => { fermer.current = onFermer })
  useEffect(() => {
    if (!ouverte) return undefined
    if (!historique || typeof window === 'undefined' || typeof window.history?.pushState !== 'function') {
      // sans entrée d'historique (la fiche, déjà dans l'adresse) : la suite part dès la fermeture — la DERNIÈRE suite
      // posée (lue à la fermeture, voulue : le geste est choisi après l'ouverture)
      return () => apres.current?.()
    }
    const marque = `tch-feuille-${Math.random().toString(36).slice(2)}`
    let posee = false
    let parRetour = false
    const surRetour = () => {
      if (posee && window.history.state?.tchFeuille !== marque) { parRetour = true; fermer.current?.() }
    }
    const minuteur = setTimeout(() => {
      window.history.pushState({ ...(window.history.state ?? {}), tchFeuille: marque }, '')
      posee = true
      window.addEventListener('popstate', surRetour)
    }, 0)
    return () => {
      clearTimeout(minuteur)
      window.removeEventListener('popstate', surRetour)
      const voulue = navigationVoulue
      navigationVoulue = false
      // une navigation demandée en fermant remplace l'entrée marquée : surtout pas de retour arrière qui l'annulerait
      // la DERNIÈRE suite posée, lue à la fermeture (voulu : le geste est choisi après l'ouverture)
      // eslint-disable-next-line react-hooks/exhaustive-deps
      const suite = apres.current
      if (posee && !parRetour && !voulue && window.history.state?.tchFeuille === marque) {
        // R3-063 — la suite (un geste qui ouvre SA feuille) attend que ce retour soit fait : lancée avant, la feuille
        // suivante posait son entrée, puis ce retour asynchrone la retirait — et la fermait aussitôt
        if (suite) {
          const unefois = () => { window.removeEventListener('popstate', unefois); suite() }
          window.addEventListener('popstate', unefois)
        }
        window.history.back()
      } else {
        suite?.()
      }
    }
  }, [ouverte, historique, apres])
}

export default function FeuilleACrans({
  ouverte,
  onFermer,
  titre,
  cranInitial = '50',
  variante = 'dialogue',
  ancre = null,
  historique = true,
  apresFermeture = null,
  children,
}) {
  const [cran, setCran] = useState(cranInitial)
  const feuille = useRef(null)
  const voile = useRef(null)
  const origine = useRef(null)
  const clavier = useClavier(Boolean(ouverte))
  const fermer = useRef(onFermer)
  useEffect(() => { fermer.current = onFermer })
  // R3-060 — toute fermeture voulue (Échap, croix, voile, retour arrière) quitte d'abord le champ en cours
  const fermerSansPerte = useCallback(() => {
    quitterLeChamp(feuille.current)
    fermer.current?.()
  }, [])
  // R3-063 — `apresFermeture` : ce qui suit la fermeture (le geste choisi dans la feuille), une fois son entrée
  // d'historique retirée
  const apres = useRef(apresFermeture)
  useEffect(() => { apres.current = apresFermeture })
  useRetourFerme(Boolean(ouverte), historique, fermerSansPerte, apres)
  const moiRef = useRef(null) // l'entrée de cette feuille dans `pileOuvertes`
  // R2-050 — `variante="panneau"` au bureau large : panneau fixe à droite, NON modal (ni voile, ni piège de Tab) ; la
  // liste reste lisible et cliquable, toucher une autre ligne change la fiche. iPhone et tablette : feuille / dialogue.
  const large = useLarge(REQUETE_PANNEAU)
  const panneau = variante === 'panneau' && large
  // R2-009 (choix C-3) — `variante="popover"` + `ancre` (un élément de l'écran) : la feuille est rendue DANS l'ancre,
  // dans le flux de la page (la saisie à la place de la ligne « Ajouter une tâche »), NON modale et sans voile. Sans
  // ancre, elle reste un dialogue centré (bureau) / la feuille du bas (iPhone).
  const enPlace = variante === 'popover' && Boolean(ancre)
  const nonModale = panneau || enPlace
  const enPanneau = useRef(nonModale) // non modale (panneau, saisie en place) : la liste reste à la main
  useEffect(() => { enPanneau.current = nonModale })
  const seulPanneau = useRef(panneau)
  useEffect(() => { seulPanneau.current = panneau })
  const laisserFocus = useRef(false) // panneau ouvert depuis une ligne : le focus y reste
  const focusDedans = useRef(null) // R3-066 : le dernier élément focalisé DANS la feuille

  useEffect(() => {
    if (!ouverte) return undefined
    const racine = feuille.current
    // R3-066 — un champ `autoFocus` de la feuille (Renommer, Nouveau projet) a déjà le curseur : on le lui laisse (la
    // poignée le lui reprenait), et l'ouvreur est l'élément focalisé juste avant lui
    const { champ, avant } = champAutoFocus(racine)
    const champDejaPris = Boolean(champ)
    origine.current = champDejaPris ? avant : document.activeElement
    focusDedans.current = champ
    // le menu qui a ouvert la feuille a pu reprendre le focus au champ : il lui revient (s'il le rend encore à son
    // bouton ensuite, le rattrapage ci-dessous le ramène au même champ)
    if (champ && document.activeElement !== champ && !document.activeElement?.closest?.(HORS_PIEGE)) champ.focus({ focusVisible: false })
    // R2-050 — le panneau ne vole pas le focus à la LIGNE qui l'a ouvert (`j`/`k` puis Entrée continuent dans la
    // liste) ; ouvert d'ailleurs (un menu, le bilan), il le prend comme une feuille. Fermé, il ne rend le focus que
    // s'il l'avait (ou si plus rien ne l'a) : on ne ramène jamais la personne en arrière dans la liste.
    laisserFocus.current = seulPanneau.current && Boolean(origine.current?.closest?.('[data-ligne]'))
    if (!laisserFocus.current && !champDejaPris) focusInitial(racine)
    const parClavier = derniereModalite === 'clavier'
    return () => {
      const ici = document.activeElement
      const libre = !ici || ici === document.body || racine?.contains(ici) || !ici.isConnected
      if (enPanneau.current && !libre) return
      if (parClavier) origine.current?.focus?.()
      else origine.current?.focus?.({ focusVisible: false })
    }
  }, [ouverte])

  // R2-043 — feuille MODALE : le focus ne repart jamais derrière elle. Un menu Radix qui l'a ouverte (« ⋯ > Alléger »)
  // rend le focus à son bouton juste APRÈS l'ouverture : on le ramène dans la feuille, et ce bouton devient celui
  // où il reviendra à la fermeture. Un menu, une liste, un autre dialogue ou le toast « Annuler » gardent le leur.
  // Le panneau (non modal) ne fait que ce rattrapage d'ouverture : dès que la personne touche ou tape, le focus est
  // à elle (la liste reste à la main).
  useEffect(() => {
    if (!ouverte) return undefined
    let geste = false
    // R3-066 — le dernier élément focalisé DANS la feuille (le champ `autoFocus` de « Renommer ») : c'est lui qui reprend
    // le focus quand le menu qui a ouvert la feuille le rend à son bouton — jamais la poignée à sa place
    const surGeste = () => { geste = true }
    const surFocus = (e) => {
      const cible = e.target
      const racine = feuille.current // lue au moment : la feuille peut être rendue ailleurs (saisie en place → dialogue)
      if (cible instanceof Element && racine?.contains(cible) && cible !== racine) focusDedans.current = cible
      const dedans = focusDedans.current
      if (laisserFocus.current || (enPanneau.current && geste)) return
      if (!racine?.isConnected || pileOuvertes[pileOuvertes.length - 1] !== moiRef.current) return // fermée : on rend
      if (!(cible instanceof Element) || racine.contains(cible) || cible.closest?.(HORS_PIEGE)) return
      origine.current = cible
      if (dedans?.isConnected && racine.contains(dedans)) dedans.focus({ focusVisible: false })
      else focusInitial(racine)
    }
    document.addEventListener('focusin', surFocus)
    document.addEventListener('pointerdown', surGeste, true)
    document.addEventListener('keydown', surGeste, true)
    return () => {
      document.removeEventListener('focusin', surFocus)
      document.removeEventListener('pointerdown', surGeste, true)
      document.removeEventListener('keydown', surGeste, true)
    }
  }, [ouverte])

  // R2-043 — Échap écouté sur `document` tant que cette feuille est la plus haute ouverte : au bureau le focus peut
  // être derrière (clic à la souris sur la liste), l'écouteur posé sur la feuille ne recevait alors jamais la touche.
  // Un menu ouvert (Radix) prend Échap pour lui d'abord (`preventDefault`, en capture) : on le laisse faire.
  useEffect(() => {
    if (!ouverte) return undefined
    const moi = {}
    moiRef.current = moi
    pileOuvertes.push(moi)
    const surEchap = (e) => {
      if (e.key !== 'Escape' || e.defaultPrevented || pileOuvertes[pileOuvertes.length - 1] !== moi) return
      e.preventDefault() // un seul Échap = une seule fermeture (la saisie a aussi son écouteur, il voit `defaultPrevented`)
      fermerSansPerte()
    }
    document.addEventListener('keydown', surEchap)
    return () => {
      document.removeEventListener('keydown', surEchap)
      const rang = pileOuvertes.indexOf(moi)
      if (rang >= 0) pileOuvertes.splice(rang, 1)
    }
  }, [ouverte, fermerSansPerte])

  // R2-048 — contenu plus court que le cran : la feuille épouse son contenu (`cran-auto`, plafond 85 %) — plus de
  // « 300 px de blanc sous les boutons ». Mesuré avant peinture, puis à chaque changement de taille du contenu.
  // R2-009 — la saisie en place devient un dialogue quand on y colle une liste (et inversement) : la feuille est rendue
  // ailleurs, le focus — parti avec l'ancienne — revient dans la nouvelle (au champ, au bureau)
  const rendueEnPlace = useRef(enPlace)
  useEffect(() => {
    if (rendueEnPlace.current === enPlace) return
    rendueEnPlace.current = enPlace
    const ici = document.activeElement
    if (ouverte && (!ici || ici === document.body || !ici.isConnected)) focusInitial(feuille.current)
  }, [ouverte, enPlace])

  const [court, setCourt] = useState(false)
  useLayoutEffect(() => {
    const racine = feuille.current
    const corps = racine?.querySelector('.feuille-corps')
    if (!ouverte || clavier || panneau || enPlace || !corps) return undefined
    const mesurer = () => {
      const naturel = racine.offsetHeight - corps.clientHeight + corps.scrollHeight
      const cible = window.innerHeight * (cran === '85' ? 0.85 : 0.5)
      setCourt(naturel > 0 && naturel < cible)
    }
    mesurer()
    if (typeof ResizeObserver !== 'function') return undefined
    const observateur = new ResizeObserver(mesurer)
    observateur.observe(corps)
    ;[...corps.children].forEach((enfant) => observateur.observe(enfant))
    return () => observateur.disconnect()
  }, [ouverte, clavier, panneau, enPlace, cran])

  useSortieAnimee(ouverte, enPlace, feuille, voile)
  // R4-20 — tirer vers le bas ferme (feuille du bas seulement : la poignée visible est vérifiée au toucher)
  useTirerPourFermer(feuille, voile, Boolean(ouverte) && !enPlace, fermerSansPerte, setCran)

  if (!ouverte) return null

  const surTouche = (e) => {
    if (e.key !== 'Tab' || nonModale) return
    const liste = [...(feuille.current?.querySelectorAll(FOCALISABLES) ?? [])].filter(estVisible)
    if (liste.length === 0) return
    const premier = liste[0]
    const dernier = liste[liste.length - 1]
    if (e.shiftKey && document.activeElement === premier) { e.preventDefault(); dernier.focus() }
    else if (!e.shiftKey && document.activeElement === dernier) { e.preventDefault(); premier.focus() }
  }

  // la variante `panneau` sous 1024 px garde l'allure du dialogue (tablette) et de la feuille du bas (iPhone) ; le
  // `popover` sans ancre, celle du dialogue
  const bureau = variante === 'panneau' ? (panneau ? 'panneau' : 'dialogue') : variante === 'popover' && !enPlace ? 'dialogue' : variante
  const classes = enPlace
    ? ['feuille', 'popover-bureau']
    : ['feuille', clavier ? 'sur-clavier' : court ? 'cran-auto' : `cran-${cran}`, `${bureau}-bureau`]
  const style = clavier && !enPlace ? { '--tch-clavier-h': `${clavier}px` } : undefined
  const grand = cran === '85'

  const corps = (
    <div
      ref={feuille}
      className={classes.join(' ')}
      style={style}
      role="dialog"
      aria-modal={nonModale ? 'false' : 'true'}
      aria-label={titre}
      onKeyDown={surTouche}
    >
      {enPlace ? null : (
        <button
          type="button"
          className="poignee"
          aria-label={grand ? 'Réduire la feuille' : 'Agrandir la feuille'}
          onClick={() => setCran(grand ? '50' : '85')}
        />
      )}
      <div className="feuille-entete">
        <button type="button" className="bouton-icone" aria-label="Fermer" onClick={fermerSansPerte}>
          <X className="i" aria-hidden="true" />
        </button>
        <div className="feuille-titre">{titre}</div>
        <span />
      </div>
      <div className="feuille-corps">{children}</div>
    </div>
  )
  if (enPlace) return createPortal(corps, ancre)
  return (
    <>
      {nonModale ? null : <div ref={voile} className="voile" onClick={fermerSansPerte} aria-hidden="true" />}
      {corps}
    </>
  )
}
