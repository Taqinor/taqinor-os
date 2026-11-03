// ERR-ACVI9-KANBAN-FROID — le dialogue de `useRaisonFroid` : une raison du contrat, ou rien.
import { useState } from 'react'
import { Button } from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { RAISONS_FROID } from './raisonsFroid'

export default function RaisonFroidDialog({ lead, onFin }) {
  const [raison, setRaison] = useState('')
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onFin(null) }} className="sm:max-w-lg" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Mettre « {lead?.nom || 'ce lead'} » au Froid</h3>
      </div>
      <div className="modal-body">
        <label className="form-label" htmlFor="raison-froid">Raison de mise au Froid</label>
        <select id="raison-froid" className="form-select" value={raison}
                onChange={(e) => setRaison(e.target.value)}>
          <option value="">Raison…</option>
          {RAISONS_FROID.map(([code, libelle]) => (
            <option key={code} value={code}>{libelle}</option>
          ))}
        </select>
      </div>
      <div className="modal-footer">
        <Button type="button" variant="outline" onClick={() => onFin(null)}>Annuler</Button>
        <Button type="button" disabled={!raison} onClick={() => onFin(raison)}>
          Mettre au Froid
        </Button>
      </div>
    </ResponsiveDialog>
  )
}
