import { useEffect, useRef, useState } from 'react'
import { ArrowRight, CalendarCheck, CalendarClock, Check } from 'lucide-react'
import {
  decalerProjet, dupliquerProjet, enregistrerModele, instancierModele, listerTousLesProjets, renommerModele,
  supprimerModele, supprimerProjet, terminerProjet,
} from '../../../api/tachesApi'
import { frenchError } from '../../../lib/frenchError'
import FeuilleACrans from '../ui/FeuilleACrans'
import { premiereDate } from '../lib/projets'
import { accord, aujourdhuiIso, jourCourt, jourNomme } from '../lib/textes'
import { jourProjet } from './LigneProjet'

/* ============================================================================
   TCH92 — Les trois dialogues d'un projet : Supprimer (« … et ses N tâches ? »), Décaler les dates (aperçu
   AVANT d'écrire, dont « N tâches passeraient avant aujourd'hui »), Terminer (issue, bilan, tâches encore ouvertes).
   Maquettes : projet-supprimer.html, projet-decaler.html, projet-decaler-avant.html, projet-terminer.html.
   Textes : reference/textes.md §2.6 (Décaler, Pause, Terminer, Supprimer). Contrats : `decalage.json`,
   `projet_ecrit.json`. Chaque dialogue est une FeuilleACrans (feuille sur iPhone, dialogue centré au bureau) ;
   il appelle l'API, dit l'erreur SOUS le champ fautif, puis rend la main par `onFait(reponse)`.
   ========================================================================== */

const premiere = (valeur) => (Array.isArray(valeur) ? valeur[0] : valeur)

/** Le lundi qui SUIT `iso` (si `iso` est un lundi : celui de la semaine d'après) — calcul en UTC, aucune horloge cachée. */
// eslint-disable-next-line react-refresh/only-export-components -- calcul pur co-localisé, testé à part (D-ENF22)
export function lundiProchain(iso) {
  const d = new Date(`${iso}T12:00:00Z`)
  d.setUTCDate(d.getUTCDate() + (7 - ((d.getUTCDay() + 6) % 7)))
  return d.toISOString().split('T')[0]
}

function Pied({ onFermer, principal, occupe, danger = false, desactive = false }) {
  return (
    <div className="carte-actions ep-dialogue-pied">
      <button type="button" className="bouton second" onClick={onFermer}>Fermer</button>
      <button
        type="button"
        className={`bouton ${danger ? 'danger' : 'plein'}`}
        disabled={occupe || desactive}
        onClick={principal.onClick}
      >
        {principal.libelle}
      </button>
    </div>
  )
}

function Erreur({ id, texte }) {
  return texte ? <p id={id} className="ep-erreur" role="alert">{texte}</p> : null
}

export function DialogueSupprimer({ projet, onFait, onFermer }) {
  const [occupe, setOccupe] = useState(false)
  const [erreur, setErreur] = useState('')
  const n = (projet.compteurs?.ouvertes ?? 0) + (projet.compteurs?.faites ?? 0)
  const supprimer = async () => {
    setOccupe(true)
    try {
      const { data } = await supprimerProjet(projet.id)
      onFait?.(data)
    } catch (err) {
      setErreur(frenchError(err, 'Le projet n\'a pas été supprimé. Réessaie.'))
    } finally {
      setOccupe(false)
    }
  }
  return (
    <FeuilleACrans ouverte onFermer={onFermer} titre="Supprimer le projet">
      <div className="ep-formulaire" data-p={projet.couleur}>
        <p className="ep-dialogue-texte">{`Supprimer « ${projet.nom} » et ses ${accord(n, 'tâche')} ?`}</p>
        <p className="ep-dialogue-sous">Ils restent 30 jours dans Supprimées récemment.</p>
        <Erreur id="ep-supprimer-erreur" texte={erreur} />
        <Pied onFermer={onFermer} principal={{ libelle: 'Supprimer', onClick: supprimer }} occupe={occupe} danger />
      </div>
    </FeuilleACrans>
  )
}

/* R2-061 — Couleur et échéance d'un projet, sans repasser par la planification. Les dix couleurs sont celles du
   serveur (`choix.Couleur`) ; un choix écrit tout de suite et ferme la feuille. */
// eslint-disable-next-line react-refresh/only-export-components -- table des couleurs, co-localisée avec sa feuille (D-ENF22)
export const COULEURS = [
  ['terre', 'Terre'], ['ambre', 'Ambre'], ['olive', 'Olive'], ['vert', 'Vert'], ['menthe', 'Menthe'],
  ['ciel', 'Ciel'], ['bleu', 'Bleu'], ['indigo', 'Indigo'], ['prune', 'Prune'], ['rose', 'Rose'],
]

export function DialogueRenommerProjet({ projet, onEnregistrer, onFermer }) {
  const [nom, setNom] = useState(projet.nom)
  const [erreur, setErreur] = useState('')
  const [occupe, setOccupe] = useState(false)
  const enregistrer = async () => {
    if (nom.trim() === projet.nom) { onFermer(); return }
    setOccupe(true)
    setErreur('')
    try {
      await onEnregistrer(nom.trim())
    } catch (err) {
      const champs = err?.response?.status === 400 ? err.response.data : null
      setErreur(premiere(champs?.nom) ?? frenchError(err, 'Le projet n\'a pas été renommé. Réessaie.'))
      setOccupe(false)
    }
  }
  return (
    <FeuilleACrans ouverte onFermer={onFermer} titre="Renommer">
      <form className="ep-formulaire" data-p={projet.couleur} noValidate onSubmit={(e) => { e.preventDefault(); enregistrer() }}>
        <div className="ep-groupe">
          <label className="ep-etiquette" htmlFor="ep-renommer-projet">Nom du projet</label>
          <input id="ep-renommer-projet" className="champ" type="text" value={nom} maxLength={120} autoFocus
            onChange={(e) => setNom(e.target.value)} onFocus={(e) => e.target.select()}
            aria-invalid={erreur ? 'true' : undefined} aria-describedby={erreur ? 'ep-renommer-projet-erreur' : undefined} />
          <Erreur id="ep-renommer-projet-erreur" texte={erreur} />
        </div>
        <Pied onFermer={onFermer} principal={{ libelle: 'Enregistrer', onClick: enregistrer }} occupe={occupe} desactive={!nom.trim()} />
      </form>
    </FeuilleACrans>
  )
}

export function DialogueCouleur({ projet, onChoisir, onFermer }) {
  return (
    <FeuilleACrans ouverte onFermer={onFermer} titre="Couleur">
      <div className="ep-formulaire">
        <p className="ep-dialogue-sous" data-p={projet.couleur}><i className="point" aria-hidden="true" />{projet.nom}</p>
        <div className="ep-couleurs" role="radiogroup" aria-label="Couleur du projet">
          {COULEURS.map(([code, nom]) => (
            <button key={code} type="button" className="ep-couleur" role="radio" aria-checked={projet.couleur === code}
              aria-label={nom} data-p={code} onClick={() => onChoisir(code)}>
              <i className="point" aria-hidden="true">{projet.couleur === code ? <Check className="i i-14" aria-hidden="true" /> : null}</i>
              <span>{nom}</span>
            </button>
          ))}
        </div>
      </div>
    </FeuilleACrans>
  )
}

export function DialogueEcheance({ projet, aujourdhui = aujourdhuiIso(), onEnregistrer, onFermer }) {
  const [date, setDate] = useState(projet.echeance ?? '')
  const [erreur, setErreur] = useState('')
  const [occupe, setOccupe] = useState(false)
  const enregistrer = async (valeur) => {
    setOccupe(true)
    setErreur('')
    try {
      await onEnregistrer(valeur || null)
    } catch (err) {
      const champs = err?.response?.status === 400 ? err.response.data : null
      setErreur(premiere(champs?.echeance) ?? frenchError(err, "L'échéance n'a pas été changée. Réessaie."))
      setOccupe(false)
    }
  }
  return (
    <FeuilleACrans ouverte onFermer={onFermer} titre="Échéance">
      <form className="ep-formulaire" data-p={projet.couleur} noValidate onSubmit={(e) => { e.preventDefault(); enregistrer(date) }}>
        <p className="ep-dialogue-sous"><i className="point" aria-hidden="true" />{projet.nom}</p>
        <div className="ep-groupe">
          <label className="ep-etiquette" htmlFor="ep-echeance-projet">Échéance du projet</label>
          <input id="ep-echeance-projet" className="champ" type="date" value={date} onChange={(e) => setDate(e.target.value)}
            aria-invalid={erreur ? 'true' : undefined} aria-describedby={erreur ? 'ep-echeance-projet-erreur' : undefined} />
          {date ? <p className="ep-dialogue-sous chiffres">{jourProjet(date, aujourdhui)}</p> : null}
          <Erreur id="ep-echeance-projet-erreur" texte={erreur} />
        </div>
        <div className="carte-actions ep-dialogue-pied">
          {projet.echeance ? <button type="button" className="bouton second" disabled={occupe} onClick={() => enregistrer('')}>Retirer l'échéance</button> : null}
          <button type="submit" className="bouton plein" disabled={occupe || !date || date === projet.echeance}>Enregistrer</button>
        </div>
      </form>
    </FeuilleACrans>
  )
}

/** Un changement du décalage, en une ligne : « Envoyer le devis · mar. 24 → mar. 1 déc. ». */
function nomDuChangement(c, noms) {
  if (c.objet === 'projet') return c.champ === 'echeance' ? 'Échéance du projet' : 'Date de début du projet'
  if (c.objet === 'section') return noms?.sections?.[c.id] ?? 'Étape'
  return c.titre || noms?.taches?.[c.id] || 'Tâche' // `changements[].titre` servi par `decaler/`
}

export function DialogueDecaler({ projet, noms, aujourdhui = aujourdhuiIso(), onFait, onFermer }) {
  const [delta, setDelta] = useState(null)
  const [libre, setLibre] = useState(false)
  const [apercu, setApercu] = useState(null)
  const [erreur, setErreur] = useState('')
  const [occupe, setOccupe] = useState(false)
  const rang = useRef(0)

  const calculer = async (valeur) => {
    setDelta(valeur)
    rang.current += 1
    const mien = rang.current
    setApercu(null)
    setErreur('')
    if (!Number.isInteger(valeur) || valeur === 0) return
    try {
      const { data } = await decalerProjet(projet.id, { delta_jours: valeur, apercu: true }, { erreurSousLeChamp: true })
      if (mien === rang.current) setApercu(data)
    } catch (err) {
      if (mien !== rang.current) return
      // 400 « N tâches passeraient avant aujourd'hui » : le serveur rend aussi l'aperçu ; il s'affiche, Appliquer reste éteint
      const corps = err?.response?.status === 400 ? err.response.data : null
      if (Array.isArray(corps?.changements)) setApercu({ changements: corps.changements, refuse: true })
      setErreur(premiere(corps?.delta_jours) ?? frenchError(err, 'Le décalage n\'a pas pu être calculé. Réessaie.'))
    }
  }

  const appliquer = async () => {
    setOccupe(true)
    try {
      const { data } = await decalerProjet(projet.id, { delta_jours: delta, apercu: false }, { erreurSousLeChamp: true })
      onFait?.(data)
    } catch (err) {
      setErreur(premiere(err?.response?.data?.delta_jours) ?? frenchError(err, 'Les dates n\'ont pas été décalées. Réessaie.'))
    } finally {
      setOccupe(false)
    }
  }

  const n = apercu?.changements?.length ?? 0
  return (
    <FeuilleACrans ouverte onFermer={onFermer} titre="Décaler les dates">
      <div className="ep-formulaire" data-p={projet.couleur}>
        <p className="ep-dialogue-sous"><i className="point" aria-hidden="true" />{projet.nom}</p>
        <div className="puces" role="radiogroup" aria-label="Décaler de">
          <button type="button" className="puce" role="radio" aria-checked={!libre && delta === 7} onClick={() => { setLibre(false); calculer(7) }}>+1 semaine</button>
          <button type="button" className="puce" role="radio" aria-checked={!libre && delta === -7} onClick={() => { setLibre(false); calculer(-7) }}>−1 semaine</button>
          <button type="button" className="puce" role="radio" aria-checked={libre} onClick={() => setLibre(true)}>Choisir</button>
        </div>
        {libre ? (
          <>
            <label className="ep-etiquette" htmlFor="ep-decaler-jours">Nombre de jours (− pour avancer)</label>
            <input
              id="ep-decaler-jours" className="champ" type="number" step="any" inputMode="numeric"
              value={delta ?? ''}
              onChange={(e) => calculer(e.target.value === '' ? null : Math.round(Number(e.target.value)))}
              aria-invalid={erreur ? 'true' : undefined} aria-describedby={erreur ? 'ep-decaler-erreur' : undefined}
            />
          </>
        ) : null}
        <Erreur id="ep-decaler-erreur" texte={erreur} />
        {apercu ? (
          <>
            <p className="ep-resume"><CalendarClock className="i i-16" aria-hidden="true" />{`${accord(n, 'date change', 'dates changent')}.`}</p>
            <ul className="ep-apercu-liste" aria-label="Dates qui changent">
              {apercu.changements.map((c) => (
                <li key={`${c.objet}:${c.id}:${c.champ}`}>
                  <span>{nomDuChangement(c, noms)}</span>
                  <span className="chiffres">
                    {jourCourt(c.avant, aujourdhui)}<ArrowRight className="i i-14" aria-hidden="true" /><b>{jourCourt(c.apres, aujourdhui)}</b>
                  </span>
                </li>
              ))}
            </ul>
          </>
        ) : null}
        <Pied onFermer={onFermer} principal={{ libelle: 'Appliquer', onClick: appliquer }} occupe={occupe} desactive={!apercu || apercu.refuse || n === 0} />
      </div>
    </FeuilleACrans>
  )
}

const OUVERTES = [
  ['boite', 'Les remettre dans À trier'],
  ['annuler', 'Les abandonner'], // `taches_ouvertes` ∈ boite · annuler · deplacer (TerminerSerializer)
  ['deplacer', 'Les déplacer vers…'],
]

export function DialogueTerminer({ projet, onFait, onFermer }) {
  const [issue, setIssue] = useState('')
  const [bilan, setBilan] = useState('')
  const [ouvertes, setOuvertes] = useState('boite')
  const [cible, setCible] = useState('')
  const [choix, setChoix] = useState([])
  const [erreurs, setErreurs] = useState({})
  const [occupe, setOccupe] = useState(false)
  const nbOuvertes = projet.compteurs?.ouvertes ?? 0

  const choisirOuvertes = async (valeur) => {
    setOuvertes(valeur)
    if (valeur !== 'deplacer' || choix.length > 0) return
    try {
      const projets = await listerTousLesProjets({ statut: 'actif' })
      setChoix(projets.filter((p) => p.id !== projet.id))
    } catch (err) {
      setErreurs((e) => ({ ...e, projet_cible_id: frenchError(err, 'La liste des projets n\'a pas pu être lue. Réessaie.') }))
    }
  }

  const terminer = async () => {
    setOccupe(true)
    setErreurs({})
    const corps = { issue, bilan, taches_ouvertes: ouvertes, projet_cible_id: ouvertes === 'deplacer' && cible ? Number(cible) : null }
    try {
      const { data } = await terminerProjet(projet.id, corps, { erreurSousLeChamp: true })
      onFait?.(data)
    } catch (err) {
      const champs = err?.response?.status === 400 ? err.response.data : null
      if (champs && typeof champs === 'object') {
        setErreurs(Object.fromEntries(Object.entries(champs).map(([k, v]) => [k, premiere(v)])))
      } else {
        setErreurs({ general: frenchError(err, 'Le projet n\'a pas été terminé. Réessaie.') })
      }
    } finally {
      setOccupe(false)
    }
  }

  return (
    <FeuilleACrans ouverte onFermer={onFermer} titre="Terminer le projet" cranInitial="85">
      <div className="ep-formulaire" data-p={projet.couleur}>
        <p className="ep-dialogue-sous"><i className="point" aria-hidden="true" />{projet.nom}</p>
        <div className="ep-groupe">
          <div className="ep-etiquette" id="ep-issue-titre">Atteint ou abandonné ?</div>
          <div className="puces" role="radiogroup" aria-labelledby="ep-issue-titre" aria-invalid={erreurs.issue ? 'true' : undefined}>
            <button type="button" className="puce" role="radio" aria-checked={issue === 'atteint'} onClick={() => setIssue('atteint')}>Atteint</button>
            <button type="button" className="puce" role="radio" aria-checked={issue === 'abandonne'} onClick={() => setIssue('abandonne')}>Abandonné</button>
          </div>
          <Erreur id="ep-issue-erreur" texte={erreurs.issue} />
        </div>
        <div className="ep-groupe">
          <label className="ep-etiquette" htmlFor="ep-bilan">Bilan (facultatif)</label>
          <textarea id="ep-bilan" className="champ ep-zone" rows={3} value={bilan} onChange={(e) => setBilan(e.target.value)} />
          <Erreur id="ep-bilan-erreur" texte={erreurs.bilan} />
        </div>
        {nbOuvertes > 0 ? (
          <div className="ep-groupe">
            <div className="ep-etiquette" id="ep-ouvertes-titre">{`Ses ${accord(nbOuvertes, 'tâche')} encore ouvertes :`}</div>
            <div className="ep-choix" role="radiogroup" aria-labelledby="ep-ouvertes-titre">
              {OUVERTES.map(([valeur, libelle]) => (
                <button key={valeur} type="button" className="ep-choix-ligne" role="radio" aria-checked={ouvertes === valeur}
                  onClick={() => choisirOuvertes(valeur)}>{libelle}</button>
              ))}
            </div>
            {ouvertes === 'deplacer' ? (
              <>
                <label className="ep-etiquette" htmlFor="ep-cible">Projet de destination</label>
                <select id="ep-cible" className="champ" value={cible} onChange={(e) => setCible(e.target.value)}
                  aria-invalid={erreurs.projet_cible_id ? 'true' : undefined}>
                  <option value="">Choisir un projet</option>
                  {choix.map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}
                </select>
              </>
            ) : null}
            <Erreur id="ep-cible-erreur" texte={erreurs.projet_cible_id ?? erreurs.taches_ouvertes} />
          </div>
        ) : null}
        <Erreur id="ep-terminer-erreur" texte={erreurs.general} />
        <Pied onFermer={onFermer} principal={{ libelle: 'Terminer', onClick: terminer }} occupe={occupe} />
      </div>
    </FeuilleACrans>
  )
}

/* ============================================================================
   TCH157 — Les modèles de projet : « Enregistrer comme modèle », « Utiliser ce modèle » et « Dupliquer » (même
   dialogue, même moteur serveur), « Renommer » et « Supprimer » un modèle. Maquettes : projets-modeles-enregistrer.html,
   projets-modeles-utiliser.html, projets-modeles.html. Textes : reference/textes.md §2.6 « Modèles » (« Enregistrer comme
   modèle », « Inclure les notes », « Date de lancement », « {n} tâches, première le {jour} », Créer). Contrats :
   `modele.json`, `modele_instancier.json` (l'APERÇU des dates, obligatoire avant d'écrire : `apercu: true` puis `false`),
   `projet_ecrit.json`. Chaque dialogue dit l'erreur SOUS le champ fautif.
   ========================================================================== */

/** La clé que le serveur ajoute à l'APERÇU d'une copie : le nombre de tâches confidentielles NON reprises (jamais copiées
 *  dans un modèle ni dans un double). Absente ou nulle : rien n'est dit. Servie par `modele.json` et
 *  `modele_instancier.json`. */
const CLE_CONFIDENTIELLES = 'confidentielles_non_reprises'

function NonReprises({ apercu }) {
  const n = apercu?.[CLE_CONFIDENTIELLES]
  if (!Number.isInteger(n) || n <= 0) return null
  return <p className="es-aide">{`${accord(n, 'tâche confidentielle', 'tâches confidentielles')} non ${n > 1 ? 'reprises' : 'reprise'}`}</p>
}

function Etapes({ etapes }) {
  if (!etapes || etapes.length === 0) return null
  return (
    <div className="es-etapes-modele">
      {etapes.map((e) => (
        <div className="es-etape-modele" key={e.nom}>
          <span>{e.nom}</span>{e.n != null ? <span className="chiffres">{accord(e.n, 'tâche')}</span> : null}
        </div>
      ))}
    </div>
  )
}

export function DialogueEnregistrerModele({ projet, onFait, onFermer }) {
  const [nom, setNom] = useState(projet.nom)
  const [notes, setNotes] = useState(false)
  const [erreur, setErreur] = useState('')
  const [occupe, setOccupe] = useState(false)
  const [apercu, setApercu] = useState(null)

  // Ce que le modèle contiendra, c'est ce que le SERVEUR copie (confidentielles écartées, sous-tâches comprises) : on lit
  // l'aperçu de la copie — le même moteur que « Dupliquer », `apercu: true`, rien n'est écrit. Sans aperçu lisible
  // (nom déjà pris, réseau), aucun nombre n'est montré : jamais ceux du projet.
  useEffect(() => {
    let vivant = true
    ;(async () => {
      try {
        const { data } = await dupliquerProjet(projet.id, { nom: `${projet.nom} (aperçu)`, date_debut: null, apercu: true })
        if (vivant) setApercu(data)
      } catch {
        if (vivant) setApercu(null) // aperçu illisible : le dialogue se tait sur les nombres, l'enregistrement reste possible
      }
    })()
    return () => { vivant = false }
  }, [projet.id, projet.nom])
  const nbTaches = apercu?.taches?.length
  const etapes = (apercu?.sections ?? []).map((e) => ({ nom: e.nom, n: null }))

  const enregistrer = async () => {
    setOccupe(true)
    setErreur('')
    try {
      const { data } = await enregistrerModele(projet.id, { nom: nom.trim(), inclure_notes: notes }, { erreurSousLeChamp: true })
      onFait?.(data)
    } catch (err) {
      const champs = err?.response?.status === 400 ? err.response.data : null
      setErreur(premiere(champs?.nom) ?? frenchError(err, 'Le modèle n\'a pas été enregistré. Réessaie.'))
    } finally {
      setOccupe(false)
    }
  }
  return (
    <FeuilleACrans ouverte onFermer={onFermer} titre="Enregistrer comme modèle">
      <form className="ep-formulaire" data-p={projet.couleur} noValidate onSubmit={(e) => { e.preventDefault(); enregistrer() }}>
        <p className="ep-dialogue-sous"><i className="point" aria-hidden="true" />{projet.nom}</p>
        <div className="ep-groupe">
          <label className="ep-etiquette" htmlFor="ep-modele-nom">Nom du modèle</label>
          <input id="ep-modele-nom" className="champ" type="text" value={nom} onChange={(e) => setNom(e.target.value)}
            aria-invalid={erreur ? 'true' : undefined} aria-describedby={erreur ? 'ep-modele-erreur' : undefined} />
          <Erreur id="ep-modele-erreur" texte={erreur} />
        </div>
        {Number.isInteger(nbTaches) ? (
          <p className="es-resume"><CalendarCheck className="i i-16" aria-hidden="true" />
            <span className="chiffres">{`${accord(nbTaches, 'tâche')} · ${accord(etapes.length, 'étape')}`}</span>
          </p>
        ) : null}
        <NonReprises apercu={apercu} />
        <Etapes etapes={etapes} />
        <div className="ep-reglage">
          <span id="ep-modele-notes">Inclure les notes</span>
          <button type="button" className="interrupteur" role="switch" aria-checked={notes} aria-labelledby="ep-modele-notes"
            onClick={() => setNotes((v) => !v)} />
        </div>
        <p className="es-aide">Les dates deviennent des écarts depuis la date de lancement&nbsp;; rien n'est coché.</p>
        <Pied onFermer={onFermer} principal={{ libelle: 'Créer', onClick: enregistrer }} occupe={occupe} desactive={!nom.trim()} />
      </form>
    </FeuilleACrans>
  )
}

/**
 * « Utiliser ce modèle » (`source.type === 'modele'`) ou « Dupliquer » (`'projet'`) : un nom, une date de lancement,
 * l'APERÇU des dates annoncé par le serveur (« {n} tâches, première le {jour} »), puis Créer. L'aperçu se lit quand le
 * nom ou la date est posé ; un Créer sans aperçu à jour LIT l'aperçu seulement : rien n'est écrit avant de l'avoir vu.
 */
export function DialogueUtiliser({ source, etapes = null, aujourdhui = aujourdhuiIso(), onFait, onFermer }) {
  const modele = source.type === 'modele'
  // R2-065 — le nom est prérempli (« {nom} (copie) » pour un double) : un seul « Créer » qui écrit
  const [nom, setNom] = useState(modele ? source.nom : `${source.nom} (copie)`)
  // R3-137 — Dupliquer part du lundi PROCHAIN (ses premières tâches ne tombent plus, sans qu'on le dise, aujourd'hui) ; « Utiliser un
  // modèle » garde aujourd'hui
  const [date, setDate] = useState(modele ? aujourdhui : lundiProchain(aujourdhui))
  const [apercu, setApercu] = useState(null)
  const [erreur, setErreur] = useState('')
  const [occupe, setOccupe] = useState(false)
  const rang = useRef(0)

  const corps = (n, d, sansApercu) => (modele
    ? { nom: n, date_lancement: d || null, apercu: !sansApercu }
    : { nom: n, date_debut: d || null, apercu: !sansApercu })
  const appeler = (n, d, sansApercu) => (modele ? instancierModele(source.id, corps(n, d, sansApercu), { erreurSousLeChamp: true })
    : dupliquerProjet(source.id, corps(n, d, sansApercu), { erreurSousLeChamp: true }))

  const lireApercu = async (n, d) => {
    rang.current += 1
    const mien = rang.current
    setApercu(null)
    setErreur('')
    if (!n.trim()) return null
    try {
      const { data } = await appeler(n.trim(), d, false)
      if (mien !== rang.current) return null
      const lu = { ...data, pour: { nom: n.trim(), date: d } }
      setApercu(lu)
      return lu
    } catch (err) {
      if (mien !== rang.current) return null
      const champs = err?.response?.status === 400 ? err.response.data : null
      setErreur(premiere(champs?.nom) ?? premiere(champs?.date_lancement) ?? premiere(champs?.date_debut)
        ?? frenchError(err, 'L\'aperçu n\'a pas pu être lu. Réessaie.'))
      return null
    }
  }

  const aJour = apercu && apercu.pour.nom === nom.trim() && apercu.pour.date === date
  // l'aperçu (rien n'est écrit) est lu dès l'OUVERTURE, puis à chaque changement de date ou de nom posé
  // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps -- lecture à l'ouverture, une fois (D-ENF22)
  useEffect(() => { lireApercu(nom, date) }, [])
  const creer = async () => {
    // UN seul « Créer » qui écrit : l'aperçu est déjà à l'écran ; un nom refusé (déjà pris) s'affiche sous le champ
    rang.current += 1 // un aperçu encore en route ne doit plus rien afficher
    setOccupe(true)
    try {
      const { data } = await appeler(nom.trim(), date, true)
      // R3-137 — ce que l'aperçu avait annoncé (nombre de tâches, premier jour) : l'écran le redit dans son toast
      onFait?.(data, aJour ? { nombre: apercu.taches?.length ?? 0, premier: premiereDate(apercu) } : null)
    } catch (err) {
      const champs = err?.response?.status === 400 ? err.response.data : null
      setErreur(premiere(champs?.nom) ?? frenchError(err, 'Le projet n\'a pas été créé. Réessaie.'))
    } finally {
      setOccupe(false)
    }
  }

  const n = apercu?.taches?.length ?? 0
  const premier = premiereDate(apercu)
  return (
    <FeuilleACrans ouverte onFermer={onFermer} titre={modele ? 'Utiliser ce modèle' : 'Dupliquer'}>
      <form className="ep-formulaire" noValidate onSubmit={(e) => { e.preventDefault(); creer() }}>
        <p className="ep-dialogue-sous">{source.nom}</p>
        <div className="ep-groupe">
          <label className="ep-etiquette" htmlFor="ep-utiliser-nom">Nom du projet</label>
          <input id="ep-utiliser-nom" className="champ" type="text" value={nom}
            onChange={(e) => { setNom(e.target.value); setApercu(null); setErreur('') }}
            onBlur={() => { if (nom.trim() && !aJour) lireApercu(nom, date) }}
            aria-invalid={erreur ? 'true' : undefined} aria-describedby={erreur ? 'ep-utiliser-erreur' : undefined} />
          <Erreur id="ep-utiliser-erreur" texte={erreur} />
        </div>
        <div className="ep-groupe">
          <label className="ep-etiquette" htmlFor="ep-utiliser-date">Date de lancement</label>
          <input id="ep-utiliser-date" className="champ" type="date" value={date}
            onChange={(e) => { setDate(e.target.value); lireApercu(nom, e.target.value) }} />
        </div>
        {apercu ? (
          <p className="es-resume"><CalendarCheck className="i i-16" aria-hidden="true" />
            <span className="chiffres">{`${accord(n, 'tâche')}${premier ? `, première le ${jourNomme(premier, aujourdhui)}` : ''}`}</span>
          </p>
        ) : null}
        <NonReprises apercu={apercu} />
        <Etapes etapes={etapes} />
        <Pied onFermer={onFermer} principal={{ libelle: 'Créer', onClick: creer }} occupe={occupe} desactive={!nom.trim()} />
      </form>
    </FeuilleACrans>
  )
}

export function DialogueRenommerModele({ modele, onFait, onFermer }) {
  const [nom, setNom] = useState(modele.nom)
  const [erreur, setErreur] = useState('')
  const [occupe, setOccupe] = useState(false)
  const renommer = async () => {
    setOccupe(true)
    setErreur('')
    try {
      const { data } = await renommerModele(modele.id, { nom: nom.trim() }, { erreurSousLeChamp: true })
      onFait?.(data)
    } catch (err) {
      const champs = err?.response?.status === 400 ? err.response.data : null
      setErreur(premiere(champs?.nom) ?? frenchError(err, 'Le modèle n\'a pas été renommé. Réessaie.'))
    } finally {
      setOccupe(false)
    }
  }
  return (
    <FeuilleACrans ouverte onFermer={onFermer} titre="Renommer">
      <form className="ep-formulaire" noValidate onSubmit={(e) => { e.preventDefault(); renommer() }}>
        <div className="ep-groupe">
          <label className="ep-etiquette" htmlFor="ep-renommer-nom">Nom du modèle</label>
          <input id="ep-renommer-nom" className="champ" type="text" value={nom} onChange={(e) => setNom(e.target.value)}
            aria-invalid={erreur ? 'true' : undefined} aria-describedby={erreur ? 'ep-renommer-erreur' : undefined} />
          <Erreur id="ep-renommer-erreur" texte={erreur} />
        </div>
        <Pied onFermer={onFermer} principal={{ libelle: 'Renommer', onClick: renommer }} occupe={occupe} desactive={!nom.trim()} />
      </form>
    </FeuilleACrans>
  )
}

export function DialogueSupprimerModele({ modele, onFait, onFermer }) {
  const [erreur, setErreur] = useState('')
  const [occupe, setOccupe] = useState(false)
  const supprimer = async () => {
    setOccupe(true)
    try {
      await supprimerModele(modele.id)
      onFait?.(modele)
    } catch (err) {
      setErreur(frenchError(err, 'Le modèle n\'a pas été supprimé. Réessaie.'))
    } finally {
      setOccupe(false)
    }
  }
  return (
    <FeuilleACrans ouverte onFermer={onFermer} titre="Supprimer">
      <div className="ep-formulaire">
        <p className="ep-dialogue-texte">{`Supprimer « ${modele.nom} » ?`}</p>
        <Erreur id="ep-supprimer-modele-erreur" texte={erreur} />
        <Pied onFermer={onFermer} principal={{ libelle: 'Supprimer', onClick: supprimer }} occupe={occupe} danger />
      </div>
    </FeuilleACrans>
  )
}
