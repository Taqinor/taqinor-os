import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight, MapPin } from 'lucide-react'

import { lireAgenda, rouvrirTache, terminerTache } from '../../api/tachesApi'
import VueMois from '../../features/taches/agenda/VueMois'
import CoquilleTaches, { EVENEMENT_SAISIR } from '../../features/taches/coquille/CoquilleTaches'
import { proposerAnnuler } from '../../features/taches/lib/gestes'
import { ABR_JOURS, ABR_MOIS, aujourdhuiIso, jourLong } from '../../features/taches/lib/textes'
import GrilleAgenda from '../../features/taches/ui/GrilleAgenda'
import LigneTache from '../../features/taches/ui/LigneTache'
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
const versIso = (t) => new Date(t).toISOString().slice(0, 10)
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

function titrePeriode(vue, jour, { du, au }) {
  if (vue === 'jour') return jourLong(jour)
  if (vue === 'mois') return `${MOIS_LONGS[Number(jour.slice(5, 7)) - 1]} ${jour.slice(0, 4)}`
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
    <div className="bande-jours chiffres" role="tablist" aria-label="Jours de la semaine">
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
            aria-label={jourLong(iso)}
            onClick={() => onChoisir(iso)}
          >
            <small>{ABR_JOURS[new Date(versUtc(iso)).getUTCDay()]}</small>
            <b>{Number(iso.slice(8, 10))}</b>
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
  const taches = [...(jour.blocs ?? []), ...(jour.sans_heure ?? []),
    ...(jour.echeances ?? []).filter((t) => !(jour.blocs ?? []).some((b) => b.id === t.id))]
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
            onTerminer={gestes.basculer} onOuvrir={gestes.ouvrir} />
        ))}
      </div>
    </>
  )
}

function VueJour({ jour, dates, parJour, aujourdhui, maintenant, gestes, placement, onChoisir }) {
  return (
    <>
      <BandeJours dates={dates} parJour={parJour} jour={jour.jour} aujourdhui={aujourdhui} onChoisir={onChoisir} />
      <ToutesLaJournee jour={jour} />
      <EtatDuJour jour={jour} />
      {jour.sans_heure?.length ? (
        <section className="section" aria-label="Sans heure">
          <div className="liste" role="list">
            {jour.sans_heure.map((t) => (
              <LigneTache key={`tache:${t.id}`} item={t} aujourdhui={aujourdhui}
                onTerminer={gestes.basculer} onOuvrir={gestes.ouvrir} />
            ))}
          </div>
        </section>
      ) : null}
      <GrilleAgenda
        jours={[jour]} aujourdhui={aujourdhui} maintenant={maintenant} placement={placement}
        onCreneau={gestes.ajouter} onCocher={gestes.cocher} onOuvrir={gestes.ouvrir}
      />
    </>
  )
}

function SemaineListe({ jours, aujourdhui, onChoisir }) {
  return (
    <div className="ag-sem chiffres mobile-seul">
      {jours.map((j) => {
        const taches = [...(j.blocs ?? []), ...(j.sans_heure ?? [])]
        return (
          <button key={j.jour} type="button" className={j.jour === aujourdhui ? 'ag-sj auj' : 'ag-sj'}
            aria-current={j.jour === aujourdhui ? 'date' : undefined} onClick={() => onChoisir(j.jour)}>
            <span className="ag-sj-date">
              <small>{ABR_JOURS[new Date(versUtc(j.jour)).getUTCDay()]}</small>
              <b>{Number(j.jour.slice(8, 10))}</b>
            </span>
            <span className="ag-sj-corps">
              <span className="ag-sj-tete">
                {j.ferie ? 'Férié' : !j.ouvre ? 'Jour non travaillé' : taches.length >= 2 ? `${taches.length} tâches` : `${taches.length} tâche`}
              </span>
              {taches.slice(0, 3).map((t) => (
                <span key={t.id} className={t.statut === 'fait' ? 'ag-sj-l faite' : 'ag-sj-l'}>
                  <span className="h">{t.heure_debut ? t.heure_debut.slice(0, 5) : ''}</span>
                  <i className="point" data-p={t.projet?.couleur || undefined} aria-hidden="true" />
                  <span className="t">{t.titre}</span>
                </span>
              ))}
            </span>
          </button>
        )
      })}
    </div>
  )
}

function VueSemaine({ jours, aujourdhui, maintenant, gestes, placement, onChoisir }) {
  const noms = Object.fromEntries(jours.map((j) => [j.jour, nomCourt(j.jour)]))
  return (
    <>
      <div className="ag-semtj bureau-seul" role="group" aria-label="Toute la journée">
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
      <div className="bureau-seul">
        <GrilleAgenda
          jours={jours} aujourdhui={aujourdhui} maintenant={maintenant} pas={60} nomsJours={noms}
          placement={placement} onCreneau={gestes.ajouter} onCocher={gestes.cocher} onOuvrir={gestes.ouvrir}
        />
      </div>
      <SemaineListe jours={jours} aujourdhui={aujourdhui} onChoisir={onChoisir} />
    </>
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

function BandeauPasAJour({ maj, message, onReessayer }) {
  return (
    <div className="pas-a-jour" role="alert">
      <span>{maj ? `Pas à jour · ${maj}` : 'Pas à jour'}{message ? ` — ${message}` : ''}</span>
      <button type="button" className="bouton discret" onClick={onReessayer}>Réessayer</button>
    </div>
  )
}

// --- Gestes de l'écran ------------------------------------------------------------------------

function useGestes(setDonnees, setParams) {
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

  const ouvrir = useCallback((item) => {
    setParams((actuels) => { const suite = new URLSearchParams(actuels); suite.set('tache', String(item.id)); return suite })
  }, [setParams])

  const ajouter = useCallback((jour, heureDebut) => {
    window.dispatchEvent(new CustomEvent(EVENEMENT_SAISIR, { detail: { jour_prevu: jour, heure_debut: heureDebut } }))
  }, [])

  return { basculer, ouvrir, ajouter, poserStatut }
}

// --- La page ----------------------------------------------------------------------------------

export default function Agenda({ aujourdhui = aujourdhuiIso(), maintenant = null }) {
  const [params, setParams] = useSearchParams()
  const vue = VUES.some(([cle]) => cle === params.get('vue')) ? params.get('vue') : 'jour'
  const jour = estIso(params.get('jour')) ? params.get('jour') : aujourdhui
  const projet = params.get('projet')
  const periode = useMemo(() => periodeDe(vue, jour, aujourdhui), [vue, jour, aujourdhui])
  const [donnees, setDonnees] = useState(null)
  const [echec, setEchec] = useState(null)
  const [maj, setMaj] = useState('')
  const [relire, setRelire] = useState(0)
  const [erreurGeste, setErreurGeste] = useState('')
  const derniere = useRef(0)
  const gestes = useGestes(setDonnees, setParams)
  const horloge = useMemo(() => maintenant ?? new Date(), [maintenant])

  useEffect(() => {
    derniere.current += 1
    const rang = derniere.current
    const requete = { du: periode.du, au: periode.au }
    if (vue === 'semaine') requete.vue = 'semaine'
    if (projet) requete.projet = projet
    lireAgenda(requete).then((reponse) => {
      if (rang !== derniere.current) return
      setDonnees(reponse.data)
      setEchec(null)
      setMaj(heureMaj())
    }).catch((err) => {
      if (rang === derniere.current) setEchec(frenchError(err, "L'agenda n'a pas pu être lu."))
    })
  }, [periode.du, periode.au, vue, projet, relire])

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
    cocher: (item) => {
      setErreurGeste('')
      gestes.basculer(item, item.statut !== 'fait').catch((err) => setErreurGeste(frenchError(err)))
    },
  }
  const choisirJour = (iso) => changer({ vue: 'jour', jour: iso })

  return (
    <CoquilleTaches ecran="agenda" titre="Agenda" sousTitre={jourLong(aujourdhui)}>
      <div className="ag-vues">
        <SegmenteVues vue={vue} onVue={(cle) => changer({ vue: cle })} />
      </div>
      <Navigation
        vue={vue} titre={titrePeriode(vue, jour, periode)}
        onPas={(sens) => changer({ jour: pas(vue, jour, sens) })}
        onAujourdhui={() => changer({ jour: null })}
      />
      {echec ? <BandeauPasAJour maj={maj} message={echec} onReessayer={() => setRelire((n) => n + 1)} /> : null}
      {erreurGeste ? <p className="ag-erreur" role="alert">{erreurGeste}</p> : null}
      {!donnees && !echec ? <p className="ag-chargement" role="status">Chargement</p> : null}
      {vue === 'jour' ? (
        <VueJour jour={parJour[jour] ?? jourVide(jour)} dates={joursEntre(lundiDe(jour), decaler(lundiDe(jour), 6))}
          parJour={parJour} aujourdhui={aujourdhui} maintenant={horloge} gestes={gestesEcran}
          onChoisir={(iso) => changer({ jour: iso })} />
      ) : null}
      {vue === 'semaine' ? (
        <VueSemaine jours={jours} aujourdhui={aujourdhui} maintenant={horloge} gestes={gestesEcran}
          onChoisir={choisirJour} />
      ) : null}
      {vue === 'mois' ? (
        <>
          <VueMois du={periode.du} au={periode.au} mois={jour.slice(0, 7)} jours={donnees?.jours}
            aujourdhui={aujourdhui} jourChoisi={jour} onChoisir={(iso) => changer({ jour: iso })} />
          <section className="ag-av" aria-label={jourLong(jour)}>
            <div className="ag-jour-tete"><b>{jourLong(jour)}</b></div>
            <EtatDuJour jour={parJour[jour] ?? jourVide(jour)} />
            <ListeDuJour jour={parJour[jour] ?? jourVide(jour)} aujourdhui={aujourdhui} gestes={gestesEcran} />
          </section>
        </>
      ) : null}
      {vue === 'a-venir' ? <VueAVenir jours={jours} aujourdhui={aujourdhui} gestes={gestesEcran} /> : null}
    </CoquilleTaches>
  )
}
