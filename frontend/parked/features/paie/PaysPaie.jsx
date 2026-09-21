import { useEffect, useState } from 'react'
import { Globe, Plus, Sprout, Pencil } from 'lucide-react'
import api from '../../api/axios'
import {
  Button, Card, Badge, Spinner, EmptyState, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Checkbox, DataTable,
} from '../../ui'

/* ============================================================================
   NTPAY12 — Pays de paie.
   ----------------------------------------------------------------------------
   Surface le moteur multi-pays NTPAY7 (`PaysPaie`, `/paie/pays-paie/`) :
   déclarer/activer un pays et voir si son PACK DE CALCUL est réellement livré
   (`moteur_disponible`, dit par le serveur — jamais deviné ici).

   Le Maroc est le pays par défaut : sans aucun pays déclaré, la paie se
   calcule exactement comme avant. Les packs France / Sénégal / Côte d'Ivoire
   sont gatés fondateur — ils n'apparaissent utilisables que si le pays est
   déclaré ET que son moteur est livré.
   ========================================================================== */

const listOf = (data) => (Array.isArray(data) ? data : (data?.results ?? []))

const PAYS_OPTIONS = [
  { value: 'MA', label: 'Maroc', devise: 'MAD' },
  { value: 'FR', label: 'France', devise: 'EUR' },
  { value: 'SN', label: 'Sénégal', devise: 'XOF' },
  { value: 'CI', label: 'Côte d’Ivoire', devise: 'XOF' },
]

export default function PaysPaie() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState(null)

  const load = () =>
    api.get('/paie/pays-paie/')
      .then((r) => setRows(listOf(r.data)))
      .catch(() => toast.error('Chargement des pays de paie impossible.'))
      .finally(() => setLoading(false))

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
    load()
  }, [])

  const seed = async () => {
    setBusy(true)
    try {
      await api.post('/paie/pays-paie/seed-standard/')
      toast.success('Pays Maroc provisionné.')
      await load()
    } catch {
      toast.error('Semis impossible.')
    } finally { setBusy(false) }
  }

  const columns = [
    { id: 'code_iso', header: 'Code', width: 90, accessor: (r) => r.code_iso },
    { id: 'libelle', header: 'Pays', accessor: (r) => r.libelle },
    { id: 'devise', header: 'Devise', width: 100, accessor: (r) => r.devise },
    {
      id: 'moteur', header: 'Pack de calcul', width: 170,
      accessor: (r) => r.moteur_disponible,
      cell: (_v, r) => (
        <Badge tone={r.moteur_disponible ? 'success' : 'neutral'}>
          {r.moteur_disponible ? 'Livré' : 'Non livré'}
        </Badge>
      ),
    },
    {
      id: 'actif', header: 'Statut', width: 110, accessor: (r) => r.actif,
      cell: (_v, r) => (
        <Badge tone={r.actif ? 'success' : 'neutral'}>
          {r.actif ? 'Actif' : 'Inactif'}
        </Badge>
      ),
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Pays de paie
        </h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Le Maroc est le pays par défaut. Un profil sans pays est calculé au
          moteur marocain. Un pays dont le pack de calcul n’est pas livré ne
          peut pas être affecté à un salarié.
        </p>
      </div>

      <div className="flex flex-wrap justify-end gap-2">
        <Button onClick={seed} loading={busy} variant="outline">
          <Sprout size={16} aria-hidden="true" /> Provisionner le Maroc
        </Button>
        <Button onClick={() => { setEditing(null); setDialogOpen(true) }}>
          <Plus size={16} aria-hidden="true" /> Déclarer un pays
        </Button>
      </div>

      <Card className="p-4 sm:p-5">
        {loading ? (
          <div className="flex items-center gap-2 py-6 text-muted-foreground">
            <Spinner className="size-4" /> Chargement…
          </div>
        ) : rows.length === 0 ? (
          <EmptyState icon={Globe} title="Aucun pays de paie déclaré"
            description="Provisionnez le Maroc ou déclarez un pays." />
        ) : (
          <DataTable data={rows} columns={columns} searchable
            exportName="pays-paie"
            rowActions={(r) => [
              {
                id: 'editer', label: 'Éditer le pays', icon: Pencil,
                onClick: () => { setEditing(r); setDialogOpen(true) },
              },
            ]} />
        )}
      </Card>

      {dialogOpen && (
        <PaysDialog
          pays={editing}
          onClose={() => setDialogOpen(false)}
          onSaved={() => { setDialogOpen(false); load() }}
        />
      )}
    </div>
  )
}

function PaysDialog({ pays, onClose, onSaved }) {
  const isEdit = !!pays
  const [codeIso, setCodeIso] = useState(pays?.code_iso || 'MA')
  const [libelle, setLibelle] = useState(pays?.libelle || 'Maroc')
  const [devise, setDevise] = useState(pays?.devise || 'MAD')
  const [moteur, setMoteur] = useState(pays?.moteur || '')
  const [actif, setActif] = useState(pays ? Boolean(pays.actif) : true)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  const choisirPays = (code) => {
    setCodeIso(code)
    const option = PAYS_OPTIONS.find((p) => p.value === code)
    if (option && !isEdit) { setLibelle(option.label); setDevise(option.devise) }
  }

  const submit = async (e) => {
    e.preventDefault()
    if (!libelle.trim()) { setErr('Le libellé du pays est requis.'); return }
    if (!devise.trim()) { setErr('La devise est requise.'); return }
    setSaving(true)
    setErr(null)
    const data = {
      code_iso: codeIso, libelle: libelle.trim(),
      devise: devise.trim().toUpperCase(), moteur: moteur.trim(), actif,
    }
    try {
      if (isEdit) {
        await api.patch(`/paie/pays-paie/${pays.id}/`, data)
        toast.success('Pays mis à jour.')
      } else {
        await api.post('/paie/pays-paie/', data)
        toast.success('Pays déclaré.')
      }
      onSaved()
    } catch (e2) {
      const payload = e2?.response?.data
      setErr(
        payload?.detail
        || payload?.code_iso?.[0]
        || payload?.libelle?.[0]
        || 'Enregistrement impossible.',
      )
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {isEdit ? `Pays — ${pays.code_iso}` : 'Déclarer un pays de paie'}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pp-code" required>Pays</Label>
            <Select value={codeIso} onValueChange={choisirPays}
              disabled={isEdit}>
              <SelectTrigger id="pp-code"><SelectValue /></SelectTrigger>
              <SelectContent>
                {PAYS_OPTIONS.map((p) => (
                  <SelectItem key={p.value} value={p.value}>
                    {p.value} — {p.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex gap-3">
            <div className="flex flex-[2] flex-col gap-1.5">
              <Label htmlFor="pp-libelle" required>Libellé</Label>
              <Input id="pp-libelle" value={libelle}
                onChange={(e) => setLibelle(e.target.value)} />
            </div>
            <div className="flex w-28 flex-col gap-1.5">
              <Label htmlFor="pp-devise" required>Devise</Label>
              <Input id="pp-devise" value={devise}
                onChange={(e) => setDevise(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pp-moteur">Clé de moteur (facultatif)</Label>
            <Input id="pp-moteur" value={moteur}
              onChange={(e) => setMoteur(e.target.value)}
              placeholder="vide = code du pays" />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <Checkbox checked={actif} onCheckedChange={(v) => setActif(Boolean(v))} />
            Actif
          </label>
          {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>
              {saving ? 'Enregistrement…' : (isEdit ? 'Mettre à jour' : 'Déclarer')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
