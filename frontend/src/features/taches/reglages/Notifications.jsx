import { useEffect, useState } from 'react'
import { lireReglagesSociete, modifierReglagesSociete, poserPreference } from '../../../api/tachesApi'
import { frenchError } from '../../../lib/frenchError'
import { proposerAnnuler } from '../lib/gestes'
import { heureDite } from '../lib/textes'
import FeuilleACrans from '../ui/FeuilleACrans'

/* ============================================================================
   TCH160 — Réglages → Notifications (heures du Plan du matin, du Message de 15 h, du Bilan du soir,
   Revue de la semaine, Heure limite, titre sur l'écran verrouillé, sollicitations en pause « Réactiver »)
   et, pour un administrateur, le coupe-circuit « Messages et rappels de Tâches dans la société »
   (Réglages → Avancé, `reglages-societe/`).
   Une heure se DIT par `POST preferences/ {cle, valeur}` (« HH:MM » ou « off » ; l'heure limite n'a pas
   de « off ») : la valeur adoptée est celle que le serveur a acceptée. Le titre et « Réactiver »
   passent par `PATCH reglages/` (liste blanche, via `onReglage`). Une erreur s'affiche sous le champ
   fautif. Rien n'est écrit si la valeur n'a pas changé (« enregistrer sans toucher » ne change rien).
   Textes : reference/textes.md §2.14, §2.21. Maquette : reglages-notifications.html.
   Contrats : reglages.json, reglages_societe.json.
   ========================================================================== */

const ETEINT = 'off'
const HEURES = [
  { cle: 'heure_matin', nom: () => 'Plan du matin', defaut: '08:30', type: 'plan_matin' },
  { cle: 'relance_jour', nom: (valeur) => `Message de ${heureDite(valeur)}`, defaut: '15:00', type: 'relance' },
  { cle: 'heure_soir', nom: () => 'Bilan du soir', defaut: '18:00', type: 'bilan_soir' },
]
// la revue : entier 0-6 (lundi = 0, comme `jours_travailles` : lun → dim), « auto » ou « off »
const JOURS_REVUE = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
const AIDE_LIMITE = "Après cette heure, plus aucun message. Un rappel que tu as posé sonne toujours."

const messageDe = (err, champs) => {
  const reponse = err?.response?.data
  for (const champ of champs) {
    const brut = reponse?.[champ]
    if (Array.isArray(brut) && brut.length > 0) return String(brut[0])
  }
  return frenchError(err, 'Réessaie dans un instant.')
}

const valeurRevue = (texte) => (/^\d$/.test(texte) ? Number(texte) : texte)

export function Interrupteur({ nom, allume, onBasculer }) {
  return <button type="button" className="interrupteur" role="switch" aria-checked={allume} aria-label={nom} onClick={onBasculer} />
}

function ChampHeure({ nom, valeur, onValider }) {
  const [brouillon, setBrouillon] = useState(null) // null = pas en cours de saisie : on montre la valeur du serveur
  return (
    <input
      type="time"
      className="es-heure chiffres"
      aria-label={`Heure : ${nom}`}
      value={brouillon ?? valeur}
      onChange={(e) => setBrouillon(e.target.value)}
      onBlur={() => { if (brouillon && brouillon !== valeur) onValider(brouillon); setBrouillon(null) }}
    />
  )
}

function LigneHeure({ ligne, valeur, onDire, erreur }) {
  const allume = valeur !== ETEINT
  const nom = ligne.nom(allume ? valeur : ligne.defaut)
  return (
    <>
      <div className="es-reglage">
        <span className="txt"><b>{nom}</b></span>
        {allume
          ? <ChampHeure nom={nom} valeur={valeur} onValider={(v) => onDire(ligne.cle, v)} />
          : <span className="es-heure eteint">Éteint</span>}
        <Interrupteur nom={nom} allume={allume} onBasculer={() => onDire(ligne.cle, allume ? ETEINT : ligne.defaut)} />
      </div>
      {erreur ? <p className="es-erreur" role="alert">{erreur}</p> : null}
    </>
  )
}

function LigneRevue({ valeur, onDire, erreur }) {
  return (
    <>
      <div className="es-reglage">
        <span className="txt">
          <b>Revue de la semaine</b>
          {valeur === 'auto' ? <small>dernier jour travaillé</small> : null}
        </span>
        <select className="es-champ" aria-label="Revue de la semaine" value={String(valeur)}
          onChange={(e) => onDire('revue_semaine', valeurRevue(e.target.value))}>
          <option value="auto">Auto</option>
          {JOURS_REVUE.map((jour, i) => <option key={jour} value={String(i)}>{jour}</option>)}
          <option value={ETEINT}>Éteinte</option>
        </select>
      </div>
      {erreur ? <p className="es-erreur" role="alert">{erreur}</p> : null}
    </>
  )
}

function Pauses({ pauses, sollicitations, onReactiver }) {
  return pauses.map((pause) => {
    const ligne = HEURES.find((h) => h.type === pause.type)
    const nom = ligne ? ligne.nom(sollicitations[ligne.cle] === ETEINT ? ligne.defaut : sollicitations[ligne.cle]) : pause.type
    return (
      <div key={pause.type} className="es-reglage">
        <span className="txt"><b>{`${nom} : ${pause.ignorees} de suite sans être ouverts`}</b></span>
        <button type="button" className="bouton second" onClick={() => onReactiver(pause.type)}>Réactiver</button>
      </div>
    )
  })
}

export default function Notifications({ reglages, onReglage, erreur = {} }) {
  const [dites, setDites] = useState({})
  const [erreurs, setErreurs] = useState({})
  if (!reglages) return null

  const sollicitations = { ...reglages.sollicitations, ...dites }
  const dire = async (cle, valeur) => {
    setErreurs((anciennes) => ({ ...anciennes, [cle]: '' }))
    try {
      await poserPreference({ cle, valeur })
      setDites((anciennes) => ({ ...anciennes, [cle]: valeur }))
    } catch (err) {
      setErreurs((anciennes) => ({ ...anciennes, [cle]: messageDe(err, ['valeur', 'cle']) }))
    }
  }
  const pauses = reglages.pauses_sollicitations ?? []
  const fenetre = reglages.fenetre_societe

  return (
    <div>
      <div className="es-reglages">
        {HEURES.map((ligne) => (
          <LigneHeure key={ligne.cle} ligne={ligne} valeur={sollicitations[ligne.cle]} onDire={dire} erreur={erreurs[ligne.cle]} />
        ))}
        <LigneRevue valeur={sollicitations.revue_semaine} onDire={dire} erreur={erreurs.revue_semaine} />
        <Pauses pauses={pauses} sollicitations={sollicitations}
          onReactiver={(type) => onReglage('pauses_sollicitations', pauses.filter((p) => p.type !== type))} />
        {erreur.pauses_sollicitations ? <p className="es-erreur" role="alert">{erreur.pauses_sollicitations}</p> : null}
      </div>
      <div className="es-ecart" />
      <div className="es-reglages">
        <div className="es-reglage">
          <span className="txt"><b>Heure limite</b></span>
          <ChampHeure nom="Heure limite" valeur={sollicitations.heure_limite} onValider={(v) => dire('heure_limite', v)} />
        </div>
        {erreurs.heure_limite ? <p className="es-erreur" role="alert">{erreurs.heure_limite}</p> : null}
      </div>
      <p className="es-aide">{AIDE_LIMITE}</p>
      <div className="es-ecart" />
      <div className="es-reglages">
        <div className="es-reglage">
          <span className="txt"><b>Montrer le titre sur l'écran verrouillé</b></span>
          <Interrupteur nom="Montrer le titre sur l'écran verrouillé" allume={Boolean(reglages.titres_notifications)}
            onBasculer={() => onReglage('titres_notifications', !reglages.titres_notifications)} />
        </div>
        {erreur.titres_notifications ? <p className="es-erreur" role="alert">{erreur.titres_notifications}</p> : null}
      </div>
      {fenetre ? (
        <p className="es-note">
          {`Heures de travail de la société : ${fenetre.debut} à ${fenetre.fin}. Hors de ces heures, un message est sauté, jamais envoyé plus tard.`}
        </p>
      ) : null}
    </div>
  )
}

/* ── Coupe-circuit (administrateur seulement, Réglages → Avancé) ─────────────────────────────── */

/** « 17/11 à 10:00 » lu dans le texte ISO du serveur, tel qu'il l'a écrit. */
function depuis(modifieLe) {
  const m = /^\d{4}-(\d{2})-(\d{2})T(\d{2}:\d{2})/.exec(modifieLe ?? '')
  return m ? ` depuis le ${m[2]}/${m[1]} à ${m[3]}` : ''
}

function CoupeCircuitAdmin() {
  const [societe, setSociete] = useState(null)
  const [echec, setEchec] = useState(false)
  const [dialogue, setDialogue] = useState(false)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    let vivant = true
    lireReglagesSociete()
      .then((reponse) => { if (vivant) setSociete(reponse.data) })
      .catch(() => { if (vivant) setEchec(true) })
    return () => { vivant = false }
  }, [])

  const ecrire = async (actif) => {
    setErreur('')
    try {
      const { data } = await modifierReglagesSociete({ balayage_actif: actif })
      setSociete(data)
      return true
    } catch (err) {
      setErreur(messageDe(err, ['balayage_actif', 'detail']))
      return false
    }
  }
  const couper = async () => {
    setDialogue(false)
    if (await ecrire(false)) proposerAnnuler({ message: 'Messages et rappels coupés', onAnnuler: () => modifierReglagesSociete({ balayage_actif: true }).then(({ data }) => setSociete(data)) })
  }

  if (echec) return <p className="es-erreur es-aide" role="alert">Pas à jour</p>
  if (!societe) return null
  const actif = societe.balayage_actif
  return (
    <div>
      {actif ? null : (
        <div className="bandeau" role="status">
          <span className="bandeau-texte">
            <span className="bandeau-titre">{`Messages et rappels de Tâches coupés pour la société${depuis(societe.modifie_le)}.`}</span>
          </span>
          <button type="button" className="bouton lien" onClick={() => ecrire(true)}>Rallumer</button>
        </div>
      )}
      <div className="es-reglages">
        <div className="es-reglage">
          <span className="txt">
            <b>Messages et rappels de Tâches dans la société</b>
            <small>Éteint : plus aucun message ni rappel de Tâches n'est envoyé dans la société, jusqu'à ce que tu le rallumes. Rien d'autre ne change.</small>
          </span>
          <Interrupteur nom="Messages et rappels de Tâches dans la société" allume={actif}
            onBasculer={() => (actif ? setDialogue(true) : ecrire(true))} />
        </div>
        {erreur ? <p className="es-erreur" role="alert">{erreur}</p> : null}
      </div>
      <FeuilleACrans ouverte={dialogue} onFermer={() => setDialogue(false)} titre="Couper tous les messages et rappels de Tâches pour la société ?">
        <p className="es-dialogue-texte">Couper tous les messages et rappels de Tâches pour la société ?</p>
        <div className="es-dialogue-pied">
          <button type="button" className="bouton second" onClick={() => setDialogue(false)}>Fermer</button>
          <button type="button" className="bouton danger" onClick={couper}>Couper</button>
        </div>
      </FeuilleACrans>
    </div>
  )
}

/** Rendu seulement si `estAdmin` (`reglages.json`) : un autre rôle ne frappe même pas la route (403). */
export function CoupeCircuit({ estAdmin }) {
  return estAdmin ? <CoupeCircuitAdmin /> : null
}
