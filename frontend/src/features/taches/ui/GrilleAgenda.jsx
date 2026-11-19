import { useLayoutEffect, useRef, useState } from 'react'
import { Check, Star } from 'lucide-react'
import { retenirApercu } from '../lib/fiche'
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

/** R3-120 — Jour ET Semaine : deux blocs qui se chevauchent se rangent côte à côte en deux voies ÉGALES (comme Apple
 *  Calendrier et Notion Calendar) et ne se recouvrent jamais. La cascade décalée de 10 % de la passe visuelle n° 7
 *  recouvrait le titre du premier bloc ; la Semaine garantit désormais des colonnes de jour d'au moins 120 px
 *  (`colonnesSemaine`), assez pour deux voies lisibles. */
function position(ev, debutGrille, finGrille) {
  const debut = Math.max(ev.debut, debutGrille * 60)
  const fin = Math.min(ev.fin, finGrille * 60)
  const style = {
    top: `calc(var(--tch-heure-h) * ${(debut - debutGrille * 60) / 60} + 1px)`,
    height: `calc(var(--tch-heure-h) * ${Math.max(fin - debut, 15) / 60} - 2px)`,
  }
  if (ev.voies >= 2) {
    if (ev.voie === 0) style.right = 'calc(50% + 1px)'
    else style.left = 'calc(50% + 1px)'
  }
  return style
}

/** Classes d'un bloc : `court` (≤ 30 min), `h1` (≤ 1 h), `en-voies` (il partage sa colonne avec un autre bloc). */
const classesBloc = (ev) => [
  ev.fin - ev.debut <= COURT ? 'court' : (ev.fin - ev.debut <= 60 ? 'h1' : ''),
  ev.voies >= 2 ? 'en-voies' : '',
]

function BlocTache({ ev, style, choisi, deplacable = false, onCocher, onOuvrir, onDeplacer }) {
  const { item } = ev
  const fait = item.statut === 'fait'
  const plage = ev.sansDuree
    ? `${heure(item.heure_debut)} · durée non estimée`
    : `${enHeure(ev.debut)} – ${enHeure(ev.fin)}`
  const plus = ev.voie === VOIES_VISIBLES - 1 && ev.caches > 0
  const classes = ['bloc', ...classesBloc(ev), fait ? 'fait-bloc' : '', choisi ? 'choisi' : '',
    item.essentielle ? 'essentielle' : '', plus ? 'a-plus' : '', deplacable ? 'deplacable' : ''].filter(Boolean).join(' ')
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
      {/* R3-132 — en mode « placer » (une tâche est choisie), toucher un bloc déjà posé le DÉPLACE (il devient la tâche choisie) ;
          sinon il ouvre sa fiche. Le nom accessible dit le geste et garde le titre et la plage visibles. */}
      <button type="button" className="ag-bt" aria-label={deplacable ? `Déplacer ${item.titre} · ${plage}` : undefined}
        onClick={() => {
          if (deplacable) { onDeplacer?.(item); return }
          retenirApercu(item) // la fiche s'ouvre à l'instant sur cet aperçu (titre, jour, heure, ★), comme depuis une liste
          onOuvrir?.(item)
        }}>
        <b>{item.titre}</b>
        <small className="chiffres">{plage}</small>
      </button>
      {item.essentielle ? <Star className="i i-14 etoile" role="img" aria-label="Essentielle" /> : null}
      {plus ? <span className="ag-plus chiffres">+{ev.caches}</span> : null}
    </div>
  )
}

/** R2-112 — l'adresse d'un rendez-vous (si l'agenda en sert une) ne devient un lien que si elle est http(s). */
const adresseSure = (url) => (/^https?:\/\//i.test(String(url ?? '')) ? url : null)

function BlocExterne({ ev, style, ouvert, versGauche, onBasculer }) {
  const { item } = ev
  const plage = `${enHeure(ev.debut)}–${enHeure(ev.fin)}`
  const adresse = adresseSure(item.url)
  const classes = ['bloc', 'erp', 'ag-externe', ...classesBloc(ev)].filter(Boolean).join(' ')
  // R3-133 — la bulle s'ouvre sous le bloc ; si elle déborderait du bas de l'écran (rendez-vous de fin de journée), elle se
  // RETOURNE vers le haut (son bas sur le bas du bloc). Mesure du rendu réel, avant la peinture ; la classe est posée sur le
  // nœud (React ne la touche pas : `className` ne change pas).
  const bulle = useRef(null)
  useLayoutEffect(() => {
    const b = bulle.current
    if (!ouvert || !b) return
    b.classList.remove('vers-haut')
    const r = b.getBoundingClientRect()
    if (r.bottom > window.innerHeight - 8 && r.height <= r.top) b.classList.add('vers-haut')
  }, [ouvert])
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
        <p ref={bulle} className={versGauche ? 'ag-bulle vers-gauche' : 'ag-bulle'} role="status" style={{ top: style.top, '--h-bloc': style.height }}>
          {`${item.titre} · ${plage} · ${item.agenda}`}
          {adresse ? (
            <>
              {' · '}
              <a href={adresse} target="_blank" rel="noopener noreferrer">Ouvrir dans ton agenda d&apos;origine</a>
            </>
          ) : null}
        </p>
      ) : null}
    </>
  )
}

/** R2-107 — les heures (en minutes) où un créneau vide est offert : toutes, ou (`libres`) seulement celles qui ne
 *  tombent pas SOUS un bloc ou un rendez-vous (un créneau caché sous un bloc ne se voit ni ne se touche). */
function heuresOffertes(jour, debut, fin, pas, libres) {
  const occupes = libres ? evenements(jour) : []
  const heures = []
  for (let m = debut * 60; m < fin * 60; m += pas) {
    if (!occupes.some((ev) => ev.debut <= m && m < ev.fin)) heures.push(m)
  }
  return heures
}

/** R3-120 — un glisser qui passe sur un créneau le surligne SANS état React (aucun rendu pendant un glisser : le
 *  navigateur annule un glisser dont la page se redessine à son début) ; l'attribut part à la sortie ou au dépôt. */
const survolerCreneau = (e, oui) => {
  if (oui) e.currentTarget.dataset.survol = 'oui'
  else delete e.currentTarget.dataset.survol
}

function Creneaux({ jour, debut, heures, pas, plusieurs, placement, onDepot, arret, onArret, onCreneau }) {
  const verbe = placement ? 'Placer' : 'Ajouter'
  // `onDepot(jour, 'HH:MM')` : la page sait quelle tâche on glisse ; le dépôt marche sans que la tâche soit « choisie »
  const deposer = onDepot ?? placement?.onPoser
  return heures.map((m) => {
    const h = enHeure(m)
    const libelle = `${verbe} à ${h}`
    return (
      <button
        key={m}
        type="button"
        className={placement ? 'ag-creneau-vide cible' : 'ag-creneau-vide'}
        data-m={m}
        tabIndex={arret.jour === jour.jour && arret.m === m ? 0 : -1}
        style={{
          top: `calc(var(--tch-heure-h) * ${(m - debut * 60) / 60})`,
          height: `calc(var(--tch-heure-h) * ${pas / 60})`,
        }}
        aria-label={plusieurs ? `${libelle} · ${plusieurs}` : libelle}
        onFocus={() => onArret({ jour: jour.jour, m })}
        onClick={() => (placement ? placement.onPoser(jour.jour, h) : onCreneau?.(jour.jour, h))}
        onDragOver={deposer ? (e) => e.preventDefault() : undefined}
        onDragEnter={deposer ? (e) => survolerCreneau(e, true) : undefined}
        onDragLeave={deposer ? (e) => survolerCreneau(e, false) : undefined}
        onDrop={deposer ? (e) => { e.preventDefault(); survolerCreneau(e, false); deposer(jour.jour, h) } : undefined}
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

/** R3-131 — dans la Semaine l'heure courante s'écrit UNE fois, dans la gouttière des heures, à la hauteur de la ligne « maintenant »
 *  (comme Apple Calendrier) : posée à gauche de la colonne d'aujourd'hui elle tombait sur la colonne de la veille, par-dessus
 *  un bloc. La Semaine masque donc `.maintenant-heure` (agenda.css) ; le Jour garde la sienne. */
function EtiquetteMaintenant({ maintenant, debut, fin }) {
  const m = maintenant.getHours() * 60 + maintenant.getMinutes()
  if (m < debut * 60 || m > fin * 60) return null
  return (
    <span className="maintenant-gouttiere chiffres" style={{ top: `calc(var(--tch-heure-h) * ${(m - debut * 60) / 60})` }}>{enHeure(m)}</span>
  )
}

function Colonne({ jour, nomJour, props, versGauche = false }) {
  const { aujourdhui, maintenant, debut, fin, pas, placement, onDepot, choisi, onCreneau, onCocher, onOuvrir, onDeplacer } = props
  const heures = props.heuresParJour[jour.jour]
  const [ouvert, setOuvert] = useState(null)
  const repos = !jour.ouvre || jour.ferie
  return (
    <div
      className={['agenda-grille', 'ag-colonne', props.plusieurs ? 'semaine-col' : '', repos ? 'repos-col' : ''].filter(Boolean).join(' ')}
      style={{ height: `calc(var(--tch-heure-h) * ${fin - debut})` }}
      data-jour={jour.jour}
    >
      <Creneaux
        jour={jour} debut={debut} heures={heures} pas={pas} plusieurs={props.plusieurs ? nomJour : ''}
        placement={placement} onDepot={onDepot} arret={props.arret} onArret={props.onArret} onCreneau={onCreneau}
      />
      {disposer(evenements(jour)).filter((ev) => ev.voie < VOIES_VISIBLES).map((ev) => {
        const style = position(ev, debut, fin)
        if (ev.type === 'externe') {
          return (
            <BlocExterne
              key={ev.cle} ev={ev} style={style} ouvert={ouvert === ev.cle} versGauche={versGauche}
              onBasculer={() => setOuvert((actuel) => (actuel === ev.cle ? null : ev.cle))}
            />
          )
        }
        return (
          <BlocTache key={ev.cle} ev={ev} style={style} choisi={choisi === ev.item.id}
            deplacable={Boolean(placement && onDeplacer)} onCocher={onCocher} onOuvrir={onOuvrir} onDeplacer={onDeplacer} />
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

/** R3-121 — l'en-tête d'un jour PASSÉ dit ce qui y a été fait : « {n} faites », le nombre servi (`faites_nb`, la même
 *  somme que Mon rythme) ; jamais deviné, jamais dans une colonne étroite (jour non travaillé vide). */
function faitesDuJour(jour, aujourdhui, etroit) {
  if (etroit || jour.jour >= aujourdhui || !Number.isInteger(jour.faites_nb)) return ''
  return `${jour.faites_nb} ${jour.faites_nb >= 2 ? 'faites' : 'faite'}`
}

/** R3-120 (passe visuelle n° 36 reprise) — colonnes de la Semaine : gouttière des heures de 56 px, chaque jour travaillé
 *  d'AU MOINS 120 px (un titre lisible, deux voies côte à côte), un jour non travaillé étroit (56 px, à demi-part)
 *  seulement s'il est VIDE — un week-end qui porte une tâche, un rendez-vous ou une échéance garde une colonne entière
 *  (R2-108). La rangée « Toute la journée » suit les mêmes colonnes (`subgrid`). */
const jourEtroit = (j) => j.ouvre === false
  && !['blocs', 'sans_heure', 'echeances', 'toute_la_journee', 'externes'].some((cle) => j[cle]?.length)
  && !(j.faites_nb > 0) // R3-125 : un week-end où il a travaillé garde une colonne entière
const colonnesSemaine = (jours) => ['56px', ...jours.map((j) => (jourEtroit(j) ? 'minmax(56px, 0.5fr)' : 'minmax(120px, 1fr)'))].join(' ')

/**
 * `jours` : les jours d'`agenda.json` ; `nomsJours` : `{iso: « mar. 17 »}` (tête de la Semaine) ;
 * `placement` : `{ onPoser(jour, 'HH:MM') }` pendant « Placer à une heure » (TCH105), sinon nul ;
 * `onDepot(jour, 'HH:MM')` : le dépôt d'une tâche glissée depuis « À placer » (R3-120), accepté sans état « placement » ;
 * `ligneJournee` : la rangée « Toute la journée » de la Semaine, posée sous la tête des jours, dans la grille ;
 * `creneauxLibres` : n'offrir aucun créneau sous un bloc ou un rendez-vous (R2-107 ; l'Agenda le demande).
 */
/** R2-107 — au clavier la grille est UN seul arrêt de Tab (créneau d'arrêt, `tabIndex=0`) ; ↑ ↓ passent d'un créneau à
 *  l'autre dans le jour, ← → au même moment du jour voisin, Début / Fin aux bouts. Entrée ou Espace le valident (bouton). */
function surTouche(e) {
  if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return
  const creneau = e.target?.closest?.('.ag-creneau-vide')
  const colonne = creneau?.closest('.ag-colonne')
  if (!colonne) return
  const dans = (col) => [...col.querySelectorAll('.ag-creneau-vide')]
  let suivant = null
  if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(e.key)) {
    const liste = dans(colonne)
    const rang = liste.indexOf(creneau)
    suivant = { ArrowDown: liste[rang + 1], ArrowUp: liste[rang - 1], Home: liste[0], End: liste[liste.length - 1] }[e.key]
  } else if (['ArrowLeft', 'ArrowRight'].includes(e.key)) {
    const colonnes = [...colonne.parentElement.querySelectorAll('.ag-colonne')]
    const voisine = colonnes[colonnes.indexOf(colonne) + (e.key === 'ArrowRight' ? 1 : -1)]
    const m = Number(creneau.dataset.m)
    suivant = voisine ? dans(voisine).reduce((meilleur, c) => (
      !meilleur || Math.abs(Number(c.dataset.m) - m) < Math.abs(Number(meilleur.dataset.m) - m) ? c : meilleur), null) : null
  }
  if (!suivant) return
  e.preventDefault()
  suivant.focus()
}

export default function GrilleAgenda({
  jours, aujourdhui, maintenant = null, debut = 7, fin = 21, pas = 30, nomsJours = {},
  placement = null, onDepot = undefined, choisi = null, ligneJournee = null, creneauxLibres = false, onCreneau, onCocher, onOuvrir,
  onDeplacer = undefined,
}) {
  const plusieurs = jours.length > 1
  const heures = []
  for (let h = debut; h < fin; h += 1) heures.push(h)
  const heuresParJour = Object.fromEntries(jours.map((j) => [j.jour, heuresOffertes(j, debut, fin, pas, creneauxLibres)]))
  // l'arrêt de Tab : le dernier créneau focalisé s'il existe encore, sinon le premier créneau offert
  const [dernier, setDernier] = useState(null)
  const premier = jours.map((j) => ({ jour: j.jour, m: heuresParJour[j.jour][0] })).find((c) => c.m !== undefined) ?? { jour: null, m: null }
  const arret = dernier && heuresParJour[dernier.jour]?.includes(dernier.m) ? dernier : premier
  const props = {
    aujourdhui, maintenant, debut, fin, pas, placement, onDepot, choisi, onCreneau, onCocher, onOuvrir, onDeplacer, plusieurs,
    heuresParJour, arret, onArret: setDernier,
  }
  return (
    <div className={plusieurs ? 'semaine grille-agenda chiffres' : 'agenda grille-agenda chiffres'}
      style={plusieurs ? { gridTemplateColumns: colonnesSemaine(jours) } : undefined} onKeyDown={surTouche}>
      {plusieurs ? (
        <div className="semaine-tete">
          <div />
          {jours.map((j) => {
            const faites = faitesDuJour(j, aujourdhui, jourEtroit(j))
            return (
              <div
                key={j.jour}
                className={!j.ouvre || j.ferie ? 'repos' : undefined}
                aria-current={j.jour === aujourdhui ? 'date' : undefined}
              >
                <TeteJour nom={nomsJours[j.jour] ?? j.jour} />
                {j.ferie ? <small className="ag-ferie">Férié</small> : null}
                {faites ? <small className="ag-faites chiffres">{faites}</small> : null}
              </div>
            )
          })}
        </div>
      ) : null}
      {plusieurs ? ligneJournee : null}
      <div className="agenda-heures" aria-hidden="true">
        {heures.map((h) => <div key={h}>{`${deux(h)}:00`}</div>)}
        {plusieurs && maintenant && jours.some((j) => j.jour === aujourdhui)
          ? <EtiquetteMaintenant maintenant={maintenant} debut={debut} fin={fin} /> : null}
      </div>
      {/* R2-112 — la bulle d'un rendez-vous des colonnes de droite s'ouvre vers la gauche : jamais coupée par l'écran */}
      {jours.map((j, rang) => (
        <Colonne key={j.jour} jour={j} nomJour={nomsJours[j.jour] ?? j.jour} props={props} versGauche={rang >= jours.length / 2} />
      ))}
    </div>
  )
}
