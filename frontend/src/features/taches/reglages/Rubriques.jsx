import { useEffect, useState } from 'react'
import { ChevronRight, Download, Trash2 } from 'lucide-react'
import {
  ajouterAgendaExterne, exporterMesDonnees, listerAgendasExternes, modifierAgendaExterne, rafraichirAgendaExterne,
  retirerAgendaExterne, toutEffacer,
} from '../../../api/tachesApi'
import { frenchError } from '../../../lib/frenchError'
import { jourCourt } from '../lib/textes'
import FeuilleACrans from '../ui/FeuilleACrans'
import { chargerBadgeTaches } from '../useBadgeTaches'

/* ============================================================================
   TCH108 — Réglages (cœur) : la liste des rubriques, « Mes données » (Exporter, Tout effacer
   EFFACER) et « Avancé » (messages sans délai, agendas externes : 3 au plus). Notifications et
   Mon iPhone (F3) et « L'ERP me suggère » (F4, TCH167) ont leur propre composant.
   Textes : textes.md §2.14, §2.20. Maquettes : reglages.html, reglages-donnees*.html.
   Une erreur s'affiche sous le champ fautif ; un geste n'a jamais besoin de relire la liste.
   ========================================================================== */

const RUBRIQUES = [
  ['notifications', 'Notifications', 'Plan du matin, message de 15 h, bilan du soir'],
  ['iphone', 'Mon iPhone', 'Six étapes, à faire une fois'],
  ['vie-privee', 'Vie privée', 'Ce qui part au Copilote, qui peut lire'],
  ['suggestions', "L'ERP me suggère", ''], // le résumé « {k} suggestions sur 4 » vient des réglages lus (`resumes`)
  ['donnees', 'Mes données', 'Télécharger, tout effacer'],
  ['avance', 'Avancé', 'Messages sans délai'],
]
/** Le titre d'une rubrique (« Mes données ») : celui de la sous-page qu'elle ouvre ; '' si inconnue. */
// eslint-disable-next-line react-refresh/only-export-components -- la table des rubriques reste dans ce module
export const titreRubrique = (cle) => RUBRIQUES.find(([c]) => c === cle)?.[1] ?? ''
const CONFIRMATION = 'EFFACER'
const ETATS = {
  '': 'Pas encore lu.',
  pas_https: 'Adresse refusée : elle doit commencer par https:// (ou webcal://).',
  adresse_privee: 'Adresse refusée : elle mène à un serveur privé.',
  injoignable: 'Agenda injoignable pour l\'instant.',
  trop_grande: 'Agenda trop gros pour être lu.',
  delai: 'Agenda trop lent à répondre.',
  illisible: 'Agenda illisible : ce n\'est pas une adresse de calendrier (.ics).',
}
const AIDE_AGENDAS = "Ajoute l'adresse de ton agenda (Microsoft 365, Google, iCloud) : tes rendez-vous s'affichent dans Aujourd'hui et l'Agenda, et leur durée est retirée de ton temps disponible. Ils restent en lecture seule."
const OU_TROUVER = [
  ['Microsoft 365', 'Outlook sur le web → Paramètres → Calendrier → Calendriers partagés → Publier un calendrier → copier le lien ICS.'],
  ['Google', 'Google Agenda sur ordinateur → Paramètres de l\'agenda → Adresse secrète au format iCal.'],
  ['iCloud', 'App Calendrier → Calendriers → ⓘ à côté de l\'agenda → Calendrier public → Partager le lien.'],
]

const messageDe = (err, champ) => {
  const brut = err?.response?.data?.[champ]
  return Array.isArray(brut) && brut.length > 0 ? String(brut[0]) : frenchError(err, 'Réessaie dans un instant.')
}

/** La dernière lecture RÉUSSIE de l'agenda, « jeu. 19 09:05 » (jour et heure lus dans le texte ISO du serveur), ou ''. */
function derniereLecture(agenda) {
  const trouve = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/.exec(agenda.dernier_chargement_le ?? '')
  return trouve ? `${jourCourt(trouve[1])} ${trouve[2]}` : ''
}

/** « À jour à 09:05. » ; sinon l'état dit, suivi de la dernière lecture réussie quand il y en a une
 *  (« Pas encore lu. » seulement s'il n'y en a aucune : jamais une heure inventée). */
function texteEtat(agenda) {
  if (agenda.dernier_etat === 'ok') {
    const heure = /T(\d{2}:\d{2})/.exec(agenda.dernier_chargement_le ?? '')
    return heure ? `À jour à ${heure[1]}.` : 'À jour.'
  }
  const lecture = derniereLecture(agenda)
  const etat = agenda.dernier_etat ? (ETATS[agenda.dernier_etat] ?? '') : ''
  if (!lecture) return etat || ETATS['']
  return `${etat ? `${etat} ` : ''}Dernière lecture réussie : ${lecture}.`
}

export default function ListeRubriques({ courante, onOuvrir, resumes = {} }) {
  return (
    <div className="es-rubriques" role="list">
      {RUBRIQUES.map(([cle, titre, resume]) => (
        <div key={cle} role="listitem">
          <button
            type="button"
            className="es-rubrique"
            aria-current={courante === cle ? 'page' : undefined}
            onClick={() => onOuvrir(cle)}
          >
            <span><b>{titre}</b><span>{resumes[cle] ?? resume}</span></span>
            <ChevronRight className="i i-16" aria-hidden="true" />
          </button>
        </div>
      ))}
    </div>
  )
}

function telecharger(donnees) {
  const lien = document.createElement('a')
  const url = URL.createObjectURL(new Blob([JSON.stringify(donnees, null, 2)], { type: 'application/json' }))
  lien.href = url
  lien.download = `mes-donnees-taches-${String(donnees.exporte_le ?? '').slice(0, 10) || 'export'}.json`
  lien.click()
  URL.revokeObjectURL(url)
}

function DialogueEffacer({ ouvert, onFermer, onEfface }) {
  const [saisie, setSaisie] = useState('')
  const [erreur, setErreur] = useState('')

  const confirmer = async () => {
    if (saisie !== CONFIRMATION) { setErreur('Tape EFFACER pour confirmer.'); return }
    setErreur('')
    try {
      await toutEffacer({ confirmation: saisie })
      // R3-097 — la pastille « À trier » (et celle de l'icône) se relit tout de suite : « À trier 4 » restait après
      // l'effacement, jusqu'à la fin du cache de 60 s
      chargerBadgeTaches({ force: true })
      onEfface()
    } catch (err) { setErreur(messageDe(err, 'confirmation')) }
  }

  return (
    <FeuilleACrans ouverte={ouvert} onFermer={onFermer} titre="Tout effacer ?" cranInitial="85">
      <p className="es-dialogue-texte">
        <b>Tes tâches, projets, réglages et jetons de cette société</b>
        {' sont supprimés définitivement. Ni les journaux du serveur, ni les sauvegardes, ni ton téléphone ne sont touchés. Tape EFFACER pour confirmer.'}
      </p>
      <input
        className="es-champ"
        type="text"
        autoComplete="off"
        aria-label="Confirmation"
        aria-describedby="err-effacer"
        aria-invalid={Boolean(erreur) || undefined}
        value={saisie}
        onChange={(e) => setSaisie(e.target.value)}
      />
      {erreur ? <p id="err-effacer" className="es-erreur" role="alert">{erreur}</p> : null}
      <div className="es-dialogue-pied">
        <button type="button" className="bouton second" onClick={onFermer}>Fermer</button>
        <button type="button" className="bouton danger" onClick={confirmer}>Tout effacer</button>
      </div>
    </FeuilleACrans>
  )
}

export function MesDonnees({ onEfface }) {
  const [dialogue, setDialogue] = useState(false)
  const [erreur, setErreur] = useState('')

  const exporter = async () => {
    setErreur('')
    try { telecharger((await exporterMesDonnees()).data) } catch (err) { setErreur(messageDe(err, 'detail')) }
  }

  return (
    <div>
      {/* R2-130 : une liste groupée de deux rangées (plus deux liens séparés par 150 pt de vide) */}
      <div className="es-groupe-actions">
        <button type="button" className="es-action-ligne" onClick={exporter}>
          {/* R3-098 (M6) — le geste dit ce qu'il fait pour Reda, pas le format du fichier */}
          <Download className="i" aria-hidden="true" />Télécharger mes données
        </button>
        <button type="button" className="es-action-ligne danger" onClick={() => setDialogue(true)}>
          <Trash2 className="i" aria-hidden="true" />Tout effacer
        </button>
      </div>
      {erreur ? <p className="es-erreur es-aide" role="alert">{erreur}</p> : null}
      <DialogueEffacer ouvert={dialogue} onFermer={() => setDialogue(false)} onEfface={onEfface} />
    </div>
  )
}

function LigneAgenda({ agenda, onChange, onRetirer }) {
  const [erreur, setErreur] = useState('')
  const [confirme, setConfirme] = useState(false)

  const agir = async (appel) => {
    setErreur('')
    try { onChange((await appel()).data) } catch (err) { setErreur(messageDe(err, 'detail')) }
  }
  const retirer = async () => {
    try { await retirerAgendaExterne(agenda.id); onRetirer(agenda.id) } catch (err) { setErreur(messageDe(err, 'detail')) }
    setConfirme(false)
  }
  const nom = agenda.libelle || agenda.hote
  const refus = agenda.dernier_etat && agenda.dernier_etat !== 'ok'

  return (
    <li className="es-agenda">
      <div className="es-agenda-ligne">
        <span className="txt"><b>{`${nom} · ${agenda.hote}`}</b></span>
        <button type="button" className="bouton lien" onClick={() => agir(() => rafraichirAgendaExterne(agenda.id))}>Rafraîchir</button>
        <button type="button" className="bouton lien" onClick={() => setConfirme(true)}>Retirer</button>
        <button
          type="button"
          className="interrupteur"
          role="switch"
          aria-checked={agenda.actif}
          aria-label={`Afficher ${nom}`}
          onClick={() => agir(() => modifierAgendaExterne(agenda.id, { actif: !agenda.actif }))}
        />
      </div>
      <p className={`es-agenda-etat${refus ? ' refus' : ''}`}>{texteEtat(agenda)}</p>
      {erreur ? <p className="es-erreur" role="alert">{erreur}</p> : null}
      <FeuilleACrans ouverte={confirme} onFermer={() => setConfirme(false)} titre={`Retirer « ${nom} » ?`}>
        <p className="es-dialogue-texte">{`Retirer «\u00A0${nom}\u00A0» ? Ses rendez-vous disparaissent de Tâches ; ton agenda n'est pas touché.`}</p>
        <div className="es-dialogue-pied">
          <button type="button" className="bouton second" onClick={() => setConfirme(false)}>Fermer</button>
          <button type="button" className="bouton danger" onClick={retirer}>Retirer</button>
        </div>
      </FeuilleACrans>
    </li>
  )
}

function AjoutAgenda({ onAjoute }) {
  const [url, setUrl] = useState('')
  const [libelle, setLibelle] = useState('')
  const [erreur, setErreur] = useState('')
  const [lecture, setLecture] = useState(false)

  // L'ajout LIT l'adresse côté serveur (parfois plusieurs secondes) : un indicateur, et un seul envoi à la fois.
  const ajouter = async () => {
    if (lecture) return
    setErreur('')
    setLecture(true)
    try {
      const { data } = await ajouterAgendaExterne({ url: url.trim(), libelle: libelle.trim() }, { erreurSousLeChamp: true })
      onAjoute(data)
      setUrl('')
      setLibelle('')
    } catch (err) { setErreur(messageDe(err, 'url')) } finally { setLecture(false) }
  }

  return (
    <div className="es-agenda-ajout">
      <input className="es-champ" type="text" inputMode="url" autoComplete="off" aria-label="Adresse de l'agenda (https://… ou webcal://…)"
        placeholder="Adresse de l'agenda (https://… ou webcal://…)" aria-describedby="err-agenda"
        aria-invalid={Boolean(erreur) || undefined} value={url} onChange={(e) => setUrl(e.target.value)} />
      <input className="es-champ" type="text" autoComplete="off" aria-label="Nom (facultatif)" placeholder="Nom (facultatif)"
        value={libelle} onChange={(e) => setLibelle(e.target.value)} />
      {erreur ? <p id="err-agenda" className="es-erreur" role="alert">{erreur}</p> : null}
      {lecture ? <p className="sr-only" role="status">{"Lecture de l'agenda…"}</p> : null}
      <button type="button" className="bouton second" disabled={lecture} aria-busy={lecture || undefined} onClick={ajouter}>
        {lecture ? "Lecture de l'agenda…" : 'Ajouter'}
      </button>
      <p className="es-sous">Cette adresse vaut une clé : l'ERP la garde sans jamais l'afficher en entier.</p>
    </div>
  )
}

export function Agendas() {
  const [agendas, setAgendas] = useState(null)
  const [echec, setEchec] = useState(false)

  useEffect(() => {
    let actif = true
    listerAgendasExternes()
      .then((reponse) => { if (actif) { const { results } = reponse.data; setAgendas(results) } })
      .catch(() => { if (actif) setEchec(true) })
    return () => { actif = false }
  }, [])

  const remplacer = (agenda) => setAgendas((liste) => liste.map((a) => (a.id === agenda.id ? agenda : a)))
  return (
    <section className="section">
      <h2 className="section-titre"><span>Mes agendas</span></h2>
      <p className="es-aide">{AIDE_AGENDAS}</p>
      {echec ? <p className="es-erreur es-aide" role="alert">Pas à jour</p> : null}
      {agendas ? (
        <ul className="es-reglages">
          {agendas.map((agenda) => (
            <LigneAgenda key={agenda.id} agenda={agenda} onChange={remplacer}
              onRetirer={(id) => setAgendas((liste) => liste.filter((a) => a.id !== id))} />
          ))}
        </ul>
      ) : null}
      {agendas ? <AjoutAgenda onAjoute={(agenda) => setAgendas((liste) => [...liste, agenda])} /> : null}
      <p className="es-sous">Les rendez-vous qui se répètent n'apparaissent qu'à leur première date pour l'instant.</p>
      {OU_TROUVER.map(([nom, texte]) => (
        <details key={nom} className="es-sous"><summary>{`Où trouver l'adresse : ${nom}`}</summary><p>{texte}</p></details>
      ))}
    </section>
  )
}

export function Avance({ sansDelai, onSansDelai, erreur = '' }) {
  return (
    <div>
      <div className="es-reglages">
        <div className="es-reglage">
          <span className="txt">
            <b>Messages sans délai</b>
            <small>Le message «&nbsp;Annuler&nbsp;» reste jusqu'à ce que tu le fermes.</small>
          </span>
          <button type="button" className="interrupteur" role="switch" aria-checked={sansDelai}
            aria-label="Messages sans délai" onClick={() => onSansDelai(!sansDelai)} />
        </div>
        {erreur ? <p className="es-erreur" role="alert">{erreur}</p> : null}
      </div>
    </div>
  )
}
