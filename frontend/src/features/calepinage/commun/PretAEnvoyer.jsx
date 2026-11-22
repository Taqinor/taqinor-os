import { useSearchParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { Badge } from '../../../ui'
import EtatEcranAtelier from '../atelier/EtatEcranAtelier'
import { PARAM_ONGLET } from '../atelier/onglets'
import { PARAM_CHAMP } from '../atelier/ouvrirChamp'
import { libelleEtat } from '../electrique/etatVerdict'
import Pourquoi from './Pourquoi'

/* ============================================================================
   ACAL865 — « PRÊT À ENVOYER ? » (maquette `Electrique.dc.html`).
   ----------------------------------------------------------------------------
   Lit `GET calepinages/<id>/pret-a-envoyer/` (ACAL860, contrat
   `calepinage_pret_a_envoyer.json`) : UN compte (« n points à régler »,
   n = bloquants + à régler, ou « Prêt à envoyer »), puis les rouges et les
   oranges — libellé, valeur servie, « ? » et « Régler » (qui pousse
   `?onglet=<cible.onglet>&champ=<cible.champ>`) —, les `info` en valeur sans
   pastille, les `ok` repliés. Aucun prix, aucun statut : l'écran LIT.
   Partagé : l'étape Électrique le monte en tête (son compte remplace l'ancienne
   synthèse), l'écran Documents le reprendra (ACAL867).
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
  return (
    <li data-testid={`cal-pret-ligne-${controle.code}`}
      className="flex min-h-11 flex-wrap items-center gap-x-2 gap-y-1 border-b border-border py-1.5 text-sm">
      {marque && controle.etat !== 'ok' && <Badge tone={marque.ton}>{marque.libelle}</Badge>}
      <span className="font-medium">{controle.libelle}</span>
      <span className="text-muted-foreground">{controle.valeur_texte}</span>
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

export default function PretAEnvoyer({ calepinageId, testIdCompte }) {
  const [parametres, setParametres] = useSearchParams()
  const { data, loading, error } = useResource(
    (id) => calepinageApi.calepinages.pretAEnvoyer(id), calepinageId,
    { select: (r) => r.data, errorMessage: 'Le contrôle « Prêt à envoyer ? » n’a pas pu être lu.' },
  )
  const lu = typeof data?.pret === 'boolean'
  if (loading || error || !lu) {
    return (
      <EtatEcranAtelier id={calepinageId} loading={loading}
        error={error || 'Le contrôle « Prêt à envoyer ? » n’a pas pu être lu.'} testIdErreur="cal-pret-erreur" />
    )
  }

  const controles = data.controles ?? []
  const n = Number(data.nombre_bloquants ?? 0) + Number(data.nombre_a_regler ?? 0)
  const enTete = controles.filter((c) => c.etat in RANG).sort((a, b) => RANG[a.etat] - RANG[b.etat])
  const reussis = controles.filter((c) => c.etat === 'ok')

  const regler = (cible) => {
    const suivants = new URLSearchParams(parametres)
    suivants.set(PARAM_ONGLET, cible.onglet)
    if (cible.champ) suivants.set(PARAM_CHAMP, cible.champ)
    else suivants.delete(PARAM_CHAMP)
    setParametres(suivants)
  }

  return (
    <section data-testid="cal-pret-a-envoyer" aria-label="Prêt à envoyer ?" className="mb-3 rounded-lg border border-border bg-card p-3">
      <div className="flex flex-wrap items-baseline gap-x-2">
        {n > 0 && <h3 className="text-base font-semibold">Prêt à envoyer ?</h3>}
        <p data-testid={testIdCompte} className="text-base font-medium">
          {n > 0 ? `${n} point${n > 1 ? 's' : ''} à régler` : 'Prêt à envoyer'}
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
