import { useState } from 'react'
import { Link } from 'react-router-dom'
import * as client from '../../../api/tachesApi'
import { frenchError } from '../../../lib/frenchError'
import CaseRonde from '../ui/CaseRonde'
import { accord, jourNomme } from '../lib/textes'

/* ============================================================================
   TCH117 — Les cartes « Tâches » du Copilote, rendues DIRECTEMENT (sans passer par
   `CarteResultat`) : `ma_journee`, `plan_propose`, `liste_taches`, `tache` (écho ou écriture) ; la suite est TCH165.
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

function Tete({ titre, chiffres = '' }) {
  return (
    <div className="flex items-baseline justify-between gap-2 pb-1">
      <h3 className="m-0 text-base font-semibold">{titre}</h3>
      {chiffres ? <span className="chiffres text-sm">{chiffres}</span> : null}
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
        <div className="propose-actions">
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
      {lignes.length > 0 ? <div className="propose-actions"><BoutonGarder lignes={lignes} jour={donnees.jour} geste={geste} /></div> : null}
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
        <div className="propose-actions">
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

function CarteTache({ donnees }) {
  const { tache, proposition, avertissements } = donnees
  const geste = useGeste(donnees.geste_id ? { message: 'Modifiée', geste: donnees.geste_id } : null)
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

const COMPOSANTS = {
  ma_journee: CarteMaJournee,
  plan_propose: CartePlanPropose,
  liste_taches: CarteListeTaches,
  tache: CarteTache,
}

/** Une carte `taches` du Copilote : `carte` = `{ carte: '<clé>', donnees: <corps de la route> }`. */
export default function CartesTaches({ carte }) {
  const Composant = COMPOSANTS[carte?.carte]
  if (!Composant || !carte.donnees) return null
  return (
    <div className="tch" data-testid={`carte-taches-${carte.carte}`}>
      <Composant donnees={carte.donnees} />
    </div>
  )
}
