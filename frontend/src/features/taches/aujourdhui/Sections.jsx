import { useEffect, useRef, useState } from 'react'
import { ChevronDown, ChevronRight, ChevronUp, ClipboardPaste, CalendarDays, MapPin, Mic, Phone, RefreshCw } from 'lucide-react'
import LigneTache from '../ui/LigneTache'
import { proposerAnnuler } from '../lib/gestes'
import { LigneOs } from '../ui/ChargementTardif'
import { accord, heure, jourNomme } from '../lib/textes'

/* ============================================================================
   TCH76 — Les sections d'Aujourd'hui, dans l'ORDRE VERTICAL de regles.md §4.1 :
   Essentiel · Toute la journée · Prévu · Ce soir · (Proposé) · repliés. Une section vide est
   absente. Ce module ne parle jamais au serveur : il lit `aujourdhui.json` et appelle les
   gestes que la page lui passe (`geste`). Maquettes : ecran-aujourdhui-matin.html,
   ecran-aujourdhui-matin-bas.html, ecran-aujourdhui-vide.html, etat-chargement.html,
   etat-pas-a-jour.html. Textes : reference/textes.md §2.2 « Aujourd'hui ».
   ========================================================================== */

export const PHRASE_HORS_LIGNE = 'Possible une fois connecté'
const SEUIL_ACTIVITES_REPLIEES = 3

/** Une section du contrat : titre, phrase d'aide facultative, liste à plat. */
export function Section({ titre, sous = null, premiere = false, children, ...reste }) {
  return (
    <section className={premiere ? 'section premiere' : 'section'} {...reste}>
      <h2 className="section-titre"><span>{titre}</span></h2>
      {sous ? <p className="section-sous">{sous}</p> : null}
      <div className="liste" role="list">{children}</div>
    </section>
  )
}

/** Une ligne de tâche ou d'activité ERP : toutes les sections passent par ici (geste = ce que la page sait faire). */
export function Ligne({ item, contexte, geste, extra = {}, reorg = false }) {
  const { donnees, estampilles, nbEssentielles, selection, reorganiser } = contexte
  const cle = `${item.type}:${item.id}`
  const choix = selection?.actif && item.type === 'tache'
    ? { actif: true, selectionnee: selection.ids.has(cle), onBasculer: () => geste.selectionner(item) }
    : null
  const ligne = (
    <LigneTache
      item={item}
      aujourdhui={donnees.jour}
      reporterLibelle={jourNomme(donnees.prochain_jour_ouvre, donnees.jour)}
      estampille={estampilles[cle] ?? ''}
      nbEssentielles={nbEssentielles}
      selection={choix}
      onTerminer={geste.terminer}
      onReporter={geste.reporter}
      onChoisirJour={geste.choisirJour}
      onOuvrir={geste.ouvrir}
      onAction={geste.action}
      onAnnonce={geste.annoncer}
      onRefusEssentiel={geste.refusEssentiel}
      glissable={contexte.glissable ?? undefined}
      {...extra}
    />
  )
  // R3-021 — reportée mais gardée par son échéance du jour : la ligne reste (sa pastille le dit), jamais le fondu de départ
  if (contexte.restes?.has(cle)) return <div className="ligne-reste" role="presentation">{ligne}</div>
  if (!reorganiser || !reorg || item.type !== 'tache') return ligne
  return (
    <div className="ligne-reorg" role="presentation">
      {ligne}
      <div className="reorg-controles">
        <button type="button" className="bouton-icone" aria-label={`Monter « ${item.titre} »`} onClick={() => geste.deplacer(item, -1)}>
          <ChevronUp className="i i-16" aria-hidden="true" />
        </button>
        <button type="button" className="bouton-icone" aria-label={`Descendre « ${item.titre} »`} onClick={() => geste.deplacer(item, 1)}>
          <ChevronDown className="i i-16" aria-hidden="true" />
        </button>
      </div>
    </div>
  )
}

/** « Toute la journée » : visites, poses, interventions et rendez-vous externes « journée entière ». */
export function BandesJournee({ donnees, ouvrir }) {
  const familles = (donnees.obligations ?? []).filter((o) => o.famille !== 'touches')
  const entiers = (donnees.rendez_vous ?? []).filter((r) => r.journee_entiere)
  return (
    <>
      {familles.map((o) => (
        <button
          key={`${o.famille}:${o.id}`}
          type="button"
          className="bande-journee"
          aria-label={`Ouvrir : ${o.titre}`}
          onClick={() => ouvrir(o.url)}
        >
          <MapPin className="i i-16" aria-hidden="true" />
          <b>{o.titre}</b>
          <small>Toute la journée</small>
        </button>
      ))}
      {entiers.map((r) => (
        <div key={r.cle} className="bande-journee" role="group" aria-label={`${r.titre}, ${r.agenda}, toute la journée`}>
          <CalendarDays className="i i-16" aria-hidden="true" />
          <b>{r.titre}</b>
          <small>{r.agenda}</small>
        </div>
      ))}
    </>
  )
}

/** Un rendez-vous d'un agenda externe : lecture seule, ni case ni geste (textes.md §2.2 « Prévu »). */
function LigneRendezVous({ rdv }) {
  const debut = heure(rdv.debut.slice(11, 16))
  const fin = heure(rdv.fin.slice(11, 16))
  return (
    <div className="ligne lecture-seule" role="listitem" data-ligne={`rdv:${rdv.cle}`}>
      <span className="case vide"><span className="pastille-erp"><CalendarDays className="i" aria-hidden="true" /></span></span>
      <div className="ligne-corps">
        <div className="titre">{`${debut}–${fin} ${rdv.titre}`}</div>
        <div className="meta"><span>{rdv.agenda}</span></div>
      </div>
      <div className="ligne-fin" />
    </div>
  )
}

/** La ligne « Suivi des relances : n » : un raccourci vers les relances de l'ERP (famille `touches`). */
function LigneRelances({ obligation, ouvrir }) {
  const retard = obligation.en_retard > 0 ? `, dont ${accord(obligation.en_retard, 'en retard', 'en retard')}` : ''
  return (
    <div className="ligne" role="listitem" data-ligne="touches">
      <span className="case vide"><span className="pastille-erp"><Phone className="i" aria-hidden="true" /></span></span>
      <div className="ligne-corps">
        <button
          type="button"
          className="ligne-corps-bouton"
          aria-label={`Suivi des relances : ${obligation.nb}${retard}. Ouvrir`}
          onClick={() => ouvrir(obligation.url)}
        >
          <span className="titre">{`Suivi des relances : ${obligation.nb}`}</span>
        </button>
      </div>
      <div className="ligne-fin"><ChevronRight className="i i-16" aria-hidden="true" /></div>
    </div>
  )
}

/** Les entrées de « Prévu » : à leur heure d'abord (tâches, activités, rendez-vous), puis celles sans heure. */
function entreesPrevu(donnees) {
  const avecHeure = []
  const sansHeure = []
  for (const item of donnees.journee ?? []) {
    const cible = item.heure_debut ? avecHeure : sansHeure
    cible.push({ cle: `${item.type}:${item.id}`, item, heure: item.heure_debut ? heure(item.heure_debut) : '' })
  }
  for (const rdv of (donnees.rendez_vous ?? []).filter((r) => !r.journee_entiere)) {
    avecHeure.push({ cle: `rdv:${rdv.cle}`, rdv, heure: heure(rdv.debut.slice(11, 16)) })
  }
  avecHeure.sort((a, b) => a.heure.localeCompare(b.heure))
  return { avecHeure, sansHeure }
}

/** « Prévu » : blocs à leur heure, tâches et activités ERP mêlées ; plus de 3 activités sans heure : une ligne repliable. */
export function Prevu({ donnees, contexte, geste }) {
  const [depliee, setDepliee] = useState(false)
  const section = useRef(null)
  // TCH78 — après « Garder ces N », le focus va sur « Prévu » (critère 8 de spec-7 §6)
  useEffect(() => { if (contexte.focusPrevu) section.current?.focus() }, [contexte.focusPrevu])
  const relances = (donnees.obligations ?? []).find((o) => o.famille === 'touches')
  const { avecHeure, sansHeure } = entreesPrevu(donnees)
  const activites = sansHeure.filter((e) => e.item.type === 'activite')
  const replier = activites.length > SEUIL_ACTIVITES_REPLIEES
  const visibles = sansHeure.filter((e) => depliee || !replier || e.item.type !== 'activite')
  if (avecHeure.length + sansHeure.length === 0 && !relances && !contexte.invite) return null
  const rendre = (e) => (e.rdv
    ? <LigneRendezVous key={e.cle} rdv={e.rdv} />
    : (
      <Ligne key={e.cle} item={e.item} contexte={contexte} geste={geste} reorg
        extra={contexte.gardee && e.item.type === 'tache' ? { onEssentiel: geste.essentiel } : {}} />
    ))
  return (
    <Section titre="Prévu" sous={contexte.invite ? 'Touche ★ pour ton essentiel' : null} ref={section} tabIndex={-1}>
      {avecHeure.map(rendre)}
      {replier ? (
        <button
          type="button"
          className="ligne ligne-repli"
          aria-expanded={depliee}
          onClick={() => setDepliee((v) => !v)}
        >
          <span className="case vide"><span className="pastille-erp"><Phone className="i" aria-hidden="true" /></span></span>
          <span className="ligne-corps"><span className="titre">{`${activites.length} activités ERP`}</span></span>
          <span className="ligne-fin">
            {depliee ? <ChevronDown className="i i-16" aria-hidden="true" /> : <ChevronRight className="i i-16" aria-hidden="true" />}
          </span>
        </button>
      ) : null}
      {visibles.map(rendre)}
      {relances ? <LigneRelances obligation={relances} ouvrir={geste.naviguer} /> : null}
    </Section>
  )
}

/** Les sections ouvertes d'Aujourd'hui dans l'ordre vertical (Proposé s'y insère par `propose`). */
export default function Sections({ donnees, contexte, geste, propose = null, repliees = null }) {
  const lignes = (items) => items.map((item) => <Ligne key={`${item.type}:${item.id}`} item={item} contexte={contexte} geste={geste} reorg />)
  const essentiel = donnees.essentiel ?? []
  const ceSoir = donnees.ce_soir ?? []
  return (
    <>
      {essentiel.length > 0 ? (
        <Section titre="Essentiel" premiere>
          {essentiel.map((item) => (
            <Ligne key={`${item.type}:${item.id}`} item={item} contexte={contexte} geste={geste} reorg
              extra={{ onEssentiel: geste.essentiel }} />
          ))}
        </Section>
      ) : null}
      <BandesJournee donnees={donnees} ouvrir={geste.naviguer} />
      <Prevu donnees={donnees} contexte={contexte} geste={geste} />
      {ceSoir.length > 0 ? <Section titre="Ce soir">{lignes(ceSoir)}</Section> : null}
      {propose}
      {repliees}
      {donnees.tronque ? <p className="section-sous">Plus de 200 lignes : affine avec la recherche.</p> : null}
    </>
  )
}

/** Le squelette (après 1 s sans réponse, jamais sur une liste déjà affichée) : etat-chargement.html. */
export function Squelette() {
  const bloc = (largeurs, titre = '') => (
    <div className="squelette-bloc">
      <span className="os titre-section" style={titre ? { width: titre } : undefined} />
      {largeurs.map(([l1, l2], rang) => <LigneOs key={rang} l1={l1} l2={l2} />)}
    </div>
  )
  return (
    <div className="squelette-liste" role="status" aria-label="Chargement">
      <div className="progression">
        <span className="segments" aria-hidden="true"><i /><i /><i /><i /><i /></span>
        <span className="os" style={{ width: 120, height: 12 }} />
      </div>
      {bloc([['72%', '44%'], ['84%', '38%']])}
      {bloc([['64%'], ['78%', '48%'], ['56%', '40%']])}
      {bloc([['70%', '46%'], ['60%']], '150px')}
    </div>
  )
}

/** « Pas à jour · 08:20 » [Réessayer] : la liste reste (etat-pas-a-jour.html). */
export function BandeauPasAJour({ derniere, onReessayer }) {
  return (
    <div className="pas-a-jour" role="status">
      <RefreshCw className="i i-16" aria-hidden="true" />
      <span className="chiffres">{derniere ? `Pas à jour · ${derniere}` : 'Pas à jour'}</span>
      <button type="button" className="bouton lien" onClick={onReessayer}>Réessayer</button>
    </div>
  )
}

const AIDE_COLLER = 'Appuie longuement dans le champ puis Coller'

/**
 * R2-033 — « Coller mes listes » colle VRAIMENT : le presse-papiers est lu au toucher et son texte arrive dans la saisie
 * (l'aperçu des listes s'ouvre aussitôt, par l'événement `taqinor:taches:saisir` et son `texte`). Lecture refusée ou
 * presse-papiers vide : la saisie s'ouvre quand même, et un message dit le geste (« Appuie longuement… »).
 */
async function lirePressePapiers() {
  const lire = typeof navigator !== 'undefined' ? navigator.clipboard?.readText : null
  if (typeof lire !== 'function') return ''
  const texte = await lire.call(navigator.clipboard).then((t) => t, () => '') // refus du navigateur = rien à coller
  return typeof texte === 'string' ? texte : ''
}

/** Les deux écrans vides : aucune tâche (« Colle ou dicte tes listes ») ou rien de gardé (des tâches attendent dans À trier). */
export function EtatVide({ donnees, onColler, onDicter, onTrier }) {
  const coller = async () => {
    const texte = await lirePressePapiers()
    if (texte.trim()) { onColler({ texte }); return }
    onColler({})
    proposerAnnuler({ message: AIDE_COLLER })
  }
  const attente = donnees.a_trier?.boite_reception ?? 0
  if (attente > 0) {
    return (
      <div className="vide-etat vide-plein">
        <p className="vide-phrase">
          {`Rien de prévu aujourd'hui. ${attente >= 2 ? `${attente} tâches attendent` : '1 tâche attend'} dans À trier.`}
        </p>
        <button type="button" className="bouton plein" onClick={onTrier}>Trier</button>
      </div>
    )
  }
  return (
    <div className="vide-etat vide-plein">
      <span className="vide-picto grand"><ClipboardPaste className="i" aria-hidden="true" /></span>
      {/* espace insécable avant « : » (maquette ecran-aujourdhui-vide.html) : le deux-points ne commence jamais une ligne */}
      <p className="vide-phrase">{'Colle ou dicte tes listes : je les range par projet.'}</p>
      <p className="vide-aide">Une liste par projet, une tâche par ligne.</p>
      <button type="button" className="bouton plein" onClick={coller}>Coller mes listes</button>
      <p className="vide-aide vide-plus">ou touche + pour une tâche</p>
      <button type="button" className="bouton discret" onClick={onDicter}>
        <Mic className="i" aria-hidden="true" />Dicter
      </button>
    </div>
  )
}
