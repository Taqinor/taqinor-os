import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'

/* ============================================================================
   TCH45 — Feuille du bas à crans (spec-7 §10, spec-8 §2 : rayon 20, `--popover` +
   `--shadow-lg`, 260 ms entrée / 180 ms sortie). Deux crans, 50 % et 85 % de la hauteur,
   que la poignée (44 px) fait basculer : « Agrandir la feuille » / « Réduire la feuille ».
   CLAVIER OUVERT : les crans ne valent plus (86 px utiles à 50 %) — la feuille épouse son
   contenu et se pose SUR le clavier (`sur-clavier`, hauteur du clavier lue sur
   `visualViewport`, jetée dans `--tch-clavier-h`). Au bureau (≥ 768 px) la même feuille est
   un dialogue centré (`dialogue-bureau`) ou un popover (`popover-bureau`) — CSS seul ; `variante="panneau"`
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
  if (voulu) voulu.focus()
  else if (poignee) poignee.focus({ focusVisible: false })
  else (premierVisible(racine, CHAMPS) ?? premierVisible(racine, FOCALISABLES))?.focus()
}

/** Ce qui garde son focus même hors d'une feuille modale : menus et listes (portails Radix), autres dialogues, toast. */
const HORS_PIEGE = '[role="dialog"], [role="alertdialog"], [role="menu"], [role="listbox"], [data-radix-popper-content-wrapper], .toast-place'

/** R2-049 — le dernier geste était-il au clavier ? (lu à l'ouverture d'une feuille) Au doigt ou à la souris, le focus
 *  rendu à la fermeture ne dessine pas d'anneau épais sur le bouton touché (« ⋯ » après Alléger). */
let derniereModalite = 'pointeur'
if (typeof document !== 'undefined') {
  document.addEventListener('keydown', () => { derniereModalite = 'clavier' }, true)
  document.addEventListener('pointerdown', () => { derniereModalite = 'pointeur' }, true)
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
function useRetourFerme(actif, onFermer) {
  const fermer = useRef(onFermer)
  useEffect(() => { fermer.current = onFermer })
  useEffect(() => {
    if (!actif || typeof window === 'undefined' || typeof window.history?.pushState !== 'function') return undefined
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
      if (posee && !parRetour && !voulue && window.history.state?.tchFeuille === marque) window.history.back()
    }
  }, [actif])
}

export default function FeuilleACrans({
  ouverte,
  onFermer,
  titre,
  cranInitial = '50',
  variante = 'dialogue',
  historique = true,
  children,
}) {
  const [cran, setCran] = useState(cranInitial)
  const feuille = useRef(null)
  const origine = useRef(null)
  const clavier = useClavier(Boolean(ouverte))
  useRetourFerme(Boolean(ouverte) && historique, onFermer)
  const fermer = useRef(onFermer)
  useEffect(() => { fermer.current = onFermer })
  const moiRef = useRef(null) // l'entrée de cette feuille dans `pileOuvertes`
  // R2-050 — `variante="panneau"` au bureau large : panneau fixe à droite, NON modal (ni voile, ni piège de Tab) ; la
  // liste reste lisible et cliquable, toucher une autre ligne change la fiche. iPhone et tablette : feuille / dialogue.
  const large = useLarge(REQUETE_PANNEAU)
  const panneau = variante === 'panneau' && large
  const enPanneau = useRef(panneau)
  useEffect(() => { enPanneau.current = panneau })
  const laisserFocus = useRef(false) // panneau ouvert depuis une ligne : le focus y reste

  useEffect(() => {
    if (!ouverte) return undefined
    origine.current = document.activeElement
    const racine = feuille.current
    // R2-050 — le panneau ne vole pas le focus à la LIGNE qui l'a ouvert (`j`/`k` puis Entrée continuent dans la
    // liste) ; ouvert d'ailleurs (un menu, le bilan), il le prend comme une feuille. Fermé, il ne rend le focus que
    // s'il l'avait (ou si plus rien ne l'a) : on ne ramène jamais la personne en arrière dans la liste.
    laisserFocus.current = enPanneau.current && Boolean(origine.current?.closest?.('[data-ligne]'))
    if (!laisserFocus.current) focusInitial(racine)
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
    const racine = feuille.current
    let geste = false
    const surGeste = () => { geste = true }
    const surFocus = (e) => {
      const cible = e.target
      if (laisserFocus.current || (enPanneau.current && geste)) return
      if (!racine?.isConnected || pileOuvertes[pileOuvertes.length - 1] !== moiRef.current) return // fermée : on rend
      if (!(cible instanceof Element) || racine.contains(cible) || cible.closest?.(HORS_PIEGE)) return
      origine.current = cible
      focusInitial(racine)
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
      fermer.current?.()
    }
    document.addEventListener('keydown', surEchap)
    return () => {
      document.removeEventListener('keydown', surEchap)
      const rang = pileOuvertes.indexOf(moi)
      if (rang >= 0) pileOuvertes.splice(rang, 1)
    }
  }, [ouverte])

  // R2-048 — contenu plus court que le cran : la feuille épouse son contenu (`cran-auto`, plafond 85 %) — plus de
  // « 300 px de blanc sous les boutons ». Mesuré avant peinture, puis à chaque changement de taille du contenu.
  const [court, setCourt] = useState(false)
  useLayoutEffect(() => {
    const racine = feuille.current
    const corps = racine?.querySelector('.feuille-corps')
    if (!ouverte || clavier || panneau || !corps) return undefined
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
  }, [ouverte, clavier, panneau, cran])

  if (!ouverte) return null

  const surTouche = (e) => {
    if (e.key !== 'Tab' || panneau) return
    const liste = [...(feuille.current?.querySelectorAll(FOCALISABLES) ?? [])].filter(estVisible)
    if (liste.length === 0) return
    const premier = liste[0]
    const dernier = liste[liste.length - 1]
    if (e.shiftKey && document.activeElement === premier) { e.preventDefault(); dernier.focus() }
    else if (!e.shiftKey && document.activeElement === dernier) { e.preventDefault(); premier.focus() }
  }

  // la variante `panneau` sous 1024 px garde l'allure du dialogue (tablette) et de la feuille du bas (iPhone)
  const bureau = variante === 'panneau' ? (panneau ? 'panneau' : 'dialogue') : variante
  const classes = ['feuille', clavier ? 'sur-clavier' : court ? 'cran-auto' : `cran-${cran}`, `${bureau}-bureau`]
  const style = clavier ? { '--tch-clavier-h': `${clavier}px` } : undefined
  const grand = cran === '85'

  return (
    <>
      {panneau ? null : <div className="voile" onClick={onFermer} aria-hidden="true" />}
      <div
        ref={feuille}
        className={classes.join(' ')}
        style={style}
        role="dialog"
        aria-modal={panneau ? 'false' : 'true'}
        aria-label={titre}
        onKeyDown={surTouche}
      >
        <button
          type="button"
          className="poignee"
          aria-label={grand ? 'Réduire la feuille' : 'Agrandir la feuille'}
          onClick={() => setCran(grand ? '50' : '85')}
        />
        <div className="feuille-entete">
          <button type="button" className="bouton-icone" aria-label="Fermer" onClick={onFermer}>
            <X className="i" aria-hidden="true" />
          </button>
          <div className="feuille-titre">{titre}</div>
          <span />
        </div>
        <div className="feuille-corps">{children}</div>
      </div>
    </>
  )
}
