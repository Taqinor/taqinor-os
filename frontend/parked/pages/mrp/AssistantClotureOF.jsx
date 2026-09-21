// NTMFG28 — Assistant de clôture d'OF avec saisie qualité groupée : wizard
// 2 écrans (1. saisie groupée quantité bonne/rebut + motif par opération
// restante ; 2. confirmation) qui appelle EN UN SEUL CLIC final l'endpoint
// composite `cloture-assistee` (apps/mrp/views.py), lequel réutilise en
// séquence les MÊMES services `terminer_operation` que le terminal atelier
// (NTMFG8) — jamais un chemin de clôture parallèle. Réservé responsable/admin
// (garde côté backend `IsResponsableOrAdmin`).
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { CheckCircle2, ClipboardCheck } from 'lucide-react'
import mrpApi from '../../api/mrpApi'
import {
  Badge, Button, Card, CardContent, EmptyState, Input, Select, SelectContent,
  SelectItem, SelectTrigger, SelectValue, Spinner,
} from '../../ui'
import { PageHeader } from '../../ui/PageHeader'

const MOTIFS_REBUT = [
  { value: 'casse', label: 'Casse' },
  { value: 'defaut', label: 'Défaut' },
  { value: 'erreur', label: 'Erreur' },
  { value: 'autre', label: 'Autre' },
]

function LigneSaisie({ operation, saisie, onChange }) {
  return (
    <Card className="mb-2">
      <CardContent className="py-3">
        <div className="flex items-center justify-between gap-2 mb-2">
          <div className="font-medium">{operation.ordre}. {operation.libelle}</div>
          <Badge tone="neutral">{operation.statut}</Badge>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-sm text-muted-foreground" htmlFor={`bonne-${operation.id}`}>
            Quantité bonne
          </label>
          <Input id={`bonne-${operation.id}`} type="number" min="0" step="any" className="w-24"
                 value={saisie.quantite_bonne}
                 onChange={(e) => onChange({ ...saisie, quantite_bonne: e.target.value })} />
          <label className="text-sm text-muted-foreground" htmlFor={`rebut-${operation.id}`}>
            Quantité rebut
          </label>
          <Input id={`rebut-${operation.id}`} type="number" min="0" step="any" className="w-24"
                 value={saisie.quantite_rebut}
                 onChange={(e) => onChange({ ...saisie, quantite_rebut: e.target.value })} />
          {Number(saisie.quantite_rebut) > 0 && (
            <Select value={saisie.motif_rebut} onValueChange={(v) => onChange({ ...saisie, motif_rebut: v })}>
              <SelectTrigger className="w-40"><SelectValue placeholder="Motif du rebut" /></SelectTrigger>
              <SelectContent>
                {MOTIFS_REBUT.map((m) => (
                  <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

export default function AssistantClotureOF() {
  const { ofId } = useParams()
  const navigate = useNavigate()

  const [of, setOf] = useState(null)
  const [loading, setLoading] = useState(true)
  const [ecran, setEcran] = useState(1)
  const [saisies, setSaisies] = useState({}) // { [operationId]: {quantite_bonne, quantite_rebut, motif_rebut} }
  const [envoi, setEnvoi] = useState(false)
  const [resultat, setResultat] = useState(null)
  const [erreur, setErreur] = useState(null)

  useEffect(() => {
    mrpApi.getOrdreFabrication(ofId).then((resp) => {
      const data = resp.data
      setOf(data)
      const init = {}
      for (const op of (data.operations || [])) {
        if (op.statut !== 'terminee') {
          init[op.id] = { quantite_bonne: '', quantite_rebut: '0', motif_rebut: '' }
        }
      }
      setSaisies(init)
      setLoading(false)
    })
  }, [ofId])

  const operationsRestantes = (of?.operations || []).filter((op) => op.statut !== 'terminee')

  const majSaisie = (operationId, next) => {
    setSaisies((s) => ({ ...s, [operationId]: next }))
  }

  const confirmer = async () => {
    setEnvoi(true)
    setErreur(null)
    try {
      const resp = await mrpApi.clotureAssisteeOF(ofId, {
        operations: operationsRestantes.map((op) => ({
          id: op.id,
          quantite_bonne: saisies[op.id]?.quantite_bonne || 0,
          quantite_rebut: saisies[op.id]?.quantite_rebut || 0,
          motif_rebut: saisies[op.id]?.motif_rebut || '',
        })),
      })
      setResultat(resp.data)
    } catch (err) {
      setErreur(err?.response?.data?.detail || 'Clôture assistée impossible.')
    } finally {
      setEnvoi(false)
    }
  }

  if (loading) return <Spinner />

  return (
    <div>
      <PageHeader
        title={`Clôture assistée — OF-${ofId}`}
        subtitle="Saisie groupée quantité bonne/rebut, une seule confirmation."
        icon={ClipboardCheck}
      />
      <Card>
        <CardContent className="pt-4">
          {resultat ? (
            <div className="text-center py-6">
              <CheckCircle2 className="mx-auto mb-2 text-success" size={32} aria-hidden="true" />
              <p className="font-medium">
                {resultat.operations_terminees.length} opération(s) terminée(s).
              </p>
              {resultat.erreurs.length > 0 && (
                <p className="text-sm text-destructive mt-1">
                  {resultat.erreurs.length} opération(s) en erreur — vérifiez les motifs de rebut.
                </p>
              )}
              <Button className="mt-4" onClick={() => navigate('/mrp/ordres-fabrication')}>
                Retour aux Ordres de fabrication
              </Button>
            </div>
          ) : operationsRestantes.length === 0 ? (
            <EmptyState
              title="Toutes les opérations sont déjà terminées."
              action={(
                <Button onClick={() => navigate('/mrp/ordres-fabrication')}>
                  Retour aux Ordres de fabrication
                </Button>
              )}
            />
          ) : (
            <>
              {ecran === 1 && (
                <div>
                  {operationsRestantes.map((op) => (
                    <LigneSaisie
                      key={op.id} operation={op} saisie={saisies[op.id] || {}}
                      onChange={(next) => majSaisie(op.id, next)}
                    />
                  ))}
                  <div className="flex justify-end mt-2">
                    <Button onClick={() => setEcran(2)}>Vérifier et confirmer</Button>
                  </div>
                </div>
              )}

              {ecran === 2 && (
                <div>
                  <div className="grid gap-1 mb-3">
                    {operationsRestantes.map((op) => (
                      <div key={op.id} className="text-sm flex justify-between border-b py-1">
                        <span>{op.ordre}. {op.libelle}</span>
                        <span>
                          Bonne : {saisies[op.id]?.quantite_bonne || 0} · Rebut :{' '}
                          {saisies[op.id]?.quantite_rebut || 0}
                          {Number(saisies[op.id]?.quantite_rebut) > 0
                            && ` (${saisies[op.id]?.motif_rebut || '—'})`}
                        </span>
                      </div>
                    ))}
                  </div>
                  {erreur && (
                    <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-2 text-sm text-destructive mb-2">
                      {erreur}
                    </div>
                  )}
                  <div className="flex justify-between">
                    <Button variant="outline" onClick={() => setEcran(1)}>Précédent</Button>
                    <Button loading={envoi} onClick={confirmer}>Confirmer la clôture assistée</Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
