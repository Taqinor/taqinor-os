import { useState } from 'react'
import { Check, Star } from 'lucide-react'
import { heure } from '../lib/textes'

/* ============================================================================
   TCH104 — LA grille horaire de l'Agenda : un jour (vue Jour) ou sept (vue Semaine), une
   colonne par jour de `agenda.json` (`jours[]`). Maquettes : agenda-jour.html,
   agenda-semaine.html, composants-8.html ; classes de base.css (`.agenda`, `.semaine`,
   `.bloc`, `.maintenant`) et d'agenda.css (`.ag-*`).

   Dans une colonne :
     · les BLOCS des tâches à heure (`blocs`), hauteur = `estimation_minutes` (30 min et
       « durée non estimée » sans estimation), case « Fait : {titre} » et titre qui ouvre la fiche ;
     · les rendez-vous EXTERNES (`externes`, hors journée entière) en LECTURE SEULE : puce du
       libellé de l'agenda ; toucher → « {titre} · {HH:MM}–{HH:MM} · {libellé} · Ouvrir dans ton
       agenda d'origine » ;
     · deux blocs qui se chevauchent se partagent la largeur, au-delà « +{n} » ;
     · chaque créneau VIDE est un bouton « Ajouter à {HH:MM} » ; pendant un placement (TCH105)
       il devient « Placer à {HH:MM} » et pose la tâche choisie ;
     · la ligne « maintenant » sur la colonne d'aujourd'hui.
   Le composant ne parle jamais au serveur : il appelle les rappels de la page.
   ========================================================================== */

const DUREE_DEFAUT = 30
const VOIES_VISIBLES = 2
const COURT = 30
const deux = (n) => String(n).padStart(2, '0')

function enMinutes(texte) {
  const m = /^(\d{1,2}):(\d{2})/.exec(String(texte ?? ''))
  return m ? Number(m[1]) * 60 + Number(m[2]) : null
}

const enHeure = (minutes) => `${deux(Math.floor(minutes / 60) % 24)}:${deux(minutes % 60)}`
/** L'heure murale d'un instant ISO servi avec son décalage (« 2026-11-17T11:00:00+01:00 » → 660). */
const minutesDeLInstant = (iso) => enMinutes(String(iso ?? '').slice(11, 16))

function evenements(jour) {
  const taches = (jour.blocs ?? []).filter((t) => enMinutes(t.heure_debut) !== null).map((t) => {
    const debut = enMinutes(t.heure_debut)
    return {
      cle: `tache:${t.id}`, type: 'tache', item: t, debut,
      fin: debut + (t.estimation_minutes || DUREE_DEFAUT), sansDuree: !t.estimation_minutes,
    }
  })
  const externes = (jour.externes ?? []).filter((e) => !e.journee_entiere).map((e) => {
    const debut = minutesDeLInstant(e.debut) ?? 0
    const fin = minutesDeLInstant(e.fin)
    return { cle: `externe:${e.cle}`, type: 'externe', item: e, debut, fin: fin > debut ? fin : debut + DUREE_DEFAUT }
  })
  return [...taches, ...externes].sort((a, b) => a.debut - b.debut || b.fin - a.fin)
}

/** Répartit les événements en voies par groupe de chevauchement (`voie`, `voies`, `groupe`). */
function disposer(liste) {
  const groupes = []
  let courant = null
  for (const ev of liste) {
    if (!courant || ev.debut >= courant.fin) {
      courant = { membres: [], fin: ev.fin, voies: [] }
      groupes.push(courant)
    }
    let voie = courant.voies.findIndex((finVoie) => finVoie <= ev.debut)
    if (voie === -1) { voie = courant.voies.length; courant.voies.push(ev.fin) } else courant.voies[voie] = ev.fin
    courant.fin = Math.max(courant.fin, ev.fin)
    courant.membres.push({ ...ev, voie })
  }
  return groupes.flatMap((g, rang) => {
    const caches = g.membres.filter((ev) => ev.voie >= VOIES_VISIBLES).length
    return g.membres.map((ev) => ({ ...ev, voies: g.voies.length, groupe: rang, caches }))
  })
}

/** Passe visuelle n° 7 — dans la Semaine (`cascade`), les colonnes sont étroites : deux blocs qui se chevauchent ne se
 *  partagent plus la largeur (le premier, réduit à une pilule, perdait son titre) ; le second se pose en cascade sur
 *  le premier, décalé de 10 % (maquette agenda-semaine.html `.ag-semcol .bloc.g2`). Le Jour garde les deux moitiés. */
function position(ev, debutGrille, finGrille, cascade = false) {
  const debut = Math.max(ev.debut, debutGrille * 60)
  const fin = Math.min(ev.fin, finGrille * 60)
  const style = {
    top: `calc(var(--tch-heure-h) * ${(debut - debutGrille * 60) / 60} + 1px)`,
    height: `calc(var(--tch-heure-h) * ${Math.max(fin - debut, 15) / 60} - 2px)`,
  }
  if (ev.voies >= 2 && cascade) {
    if (ev.voie > 0) style.left = '10%'
  } else if (ev.voies >= 2) {
    if (ev.voie === 0) style.right = 'calc(50% + 1px)'
    else style.left = 'calc(50% + 1px)'
  }
  return style
}

/** Classes de hauteur et de cascade d'un bloc : `court` (≤ 30 min), `h1` (≤ 1 h), `g2` (second d'un chevauchement). */
const classesBloc = (ev, cascade) => [
  ev.fin - ev.debut <= COURT ? 'court' : (ev.fin - ev.debut <= 60 ? 'h1' : ''),
  cascade && ev.voies >= 2 && ev.voie > 0 ? 'g2' : '',
]

function BlocTache({ ev, style, cascade, choisi, onCocher, onOuvrir }) {
  const { item } = ev
  const fait = item.statut === 'fait'
  const plage = ev.sansDuree
    ? `${heure(item.heure_debut)} · durée non estimée`
    : `${enHeure(ev.debut)} – ${enHeure(ev.fin)}`
  const classes = ['bloc', ...classesBloc(ev, cascade), fait ? 'fait-bloc' : '', choisi ? 'choisi' : '']
    .filter(Boolean).join(' ')
  return (
    <div className={classes} data-p={item.projet?.couleur || undefined} style={style} data-bloc={item.id}>
      <button
        type="button"
        className="ag-bc"
        role="checkbox"
        aria-checked={fait}
        aria-label={`Fait : ${item.titre}`}
        onClick={() => onCocher?.(item)}
      >
        <Check aria-hidden="true" />
      </button>
      <button type="button" className="ag-bt" onClick={() => onOuvrir?.(item)}>
        <b>{item.titre}</b>
        <small className="chiffres">{plage}</small>
      </button>
      {item.essentielle ? <Star className="i i-14 etoile" role="img" aria-label="Essentielle" /> : null}
      {ev.voie === VOIES_VISIBLES - 1 && ev.caches > 0 ? <span className="ag-plus chiffres">+{ev.caches}</span> : null}
    </div>
  )
}

function BlocExterne({ ev, style, cascade, ouvert, onBasculer }) {
  const { item } = ev
  const plage = `${enHeure(ev.debut)}–${enHeure(ev.fin)}`
  const classes = ['bloc', 'erp', 'ag-externe', ...classesBloc(ev, cascade)].filter(Boolean).join(' ')
  return (
    <>
      <button
        type="button"
        className={classes}
        style={style}
        aria-expanded={ouvert}
        aria-label={`${item.titre} · ${plage} · ${item.agenda}`}
        onClick={onBasculer}
      >
        <b>{item.titre}</b>
        <small className="chiffres">{plage}</small>
        <span className="ag-agenda">{item.agenda}</span>
      </button>
      {ouvert ? (
        <p className="ag-bulle" role="status" style={{ top: style.top }}>
          {`${item.titre} · ${plage} · ${item.agenda} · Ouvrir dans ton agenda d'origine`}
        </p>
      ) : null}
    </>
  )
}

function Creneaux({ jour, debut, fin, pas, plusieurs, placement, onCreneau }) {
  const creneaux = []
  for (let m = debut * 60; m < fin * 60; m += pas) creneaux.push(m)
  const verbe = placement ? 'Placer' : 'Ajouter'
  return creneaux.map((m) => {
    const h = enHeure(m)
    const libelle = `${verbe} à ${h}`
    return (
      <button
        key={m}
        type="button"
        className={placement ? 'ag-creneau-vide cible' : 'ag-creneau-vide'}
        style={{
          top: `calc(var(--tch-heure-h) * ${(m - debut * 60) / 60})`,
          height: `calc(var(--tch-heure-h) * ${pas / 60})`,
        }}
        aria-label={plusieurs ? `${libelle} · ${plusieurs}` : libelle}
        onClick={() => (placement ? placement.onPoser(jour.jour, h) : onCreneau?.(jour.jour, h))}
        onDragOver={placement ? (e) => e.preventDefault() : undefined}
        onDrop={placement ? (e) => { e.preventDefault(); placement.onPoser(jour.jour, h) } : undefined}
      >
        <span>{libelle}</span>
      </button>
    )
  })
}

function Maintenant({ maintenant, debut, fin }) {
  if (!maintenant) return null
  const m = maintenant.getHours() * 60 + maintenant.getMinutes()
  if (m < debut * 60 || m > fin * 60) return null
  return (
    <div className="maintenant" style={{ top: `calc(var(--tch-heure-h) * ${(m - debut * 60) / 60})` }}>
      <span className="maintenant-heure chiffres">{enHeure(m)}</span>
    </div>
  )
}

function Colonne({ jour, nomJour, props }) {
  const { aujourdhui, maintenant, debut, fin, pas, placement, choisi, onCreneau, onCocher, onOuvrir } = props
  const [ouvert, setOuvert] = useState(null)
  const repos = !jour.ouvre || jour.ferie
  return (
    <div
      className={['agenda-grille', 'ag-colonne', props.plusieurs ? 'semaine-col' : '', repos ? 'repos-col' : ''].filter(Boolean).join(' ')}
      style={{ height: `calc(var(--tch-heure-h) * ${fin - debut})` }}
      data-jour={jour.jour}
    >
      <Creneaux
        jour={jour} debut={debut} fin={fin} pas={pas} plusieurs={props.plusieurs ? nomJour : ''}
        placement={placement} onCreneau={onCreneau}
      />
      {disposer(evenements(jour)).filter((ev) => ev.voie < VOIES_VISIBLES).map((ev) => {
        const cascade = Boolean(props.plusieurs)
        const style = position(ev, debut, fin, cascade)
        if (ev.type === 'externe') {
          return (
            <BlocExterne
              key={ev.cle} ev={ev} style={style} cascade={cascade} ouvert={ouvert === ev.cle}
              onBasculer={() => setOuvert((actuel) => (actuel === ev.cle ? null : ev.cle))}
            />
          )
        }
        return (
          <BlocTache key={ev.cle} ev={ev} style={style} cascade={cascade} choisi={choisi === ev.item.id}
            onCocher={onCocher} onOuvrir={onOuvrir} />
        )
      })}
      {jour.jour === aujourdhui ? <Maintenant maintenant={maintenant} debut={debut} fin={fin} /> : null}
    </div>
  )
}

/** « mar. 17 » → « mar. » + chiffre en gras (tête de colonne de la Semaine). */
function TeteJour({ nom }) {
  const [abr, ...reste] = String(nom).split(' ')
  return reste.length ? <>{abr} <b>{reste.join(' ')}</b></> : <b>{abr}</b>
}

/** Passe visuelle n° 36 — colonnes de la Semaine (maquette agenda-semaine.html `.ag-semgrille`) : gouttière des heures
 *  de 68 px, jours travaillés larges, jours non travaillés de 64 px ; la rangée « Toute la journée » suit les mêmes. */
const colonnesSemaine = (jours) => ['68px', ...jours.map((j) => (j.ouvre === false ? '64px' : 'minmax(0, 1fr)'))].join(' ')

/**
 * `jours` : les jours d'`agenda.json` ; `nomsJours` : `{iso: « mar. 17 »}` (tête de la Semaine) ;
 * `placement` : `{ onPoser(jour, 'HH:MM') }` pendant « Placer à une heure » (TCH105), sinon nul ;
 * `ligneJournee` : la rangée « Toute la journée » de la Semaine, posée sous la tête des jours, dans la grille.
 */
export default function GrilleAgenda({
  jours, aujourdhui, maintenant = null, debut = 7, fin = 21, pas = 30, nomsJours = {},
  placement = null, choisi = null, ligneJournee = null, onCreneau, onCocher, onOuvrir,
}) {
  const plusieurs = jours.length > 1
  const heures = []
  for (let h = debut; h < fin; h += 1) heures.push(h)
  const props = { aujourdhui, maintenant, debut, fin, pas, placement, choisi, onCreneau, onCocher, onOuvrir, plusieurs }
  return (
    <div className={plusieurs ? 'semaine grille-agenda chiffres' : 'agenda grille-agenda chiffres'}
      style={plusieurs ? { gridTemplateColumns: colonnesSemaine(jours) } : undefined}>
      {plusieurs ? (
        <div className="semaine-tete">
          <div />
          {jours.map((j) => (
            <div
              key={j.jour}
              className={!j.ouvre || j.ferie ? 'repos' : undefined}
              aria-current={j.jour === aujourdhui ? 'date' : undefined}
            >
              <TeteJour nom={nomsJours[j.jour] ?? j.jour} />
              {j.ferie ? <small className="ag-ferie">Férié</small> : null}
            </div>
          ))}
        </div>
      ) : null}
      {plusieurs ? ligneJournee : null}
      <div className="agenda-heures" aria-hidden="true">
        {heures.map((h) => <div key={h}>{`${deux(h)}:00`}</div>)}
      </div>
      {jours.map((j) => <Colonne key={j.jour} jour={j} nomJour={nomsJours[j.jour] ?? j.jour} props={props} />)}
    </div>
  )
}
