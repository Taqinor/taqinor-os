import { useState } from 'react'
import { Link as LienIcone, X } from 'lucide-react'

import { frenchError } from '../../../lib/frenchError'
import {
  annulerGeste, attendreTache, classerErreur, creerTache, modifierRecurrence, nouvelleCle, poserRappel, recevoirTache,
  restaurerTache, retirerRappel, sauterTache, supprimerTache, trancherTache, rechercher } from '../../../api/tachesApi'
import { annoncer, proposerAnnuler } from '../lib/gestes'
import { accord, duree, heure, jourCourt } from '../lib/textes'
import CaseRonde from '../ui/CaseRonde'
import { ajouterJours } from '../ui/SelecteurQuand'

/* ============================================================================
   TCH85 — « Plus » d'une fiche : Rappel (avec la question du titre au 1er rappel) · Répéter ·
   Durée · En attente de… · Jalon · Lié à · Confidentielle · Sous-tâches · Abandonner · Supprimer
   (dialogue qui NOMME la tâche). Les étiquettes viennent en F4 (TCH166). Source : textes.md
   « Fiche d'une tâche, Quand, Rappel » ; maquettes ecran-fiche-plus.html, etat-question-rappel.html.
   Rouvrir ce volet montre les MÊMES valeurs : tout est lu de la tâche, rien n'est gardé ici sauf
   ce qui est en cours de frappe. La fiche (`Fiche.jsx`) fournit `ecrire` / `patcher` : un 400
   s'affiche sous le champ fautif, un 409 déclenche son bandeau de conflit.
   ========================================================================== */

const JOURS_SEMAINE = ['dimanche', 'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi']
const ETATS_LIEN = {
  archive: 'Élément archivé', introuvable: 'Élément introuvable', inaccessible: 'Hors de ta portée', efface: 'Lead effacé',
}

const dateDe = (iso) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso ?? ''))
  return m ? new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]))) : null
}

/** Les façons de répéter proposées à partir du jour de la tâche (libellés de `libelle_regle`, textes.md §2.4). */
function reglesProposees(jour) {
  const d = dateDe(jour)
  if (!d) return []
  const sem = d.getUTCDay()
  const masque = Array.from({ length: 7 }, (_, i) => (i === (sem + 6) % 7 ? '1' : '0')).join('')
  const jj = String(d.getUTCDate()).padStart(2, '0')
  const mm = String(d.getUTCMonth() + 1).padStart(2, '0')
  return [
    { cle: 'jour', libelle: 'chaque jour', regle: { frequence: 'quotidien', intervalle: 1 } },
    { cle: 'ouvre', libelle: 'chaque jour travaillé', regle: { frequence: 'jours_ouvres', intervalle: 1 } },
    { cle: 'semaine', libelle: `chaque ${JOURS_SEMAINE[sem]}`, regle: { frequence: 'hebdo', intervalle: 1, jours_semaine: masque } },
    { cle: 'mois', libelle: `chaque mois le ${d.getUTCDate()}`, regle: { frequence: 'mensuel', intervalle: 1, jour_du_mois: d.getUTCDate() } },
    { cle: 'an', libelle: `chaque année le ${jj}/${mm}`, regle: { frequence: 'annuel', intervalle: 1 } },
  ]
}

function Rappel({ tache, aujourdhui, ecrire, annulable }) {
  const [mode, setMode] = useState('meme')
  const [heureRappel, setHeureRappel] = useState('09:00')
  const [jourChoisi, setJourChoisi] = useState('')
  const ancre = Boolean(tache.echeance)
  const pivot = tache.echeance ?? tache.jour_prevu

  const poser = async () => {
    let corps
    if (mode === 'choisir') corps = { jour: jourChoisi, heure: heureRappel }
    else if (ancre) corps = { ancre: 'echeance', decalage_jours: mode === 'veille' ? -1 : 0, heure: heureRappel }
    else corps = { jour: mode === 'veille' ? ajouterJours(pivot, -1) : pivot, heure: heureRappel }
    const r = await ecrire(() => poserRappel(tache.id, corps), 'rappel')
    if (r) {
      const pose = r.data?.rappel ?? corps
      const quand = pose.jour ? `${jourCourt(pose.jour, aujourdhui)} à ${heure(pose.heure ?? heureRappel)}` : `à ${heure(heureRappel)}`
      annulable(`Rappel posé ${quand}`, r.geste)
    }
  }
  const retirer = (rappel) => ecrire(() => retirerRappel(rappel.id), 'rappel', undefined, true)
  const actifs = (tache.rappels ?? []).filter((r) => r.statut === 'en_attente')

  return (
    <section className="fiche-bloc" aria-label="Rappel">
      <h3 className="fiche-bloc-titre">Rappel</h3>
      {actifs.map((r) => (
        <p key={r.id} className="fiche-rappel-ligne chiffres">
          {r.ancre ? `${accord(Math.abs(r.decalage_jours), 'jour')} avant l'échéance à ${heure(r.heure)}` : `${jourCourt(r.jour, aujourdhui)} ${heure(r.heure)}`}
          <button type="button" className="bouton-icone" aria-label={`Retirer le rappel de ${heure(r.heure)}`} onClick={() => retirer(r)}>
            <X className="i i-16" aria-hidden="true" />
          </button>
        </p>
      ))}
      <div className="segmente" role="radiogroup" aria-label="Quand sonner">
        {[['meme', 'Le jour même'], ['veille', 'La veille'], ['choisir', 'Choisir']].map(([cle, libelle]) => (
          <button key={cle} type="button" role="radio" aria-checked={mode === cle} onClick={() => setMode(cle)}>{libelle}</button>
        ))}
      </div>
      {mode === 'choisir' ? (
        <input type="date" className="champ-discret chiffres" aria-label="Jour du rappel" value={jourChoisi} onChange={(e) => setJourChoisi(e.target.value)} />
      ) : null}
      <input type="time" className="champ-discret chiffres" aria-label="Heure du rappel" value={heureRappel} onChange={(e) => setHeureRappel(e.target.value)} />
      <button type="button" className="bouton second" onClick={poser}>Poser le rappel</button>
    </section>
  )
}

function Repeter({ tache, aujourdhui, ecrire, patcher, erreur }) {
  const regle = tache.recurrence
  const propositions = reglesProposees(tache.jour_prevu ?? aujourdhui)
  const [apresFait, setApresFait] = useState(regle?.mode === 'apres_fait')
  const debut = tache.jour_prevu ?? aujourdhui

  const choisir = async (proposition) => {
    const corps = { ...proposition.regle, mode: apresFait ? 'apres_fait' : 'calendrier', date_debut: regle?.date_debut ?? debut }
    if (regle) await ecrire(() => modifierRecurrence(regle.id, corps), 'repeter', undefined, true)
    else await patcher({ recurrence: corps }, 'repeter')
  }
  const arreter = () => ecrire(() => modifierRecurrence(regle.id, { actif: false }), 'repeter', undefined, true)
  const appliquer = () => ecrire(() => modifierRecurrence(regle.id, { appliquer_a_l_ouverte: true }), 'repeter', undefined, true)
  const sauter = () => ecrire(() => sauterTache(tache.id), 'repeter', undefined, true)

  return (
    <section className="fiche-bloc" aria-label="Répéter">
      <h3 className="fiche-bloc-titre">Répéter</h3>
      {regle ? <p className="chiffres">{`${regle.libelle}${regle.mode === 'apres_fait' ? ' après fait' : ''}`}</p> : null}
      <div className="puces" role="radiogroup" aria-label="Répéter">
        {propositions.map((p) => (
          <button
            key={p.cle}
            type="button"
            role="radio"
            className="puce"
            aria-checked={regle?.frequence === p.regle.frequence}
            onClick={() => choisir(p)}
          >
            {p.libelle}
          </button>
        ))}
      </div>
      <label className="fiche-ajout">
        <input type="checkbox" checked={apresFait} onChange={(e) => { setApresFait(e.target.checked); erreur('repeter', '') }} />
        <span>après fait</span>
      </label>
      {regle ? (
        <div className="carte-actions">
          <button type="button" className="bouton second" onClick={sauter}>Sauter cette fois</button>
          <button type="button" className="bouton second" onClick={appliquer}>Appliquer à celle-ci aussi</button>
          <button type="button" className="bouton second" onClick={arreter}>Arrêter de répéter</button>
        </div>
      ) : null}
    </section>
  )
}

function Attente({ tache, ecrire, patcher, erreur }) {
  const [qui, setQui] = useState(tache.en_attente_de ?? '')
  const [mode, setMode] = useState(tache.bloquee_par ? 'tache' : 'quelquun')
  const [q, setQ] = useState('')
  const [resultats, setResultats] = useState([])

  const chercher = async (texte) => {
    setQ(texte)
    if (!texte.trim()) { setResultats([]); return }
    try {
      const { data } = await rechercher({ q: texte, limite: 8 })
      setResultats((data.taches ?? []).filter((t) => t.id !== tache.id))
    } catch (err) {
      erreur('attente', frenchError(err))
    }
  }
  const attendreQui = () => ecrire(() => attendreTache(tache.id, { en_attente_de: qui }), 'attente', undefined, true)
  const attendreTache2 = async (autre) => {
    setResultats([]); setQ('')
    await patcher({ bloquee_par_id: autre.id }, 'attente')
  }

  return (
    <section className="fiche-bloc" aria-label="En attente de">
      <h3 className="fiche-bloc-titre">En attente de…</h3>
      <div className="segmente" role="radiogroup" aria-label="En attente de">
        <button type="button" role="radio" aria-checked={mode === 'quelquun'} onClick={() => setMode('quelquun')}>Quelqu'un ou quelque chose</button>
        <button type="button" role="radio" aria-checked={mode === 'tache'} onClick={() => setMode('tache')}>Une autre tâche</button>
      </div>
      {mode === 'quelquun' ? (
        <>
          <input type="text" className="champ-discret" aria-label="De qui ou de quoi ?" placeholder="De qui ou de quoi ?" value={qui}
            onChange={(e) => setQui(e.target.value)} onBlur={() => { if (qui !== (tache.en_attente_de ?? '')) attendreQui() }} />
          {tache.en_attente_de ? (
            <button type="button" className="bouton second" onClick={() => ecrire(() => recevoirTache(tache.id), 'attente', undefined, true)}>Reçu</button>
          ) : null}
        </>
      ) : (
        <>
          {tache.bloquee_par?.titre ? <p>{`attend : ${tache.bloquee_par.titre}`}</p> : null}
          <input type="search" className="champ-discret" aria-label="Chercher une tâche" placeholder="Chercher une tâche" value={q} onChange={(e) => chercher(e.target.value)} />
          <div aria-label="Tâches trouvées">
            {resultats.map((t) => (
              <button key={t.id} type="button" className="fiche-ligne" onClick={() => attendreTache2(t)}>{t.titre}</button>
            ))}
          </div>
        </>
      )}
    </section>
  )
}

function SousTaches({ tache, charger, erreur }) {
  const [titre, setTitre] = useState('')
  const enfants = tache.enfants ?? []
  const ajouter = async () => {
    if (!titre.trim()) return
    try {
      await creerTache({ titre: titre.trim(), parent_id: tache.id, client_id: nouvelleCle() })
      setTitre('')
      await charger()
    } catch (err) {
      erreur('sous_taches', classerErreur(err).champs?.titre?.[0] || frenchError(err))
    }
  }
  return (
    <section className="fiche-bloc" aria-label="Sous-tâches">
      <h3 className="fiche-bloc-titre">Sous-tâches</h3>
      {enfants.map((e) => (
        <div key={e.id} className="fiche-point">
          <CaseRonde coche={e.statut === 'fait'} desactivee libelle={`${e.statut === 'fait' ? 'Faite' : 'À faire'} : ${e.titre}`} />
          <span className="titre">{e.titre}</span>
        </div>
      ))}
      <input type="text" className="champ-discret" aria-label="Découper" placeholder="Découper" value={titre}
        onChange={(e) => setTitre(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); ajouter() } }} />
    </section>
  )
}

function Supprimer({ tache, onFermer, erreur }) {
  const [confirmation, setConfirmation] = useState(false)
  const nb = (tache.enfants ?? []).length
  const supprimer = async () => {
    try {
      const { data } = await supprimerTache(tache.id)
      // « Annuler » défait le geste côté serveur (A7) ; sans `geste_id` (hors ligne, file), repli sur la restauration.
      const defaire = async () => {
        if (!data?.geste_id) { await restaurerTache(tache.id); return }
        const { data: bilan } = await annulerGeste(data.geste_id)
        const conflits = bilan?.conflits?.length ?? 0
        if (conflits > 0) annoncer(`Annulé, sauf ${conflits} modifiée${conflits > 1 ? 's' : ''} depuis.`)
      }
      proposerAnnuler({ message: 'Supprimée', onAnnuler: defaire })
      onFermer?.()
    } catch (err) {
      erreur('general', frenchError(err))
    }
  }
  if (!confirmation) {
    return <button type="button" className="bouton discret destructif" onClick={() => setConfirmation(true)}>Supprimer</button>
  }
  return (
    <div className="fiche-question" role="alertdialog" aria-label={`Supprimer « ${tache.titre} »`}>
      <p>{`Supprimer « ${tache.titre} » ?`}</p>
      {nb > 0 ? <p className="aide-champ">{nb === 1 ? '1 sous-tâche sera supprimée aussi.' : `${nb} sous-tâches seront supprimées aussi.`}</p> : null}
      <div className="carte-actions">
        <button type="button" className="bouton second destructif" onClick={supprimer}>{`Supprimer « ${tache.titre} »`}</button>
        <button type="button" className="bouton second" onClick={() => setConfirmation(false)}>Annuler</button>
      </div>
    </div>
  )
}

function Lien({ lien }) {
  if (!lien) return null
  const message = ETATS_LIEN[lien.etat]
  return (
    <p className="fiche-lien">
      <LienIcone className="i i-16" aria-hidden="true" />
      {message ? <span>{message}</span> : <a href={lien.url}>{`Lié à : ${lien.libelle}`}</a>}
    </p>
  )
}

export default function FichePlus({ tache, aujourdhui, ecrire, patcher, erreur, erreurs, annulable, charger, onFermer }) {
  const [duree2, setDuree] = useState(null)
  const minutes = duree2 ?? (tache.estimation_minutes ?? '')

  const abandonner = async () => {
    const r = await ecrire(() => trancherTache(tache.id, { choix: 'abandonner' }), 'general', undefined, true)
    if (r) { annulable('Abandonnée', r.data?.geste_id); onFermer?.() }
  }
  const enregistrerDuree = () => {
    if (duree2 === null) return
    const valeur = String(duree2).trim() === '' ? null : Number(duree2)
    patcher({ estimation_minutes: valeur }, 'duree').then((r) => { if (r) setDuree(null) })
  }

  return (
    <div className="fiche-plus">
      <Rappel tache={tache} aujourdhui={aujourdhui} ecrire={ecrire} annulable={annulable} />
      {erreurs.rappel ? <p className="erreur-champ" role="alert">{erreurs.rappel}</p> : null}
      <Repeter tache={tache} aujourdhui={aujourdhui} ecrire={ecrire} patcher={patcher} erreur={erreur} />
      {erreurs.repeter ? <p className="erreur-champ" role="alert">{erreurs.repeter}</p> : null}

      <div className="fiche-champ">
        <label className="fiche-ligne" htmlFor="fiche-duree">
          <span className="fiche-etiquette">{`Durée${tache.estimation_minutes ? ` · ${duree(tache.estimation_minutes)}` : ''}`}</span>
          <input
            id="fiche-duree"
            type="number"
            step="any"
            inputMode="numeric"
            className="champ-discret chiffres"
            placeholder="min"
            value={minutes}
            onChange={(e) => setDuree(e.target.value)}
            onBlur={enregistrerDuree}
          />
        </label>
        {erreurs.duree ? <p className="erreur-champ" role="alert">{erreurs.duree}</p> : null}
      </div>

      <Attente tache={tache} ecrire={ecrire} patcher={patcher} erreur={erreur} />
      {erreurs.attente ? <p className="erreur-champ" role="alert">{erreurs.attente}</p> : null}

      <div className="fiche-champ">
        <div className="fiche-ligne">
          <span className="fiche-etiquette">Jalon</span>
          <button type="button" className="interrupteur" role="switch" aria-checked={Boolean(tache.jalon)} aria-label="Jalon"
            onClick={() => patcher({ jalon: !tache.jalon }, 'jalon')} />
        </div>
        <div className="fiche-ligne">
          <span className="fiche-etiquette">Confidentielle</span>
          <button type="button" className="interrupteur" role="switch" aria-checked={Boolean(tache.confidentiel)} aria-label="Confidentielle"
            onClick={() => patcher({ confidentiel: !tache.confidentiel }, 'confidentiel')} />
        </div>
      </div>

      <Lien lien={tache.lien} />
      <SousTaches tache={tache} charger={charger} erreur={erreur} />
      {erreurs.sous_taches ? <p className="erreur-champ" role="alert">{erreurs.sous_taches}</p> : null}

      <div className="carte-actions">
        <button type="button" className="bouton discret" onClick={abandonner}>Abandonner</button>
        <Supprimer tache={tache} onFermer={onFermer} erreur={erreur} />
      </div>
    </div>
  )
}
