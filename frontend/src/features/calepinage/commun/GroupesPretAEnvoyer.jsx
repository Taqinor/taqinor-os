import { createContext, useContext } from 'react'
import { ChevronRight, Info } from 'lucide-react'
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { Popover, PopoverContent, PopoverTrigger } from '../../../ui/Popover'
import { Icone as Picto } from '../atelier/coque/primitives'
import { ETAPES, etapeDeOnglet } from '../atelier/parcoursGuide'
import {
  cibleDuReglage, phraseDesBons, pointsServis, rangerControles, sansCleInterne, valeurAffichee,
} from './PretAEnvoyer.helpers'
import useExplications, { remplirPhrase } from './useExplications'

/* ACAL1193 — la présentation « par étape » de « Prêt à envoyer ? » (maquette `Documents.dc.html`,
   `PretAEnvoyer groupes`). Aucun état n'est calculé ici : chaque pastille, chaque phrase et chaque
   cible vient du contrôle SERVI ; les longues explications (cause, registre, geste) sont derrière
   le « ? » de la ligne — rien n'est supprimé. */

const LEGENDE = [
  ['ok', 'Bon'], ['a_regler', 'À régler'], ['bloquant', 'Bloque le devis'],
]
const libelleEtape = (cible) => ETAPES.find((e) => e.cle === etapeDeOnglet(cible?.onglet))?.libelle ?? null

/* ACAL1834 — les pastilles d'état de la maquette v2 : rond plein clair + coche (bon), triangle (à régler), octogone
   (bloque le devis) ; `info` garde son pictogramme. Teintes en jetons `--cal-*`, jamais une couleur écrite ici. */
function Pastille({ etat, taille = 22 }) {
  if (etat === 'ok') {
    return (
      <svg width={taille} height={taille} viewBox="0 0 24 24" className="cdoc-ico" data-etat={etat} aria-hidden="true">
        <circle cx="12" cy="12" r="10" fill="color-mix(in srgb, var(--cal-ok) 16%, var(--cal-surface))" />
        <path d="M7.5 12.5l3 3 6-6.5" fill="none" stroke="var(--cal-ok)" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    )
  }
  if (etat === 'a_regler') {
    return (
      <svg width={taille} height={taille} viewBox="0 0 24 24" className="cdoc-ico" data-etat={etat} aria-hidden="true">
        <path d="M12 2.8l10 17.7H2z" fill="color-mix(in srgb, var(--cal-production) 45%, var(--cal-surface))" stroke="var(--cal-or-texte)" strokeWidth="1.6" strokeLinejoin="round" />
        <path d="M12 9.5v5M12 17.4v.3" stroke="var(--cal-surveiller-texte)" strokeWidth="2.2" strokeLinecap="round" />
      </svg>
    )
  }
  if (etat === 'bloquant') {
    return (
      <svg width={taille} height={taille} viewBox="0 0 24 24" className="cdoc-ico" data-etat={etat} aria-hidden="true">
        <path d="M8 2h8l6 6v8l-6 6H8l-6-6V8z" fill="color-mix(in srgb, var(--cal-refus) 14%, var(--cal-surface))" stroke="var(--cal-refus)" strokeWidth="1.6" strokeLinejoin="round" />
        <path d="M9 9l6 6M15 9l-6 6" stroke="var(--cal-refus)" strokeWidth="2.2" strokeLinecap="round" />
      </svg>
    )
  }
  return <Info size={taille} className="cdoc-ico" data-etat={etat} aria-hidden="true" />
}

/* ACAL1834 — l'anneau de progression à côté de la pastille : la part de contrôles bons (vert) puis la part à
   régler (or), sur les contrôles qui portent un verdict ; rien n'est tracé sans verdict servi. */
function Anneau({ bons, total }) {
  const C = 100.53
  const part = total > 0 ? (bons / total) * C : 0
  const reste = total > 0 ? C - part : 0
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" className="cdoc-anneau" role="img" data-testid="cal-docs-anneau"
      aria-label={total > 0 ? `${bons} ${bons > 1 ? 'contrôles bons' : 'contrôle bon'} sur ${total}` : 'Aucun verdict'}>
      <circle cx="20" cy="20" r="16" fill="none" stroke="var(--cal-surface-2)" strokeWidth="5" />
      {part > 0 && <circle cx="20" cy="20" r="16" fill="none" stroke="var(--cal-ok)" strokeWidth="5"
        strokeDasharray={`${Math.max(part - 2, 0)} ${C}`} transform="rotate(-90 20 20)" />}
      {reste > 0 && <circle cx="20" cy="20" r="16" fill="none" stroke="var(--cal-production)" strokeWidth="5"
        strokeDasharray={`${Math.max(reste - 2, 0)} ${C}`} strokeDashoffset={-part} transform="rotate(-90 20 20)" />}
    </svg>
  )
}

/* T4-U4-007 — le calepinage de la liste, pour le « ? » du dossier électrique (qui relit ses motifs servis). */
const CalepinageDeLaListe = createContext(null)
const BLOQUE = new Set(['bloquant'])
const A_COMPLETER = new Set(['non_verifiable', 'omis', 'sans_source'])
const MAX_POINTS = 4

/** T4-U4-007 — « Dossier électrique » : le serveur ne sert que « Bloquant : 1 » ; le « ? » NOMME le ou les points en
    relisant les motifs du verdict publiable (`evaluer-electrique`, corps vide — la lecture de l'onglet Verdict), mot
    pour mot : bloquant ⇒ motifs bloquants ; à compléter ⇒ motifs non vérifiables, omis ou sans source. */
function PointsDossier({ calepinageId, etat }) {
  const { data, loading, error } = useResource(
    (id) => calepinageApi.calepinages.evaluerElectrique(id, {}), calepinageId,
    { select: (r) => r?.data?.publication ?? null, errorMessage: 'Les points n’ont pas pu être lus.' },
  )
  const retenus = etat === 'bloquant' ? BLOQUE : A_COMPLETER
  // Une phrase servie deux fois (deux producteurs du même motif) ne se lit qu'une fois ; quatre au plus dans la bulle.
  const points = [...new Set((Array.isArray(data?.motifs) ? data.motifs : [])
    .filter((m) => retenus.has(m?.statut) && m.libelle).map((m) => m.libelle))]
  const visibles = points.slice(0, MAX_POINTS)
  const titre = etat === 'bloquant' ? 'Ce qui bloque :' : 'À compléter :'
  return (
    <div data-testid="cal-pret-points-dossier">
      {loading && <p className="text-muted-foreground">Lecture des points du dossier…</p>}
      {!loading && error && <p className="text-muted-foreground">{`${error} « Régler » ouvre le verdict détaillé.`}</p>}
      {!loading && !error && points.length > 0 && (
        <>
          <p className="font-medium">{titre}</p>
          <ul className="list-disc pl-5">{visibles.map((libelle) => <li key={libelle}>{libelle}</li>)}</ul>
          {points.length > visibles.length && (
            <p className="text-muted-foreground">{`… et ${points.length - visibles.length} autre${points.length - visibles.length > 1 ? 's' : ''} : « Régler » ouvre la liste complète.`}</p>
          )}
        </>
      )}
    </div>
  )
}

/* T4-U4-014 — les contrôles dont le geste servi renvoie au lead (« saisissez la facture du lead », « Saisir la
   facture ») : sur un calepinage SANS lead (créé depuis un client), la bulle relit le rattachement servi
   (`GET calepinages/<pk>/`) et dit le geste faisable à la place. */
const GESTE_SANS_LEAD = {
  taille_sans_facture: 'Ce calepinage n’a pas de lead : aucune facture à lire. Choisissez le nombre de panneaux à '
    + 'l’étape Panneaux, ou rattachez un lead pour dimensionner sur sa facture.',
}
function useSansLead(calepinageId, actif) {
  const { data } = useResource(
    (id) => calepinageApi.calepinages.get(id), actif ? calepinageId : null,
    { select: (r) => r?.data ?? null, enabled: actif && calepinageId != null },
  )
  return data ? data.lead == null : null
}

/** Le « ? » de la ligne : cause servie + phrase du registre + geste, dans UNE bulle. Rien à dire ⇒ rien. */
function Pourquoi({ controle }) {
  const calepinageId = useContext(CalepinageDeLaListe)
  const entrees = useExplications()
  const entree = entrees?.find((e) => e.cle === `controle.${controle.code}`) ?? null
  const cause = controle.etat !== 'ok' ? controle.cause : ''
  const gesteServi = controle.geste && controle.etat !== 'ok' ? controle.geste : ''
  // F3 — le registre publie une entrée `controle.<code>` par contrôle (ce qu'il vérifie + quoi faire) :
  // le « ? » est sur CHAQUE ligne, ok compris, dès qu'un texte existe — jamais un cercle qui n'ouvre rien
  // (registre encore en lecture et aucun autre texte : pas de « ? » pour l'instant).
  if (!cause && !controle.seuil_source && !gesteServi && !entree) return null
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button type="button" className="cdoc-aide" aria-label={`Pourquoi : ${controle.libelle}`}
          data-grandeur={`controle.${controle.code}`}>
          <span aria-hidden="true">?</span>
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-80 text-sm leading-relaxed text-foreground normal-case tracking-normal">
        <ContenuPourquoi controle={controle} calepinageId={calepinageId} cause={cause} entree={entree} gesteServi={gesteServi} />
      </PopoverContent>
    </Popover>
  )
}

/** T4-U4-007 — les points SERVIS par « Prêt à envoyer » (`controles[].points[]`) : phrase (clé interne retirée) et
    geste, mot pour mot, quatre au plus dans la bulle. */
function PointsServis({ points, etat }) {
  const visibles = points.slice(0, MAX_POINTS)
  return (
    <div data-testid="cal-pret-points-dossier" data-source="servi">
      <p className="font-medium">{etat === 'bloquant' ? 'Ce qui bloque :' : 'À compléter :'}</p>
      <ul className="list-disc pl-5">
        {visibles.map((p, i) => (
          <li key={`${p.code}-${i}`}>
            {p.phrase}
            {p.geste ? <span className="text-muted-foreground">{` — ${p.geste}`}</span> : null}
          </li>
        ))}
      </ul>
      {points.length > visibles.length && (
        <p className="text-muted-foreground">{`… et ${points.length - visibles.length} autre${points.length - visibles.length > 1 ? 's' : ''} : « Régler » ouvre la liste complète.`}</p>
      )}
    </div>
  )
}

/* Monté à l'ouverture de la bulle seulement : la lecture du rattachement (T4-U4-014) ne part qu'à ce moment. */
function ContenuPourquoi({ controle, calepinageId, cause, entree, gesteServi }) {
  const gesteSansLead = controle.etat !== 'ok' ? GESTE_SANS_LEAD[controle.code] : null
  const sansLead = useSansLead(calepinageId, Boolean(gesteSansLead))
  const remplace = Boolean(gesteSansLead) && sansLead === true
  const dossier = controle.code === 'verdict_electrique' && controle.etat !== 'ok'
  // Points SERVIS d'abord ; la relecture d'`evaluer-electrique` n'est plus qu'un repli quand le serveur n'en sert pas.
  const points = dossier ? pointsServis(controle) : []
  const causeLue = sansCleInterne(cause)
  // `cause` = la phrase du premier point servi : jamais dite deux fois.
  const causeAffichee = causeLue && !points.some((p) => p.phrase === causeLue) ? causeLue : ''
  return (
        <div className="flex flex-col gap-2">
          {points.length > 0 && <PointsServis points={points} etat={controle.etat} />}
          {dossier && points.length === 0 && calepinageId != null && (
            <PointsDossier calepinageId={calepinageId} etat={controle.etat} />
          )}
          {causeAffichee && <p>{causeAffichee}</p>}
          {entree && !remplace && <p>{remplirPhrase(entree, controle)}</p>}
          {controle.seuil_source && <p className="text-muted-foreground">{`Source du seuil : ${controle.seuil_source}.`}</p>}
          {remplace && <p className="text-muted-foreground" data-testid="cal-pret-sans-lead">{gesteSansLead}</p>}
          {gesteServi && !remplace && <p className="text-muted-foreground">{gesteServi}</p>}
          {entree?.geste && !remplace && <p className="text-muted-foreground">{entree.geste}</p>}
        </div>
  )
}

/* ACAL1983 — « Fiche incomplète » : le bouton dit le geste SERVI (« Compléter la fiche du module »), pas le générique. */
const libelleBouton = (controle, etape) => {
  const geste = String(controle?.geste || '')
  if (/^Compléter la fiche/.test(geste) && geste.length <= 48) return geste
  return etape ? `Régler dans ${etape}` : 'Régler'
}

function Ligne({ controle, onRegler }) {
  const cible = cibleDuReglage(controle) // T4-U4-007 — la cible du point servi
  const aRegler = (controle.etat === 'a_regler' || controle.etat === 'bloquant') && Boolean(cible?.onglet)
  const etape = libelleEtape(cible)
  return (
    <li data-testid={`cal-pret-ligne-${controle.code}`} data-etat={controle.etat} className="cdoc-ligne">
      <Pastille etat={controle.etat} />
      <span className="cdoc-ligne-texte">
        <span className="cdoc-ligne-titre">{controle.libelle}</span>
        {controle.valeur_texte ? <span className="cdoc-ligne-detail">{valeurAffichee(controle)}</span> : null}
      </span>
      <Pourquoi controle={controle} />
      {aRegler && (
        <button type="button" data-testid={`cal-pret-regler-${controle.code}`} className="cdoc-regler"
          onClick={() => onRegler(cible)}>
          {libelleBouton(controle, etape)}
        </button>
      )}
    </li>
  )
}

const estPoint = (c) => c.etat === 'a_regler' || c.etat === 'bloquant'

/* ACAL1725 — un groupe qui porte un point à régler reste déplié (ses points d'abord) ; un groupe SANS point se
   replie sur UNE ligne « Électrique — 4 bons » (ses contrôles restent là, un clic les ouvre) : les quinze
   contrôles tiennent dans la carte sans liste à défilement. Le compte ne vient que des états servis. */
/* `serre` (plus de dix contrôles : la maquette en dessine dix) : un groupe déplié ne montre que ses points, le
   reste suit sur une ligne « Autres contrôles — 3 bons ». Les comptes ne viennent que des états servis. */
const compteDe = (controles) => {
  const bons = controles.filter((c) => c.etat === 'ok').length
  const infos = controles.length - bons
  return [bons > 0 && `${bons} ${bons > 1 ? 'bons' : 'bon'}`, infos > 0 && `${infos} pour information`].filter(Boolean).join(' · ')
}

function Repliable({ titre, controles, onRegler, className = '', ...props }) {
  return (
    <details className={`cdoc-groupe-replie ${className}`} {...props}>
      <summary>
        <ChevronRight size={16} className="cdoc-chevron" aria-hidden="true" />
        <h3 className="cdoc-groupe-titre">{`${titre} — ${compteDe(controles)}`}</h3>
      </summary>
      <ul className="cdoc-lignes">
        {controles.map((c) => <Ligne key={c.code} controle={c} onRegler={onRegler} />)}
      </ul>
    </details>
  )
}

function Groupe({ groupe, onRegler, serre = false }) {
  const rangees = rangerControles(groupe.controles)
  const testid = `cal-pret-groupe-${groupe.cle}`
  if (!rangees.some(estPoint)) {
    return <Repliable titre={groupe.libelle} controles={rangees} onRegler={onRegler} className="cdoc-groupe" data-testid={testid} />
  }
  const visibles = serre ? rangees.filter(estPoint) : rangees
  const reste = serre ? rangees.filter((c) => !estPoint(c)) : []
  return (
    <div className="cdoc-groupe" data-testid={testid}>
      <h3 className="cdoc-groupe-titre">{groupe.libelle}</h3>
      <ul className="cdoc-lignes">
        {visibles.map((c) => <Ligne key={c.code} controle={c} onRegler={onRegler} />)}
      </ul>
      {reste.length > 0 && <Repliable titre="Autres contrôles" controles={reste} onRegler={onRegler} />}
    </div>
  )
}

function messagePied(controles) {
  const bloquants = controles.filter((c) => c.etat === 'bloquant').length
  const aRegler = controles.filter((c) => c.etat === 'a_regler').length
  if (bloquants > 0) {
    return `${bloquants > 1 ? 'Ces points bloquent' : 'Ce point bloque'} le devis : à régler avant de le générer.`
  }
  if (aRegler > 0) {
    return `${aRegler > 1 ? 'Les points à régler n’empêchent' : 'Le point à régler n’empêche'} pas le devis : `
      + `${aRegler > 1 ? 'ils restent signalés' : 'il reste signalé'} tant qu’${aRegler > 1 ? 'ils ne sont' : 'il n’est'} pas réglé${aRegler > 1 ? 's' : ''}.`
  }
  return null
}

/* ACAL1830 (maquette v2 Electrique.dc.html) — la carte « Prêt à envoyer ? » EN TÊTE du panneau : le titre, la pastille
   « N points à régler » et, DANS la carte (fond or pâle), le point à régler avec son « Régler » bleu nuit (le premier de
   la liste rangée ; les suivants, discrets) ; puis la section « Contrôles · N bons » REPLIÉE (coches vertes, « ? » rond).
   Tous les contrôles servis restent à l'écran (rien n'est retiré) ; aucun compte n'est calculé hors des états servis. */
function LigneCourte({ c, premierARegler, onRegler }) {
  const cible = cibleDuReglage(c) // T4-U4-007 — la cible du point servi
  const aRegler = (c.etat === 'a_regler' || c.etat === 'bloquant') && Boolean(cible?.onglet)
  return (
    <li data-testid={`cal-pret-ligne-${c.code}`} data-etat={c.etat} className="cel-pret-ligne">
      {c.etat === 'ok'
        ? <Picto nom="coche" taille={18} epaisseur={2.4} className="cel-pret-coche" />
        : <Pastille etat={c.etat} taille={18} />}
      <span className="cel-pret-texte">
        <span className="cel-pret-titre">{c.libelle}</span>
        {c.valeur_texte ? <span className="cel-pret-detail">{valeurAffichee(c)}</span> : null}
      </span>
      <Pourquoi controle={c} />
      {aRegler && (
        <button type="button" data-testid={`cal-pret-regler-${c.code}`} className="cel-pret-regler"
          data-recommande={c.code === premierARegler ? 'oui' : 'non'}
          onClick={() => onRegler(cible)}>
          Régler
        </button>
      )}
    </li>
  )
}

/* F3 — `attente` : une lecture est en vol. Sans ligne déjà servie, le titre est posé et seules les
   lignes sont grisées (aucun compte inventé) ; avec la lecture précédente, ses lignes restent. */
/* H3 — `avis` (nœud) : l'avis « plus de temps que prévu » posé sous le titre ; sans ligne servie, il
   remplace le squelette. Lignes rangées bloquant, à régler, bon, info (`rangerControles`) : le point à
   régler est EN TÊTE de la carte, jamais sous le pli. */
function ListeCourte({ controles, testIdCompte, onRegler, attente = false, avis = null }) {
  const n = controles.filter((c) => c.etat === 'a_regler' || c.etat === 'bloquant').length
  const lignes = rangerControles(controles)
  const premiere = (attente || Boolean(avis)) && controles.length === 0
  const aTraiter = lignes.filter((c) => c.etat === 'a_regler' || c.etat === 'bloquant')
  const autres = lignes.filter((c) => c.etat !== 'a_regler' && c.etat !== 'bloquant')
  const nbBons = autres.filter((c) => c.etat === 'ok').length
  // ACAL1543 — UN seul « Régler » appuyé à la fois : le premier de la liste rangée ; les autres sont discrets.
  const premierARegler = aTraiter.find((c) => c.cible?.onglet)?.code
  return (
    <section data-testid="cal-pret-a-envoyer" aria-labelledby="cel-pret-titre" aria-busy={attente || undefined} className="cel-pret">
      <div className="cel-pret-carte" data-ton={n > 0 ? 'a_regler' : 'ok'}>
        <div className="cel-pret-tete">
          <h2 id="cel-pret-titre">Prêt à envoyer ?</h2>
          {!premiere && (
            <span data-testid={testIdCompte} className="cel-pret-badge" data-ton={n > 0 ? 'a_regler' : 'ok'}>
              {n > 0 ? `${n} point${n > 1 ? 's' : ''} à régler` : 'Prêt à envoyer'}
            </span>
          )}
        </div>
        {avis}
        {premiere && !avis && (
          <ul className="cel-pret-lignes" data-testid="cel-pret-attente" aria-label="Lecture des contrôles en cours">
            {[0, 1, 2].map((i) => <li key={i} className="cel-pret-ligne cel-pret-squelette"><span /></li>)}
          </ul>
        )}
        {!premiere && aTraiter.length > 0 && (
          <ul className="cel-pret-lignes cel-pret-lignes-regler">
            {aTraiter.map((c) => <LigneCourte key={c.code} c={c} premierARegler={premierARegler} onRegler={onRegler} />)}
          </ul>
        )}
        {!premiere && lignes.length === 0 && <p className="cel-pret-vide">Aucun contrôle publié pour cette étape.</p>}
      </div>
      {!premiere && autres.length > 0 && (
        <details className="cel-pret-bons" data-testid="cal-pret-bons">
          <summary>{nbBons > 0 ? `Contrôles · ${nbBons} ${nbBons > 1 ? 'bons' : 'bon'} sur ${lignes.length}` : 'Autres contrôles'}</summary>
          <ul className="cel-pret-lignes">
            {autres.map((c) => <LigneCourte key={c.code} c={c} premierARegler={premierARegler} onRegler={onRegler} />)}
          </ul>
        </details>
      )}
    </section>
  )
}

/* H3 — présentation par étape EN ATTENTE (aucune lecture servie encore) : le titre, des lignes grisées
   (ou l'avis « plus de temps que prévu ») et le `pied` ; aucun compte inventé. */
function AttenteGroupes({ avis, attente, pied }) {
  return (
    <section data-testid="cal-pret-a-envoyer" aria-labelledby="cdoc-pret-titre" aria-busy={attente || undefined} className="cdoc-pret">
      <div className="cdoc-pret-tete">
        <div className="cdoc-pret-titres">
          <h2 id="cdoc-pret-titre" className="cdoc-titre">Prêt à envoyer ?</h2>
        </div>
      </div>
      {avis}
      {!avis && (
        <ul className="cel-pret-lignes" data-testid="cel-pret-attente" aria-label="Lecture des contrôles en cours">
          {[0, 1, 2, 3, 4].map((i) => <li key={i} className="cel-pret-ligne cel-pret-squelette"><span /></li>)}
        </ul>
      )}
      {pied && <div className="cdoc-pied"><div className="cdoc-pied-texte" />{pied}</div>}
    </section>
  )
}

export default function GroupesPretAEnvoyer({ calepinageId = null, ...props }) {
  return (
    <CalepinageDeLaListe.Provider value={calepinageId}>
      <Groupes {...props} />
    </CalepinageDeLaListe.Provider>
  )
}

function Groupes({
  groupes, testIdCompte, pied, onRegler, court = false, controles = [], attente = false, avis = null,
}) {
  if (court) return <ListeCourte controles={controles} testIdCompte={testIdCompte} onRegler={onRegler} attente={attente} avis={avis} />
  if ((attente || avis) && groupes.length === 0) return <AttenteGroupes avis={avis} attente={attente} pied={pied} />
  // H3 — les groupes qui portent un point bloquant puis à régler passent EN TÊTE (ordre des étapes
  // gardé à égalité) : le premier point à régler est visible sans défiler.
  const pire = (g) => Math.min(...g.controles.map((c) => ({ bloquant: 0, a_regler: 1 })[c.etat] ?? 2))
  const ranges = groupes.map((g, i) => [g, i]).sort(([a, i], [b, j]) => (pire(a) - pire(b)) || (i - j)).map(([g]) => g)
  const tous = groupes.flatMap((g) => g.controles)
  const avecVerdict = tous.filter((c) => ['ok', 'a_regler', 'bloquant'].includes(c.etat))
  const bons = avecVerdict.filter((c) => c.etat === 'ok').length
  const n = avecVerdict.length - bons
  const message = messagePied(tous)
  return (
    <section data-testid="cal-pret-a-envoyer" aria-labelledby="cdoc-pret-titre" className="cdoc-pret">
      <div className="cdoc-pret-tete">
        <div className="cdoc-pret-titres">
          <h2 id="cdoc-pret-titre" className="cdoc-titre">Prêt à envoyer ?</h2>
          <span data-testid={testIdCompte} className="cdoc-sous">
            {avecVerdict.length > 0 ? phraseDesBons(bons, avecVerdict.length) : 'Aucun contrôle publié pour l’instant.'}
          </span>
        </div>
        <div className="cdoc-pret-etat">
          <Anneau bons={bons} total={avecVerdict.length} />
          <span className="cdoc-badge" data-ton={n > 0 ? 'a_regler' : 'ok'}>
            <Pastille etat={n > 0 ? 'a_regler' : 'ok'} taille={16} />
            {n > 0 ? `${n} point${n > 1 ? 's' : ''} à régler` : 'Prêt à envoyer'}
          </span>
        </div>
      </div>
      {avis}
      <div className="cdoc-groupes" data-testid="cal-pret-groupes">
        {ranges.map((g) => <Groupe key={g.cle} groupe={g} onRegler={onRegler} serre={tous.length > 10} />)}
      </div>
      <div className="cdoc-pied">
        <div className="cdoc-pied-texte">
          {message && <span className="cdoc-note">{message}</span>}
          <div role="group" aria-label="Légende" className="cdoc-legende">
            {LEGENDE.map(([etat, libelle]) => (
              <span key={etat}><Pastille etat={etat} taille={16} />{libelle}</span>
            ))}
          </div>
        </div>
        {pied}
      </div>
    </section>
  )
}
