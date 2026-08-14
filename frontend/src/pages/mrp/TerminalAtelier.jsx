// NTMFG8 — Terminal atelier MES : plein écran mobile-first, gros boutons
// tactiles (cibles ≥44pt, `size="lg"`). Sélection poste -> liste des
// opérations à faire/en cours/en pause de ce poste -> démarrer/pauser/
// reprendre en un tap, terminer avec saisie quantité bonne/rebut (+ motif si
// rebut). Rôle Technicien suffit (pas besoin de responsable) — distinct de
// l'écran de gestion OF (NTMFG9).
import { useEffect, useState } from 'react'
import { Play, Pause, Check, Factory } from 'lucide-react'
import mrpApi from '../../api/mrpApi'
import {
  Card, CardContent, Badge, Spinner, EmptyState, Button, Input,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { PageHeader } from '../../ui/PageHeader'

const STATUT_LABEL = {
  a_faire: 'À faire',
  en_cours: 'En cours',
  en_pause: 'En pause',
}

const MOTIFS_REBUT = [
  { value: 'casse', label: 'Casse' },
  { value: 'defaut', label: 'Défaut' },
  { value: 'erreur', label: 'Erreur' },
  { value: 'autre', label: 'Autre' },
]

function OperationCard({ operation, onChanged }) {
  const [enSaisie, setEnSaisie] = useState(false)
  const [quantiteBonne, setQuantiteBonne] = useState('')
  const [quantiteRebut, setQuantiteRebut] = useState('0')
  const [motifRebut, setMotifRebut] = useState('')
  const [erreur, setErreur] = useState('')

  async function appeler(fonction) {
    setErreur('')
    try {
      await fonction(operation.id)
      onChanged()
    } catch (err) {
      setErreur(err?.response?.data?.detail || 'Action impossible.')
    }
  }

  async function terminer() {
    setErreur('')
    if (Number(quantiteRebut) > 0 && !motifRebut) {
      setErreur('Motif de rebut requis.')
      return
    }
    try {
      await mrpApi.terminerOperationOF(operation.id, {
        quantite_bonne: quantiteBonne || 0,
        quantite_rebut: quantiteRebut || 0,
        motif_rebut: motifRebut,
      })
      setEnSaisie(false)
      onChanged()
    } catch (err) {
      setErreur(err?.response?.data?.detail || "Impossible de terminer l'opération.")
    }
  }

  return (
    <Card className="mb-3">
      <CardContent>
        <div className="flex items-center justify-between gap-2 mb-2">
          <div className="font-medium">{operation.libelle}</div>
          <Badge tone="info">{STATUT_LABEL[operation.statut] || operation.statut}</Badge>
        </div>
        {erreur && <div className="text-destructive text-sm mb-2">{erreur}</div>}

        {!enSaisie && (
          <div className="flex flex-wrap gap-2">
            {operation.statut === 'a_faire' && (
              <Button size="lg" onClick={() => appeler(mrpApi.demarrerOperationOF)}>
                <Play /> Démarrer
              </Button>
            )}
            {operation.statut === 'en_cours' && (
              <>
                <Button size="lg" variant="secondary" onClick={() => appeler(mrpApi.pauserOperationOF)}>
                  <Pause /> Pause
                </Button>
                <Button size="lg" variant="success" onClick={() => setEnSaisie(true)}>
                  <Check /> Terminer
                </Button>
              </>
            )}
            {operation.statut === 'en_pause' && (
              <Button size="lg" onClick={() => appeler(mrpApi.reprendreOperationOF)}>
                <Play /> Reprendre
              </Button>
            )}
          </div>
        )}

        {enSaisie && (
          <div className="flex flex-col gap-2 max-w-sm">
            <label className="text-sm">Quantité bonne
              <Input type="number" min="0" value={quantiteBonne}
                    onChange={(e) => setQuantiteBonne(e.target.value)} />
            </label>
            <label className="text-sm">Quantité rebut
              <Input type="number" min="0" value={quantiteRebut}
                    onChange={(e) => setQuantiteRebut(e.target.value)} />
            </label>
            {Number(quantiteRebut) > 0 && (
              <Select value={motifRebut} onValueChange={setMotifRebut}>
                <SelectTrigger><SelectValue placeholder="Motif du rebut" /></SelectTrigger>
                <SelectContent>
                  {MOTIFS_REBUT.map((m) => (
                    <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            <div className="flex gap-2">
              <Button size="lg" variant="success" onClick={terminer}>Valider</Button>
              <Button size="lg" variant="ghost" onClick={() => setEnSaisie(false)}>Annuler</Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default function TerminalAtelier() {
  const [postes, setPostes] = useState([])
  const [posteId, setPosteId] = useState('')
  const [operations, setOperations] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    mrpApi.getPostesCharge({ actif: true }).then((resp) => {
      const rows = resp.data?.results || resp.data || []
      setPostes(rows)
      if (rows.length && !posteId) setPosteId(String(rows[0].id))
    }).finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function recharger() {
    if (!posteId) { setOperations([]); return }
    mrpApi.getOperationsOF({ poste_charge: posteId }).then((resp) => {
      const rows = resp.data?.results || resp.data || []
      setOperations(rows.filter((o) => o.statut !== 'terminee'))
    })
  }

  useEffect(() => { recharger() }, [posteId]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="max-w-2xl mx-auto">
      <PageHeader title="Terminal atelier" icon={Factory} />
      {loading && <Spinner />}
      {!loading && (
        <>
          <Select value={posteId} onValueChange={setPosteId}>
            <SelectTrigger className="mb-4"><SelectValue placeholder="Poste de charge" /></SelectTrigger>
            <SelectContent>
              {postes.map((p) => (
                <SelectItem key={p.id} value={String(p.id)}>{p.nom}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          {operations.length === 0 && (
            <EmptyState title="Aucune opération à traiter sur ce poste." />
          )}
          {operations.map((op) => (
            <OperationCard key={op.id} operation={op} onChanged={recharger} />
          ))}
        </>
      )}
    </div>
  )
}
