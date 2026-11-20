import { useEffect, useRef, useState } from 'react'
import { ChevronDown, Sparkles, X } from 'lucide-react'
import { apercuPlanification, planifierProjet, planifierTache, saisieRapide } from '../../../api/tachesApi'
import { frenchError } from '../../../lib/frenchError'
import { EVENEMENT_OUVRIR } from '../../ia/copilotMessages'
import { proposerAnnuler } from '../lib/gestes'
import { accord, aujourdhuiIso, jourCourt } from '../lib/textes'
import { ajouterJours } from '../ui/SelecteurQuand'
import { PRIORITES, jourProjet } from './LigneProjet'

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
// valeurs de `actions[].quand` acceptées par `planification/` : aujourdhui · demain · plus_tard · '' (sans jour)
const QUAND = [['aujourdhui', "Aujourd'hui"], ['demain', 'Demain'], ['', 'Sans jour']]
/** Un brouillon d'avant le raccord peut porter `sans_jour` (refusé) ou `plus_tard` : « Sans jour » part en `''`. */
const quandServi = (quand) => (quand === 'sans_jour' || quand === 'plus_tard' || quand == null ? '' : quand)
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

/**
 * R4-27 — une première action se lit avec l'ANALYSEUR DE LA SAISIE (`saisie-rapide/` aperçu, rien n'est écrit) : le
 * jour qu'elle nomme (« demain », « samedi », « dans 15 jours ») quitte le titre et devient son « Quand » — Aujourd'hui,
 * Demain, ou un autre jour (`jour`, posé après la création : `planification/` ne connaît que ces deux mots). Le reste
 * de la phrase reste tel quel. Rend `{ titre, quand, jour? }` ou `null` (aucun jour lu, hors ligne : l'action garde son
 * texte, rien n'est perdu).
 */
async function lireAction(texte, aujourdhui) {
  let ligne = null
  try {
    ligne = (await saisieRapide({ texte, apercu: true }, { cle: null, erreurSousLeChamp: true })).data?.lignes?.[0]
  } catch {
    return null // pas de lecture (réseau, refus) : l'action garde la phrase tapée
  }
  const jeton = (ligne?.jetons ?? []).find((j) => j.type === 'jour' && typeof j.valeur === 'string'
    && texte.slice(j.debut, j.fin) === j.source)
  if (!jeton) return null
  const titre = `${texte.slice(0, jeton.debut)} ${texte.slice(jeton.fin)}`.replace(/\s+/g, ' ').trim()
  if (!titre) return null // la phrase n'était qu'une date : elle reste le titre
  const quand = jeton.valeur === aujourdhui ? 'aujourdhui' : jeton.valeur === ajouterJours(aujourdhui, 1) ? 'demain' : ''
  return quand ? { titre, quand, jour: null } : { titre, quand: '', jour: jeton.valeur }
}

/** Le corps envoyé d'une action : `{ titre, quand }` (un autre jour lu part « sans jour », posé ensuite). */
const actionServie = (a) => ({ titre: a.titre, quand: a.jour ? '' : quandServi(a.quand) })

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
        {etat.echeance ? <p className="es-aide chiffres">{jourProjet(etat.echeance, aujourdhui)}</p> : null}
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

/** « 3 étapes · 0 tâche » : ce que l'aperçu a lu (une section sans nom = des tâches sans étape, non comptée comme étape). */
function resumeDuPlan(sections) {
  const etapes = sections.filter((s) => s.nom != null).length
  const taches = sections.reduce((n, s) => n + s.taches.length, 0)
  return `${accord(etapes, 'étape')} · ${accord(taches, 'tâche')}`
}

function Plus({ etat, maj, apercu, onApercu, erreurs, occupe }) {
  const jalons = (apercu?.sections ?? []).flatMap((s) => s.taches.filter((t) => t.jalon))
  return (
    <details className="ep-plus">
      <summary>Plus<ChevronDown className="i i-16" aria-hidden="true" /></summary>
      <div className="ep-groupe">
        <label className="ep-etiquette" htmlFor="pp-etapes">Étapes</label>
        <p className="es-aide" id="pp-etapes-aide">Une ligne par étape ; ses tâches dessous, en retrait ou avec un tiret.</p>
        <textarea id="pp-etapes" className="champ ep-zone" value={etat.texte} rows={4}
          onChange={(e) => maj({ texte: e.target.value })}
          aria-invalid={erreurs.sections ? 'true' : undefined}
          aria-describedby={erreurs.sections ? 'pp-etapes-aide pp-etapes-err' : 'pp-etapes-aide'} />
        <Erreur id="pp-etapes-err" texte={erreurs.sections} />
        <button type="button" className="bouton second" disabled={occupe || !etat.texte.trim()} onClick={onApercu}>Lire la liste</button>
        {apercu ? (
          <>
            <p className="ep-resume chiffres" role="status">{resumeDuPlan(apercu.sections)}</p>
            <ul className="ep-apercu" aria-label="Étapes lues">
              {apercu.sections.map((s, i) => (
                <li key={`${s.nom}:${i}`}>
                  <b>{s.nom ?? 'Sans étape'}</b>
                  {s.taches.length > 0 ? <ul>{s.taches.map((t, j) => <li key={`${t.titre}:${j}`}>{t.titre}</li>)}</ul> : null}
                </li>
              ))}
            </ul>
          </>
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
          onClick={() => maj({ actions: [...etat.actions, { titre: `Parer : ${etat.risque.trim()}`, quand: '' }], risque: '' })}>
          En faire une tâche
        </button>
      </div>
    </details>
  )
}

function PasDeux({ etat, maj, erreurs, projet, apercu, onApercu, occupe, onAjouter, aujourdhui }) {
  // le champ « Nouvelle action » vit dans la saisie du rituel (`etat.nouvelle`) : Terminer, Précédent et le brouillon le
  // retrouvent, une frappe laissée sans Entrée ne se perd jamais
  const nouvelle = etat.nouvelle
  const ajouter = (e) => {
    e.preventDefault()
    onAjouter()
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
            <div className="ep-action-tete">
              <span className="ep-action-titre">{a.titre}</span>
              <button type="button" className="ep-action-retirer" aria-label={`Retirer « ${a.titre} »`}
                onClick={() => maj({ actions: etat.actions.filter((_, j) => j !== i) })}>
                <X className="i i-16" aria-hidden="true" />
              </button>
            </div>
            <div className="puces" role="radiogroup" aria-label={`Quand : ${a.titre}`}>
              {QUAND.map(([code, libelle]) => (
                <button key={code} type="button" className="puce" role="radio" aria-checked={!a.jour && quandServi(a.quand) === code}
                  onClick={() => maj({ actions: etat.actions.map((x, j) => (j === i ? { ...x, quand: code, jour: null } : x)) })}>
                  {libelle}
                </button>
              ))}
              {/* R4-27 — un autre jour lu dans la phrase (« samedi ») : sa puce, choisie */}
              {a.jour ? (
                <button type="button" className="puce chiffres" role="radio" aria-checked>{jourCourt(a.jour, aujourdhui)}</button>
              ) : null}
            </div>
          </div>
        ))}
        <Erreur id="pp-actions-err" texte={erreurs.actions} />
        <form className="ep-ajout-action" onSubmit={ajouter} noValidate>
          <label className="sr" htmlFor="pp-nouvelle">Nouvelle action</label>
          <input id="pp-nouvelle" className="champ" value={nouvelle} onChange={(e) => maj({ nouvelle: e.target.value })} />
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

const VIDE = { pas: 1, priorite: 2, objectif: '', echeance: '', actions: [], nouvelle: '', texte: '', risque: '' }

export default function PlanifierProjet({ projet, onTermine, onPasser, aujourdhui = aujourdhuiIso() }) {
  const cle = CLE_BROUILLON(projet.id)
  const [etat, setEtat] = useState(() => ({ ...VIDE, priorite: projet.priorite || VIDE.priorite, ...(lireBrouillon(cle) ?? {}) }))
  const [apercu, setApercu] = useState(null)
  const [erreurs, setErreurs] = useState({})
  const [occupe, setOccupe] = useState(false)
  const modifie = useRef(false)
  // R4-27 — la DERNIÈRE saisie (lue après une lecture d'action revenue) et les lectures encore en vol
  const etatRef = useRef(etat)
  useEffect(() => { etatRef.current = etat })
  const lectures = useRef(new Set())
  const numero = useRef(0)

  /** R4-27 — une écriture de la saisie : la même fonction pure pour l'écran et pour `etatRef` (lu par « Terminer »
   *  aussitôt une lecture revenue, avant même le rendu suivant). */
  const poser = (changer) => {
    modifie.current = true
    etatRef.current = changer(etatRef.current)
    setEtat(changer)
  }
  const maj = (suite) => {
    if (suite.texte !== undefined) setApercu(null)
    poser((e) => ({ ...e, ...suite }))
  }

  // brouillon gardé : écrit peu après la dernière frappe, vidé à la déconnexion
  const minuteur = useRef(null)
  useEffect(() => {
    if (!modifie.current) return undefined
    minuteur.current = setTimeout(() => ecrireBrouillon(cle, etat), DELAI_ECRITURE_MS)
    return () => clearTimeout(minuteur.current)
  }, [cle, etat])
  useEffect(() => {
    const vider = () => ecrireBrouillon(cle, null)
    window.addEventListener('taqinor:auth-logout', vider)
    return () => window.removeEventListener('taqinor:auth-logout', vider)
  }, [cle])

  /** R4-27 — l'action part TOUT DE SUITE avec la phrase tapée ; sa lecture (jour lu, titre sans le jour) la remplace
   *  au retour, sur la valeur COURANTE (jamais une copie d'avant la lecture). Sans argument : le texte COURANT du
   *  champ « Nouvelle action » (Entrée, « Ajouter », et tout bouton qui quitte l'étape : une frappe ne se perd jamais). */
  const ajouterAction = () => {
    const texte = etatRef.current.nouvelle.trim()
    if (!texte) return
    numero.current += 1
    const cleAction = `a${numero.current}`
    poser((e) => ({ ...e, actions: [...e.actions, { titre: texte, quand: '', cle: cleAction }], nouvelle: '' }))
    const lecture = lireAction(texte, aujourdhui).then((lue) => {
      if (lue) poser((e) => ({ ...e, actions: e.actions.map((a) => (a.cle === cleAction && a.titre === texte ? { ...a, ...lue } : a)) }))
    })
    lectures.current.add(lecture)
    lecture.finally(() => lectures.current.delete(lecture))
  }

  /** R4-27 — après la création, les actions à un AUTRE jour lu (« samedi ») y sont posées (`planifier/`) ; la tâche
   *  créée est retrouvée à sa place (les tâches des étapes d'abord, puis les actions, dans l'ordre), sinon par son
   *  titre. Un jour qui n'a pas pu être posé est DIT ; la tâche, elle, existe. Rend les `creees` à jour. */
  const poserLesJours = async (data, actions, sections) => {
    const creees = [...(data?.creees ?? [])]
    const avant = sections.reduce((n, s) => n + (s.taches?.length ?? 0), 0)
    for (const [i, action] of actions.entries()) {
      if (!action.jour) continue
      let rang = avant + i
      if (creees[rang]?.titre !== action.titre) rang = creees.findIndex((c) => c?.titre === action.titre)
      const tache = creees[rang]
      if (!tache) continue
      try {
        const { data: ecrite } = await planifierTache(tache.id, {
          jour_prevu: action.jour, moment: '', heure_debut: null, quelque_jour: false, lock_version: tache.lock_version,
        })
        creees[rang] = { ...tache, ...(ecrite?.tache ?? {}) }
      } catch (err) {
        proposerAnnuler({ message: `« ${action.titre} » créée sans jour : ${frenchError(err)}` })
      }
    }
    return creees
  }

  const lireListe = async () => {
    setOccupe(true)
    try {
      // ce champ lit des ÉTAPES (R2-062) : une ligne non indentée = une étape, sans « : » à taper
      const { data } = await apercuPlanification(projet.id, { texte: etat.texte, mode: 'etapes' })
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
      ajouterAction() // le texte resté dans « Nouvelle action » est une action, comme si Entrée l'avait prise
      // R4-27 — une action dont la lecture est encore en vol : on l'attend (jamais « … demain » dans un titre)
      await Promise.all([...lectures.current])
      const saisi = etatRef.current
      let lue = apercu
      if (saisi.texte.trim() && !lue) {
        lue = await lireListe()
        if (!lue) return
      }
      const corps = {
        priorite: saisi.priorite,
        objectif: saisi.objectif,
        echeance: saisi.echeance || null,
        risque: saisi.risque,
        sections: lue?.sections ?? [],
        actions: saisi.actions.map(actionServie),
        lock_version: projet.lock_version,
      }
      const { data } = await planifierProjet(projet.id, corps)
      // le projet est planifié : le brouillon part, et l'écriture différée d'une frappe récente ne le ressuscite pas
      clearTimeout(minuteur.current)
      modifie.current = false
      ecrireBrouillon(cle, null)
      const creees = saisi.actions.some((a) => a.jour) ? await poserLesJours(data, saisi.actions, corps.sections) : null
      onTermine?.(creees ? { ...data, creees } : data)
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
      <ol className="ep-pas" aria-label="Étapes du rituel">
        <li className={etat.pas >= 1 ? 'fait' : ''} aria-current={etat.pas === 1 ? 'step' : undefined}><i /></li>
        <li className={etat.pas >= 2 ? 'fait' : ''} aria-current={etat.pas === 2 ? 'step' : undefined}><i /></li>
      </ol>
      {erreurs.general ? <p className="ep-erreur" role="alert">{erreurs.general}</p> : null}
      {etat.pas === 1
        ? <PasUn etat={etat} maj={maj} erreurs={erreurs} aujourdhui={aujourdhui} />
        : <PasDeux etat={etat} maj={maj} erreurs={erreurs} projet={projet} apercu={apercu} onApercu={lireListe} occupe={occupe}
          onAjouter={ajouterAction} aujourdhui={aujourdhui} />}
      {/* R3-128 — au pas 1 le pied suit le contenu (jamais collé au-dessus des trois priorités) ; au pas 2, long, il reste en bas */}
      <div className={etat.pas === 1 ? 'carte-actions ep-planifier-pied pas-un' : 'carte-actions ep-planifier-pied'}>
        {etat.pas === 2 ? <button type="button" className="bouton second" onClick={() => { ajouterAction(); maj({ pas: 1 }) }}>Précédent</button> : null}
        {etat.pas === 1
          ? <button type="button" className="bouton plein" onClick={() => maj({ pas: 2 })}>Suivant</button>
          : <button type="button" className="bouton plein" disabled={occupe} onClick={terminer}>Terminer</button>}
      </div>
    </section>
  )
}
