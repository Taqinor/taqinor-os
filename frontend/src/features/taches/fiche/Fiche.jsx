import { useCallback, useEffect, useRef, useState } from 'react'
import { Plus, X } from 'lucide-react'

import { frenchError } from '../../../lib/frenchError'
import {
  ajouterPoint, annulerGeste, classerErreur, creerProjet, lireTache, listerTousLesProjets, marquerEssentiel,
  modifierPoint, modifierReglages, modifierTache, planifierTache, repeterRappel, retirerPoint, rouvrirTache, terminerTache,
} from '../../../api/tachesApi'
import { proposerAnnuler } from '../lib/gestes'
import { aujourdhuiIso, heure, jourCourt, jourNomme } from '../lib/textes'
import BandeauConflit from '../ui/BandeauConflit'
import FichePlus from './FichePlus'
import CaseRonde from '../ui/CaseRonde'
import Etoile from '../ui/Etoile'
import FeuilleACrans from '../ui/FeuilleACrans'
import SelecteurProjet from '../ui/SelecteurProjet'
import SelecteurQuand, { ajouterJours } from '../ui/SelecteurQuand'

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
  projet_id: 'projet', essentielle: 'essentielle', essentielles: 'essentielle', libelle: 'checklist',
}
const PRIORITES = [['Basse', 1], ['Moyenne', 2], ['Haute', 3]]

/** `{champ: [messages]}` d'un 400 → `{ champDeLaFiche: premier message }` (le reste : `general`). */
function erreursParChamp(champs) {
  const sortie = {}
  Object.entries(champs ?? {}).forEach(([cle, liste]) => {
    const message = Array.isArray(liste) && typeof liste[0] === 'string' ? liste[0] : ''
    if (message) sortie[CHAMP_DE_ERREUR[cle] ?? 'general'] = message
  })
  return sortie
}

const sansCle = (objet, cle) => Object.fromEntries(Object.entries(objet).filter(([k]) => k !== cle))

const texteQuand = (t, aujourdhui) => {
  if (t.quelque_jour) return 'En réserve'
  if (!t.jour_prevu) return 'Sans jour'
  const jour = t.moment === 'soir' ? 'ce soir' : jourCourt(t.jour_prevu, aujourdhui)
  return t.heure_debut ? `${jour} · ${heure(t.heure_debut)}` : jour
}

function Erreur({ id, message }) {
  return message ? <p id={id} className="erreur-champ" role="alert">{message}</p> : null
}

function Ligne({ etiquette, valeur, ouvert, onBasculer, erreur, idErreur, enfants }) {
  return (
    <div className="fiche-champ">
      <button type="button" className="fiche-ligne" aria-expanded={ouvert} aria-describedby={erreur ? idErreur : undefined} onClick={onBasculer}>
        <span className="fiche-etiquette">{etiquette}</span>
        <span className="fiche-valeur chiffres">{valeur}</span>
      </button>
      <Erreur id={idErreur} message={erreur} />
      {ouvert ? enfants : null}
    </div>
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
    } catch (err) {
      onChange(points)
      onErreur('checklist', frenchError(err))
    }
  }

  return (
    <div className="fiche-checklist">
      {points.map((point) => (
        <div key={point.id} className="fiche-point">
          <CaseRonde coche={Boolean(point.fait)} libelle={`${point.fait ? 'Rouvrir' : 'Fait'} : ${point.libelle}`} onBasculer={(suivant) => basculer(point, suivant)} />
          <span className={point.fait ? 'titre faite' : 'titre'}>{point.libelle}</span>
          <button type="button" className="bouton-icone" aria-label={`Retirer le point : ${point.libelle}`} onClick={() => retirer(point)}>
            <X className="i i-16" aria-hidden="true" />
          </button>
        </div>
      ))}
      <label className="fiche-ajout">
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
      </label>
    </div>
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
  const courant = useRef(id)

  // lecture (et relecture après un « Annuler ») : la réponse n'est gardée que pour la fiche encore ouverte
  const charger = useCallback(() => lireTache(id)
    .then((r) => { if (courant.current === id) { setTache(r.data); setEchec('') } })
    .catch((err) => { if (courant.current === id) setEchec(classerErreur(err).code === 'introuvable' ? 'Introuvable.' : frenchError(err)) })
    .finally(() => { if (courant.current === id) setChargement(false) }), [id])

  useEffect(() => { courant.current = id; charger() }, [id, charger])

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
    onAnnuler: geste ? async () => { await annulerGeste(geste); await charger() } : undefined,
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
            {conflit ? <BandeauConflit onGarder={garderLaMienne} onPrendre={prendreLautre} /> : null}
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

            <Ligne
              etiquette="Quand je la fais"
              valeur={texteQuand(tache, aujourdhui)}
              ouvert={ouvert === 'quand'}
              onBasculer={() => setOuvert((o) => (o === 'quand' ? '' : 'quand'))}
              erreur={erreurs.quand}
              idErreur="fiche-err-quand"
              enfants={(
                <SelecteurQuand
                  valeur={{ jour_prevu: tache.jour_prevu, moment: tache.moment, heure_debut: tache.heure_debut, quelque_jour: tache.quelque_jour }}
                  aujourdhui={aujourdhui}
                  reporterA={lendemain}
                  onChoisir={planifier}
                />
              )}
            />
            {avertissements.map((a) => <p key={a.code} className="apercu-note">{a.message}</p>)}

            <div className="fiche-champ">
              <label className="fiche-ligne" htmlFor="fiche-echeance">
                <span className="fiche-etiquette">Échéance</span>
                <input
                  id="fiche-echeance"
                  type="date"
                  className="champ-discret chiffres"
                  value={tache.echeance ?? ''}
                  onChange={(e) => patcher({ echeance: e.target.value || null }, 'echeance')}
                />
              </label>
              <Erreur message={erreurs.echeance} />
            </div>

            <Ligne
              etiquette="Projet"
              valeur={tache.projet ? tache.projet.nom : 'Sans projet'}
              ouvert={ouvert === 'projet'}
              onBasculer={ouvrirProjet}
              erreur={erreurs.projet}
              idErreur="fiche-err-projet"
              enfants={<SelecteurProjet projets={projets ?? []} valeur={tache.projet?.id ?? null} sansProjet onChoisir={choisirProjet} onNouveau={nouveauProjet} />}
            />

            <div className="fiche-champ">
              <div className="fiche-ligne">
                <span className="fiche-etiquette">Priorité</span>
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
              <Erreur message={erreurs.priorite} />
            </div>

            <div className="fiche-champ">
              <div className="fiche-ligne">
                <span className="fiche-etiquette">Essentielle</span>
                <Etoile active={Boolean(tache.essentielle)} onBasculer={essentielle} titre={tache.titre} />
              </div>
              <Erreur message={erreurs.essentielle} />
            </div>

            <div className="fiche-champ">
              <label className="fiche-etiquette" htmlFor="fiche-notes">Notes</label>
              <textarea
                id="fiche-notes"
                className="saisie-champ fiche-notes"
                rows={3}
                aria-invalid={erreurs.notes ? true : undefined}
                value={notes}
                onChange={(e) => setSaisie((s) => ({ ...s, notes: e.target.value }))}
                onBlur={() => enregistrerTexte('notes')}
              />
              <Erreur message={erreurs.notes} />
            </div>

            <div className="fiche-champ">
              <span className="fiche-etiquette">Check-list</span>
              <CheckList
                tache={tache}
                onChange={(points) => (points ? setTache((t) => ({ ...t, elements_checklist: points })) : charger())}
                onErreur={erreur}
              />
              <Erreur message={erreurs.checklist} />
            </div>

            <button type="button" className="fiche-ligne" aria-expanded={plusOuvert} onClick={() => setPlusOuvert((v) => !v)}>
              <span className="fiche-etiquette">Plus</span>
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
              />
            ) : null}
            <Erreur message={erreurs.general} />
          </div>
        ) : null}
        {tache ? (
          <div className="feuille-pied">
            <button type="button" className="bouton second" onClick={() => reporter(lendemain)}>
              {`Reporter à ${jourNomme(lendemain, aujourdhui)}`}
            </button>
            <button type="button" className="bouton plein large" onClick={fait ? rouvrir : terminer}>
              {fait ? 'Rouvrir' : 'Fait'}
            </button>
          </div>
        ) : null}
      </FeuilleACrans>
    </div>
  )
}
