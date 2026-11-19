import { useEffect, useRef } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { ABR_JOURS, duree as dureeTexte } from '../lib/textes'
import VoletAPlacer from '../ui/VoletAPlacer'

/* ============================================================================
   TCH106 — « Planifier ma semaine » (`/taches/agenda?placer=1`, fin de la Revue) : les sept
   jours de la Semaine en sept lignes + le volet « À placer » avec « Mes projets » déplié.
   Toucher une tâche puis un jour la pose sur ce jour (`taches/{id}/planifier/`, sans heure),
   SANS ouvrir de fiche ; au bureau, la glisser sur un jour, ou (tâche choisie) ← → pour aller
   d'un jour à l'autre puis Entrée. Jour passé : « passé · {n} faites », non posable ; jour non
   travaillé : « non travaillé ». En-tête de jour « {n} tâches · {durée} ». Bouton **Terminer**.
   Maquettes : agenda-semaine-planifier.html, agenda-semaine-planifier-pose.html ; textes.md §2.8.
   La capacité du jour (« pour {cap} », barre de charge) n'est affichée que si `agenda/` la sert (`capacite.minutes`) :
   aucun chiffre inventé. Le composant ne parle jamais au serveur.
   ========================================================================== */

const versUtc = (iso) => { const [a, m, j] = iso.split('-').map(Number); return Date.UTC(a, m - 1, j) }
const nomJour = (iso) => `${ABR_JOURS[new Date(versUtc(iso)).getUTCDay()]} ${Number(iso.slice(8, 10))}`
/** « 4 h » ne se coupe jamais entre le chiffre et l'unité (« pour 4 / h » sur deux lignes) */
const insecables = (texte) => String(texte).replace(/(\d) (h|min)\b/g, '$1\u00a0$2')
const accordTaches = (n) => (n >= 2 ? `${n} tâches` : `${n} tâche`)

/** Barre de charge (maquette : la capacité est le repère à 2/3 de la barre ; au-delà, la part en trop). */
function BarreCharge({ minutes, capacite }) {
  const echelle = capacite * 1.5
  const dans = Math.min(minutes, capacite) / echelle * 100
  const trop = Math.max(0, Math.min(minutes, echelle) - capacite) / echelle * 100
  return (
    <span className="ag-charge" aria-hidden="true">
      <i className="b" style={{ '--c': `${dans}%` }} />
      {trop > 0 ? <i className="bp" style={{ '--c': `${trop}%` }} /> : null}
    </span>
  )
}

/** L'en-tête d'un jour (textes.md §2.8) — partagé avec la vue Semaine de l'Agenda (F2 acceptation, P139.1). */
// eslint-disable-next-line react-refresh/only-export-components -- helper pur co-localisé (D-ENF22)
export function resume(jour, aujourdhui, capaciteServie = null) {
  const taches = [...(jour.blocs ?? []), ...(jour.sans_heure ?? [])]
  if (jour.jour < aujourdhui) {
    // R2-102 (règle C-12) — « faites » = les tâches FINIES ce jour-là, le nombre de Mon rythme servi par `agenda/`
    // (`faites_nb`), jamais un recompte des tâches prévues ce jour-là ; non servi : rien de deviné.
    const faites = jour.faites_nb
    if (!Number.isInteger(faites)) return { passe: true, texte: 'passé' }
    return { passe: true, texte: `passé · ${faites} ${faites >= 2 ? 'faites' : 'faite'}` }
  }
  if (!jour.ouvre || jour.ferie) return { repos: true, texte: jour.ferie ? 'Férié' : 'non travaillé' }
  const ouvertes = taches.filter((t) => t.statut !== 'fait')
  const minutes = ouvertes.reduce((n, t) => n + (t.estimation_minutes || 0), 0)
  // Raccord F2 — « {n} tâches · {h} pour {cap} » (textes.md §2.8) et la barre de charge SEULEMENT si `agenda/` sert
  // la capacité (`capacite: {minutes, source}`) ; sinon elles sont omises, jamais devinées.
  const base = Number.isFinite(capaciteServie) && capaciteServie > 0 ? capaciteServie : null
  if (base) {
    // R2-100 — le temps libre du jour = la capacité moins ses rendez-vous (servi : `rendez_vous_minutes`, invariant 35)
    const pris = Number.isFinite(jour.rendez_vous_minutes) && jour.rendez_vous_minutes > 0 ? jour.rendez_vous_minutes : 0
    const capacite = Math.max(0, base - pris)
    const texte = `${accordTaches(ouvertes.length)} · ${dureeTexte(minutes) || '0 min'} pour ${dureeTexte(capacite) || '0 min'}`
    // R2-114 — un jour qui dépasse son temps libre le DIT (« 3 h 30 de trop »), pas seulement par un segment orange
    const trop = minutes > capacite ? dureeTexte(minutes - capacite) : ''
    return {
      texte: trop ? `${texte} · ${trop} de trop` : texte, base: texte, trop: trop ? `${trop} de trop` : '',
      charge: capacite > 0 ? { minutes, capacite } : null,
    }
  }
  return { texte: minutes ? `${accordTaches(ouvertes.length)} · ${dureeTexte(minutes)}` : accordTaches(ouvertes.length) }
}

/** Raccord F2 — au bureau (≥ 1024 px), chaque jour est une COLONNE à cartes (agenda-semaine-planifier.html) ; sur
 * iPhone ces cartes sont masquées et le jour reste une ligne. Décor seulement : le nom du jour reste sur le bouton. */
function CartesDuJour({ jour }) {
  const taches = [...(jour.blocs ?? []), ...(jour.sans_heure ?? [])]
  if (taches.length === 0) return null
  return (
    <span className="ag-pj-cartes" aria-hidden="true">
      {taches.map((t) => {
        const heure = t.heure_debut ? t.heure_debut.slice(0, 5) : ''
        const d = dureeTexte(t.estimation_minutes)
        return (
          <span key={t.id} className={t.statut === 'fait' ? 'ag-carte faite' : 'ag-carte'}>
            {heure ? <span className="h">{d ? `${heure} · ${d}` : heure}</span> : null}
            <span className="t">{t.titre}</span>
            {t.projet ? (
              <span className="m"><i className="point" data-p={t.projet.couleur || undefined} /><span>{t.projet.nom}</span></span>
            ) : null}
          </span>
        )
      })}
    </span>
  )
}

function LigneJour({ jour, aujourdhui, capacite, choisie, posee, onPoser, onDeposer, onOuvrirJour, refBouton }) {
  const { passe, repos, texte, base, trop, charge } = resume(jour, aujourdhui, capacite)
  const nom = nomJour(jour.jour)
  const classes = ['ag-pj', passe ? 'passe' : '', repos ? 'repos' : '', jour.jour === aujourdhui ? 'auj' : '',
    posee ? 'nouveau' : ''].filter(Boolean).join(' ')
  const poser = () => (choisie ? onPoser(choisie, jour.jour) : onOuvrirJour(jour.jour))
  return (
    <div role="listitem" className={repos ? 'ag-pj-place repos' : 'ag-pj-place'}>
      <button
        ref={refBouton}
        type="button"
        className={classes}
        disabled={passe}
        aria-current={jour.jour === aujourdhui ? 'date' : undefined}
        onClick={poser}
        onDragOver={(e) => { if (!passe) e.preventDefault() }}
        // R3-120 — le dépôt d'une tâche GLISSÉE (la page la retient sans la « choisir ») ; sinon la tâche choisie
        onDrop={(e) => {
          e.preventDefault()
          if (passe) return
          if (onDeposer) onDeposer(jour.jour)
          else if (choisie) onPoser(choisie, jour.jour)
        }}
      >
        {/* Le nom accessible est porté par `.sr` ; le texte visible est masqué au lecteur d'écran : le nom
            ne peut donc pas contredire ce qui se voit (axe `label-content-name-mismatch`). */}
        <span className="sr">{choisie && !passe ? `${nom} · ${texte} · placer ${choisie.titre}` : `${nom} · ${texte}`}</span>
        <span className="j" aria-hidden="true">{nom}</span>
        <span className="n" aria-hidden="true">
          {trop ? <>{insecables(base)}{' · '}<b className="trop">{insecables(trop)}</b></> : insecables(texte)}
        </span>
        {charge ? <BarreCharge {...charge} /> : null}
        <CartesDuJour jour={jour} />
        {posee ? (
          <span className="ag-pj-ajout" aria-hidden="true" data-p={posee.projet?.couleur || undefined}>
            <i className="point" aria-hidden="true" />{posee.titre}
          </span>
        ) : null}
      </button>
    </div>
  )
}

/** ← → déplacent le focus d'un jour posable à l'autre tant qu'une tâche est choisie (Entrée pose). */
function useFlechesJours(actif, boutons) {
  useEffect(() => {
    if (!actif) return undefined
    const surTouche = (e) => {
      if (!['ArrowLeft', 'ArrowRight'].includes(e.key) || e.shiftKey || e.altKey || e.metaKey || e.ctrlKey) return
      if (e.target?.closest?.('input, textarea, [contenteditable="true"]')) return
      const liste = boutons.current.filter((b) => b && !b.disabled)
      if (!liste.length) return
      e.preventDefault()
      const ici = liste.indexOf(document.activeElement)
      const sens = e.key === 'ArrowRight' ? 1 : -1
      const suivant = ici === -1 ? (sens === 1 ? 0 : liste.length - 1) : (ici + sens + liste.length) % liste.length
      liste[suivant].focus()
    }
    window.addEventListener('keydown', surTouche)
    return () => window.removeEventListener('keydown', surTouche)
  }, [actif, boutons])
}

/**
 * `jours` : les sept jours de la semaine (`agenda.json` → `jours`, complétés) ; `choisie` : la tâche
 * choisie (objet ou nul) ; `posees` : `{jour: tâche}` des dernières poses ; `onPoser(item, jour)`.
 */
export default function PlanifierSemaine({
  jours, aujourdhui, capacite = null, aPlacer = [], mesProjets = [], choisie = null, posees = {},
  onChoisir, onPoser, onOuvrirJour, onTerminer, onSemaine = null, semaine = '', onGlisser = undefined, onDeposer = undefined,
}) {
  const boutons = useRef([])
  useFlechesJours(Boolean(choisie), boutons)
  // R2-105 — sur iPhone les jours et le volet « À placer » sont l'un sous l'autre : une tâche choisie, la vue monte sur
  // les jours ; la tâche posée (ou le choix annulé), elle revient sur le volet : on place trois tâches sans défiler.
  const racine = useRef(null)
  const avait = useRef(false)
  useEffect(() => {
    const actif = Boolean(choisie)
    if (actif === avait.current) return
    avait.current = actif
    if (window.matchMedia?.('(min-width: 1024px)').matches) return // au bureau tout est visible d'un coup
    const cible = racine.current?.querySelector(actif ? '.ag-jours' : '.ag-aside')
    const reduit = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    cible?.scrollIntoView?.({ block: 'start', behavior: reduit ? 'auto' : 'smooth' })
  }, [choisie])
  // R3-122 — au bureau les sept jours tiennent sur UNE rangée : un jour non travaillé VIDE est étroit (72 px), un week-end
  // qui porte des tâches (ou une tâche qu'on y pose) garde une colonne entière (agenda.css lit `--ag-jours-colonnes`)
  const etroit = (j) => (!j.ouvre || j.ferie) && !posees[j.jour] && ![...(j.blocs ?? []), ...(j.sans_heure ?? [])].length
  const colonnes = jours.map((j) => (etroit(j) ? 'minmax(72px, 0.6fr)' : 'minmax(0, 1fr)')).join(' ')
  return (
    <div className="ag-planifier" ref={racine}>
      <div className="ag-planifier-tete">
        <span className="raccourci bureau-seul">
          Glisse une tâche sur un jour · ou <kbd>Entrée</kbd> puis <kbd>←</kbd> <kbd>→</kbd>
        </span>
        <button type="button" className="bouton plein ag-terminer" onClick={onTerminer}>Terminer</button>
      </div>
      {onSemaine ? (
        // R2-103 — de semaine en semaine sans quitter le mode ; R3-123 — « ‹ 16 – 22 nov. › » sur UNE rangée : la semaine
        // est dite ici, entre les flèches, et nulle part ailleurs
        <div className="ag-plan-nav">
          <button type="button" className="bouton-icone" aria-label="Semaine précédente" onClick={() => onSemaine(-1)}>
            <ChevronLeft className="i" aria-hidden="true" />
          </button>
          {semaine ? <b className="ag-plan-semaine chiffres">{semaine}</b> : null}
          <button type="button" className="bouton-icone" aria-label="Semaine suivante" onClick={() => onSemaine(1)}>
            <ChevronRight className="i" aria-hidden="true" />
          </button>
        </div>
      ) : null}
      <div className="ag-corps">
        <div className="ag-jours chiffres" role="list" aria-label="Jours de la semaine" style={{ '--ag-jours-colonnes': colonnes }}>
          {jours.map((j, rang) => (
            <LigneJour
              key={j.jour} jour={j} aujourdhui={aujourdhui} capacite={capacite} choisie={choisie} posee={posees[j.jour] ?? null}
              onPoser={onPoser} onDeposer={onDeposer} onOuvrirJour={onOuvrirJour}
              refBouton={(el) => { boutons.current[rang] = el }}
            />
          ))}
        </div>
        <VoletAPlacer
          aPlacer={aPlacer} mesProjets={mesProjets} aujourdhui={aujourdhui} choisie={choisie?.id ?? null}
          onChoisir={onChoisir} onGlisser={onGlisser} projetsOuverts
          consigne={(titre) => `Touche un jour pour placer ${titre}`}
          aide="Glisse une tâche sur un jour · ou Entrée puis ← →" aideTactile="Touche une tâche, puis un jour."
        />
      </div>
    </div>
  )
}
