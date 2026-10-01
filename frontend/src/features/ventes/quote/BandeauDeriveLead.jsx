// QJR589 (contrat QJR505 `devis_reappliquer_lead.json`) — la bannière de
// DÉRIVE lead → devis, partagée par l'Édition complète et la fenêtre devis du
// cockpit lead. Le verdict (`lead_valeurs_modifiees`) vient du SERVEUR ; la
// bannière NOMME les champs et propose les deux gestes qui la résolvent :
//   « Reprendre les valeurs du lead » → POST reappliquer-lead
//   « Garder les valeurs du devis »   → POST acquitter-derive
// Sur un ENVOYÉ, le vendeur est prévenu que le client verra la version
// corrigée (D-QJR5-1). Sur un devis figé (accepté…), aucun geste : « Réviser »
// (D-QJR5-2). Le statut est LU, jamais écrit (règle #4).
import { useState } from 'react'
import ventesApi from '../../../api/ventesApi'
import { Button } from '../../../ui'
import fieldLabels from '../../crm/workspace/fieldLabels'

// DC11 / QJR106 / QJR587 / QJR656 — les champs du lead surveillés par
// l'estampille de provenance (`crm.selectors.LEAD_PROVENANCE_FIELDS`) sont
// NOMMÉS par leur `libelleCourt` de `fieldLabels.js` (une seule table, garde
// de contrat dans `fieldLabels.test.jsx`). Un champ inconnu s'affiche sous son
// nom technique plutôt que de disparaître.
const MODIFIABLES = new Set(['brouillon', 'envoye'])

/**
 * @param {number}   devisId
 * @param {string}   statut      statut du devis (lu, jamais écrit)
 * @param {string[]} champs      `lead_valeurs_modifiees` servi par le GET devis
 * @param {function} [onResolu]  (réponse 200 du contrat) après un geste réussi
 * @param {function} [onReviser] geste « Réviser » d'un devis figé
 */
export default function BandeauDeriveLead({ devisId, statut, champs, onResolu, onReviser }) {
  const [enCours, setEnCours] = useState(null)
  const [resolu, setResolu] = useState(false)
  const [erreur, setErreur] = useState(null)

  const liste = (Array.isArray(champs) ? champs : [])
    .filter(c => typeof c === 'string' && c)
  if (resolu || !devisId || !liste.length) return null
  const noms = liste.map(c => fieldLabels[c]?.libelleCourt || c)
  const modifiable = MODIFIABLES.has(statut)

  const agir = async (geste) => {
    setEnCours(geste)
    setErreur(null)
    try {
      const appel = geste === 'reprendre'
        ? ventesApi.reappliquerLeadDevis : ventesApi.acquitterDeriveDevis
      const { data } = await appel(devisId)
      setResolu(true)
      onResolu?.(data)
    } catch (err) {
      const detail = err?.response?.data?.detail
      setErreur(typeof detail === 'string' ? detail : 'L’opération a échoué — réessayez.')
    } finally {
      setEnCours(null)
    }
  }

  return (
    <div
      data-testid="lead-valeurs-modifiees"
      role="status"
      className="mt-3 space-y-2 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning"
    >
      <p>Valeurs du lead modifiées depuis la reprise dans ce devis : {noms.join(', ')}.</p>
      {modifiable ? (
        <>
          {statut === 'envoye' && (
            <p className="text-xs">
              Devis déjà envoyé : en reprenant les valeurs du lead, le client verra la version corrigée.
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" variant="outline"
                    disabled={enCours != null} onClick={() => agir('reprendre')}>
              Reprendre les valeurs du lead
            </Button>
            <Button type="button" size="sm" variant="ghost"
                    disabled={enCours != null} onClick={() => agir('garder')}>
              Garder les valeurs du devis
            </Button>
          </div>
        </>
      ) : (
        <p className="text-xs">
          Ce devis est figé : pour reprendre les valeurs du lead,{' '}
          {onReviser ? (
            <button type="button" className="underline" onClick={onReviser}>Réviser</button>
          ) : 'révisez-le'}
          {' '}(une nouvelle version).
        </p>
      )}
      {erreur && <p role="alert" className="text-xs text-destructive">{erreur}</p>}
    </div>
  )
}
