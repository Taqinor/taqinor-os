import { useRef, useState } from 'react'
import { ArrowRight, CalendarClock } from 'lucide-react'
import { decalerProjet, listerTousLesProjets, supprimerProjet, terminerProjet } from '../../../api/tachesApi'
import { frenchError } from '../../../lib/frenchError'
import FeuilleACrans from '../ui/FeuilleACrans'
import { accord, aujourdhuiIso, jourCourt } from '../lib/textes'

/* ============================================================================
   TCH92 — Les trois dialogues d'un projet : Supprimer (« … et ses N tâches ? »), Décaler les dates (aperçu
   AVANT d'écrire, dont « N tâches passeraient avant aujourd'hui »), Terminer (issue, bilan, tâches encore ouvertes).
   Maquettes : projet-supprimer.html, projet-decaler.html, projet-decaler-avant.html, projet-terminer.html.
   Textes : reference/textes.md §2.6 (Décaler, Pause, Terminer, Supprimer). Contrats : `decalage.json`,
   `projet_ecrit.json`. Chaque dialogue est une FeuilleACrans (feuille sur iPhone, dialogue centré au bureau) ;
   il appelle l'API, dit l'erreur SOUS le champ fautif, puis rend la main par `onFait(reponse)`.
   ========================================================================== */

const premiere = (valeur) => (Array.isArray(valeur) ? valeur[0] : valeur)

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

/** Un changement du décalage, en une ligne : « Envoyer le devis · mar. 24 → mar. 1 déc. ». */
function nomDuChangement(c, noms) {
  if (c.objet === 'projet') return c.champ === 'echeance' ? 'Échéance du projet' : 'Date de début du projet'
  if (c.objet === 'section') return noms?.sections?.[c.id] ?? 'Étape'
  return noms?.taches?.[c.id] ?? 'Tâche'
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
      const { data } = await decalerProjet(projet.id, { delta_jours: valeur, apercu: true })
      if (mien === rang.current) setApercu(data)
    } catch (err) {
      if (mien === rang.current) setErreur(premiere(err?.response?.data?.delta_jours) ?? frenchError(err, 'Le décalage n\'a pas pu être calculé. Réessaie.'))
    }
  }

  const appliquer = async () => {
    setOccupe(true)
    try {
      const { data } = await decalerProjet(projet.id, { delta_jours: delta, apercu: false })
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
        <Pied onFermer={onFermer} principal={{ libelle: 'Appliquer', onClick: appliquer }} occupe={occupe} desactive={!apercu || n === 0} />
      </div>
    </FeuilleACrans>
  )
}

const OUVERTES = [
  ['boite', 'Les remettre dans À trier'],
  ['abandonner', 'Les abandonner'],
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
      const { data } = await terminerProjet(projet.id, corps)
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
