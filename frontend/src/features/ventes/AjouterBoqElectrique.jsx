// QJR667 (décision fondateur 01/10/2026 : construire l'écran) — bouton
// « Ajouter le BOQ électrique » de l'Édition complète, sur l'action existante
// `ajouter-boq-electrique` (PV47). Contrat partagé (PACT10) :
// `apps/ventes/contract_samples/devis_boq_electrique.json`.
//
// Geste EXPLICITE : les lignes du bordereau de la conception électrique
// deviennent des lignes du devis. Le serveur n'invente aucun prix (« — à
// chiffrer ») et ne duplique rien sur un second clic. Après un ajout,
// `onAjoute` demande au parent de relire le devis. Rien n'est lu au montage.
import { useState } from 'react'
import { Cable } from 'lucide-react'
import ventesApi from '../../api/ventesApi'
import { Button } from '../../ui'
import { bilanBoq } from './lotsBoq'

/**
 * @param {number}   devisId     devis rouvert en Édition complète
 * @param {boolean}  modifiable  verdict servi (QJR516) : sinon aucun bouton
 * @param {function} [onAjoute]  après un ajout : le parent relit le devis
 */
export default function AjouterBoqElectrique({ devisId, modifiable, onAjoute }) {
  const [resultat, setResultat] = useState(null)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  if (!devisId || !modifiable) return null

  const ajouter = async () => {
    setEnCours(true)
    setErreur('')
    try {
      const { data } = await ventesApi.ajouterBoqElectrique(devisId)
      setResultat(data ?? null)
      if ((data?.creees ?? 0) > 0) onAjoute?.()
    } catch (err) {
      setResultat(null)
      setErreur(err?.response?.data?.detail
        || 'Le bordereau électrique n’a pas pu être ajouté.')
    } finally {
      setEnCours(false)
    }
  }

  return (
    <div className="space-y-1" data-testid="ajouter-boq-electrique">
      <Button type="button" size="sm" variant="outline" disabled={enCours} onClick={ajouter}>
        <Cable className="size-4" aria-hidden="true" /> Ajouter le BOQ électrique
      </Button>
      <p className="text-xs text-muted-foreground">
        Reporte le bordereau de la conception électrique en lignes du devis.
        Enregistrez d’abord vos modifications en cours : l’écran est rechargé.
      </p>
      {resultat && (
        <div className="text-xs" role="status">
          <p>{bilanBoq(resultat)}</p>
          {resultat.manques?.length > 0 && (
            <ul className="list-disc pl-5 text-muted-foreground">
              {resultat.manques.map(m => (
                <li key={m.designation}>{m.designation}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      {erreur && <p className="text-xs text-destructive" role="alert">{erreur}</p>}
    </div>
  )
}
