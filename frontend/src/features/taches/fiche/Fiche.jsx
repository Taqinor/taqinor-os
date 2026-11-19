import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Calendar, CalendarClock, Check, ChevronDown, Ellipsis, Flag, Folder, Plus, X,
} from 'lucide-react'

import { frenchError } from '../../../lib/frenchError'
import {
  ajouterPoint, annulerGeste, classerErreur, creerProjet, lireTache, listerTousLesProjets, marquerEssentiel,
  modifierPoint, modifierReglages, modifierTache, planifierTache, repeterRappel, retirerPoint, rouvrirTache, terminerTache,
  trancherTache,
} from '../../../api/tachesApi'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from '../../../ui/DropdownMenu'
import { signalerEcrite } from '../lib/fiche'
import { proposerAnnuler } from '../lib/gestes'
import {
  aujourdhuiIso, ecartJours, echeanceTexte, heure, heureDuConflit, jourCourt, jourNomme,
} from '../lib/textes'
import BandeauConflit from '../ui/BandeauConflit'
import FichePlus from './FichePlus'
import CaseRonde from '../ui/CaseRonde'
import Etoile from '../ui/Etoile'
import FeuilleACrans from '../ui/FeuilleACrans'
import SelecteurProjet from '../ui/SelecteurProjet'
import SelecteurQuand, { ajouterJours, dateComplete } from '../ui/SelecteurQuand'

/* ============================================================================
   TCH84 — Fiche d'une tâche (`?tache=<id>`, ouverte par un clic sur une ligne ou par un rappel).
   Champs visibles : Quand je la fais · Échéance · Projet · Priorité · ★ Essentielle · Notes ·
   Check-list ; pied : Reporter à {jour} · Fait (faite : Rouvrir). Le reste est dans « Plus »
   (TCH85). Source : textes.md « Fiche d'une tâche, Quand, Rappel » ; arbitrage A16-N8.
   Règles tenues ici :
     · chaque champ s'enregistre SEUL (PATCH `{champ, lock_version}`), la réponse remplace la tâche ;
     · une erreur s'affiche SOUS le champ fautif (400) ; rien n'est corrigé d'office ;
     · CONFLIT (409 `conflit_version`, modifiée sur un autre appareil) : la saisie en cours reste à
       l'écran ; « Garder la mienne » la renvoie avec la version de l'autre, « Prendre l'autre »
       adopte la tâche de l'autre SANS vider ce qui est en cours de frappe ;
     · ouverte par un rappel envoyé : « Encore 10 min · Encore 1 h · Demain 9 h » en tête.
   Maquettes : ecran-fiche.html, rappel-ouvert.html, etat-conflit.html.
   ========================================================================== */

const CHAMP_DE_ERREUR = {
  jour_prevu: 'quand', heure_debut: 'quand', moment: 'quand', quelque_jour: 'quand',
  echeance: 'echeance', echeance_heure: 'echeance', titre: 'titre', notes: 'notes', priorite: 'priorite',
  projet_id: 'projet', essentielle: 'essentielle', essentielles: 'essentielle', libelle: 'checklist', etiquettes: 'etiquettes',
}
const PRIORITES = [['Haute', 3], ['Moyenne', 2], ['Basse', 1]] // ordre de textes.md §2.3 / §2.6 : Haute · Moyenne · Basse

/** `{champ: [messages]}` d'un 400 → `{ champDeLaFiche: premier message }` (le reste : `general`). */
const CLES_HORS_CHAMP = new Set(['error', 'code', 'detail'])

/** R2-042 — le message de format de date de l'API (« Date has wrong format. Use … YYYY-MM-DD. ») n'est jamais montré
 *  tel quel : il devient « Date incomplète. ». */
const MESSAGE_FORMAT_DATE = /YYYY|AAAA-MM-JJ|wrong format|format de date/i
const DATE_INCOMPLETE = 'Date incomplète.'

function erreursParChamp(champs) {
  const sortie = {}
  Object.entries(champs ?? {}).forEach(([cle, liste]) => {
    if (CLES_HORS_CHAMP.has(cle)) return // le 400 porte aussi `error` (et `code`) à la racine : jamais un champ
    const message = Array.isArray(liste) && typeof liste[0] === 'string' ? liste[0] : ''
    if (message) sortie[CHAMP_DE_ERREUR[cle] ?? 'general'] = MESSAGE_FORMAT_DATE.test(message) ? DATE_INCOMPLETE : message
  })
  return sortie
}

/** R2-042 — les raccourcis d'échéance, comme ceux de « Quand » : Demain · Vendredi (le prochain, jamais aujourd'hui) ·
 *  Fin de mois ; calculés en UTC à partir du jour de la fiche (jamais décalés par l'heure d'été). */
function raccourcisEcheance(aujourdhui) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(aujourdhui ?? ''))
  if (!m) return []
  const jour = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])))
  const versVendredi = ((5 - jour.getUTCDay() + 7) % 7) || 7
  const finDeMois = new Date(Date.UTC(Number(m[1]), Number(m[2]), 0)).toISOString().split('T')[0]
  return [
    { cle: 'demain', titre: 'Demain', jour: ajouterJours(aujourdhui, 1) },
    { cle: 'vendredi', titre: 'Vendredi', jour: ajouterJours(aujourdhui, versVendredi) },
    { cle: 'mois', titre: 'Fin de mois', jour: finDeMois },
  ]
}

/** R2-042 — l'échéance : raccourcis + un champ date qui n'écrit qu'à la SORTIE (ou Entrée) et seulement une date
 *  entière — le champ rendait « 0002-11-27 » au 1er chiffre de l'année, envoyé au serveur (400, « YYYY-MM-DD »). */
function EditeurEcheance({ echeance, aujourdhui, onPoser, onIncomplete }) {
  const [frappe, setFrappe] = useState(null) // { pour: échéance reçue, valeur tapée }
  const valeur = frappe && frappe.pour === (echeance ?? '') ? frappe.valeur : echeance ?? ''
  const ecrire = () => {
    if (!frappe || frappe.pour !== (echeance ?? '') || frappe.valeur === (echeance ?? '')) return
    if (frappe.valeur && !dateComplete(frappe.valeur)) { onIncomplete(); return } // la frappe reste, à corriger
    setFrappe(null)
    if (!frappe.valeur) return // champ vidé : « Aucune » retire l'échéance, un champ vide ne l'efface pas en silence
    onPoser(frappe.valeur)
  }
  const raccourcis = raccourcisEcheance(aujourdhui)
  return (
    <>
      <div className="quand-tuiles" role="radiogroup" aria-label="Choisir l'échéance">
        {raccourcis.map((r) => (
          <button key={r.cle} type="button" role="radio" className="quand-tuile" aria-checked={echeance === r.jour} onClick={() => onPoser(r.jour)}>
            <b>{r.titre}</b>
            <span className="chiffres">{jourNomme(r.jour, aujourdhui)}</span>
          </button>
        ))}
        {echeance ? (
          <button type="button" role="radio" className="quand-tuile" aria-checked={false} onClick={() => onPoser(null)}>
            <b>Aucune</b>
          </button>
        ) : null}
      </div>
      <label className="champ-etiquette" htmlFor="fiche-echeance">
        <span>Choisir un jour</span>
        <input
          id="fiche-echeance"
          type="date"
          className="champ chiffres"
          aria-label="Échéance"
          value={valeur}
          onChange={(e) => setFrappe({ pour: echeance ?? '', valeur: e.target.value })}
          onBlur={ecrire}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); ecrire() } }}
        />
      </label>
    </>
  )
}

const sansCle = (objet, cle) => Object.fromEntries(Object.entries(objet).filter(([k]) => k !== cle))

const majuscule = (texte) => (texte ? texte.charAt(0).toUpperCase() + texte.slice(1) : texte)

const texteQuand = (t, aujourdhui) => {
  if (t.quelque_jour) return 'En réserve'
  if (!t.jour_prevu) return 'Sans jour'
  const jour = majuscule(t.moment === 'soir' ? 'ce soir' : jourCourt(t.jour_prevu, aujourdhui))
  return t.heure_debut ? `${jour} · ${heure(t.heure_debut)}` : jour
}

/** La puce d'échéance (ecran-fiche.html « échéance mer. 25 ») : le jour nommé dès demain, sinon la phrase de la ligne. */
function texteEcheance(echeance, aujourdhui) {
  if (ecartJours(echeance, aujourdhui) === 1) return `échéance ${jourNomme(echeance, aujourdhui)}`
  return echeanceTexte(echeance, aujourdhui)?.texte ?? ''
}

const PRIORITE_NOMMEE = { 3: 'haute', 2: 'moyenne', 1: 'basse' }

function Erreur({ id, message }) {
  return message ? <p id={id} className="erreur-champ" role="alert">{message}</p> : null
}

/** Une puce de la fiche (ecran-fiche.html) : un toucher ouvre le champ dessous ; le nom du champ (« Quand je la
 *  fais », « Échéance »…) précède la valeur pour le lecteur d'écran ; son erreur est rattachée à la puce. */
function PuceChamp({ nom, valeur, vide = false, ouvert, onBasculer, idErreur, erreur, icone, couleur, children }) {
  return (
    <button
      type="button"
      className={vide ? 'puce vide' : 'puce'}
      data-p={couleur}
      aria-label={`${nom} : ${valeur}`}
      aria-expanded={ouvert}
      aria-describedby={erreur ? idErreur : undefined}
      onClick={onBasculer}
    >
      {icone}
      {children ?? <span className="chiffres">{valeur}</span>}
    </button>
  )
}

function CheckList({ tache, onChange, onErreur }) {
  const [nouveau, setNouveau] = useState('')
  const points = tache.elements_checklist ?? []

  const ajouter = async () => {
    const libelle = nouveau.trim()
    if (!libelle) return
    try {
      const { data } = await ajouterPoint({ tache_id: tache.id, libelle })
      const element = data?.element ?? data
      onChange(element?.id ? [...points, element] : null)
      signalerEcrite()
      setNouveau('')
      onErreur('checklist', '')
    } catch (err) {
      onErreur('checklist', erreursParChamp(classerErreur(err).champs).checklist || frenchError(err))
    }
  }
  const basculer = async (point, fait) => {
    onChange(points.map((p) => (p.id === point.id ? { ...p, fait } : p)))
    try {
      await modifierPoint(point.id, { fait })
      signalerEcrite()
    } catch (err) {
      onChange(points)
      onErreur('checklist', frenchError(err))
      throw err
    }
  }
  const retirer = async (point) => {
    onChange(points.filter((p) => p.id !== point.id))
    try {
      await retirerPoint(point.id)
      signalerEcrite()
    } catch (err) {
      onChange(points)
      onErreur('checklist', frenchError(err))
    }
  }

  return (
    <ul className="points">
      {points.map((point) => (
        <li key={point.id} className={point.fait ? 'point-liste fait' : 'point-liste'}>
          <CaseRonde coche={Boolean(point.fait)} libelle={`${point.fait ? 'Rouvrir' : 'Fait'} : ${point.libelle}`} onBasculer={(suivant) => basculer(point, suivant)} />
          <span className="libelle">{point.libelle}</span>
          <button type="button" className="bouton-icone" aria-label={`Retirer le point : ${point.libelle}`} onClick={() => retirer(point)}>
            <X className="i i-16" aria-hidden="true" />
          </button>
        </li>
      ))}
      <li className="point-liste ajout">
        <Plus className="i i-16" aria-hidden="true" />
        <input
          type="text"
          className="champ-discret"
          aria-label="Ajouter un point"
          placeholder="Ajouter un point"
          value={nouveau}
          onChange={(e) => setNouveau(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); ajouter() } }}
        />
      </li>
    </ul>
  )
}

function RappelOuvert({ rappel, onRepeter }) {
  return (
    <div className="fiche-rappel" role="group" aria-label="Ce rappel vient de sonner">
      <button type="button" className="bouton second" onClick={() => onRepeter(rappel, { dans_minutes: 10 }, 'Rappel dans 10 min')}>Encore 10 min</button>
      <button type="button" className="bouton second" onClick={() => onRepeter(rappel, { dans_minutes: 60 }, 'Rappel dans 1 h')}>Encore 1 h</button>
      <button type="button" className="bouton second" onClick={() => onRepeter(rappel, { jour: ajouterJours(aujourdhuiIso(), 1), heure: '09:00' }, 'Rappel demain à 09:00')}>Demain 9 h</button>
    </div>
  )
}

export default function Fiche({ id, onFermer, aujourdhui = aujourdhuiIso() }) {
  const [tache, setTache] = useState(null)
  const [chargement, setChargement] = useState(true)
  const [echec, setEchec] = useState('')
  const [erreurs, setErreurs] = useState({})
  const [saisie, setSaisie] = useState({})
  const [conflit, setConflit] = useState(null)
  const [avertissements, setAvertissements] = useState([])
  const [ouvert, setOuvert] = useState('')
  const [projets, setProjets] = useState(null)
  const [questionTitres, setQuestionTitres] = useState(false)
  const [plusOuvert, setPlusOuvert] = useState(false)
  const [supprimerDemande, setSupprimerDemande] = useState(0)
  const courant = useRef(id)

  // lecture (et relecture après un « Annuler ») : la réponse n'est gardée que pour la fiche encore ouverte
  const charger = useCallback(() => lireTache(id)
    .then((r) => { if (courant.current === id) { setTache(r.data); setEchec('') } })
    .catch((err) => { if (courant.current === id) setEchec(classerErreur(err).code === 'introuvable' ? 'Introuvable.' : frenchError(err)) })
    .finally(() => { if (courant.current === id) setChargement(false) }), [id])

  useEffect(() => { courant.current = id; charger() }, [id, charger])
  // R2-040 — la fiche fermée (croix, Échap, retour arrière), l'écran se relit une dernière fois
  useEffect(() => () => signalerEcrite(), [])

  const erreur = useCallback((champ, message) => setErreurs((e) => ({ ...e, [champ]: message })), [])

  const appliquer = useCallback((data) => {
    setTache(data?.tache ?? data)
    setAvertissements(data?.avertissements ?? [])
    if (data?.question_titres) setQuestionTitres(true)
    return data?.geste_id ?? null
  }, [])

  /** Un enregistrement : `appel(lock_version)` ; 400 → sous le champ, 409 → bandeau, la saisie reste. */
  const ecrire = useCallback(async (appel, champ, lock, relire = false) => {
    try {
      const { data } = await appel(lock ?? tache.lock_version)
      erreur(champ, '')
      setConflit(null)
      // R2-040 — l'écran sous la fiche (Aujourd'hui, Agenda, Projet…) se relit : la ligne suit ce qu'on vient de faire
      signalerEcrite(data?.tache ?? (data?.id ? data : null))
      if (relire) { await charger(); return { data, geste: data?.geste_id ?? null } }
      return { data, geste: appliquer(data) }
    } catch (err) {
      const classee = classerErreur(err)
      if (classee.code === 'conflit_version') {
        setConflit({ appel, champ, lock: classee.lockVersion, actuel: classee.actuel })
      } else if (classee.code === 'validation') {
        setErreurs((e) => ({ ...e, ...erreursParChamp(classee.champs), [champ]: erreursParChamp(classee.champs)[champ] ?? e[champ] }))
      } else {
        erreur(champ, frenchError(err))
      }
      return null
    }
  }, [tache, erreur, appliquer, charger])

  const annulable = (message, geste) => proposerAnnuler({
    message,
    onAnnuler: geste ? async () => { await annulerGeste(geste); signalerEcrite(); await charger() } : undefined,
  })

  const patcher = (corps, champ) => ecrire((lock) => modifierTache(id, { ...corps, lock_version: lock }), champ)

  const garderLaMienne = async () => {
    const { appel, champ, lock } = conflit
    await ecrire(appel, champ, lock ?? tache.lock_version)
  }
  const prendreLautre = () => {
    if (conflit.actuel) setTache(conflit.actuel)
    setConflit(null)
  }

  const planifier = async (quand) => {
    const r = await ecrire((lock) => planifierTache(id, { ...quand, lock_version: lock }), 'quand')
    if (r) annulable(quand.quelque_jour ? 'En réserve' : `Prévue ${jourCourt(quand.jour_prevu, aujourdhui) || 'sans jour'}`, r.geste)
  }
  const reporter = async (jour) => {
    const r = await ecrire((lock) => planifierTache(id, { jour_prevu: jour, moment: '', heure_debut: null, quelque_jour: false, lock_version: lock }), 'quand')
    if (r) annulable(`Reportée à ${jourNomme(jour, aujourdhui)}`, r.geste)
  }
  const terminer = async () => {
    const r = await ecrire(() => terminerTache(id, {}), 'general')
    if (!r) return
    const suivante = r.data?.suivante?.jour_prevu
    annulable(suivante ? `Faite · prochaine ${jourCourt(suivante, aujourdhui)}` : 'Faite', r.geste)
  }
  const rouvrir = async () => { await ecrire(() => rouvrirTache(id), 'general') }
  // ⋯ de l'en-tête (textes.md §2.4 « Pied » : Abandonner · Supprimer) — les MÊMES gestes que dans « Plus »
  const abandonner = async () => {
    const r = await ecrire(() => trancherTache(id, { choix: 'abandonner' }), 'general', undefined, true)
    if (r) { annulable('Abandonnée', r.data?.geste_id); onFermer?.() }
  }
  const demanderSuppression = () => { setPlusOuvert(true); setSupprimerDemande((n) => n + 1) }
  const basculer = (champ) => setOuvert((o) => (o === champ ? '' : champ))
  const essentielle = async (suivant) => {
    await ecrire(() => marquerEssentiel({ tache_id: id, essentielle: suivant }), 'essentielle')
  }
  const choisirProjet = (projetId) => { setOuvert(''); patcher({ projet_id: projetId }, 'projet') }
  const nouveauProjet = async (nom) => {
    try {
      const { data } = await creerProjet({ nom })
      const cree = data?.projet ?? data // POST projets/ rend `projet_ecrit` : { projet, deplacees, … }
      setProjets((liste) => (liste ? [...liste, cree] : liste))
      choisirProjet(cree.id)
    } catch (err) {
      erreur('projet', erreursParChamp(classerErreur(err).champs).projet || classerErreur(err).champs?.nom?.[0] || frenchError(err))
    }
  }
  const ouvrirProjet = () => {
    setOuvert((o) => (o === 'projet' ? '' : 'projet'))
    if (!projets) listerTousLesProjets().then(setProjets).catch((err) => erreur('projet', frenchError(err)))
  }
  const repeter = async (rappel, corps, message) => {
    try {
      const { data } = await repeterRappel(rappel.id, corps)
      signalerEcrite()
      annulable(message, data?.geste_id)
      await charger()
    } catch (err) {
      erreur('general', frenchError(err))
    }
  }
  const repondreTitres = async (oui) => {
    setQuestionTitres(false)
    try { await modifierReglages({ titres_notifications: oui }) } catch (err) { erreur('general', frenchError(err)) }
  }

  const fait = tache?.statut === 'fait'
  const rappelEnvoye = (tache?.rappels ?? []).find((r) => r.statut === 'envoye')
  const lendemain = ajouterJours(tache?.jour_prevu && tache.jour_prevu >= aujourdhui ? tache.jour_prevu : aujourdhui, 1)
  const titre = saisie.titre ?? tache?.titre ?? ''
  const notes = saisie.notes ?? tache?.notes ?? ''
  const points = tache?.elements_checklist ?? []

  const enregistrerTexte = (champ) => {
    const valeur = saisie[champ]
    if (valeur === undefined || valeur === tache?.[champ]) { setSaisie((s) => sansCle(s, champ)); return }
    patcher({ [champ]: valeur }, champ).then((r) => { if (r) setSaisie((s) => sansCle(s, champ)) })
  }

  return (
    <div data-fiche={id} className="fiche">
      {/* la fiche vit dans l'adresse (`?tache=`) : le retour arrière la ferme déjà, pas d'entrée d'historique en plus */}
      <FeuilleACrans ouverte onFermer={onFermer} titre={tache?.titre ?? "Fiche d'une tâche"} cranInitial="85" historique={false}>
        {chargement && !tache ? <p className="vide-phrase" role="status">Chargement…</p> : null}
        {echec && !tache ? <p className="erreur-champ" role="alert">{echec}</p> : null}
        {tache ? (
          <div className="fiche-corps">
            {conflit ? <BandeauConflit heure={heureDuConflit(conflit.actuel)} onGarder={garderLaMienne} onPrendre={prendreLautre} /> : null}
            {rappelEnvoye ? <RappelOuvert rappel={rappelEnvoye} onRepeter={repeter} /> : null}
            {questionTitres ? (
              <div className="fiche-question" role="group" aria-label="Question sur l'écran verrouillé">
                <p>Montrer le titre sur l'écran verrouillé ?</p>
                <div className="carte-actions">
                  <button type="button" className="bouton second" onClick={() => repondreTitres(true)}>Oui</button>
                  <button type="button" className="bouton second" onClick={() => repondreTitres(false)}>Non</button>
                </div>
                <p className="aide-champ">Sans réponse, l'écran verrouillé n'affiche que des nombres.</p>
              </div>
            ) : null}

            {/* UN seul titre : celui de la fiche, en grand (la barre de la feuille n'en répète aucun, saisie.css) */}
            <input
              type="text"
              className="fiche-titre-champ"
              aria-label="Titre"
              aria-invalid={erreurs.titre ? true : undefined}
              value={titre}
              onChange={(e) => setSaisie((s) => ({ ...s, titre: e.target.value }))}
              onBlur={() => enregistrerTexte('titre')}
              onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur() }}
            />
            <Erreur message={erreurs.titre} />

            {/* Quand je la fais · Échéance · Projet · Priorité : des PUCES (ecran-fiche.html) ; un toucher ouvre le champ dessous */}
            <div className="puces fiche-champs">
              <PuceChamp
                nom="Quand je la fais"
                valeur={texteQuand(tache, aujourdhui)}
                ouvert={ouvert === 'quand'}
                onBasculer={() => basculer('quand')}
                idErreur="fiche-err-quand"
                erreur={erreurs.quand}
                icone={<Calendar className="i i-16" aria-hidden="true" />}
              />
              <PuceChamp
                nom="Échéance"
                valeur={tache.echeance ? texteEcheance(tache.echeance, aujourdhui).replace(/^échéance /, '') : 'aucune'}
                vide={!tache.echeance}
                ouvert={ouvert === 'echeance'}
                onBasculer={() => basculer('echeance')}
                idErreur="fiche-err-echeance"
                erreur={erreurs.echeance}
                icone={<CalendarClock className="i i-16" aria-hidden="true" />}
              >
                <span className="chiffres">{tache.echeance ? texteEcheance(tache.echeance, aujourdhui) : 'Échéance'}</span>
              </PuceChamp>
              <PuceChamp
                nom="Projet"
                valeur={tache.projet ? tache.projet.nom : 'Sans projet'}
                vide={!tache.projet}
                couleur={tache.projet?.couleur}
                ouvert={ouvert === 'projet'}
                onBasculer={ouvrirProjet}
                idErreur="fiche-err-projet"
                erreur={erreurs.projet}
                icone={tache.projet ? <i className="point" aria-hidden="true" /> : <Folder className="i i-16" aria-hidden="true" />}
              >
                <span className="projet-nom">{tache.projet ? tache.projet.nom : 'Sans projet'}</span>
              </PuceChamp>
              <PuceChamp
                nom="Priorité"
                valeur={PRIORITE_NOMMEE[tache.priorite] ?? 'aucune'}
                vide={!PRIORITE_NOMMEE[tache.priorite]}
                ouvert={ouvert === 'priorite'}
                onBasculer={() => basculer('priorite')}
                idErreur="fiche-err-priorite"
                erreur={erreurs.priorite}
                icone={<Flag className="i i-16" aria-hidden="true" />}
              >
                <span>{PRIORITE_NOMMEE[tache.priorite] ? `Priorité ${PRIORITE_NOMMEE[tache.priorite]}` : 'Priorité'}</span>
              </PuceChamp>
            </div>

            {ouvert === 'quand' ? (
              <div className="fiche-editeur">
                <SelecteurQuand
                  valeur={{ jour_prevu: tache.jour_prevu, moment: tache.moment, heure_debut: tache.heure_debut, quelque_jour: tache.quelque_jour }}
                  aujourdhui={aujourdhui}
                  reporterA={lendemain}
                  onChoisir={planifier}
                />
              </div>
            ) : null}
            <Erreur id="fiche-err-quand" message={erreurs.quand} />
            {avertissements.map((a) => <p key={a.code} className="apercu-note">{a.message}</p>)}

            {ouvert === 'echeance' ? (
              <div className="fiche-editeur">
                <EditeurEcheance
                  echeance={tache.echeance}
                  aujourdhui={aujourdhui}
                  onPoser={(jour) => { erreur('echeance', ''); patcher({ echeance: jour }, 'echeance') }}
                  onIncomplete={() => erreur('echeance', DATE_INCOMPLETE)}
                />
              </div>
            ) : null}
            <Erreur id="fiche-err-echeance" message={erreurs.echeance} />

            {ouvert === 'projet' ? (
              <div className="fiche-editeur">
                <SelecteurProjet projets={projets ?? []} valeur={tache.projet?.id ?? null} sansProjet onChoisir={choisirProjet} onNouveau={nouveauProjet} />
              </div>
            ) : null}
            <Erreur id="fiche-err-projet" message={erreurs.projet} />

            {ouvert === 'priorite' ? (
              <div className="fiche-editeur">
                <div className="segmente" role="radiogroup" aria-label="Priorité">
                  {PRIORITES.map(([libelle, niveau]) => (
                    <button
                      key={niveau}
                      type="button"
                      role="radio"
                      aria-checked={tache.priorite === niveau}
                      onClick={() => patcher({ priorite: tache.priorite === niveau ? 0 : niveau }, 'priorite')}
                    >
                      {libelle}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
            <Erreur id="fiche-err-priorite" message={erreurs.priorite} />
            <Erreur message={erreurs.essentielle} />

            <div className="fiche-section">
              <label className="fiche-label" htmlFor="fiche-notes">Notes</label>
              <textarea
                id="fiche-notes"
                className="saisie-champ fiche-notes"
                rows={2}
                aria-invalid={erreurs.notes ? true : undefined}
                value={notes}
                onChange={(e) => setSaisie((s) => ({ ...s, notes: e.target.value }))}
                onBlur={() => enregistrerTexte('notes')}
              />
              <Erreur message={erreurs.notes} />
            </div>

            <div className="fiche-section">
              <p className="fiche-label">
                <span>Check-list</span>
                {points.length > 0 ? <span className="compte chiffres">{`${points.filter((p) => p.fait).length}/${points.length}`}</span> : null}
              </p>
              <CheckList
                tache={tache}
                onChange={(liste) => (liste ? setTache((t) => ({ ...t, elements_checklist: liste })) : charger())}
                onErreur={erreur}
              />
              <Erreur message={erreurs.checklist} />
            </div>

            {/* « Plus » en gras, son indice et son chevron (ecran-fiche.html) ; le nom lu reste « Plus » */}
            <button type="button" className="fiche-plus-bouton" aria-expanded={plusOuvert} onClick={() => setPlusOuvert((v) => !v)}>
              Plus
              <span className="indice" aria-hidden="true">Répéter, durée, étiquettes, en attente de…</span>
              <ChevronDown className="i i-16" aria-hidden="true" />
            </button>
            {plusOuvert ? (
              <FichePlus
                tache={tache}
                aujourdhui={aujourdhui}
                ecrire={ecrire}
                patcher={patcher}
                erreur={erreur}
                erreurs={erreurs}
                annulable={annulable}
                charger={charger}
                onFermer={onFermer}
                supprimerDemande={supprimerDemande}
              />
            ) : null}
            <Erreur message={erreurs.general} />

            {/* ☆ et ⋯ dans l'en-tête de la feuille, à droite (ecran-fiche.html), posés par saisie.css */}
            <div className="fiche-entete-actions">
              <Etoile active={Boolean(tache.essentielle)} onBasculer={essentielle} titre={tache.titre} />
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button type="button" className="bouton-icone" aria-label="Actions">
                    <Ellipsis className="i" aria-hidden="true" />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onSelect={abandonner}>Abandonner</DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem destructive onSelect={demanderSuppression}>Supprimer</DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        ) : null}
        {tache ? (
          <div className="feuille-pied">
            <button type="button" className="bouton second accent" onClick={() => reporter(lendemain)}>
              {`Reporter à ${jourNomme(lendemain, aujourdhui)}`}
            </button>
            <button type="button" className={fait ? 'bouton second large' : 'bouton fait large'} onClick={fait ? rouvrir : terminer}>
              {fait ? null : <Check className="i i-16" aria-hidden="true" />}
              {fait ? 'Rouvrir' : 'Fait'}
            </button>
          </div>
        ) : null}
      </FeuilleACrans>
    </div>
  )
}
