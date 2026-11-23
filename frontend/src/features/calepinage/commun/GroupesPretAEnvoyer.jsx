import { AlertTriangle, CheckCircle2, Info, OctagonX } from 'lucide-react'
import { Popover, PopoverContent, PopoverTrigger } from '../../../ui/Popover'
import { Icone as Picto } from '../atelier/coque/primitives'
import { ETAPES, etapeDeOnglet } from '../atelier/parcoursGuide'
import { phraseDesBons, rangerControles } from './PretAEnvoyer.helpers'
import useExplications, { remplirPhrase } from './useExplications'

/* ACAL1193 — la présentation « par étape » de « Prêt à envoyer ? » (maquette `Documents.dc.html`,
   `PretAEnvoyer groupes`). Aucun état n'est calculé ici : chaque pastille, chaque phrase et chaque
   cible vient du contrôle SERVI ; les longues explications (cause, registre, geste) sont derrière
   le « ? » de la ligne — rien n'est supprimé. */

const ICONE = { ok: CheckCircle2, a_regler: AlertTriangle, bloquant: OctagonX, info: Info }
const LEGENDE = [
  ['ok', 'Bon'], ['a_regler', 'À régler'], ['bloquant', 'Bloque le devis'],
]
const libelleEtape = (cible) => ETAPES.find((e) => e.cle === etapeDeOnglet(cible?.onglet))?.libelle ?? null

function Pastille({ etat, taille = 22 }) {
  const Icone = ICONE[etat] ?? ICONE.info
  return <Icone size={taille} className="cdoc-ico" data-etat={etat} aria-hidden="true" />
}

/** Le « ? » de la ligne : cause servie + phrase du registre + geste, dans UNE bulle. Rien à dire ⇒ rien. */
function Pourquoi({ controle }) {
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
        <div className="flex flex-col gap-2">
          {cause && <p>{cause}</p>}
          {entree && <p>{remplirPhrase(entree, controle)}</p>}
          {controle.seuil_source && <p className="text-muted-foreground">{`Source du seuil : ${controle.seuil_source}.`}</p>}
          {gesteServi && <p className="text-muted-foreground">{gesteServi}</p>}
          {entree?.geste && <p className="text-muted-foreground">{entree.geste}</p>}
        </div>
      </PopoverContent>
    </Popover>
  )
}

function Ligne({ controle, onRegler }) {
  const aRegler = (controle.etat === 'a_regler' || controle.etat === 'bloquant') && Boolean(controle.cible?.onglet)
  const etape = libelleEtape(controle.cible)
  return (
    <li data-testid={`cal-pret-ligne-${controle.code}`} data-etat={controle.etat} className="cdoc-ligne">
      <Pastille etat={controle.etat} />
      <span className="cdoc-ligne-texte">
        <span className="cdoc-ligne-titre">{controle.libelle}</span>
        {controle.valeur_texte ? <span className="cdoc-ligne-detail">{controle.valeur_texte}</span> : null}
      </span>
      <Pourquoi controle={controle} />
      {aRegler && (
        <button type="button" data-testid={`cal-pret-regler-${controle.code}`} className="cdoc-regler"
          onClick={() => onRegler(controle.cible)}>
          {etape ? `Régler dans ${etape}` : 'Régler'}
        </button>
      )}
    </li>
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
  const aRegler = (c.etat === 'a_regler' || c.etat === 'bloquant') && Boolean(c.cible?.onglet)
  return (
    <li data-testid={`cal-pret-ligne-${c.code}`} data-etat={c.etat} className="cel-pret-ligne">
      {c.etat === 'ok'
        ? <Picto nom="coche" taille={18} epaisseur={2.4} className="cel-pret-coche" />
        : <Pastille etat={c.etat} taille={18} />}
      <span className="cel-pret-texte">
        <span className="cel-pret-titre">{c.libelle}</span>
        {c.valeur_texte ? <span className="cel-pret-detail">{c.valeur_texte}</span> : null}
      </span>
      <Pourquoi controle={c} />
      {aRegler && (
        <button type="button" data-testid={`cal-pret-regler-${c.code}`} className="cel-pret-regler"
          data-recommande={c.code === premierARegler ? 'oui' : 'non'}
          onClick={() => onRegler(c.cible)}>
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
          <summary>{nbBons > 0 ? `Contrôles · ${nbBons} ${nbBons > 1 ? 'bons' : 'bon'}` : 'Autres contrôles'}</summary>
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

export default function GroupesPretAEnvoyer({
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
        <span className="cdoc-badge" data-ton={n > 0 ? 'a_regler' : 'ok'}>
          <Pastille etat={n > 0 ? 'a_regler' : 'ok'} taille={16} />
          {n > 0 ? `${n} point${n > 1 ? 's' : ''} à régler` : 'Prêt à envoyer'}
        </span>
      </div>
      {avis}
      <div className="cdoc-groupes">
        {ranges.map((g) => (
          <div key={g.cle} className="cdoc-groupe" data-testid={`cal-pret-groupe-${g.cle}`}>
            <h3 className="cdoc-groupe-titre">{g.libelle}</h3>
            <ul className="cdoc-lignes">
              {rangerControles(g.controles).map((c) => <Ligne key={c.code} controle={c} onRegler={onRegler} />)}
            </ul>
          </div>
        ))}
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
