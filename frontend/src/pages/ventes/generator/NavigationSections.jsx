// EDC9 — NAVIGATION DE SECTIONS COLLANTE de l'écran devis.
// ---------------------------------------------------------------------------
// Fondateur 09/10/2026 : un formulaire-fleuve de 13 cartes sans navigation —
// « l'ouvrier doit descendre trop loin ». Une rangée de puces, collée SOUS la
// barre d'actions (EDC4), mène en un clic aux lignes, à l'échéancier, au texte
// client… (NN/g : navigation intra-page collante + `scroll-margin-top`, jamais
// d'accordéon pour le contenu principal).
//
// Les puces sont les cartes RÉELLEMENT rendues : la navigation lit le DOM du
// formulaire (`[id^="gen-sec-"][data-nav-libelle]`, posés sur les cartes par
// `DevisGenerator.jsx`) et le relit à chaque ajout/retrait de nœud
// (MutationObserver) — une carte absente (Simulation en agricole, Échéancier
// en création) n'a donc jamais de puce, sans recopier ici une seule condition
// d'affichage du générateur.
//
// La puce de la section visible porte `aria-current="true"` (IntersectionObserver
// dont la `root` est le défileur réel : `.ldp-edit` dans le panneau,
// `.layout-content` en page). Le défilement est doux, sauf sous
// `prefers-reduced-motion`. Aucune règle métier ici.
import { useEffect, useRef, useState } from 'react'

const SELECTEUR_SECTION = '[id^="gen-sec-"][data-nav-libelle]'
const SELECTEUR_DEFILEUR = '.ldp-edit, .layout-content'

function lireSections(racine) {
  return [...racine.querySelectorAll(SELECTEUR_SECTION)].map((el) => ({
    id: el.id,
    libelle: el.getAttribute('data-nav-libelle'),
  }))
}

const memesSections = (a, b) => a.length === b.length
  && a.every((s, i) => s.id === b[i].id && s.libelle === b[i].libelle)

const mouvementReduit = () => {
  try {
    return Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches)
  } catch {
    return false
  }
}

export default function NavigationSections() {
  const navRef = useRef(null)
  const [sections, setSections] = useState([])
  const [active, setActive] = useState(null)

  // Découverte des cartes rendues (le DOM fait foi) + hauteur de la rangée
  // (`--gen-nav-h` sur `.gen-root` : l'en-tête de table collant, EDC3, se
  // colle SOUS la barre d'actions ET sous cette rangée).
  useEffect(() => {
    const nav = navRef.current
    const formulaire = nav?.closest('form') ?? nav?.parentElement
    if (!nav || !formulaire) return undefined
    const relire = () => {
      const lues = lireSections(formulaire)
      setSections((avant) => (memesSections(avant, lues) ? avant : lues))
    }
    relire()
    const racine = nav.closest('.gen-root')
    const mesurer = () => {
      racine?.style.setProperty('--gen-nav-h', `${Math.ceil(nav.getBoundingClientRect().height)}px`)
    }
    mesurer()
    const mutations = typeof MutationObserver === 'undefined' ? null : new MutationObserver(relire)
    mutations?.observe(formulaire, { childList: true, subtree: true })
    const tailles = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(mesurer)
    tailles?.observe(nav)
    return () => {
      mutations?.disconnect()
      tailles?.disconnect()
    }
  }, [])

  // Section visible : la PREMIÈRE (ordre du formulaire) qui croise la bande
  // située juste sous la barre d'actions et la rangée de puces ; tout en bas du
  // défileur, la dernière (une carte courte en fin de page n'atteint jamais
  // la bande).
  useEffect(() => {
    const nav = navRef.current
    const formulaire = nav?.closest('form')
    if (!nav || !formulaire || !sections.length || typeof IntersectionObserver === 'undefined') {
      return undefined
    }
    const defileur = nav.closest(SELECTEUR_DEFILEUR)
    const barre = nav.closest('.gen-root')?.querySelector('.gen-barre-actions')
    const haut = Math.round((barre?.offsetHeight ?? 0) + nav.offsetHeight)
    const enVue = new Map()
    const auBas = () => Boolean(defileur)
      && defileur.scrollTop > 0
      && defileur.scrollTop + defileur.clientHeight >= defileur.scrollHeight - 4
    const choisir = () => {
      if (auBas()) { setActive(sections.at(-1).id); return }
      const premiere = sections.find((s) => enVue.get(s.id))
      if (premiere) setActive(premiere.id)
    }
    const observateur = new IntersectionObserver((entrees) => {
      for (const entree of entrees) enVue.set(entree.target.id, entree.isIntersecting)
      choisir()
    }, { root: defileur ?? null, rootMargin: `-${haut}px 0px -55% 0px`, threshold: 0 })
    for (const s of sections) {
      const el = formulaire.querySelector(`[id="${s.id}"]`)
      if (el) observateur.observe(el)
    }
    const surDefilement = () => { if (auBas()) setActive(sections.at(-1).id) }
    defileur?.addEventListener('scroll', surDefilement, { passive: true })
    return () => {
      observateur.disconnect()
      defileur?.removeEventListener('scroll', surDefilement)
    }
  }, [sections])

  const aller = (id) => {
    const el = navRef.current?.closest('form')?.querySelector(`[id="${id}"]`)
    if (!el) return
    // `scroll-margin-top` (index.css, bloc EDC9) garde la carte sous la barre
    // et la rangée ; le défileur réel est l'ancêtre, scrollIntoView le trouve.
    el.scrollIntoView({ block: 'start', behavior: mouvementReduit() ? 'auto' : 'smooth' })
    setActive(id)
  }

  return (
    <nav ref={navRef} className="gen-nav-sections" aria-label="Sections du devis"
         hidden={!sections.length}>
      <ul className="gen-nav-liste">
        {sections.map((s) => (
          <li key={s.id}>
            <button type="button" className="gen-nav-puce"
                    aria-current={active === s.id ? 'true' : undefined}
                    onClick={() => aller(s.id)}>
              {s.libelle}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  )
}
