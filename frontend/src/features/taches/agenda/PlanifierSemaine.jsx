import { useEffect, useRef } from 'react'
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
   La capacité du jour (« pour {cap} ») n'est affichée que si `agenda/` la sert (`jours[].capacite_minutes`) :
   aucun chiffre inventé. Le composant ne parle jamais au serveur.
   ========================================================================== */

const versUtc = (iso) => { const [a, m, j] = iso.split('-').map(Number); return Date.UTC(a, m - 1, j) }
const nomJour = (iso) => `${ABR_JOURS[new Date(versUtc(iso)).getUTCDay()]} ${Number(iso.slice(8, 10))}`
const accordTaches = (n) => (n >= 2 ? `${n} tâches` : `${n} tâche`)

function resume(jour, aujourdhui) {
  const taches = [...(jour.blocs ?? []), ...(jour.sans_heure ?? [])]
  if (jour.jour < aujourdhui) {
    const faites = taches.filter((t) => t.statut === 'fait').length
    return { passe: true, texte: `passé · ${faites} ${faites >= 2 ? 'faites' : 'faite'}` }
  }
  if (!jour.ouvre || jour.ferie) return { repos: true, texte: jour.ferie ? 'Férié' : 'non travaillé' }
  const ouvertes = taches.filter((t) => t.statut !== 'fait')
  const minutes = ouvertes.reduce((n, t) => n + (t.estimation_minutes || 0), 0)
  // Raccord F2 — « {n} tâches · {h} pour {cap} » (textes.md §2.8) SEULEMENT si le serveur sert la capacité du jour
  // (`jours[].capacite_minutes`, même nom que `progression.capacite_minutes`) ; sinon elle est omise, jamais devinée.
  const capacite = Number.isFinite(jour.capacite_minutes) && jour.capacite_minutes > 0 ? jour.capacite_minutes : null
  if (capacite) {
    return {
      texte: `${accordTaches(ouvertes.length)} · ${dureeTexte(minutes) || '0 min'} pour ${dureeTexte(capacite)}`,
      surcharge: minutes > capacite,
    }
  }
  return { texte: minutes ? `${accordTaches(ouvertes.length)} · ${dureeTexte(minutes)}` : accordTaches(ouvertes.length) }
}

function LigneJour({ jour, aujourdhui, choisie, posee, onPoser, onOuvrirJour, refBouton }) {
  const { passe, repos, texte } = resume(jour, aujourdhui)
  const nom = nomJour(jour.jour)
  const classes = ['ag-pj', passe ? 'passe' : '', repos ? 'repos' : '', jour.jour === aujourdhui ? 'auj' : '',
    posee ? 'nouveau' : ''].filter(Boolean).join(' ')
  const poser = () => (choisie ? onPoser(choisie, jour.jour) : onOuvrirJour(jour.jour))
  return (
    <div role="listitem">
      <button
        ref={refBouton}
        type="button"
        className={classes}
        disabled={passe}
        aria-current={jour.jour === aujourdhui ? 'date' : undefined}
        aria-label={choisie && !passe ? `${nom} · ${texte} · placer ${choisie.titre}` : `${nom} · ${texte}`}
        onClick={poser}
        onDragOver={(e) => { if (!passe) e.preventDefault() }}
        onDrop={(e) => { e.preventDefault(); if (!passe && choisie) onPoser(choisie, jour.jour) }}
      >
        <span className="j">{nom}</span>
        <span className="n">{texte}</span>
        {posee ? (
          <span className="ag-pj-ajout" data-p={posee.projet?.couleur || undefined}>
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
  jours, aujourdhui, aPlacer = [], mesProjets = [], choisie = null, posees = {},
  onChoisir, onPoser, onOuvrirJour, onTerminer,
}) {
  const boutons = useRef([])
  useFlechesJours(Boolean(choisie), boutons)
  return (
    <div className="ag-planifier">
      <div className="ag-planifier-tete">
        <span className="raccourci bureau-seul">
          Glisse une tâche sur un jour · ou <kbd>Entrée</kbd> puis <kbd>←</kbd> <kbd>→</kbd>
        </span>
        <button type="button" className="bouton plein ag-terminer" onClick={onTerminer}>Terminer</button>
      </div>
      <div className="ag-corps">
        <div className="ag-jours chiffres" role="list" aria-label="Jours de la semaine">
          {jours.map((j, rang) => (
            <LigneJour
              key={j.jour} jour={j} aujourdhui={aujourdhui} choisie={choisie} posee={posees[j.jour] ?? null}
              onPoser={onPoser} onOuvrirJour={onOuvrirJour}
              refBouton={(el) => { boutons.current[rang] = el }}
            />
          ))}
        </div>
        <VoletAPlacer
          aPlacer={aPlacer} mesProjets={mesProjets} aujourdhui={aujourdhui} choisie={choisie?.id ?? null}
          onChoisir={onChoisir} projetsOuverts
          consigne={(titre) => `Touche un jour pour placer ${titre}`}
          aide="Glisse une tâche sur un jour · ou Entrée puis ← →"
        />
      </div>
    </div>
  )
}
