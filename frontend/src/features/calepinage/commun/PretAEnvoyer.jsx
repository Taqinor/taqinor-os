import { useSearchParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { Badge } from '../../../ui'
import EtatEcranAtelier from '../atelier/EtatEcranAtelier'
import { PARAM_ONGLET } from '../atelier/onglets'
import { PARAM_CHAMP } from '../atelier/ouvrirChamp'
import { libelleEtat } from '../electrique/etatVerdict'
import Pourquoi from './Pourquoi'
import { GROUPES, GROUPE_AUTRES, groupeDuControle } from './PretAEnvoyer.helpers'
import GroupesPretAEnvoyer from './GroupesPretAEnvoyer'

/* ============================================================================
   ACAL865 — « PRÊT À ENVOYER ? » (maquette `Electrique.dc.html`).
   ----------------------------------------------------------------------------
   Lit `GET calepinages/<id>/pret-a-envoyer/` (ACAL860, contrat
   `calepinage_pret_a_envoyer.json`) : UN compte (« n contrôles à régler »,
   n = bloquants + à régler, ou « Prêt à envoyer »), puis les rouges et les
   oranges — libellé, valeur servie, « ? » et « Régler » (qui pousse
   `?onglet=<cible.onglet>&champ=<cible.champ>`) —, les `info` en valeur sans
   pastille, les `ok` repliés. Aucun prix, aucun statut : l'écran LIT.
   Partagé : l'étape Électrique le monte en tête (son compte remplace l'ancienne
   synthèse), l'écran Documents le reprend (ACAL867).

   PROPS (additifs, le comportement par défaut ne change pas) — « POUR L3 » :
   - `groupes` (bool) : rend la maquette `Documents.dc.html` — « N contrôles sur M sont bons »,
     une pastille, les contrôles RANGÉS PAR ÉTAPE (Toit / Panneaux / Électrique / Résultats), une
     ligne par contrôle (pastille d'état, titre, courte phrase servie, « ? » qui ouvre la
     cause longue) et « Régler dans <étape> » sur les points à régler (mêmes cibles qu'avant).
   - `filtre` (clé d'étape : 'toit' | 'panneaux' | 'electrique' | 'resultats') : ne garde que les
     contrôles de CETTE étape — compte et lignes compris, dans les deux présentations
     (l'étape Électrique : `filtre="electrique"`).
   - `pied` (nœud) : en présentation `groupes`, posé à droite de la légende (l'écran Documents y met
     « Générer le devis »). Il reste à l'écran pendant la lecture et après un échec de lecture.
   - `court` (bool, L3 — maquette `Electrique.dc.html`) : la liste COURTE d'une étape (avec `filtre`) —
     « Prêt à envoyer ? » + pastille pâle « N points à régler », une ligne par contrôle servi (coche,
     titre, phrase de 12 px, « ? »), la ligne à régler en or pâle avec « Régler » marine.
   ========================================================================== */

const TON = { bloquant: 'danger', a_regler: 'warning' }
const MOT = { bloquant: 'Bloquant', a_regler: 'À régler' }
// La ligne `verdict_electrique` parle avec les mots de `etatVerdict.js` (ACAL935).
const ETAT_DOSSIER = { ok: 'pret', a_regler: 'a_completer', bloquant: 'bloquant' }

function pastille(controle) {
  if (controle.code === 'verdict_electrique') {
    const points = Number(String(controle.valeur_texte ?? '').match(/\d+/)?.[0] ?? 0)
    const dossier = libelleEtat(ETAT_DOSSIER[controle.etat], points)
    if (dossier) return dossier
  }
  return MOT[controle.etat] ? { libelle: MOT[controle.etat], ton: TON[controle.etat] } : null
}

function Ligne({ controle, onRegler }) {
  const marque = pastille(controle)
  const aRegler = Boolean(TON[controle.etat]) && Boolean(controle.cible?.onglet)
  const pastilleAffichee = Boolean(marque) && controle.etat !== 'ok'
  return (
    <li data-testid={`cal-pret-ligne-${controle.code}`}
      className="flex min-h-11 flex-wrap items-center gap-x-2 gap-y-1 border-b border-border py-1.5 text-sm">
      {pastilleAffichee && <Badge tone={marque.ton}>{marque.libelle}</Badge>}
      <span className="font-medium">{controle.libelle}</span>
      {/* R3-10 : la pastille dit déjà « À compléter : 3 points » — pas deux fois. */}
      {!(pastilleAffichee && controle.valeur_texte === marque.libelle) && (
        <span className="text-muted-foreground">{controle.valeur_texte}</span>
      )}
      <Pourquoi cle={`controle.${controle.code}`} valeurs={controle} />
      {aRegler && (
        <button type="button" data-testid={`cal-pret-regler-${controle.code}`}
          onClick={() => onRegler(controle.cible)}
          className="ml-auto inline-flex min-h-11 items-center rounded-md px-3 text-sm font-medium text-primary hover:underline focus-ring">
          Régler
        </button>
      )}
      {controle.etat !== 'ok' && controle.cause && (
        <p className="w-full text-xs text-muted-foreground">{controle.cause}</p>
      )}
    </li>
  )
}

const RANG = { bloquant: 0, a_regler: 1, info: 2 }

/* F3 (tour 2) — la DERNIÈRE lecture servie, par calepinage (mémoire de la page) : le contrôle est
   recalculé à chaque lecture côté serveur (10 à 25 s mesurés sur la pile de revue) ; en revenant sur
   l'étape (ou après un geste qui la remonte), la liste déjà servie reste affichée — marquée « mise
   à jour en cours » — pendant que la nouvelle lecture arrive, au lieu d'un squelette. Rien n'est
   calculé ici : ce sont les contrôles servis de la lecture précédente. */
const DERNIERES_LECTURES = new Map()

export default function PretAEnvoyer({
  calepinageId, testIdCompte, groupes = false, filtre = null, pied = null, court = false,
}) {
  const [parametres, setParametres] = useSearchParams()
  const { data: lue, loading, error } = useResource(
    (id) => calepinageApi.calepinages.pretAEnvoyer(id), calepinageId,
    { select: (r) => r.data, errorMessage: 'Le contrôle « Prêt à envoyer ? » n’a pas pu être lu.' },
  )
  if (typeof lue?.pret === 'boolean' && !loading) DERNIERES_LECTURES.set(calepinageId, lue)
  const precedente = DERNIERES_LECTURES.get(calepinageId) ?? null
  const data = typeof lue?.pret === 'boolean' && !loading ? lue : (loading ? precedente : lue)
  const lu = typeof data?.pret === 'boolean'
  if (court && loading && !lu) {
    // Le titre est posé tout de suite ; seules les lignes encore en lecture sont grisées.
    return <GroupesPretAEnvoyer court attente controles={[]} testIdCompte={testIdCompte} onRegler={() => {}} />
  }
  if ((loading && !lu) || (!loading && error) || !lu) {
    // Le `pied` (ex. le VRAI bouton de devis relayé, avec ses propres gardes) ne dépend pas de la
    // lecture des contrôles : il reste à l'écran pendant le chargement et après un échec.
    return (
      <>
        <EtatEcranAtelier id={calepinageId} loading={loading}
          error={error || 'Le contrôle « Prêt à envoyer ? » n’a pas pu être lu.'} testIdErreur="cal-pret-erreur" />
        {pied && <div className="cdoc-pied">{pied}</div>}
      </>
    )
  }

  const servis = data.controles ?? []
  const controles = filtre ? servis.filter((c) => groupeDuControle(c) === filtre) : servis
  const n = filtre
    ? controles.filter((c) => c.etat === 'bloquant' || c.etat === 'a_regler').length
    : Number(data.nombre_bloquants ?? 0) + Number(data.nombre_a_regler ?? 0)
  const enTete = controles.filter((c) => c.etat in RANG).sort((a, b) => RANG[a.etat] - RANG[b.etat])
  const reussis = controles.filter((c) => c.etat === 'ok')

  const regler = (cible) => {
    const suivants = new URLSearchParams(parametres)
    suivants.set(PARAM_ONGLET, cible.onglet)
    if (cible.champ) suivants.set(PARAM_CHAMP, cible.champ)
    else suivants.delete(PARAM_CHAMP)
    setParametres(suivants)
  }

  if (court) {
    return <GroupesPretAEnvoyer court attente={loading} controles={controles} testIdCompte={testIdCompte} onRegler={regler} />
  }
  if (groupes) {
    const rangees = [...GROUPES, GROUPE_AUTRES]
      .map((g) => ({ ...g, controles: controles.filter((c) => groupeDuControle(c) === g.cle) }))
      .filter((g) => g.controles.length > 0)
    return <GroupesPretAEnvoyer groupes={rangees} testIdCompte={testIdCompte} pied={pied} onRegler={regler} />
  }

  return (
    <section data-testid="cal-pret-a-envoyer" aria-label="Prêt à envoyer ?" className="mb-3 rounded-lg border border-border bg-card p-3">
      <div className="flex flex-wrap items-baseline gap-x-2">
        {n > 0 && <h3 className="text-base font-semibold">Prêt à envoyer ?</h3>}
        <p data-testid={testIdCompte} className="text-base font-medium">
          {n > 0 ? `${n} contrôle${n > 1 ? 's' : ''} à régler` : 'Prêt à envoyer'}
        </p>
      </div>
      {enTete.length > 0 && (
        <ul className="mt-2">
          {enTete.map((c) => <Ligne key={c.code} controle={c} onRegler={regler} />)}
        </ul>
      )}
      {reussis.length > 0 && (
        <details data-testid="cal-pret-reussis" className="mt-2 text-sm">
          <summary className="inline-flex min-h-11 cursor-pointer items-center font-medium">
            {reussis.length > 1 ? `Voir les ${reussis.length} contrôles réussis` : 'Voir le contrôle réussi'}
          </summary>
          <ul>{reussis.map((c) => <Ligne key={c.code} controle={c} onRegler={regler} />)}</ul>
        </details>
      )}
    </section>
  )
}
