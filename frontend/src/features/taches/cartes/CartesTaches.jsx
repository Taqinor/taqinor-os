import { useState } from 'react'
import { Link } from 'react-router-dom'
import * as client from '../../../api/tachesApi'
import { frenchError } from '../../../lib/frenchError'
import CaseRonde from '../ui/CaseRonde'
import { accord, duree, heure, jourCourt, jourNomme } from '../lib/textes'

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

/** Un geste d'écriture : état occupé, erreur sous le geste, message « fait » avec « Annuler ». */
function useGeste(initial = null) {
  const [etat, setEtat] = useState({ occupe: false, erreur: '', fait: initial })
  const lancer = async (appel, message) => {
    setEtat({ occupe: true, erreur: '', fait: null })
    try {
      const { data } = await appel()
      setEtat({ occupe: false, erreur: '', fait: { message, geste: data?.geste_id ?? null } })
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
      onBasculer={async () => {
        await client.terminerTache(item.id, { lock_version: item.lock_version })
        setFait(true)
      }}
    />
  )
}

function CarteMaJournee({ donnees }) {
  const lot = useGeste()
  const items = [...(donnees.essentiel ?? []), ...(donnees.journee ?? [])]
  const ids = items.filter((it) => it.type === 'tache').map((it) => it.id)
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
        accord(n, 'gardée'))}>
      {n >= 2 ? `Garder ces ${n}` : 'Garder celle-ci'}
    </button>
  )
}

function CartePlanPropose({ donnees }) {
  const geste = useGeste()
  const lignes = (donnees.proposition ?? []).filter((l) => l.cochee !== false && !l.deja_prevue).map((l) => l.item)
  const objectif = donnees.objectif?.nb
  const chiffres = objectif ? `${lignes.length} · objectif ${objectif}` : `${lignes.length}`
  return (
    <div role="group" aria-label="Proposé pour aujourd'hui">
      <Tete titre="Proposé pour aujourd'hui" chiffres={chiffres} />
      {lignes.length === 0 ? <p className="section-sous">Objectif couvert par ce que tu as gardé.</p> : (
        <div className="liste" role="list">{lignes.map((it) => <LigneCarte key={cleItem(it)} item={it} />)}</div>
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
  const geste = useGeste()
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
          <button type="button" className="bouton lien" disabled={geste.occupe} onClick={() => setLaisse(true)}>Laisser</button>
        </div>
      ) : null}
      {laisse ? <p className="section-sous" role="status">Laissée comme elle est.</p> : null}
      <Retour geste={geste} />
    </div>
  )
}

// A5 — une écriture du Copilote arrivée dans un tour où un texte tiers est entré : le relais n'a RIEN
// écrit, la carte porte le corps de la requête (`proposition.corps`, contrat `ecriture_a_valider`) et le
// doigt la valide. « Modifier » / « Laisser » : textes.md §5.5. Les autres écritures gardent le libellé
// du registre de l'agent (`proposition.libelle`) sur leur bouton.
// Revue F3 n° 2 : la carte DIT chaque champ du corps avant le doigt (`lignesDuCorps`) et le bouton
// envoie ce corps-là, le même objet ; un champ qu'elle ne sait pas dire se montre tel quel (clé : valeur).
// eslint-disable-next-line react-refresh/only-export-components -- table parcourue par la garde du test (revue F3 n° 2)
export const ECRITURES_A_VALIDER = {
  'taches.tache.modifier': { bouton: 'Modifier', fait: () => 'Modifiée', appel: (t, c) => client.modifierTache(t.id, c) },
  'taches.tache.creer': { fait: () => 'Ajoutée', appel: (t, c) => client.creerTache(c) },
  'taches.tache.terminer': { fait: () => 'Faite', appel: (t, c) => client.terminerTache(t.id, c) },
  'taches.tache.planifier': {
    fait: (c) => (c.jour_prevu ? `Prévue ${jourNomme(c.jour_prevu)}` : ''), appel: (t, c) => client.planifierTache(t.id, c),
  },
  'taches.rappel.poser': {
    fait: (c) => (c.jour ? `Rappel posé ${jourNomme(c.jour)} à ${heure(c.heure)}` : ''), appel: (t, c) => client.poserRappel(t.id, c),
  },
  'taches.projet.creer': { fait: () => '', appel: (t, c) => client.creerProjet(c) },
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
// « échéance {jour} [· {HH:MM}] », « En réserve », « Nouveau projet : {nom} », « Priorité haute »,
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
  [['quelque_jour'], (c) => (c.quelque_jour === true ? 'En réserve' : '')],
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
export function lignesDuCorps(corps, changements = [], { titreEnTete = false, titreTache = '' } = {}) {
  const lignes = []
  const dits = new Set(CHAMPS_TECHNIQUES)
  if (titreEnTete) dits.add('titre')
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
  const geste = useGeste()
  const [laisse, setLaisse] = useState(false)
  const ecriture = ECRITURES_A_VALIDER[proposition.action_key]
  // UN objet : celui que les lignes disent est celui que le bouton envoie.
  const [corps] = useState(() => proposition.corps ?? {})
  const titreEnTete = !tache && estTexte(corps.titre)
  const titre = tache?.titre ?? (titreEnTete ? corps.titre : proposition.libelle)
  const lignes = lignesDuCorps(corps, proposition.changements ?? [], { titreEnTete, titreTache: tache?.titre ?? '' })
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
          <button type="button" className="bouton lien" disabled={geste.occupe} onClick={() => setLaisse(true)}>Laisser</button>
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

function CarteCaptureApercu({ donnees }) {
  const geste = useGeste()
  const [retirees, setRetirees] = useState([])
  const lignes = (donnees.lignes ?? []).filter((l) => !retirees.includes(l.index))
  const ajouter = () => geste.lancer(() => client.saisieRapide({
    lignes: lignes.map((l) => ({ index: l.index, collage: l.collage, client_id: `copilote:${l.collage}:${l.index}`, titre: l.titre, ...l.champs })),
    apercu: false,
  }), accord(lignes.length, 'ajoutée'))
  return (
    <div role="group" aria-label="Ta liste rangée">
      <Tete titre="Ta liste rangée" chiffres={String(lignes.length)} />
      {lignes.length === 0 ? <p className="section-sous">Rien à ajouter.</p> : (
        <div className="liste" role="list">
          {lignes.map((l) => (
            <div key={l.index} className="ligne" role="listitem">
              <div className="ligne-corps">
                <div className="titre">{l.titre}</div>
                <div className="meta">
                  {l.champs?.nouveau_projet ? <span>{`Nouveau projet : ${l.champs.nouveau_projet.nom}`}</span> : <span>Pas de projet évident : choisis-le.</span>}
                </div>
              </div>
              <div className="ligne-fin">
                <button type="button" className="bouton lien" onClick={() => setRetirees((r) => [...r, l.index])}>Retirer</button>
              </div>
            </div>
          ))}
        </div>
      )}
      {lignes.length > 0 ? (
        <div className="propose-actions ep-carte-ia-pied">
          <button type="button" className="bouton second" disabled={geste.occupe || geste.fait !== null} onClick={ajouter}>
            {`Tout ajouter (${lignes.length})`}
          </button>
        </div>
      ) : null}
      <Retour geste={geste} />
    </div>
  )
}

function CartePlanProjet({ donnees }) {
  const [retirees, setRetirees] = useState([])
  const sections = donnees.sections ?? []
  return (
    <div role="group" aria-label="Le projet en étapes">
      <Tete titre="Le projet en étapes" chiffres={String(sections.length)} />
      {sections.map((s, i) => (
        <div key={s.nom}>
          <p className="ep-carte-ia-etape">{s.nom}</p>
          <div className="liste" role="list">
            {(s.taches ?? []).filter((t) => !retirees.includes(`${i}:${t.titre}`)).map((t) => (
              <div key={t.titre} className="ligne" role="listitem">
                <div className="ligne-corps">
                  <div className="titre">{t.titre}</div>
                  {(t.sous_taches ?? []).length > 0 ? <div className="meta"><span>{t.sous_taches.join(' · ')}</span></div> : null}
                </div>
                <div className="ligne-fin">
                  <button type="button" className="bouton lien" onClick={() => setRetirees((r) => [...r, `${i}:${t.titre}`])}>Retirer</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
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

function sousTitrePriorites(d) {
  if (d.objectif?.mode === LIBRE || !d.objectif?.nb) return "Dans l'ordre où l'ERP les prendrait"
  if (d.garder_n === 0) return 'Objectif atteint : le reste peut attendre.'
  return `${d.garder_n} pour atteindre ton objectif de ${d.objectif.nb}`
}

function GestesPriorite({ item, jour, plusTard }) {
  const geste = useGeste()
  const ecrire = (appel, message) => geste.lancer(appel, message)
  const ligne = [{ type: item.type, id: item.id }]
  return (
    <div className="actions-priorite">
      <button type="button" className="bouton discret" disabled={geste.occupe}
        onClick={() => ecrire(() => client.marquerEssentiel({ tache_id: item.id, essentielle: true }), 'Essentielle')}>Essentiel</button>
      <button type="button" className="bouton discret" disabled={geste.occupe}
        onClick={() => ecrire(() => client.garderJournee({ jour, mode: 'express', lignes: ligne, essentielles: [], triage: [] }), 'Mise à aujourd\'hui')}>
        Aujourd&apos;hui
      </button>
      {plusTard ? (
        <button type="button" className="bouton discret" disabled={geste.occupe}
          onClick={() => ecrire(() => client.planifierTache(item.id, { jour_prevu: plusTard, lock_version: item.lock_version }), `Prévue ${jourNomme(plusTard, jour)}`)}>
          {`Plus tard dans la semaine (→ ${jourNomme(plusTard, jour)})`}
        </button>
      ) : null}
      <Retour geste={geste} />
    </div>
  )
}

function CartePriorites({ donnees }) {
  const geste = useGeste()
  const [toutes, setToutes] = useState(false)
  const lignes = donnees.lignes ?? []
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
  if (d.restes_nb > 0) lignes.push(`Encore ${accord(d.restes_nb, 'gardée')}`)
  const rdv = d.rendez_vous_restants ?? []
  if (rdv.length > 0) lignes.push(`Rendez-vous restants : ${rdv.map((r) => `${heure(r.debut?.slice(11, 16))} ${r.titre}`).join(' · ')}`)
  if (p.disponible_minutes > 0) lignes.push(`Temps libre : ${duree(p.disponible_minutes)}`)
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
export default function CartesTaches({ carte }) {
  const aValider = carte?.donnees?.proposition?.geste === 'ecrire'
  const Composant = COMPOSANTS[carte?.carte] && aValider ? CarteEcritureAValider : COMPOSANTS[carte?.carte]
  if (!Composant || !carte.donnees) return null
  return (
    <div className="tch" data-testid={`carte-taches-${carte.carte}`}>
      <div className="ep-carte-ia">
        <Composant donnees={carte.donnees} />
      </div>
    </div>
  )
}
