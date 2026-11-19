import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { CalendarCheck, CalendarClock, ChevronLeft, ChevronRight, MapPin, X } from 'lucide-react'

import { annulerGeste, lireAgenda, listerAgendasExternes, modifierTache, planifierTache, rouvrirTache, terminerTache, trancherTache } from '../../api/tachesApi'
import { BandeauPasAJour } from '../../features/taches/aujourdhui/Sections'
import PlanifierSemaine, { resume as resumeJour } from '../../features/taches/agenda/PlanifierSemaine'
import VueMois from '../../features/taches/agenda/VueMois'
import CoquilleTaches, { EVENEMENT_SAISIR } from '../../features/taches/coquille/CoquilleTaches'
import { proposerAnnuler } from '../../features/taches/lib/gestes'
import { annulerEtRecaler } from '../../features/taches/lib/versions'
import {
  ABR_JOURS, ABR_MOIS, aujourdhuiIso, duree as dureeTexte, jourLong, jourNomme,
} from '../../features/taches/lib/textes'
import GrilleAgenda from '../../features/taches/ui/GrilleAgenda'
import LigneTache from '../../features/taches/ui/LigneTache'
import { useActionsLigne } from '../../features/taches/ui/ActionsLigne'
import { useApresCreation, useOuvrirFiche } from '../../features/taches/lib/fiche'
import VoletAPlacer from '../../features/taches/ui/VoletAPlacer'
import ChargementTardif from '../../features/taches/ui/ChargementTardif'
import { frenchError } from '../../lib/frenchError'

/* ============================================================================
   TCH104 — écran Agenda (route /taches/agenda) : vues Jour · Semaine · Mois · À venir,
   « ← Aujourd'hui → », bande « Toute la journée », « Férié », « Jour non travaillé »,
   rendez-vous des agendas externes en LECTURE SEULE, GrilleAgenda (créneau vide = Ajouter).
   Maquettes : agenda-jour.html, agenda-semaine.html, agenda-mois.html, agenda-a-venir.html,
   composants-8.html ; textes.md §2.8. Paramètres d'adresse (api.md §7) : `vue`
   (`jour|semaine|mois|a-venir`), `jour`, `projet`, `placer=1`.

   Lecture : `GET agenda/?du=&au=` (42 jours au plus) ; une lecture en échec ne vide JAMAIS
   l'écran (bandeau « Pas à jour · {HH:MM} » [Réessayer]) ; cocher met à jour la ligne seule
   (optimiste, « Faite · Annuler »), jamais en relisant tout l'agenda.

   TCH105 — vue Jour : volet « À placer » (VoletAPlacer) ; toucher une tâche puis un créneau
   « Placer à {HH:MM} » (ou la glisser dessus) la pose par `taches/{id}/planifier/`, optimiste et
   réconciliée, « Placée à {HH:MM} · Annuler » ; sa durée se règle par pas de 15 min (Maj+↓ /
   Maj+↑) ou 30 min · 1 h · 2 h (`PATCH taches/{id}/`).
   ========================================================================== */

const VUES = [['jour', 'Jour'], ['semaine', 'Semaine'], ['mois', 'Mois'], ['a-venir', 'À venir']]
const JOURS_A_VENIR = 14
const NAV = {
  jour: ['Jour précédent', 'Jour suivant'],
  semaine: ['Semaine précédente', 'Semaine suivante'],
  mois: ['Mois précédent', 'Mois suivant'],
  'a-venir': ['Période précédente', 'Période suivante'],
}
const MOIS_LONGS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre',
  'octobre', 'novembre', 'décembre']
const deux = (n) => String(n).padStart(2, '0')

// --- Dates (ISO `AAAA-MM-JJ`, calcul en UTC : aucune horloge cachée) ---------------------------

const versUtc = (iso) => { const [a, m, j] = iso.split('-').map(Number); return Date.UTC(a, m - 1, j) }
const versIso = (t) => new Date(t).toISOString().split('T')[0]
const decaler = (iso, jours) => versIso(versUtc(iso) + jours * 86400000)
const lundiDe = (iso) => decaler(iso, -((new Date(versUtc(iso)).getUTCDay() + 6) % 7))
const estIso = (texte) => /^\d{4}-\d{2}-\d{2}$/.test(String(texte ?? ''))
const nomCourt = (iso) => `${ABR_JOURS[new Date(versUtc(iso)).getUTCDay()]} ${Number(iso.slice(8, 10))}`

function decalerMois(iso, n) {
  const [a, m] = iso.split('-').map(Number)
  const t = new Date(Date.UTC(a, m - 1 + n, 1))
  return versIso(t.getTime())
}

/** `{du, au}` lus pour la vue autour de `jour` (Mois : les semaines entières du mois, ≤ 42 jours). */
function periodeDe(vue, jour, aujourdhui) {
  if (vue === 'mois') {
    const premier = `${jour.slice(0, 7)}-01`
    const dernier = decaler(decalerMois(premier, 1), -1)
    return { du: lundiDe(premier), au: decaler(lundiDe(dernier), 6) }
  }
  if (vue === 'a-venir') return { du: aujourdhui, au: decaler(aujourdhui, JOURS_A_VENIR - 1) }
  const lundi = lundiDe(jour)
  return { du: lundi, au: decaler(lundi, 6) }
}

function pas(vue, jour, sens) {
  if (vue === 'jour') return decaler(jour, sens)
  if (vue === 'semaine') return decaler(jour, 7 * sens)
  if (vue === 'mois') return decalerMois(jour, sens)
  return decaler(jour, JOURS_A_VENIR * sens)
}

/** R2-103 — la semaine que « Planifier ma semaine » ouvre quand l'adresse ne dit pas de jour : à partir du jeudi 15 h
 *  (et le week-end) on planifie la semaine SUIVANTE — celle qui finit n'a plus rien à planifier — sinon la semaine en cours. */
const HEURE_BASCULE_PLAN = 15
function jourDePlanification(aujourdhui, horloge) {
  const jourSemaine = (new Date(versUtc(aujourdhui)).getUTCDay() + 6) % 7 // lundi = 0
  const heures = horloge instanceof Date ? horloge.getHours() : 0
  const finDeSemaine = jourSemaine >= 4 || (jourSemaine === 3 && heures >= HEURE_BASCULE_PLAN)
  return finDeSemaine ? decaler(lundiDe(aujourdhui), 7) : aujourdhui
}

function titrePeriode(vue, jour, { du, au }) {
  if (vue === 'jour') return jourLong(jour)
  if (vue === 'mois') { // maquette agenda-mois.html : « Novembre 2026 »
    const mois = MOIS_LONGS[Number(jour.slice(5, 7)) - 1]
    return `${mois[0].toUpperCase()}${mois.slice(1)} ${jour.slice(0, 4)}`
  }
  const [md, ma] = [Number(du.slice(5, 7)), Number(au.slice(5, 7))]
  const debut = md === ma ? `${Number(du.slice(8))}` : `${Number(du.slice(8))} ${ABR_MOIS[md - 1]}`
  return `${debut} – ${Number(au.slice(8))} ${MOIS_LONGS[ma - 1]}`
}

const joursEntre = (du, au) => {
  const dates = []
  for (let iso = du; iso <= au; iso = decaler(iso, 1)) dates.push(iso)
  return dates
}

/** Un jour sans ligne servie : ouvré, vide. */
const jourVide = (iso) => ({
  jour: iso, ouvre: true, ferie: false, toute_la_journee: [], sans_heure: [], blocs: [], echeances: [], externes: [],
})

// --- Mise à jour d'UNE ligne dans l'agenda chargé (jamais une relecture) ----------------------

const LISTES_JOUR = ['sans_heure', 'blocs', 'echeances']

function avecItem(donnees, id, changer) {
  if (!donnees) return donnees
  const remplacer = (items) => (items ?? []).map((it) => (it.type === 'tache' && it.id === id ? changer(it) : it))
  return {
    ...donnees,
    jours: (donnees.jours ?? []).map((j) => Object.fromEntries(
      Object.entries(j).map(([cle, val]) => [cle, LISTES_JOUR.includes(cle) ? remplacer(val) : val]))),
    a_placer: remplacer(donnees.a_placer),
    mes_projets: (donnees.mes_projets ?? []).map((g) => ({ ...g, items: remplacer(g.items) })),
  }
}

/** TCH105/TCH106 — la tâche quitte « À placer » (et toute autre place) pour le jour `jour`, à
 * `heureDebut` (bloc) ou sans heure ; le jour absent de l'agenda chargé y est ajouté. */
function deplacerVers(donnees, item, jour, heureDebut) {
  if (!donnees) return donnees
  const posee = { ...item, jour_prevu: jour, heure_debut: heureDebut, quelque_jour: false }
  const sans = (items) => (items ?? []).filter((it) => !(it.type === 'tache' && it.id === item.id))
  const jours = (donnees.jours ?? []).map((j) => ({ ...j, blocs: sans(j.blocs), sans_heure: sans(j.sans_heure) }))
  if (!jours.some((j) => j.jour === jour)) jours.push(jourVide(jour))
  const cible = heureDebut ? 'blocs' : 'sans_heure'
  return {
    ...donnees,
    jours: jours.map((j) => (j.jour === jour ? { ...j, [cible]: [...j[cible], posee] } : j)),
    a_placer: sans(donnees.a_placer),
    mes_projets: (donnees.mes_projets ?? []).map((g) => ({ ...g, items: sans(g.items) })),
  }
}

/** Raccord F2 — la tâche quitte l'agenda chargé (supprimée, ou prévue ailleurs : elle reparaît au relu). */
function sansItem(donnees, id) {
  if (!donnees) return donnees
  const sans = (items) => (items ?? []).filter((it) => !(it.type === 'tache' && it.id === id))
  return {
    ...donnees,
    jours: (donnees.jours ?? []).map((j) => Object.fromEntries(
      Object.entries(j).map(([cle, val]) => [cle, LISTES_JOUR.includes(cle) ? sans(val) : val]))),
    a_placer: sans(donnees.a_placer),
    mes_projets: (donnees.mes_projets ?? []).map((g) => ({ ...g, items: sans(g.items) })),
  }
}

const CHAMPS_ECRITS = ['lock_version', 'jour_prevu', 'heure_debut', 'moment', 'statut', 'estimation_minutes']

/** Réconcilie la ligne avec la TACHE_ECRITE rendue par le serveur (version, jour, heure…). */
const reconcilier = (setDonnees, tache) => {
  if (!tache?.id) return
  setDonnees((d) => avecItem(d, tache.id, (it) => ({
    ...it, ...Object.fromEntries(CHAMPS_ECRITS.filter((c) => c in tache).map((c) => [c, tache[c]])),
  })))
}

function heureMaj(date = new Date()) {
  return `${deux(date.getHours())}:${deux(date.getMinutes())}`
}

// --- Morceaux d'écran -------------------------------------------------------------------------

function SegmenteVues({ vue, onVue }) {
  return (
    <div className="segmente" role="radiogroup" aria-label="Vue">
      {VUES.map(([cle, libelle]) => (
        <button key={cle} type="button" role="radio" aria-checked={vue === cle} onClick={() => onVue(cle)}>
          {libelle}
        </button>
      ))}
    </div>
  )
}

function Navigation({ vue, titre, onPas, onAujourdhui }) {
  const [precedent, suivant] = NAV[vue]
  return (
    <div className="ag-nav">
      <button type="button" className="bouton-icone" aria-label={precedent} onClick={() => onPas(-1)}>
        <ChevronLeft className="i" aria-hidden="true" />
      </button>
      <b className="chiffres">{titre}</b>
      <button type="button" className="bouton discret" onClick={onAujourdhui}>Aujourd&apos;hui</button>
      <button type="button" className="bouton-icone" aria-label={suivant} onClick={() => onPas(1)}>
        <ChevronRight className="i" aria-hidden="true" />
      </button>
    </div>
  )
}

function BandeJours({ dates, parJour, jour, aujourdhui, onChoisir }) {
  return (
    <div className="bande-jours ag-bande-jours chiffres" role="tablist" aria-label="Jours de la semaine">
      {dates.map((iso) => {
        const d = parJour[iso]
        const repos = d && (!d.ouvre || d.ferie)
        const garni = d && (d.blocs?.length || d.sans_heure?.length || d.toute_la_journee?.length || d.externes?.length)
        return (
          <button
            key={iso}
            type="button"
            role="tab"
            className={[repos ? 'repos' : '', garni ? 'marque' : ''].filter(Boolean).join(' ') || undefined}
            aria-selected={iso === jour}
            aria-current={iso === aujourdhui ? 'date' : undefined}
            onClick={() => onChoisir(iso)}
          >
            <small aria-hidden="true">{ABR_JOURS[new Date(versUtc(iso)).getUTCDay()]}</small>
            <b aria-hidden="true">{Number(iso.slice(8, 10))}</b>
            <span className="sr">{jourLong(iso)}</span>
          </button>
        )
      })}
    </div>
  )
}

function PuceJournee({ element }) {
  if (element.url) {
    return (
      <a className="ag-tj-item erp" href={element.url}>
        <MapPin className="i i-16" aria-hidden="true" />
        <span>{element.titre}</span>
      </a>
    )
  }
  return (
    <span className="ag-tj-item erp ag-externe">
      <span>{element.titre}</span>
      <span className="ag-agenda">{element.agenda}</span>
    </span>
  )
}

function ToutesLaJournee({ jour }) {
  const elements = [
    ...(jour.toute_la_journee ?? []).map((e) => ({ ...e, cle: `erp:${e.famille}:${e.id}` })),
    ...(jour.externes ?? []).filter((e) => e.journee_entiere).map((e) => ({ ...e, cle: `ext:${e.cle}` })),
  ]
  const echeances = (jour.echeances ?? []).filter((t) => !(jour.blocs ?? []).some((b) => b.id === t.id))
  if (!elements.length && !echeances.length) return null
  return (
    <div className="ag-tj" role="group" aria-label="Toute la journée">
      <div className="ag-tj-label">Toute la journée</div>
      <div className="ag-tj-items">
        {elements.map((e) => <PuceJournee key={e.cle} element={e} />)}
        {echeances.map((t) => (
          <span key={`ech:${t.id}`} className="ag-tj-item" data-p={t.projet?.couleur || undefined}>
            <i className="point" aria-hidden="true" />
            <span>{`${t.titre} · échéance`}</span>
          </span>
        ))}
      </div>
    </div>
  )
}

function EtatDuJour({ jour }) {
  if (jour.ferie) return <p className="ag-av-vide repos">Férié</p>
  if (!jour.ouvre) return <p className="ag-av-vide repos">Jour non travaillé</p>
  const vide = !['toute_la_journee', 'sans_heure', 'blocs', 'echeances', 'externes'].some((k) => jour[k]?.length)
  return vide ? <p className="ag-av-vide">Rien ce jour-là</p> : null
}

function ListeDuJour({ jour, aujourdhui, gestes }) {
  // R2-101 — le jour d'une échéance, la tâche est la puce « · échéance » de « Toute la journée » : jamais une ligne de plus
  const taches = [...(jour.blocs ?? []), ...(jour.sans_heure ?? [])]
  const vus = new Set()
  const uniques = taches.filter((t) => (vus.has(t.id) ? false : vus.add(t.id)))
  const externes = (jour.externes ?? []).filter((e) => !e.journee_entiere)
  return (
    <>
      <ToutesLaJournee jour={jour} />
      {externes.map((e) => (
        <p key={e.cle} className="ag-externe-ligne chiffres">
          {`${e.debut.slice(11, 16)}–${e.fin.slice(11, 16)} · ${e.titre}`}
          <span className="ag-agenda">{e.agenda}</span>
        </p>
      ))}
      <div className="liste" role="list">
        {uniques.map((t) => (
          <LigneTache key={`tache:${t.id}`} item={t} aujourdhui={aujourdhui}
            onTerminer={gestes.basculer} onOuvrir={gestes.ouvrir} onAction={gestes.action} />
        ))}
      </div>
    </>
  )
}

function VueJour({ jour, dates, parJour, aujourdhui, maintenant, gestes, placement, choisi, volet, consigne = null, onChoisir }) {
  return (
    <div className="ag-corps">
      <div className="ag-principal">
        {consigne}
        <VueJourGrille jour={jour} dates={dates} parJour={parJour} aujourdhui={aujourdhui} maintenant={maintenant}
          gestes={gestes} placement={placement} choisi={choisi} onChoisir={onChoisir} />
      </div>
      {volet}
    </div>
  )
}

function VueJourGrille({ jour, dates, parJour, aujourdhui, maintenant, gestes, placement, choisi, onChoisir }) {
  return (
    <>
      <BandeJours dates={dates} parJour={parJour} jour={jour.jour} aujourdhui={aujourdhui} onChoisir={onChoisir} />
      <ToutesLaJournee jour={jour} />
      <EtatDuJour jour={jour} />
      {jour.sans_heure?.length ? (
        <section className="section ag-sans-heure" aria-label="Sans heure">
          <div className="liste" role="list">
            {jour.sans_heure.map((t) => (
              <LigneTache key={`tache:${t.id}`} item={t} aujourdhui={aujourdhui}
                onTerminer={gestes.basculer} onOuvrir={gestes.ouvrir} onAction={gestes.action} />
            ))}
          </div>
        </section>
      ) : null}
      <GrilleAgenda
        jours={[jour]} aujourdhui={aujourdhui} maintenant={maintenant} placement={placement} choisi={choisi} creneauxLibres
        onCreneau={gestes.ajouter} onCocher={gestes.cocher} onOuvrir={gestes.ouvrir}
      />
    </>
  )
}

/** En-tête d'un jour de la Semaine (iPhone) : un jour ouvert à venir dit sa charge « {n} tâches · {h} pour {cap} »
 *  (textes.md §2.8, maquette agenda-semaine.html) par la même règle que Planifier ma semaine — capacité lue dans
 *  `agenda/` (`capacite.minutes`), jamais devinée ; un jour passé dit ce qui y a été fait, « {n} faites » (maquette
 *  agenda-semaine.html, `ag-sj passe`) ; un jour non travaillé garde son libellé. */
function teteJour(j, aujourdhui, capacite) {
  if (j.ferie) return 'Férié'
  if (!j.ouvre) return 'Jour non travaillé'
  if (j.jour >= aujourdhui) return resumeJour(j, aujourdhui, capacite).texte
  // R2-102 (règle C-12) — « faites » = les tâches FINIES ce jour-là (`faites_nb` servi, comme Mon rythme) ; non servi : « Passé »
  const faites = j.faites_nb
  if (!Number.isInteger(faites)) return 'Passé'
  return `${faites} ${faites >= 2 ? 'faites' : 'faite'}`
}

/** Passe visuelle n° 59 — un jour de la Semaine (iPhone) montre `max` lignes (passé : 1, sinon 3) ; le reste se dit
 *  « +{n} » au bout de la dernière (maquette agenda-semaine.html `.ag-sj-l .plus`, comme le Mois). Passe visuelle n° 8 —
 *  la visite de l'ERP (Toute la journée) ouvre la liste : icône de lieu, sans heure. */
function LignesDuJour({ lignes, max }) {
  const montrees = lignes.slice(0, max)
  const reste = lignes.length - montrees.length
  return montrees.map((t, rang) => {
    const plus = reste > 0 && rang === montrees.length - 1 ? <span className="plus">{`+${reste}`}</span> : null
    if (t.externe) { // R2-100 — un rendez-vous de l'agenda externe : heure + titre, lecture seule
      return (
        <span key={`ext:${t.cle}`} className="ag-sj-l ext">
          <span className="h">{t.heure}</span>
          <CalendarClock className="i i-16" aria-hidden="true" />
          <span className="t">{t.titre}</span>
          {plus}
        </span>
      )
    }
    if (t.erp) {
      return (
        <span key={`erp:${t.famille}:${t.id}`} className="ag-sj-l erp">
          <span className="h" />
          <MapPin className="i i-16" aria-hidden="true" />
          <span className="t">{t.titre}</span>
          {plus}
        </span>
      )
    }
    return (
      <span key={t.id} className={t.statut === 'fait' ? 'ag-sj-l faite' : 'ag-sj-l'}>
        <span className="h">{t.heure_debut ? t.heure_debut.slice(0, 5) : ''}</span>
        <i className="point" data-p={t.projet?.couleur || undefined} aria-hidden="true" />
        <span className="t">{t.titre}</span>
        {plus}
      </span>
    )
  })
}

/** R2-100 — les lignes d'un jour à venir : l'ERP (Toute la journée), les rendez-vous de l'agenda externe (journée
 *  entière d'abord), puis blocs et rendez-vous à l'heure, puis les tâches sans heure. */
function lignesSemaine(j) {
  const externes = j.externes ?? []
  const heureDe = (iso) => String(iso ?? '').slice(11, 16)
  const aLHeure = [
    ...(j.blocs ?? []).map((t) => ({ ...t, heure: t.heure_debut ? t.heure_debut.slice(0, 5) : '' })),
    ...externes.filter((e) => !e.journee_entiere)
      .map((e) => ({ externe: true, cle: e.cle, titre: e.titre, heure: heureDe(e.debut) })),
  ].sort((a, b) => (a.heure < b.heure ? -1 : a.heure > b.heure ? 1 : 0))
  return [
    ...(j.toute_la_journee ?? []).map((e) => ({ ...e, erp: true })),
    ...externes.filter((e) => e.journee_entiere).map((e) => ({ externe: true, cle: e.cle, titre: e.titre, heure: '' })),
    ...aLHeure,
    ...(j.sans_heure ?? []),
  ]
}

function SemaineListe({ jours, aujourdhui, capacite, onChoisir }) {
  return (
    <div className="ag-sem chiffres mobile-seul">
      {jours.map((j) => {
        const taches = [...(j.blocs ?? []), ...(j.sans_heure ?? [])]
        return (
          <button key={j.jour} type="button" className={j.jour === aujourdhui ? 'ag-sj auj' : j.jour < aujourdhui ? 'ag-sj passe' : 'ag-sj'}
            aria-current={j.jour === aujourdhui ? 'date' : undefined} onClick={() => onChoisir(j.jour)}>
            <span className="ag-sj-date">
              <small>{ABR_JOURS[new Date(versUtc(j.jour)).getUTCDay()]}</small>
              <b>{Number(j.jour.slice(8, 10))}</b>
            </span>
            <span className="ag-sj-corps">
              <span className="ag-sj-tete">
                {teteJour(j, aujourdhui, capacite)}
              </span>
              {/* un jour passé dit ce qui y a été fait (« {n} faites ») : ses lignes sont ses faites */}
              {j.jour < aujourdhui
                ? <LignesDuJour lignes={taches.filter((t) => t.statut === 'fait')} max={1} />
                : <LignesDuJour lignes={lignesSemaine(j)} max={3} />}
            </span>
          </button>
        )
      })}
    </div>
  )
}

/** Passe visuelle n° 36 — la rangée « Toute la journée » de la Semaine au bureau : une cellule par jour, posée par
 *  GrilleAgenda sous la tête des jours (mêmes colonnes ; sam./dim. ne décalent plus rien). */
function LigneJourneeSemaine({ jours }) {
  return (
    <div className="ag-semtj" role="group" aria-label="Toute la journée">
      <div className="ag-tj-label">Toute la journée</div>
      {jours.map((j) => (
        <div key={j.jour} className={!j.ouvre || j.ferie ? 'repos-fond' : undefined}>
          {(j.toute_la_journee ?? []).map((e) => <PuceJournee key={`erp:${e.famille}:${e.id}`} element={e} />)}
          {(j.externes ?? []).filter((e) => e.journee_entiere).map((e) => (
            <PuceJournee key={`ext:${e.cle}`} element={e} />
          ))}
        </div>
      ))}
    </div>
  )
}

function VueSemaine({ jours, aujourdhui, maintenant, gestes, placement, capacite = null, volet = null, onChoisir }) {
  const noms = Object.fromEntries(jours.map((j) => [j.jour, nomCourt(j.jour)]))
  return (
    <>
      <div className="ag-corps bureau-seul">
        <div className="ag-principal">
          <GrilleAgenda
            jours={jours} aujourdhui={aujourdhui} maintenant={maintenant} pas={60} nomsJours={noms} creneauxLibres
            ligneJournee={<LigneJourneeSemaine jours={jours} />}
            placement={placement} onCreneau={gestes.ajouter} onCocher={gestes.cocher} onOuvrir={gestes.ouvrir}
          />
        </div>
        {volet}
      </div>
      <SemaineListe jours={jours} aujourdhui={aujourdhui} capacite={capacite} onChoisir={onChoisir} />
    </>
  )
}

/** Passe visuelle n° 34 — pied de la Semaine sur iPhone (maquette agenda-semaine.html `.ag-barre`) : « À placer · {n} »
 *  (le même nombre que le volet, textes.md §2.8) et **Planifier ma semaine**. */
function BarreAPlacer({ total, onPlanifier }) {
  return (
    <div className="ag-barre mobile-seul">
      <div className="ag-barre-titre">À placer <span className="chiffres">{`· ${total}`}</span></div>
      <BoutonPlanifier onClick={onPlanifier} />
    </div>
  )
}

function BoutonPlanifier({ onClick }) {
  return (
    <button type="button" className="bouton second" onClick={onClick}>
      <CalendarCheck className="i i-16" aria-hidden="true" />
      Planifier ma semaine
    </button>
  )
}

/** Passe visuelle n° 58 — Mois : le jour choisi dit sa charge à droite de son titre, par la règle de Planifier ma
 *  semaine (« {n} tâches · {h} pour {cap} », textes.md §2.8 ; maquette agenda-mois.html) ; un jour non travaillé ou
 *  férié n'en dit rien ici (« Jour non travaillé » / « Férié » suivent dessous). */
function TeteJourChoisi({ jour, aujourdhui, capacite }) {
  const r = resumeJour(jour, aujourdhui, capacite)
  return (
    <div className="ag-jour-tete">
      <b>{jourLong(jour.jour)}</b>
      {r.repos ? null : <span className="ag-jour-charge chiffres">{r.texte}</span>}
    </div>
  )
}

function VueAVenir({ jours, aujourdhui, gestes }) {
  return jours.map((j) => (
    <section key={j.jour} className="ag-av" aria-label={jourLong(j.jour)}>
      <h2 className="ag-av-tete">{jourLong(j.jour)}</h2>
      <EtatDuJour jour={j} />
      <ListeDuJour jour={j} aujourdhui={aujourdhui} gestes={gestes} />
    </section>
  ))
}

/** Raccord F2 — aucun agenda externe ajouté : l'invitation de textes.md §2.8 (lue une fois, jamais devinée). */
function InvitationAgendas({ onOuvrir }) {
  return (
    <div className="bandeau" role="region" aria-label="Mes agendas">
      <span className="bandeau-texte">Ajoute ton agenda pour voir tes rendez-vous ici.</span>
      <button type="button" className="bouton discret" onClick={onOuvrir}>Mes agendas</button>
    </div>
  )
}

// --- Gestes de l'écran ------------------------------------------------------------------------

function useGestes(setDonnees) {
  const poserStatut = useCallback((id, statut) => {
    setDonnees((d) => avecItem(d, id, (it) => ({ ...it, statut })))
  }, [setDonnees])

  const basculer = useCallback(async (item, faire = true) => {
    const avant = item.statut
    poserStatut(item.id, faire ? 'fait' : 'a_faire')
    try {
      if (faire) await terminerTache(item.id, {})
      else await rouvrirTache(item.id)
    } catch (err) {
      poserStatut(item.id, avant)
      throw err
    }
    if (faire) {
      proposerAnnuler({
        message: 'Faite', annonce: `Fait : ${item.titre}`,
        onAnnuler: async () => { await rouvrirTache(item.id); poserStatut(item.id, avant) },
      })
    }
  }, [poserStatut])

  const ouvrirFiche = useOuvrirFiche()
  const ouvrir = useCallback((item) => ouvrirFiche(item.id), [ouvrirFiche])

  const ajouter = useCallback((jour, heureDebut) => {
    window.dispatchEvent(new CustomEvent(EVENEMENT_SAISIR, { detail: { jour_prevu: jour, heure_debut: heureDebut } }))
  }, [])

  return { basculer, ouvrir, ajouter, poserStatut }
}

// --- TCH105 — Placer à une heure (et TCH106 : sur un jour) ------------------------------------

const MOTIF_A_TRANCHER = 'reportee_3_fois'
const PAS_DUREE = 15
const DUREE_MIN = 15
const DUREE_MAX = 960
const DUREES_RAPIDES = [30, 60, 120]

function usePlacement(setDonnees, setErreur, aujourdhui) {
  const [choisie, setChoisie] = useState(null)
  const [posee, setPosee] = useState(null)
  const [posees, setPosees] = useState({})
  const annulerPose = useRef(null)

  /** Pose `item` sur `jour` (à `heureDebut`, ou sans heure) : optimiste, réconciliée, annulable.
   *  R2-106 — une tâche « À revoir » (reportée 3 fois) ne sort d'À revoir que par `trancher/` : la poser sur un jour EST
   *  la décision (`choix: 'jour'`), puis, si un créneau est choisi, l'heure par `planifier/`. */
  const poser = useCallback(async (item, jour, heureDebut = null) => {
    let precedent = null
    const aTrancher = item.motif === MOTIF_A_TRANCHER
    const posable = aTrancher ? { ...item, motif: null } : item
    setChoisie(null)
    setErreur('')
    setDonnees((d) => { precedent = d; return deplacerVers(d, posable, jour, heureDebut) })
    const corps = { jour_prevu: jour, heure_debut: heureDebut, moment: '', quelque_jour: false }
    if (item.lock_version != null) corps.lock_version = item.lock_version
    const gestes = []
    let reponse
    try {
      if (aTrancher) {
        reponse = await trancherTache(item.id, { choix: 'jour', jour })
        if (reponse?.data?.geste_id) gestes.push(reponse.data.geste_id)
        if (heureDebut) {
          const version = reponse?.data?.tache?.lock_version
          const suite = { jour_prevu: jour, heure_debut: heureDebut, moment: '', quelque_jour: false }
          if (version != null) suite.lock_version = version
          reponse = await planifierTache(item.id, suite)
          if (reponse?.data?.geste_id) gestes.push(reponse.data.geste_id)
        }
      } else {
        reponse = await planifierTache(item.id, corps)
        if (reponse?.data?.geste_id) gestes.push(reponse.data.geste_id)
      }
    } catch (err) {
      setDonnees(precedent)
      setErreur(frenchError(err, "La tâche n'a pas pu être placée."))
      // la décision déjà prise (R2-106) est défaite : la tâche ne reste pas à moitié placée côté serveur
      if (gestes.length) {
        annulerGeste(gestes[0]).catch((echec) => setErreur(frenchError(echec, "La tâche n'a pas pu être placée, et sa décision n'a pas pu être défaite. Relis l'agenda.")))
      }
      return
    }
    reconcilier(setDonnees, reponse?.data?.tache)
    const placee = { ...posable, ...(reponse?.data?.tache ?? {}), jour_prevu: jour, heure_debut: heureDebut }
    if (heureDebut) setPosee(placee)
    else setPosees((p) => ({ ...p, [jour]: placee }))
    const annuler = async () => {
      // « Annuler » change la version de la tâche côté serveur : la ligne remise garde celle que le serveur rend ;
      // deux gestes (décision + heure) se défont le dernier d'abord
      let retour = null
      for (const geste of [...gestes].reverse()) retour = await annulerEtRecaler(geste, [item.id])
      setDonnees(precedent)
      if (retour?.taches?.[item.id]) reconcilier(setDonnees, retour.taches[item.id])
      setPosee(null)
      setPosees((p) => Object.fromEntries(Object.entries(p).filter(([, t]) => t.id !== item.id)))
    }
    annulerPose.current = annuler
    proposerAnnuler({
      message: heureDebut ? `Placée à ${heureDebut}` : `Placée ${jourNomme(jour, aujourdhui)}`,
      onAnnuler: annuler,
    })
  }, [setDonnees, setErreur, aujourdhui])

  /** Durée de la tâche posée, par pas de 15 min (Maj+↓ / Maj+↑, ou 30 min · 1 h · 2 h). */
  const changerDuree = useCallback(async (minutes) => {
    if (!posee) return
    const valeur = Math.min(DUREE_MAX, Math.max(DUREE_MIN, minutes))
    const avant = posee.estimation_minutes
    setPosee((p) => (p ? { ...p, estimation_minutes: valeur } : p))
    setDonnees((d) => avecItem(d, posee.id, (it) => ({ ...it, estimation_minutes: valeur })))
    try {
      const corps = { estimation_minutes: valeur }
      if (posee.lock_version != null) corps.lock_version = posee.lock_version
      const reponse = await modifierTache(posee.id, corps)
      reconcilier(setDonnees, reponse?.data?.tache)
      const version = reponse?.data?.tache?.lock_version
      if (version != null) setPosee((p) => (p ? { ...p, lock_version: version } : p))
    } catch (err) {
      setPosee((p) => (p ? { ...p, estimation_minutes: avant } : p))
      setDonnees((d) => avecItem(d, posee.id, (it) => ({ ...it, estimation_minutes: avant })))
      setErreur(frenchError(err, "La durée n'a pas pu être changée."))
    }
  }, [posee, setDonnees, setErreur])

  useEffect(() => {
    if (!posee) return undefined
    const surTouche = (e) => {
      if (!e.shiftKey || !['ArrowDown', 'ArrowUp'].includes(e.key)) return
      if (e.target?.closest?.('input, textarea, [contenteditable="true"]')) return
      e.preventDefault()
      const actuelle = posee.estimation_minutes || 30
      changerDuree(actuelle + (e.key === 'ArrowDown' ? PAS_DUREE : -PAS_DUREE))
    }
    window.addEventListener('keydown', surTouche)
    return () => window.removeEventListener('keydown', surTouche)
  }, [posee, changerDuree])

  /** R2-105 — « Déplacer » : la tâche qu'on vient de poser redevient la tâche choisie, un autre créneau la reprend. */
  const deplacer = useCallback(() => {
    if (!posee) return
    setChoisie(posee.id)
    setPosee(null)
  }, [posee])

  const annulerLaPose = useCallback(() => {
    const annuler = annulerPose.current
    annulerPose.current = null
    setPosee(null)
    annuler?.().catch((err) => setErreur(frenchError(err, "L'annulation a échoué. Réessayez.")))
  }, [setErreur])

  return { choisie, setChoisie, posee, setPosee, posees, poser, changerDuree, annulerLaPose, deplacer }
}

function DureePosee({ posee, onDuree, onAnnuler, onDeplacer }) {
  const actuelle = posee.estimation_minutes || 30
  return (
    <div className="ag-duree" role="group" aria-label={`Durée de ${posee.titre}`}>
      <div className="ag-duree-haut">
        <div>
          <b>{`Placée à ${posee.heure_debut}`}</b>
          <small>{posee.titre}</small>
        </div>
        <button type="button" className="bouton lien" onClick={onDeplacer}>Déplacer</button>
        <button type="button" className="bouton lien" onClick={onAnnuler}>Annuler</button>
      </div>
      <div className="segmente" role="radiogroup" aria-label="Durée">
        {DUREES_RAPIDES.map((m) => (
          <button key={m} type="button" role="radio" aria-checked={actuelle === m} onClick={() => onDuree(m)}>
            {dureeTexte(m)}
          </button>
        ))}
      </div>
      <p className="raccourci">
        <span className="chiffres">{dureeTexte(actuelle)}</span>
        <kbd>Maj</kbd>+<kbd>↓</kbd> ajoute 15 min
      </p>
    </div>
  )
}

// --- La page ----------------------------------------------------------------------------------

export default function Agenda({ aujourdhui = aujourdhuiIso(), maintenant = null }) {
  const [params, setParams] = useSearchParams()
  const vue = VUES.some(([cle]) => cle === params.get('vue')) ? params.get('vue') : 'jour'
  const horloge = useMemo(() => maintenant ?? new Date(), [maintenant])
  const planifier = params.get('placer') === '1'
  // R2-103 — Planifier ma semaine, sans jour dans l'adresse : la semaine à planifier (suivante dès le jeudi 15 h)
  const jourDefaut = planifier ? jourDePlanification(aujourdhui, horloge) : aujourdhui
  const jour = estIso(params.get('jour')) ? params.get('jour') : jourDefaut
  const projet = params.get('projet')
  const vueLue = planifier ? 'semaine' : vue
  const periode = useMemo(() => periodeDe(vueLue, jour, aujourdhui), [vueLue, jour, aujourdhui])
  const [donnees, setDonnees] = useState(null)
  const [echec, setEchec] = useState(null)
  const [maj, setMaj] = useState('')
  const [relire, setRelire] = useState(0)
  const [erreurGeste, setErreurGeste] = useState('')
  const derniere = useRef(0)
  const gestes = useGestes(setDonnees)
  const placement = usePlacement(setDonnees, setErreurGeste, aujourdhui)
  const navigate = useNavigate()
  // Mes agendas (§2.20) : vivent dans Réglages → Mon iPhone, étape « calendrier » (`?etape=calendrier`) ; lus une fois
  const [agendas, setAgendas] = useState(null)
  useEffect(() => {
    let vivant = true
    listerAgendasExternes()
      // 3 agendas au plus : seule la question « aucun ? » compte — vide seulement sans ligne ET sans page suivante (`next`)
      .then((r) => {
        const { results, next } = r?.data ?? {}
        if (vivant) setAgendas(Array.isArray(results) ? (results.length === 0 && !next ? [] : results) : null)
      })
      .catch(() => { if (vivant) setAgendas(null) }) // illisible : pas d'invitation plutôt qu'une fausse
    return () => { vivant = false }
  }, [])
  const ouvrirMesAgendas = useCallback(() => navigate('/taches/reglages/iphone?etape=calendrier'), [navigate])
  // Raccord F2 — le gestionnaire commun des actions de ligne (menu ⋯) ; prévue un autre jour, la ligne part
  const actions = useActionsLigne({
    aujourdhui,
    maj: (id, champs) => setDonnees((d) => avecItem(d, id, (it) => ({ ...it, ...champs }))),
    retirer: (item) => {
      let avant = null
      setDonnees((d) => { avant = d; return sansItem(d, item.id) })
      return () => setDonnees((d) => avant ?? d)
    },
    sortApres: (code) => code === 'planifier',
  })
  // une création (saisie, créneau « Ajouter à {HH:MM} », file rejouée) : l'agenda se relit une fois
  useApresCreation(useCallback(() => setRelire((n) => n + 1), []))

  useEffect(() => {
    derniere.current += 1
    const rang = derniere.current
    const requete = { du: periode.du, au: periode.au }
    if (vueLue === 'semaine') requete.vue = 'semaine'
    if (projet) requete.projet = projet
    // parametres-requete: du, au, vue, projet
    lireAgenda(requete).then((reponse) => {
      if (rang !== derniere.current) return
      setDonnees(reponse.data)
      setEchec(null)
      setMaj(heureMaj())
    }).catch(() => {
      if (rang === derniere.current) setEchec(true)
    })
  }, [periode.du, periode.au, vueLue, projet, relire])

  const changer = useCallback((modifs) => {
    setParams((actuels) => {
      const suite = new URLSearchParams(actuels)
      Object.entries(modifs).forEach(([cle, val]) => (val == null ? suite.delete(cle) : suite.set(cle, val)))
      return suite
    }, { replace: true })
  }, [setParams])

  const parJour = useMemo(() => Object.fromEntries((donnees?.jours ?? []).map((j) => [j.jour, j])), [donnees])
  const dates = useMemo(() => joursEntre(periode.du, periode.au), [periode.du, periode.au])
  const jours = dates.map((iso) => parJour[iso] ?? jourVide(iso))
  const gestesEcran = {
    ...gestes,
    action: actions.surAction,
    cocher: (item) => {
      setErreurGeste('')
      gestes.basculer(item, item.statut !== 'fait').catch((err) => setErreurGeste(frenchError(err)))
    },
  }
  // R2-105 — sur iPhone le volet « À placer » est SOUS la grille : une tâche choisie, la vue remonte sur la grille, près de
  // la ligne « maintenant » (sinon en haut de la grille) — jamais de défilement manuel pour trouver où la poser.
  const lu = donnees != null
  useEffect(() => {
    if (placement.choisie == null || vue !== 'jour' || planifier || !lu) return
    if (window.matchMedia?.('(min-width: 1024px)').matches) return // au bureau le volet est à côté de la grille
    const grille = document.querySelector('.tch .grille-agenda')
    const cible = grille?.querySelector('.maintenant') ?? grille
    const reduit = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    cible?.scrollIntoView?.({ block: cible === grille ? 'start' : 'center', behavior: reduit ? 'auto' : 'smooth' })
  }, [placement.choisie, vue, planifier, lu])
  const choisirJour = (iso) => changer({ vue: 'jour', jour: iso })
  const planifierSemaine = () => changer({ placer: '1' })
  const tousAPlacer = [...(donnees?.a_placer ?? []), ...(donnees?.mes_projets ?? []).flatMap((g) => g.items)]
  // R2-105 — la tâche choisie peut aussi être un bloc déjà posé (« Déplacer ») : on la cherche dans les jours aussi
  const dansLeVolet = tousAPlacer.find((it) => it.id === placement.choisie) ?? null
  const choisie = dansLeVolet ?? (placement.choisie == null ? null
    : jours.flatMap((j) => [...(j.blocs ?? []), ...(j.sans_heure ?? [])]).find((it) => it.id === placement.choisie) ?? null)
  const consigneDeplacement = choisie && !dansLeVolet && vue === 'jour' ? (
    <div className="ag-consigne" role="status">
      <span>{`Touche un créneau pour déplacer ${choisie.titre}`}</span>
      <button type="button" className="bouton" aria-label="Annuler le déplacement" onClick={() => placement.setChoisie(null)}>
        <X className="i" aria-hidden="true" />
      </button>
    </div>
  ) : null
  const placementGrille = choisie ? { onPoser: (j, h) => placement.poser(choisie, j, h) } : null
  const volet = (
    <VoletAPlacer
      aPlacer={donnees?.a_placer ?? []} mesProjets={donnees?.mes_projets ?? []} aujourdhui={aujourdhui}
      choisie={placement.choisie} onChoisir={(item) => placement.setChoisie(item ? item.id : null)}
      sansHeure={vue === 'jour' && jour !== aujourdhui ? (parJour[jour]?.sans_heure ?? []) : []}
    />
  )

  // Raccord F2 — l'état « Pas à jour · {HH:MM} » [Réessayer] de la référence (textes.md §2.2, spec-7 « Partout ») :
  // au premier échec, sans heure de mise à jour, il dit « Pas à jour » seul — jamais une phrase de plus.
  const etats = (
    <>
      {echec ? <BandeauPasAJour derniere={maj} onReessayer={() => setRelire((n) => n + 1)} /> : null}
      {erreurGeste ? <p className="ag-erreur" role="alert">{erreurGeste}</p> : null}
      <ChargementTardif actif={!donnees && !echec} />
    </>
  )

  if (planifier) {
    const terminer = () => changer({ placer: null, vue: 'semaine', jour: jour === aujourdhui ? null : jour })
    const changerSemaine = (sens) => changer({ jour: pas('semaine', jour, sens) })
    return (
      // Passe visuelle n° 37 — un MODE (agenda-semaine-planifier.html) : la semaine est dite par le sous-titre, sans
      // navigation qui la répète ni barre « Ajouter une tâche » ; Terminer rejoint la ligne du titre (agenda.css).
      <CoquilleTaches ecran="agenda" titre="Planifier ma semaine" sousTitre={titrePeriode('semaine', jour, periode)}
        saisieBureau={false}>
        {etats}
        {/* Passe visuelle n° 6 — rien de lu : aucun jour ni compte (« 0 tâche », « Tout est placé » seraient faux) */}
        {donnees ? (
          <PlanifierSemaine
            jours={jours} aujourdhui={aujourdhui} capacite={donnees.capacite?.minutes ?? null} aPlacer={donnees.a_placer ?? []}
            mesProjets={donnees.mes_projets ?? []} choisie={choisie} posees={placement.posees}
            onChoisir={(item) => placement.setChoisie(item ? item.id : null)}
            onPoser={(item, iso) => placement.poser(item, iso, null)}
            onOuvrirJour={(iso) => changer({ placer: null, vue: 'jour', jour: iso })}
            onTerminer={terminer} onSemaine={changerSemaine}
          />
        ) : (
          // relecture adverse F4 n° 7 — rien de lu (hors ligne sans cache, erreur) : le mode garde sa sortie, au même endroit
          <div className="ag-planifier">
            <div className="ag-planifier-tete">
              <button type="button" className="bouton plein ag-terminer" onClick={terminer}>Terminer</button>
            </div>
          </div>
        )}
      </CoquilleTaches>
    )
  }

  return (
    <CoquilleTaches ecran="agenda" titre="Agenda" sousTitre={jourLong(aujourdhui)}
      actionsEcran={[{ libelle: 'Planifier ma semaine', onSelect: planifierSemaine },
        { libelle: 'Mes agendas', onSelect: ouvrirMesAgendas }]}
      feuille={actions.feuille} selecteurProjet={actions.selecteurProjet} conflit={actions.conflit}
      contexteSaisie={vue === 'jour' ? { jour_prevu: jour } : null}>
      {/* R2-110 — les vues et la navigation sont UNE barre : une seule ligne au bureau, la grille remonte */}
      <div className="ag-barre-haute">
        <div className="ag-vues">
          <SegmenteVues vue={vue} onVue={(cle) => changer({ vue: cle })} />
        </div>
        <Navigation
          vue={vue} titre={titrePeriode(vue, jour, periode)}
          onPas={(sens) => changer({ jour: pas(vue, jour, sens) })}
          onAujourdhui={() => changer({ jour: null })}
        />
      </div>
      {etats}
      {agendas && agendas.length === 0 && (vue === 'jour' || vue === 'semaine')
        ? <InvitationAgendas onOuvrir={ouvrirMesAgendas} /> : null}
      {/* rien de lu : ni grille vide ni « Rien ce jour-là » (ce serait un constat inventé) */}
      {donnees && vue === 'jour' ? (
        <VueJour jour={parJour[jour] ?? jourVide(jour)} dates={joursEntre(lundiDe(jour), decaler(lundiDe(jour), 6))}
          parJour={parJour} aujourdhui={aujourdhui} maintenant={horloge} gestes={gestesEcran}
          placement={placementGrille} choisi={placement.posee?.id ?? null} volet={volet} consigne={consigneDeplacement}
          onChoisir={(iso) => changer({ jour: iso })} />
      ) : null}
      {donnees && vue === 'jour' && placement.posee ? (
        <DureePosee posee={placement.posee} onDuree={placement.changerDuree} onAnnuler={placement.annulerLaPose}
          onDeplacer={placement.deplacer} />
      ) : null}
      {donnees && vue === 'semaine' ? (
        <>
          <VueSemaine jours={jours} aujourdhui={aujourdhui} maintenant={horloge} gestes={gestesEcran}
            placement={placementGrille} capacite={donnees?.capacite?.minutes ?? null} onChoisir={choisirJour}
            volet={(
              <VoletAPlacer
                aPlacer={donnees.a_placer ?? []} mesProjets={donnees.mes_projets ?? []} aujourdhui={aujourdhui}
                choisie={placement.choisie} onChoisir={(item) => placement.setChoisie(item ? item.id : null)}
                projetsOuverts aide="Touche une tâche, puis un jour." action={<BoutonPlanifier onClick={planifierSemaine} />}
              />
            )} />
          <BarreAPlacer total={tousAPlacer.length} onPlanifier={planifierSemaine} />
        </>
      ) : null}
      {donnees && vue === 'mois' ? (
        <>
          <VueMois du={periode.du} au={periode.au} mois={jour.slice(0, 7)} jours={donnees?.jours}
            aujourdhui={aujourdhui} jourChoisi={jour} onChoisir={(iso) => changer({ jour: iso })} />
          <section className="ag-av" aria-label={jourLong(jour)}>
            <TeteJourChoisi jour={parJour[jour] ?? jourVide(jour)} aujourdhui={aujourdhui}
              capacite={donnees?.capacite?.minutes ?? null} />
            <EtatDuJour jour={parJour[jour] ?? jourVide(jour)} />
            <ListeDuJour jour={parJour[jour] ?? jourVide(jour)} aujourdhui={aujourdhui} gestes={gestesEcran} />
          </section>
        </>
      ) : null}
      {donnees && vue === 'a-venir' ? <VueAVenir jours={jours} aujourdhui={aujourdhui} gestes={gestesEcran} /> : null}
    </CoquilleTaches>
  )
}
