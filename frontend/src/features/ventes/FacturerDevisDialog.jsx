// « Facturer » un devis ACCEPTÉ en une fois : facture complète (100 %) + les
// paiements DÉJÀ reçus (0 à 5 lignes) consignés dans le même appel atomique.
// Cas fondateur : la cliente a signé, payé ~90 % en 1 à 3 versements et n'a pas
// pu obtenir sa facture. Contrat : apps/ventes/contract_samples/devis_facturer_complet.json.
import { useEffect, useState } from 'react'
import ventesApi from '../../api/ventesApi'
import {
  Button,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  Input, Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  toast,
} from '../../ui'
import { formatMAD } from '../../lib/format'
import { openPdfBlob } from '../../utils/pdfBlob'
// Mêmes modes que la modale d'encaissement (une seule liste).
import { MODES_PAIEMENT } from './modesPaiement'
import { todayLocalIso } from '../../lib/dateLocale.js'


const MAX_LIGNES = 5
const LIGNES_DEFAUT = 3
const todayIso = () => todayLocalIso()
const ligneVide = () => ({ montant: '', date: todayIso(), mode: 'virement', reference: '' })
const num = (v) => {
  const n = parseFloat(String(v ?? '').replace(',', '.'))
  return Number.isFinite(n) ? n : 0
}

export default function FacturerDevisDialog({ devis, onOpenChange, onDone }) {
  const [lignes, setLignes] = useState(() => Array.from({ length: LIGNES_DEFAUT }, ligneVide))
  const [saving, setSaving] = useState(false)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    if (!devis) return
    // eslint-disable-next-line react-hooks/set-state-in-effect -- (ré)init form on devis change
    setLignes(Array.from({ length: LIGNES_DEFAUT }, ligneVide))
    setErreur('')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [devis?.id])

  const total = num(devis?.total_ttc)
  const paye = lignes.reduce((s, l) => s + num(l.montant), 0)
  const reste = total - paye
  const depasse = paye > total + 0.005
  const futur = lignes.some(l => l.date && l.date > todayIso())

  const maj = (i, patch) =>
    setLignes(ls => ls.map((l, k) => (k === i ? { ...l, ...patch } : l)))

  const submit = async (e) => {
    e?.preventDefault?.()
    if (!devis || depasse || futur) return
    const paiements = lignes
      .filter(l => num(l.montant) > 0)
      .map(l => ({
        montant: String(num(l.montant)),
        date_paiement: l.date,
        mode_paiement: l.mode,
        reference: l.reference || '',
      }))
    setSaving(true)
    setErreur('')
    try {
      const { data } = await ventesApi.facturerComplet(devis.id, { paiements })
      toast.success(
        `Facture ${data.facture_reference} créée — reste à payer ${formatMAD(data.montant_du)}`,
        {
          action: {
            label: 'Ouvrir le PDF',
            onClick: async () => {
              // Le PDF est généré en tâche de fond (202) : on le (re)génère —
              // il doit porter les paiements consignés — puis on attend le fichier.
              try {
                await ventesApi.genererPdfFacture(data.facture_id)
                for (let essai = 0; essai < 10; essai += 1) {
                  await new Promise(r => setTimeout(r, 1500))
                  try {
                    const res = await ventesApi.telechargerPdfFacture(data.facture_id)
                    openPdfBlob(res.data, `${data.facture_reference}.pdf`)
                    return
                  } catch { /* pas encore prêt */ }
                }
                toast.error('PDF encore en préparation : ouvrez-le depuis Ventes → Factures.')
              } catch {
                toast.error('PDF de la facture indisponible pour le moment.')
              }
            },
          },
        },
      )
      onOpenChange?.(false)
      onDone?.(data)
    } catch (err) {
      setErreur(err?.response?.data?.detail
        ?? 'Création de la facture impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={!!devis} onOpenChange={(o) => { if (!o) onOpenChange?.(false) }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Facturer — {devis?.reference}</DialogTitle>
          <DialogDescription>
            {devis?.client_nom ? `${devis.client_nom} — ` : ''}
            Total TTC {formatMAD(devis?.total_ttc)}. Saisissez les paiements
            déjà reçus : la facture complète est créée avec le reste à payer.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="grid gap-3" noValidate>
          <h3 className="text-sm font-medium">Paiements déjà reçus</h3>
          {lignes.map((l, i) => (
            <div key={i} className="grid grid-cols-2 gap-2 rounded-md border p-2"
                 data-testid="facturer-ligne">
              <Input type="number" step="any" min="0" placeholder="Montant (MAD)"
                     aria-label={`Montant paiement ${i + 1}`}
                     value={l.montant}
                     onChange={e => maj(i, { montant: e.target.value })} />
              <Input type="date" max={todayIso()}
                     aria-label={`Date paiement ${i + 1}`}
                     value={l.date}
                     onChange={e => maj(i, { date: e.target.value })} />
              <Select value={l.mode} onValueChange={v => maj(i, { mode: v })}>
                <SelectTrigger aria-label={`Mode paiement ${i + 1}`}><SelectValue /></SelectTrigger>
                <SelectContent>
                  {MODES_PAIEMENT.map(m => (
                    <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Input placeholder="Référence (optionnelle)"
                     aria-label={`Référence paiement ${i + 1}`}
                     value={l.reference}
                     onChange={e => maj(i, { reference: e.target.value })} />
            </div>
          ))}
          {lignes.length < MAX_LIGNES && (
            <Button type="button" variant="outline" size="sm"
                    onClick={() => setLignes(ls => [...ls, ligneVide()])}>
              + Ajouter un paiement
            </Button>
          )}
          <dl className="grid grid-cols-[1fr_auto] gap-x-4 text-sm" data-testid="facturer-resume">
            <dt>Total TTC</dt><dd>{formatMAD(total)}</dd>
            <dt>Déjà payé</dt><dd>{formatMAD(paye)}</dd>
            <dt className="font-medium">Reste à payer</dt>
            <dd className="font-medium" data-testid="facturer-reste">
              {formatMAD(Math.max(reste, 0))}
            </dd>
          </dl>
          {depasse && (
            <p role="alert" className="text-sm text-destructive">
              Le total des paiements dépasse le Total TTC du devis.
            </p>
          )}
          {futur && (
            <p role="alert" className="text-sm text-destructive">
              La date d'un paiement déjà reçu ne peut pas être dans le futur.
            </p>
          )}
          {erreur && <p role="alert" className="text-sm text-destructive">{erreur}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => onOpenChange?.(false)}>
              Annuler
            </Button>
            <Button type="submit" loading={saving} disabled={depasse || futur}>
              Créer la facture
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
