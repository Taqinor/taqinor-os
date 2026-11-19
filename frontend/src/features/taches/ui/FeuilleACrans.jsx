import { useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'

/* ============================================================================
   TCH45 — Feuille du bas à crans (spec-7 §10, spec-8 §2 : rayon 20, `--popover` +
   `--shadow-lg`, 260 ms entrée / 180 ms sortie). Deux crans, 50 % et 85 % de la hauteur,
   que la poignée (44 px) fait basculer : « Agrandir la feuille » / « Réduire la feuille ».
   CLAVIER OUVERT : les crans ne valent plus (86 px utiles à 50 %) — la feuille épouse son
   contenu et se pose SUR le clavier (`sur-clavier`, hauteur du clavier lue sur
   `visualViewport`, jetée dans `--tch-clavier-h`). Au bureau (≥ 768 px) la même feuille est
   un dialogue centré (`dialogue-bureau`) ou un popover (`popover-bureau`) — CSS seul.
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

  useEffect(() => {
    if (!ouverte) return undefined
    origine.current = document.activeElement
    const racine = feuille.current
    // F2 acceptation (P144.3) — une feuille ouverte au clavier peut désigner son action par défaut
    // (`data-focus-initial`) : Entrée la valide aussitôt. Sinon (R2-043) le premier élément VISIBLE : la poignée sur
    // l'iPhone (aucun clavier qui surgit), au bureau — poignée cachée — le premier champ, sinon « Fermer ».
    const voulu = premierVisible(racine, '[data-focus-initial]')
    const poignee = premierVisible(racine, '.poignee')
    // passe visuelle n° 26 — posé d'office sur la poignée, le focus ne dessine pas d'anneau (« poignée discrète »,
    // ecran-bilan.html) : il chevauchait l'écran du dessous. Tab le rend visible ; une action désignée garde le sien.
    if (voulu) voulu.focus()
    else if (poignee) poignee.focus({ focusVisible: false })
    else (premierVisible(racine, CHAMPS) ?? premierVisible(racine, FOCALISABLES))?.focus()
    return () => origine.current?.focus?.()
  }, [ouverte])

  // R2-043 — Échap écouté sur `document` tant que cette feuille est la plus haute ouverte : au bureau le focus peut
  // être derrière (clic à la souris sur la liste), l'écouteur posé sur la feuille ne recevait alors jamais la touche.
  // Un menu ouvert (Radix) prend Échap pour lui d'abord (`preventDefault`, en capture) : on le laisse faire.
  useEffect(() => {
    if (!ouverte) return undefined
    const moi = {}
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

  if (!ouverte) return null

  const surTouche = (e) => {
    if (e.key !== 'Tab') return
    const liste = [...(feuille.current?.querySelectorAll(FOCALISABLES) ?? [])].filter(estVisible)
    if (liste.length === 0) return
    const premier = liste[0]
    const dernier = liste[liste.length - 1]
    if (e.shiftKey && document.activeElement === premier) { e.preventDefault(); dernier.focus() }
    else if (!e.shiftKey && document.activeElement === dernier) { e.preventDefault(); premier.focus() }
  }

  const classes = ['feuille', clavier ? 'sur-clavier' : `cran-${cran}`, `${variante}-bureau`]
  const style = clavier ? { '--tch-clavier-h': `${clavier}px` } : undefined
  const grand = cran === '85'

  return (
    <>
      <div className="voile" onClick={onFermer} aria-hidden="true" />
      <div
        ref={feuille}
        className={classes.join(' ')}
        style={style}
        role="dialog"
        aria-modal="true"
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
