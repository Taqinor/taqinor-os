import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import * as client from '../../../api/tachesApi'
import { frenchError } from '../../../lib/frenchError'
import CaseRonde from '../ui/CaseRonde'
import SelecteurProjet from '../ui/SelecteurProjet'
// Relecture finale n° 1 — la carte de collage lit et envoie une liste comme l'écran de collage (regles.md §1.10) :
// mêmes puces, même raison d'une ligne décochée, même choix des lignes à créer.
import { PucesLues, noteDeLigne } from '../ui/ApercuListe'
import { phraseAlerte } from '../ui/ChampSaisie'
import { lignesACreer } from '../saisie/ColleListes'
import { accord, duree, heure, jourCourt, jourNomme } from '../lib/textes'
import { tempsTexte } from '../aujourdhui/Progression'

/* ============================================================================
   TCH117 + TCH165 — Les cartes « Tâches » du Copilote, rendues DIRECTEMENT (sans passer par
   `CarteResultat`) : `ma_journee`, `plan_propose`, `liste_taches`, `tache` (écho ou écriture),
   `capture_apercu`, `rythme`, `plan_projet`, `projet`, `revue_semaine`, `priorites`, `point`.
   `carte.donnees` = le corps JSON de la route qui l'a servie (`contract_samples/*.json`) : rien
   n'est recalculé ici, un constat affiché vient du serveur ou n'est pas affiché.
   Maquette : docs/taches/maquettes/copilote.html. Textes : reference/textes.md §5.2-§5.7.
   Un geste d'écriture se confirme sous la ligne, avec « Annuler » (`gestes/{id}/annuler/`) ;
   une erreur s'affiche sous le geste fautif (jamais un toast : le panneau n'est pas la coquille).
   ========================================================================== */

const LIBRE = 'libre'

// F3 acceptation ERR 5 (a) — le cadre de la carte (posé par le panneau, `CartesDuMessage`) : « attente » tant que
// la carte attend le doigt (cadre « proposition »), « fait » une fois son geste principal fait ou pour une lecture
// (cadre « résultat »), « laisse » quand il l'a laissée. Le geste principal de la carte le signale.
const EtatDuCadre = createContext(() => {})
// ERR 5 (b) — une CRÉATION validée au doigt sur une carte du Copilote est une écriture de l'assistant (A5).
const DEPUIS_LA_CARTE = { carteAssistant: true }

/** Un geste d'écriture : état occupé, erreur sous le geste, message « fait » avec « Annuler ». `principal` :
 *  le geste qui termine la carte (son cadre passe de « proposition » à « résultat »). */
function useGeste(initial = null, { principal = false } = {}) {
  const changerCadre = useContext(EtatDuCadre)
  const [etat, setEtat] = useState({ occupe: false, erreur: '', fait: initial })
  const lancer = async (appel, message) => {
    setEtat({ occupe: true, erreur: '', fait: null })
    try {
      const { data } = await appel()
      // `message` peut se lire sur la réponse (« {n} tâches créées » : le nombre que le serveur a créé).
      const dit = typeof message === 'function' ? message(data) : message
      setEtat({ occupe: false, erreur: '', fait: { message: dit, geste: data?.geste_id ?? null } })
      if (principal) changerCadre('fait')
      return data
    } catch (err) {
      setEtat({ occupe: false, erreur: frenchError(err), fait: null })
      return null
    }
  }
  const annuler = async () => {
    const geste = etat.fait?.geste
    if (!geste) return
    setEtat((e) => ({ ...e, occupe: true, erreur: '' }))
    try {
      await client.annulerGeste(geste)
      setEtat({ occupe: false, erreur: '', fait: { message: 'Annulé', geste: null } })
    } catch (err) {
      setEtat((e) => ({ ...e, occupe: false, erreur: frenchError(err, "L'annulation a échoué.") }))
    }
  }
  return { ...etat, lancer, annuler }
}

function Retour({ geste }) {
  return (
    <>
      {geste.fait ? (
        <p className="section-sous" role="status">
          {geste.fait.message}
          {geste.fait.geste ? (
            <>
              {' · '}
              <button type="button" className="bouton lien" disabled={geste.occupe} onClick={geste.annuler}>Annuler</button>
            </>
          ) : null}
        </p>
      ) : null}
      {geste.erreur ? <p className="section-sous alerte" role="alert">{geste.erreur}</p> : null}
    </>
  )
}

/** Tête d'une carte du Copilote (maquette copilote.html : `.ep-carte-ia-tete`, styles/taches/coeur.css). */
function Tete({ titre, chiffres = '' }) {
  return (
    <div className="ep-carte-ia-tete">
      <h3 className="seg-tete">{titre}</h3>
      {chiffres ? <span className="chiffres">{chiffres}</span> : null}
    </div>
  )
}

function Projet({ projet }) {
  if (!projet) return null
  return <span data-p={projet.couleur}><i className="point" /><span className="projet-nom">{projet.nom}</span></span>
}

/** Une tâche du Copilote : titre, sa raison (ou son explication), son projet ; `fin` = gestes de droite. */
function LigneCarte({ item, rang = null, fin = null, bas = null, case_ = null }) {
  const raison = item.raison?.texte || item.explication || ''
  return (
    <div className="ligne" role="listitem">
      {case_}
      <div className="ligne-corps">
        <div className="titre">{rang !== null ? <span className="chiffres">{`${rang}. `}</span> : null}{item.titre}</div>
        <div className="meta">
          {raison ? <span>{raison}</span> : null}
          <Projet projet={item.projet} />
        </div>
        {bas}
      </div>
      {fin ? <div className="ligne-fin">{fin}</div> : null}
    </div>
  )
}

const cleItem = (item) => `${item.type}:${item.id}`
const lignesDe = (items) => items.map((it) => ({ type: it.type, id: it.id }))

// ── ma_journee ────────────────────────────────────────────────────────────────

function CaseJournee({ item }) {
  const [fait, setFait] = useState(item.statut === 'fait')
  if (item.type !== 'tache') return null
  return (
    <CaseRonde
      coche={fait} titre={item.titre}
      onBasculer={async (suivant) => {
        // relecture adverse F4 n° 4 — décocher ROUVRE (terminer une faite ne fait rien : la case mentait) ; un échec
        // rejette, et `CaseRonde` remet la case comme avant le toucher
        if (suivant) await client.terminerTache(item.id, { lock_version: item.lock_version })
        else await client.rouvrirTache(item.id)
        setFait(suivant)
      }}
    />
  )
}

function CarteMaJournee({ donnees }) {
  const lot = useGeste()
  const items = [...(donnees.essentiel ?? []), ...(donnees.journee ?? [])]
  // D-V1 : une essentielle faite est aussi servie dans `essentiel` (regles.md §4.1) — le report groupé ne la prend jamais
  const ids = items.filter((it) => it.type === 'tache' && it.statut !== 'fait').map((it) => it.id)
  const p = donnees.progression
  const objectif = donnees.objectif
  const chiffres = p ? (objectif?.mode === LIBRE || !objectif?.nb ? `${p.faites} faites` : `${p.faites} sur ${objectif.nb}`) : ''
  return (
    <div role="group" aria-label="Ma journée">
      <Tete titre="Ma journée" chiffres={chiffres} />
      {items.length === 0 ? <p className="section-sous">Rien de prévu aujourd&apos;hui.</p> : (
        <div className="liste" role="list">
          {items.map((it) => (
            <LigneCarte key={cleItem(it)} item={it} case_={<CaseJournee item={it} />}
              fin={it.type === 'tache' ? <Link className="bouton lien" to={`/taches/aujourdhui?tache=${it.id}`}>Ouvrir</Link> : null} />
          ))}
        </div>
      )}
      {ids.length > 0 && donnees.prochain_jour_ouvre ? (
        <div className="propose-actions ep-carte-ia-pied">
          <button type="button" className="bouton second" disabled={lot.occupe}
            onClick={() => lot.lancer(() => client.traiterLot({ ids, action: 'planifier', valeurs: { jour_prevu: donnees.prochain_jour_ouvre } }),
              `Reportées à ${jourNomme(donnees.prochain_jour_ouvre, donnees.jour)}`)}>
            {`Tout au prochain jour travaillé (${ids.length})`}
          </button>
        </div>
      ) : null}
      <Retour geste={lot} />
    </div>
  )
}

// ── plan_propose ──────────────────────────────────────────────────────────────

function BoutonGarder({ lignes, jour, geste }) {
  const n = lignes.length
  return (
    <button type="button" className="bouton second" disabled={geste.occupe || geste.fait !== null}
      onClick={() => geste.lancer(() => client.garderJournee({ jour, mode: 'express', lignes: lignesDe(lignes), essentielles: [], triage: [] }),
        accord(n, "prévue aujourd'hui", "prévues aujourd'hui"))}>
      {n >= 2 ? `Garder ces ${n}` : 'Garder celle-ci'}
    </button>
  )
}

function CartePlanPropose({ donnees }) {
  const geste = useGeste(null, { principal: true })
  // F3 acceptation ERR 2 — une seule règle : les lignes du Proposé (`proposition` = `pour_objectif` du moteur, celles
  // que l'écran Aujourd'hui garde par « Garder ces N »), sans filtre propre à la carte.
  const lignes = (donnees.proposition ?? []).map((l) => l.item)
  const objectif = donnees.objectif?.nb
  const chiffres = objectif ? `${lignes.length} · objectif ${objectif}` : `${lignes.length}`
  return (
    <div role="group" aria-label="Proposé pour aujourd'hui">
      <Tete titre="Proposé pour aujourd'hui" chiffres={chiffres} />
      {lignes.length === 0 ? <p className="section-sous">Objectif couvert par ce que tu as gardé.</p> : (
        // Passe visuelle n° 50 — chaque ligne a sa case ronde, comme le Proposé de la maquette (copilote.html).
        <div className="liste" role="list">
          {lignes.map((it) => <LigneCarte key={cleItem(it)} item={it} case_={<CaseJournee item={it} />} />)}
        </div>
      )}
      {lignes.length > 0 ? <div className="propose-actions ep-carte-ia-pied"><BoutonGarder lignes={lignes} jour={donnees.jour} geste={geste} /></div> : null}
      <Retour geste={geste} />
    </div>
  )
}

// ── liste_taches, projet, revue_semaine ───────────────────────────────────────

function CarteListeTaches({ donnees }) {
  const taches = donnees.taches ?? []
  const projets = donnees.projets ?? []
  return (
    <div role="group" aria-label="Tes tâches">
      <Tete titre="Tes tâches" chiffres={String(taches.length + projets.length)} />
      {taches.length + projets.length === 0 ? <p className="section-sous">Rien trouvé.</p> : null}
      <div className="liste" role="list">
        {projets.map((pr) => (
          <div key={`p${pr.id}`} className="ligne" role="listitem">
            <div className="ligne-corps"><div className="titre"><Projet projet={pr} /></div></div>
            <div className="ligne-fin"><Link className="bouton lien" to={`/taches/projets/${pr.id}`}>Ouvrir</Link></div>
          </div>
        ))}
        {taches.map((it) => (
          <LigneCarte key={cleItem(it)} item={it}
            fin={<Link className="bouton lien" to={`/taches/aujourdhui?tache=${it.id}`}>Ouvrir</Link>} />
        ))}
      </div>
    </div>
  )
}

function CarteProjet({ donnees }) {
  const { projet, avancement, prochaine_action: prochaine } = donnees
  return (
    <div role="group" aria-label={projet.nom}>
      <Tete titre={projet.nom} chiffres={avancement ? `${avancement.faites} sur ${avancement.total}` : ''} />
      {projet.objectif ? <p className="section-sous">{projet.objectif}</p> : null}
      {(projet.sante ?? []).map((s) => <p key={s.code} className="section-sous">{s.phrase}</p>)}
      {prochaine ? <div className="liste" role="list"><LigneCarte item={prochaine} /></div> : null}
      <div className="propose-actions ep-carte-ia-pied">
        <Link className="bouton second" to={`/taches/projets/${projet.id}`}>Ouvrir</Link>
      </div>
    </div>
  )
}

function CarteRevueSemaine({ donnees }) {
  const cartes = donnees.cartes ?? []
  return (
    <div role="group" aria-label="Revue de la semaine">
      <Tete titre="Revue de la semaine" />
      {donnees.bilan_semaine?.texte ? <p className="section-sous">{donnees.bilan_semaine.texte}</p> : null}
      <div className="liste" role="list">
        {cartes.map((c) => (
          <div key={c.projet.id} className="ligne" role="listitem">
            <div className="ligne-corps">
              <div className="titre"><Projet projet={c.projet} /></div>
              {(c.projet.sante ?? []).map((s) => <div key={s.code} className="meta"><span>{s.phrase}</span></div>)}
            </div>
          </div>
        ))}
      </div>
      <div className="propose-actions ep-carte-ia-pied"><Link className="bouton second" to="/taches/revue">Ouvrir la revue</Link></div>
    </div>
  )
}

// ── tache : écho ou écriture ──────────────────────────────────────────────────

const ECHOS = {
  renommer: { libelle: 'Renommer', appel: (t, p) => client.modifierTache(t.id, { titre: p.apres, lock_version: t.lock_version }), fait: 'Renommée' },
  abandonner: { libelle: 'Abandonner', appel: (t) => client.trancherTache(t.id, { choix: 'abandonner' }), fait: 'Abandonnée' },
  supprimer: { libelle: 'Supprimer', appel: (t) => client.supprimerTache(t.id), fait: 'Supprimée' },
}

function CarteEcho({ tache, proposition }) {
  const geste = useGeste(null, { principal: true })
  const changerCadre = useContext(EtatDuCadre)
  const [laisse, setLaisse] = useState(false)
  const echo = ECHOS[proposition.geste]
  return (
    <div role="group" aria-label={tache.titre}>
      <Tete titre={tache.titre} />
      {proposition.avant != null && proposition.apres != null ? (
        <p className="section-sous">{`${proposition.avant} → ${proposition.apres}`}</p>
      ) : null}
      {echo && !geste.fait && !laisse ? (
        <div className="propose-actions ep-carte-ia-pied">
          <button type="button" className="bouton second" disabled={geste.occupe}
            onClick={() => geste.lancer(() => echo.appel(tache, proposition), echo.fait)}>{echo.libelle}</button>
          <button type="button" className="bouton lien" disabled={geste.occupe} onClick={() => { setLaisse(true); changerCadre('laisse') }}>Laisser</button>
        </div>
      ) : null}
      {laisse ? <p className="section-sous" role="status">Laissée comme elle est.</p> : null}
      <Retour geste={geste} />
    </div>
  )
}

// Critique serveur n° 7 — un refus au champ (5 rappels au plus, heure sans échéance…) est dit SOUS la carte (`Retour`),
// le message du serveur, sans le toast du pont par-dessus.
const SOUS_LA_CARTE = { erreurSousLeChamp: true }

// A5 — une écriture du Copilote arrivée dans un tour où un texte tiers est entré : le relais n'a RIEN
// écrit, la carte porte le corps de la requête (`proposition.corps`, contrat `ecriture_a_valider`) et le
// doigt la valide. « Modifier » / « Laisser » : textes.md §5.5. Les autres écritures gardent le libellé
// du registre de l'agent (`proposition.libelle`) sur leur bouton.
// Revue F3 n° 2 : la carte DIT chaque champ du corps avant le doigt (`lignesDuCorps`) et le bouton
// envoie ce corps-là, le même objet ; un champ qu'elle ne sait pas dire se montre tel quel (clé : valeur).
// eslint-disable-next-line react-refresh/only-export-components -- table parcourue par la garde du test (revue F3 n° 2)
export const ECRITURES_A_VALIDER = {
  'taches.tache.modifier': { bouton: 'Modifier', fait: () => 'Modifiée', appel: (t, c) => client.modifierTache(t.id, c, SOUS_LA_CARTE) },
  'taches.tache.creer': { fait: () => 'Ajoutée', appel: (t, c) => client.creerTache(c, DEPUIS_LA_CARTE) },
  'taches.tache.terminer': { fait: () => 'Faite', appel: (t, c) => client.terminerTache(t.id, c) },
  'taches.tache.planifier': {
    fait: (c) => (c.jour_prevu ? `Prévue ${jourNomme(c.jour_prevu)}` : ''), appel: (t, c) => client.planifierTache(t.id, c),
  },
  'taches.rappel.poser': {
    fait: (c) => (c.jour ? `Rappel posé ${jourNomme(c.jour)} à ${heure(c.heure)}` : ''),
    appel: (t, c) => client.poserRappel(t.id, c, SOUS_LA_CARTE),
  },
  'taches.projet.creer': { fait: () => '', appel: (t, c) => client.creerProjet(c, DEPUIS_LA_CARTE) },
  'taches.rythme.regler': { fait: () => '', appel: (t, c) => client.poserMode(c) },
  'taches.preference.noter': { fait: () => '', appel: (t, c) => client.poserPreference(c) },
}
const PRIORITE_DITE = { 3: 'haute', 2: 'moyenne', 1: 'basse', 0: 'aucune' }

function ligneDuChangement({ champ, avant, apres }, titre) {
  if (champ === 'priorite') return `Priorité de « ${titre} » : ${PRIORITE_DITE[avant] ?? ''} → ${PRIORITE_DITE[apres] ?? ''}`
  if (champ === 'echeance') return `Échéance : ${avant ? jourNomme(avant) : 'aucune'} → ${apres ? jourNomme(apres) : 'aucune'}`
  return `Projet : ${avant?.nom ?? 'sans projet'} → ${apres?.nom ?? 'sans projet'}`
}

// Les mots de chaque champ : puces de la saisie (textes.md §2.3 : « Matin » / « Après-midi » / « Ce soir »,
// « échéance {jour} [· {HH:MM}] », « Plus tard », « Nouveau projet : {nom} », « Priorité haute »,
// « Rappel {jour} {HH:MM} »), champs de la fiche (§2.4 : Quand, Heure, Durée, « Lié à : »), Mon rythme
// (§2.11 : modes, « Objectif du jour : {n} », « Plus » / « Moins »). Une valeur qui n'a pas la forme
// attendue n'est jamais « arrangée » : elle tombe dans le rendu tel quel.
const MOMENT_DIT = { matin: 'Matin', apres_midi: 'Après-midi', soir: 'Ce soir' }
const SENS_DIT = { plus: 'Plus', moins: 'Moins' }
// `lock_version` : le numéro de version que le serveur compare ; il n'écrit rien et n'est pas dit.
const CHAMPS_TECHNIQUES = new Set(['lock_version'])
const estJour = (v) => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v)
const estHeure = (v) => typeof v === 'string' && /^\d{2}:\d{2}(:\d{2})?$/.test(v)
const estTexte = (v) => typeof v === 'string' && v.trim() !== ''
const prioriteDite = (v) => (Number.isInteger(v) && v in PRIORITE_DITE ? `Priorité ${PRIORITE_DITE[v]}` : '')
const brut = (cle, v) => `${cle} : ${JSON.stringify(v) ?? String(v)}`

function nouveauProjetDit(p) {
  if (!p || typeof p !== 'object' || !estTexte(p.nom)) return ''
  if (Object.keys(p).some((k) => k !== 'nom' && k !== 'priorite')) return ''
  if (p.priorite === undefined) return `Nouveau projet : ${p.nom}`
  const priorite = prioriteDite(p.priorite)
  return priorite ? `Nouveau projet : ${p.nom} · ${priorite}` : ''
}

function lienDit(l) {
  if (!l || typeof l !== 'object' || Object.keys(l).length !== 2 || !estTexte(l.cible) || !Number.isInteger(l.id)) return ''
  return `Lié à : ${l.cible} ${l.id}`
}

// Une règle par champ (ou groupe de champs dits ensemble) : elle ne s'applique que si tous ses champs sont
// dans le corps, et rend '' quand la valeur n'a pas la forme attendue. Les groupes passent d'abord.
const DIRE_CHAMPS = [
  [['echeance', 'echeance_heure'], (c) => (estJour(c.echeance) && estHeure(c.echeance_heure)
    ? `Échéance : ${jourCourt(c.echeance)} · ${heure(c.echeance_heure)}` : '')],
  [['jour', 'heure'], (c) => (estJour(c.jour) && estHeure(c.heure) ? `Rappel ${jourCourt(c.jour)} ${heure(c.heure)}` : '')],
  [['cle', 'valeur'], (c) => (estTexte(c.cle)
    ? `${c.cle} : ${typeof c.valeur === 'string' ? c.valeur : JSON.stringify(c.valeur)}` : '')],
  [['echeance'], (c) => (estJour(c.echeance) ? `Échéance : ${jourCourt(c.echeance)}` : '')],
  [['heure'], (c) => (estHeure(c.heure) ? `Rappel ${heure(c.heure)}` : '')],
  [['jour_prevu'], (c) => (estJour(c.jour_prevu) ? `Quand : ${jourCourt(c.jour_prevu)}` : '')],
  [['moment'], (c) => MOMENT_DIT[c.moment] ?? ''],
  [['heure_debut'], (c) => (estHeure(c.heure_debut) ? `Heure : ${heure(c.heure_debut)}` : '')],
  [['estimation_minutes'], (c) => (Number.isInteger(c.estimation_minutes) && duree(c.estimation_minutes)
    ? `Durée : ${duree(c.estimation_minutes)}` : '')],
  [['priorite'], (c) => prioriteDite(c.priorite)],
  [['quelque_jour'], (c) => (c.quelque_jour === true ? 'Plus tard' : '')],
  [['nom'], (c) => (estTexte(c.nom) ? `Nouveau projet : ${c.nom}` : '')],
  [['nouveau_projet'], (c) => nouveauProjetDit(c.nouveau_projet)],
  [['lien'], (c) => lienDit(c.lien)],
  [['mode'], (c) => LIBELLES_MODE[c.mode] ?? ''],
  [['objectif'], (c) => (Number.isInteger(c.objectif) ? `Objectif du jour : ${c.objectif}` : '')],
  [['sens'], (c) => (SENS_DIT[c.sens] ? `Changer d'objectif : ${SENS_DIT[c.sens]}` : '')],
]

// `taches.tache.modifier` : un changement (avant → après, servi par le relais) dit le champ du corps
// seulement si son « après » EST la valeur envoyée ; sinon le champ se dit aussi tel quel.
const CHAMP_DU_CHANGEMENT = { priorite: 'priorite', echeance: 'echeance', projet: 'projet_id' }
function changementDit(c, corps) {
  const cle = CHAMP_DU_CHANGEMENT[c.champ]
  if (!cle || !(cle in corps)) return false
  return cle === 'projet_id' ? c.apres?.id === corps.projet_id : c.apres === corps[cle]
}

/**
 * Ce que la carte dit du corps qu'elle enverra : `[{ cles, texte, brut, changement }]`, dans l'ordre
 * changements → champs lisibles → champs dits tels quels. Tout champ du corps (hors `lock_version`) est
 * dans au moins une ligne ; `titre` est dit par la tête de la carte quand aucune tâche n'est visée.
 */
// eslint-disable-next-line react-refresh/only-export-components -- helper pur co-localisé, lu par la garde du test
export function lignesDuCorps(corps, changements = [], { titreEnTete = false, titreTache = '', projet = null } = {}) {
  const lignes = []
  const dits = new Set(CHAMPS_TECHNIQUES)
  if (titreEnTete) dits.add('titre')
  // Relecture finale n° 2 — le relais nomme le projet d'une création (`proposition.projet {id, nom}`) : « Projet :
  // {nom} » (textes.md §2.3) seulement si c'est bien le projet du corps ; sinon `projet_id` reste dit tel quel.
  if (Number.isInteger(corps.projet_id) && projet?.id === corps.projet_id && estTexte(projet?.nom)) {
    dits.add('projet_id')
    lignes.push({ cles: ['projet_id'], texte: `Projet : ${projet.nom}`, brut: false })
  }
  for (const c of changements) {
    const cle = CHAMP_DU_CHANGEMENT[c.champ]
    const exact = changementDit(c, corps)
    if (exact) dits.add(cle)
    lignes.push({ cles: exact ? [cle] : [], texte: ligneDuChangement(c, titreTache), brut: false, changement: true })
  }
  for (const [cles, dire] of DIRE_CHAMPS) {
    if (cles.some((k) => !(k in corps) || dits.has(k))) continue
    const texte = dire(corps)
    if (!texte) continue
    cles.forEach((k) => dits.add(k))
    lignes.push({ cles, texte, brut: false })
  }
  for (const [cle, valeur] of Object.entries(corps)) {
    if (!dits.has(cle)) lignes.push({ cles: [cle], texte: brut(cle, valeur), brut: true })
  }
  return lignes
}

function CarteAValider({ tache, proposition }) {
  const geste = useGeste(null, { principal: true })
  const changerCadre = useContext(EtatDuCadre)
  const [laisse, setLaisse] = useState(false)
  const ecriture = ECRITURES_A_VALIDER[proposition.action_key]
  // UN objet : celui que les lignes disent est celui que le bouton envoie.
  const [corps] = useState(() => proposition.corps ?? {})
  const titreEnTete = !tache && estTexte(corps.titre)
  const titre = tache?.titre ?? (titreEnTete ? corps.titre : proposition.libelle)
  const lignes = lignesDuCorps(corps, proposition.changements ?? [], {
    titreEnTete, titreTache: tache?.titre ?? '', projet: proposition.projet,
  })
  return (
    <div role="group" aria-label={titre}>
      <Tete titre={titre} />
      {lignes.map((l, i) => (
        <p key={`${i}:${l.cles.join(',')}`} className="section-sous whitespace-pre-wrap break-words"
          data-brut={l.brut ? '' : undefined}>
          {l.texte}
        </p>
      ))}
      {ecriture && !geste.fait && !laisse ? (
        <div className="propose-actions ep-carte-ia-pied">
          <button type="button" className="bouton second" disabled={geste.occupe}
            onClick={() => geste.lancer(() => ecriture.appel(tache, corps), ecriture.fait(corps) || proposition.libelle)}>
            {ecriture.bouton ?? proposition.libelle}
          </button>
          <button type="button" className="bouton lien" disabled={geste.occupe} onClick={() => { setLaisse(true); changerCadre('laisse') }}>Laisser</button>
        </div>
      ) : null}
      {laisse ? <p className="section-sous" role="status">Laissée comme elle est.</p> : null}
      <Retour geste={geste} />
    </div>
  )
}

function CarteTache({ donnees }) {
  const { tache, proposition, avertissements } = donnees
  const geste = useGeste(donnees.geste_id ? { message: 'Modifiée', geste: donnees.geste_id } : null)
  if (proposition?.geste === 'ecrire') return <CarteAValider tache={tache} proposition={proposition} />
  if (proposition) return <CarteEcho tache={tache} proposition={proposition} />
  return (
    <div role="group" aria-label={tache.titre}>
      <Tete titre={tache.titre} />
      <div className="liste" role="list"><LigneCarte item={tache} /></div>
      {(avertissements ?? []).map((a) => <p key={a.code} className="section-sous">{a.message}</p>)}
      <Retour geste={geste} />
    </div>
  )
}

// ── capture_apercu, plan_projet ───────────────────────────────────────────────

// F3 acceptation ERR 4 — « Changer de projet » lit les projets du compte (`projets/`, toutes les pages) une fois,
// quand une ligne doit nommer un projet servi par son seul id ou qu'on ouvre le choix.
function useProjetsDuCompte(aLire) {
  const [etat, setEtat] = useState({ projets: null, erreur: '' })
  const lance = useRef(false)
  const lire = useCallback(() => {
    if (lance.current) return
    lance.current = true
    client.listerTousLesProjets()
      .then((projets) => setEtat({ projets: projets ?? [], erreur: '' }))
      .catch((err) => { lance.current = false; setEtat({ projets: null, erreur: frenchError(err) }) })
  }, [])
  useEffect(() => { if (aLire) lire() }, [aLire, lire])
  const ajouter = useCallback((projet) => setEtat((e) => ({ ...e, projets: [...(e.projets ?? []), projet] })), [])
  return { ...etat, lire, ajouter }
}

// Un projet né d'un collage est en priorité moyenne (textes.md §1 « Priorité », §2.3 « Moyenne par défaut »).
const PRIORITE_PROJET_NE = 2
const sansProjet = (champs) => Object.fromEntries(Object.entries(champs).filter(([k]) => k !== 'projet_id' && k !== 'nouveau_projet'))

/** Ce que la ligne dit de son projet (textes.md §2.3 et §5.2) ; un id que la liste ne nomme pas se montre tel quel. */
function projetDeLigne(champs, { projets, choisi, rangement }) {
  if (champs.nouveau_projet) return `Nouveau projet : ${champs.nouveau_projet.nom}`
  if (champs.projet_id == null) return 'Pas de projet évident : choisis-le.'
  const nom = (projets ?? []).find((p) => p.id === champs.projet_id)?.nom
  if (!nom) return projets === null ? '' : `projet_id : ${champs.projet_id}`
  return rangement && !choisi ? `Projet suggéré : ${nom}` : `Projet : ${nom}`
}

function CarteCaptureApercu({ donnees }) {
  const geste = useGeste(null, { principal: true })
  const [retirees, setRetirees] = useState([])
  const [choix, setChoix] = useState({}) // index → champs de projet choisis au doigt
  const [ouverte, setOuverte] = useState(null) // index de la ligne dont le choix de projet est ouvert
  const [erreurLigne, setErreurLigne] = useState({})
  const toutes = donnees.lignes ?? []
  // « Range ma liste » (`ids` d'À trier) : des tâches EXISTANTES, rangées par `taches/lot/` `deplacer`, jamais recréées.
  const rangement = toutes.some((l) => l.tache_id != null)
  const lignes = toutes.filter((l) => !retirees.includes(l.index))
  const champsDe = (l) => (choix[l.index] ? { ...sansProjet(l.champs ?? {}), ...choix[l.index] } : (l.champs ?? {}))
  const projets = useProjetsDuCompte(toutes.some((l) => l.champs?.projet_id != null))
  const choisir = (index, champs) => { setChoix((c) => ({ ...c, [index]: champs })); setOuverte(null) }
  const nouveauProjet = async (index, nom) => {
    const propre = String(nom ?? '').trim()
    if (!propre) return
    if (!rangement) { choisir(index, { nouveau_projet: { nom: propre, priorite: PRIORITE_PROJET_NE } }); return }
    try {
      const { data } = await client.creerProjet({ nom: propre, priorite: PRIORITE_PROJET_NE }, DEPUIS_LA_CARTE)
      choisir(index, { projet_id: data.id })
      projets.ajouter(data)
    } catch (err) {
      setErreurLigne((e) => ({ ...e, [index]: frenchError(err) }))
    }
  }
  const aRanger = lignes.filter((l) => champsDe(l).projet_id != null)
  // Un collage : la ligne décochée par le serveur (déjà faite, doublon) n'est ni créée ni comptée, les points en retrait
  // vont dans la check-list de leur tâche — la règle de l'écran de collage (`lignesACreer`), pas une seconde.
  // `client_id` : une clé PROPRE à cette carte (deux collages n'ont jamais la même ligne 0), tirée au premier toucher
  // et gardée pour un nouvel essai depuis la même carte.
  const cid = useRef(null)
  const decochee = (l) => !rangement && l.cochee === false
  const aEnvoyerAvec = (c) => (rangement ? [] : lignesACreer(
    { ...donnees, lignes: lignes.map((l) => ({ ...l, champs: champsDe(l) })) },
    { cochees: {}, titres: {}, enTache: {}, sousTaches: {} }, { cid: c }))
  const aEnvoyer = aEnvoyerAvec('')
  const ajouter = () => {
    cid.current = cid.current ?? `copilote:${client.nouvelleCle()}`
    return geste.lancer(() => client.saisieRapide({ lignes: aEnvoyerAvec(cid.current), apercu: false }, DEPUIS_LA_CARTE),
      accord(aEnvoyer.length, 'ajoutée'))
  }
  const ranger = () => geste.lancer(() => client.traiterLot({
    ids: aRanger.map((l) => l.tache_id), action: 'deplacer',
    valeurs: { par_tache: Object.fromEntries(aRanger.map((l) => [l.tache_id, { projet_id: champsDe(l).projet_id }])) },
  }), accord(aRanger.length, 'tâche rangée', 'tâches rangées'))
  const listeProjets = projets.projets ?? []
  return (
    <div role="group" aria-label="Ta liste rangée">
      <Tete titre="Ta liste rangée" chiffres={String(lignes.length)} />
      {lignes.length === 0 ? <p className="section-sous">Rien à ajouter.</p> : (
        <div className="liste" role="list">
          {lignes.map((l) => {
            const dit = projetDeLigne(champsDe(l), { projets: projets.projets, choisi: l.index in choix, rangement })
            return (
              <div key={l.index} className={decochee(l) ? 'ligne decochee' : 'ligne'} role="listitem">
                <div className="ligne-corps">
                  <div className="titre">{l.titre}</div>
                  {decochee(l) && noteDeLigne(l) ? <p className="apercu-note">{noteDeLigne(l)}</p> : null}
                  {(l.alertes ?? []).map(phraseAlerte).filter(Boolean).map((phrase) => <p key={phrase} className="apercu-note">{phrase}</p>)}
                  {/* Le projet se dit (et se change) à part : une puce de projet resterait vraie après « Changer de projet ». */}
                  <PucesLues jetons={(l.jetons ?? []).filter((j) => j.type !== 'projet')} />
                  {dit && !decochee(l) ? <div className="meta"><span>{dit}</span></div> : null}
                  {ouverte === l.index ? (
                    projets.projets === null ? (
                      <p className="section-sous" role={projets.erreur ? 'alert' : 'status'}>{projets.erreur || 'Chargement…'}</p>
                    ) : (
                      <SelecteurProjet projets={listeProjets} valeur={champsDe(l).projet_id ?? null} sansProjet={!rangement}
                        onChoisir={(id) => choisir(l.index, id == null ? {} : { projet_id: id })}
                        onNouveau={(nom) => nouveauProjet(l.index, nom)} />
                    )
                  ) : null}
                  {erreurLigne[l.index] ? <p className="section-sous alerte" role="alert">{erreurLigne[l.index]}</p> : null}
                  {/* Sous la ligne, comme les gestes des priorités : deux gestes à droite écrasaient le titre. */}
                  <div className="actions-priorite" hidden={decochee(l)}>
                    <button type="button" className="bouton lien" disabled={geste.fait !== null}
                      onClick={() => { projets.lire(); setOuverte((o) => (o === l.index ? null : l.index)) }}>
                      Changer de projet
                    </button>
                    <button type="button" className="bouton lien" disabled={geste.fait !== null}
                      onClick={() => setRetirees((r) => [...r, l.index])}>Retirer</button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
      {lignes.length > 0 ? (
        <div className="propose-actions ep-carte-ia-pied">
          {rangement ? (
            <button type="button" className="bouton second" disabled={geste.occupe || geste.fait !== null || aRanger.length === 0}
              onClick={ranger}>
              {`Tout ranger (${aRanger.length})`}
            </button>
          ) : (
            <button type="button" className="bouton second" disabled={geste.occupe || geste.fait !== null || aEnvoyer.length === 0}
              onClick={ajouter}>
              {`Tout ajouter (${aEnvoyer.length})`}
            </button>
          )}
        </div>
      ) : null}
      <Retour geste={geste} />
    </div>
  )
}

// `projet` ({id, lock_version}) est servi par `planification/apercu/` (planification_apercu.json) : sans lui (carte
// d'une réponse plus ancienne), « Tout ajouter » n'a pas de projet où écrire et n'est pas montré.
const projetPlanifiable = (projet) => Number.isInteger(projet?.id) && Number.isInteger(projet?.lock_version)

function CartePlanProjet({ donnees }) {
  const geste = useGeste(null, { principal: true })
  const [etapes, setEtapes] = useState(() => (donnees.sections ?? []).map((s, i) => ({
    nom: s.nom, taches: (s.taches ?? []).map((t, j) => ({ ...t, cle: `${i}:${j}` })),
  })))
  const [ouverte, setOuverte] = useState(null) // clé de la tâche dont « Changer d'étape » est ouvert
  const retirer = (cle) => setEtapes((es) => es.map((e) => ({ ...e, taches: e.taches.filter((t) => t.cle !== cle) })))
  const deplacer = (cle, vers) => {
    setEtapes((es) => {
      const tache = es.flatMap((e) => e.taches).find((t) => t.cle === cle)
      return es.map((e, i) => ({
        ...e, taches: i === vers ? [...e.taches.filter((t) => t.cle !== cle), tache] : e.taches.filter((t) => t.cle !== cle),
      }))
    })
    setOuverte(null)
  }
  const projet = donnees.projet
  const toutAjouter = () => geste.lancer(() => client.planifierProjet(projet.id, {
    sections: etapes.map((e) => ({ nom: e.nom, taches: e.taches.map((t) => Object.fromEntries(Object.entries(t).filter(([k]) => k !== 'cle'))) })),
    lock_version: projet.lock_version,
  }, DEPUIS_LA_CARTE), (data) => accord(data?.creees?.length ?? 0, 'tâche créée', 'tâches créées'))
  const fige = geste.fait !== null
  return (
    <div role="group" aria-label="Le projet en étapes">
      <Tete titre="Le projet en étapes" chiffres={String(etapes.length)} />
      {etapes.map((s, i) => (
        <div key={`${i}:${s.nom}`}>
          <p className="ep-carte-ia-etape">{s.nom}</p>
          <div className="liste" role="list">
            {s.taches.map((t) => (
              <div key={t.cle} className="ligne" role="listitem">
                <div className="ligne-corps">
                  <div className="titre">{t.titre}</div>
                  {(t.sous_taches ?? []).length > 0 ? <div className="meta"><span>{t.sous_taches.join(' · ')}</span></div> : null}
                  <div className="actions-priorite">
                    {etapes.length > 1 ? (
                      <button type="button" className="bouton lien" disabled={fige}
                        onClick={() => setOuverte((o) => (o === t.cle ? null : t.cle))}>Changer d&apos;étape</button>
                    ) : null}
                    <button type="button" className="bouton lien" disabled={fige} onClick={() => retirer(t.cle)}>Retirer</button>
                  </div>
                  {ouverte === t.cle ? (
                    <div className="actions-priorite" role="group" aria-label="Étapes">
                      {etapes.map((e, j) => (j === i ? null : (
                        <button key={`${j}:${e.nom}`} type="button" className="bouton discret" onClick={() => deplacer(t.cle, j)}>{e.nom}</button>
                      )))}
                    </div>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
      {projetPlanifiable(projet) ? (
        <div className="propose-actions ep-carte-ia-pied">
          <button type="button" className="bouton second" disabled={geste.occupe || fige} onClick={toutAjouter}>Tout ajouter</button>
        </div>
      ) : null}
      <Retour geste={geste} />
    </div>
  )
}

// ── rythme ────────────────────────────────────────────────────────────────────

const LIBELLES_MODE = { pousser: 'En faire plus', tenir: 'Garder ce rythme', libre: 'Sans objectif' }

function BoutonsReponse({ proposition }) {
  const geste = useGeste()
  if (!proposition) return null
  return (
    <div>
      <p className="section-sous">{proposition.texte}</p>
      {geste.fait ? null : (
        <div className="propose-actions ep-carte-ia-pied">
          {(proposition.boutons ?? []).map((b) => (
            <button key={b.reponse} type="button" className="bouton second" disabled={geste.occupe}
              onClick={() => geste.lancer(() => client.repondreProposition(proposition.id, { reponse: b.reponse }), b.libelle)}>
              {b.libelle}
            </button>
          ))}
        </div>
      )}
      <Retour geste={{ ...geste, fait: geste.fait ? { message: geste.fait.message, geste: null } : null }} />
    </div>
  )
}

function Preference({ preference }) {
  const geste = useGeste()
  if (geste.fait) return <p className="section-sous" role="status">{`${preference.cle} retirée`}</p>
  return (
    <div className="ligne" role="listitem">
      <div className="ligne-corps"><div className="titre">{`${preference.cle} : ${preference.valeur}`}</div></div>
      <div className="ligne-fin">
        <button type="button" className="bouton lien" disabled={geste.occupe}
          onClick={() => geste.lancer(() => client.retirerPreference(preference.cle), 'Retirée')}>Retirer</button>
        {geste.erreur ? <span className="alerte" role="alert">{geste.erreur}</span> : null}
      </div>
    </div>
  )
}

function CarteRythme({ donnees }) {
  const d = donnees.rythme ?? donnees
  const objectif = d.objectif
  const chiffres = objectif?.nb ? `objectif ${objectif.nb}` : ''
  return (
    <div role="group" aria-label="Ton rythme">
      <Tete titre="Ton rythme" chiffres={chiffres} />
      <p className="section-sous">{LIBELLES_MODE[d.mode] ?? ''}{d.trace ? ` · ${d.trace}` : ''}</p>
      <BoutonsReponse proposition={d.proposition} />
      {(d.constats ?? []).map((c) => <BoutonsReponse key={c.id} proposition={c} />)}
      {(d.preferences ?? []).length > 0 ? (
        <div className="liste" role="list">{d.preferences.map((p) => <Preference key={p.cle} preference={p} />)}</div>
      ) : null}
    </div>
  )
}

// ── priorites ─────────────────────────────────────────────────────────────────

/** R3-023 — `garder_n === 0` veut dire « rien à ajouter », pas « objectif atteint » : seul `faites` ≥ l'objectif
 *  l'est ; sinon l'objectif est COUVERT par ce qui est déjà gardé (« 1 sur 9 faites »). */
function sousTitrePriorites(d) {
  if (d.objectif?.mode === LIBRE || !d.objectif?.nb) return "Dans l'ordre où l'ERP les prendrait"
  if (d.garder_n === 0) {
    const faites = Number(d.faites) || 0
    if (faites >= d.objectif.nb) return 'Objectif atteint : le reste peut attendre.'
    return `Ton objectif est couvert par tes tâches du jour (${faites} sur ${d.objectif.nb} faites)`
  }
  return `${d.garder_n} pour atteindre ton objectif de ${d.objectif.nb}`
}

/** R3-023 — la journée déborde (`priorites/` sert alors les GARDÉES ouvertes, `geste_propose: "alleger"`) : rien
 *  à ajouter, chaque ligne se reporte, et « Alléger ma journée » ouvre la feuille d'Aujourd'hui. */
function ReporterPriorite({ item, jour, plusTard }) {
  const geste = useGeste()
  if (!plusTard) return null
  return (
    <div className="actions-priorite">
      <button type="button" className="bouton lien" disabled={geste.occupe}
        onClick={() => geste.lancer(() => client.planifierTache(item.id, { jour_prevu: plusTard, lock_version: item.lock_version }), `Reportée à ${jourNomme(plusTard, jour)}`)}>
        {`Reporter à ${jourNomme(plusTard, jour)}`}
      </button>
      <Retour geste={geste} />
    </div>
  )
}

function CarteDebordement({ donnees }) {
  const lignes = donnees.lignes ?? []
  return (
    <div role="group" aria-label="Tes priorités">
      <Tete titre={`Ta journée déborde de ${duree(donnees.charge?.deborde_minutes)}`} />
      <div className="liste" role="list">
        {lignes.map((l) => (
          <LigneCarte key={cleItem(l.item)} item={l.item} rang={l.rang}
            bas={<ReporterPriorite item={l.item} jour={donnees.jour} plusTard={donnees.plus_tard} />} />
        ))}
      </div>
      <div className="propose-actions ep-carte-ia-pied">
        <Link className="bouton second" to="/taches/aujourdhui?ouvrir=alleger">Alléger ma journée</Link>
      </div>
    </div>
  )
}

function GestesPriorite({ item, jour, plusTard }) {
  const geste = useGeste()
  const ecrire = (appel, message) => geste.lancer(appel, message)
  const ligne = [{ type: item.type, id: item.id }]
  // Passe visuelle n° 65 — des gestes en liens d'accent, comme ceux de « Ta liste rangée » : un mot gras nu ne
  // disait pas qu'on pouvait le toucher.
  return (
    <div className="actions-priorite">
      <button type="button" className="bouton lien" disabled={geste.occupe}
        onClick={() => ecrire(() => client.marquerEssentiel({ tache_id: item.id, essentielle: true }), 'Essentielle')}>Essentiel</button>
      <button type="button" className="bouton lien" disabled={geste.occupe}
        onClick={() => ecrire(() => client.garderJournee({ jour, mode: 'express', lignes: ligne, essentielles: [], triage: [] }), 'Mise à aujourd\'hui')}>
        Aujourd&apos;hui
      </button>
      {plusTard ? (
        <button type="button" className="bouton lien" disabled={geste.occupe}
          onClick={() => ecrire(() => client.planifierTache(item.id, { jour_prevu: plusTard, lock_version: item.lock_version }), `Reportée à ${jourNomme(plusTard, jour)}`)}>
          {`Reporter à ${jourNomme(plusTard, jour)}`}
        </button>
      ) : null}
      <Retour geste={geste} />
    </div>
  )
}

function CartePriorites({ donnees }) {
  const geste = useGeste(null, { principal: true })
  const [toutes, setToutes] = useState(false)
  const lignes = donnees.lignes ?? []
  // R4-01 — LA charge du jour (`charge`, la même que la page Aujourd'hui) : un seul verdict « trop plein » partout
  if (donnees.geste_propose === 'alleger' && donnees.charge?.deborde_minutes > 0 && lignes.length > 0) return <CarteDebordement donnees={donnees} />
  if (lignes.length === 0) {
    return <div role="group" aria-label="Tes priorités"><Tete titre="Tes priorités" /><p className="section-sous">Rien à prioriser : tout est gardé ou fait.</p></div>
  }
  const n = donnees.garder_n ?? 0
  const visibles = toutes ? lignes : lignes.slice(0, Math.max(n, 1))
  const aGarder = lignes.slice(0, n).map((l) => l.item)
  return (
    <div role="group" aria-label="Tes priorités">
      <Tete titre="Tes priorités" />
      <p className="section-sous">{sousTitrePriorites(donnees)}</p>
      <div className="liste" role="list">
        {visibles.map((l) => (
          <LigneCarte key={cleItem(l.item)} item={l.item} rang={l.rang}
            bas={<GestesPriorite item={l.item} jour={donnees.jour} plusTard={donnees.plus_tard} />} />
        ))}
      </div>
      {!toutes && lignes.length > visibles.length ? (
        <button type="button" className="lien-plus" onClick={() => setToutes(true)}>{`Voir les ${lignes.length - visibles.length} suivantes`}</button>
      ) : null}
      {n > 0 ? <div className="propose-actions ep-carte-ia-pied"><BoutonGarder lignes={aGarder} jour={donnees.jour} geste={geste} /></div> : null}
      <Retour geste={geste} />
    </div>
  )
}

// ── point ─────────────────────────────────────────────────────────────────────

function lignesDuPoint(d) {
  const p = d.progression ?? {}
  const objectif = d.objectif
  const lignes = [objectif?.mode === LIBRE || !objectif?.nb ? `${p.faites} faites` : `${p.faites} sur ${objectif.nb}`]
  const essentiel = d.essentiel_restant ?? []
  if (essentiel.length > 0) lignes.push(`Essentiel restant : ${essentiel.map((t) => t.titre).join(', ')}`)
  else if (p.essentiel_prevues > 0) lignes.push('Essentiel fait')
  if (d.prochaine) lignes.push(`Prochaine : ${d.prochaine.titre}${d.prochaine.heure_debut ? ` · ${heure(d.prochaine.heure_debut)}` : ''}`)
  // R4-07 (M6) — plus de « gardées » : ce qui reste prévu aujourd'hui
  if (d.restes_nb > 0) lignes.push(`Encore ${accord(d.restes_nb, "prévue aujourd'hui", "prévues aujourd'hui")}`)
  const rdv = d.rendez_vous_restants ?? []
  if (rdv.length > 0) lignes.push(`Rendez-vous restants : ${rdv.map((r) => `${heure(r.debut?.slice(11, 16))} ${r.titre}`).join(' · ')}`)
  // R4-01 — LA phrase du temps d'Aujourd'hui, sur LA charge servie (`progression.charge`) : mêmes mots, même chiffre
  const temps = tempsTexte(p.charge)
  if (temps) lignes.push(temps)
  return lignes
}

function CartePoint({ donnees }) {
  return (
    <div role="group" aria-label="Où tu en es">
      <Tete titre="Où tu en es" />
      <ul className="m-0 list-none p-0">
        {lignesDuPoint(donnees).map((t) => <li key={t} className="section-sous">{t}</li>)}
      </ul>
      <div className="propose-actions ep-carte-ia-pied"><Link className="bouton second" to="/taches/aujourdhui">Ouvrir Aujourd&apos;hui</Link></div>
    </div>
  )
}

/** ERR 5 (a) — la carte attend-elle le doigt à son arrivée ? Une écriture à valider, un écho (Renommer…), un
 *  Proposé ou des priorités à garder, une liste à ajouter ou ranger, des étapes à ajouter ; une lecture, non. */
function attendLeDoigt(cle, d) {
  if (!d) return false
  if (d.proposition?.geste === 'ecrire') return true
  if (cle === 'plan_propose') return (d.proposition ?? []).length > 0
  if (cle === 'priorites') return ((d.garder_n ?? 0) > 0 || d.geste_propose === 'alleger') && (d.lignes ?? []).length > 0
  if (cle === 'capture_apercu') return (d.lignes ?? []).length > 0
  if (cle === 'plan_projet') return projetPlanifiable(d.projet)
  if (cle === 'tache') return Boolean(d.proposition && ECHOS[d.proposition.geste])
  return false
}

const COMPOSANTS = {
  ma_journee: CarteMaJournee,
  plan_propose: CartePlanPropose,
  liste_taches: CarteListeTaches,
  tache: CarteTache,
  capture_apercu: CarteCaptureApercu,
  rythme: CarteRythme,
  plan_projet: CartePlanProjet,
  projet: CarteProjet,
  revue_semaine: CarteRevueSemaine,
  priorites: CartePriorites,
  point: CartePoint,
}

/** Une écriture à valider arrive sous la clé de carte de son action (`tache`, ou `rythme` pour
 *  `taches.rythme.regler` et `taches.preference.noter`) : elle se rend TOUJOURS en carte à valider. */
function CarteEcritureAValider({ donnees }) {
  return <CarteAValider tache={donnees.tache} proposition={donnees.proposition} />
}

/** Une carte `taches` du Copilote : `carte` = `{ carte: '<clé>', donnees: <corps de la route> }`. */
export default function CartesTaches({ carte, cadre = null, testId }) {
  const aValider = carte?.donnees?.proposition?.geste === 'ecrire'
  const Composant = COMPOSANTS[carte?.carte] && aValider ? CarteEcritureAValider : COMPOSANTS[carte?.carte]
  const [etatCadre, setEtatCadre] = useState(() => (attendLeDoigt(carte?.carte, carte?.donnees) ? 'attente' : 'fait'))
  if (!Composant || !carte.donnees) return null
  const contenu = (
    <EtatDuCadre.Provider value={setEtatCadre}>
      <div className="tch" data-testid={`carte-taches-${carte.carte}`}>
        <div className="ep-carte-ia">
          <Composant donnees={carte.donnees} />
        </div>
      </div>
    </EtatDuCadre.Provider>
  )
  if (!cadre) return contenu
  return <div className={cadre[etatCadre] ?? cadre.fait} data-testid={testId} data-cadre={etatCadre}>{contenu}</div>
}
