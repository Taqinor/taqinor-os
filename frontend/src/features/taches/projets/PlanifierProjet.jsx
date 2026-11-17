import { useEffect, useRef, useState } from 'react'
import { Sparkles } from 'lucide-react'
import { apercuPlanification, planifierProjet } from '../../../api/tachesApi'
import { frenchError } from '../../../lib/frenchError'
import { EVENEMENT_OUVRIR } from '../../ia/copilotMessages'
import { aujourdhuiIso } from '../lib/textes'
import { PRIORITES } from './LigneProjet'

/* ============================================================================
   TCH91 — « Planifier le projet » : un rituel en deux pas (`?planifier=1` sur l'écran Un projet).
   Maquettes : projet-planifier.html (pas 1 : « Ce sera fini quand… », échéance, priorité) et
   projet-planifier-2.html (pas 2 : premières actions, Plus, Copilote). Textes : reference/textes.md §2.6.
   Contrats : `planification_apercu.json` (lire une liste, RIEN écrit) et `planification.json` (tout créer).
   Boutons : Suivant · Passer · Terminer. Rien n'est écrit avant Terminer ; la saisie est GARDÉE (brouillon dans
   le navigateur, par projet, vidé à la déconnexion et au succès) et rouverte à l'identique.
   Une erreur du serveur s'affiche sous le champ nommé.
   ========================================================================== */

const PRIORITE_AIDE = { 3: 'passe avant les autres', 2: 'le rythme normal', 1: 'quand il reste du temps' }
const QUAND = [['aujourdhui', "Aujourd'hui"], ['demain', 'Demain'], ['sans_jour', 'Sans jour']]
const ECHEANCES = [['1 semaine', 'jours', 7], ['2 semaines', 'jours', 14], ['1 mois', 'mois', 1], ['6 semaines', 'jours', 42], ['3 mois', 'mois', 3]]
export const QUESTION_COPILOTE = 'Découpe ce projet en étapes'
const CLE_BROUILLON = (id) => `taqinor:draft:taches:plan-projet:${id}`
const DELAI_ECRITURE_MS = 400

const deux = (n) => String(n).padStart(2, '0')
function plusLe(iso, unite, n) {
  const [a, m, j] = iso.split('-').map(Number)
  const d = unite === 'mois' ? new Date(a, m - 1 + n, j) : new Date(a, m - 1, j + n)
  return `${d.getFullYear()}-${deux(d.getMonth() + 1)}-${deux(d.getDate())}`
}

function lireBrouillon(cle) {
  try {
    const brut = window.localStorage.getItem(cle)
    return brut ? JSON.parse(brut).data : null
  } catch {
    return null // stockage indisponible ou illisible : on repart d'un formulaire neuf
  }
}

/** Écrit (ou, avec `null`, vide) le brouillon ; `false` si le stockage refuse : un confort, jamais une condition. */
function ecrireBrouillon(cle, data) {
  try {
    if (data) window.localStorage.setItem(cle, JSON.stringify({ savedAt: new Date().toISOString(), data }))
    else window.localStorage.removeItem(cle)
    return true
  } catch {
    return false
  }
}

function Erreur({ id, texte }) {
  return texte ? <p id={id} className="ep-erreur" role="alert">{texte}</p> : null
}

function PasUn({ etat, maj, erreurs, aujourdhui }) {
  return (
    <>
      <div className="ep-groupe">
        <label className="ep-etiquette" htmlFor="pp-objectif">Ce sera fini quand…</label>
        <input
          id="pp-objectif" className="champ" placeholder="Une phrase" value={etat.objectif}
          onChange={(e) => maj({ objectif: e.target.value })}
          aria-invalid={erreurs.objectif ? 'true' : undefined} aria-describedby={erreurs.objectif ? 'pp-objectif-err' : undefined}
        />
        <Erreur id="pp-objectif-err" texte={erreurs.objectif} />
      </div>
      <div className="ep-groupe">
        <div className="ep-etiquette" id="pp-echeance-titre">Échéance</div>
        <div className="puces" role="radiogroup" aria-labelledby="pp-echeance-titre">
          {ECHEANCES.map(([libelle, unite, n]) => {
            const valeur = plusLe(aujourdhui, unite, n)
            return (
              <button key={libelle} type="button" className="puce" role="radio" aria-checked={etat.echeance === valeur}
                onClick={() => maj({ echeance: valeur })}>{libelle}</button>
            )
          })}
        </div>
        <label className="ep-etiquette" htmlFor="pp-echeance-date">Choisir</label>
        <input
          id="pp-echeance-date" className="champ" type="date" value={etat.echeance}
          onChange={(e) => maj({ echeance: e.target.value })}
          aria-invalid={erreurs.echeance ? 'true' : undefined} aria-describedby={erreurs.echeance ? 'pp-echeance-err' : undefined}
        />
        <Erreur id="pp-echeance-err" texte={erreurs.echeance} />
      </div>
      <div className="ep-groupe">
        <div className="ep-etiquette" id="pp-priorite-titre">Priorité</div>
        <div className="ep-choix" role="radiogroup" aria-labelledby="pp-priorite-titre">
          {PRIORITES.filter((p) => p.valeur > 0).map((p) => (
            <button key={p.valeur} type="button" className="ep-choix-ligne" role="radio" aria-checked={etat.priorite === p.valeur}
              onClick={() => maj({ priorite: p.valeur })}>
              <b>{p.libelle}</b><span>{PRIORITE_AIDE[p.valeur]}</span>
            </button>
          ))}
        </div>
        <Erreur id="pp-priorite-err" texte={erreurs.priorite} />
      </div>
    </>
  )
}

function Plus({ etat, maj, apercu, onApercu, erreurs, occupe }) {
  const jalons = (apercu?.sections ?? []).flatMap((s) => s.taches.filter((t) => t.jalon))
  return (
    <details className="ep-plus">
      <summary>Plus</summary>
      <div className="ep-groupe">
        <label className="ep-etiquette" htmlFor="pp-etapes">Étapes</label>
        <textarea id="pp-etapes" className="champ ep-zone" value={etat.texte} rows={4}
          onChange={(e) => maj({ texte: e.target.value })}
          aria-invalid={erreurs.sections ? 'true' : undefined} aria-describedby={erreurs.sections ? 'pp-etapes-err' : undefined} />
        <Erreur id="pp-etapes-err" texte={erreurs.sections} />
        <button type="button" className="bouton second" disabled={occupe || !etat.texte.trim()} onClick={onApercu}>Lire la liste</button>
        {apercu ? (
          <ul className="ep-apercu" aria-label="Étapes lues">
            {apercu.sections.map((s) => (
              <li key={s.nom}>
                <b>{s.nom}</b>
                <ul>{s.taches.map((t) => <li key={t.titre}>{t.titre}</li>)}</ul>
              </li>
            ))}
          </ul>
        ) : null}
        {jalons.length > 0 ? (
          <div className="ep-jalons">
            <b>Jalons</b>
            <ul>{jalons.map((t) => <li key={t.titre}>{t.titre}</li>)}</ul>
          </div>
        ) : null}
      </div>
      <div className="ep-groupe">
        <label className="ep-etiquette" htmlFor="pp-risque">Si ça échoue, ce sera sans doute parce que…</label>
        <input id="pp-risque" className="champ" value={etat.risque} onChange={(e) => maj({ risque: e.target.value })}
          aria-invalid={erreurs.risque ? 'true' : undefined} aria-describedby={erreurs.risque ? 'pp-risque-err' : undefined} />
        <Erreur id="pp-risque-err" texte={erreurs.risque} />
        <button type="button" className="bouton second" disabled={!etat.risque.trim()}
          onClick={() => maj({ actions: [...etat.actions, { titre: etat.risque.trim(), quand: 'sans_jour' }], risque: '' })}>
          En faire une tâche
        </button>
      </div>
    </details>
  )
}

function PasDeux({ etat, maj, erreurs, projet, apercu, onApercu, occupe }) {
  const [nouvelle, setNouvelle] = useState('')
  const ajouter = (e) => {
    e.preventDefault()
    if (!nouvelle.trim()) return
    maj({ actions: [...etat.actions, { titre: nouvelle.trim(), quand: 'sans_jour' }] })
    setNouvelle('')
  }
  const ouvrirCopilote = () => window.dispatchEvent(new CustomEvent(EVENEMENT_OUVRIR, {
    detail: { ecran: window.location.pathname, question: QUESTION_COPILOTE, envoyer: true, projet_id: projet.id },
  }))
  return (
    <>
      <div className="ep-groupe">
        <h3 className="ep-etiquette">Premières actions</h3>
        {etat.actions.map((a, i) => (
          <div key={`${a.titre}:${i}`} className="ep-action">
            <span className="ep-action-titre">{a.titre}</span>
            <div className="puces" role="radiogroup" aria-label={`Quand : ${a.titre}`}>
              {QUAND.map(([code, libelle]) => (
                <button key={code} type="button" className="puce" role="radio" aria-checked={a.quand === code}
                  onClick={() => maj({ actions: etat.actions.map((x, j) => (j === i ? { ...x, quand: code } : x)) })}>
                  {libelle}
                </button>
              ))}
            </div>
          </div>
        ))}
        <Erreur id="pp-actions-err" texte={erreurs.actions} />
        <form className="ep-ajout-action" onSubmit={ajouter} noValidate>
          <label className="sr" htmlFor="pp-nouvelle">Nouvelle action</label>
          <input id="pp-nouvelle" className="champ" value={nouvelle} onChange={(e) => setNouvelle(e.target.value)} />
          <button type="submit" className="bouton second" disabled={!nouvelle.trim()}>Ajouter</button>
        </form>
        {projet.confidentiel ? null : (
          <button type="button" className="copilote" onClick={ouvrirCopilote}>
            <Sparkles className="i i-16" aria-hidden="true" />Planifier avec le Copilote
          </button>
        )}
      </div>
      <Plus etat={etat} maj={maj} apercu={apercu} onApercu={onApercu} erreurs={erreurs} occupe={occupe} />
    </>
  )
}

const VIDE = { pas: 1, priorite: 2, objectif: '', echeance: '', actions: [], texte: '', risque: '' }

export default function PlanifierProjet({ projet, onTermine, onPasser, aujourdhui = aujourdhuiIso() }) {
  const cle = CLE_BROUILLON(projet.id)
  const [etat, setEtat] = useState(() => ({ ...VIDE, priorite: projet.priorite || VIDE.priorite, ...(lireBrouillon(cle) ?? {}) }))
  const [apercu, setApercu] = useState(null)
  const [erreurs, setErreurs] = useState({})
  const [occupe, setOccupe] = useState(false)
  const modifie = useRef(false)

  const maj = (suite) => {
    modifie.current = true
    if (suite.texte !== undefined) setApercu(null)
    setEtat((e) => ({ ...e, ...suite }))
  }

  // brouillon gardé : écrit peu après la dernière frappe, vidé à la déconnexion
  useEffect(() => {
    if (!modifie.current) return undefined
    const minuteur = setTimeout(() => ecrireBrouillon(cle, etat), DELAI_ECRITURE_MS)
    return () => clearTimeout(minuteur)
  }, [cle, etat])
  useEffect(() => {
    const vider = () => ecrireBrouillon(cle, null)
    window.addEventListener('taqinor:auth-logout', vider)
    return () => window.removeEventListener('taqinor:auth-logout', vider)
  }, [cle])

  const lireListe = async () => {
    setOccupe(true)
    try {
      const { data } = await apercuPlanification(projet.id, { texte: etat.texte })
      setApercu(data)
      setErreurs((e) => ({ ...e, sections: '' }))
      return data
    } catch (err) {
      setErreurs((e) => ({ ...e, sections: err?.response?.data?.texte?.[0] ?? frenchError(err, 'La liste n\'a pas pu être lue. Réessaie.') }))
      return null
    } finally {
      setOccupe(false)
    }
  }

  const terminer = async () => {
    setOccupe(true)
    setErreurs({})
    try {
      let lue = apercu
      if (etat.texte.trim() && !lue) {
        lue = await lireListe()
        if (!lue) return
      }
      const corps = {
        priorite: etat.priorite,
        objectif: etat.objectif,
        echeance: etat.echeance || null,
        risque: etat.risque,
        sections: lue?.sections ?? [],
        actions: etat.actions,
        lock_version: projet.lock_version,
      }
      const { data } = await planifierProjet(projet.id, corps)
      ecrireBrouillon(cle, null)
      onTermine?.(data)
    } catch (err) {
      const champs = err?.response?.status === 400 ? err.response.data : null
      if (champs && typeof champs === 'object') {
        const lus = Object.fromEntries(Object.entries(champs).map(([k, v]) => [k, Array.isArray(v) ? v[0] : String(v)]))
        setErreurs(lus)
        if (lus.objectif || lus.echeance || lus.priorite) setEtat((e) => ({ ...e, pas: 1 }))
      } else {
        setErreurs({ general: frenchError(err, 'Le projet n\'a pas été planifié. Réessaie.') })
      }
    } finally {
      setOccupe(false)
    }
  }

  return (
    <section className="ep-planifier" aria-label="Planifier le projet" data-p={projet.couleur}>
      <header className="ep-planifier-tete">
        <div>
          <h2 className="ep-titre">Planifier le projet</h2>
          <p className="ep-sous chiffres">{`${projet.nom} · pas ${etat.pas} sur 2`}</p>
        </div>
        <button type="button" className="bouton discret" onClick={onPasser}>Passer</button>
      </header>
      {erreurs.general ? <p className="ep-erreur" role="alert">{erreurs.general}</p> : null}
      {etat.pas === 1
        ? <PasUn etat={etat} maj={maj} erreurs={erreurs} aujourdhui={aujourdhui} />
        : <PasDeux etat={etat} maj={maj} erreurs={erreurs} projet={projet} apercu={apercu} onApercu={lireListe} occupe={occupe} />}
      <div className="carte-actions ep-planifier-pied">
        {etat.pas === 2 ? <button type="button" className="bouton second" onClick={() => maj({ pas: 1 })}>Précédent</button> : null}
        {etat.pas === 1
          ? <button type="button" className="bouton plein" onClick={() => maj({ pas: 2 })}>Suivant</button>
          : <button type="button" className="bouton plein" disabled={occupe} onClick={terminer}>Terminer</button>}
      </div>
    </section>
  )
}
