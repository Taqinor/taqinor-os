import { useEffect, useMemo, useState } from 'react'
import { Plus, Check, Banknote } from 'lucide-react'
import { ListShell } from '../../ui/module'
import {
  Segmented, Badge, toast, Button,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Checkbox, confirmLeaveIfDirty,
} from '../../ui'
import { formatNumber } from '../../lib/format'
import { unwrapList } from '../../api/resource'
import rhApi from '../../api/rhApi'

/* ============================================================================
   PACT93 — Primes & indemnités.
   ----------------------------------------------------------------------------
   `TypePrime` (FG193, catalogue) et `PrimeAttribuee` (attribution proposée →
   validée → payée) alimentent le bordereau de paie une fois validées — aucun
   des deux n'avait d'écran. Le catalogue de types vit comme ONGLET du même
   écran. Le montant pré-rempli depuis le type reste MODIFIABLE, et le statut
   affiché vient TOUJOURS du serveur, jamais dérivé côté client.
   ========================================================================== */

const VUES = [
  { value: 'attributions', label: 'Primes attribuées' },
  { value: 'types', label: 'Catalogue de types' },
]

export default function PrimesIndemnites() {
  const [vue, setVue] = useState('attributions')
  const [attributions, setAttributions] = useState([])
  const [types, setTypes] = useState([])
  const [employes, setEmployes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadTick, setReloadTick] = useState(0)
  const [attribOpen, setAttribOpen] = useState(false)
  const [typeOpen, setTypeOpen] = useState(false)

  const recharger = () => setReloadTick((t) => t + 1)

  useEffect(() => {
    let vivant = true
    setLoading(true)
    setError(null)
    Promise.all([
      rhApi.getPrimesAttribuees(),
      rhApi.getTypesPrime(),
      rhApi.getEmployes(),
    ])
      .then(([a, t, e]) => {
        if (!vivant) return
        setAttributions(unwrapList(a))
        setTypes(unwrapList(t))
        setEmployes(unwrapList(e))
      })
      .catch(() => {
        if (!vivant) return
        setError('Impossible de charger les primes & indemnités.')
        toast.error('Impossible de charger les primes & indemnités.')
      })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }, [reloadTick])

  const valider = async (p) => {
    try {
      await rhApi.validerPrimeAttribuee(p.id)
      toast.success('Prime validée.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Validation impossible.')
    }
  }

  const marquerPayee = async (p) => {
    try {
      await rhApi.updatePrimeAttribuee(p.id, { statut: 'payee' })
      toast.success('Prime marquée payée.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Marquage impossible.')
    }
  }

  const tone = (statut) => (statut === 'payee' ? 'success' : statut === 'validee' ? 'info' : 'neutral')

  const attribColumns = useMemo(() => [
    { id: 'employe', header: 'Employé', width: 170, accessor: (p) => p.employe_nom || String(p.employe || ''), cell: (v) => <span className="font-medium">{v || '—'}</span> },
    // FG193 — `type_prime_libelle` vient DÉJÀ du serveur (PrimeAttribueeSerializer).
    { id: 'type', header: 'Type', width: 170, accessor: (p) => p.type_prime_libelle || '', cell: (v) => v || '—' },
    { id: 'periode', header: 'Période', width: 90, accessor: (p) => `${p.mois}/${p.annee}`, cell: (v) => v },
    { id: 'montant', header: 'Montant (MAD)', width: 130, align: 'right', numeric: true, searchable: false, accessor: (p) => Number(p.montant ?? 0), cell: (v) => formatNumber(v, { decimals: 2 }) },
    { id: 'statut', header: 'Statut', width: 120, accessor: (p) => p.statut_display || p.statut || '', cell: (v, p) => <Badge tone={tone(p.statut)}>{v || '—'}</Badge> },
  ], [])

  const typeColumns = useMemo(() => [
    { id: 'libelle', header: 'Libellé', width: 200, accessor: (t) => t.libelle || '', cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'code', header: 'Code', width: 120, accessor: (t) => t.code || '', cell: (v) => v || '—' },
    { id: 'nature', header: 'Nature', width: 120, accessor: (t) => t.nature || '', cell: (v) => (v === 'indemnite' ? 'Indemnité' : 'Prime') },
    { id: 'defaut', header: 'Montant défaut (MAD)', width: 160, align: 'right', numeric: true, searchable: false, accessor: (t) => Number(t.montant_defaut ?? 0), cell: (v) => formatNumber(v, { decimals: 2 }) },
    { id: 'actif', header: 'Actif', width: 90, accessor: (t) => (t.actif ? 'oui' : 'non'), cell: (_v, t) => <Badge tone={t.actif ? 'success' : 'neutral'}>{t.actif ? 'Actif' : 'Inactif'}</Badge> },
  ], [])

  const rowActions = (p) => {
    if (p.statut === 'proposee') return [{ id: 'valider', label: 'Valider', icon: Check, onClick: () => valider(p) }]
    if (p.statut === 'validee') return [{ id: 'payer', label: 'Marquer payée', icon: Banknote, onClick: () => marquerPayee(p) }]
    return []
  }

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2>Primes & indemnités</h2>
      </div>

      <Segmented options={VUES} value={vue} onChange={setVue} aria-label="Vue primes & indemnités" />

      {vue === 'attributions' ? (
        <ListShell
          title="Primes attribuées"
          columns={attribColumns}
          rows={attributions}
          loading={loading}
          error={error}
          searchable
          exportName="primes-attribuees"
          rowActions={rowActions}
          actions={<Button onClick={() => setAttribOpen(true)}><Plus size={15} strokeWidth={1.75} aria-hidden="true" />Nouvelle attribution</Button>}
          emptyTitle="Aucune attribution"
          emptyDescription="Aucune prime attribuée."
        />
      ) : (
        <ListShell
          title="Catalogue de types"
          columns={typeColumns}
          rows={types}
          loading={loading}
          error={error}
          searchable
          exportName="types-prime"
          actions={<Button onClick={() => setTypeOpen(true)}><Plus size={15} strokeWidth={1.75} aria-hidden="true" />Nouveau type</Button>}
          emptyTitle="Aucun type"
          emptyDescription="Aucun type de prime configuré."
        />
      )}

      {attribOpen && (
        <AttributionDialog
          employes={employes}
          types={types}
          onClose={() => setAttribOpen(false)}
          onSaved={() => { setAttribOpen(false); recharger() }}
        />
      )}
      {typeOpen && (
        <TypeDialog
          onClose={() => setTypeOpen(false)}
          onSaved={() => { setTypeOpen(false); recharger() }}
        />
      )}
    </div>
  )
}

function AttributionDialog({ employes, types, onClose, onSaved }) {
  const now = new Date()
  const [employe, setEmploye] = useState('')
  const [typePrime, setTypePrime] = useState('')
  const [annee, setAnnee] = useState(String(now.getFullYear()))
  const [mois, setMois] = useState(String(now.getMonth() + 1))
  const [montant, setMontant] = useState('')
  const [montantModifie, setMontantModifie] = useState(false)
  const [motif, setMotif] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(employe || typePrime || motif)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const valide = Boolean(employe && typePrime)

  // Le montant se PRÉ-REMPLIT depuis le type choisi mais reste modifiable —
  // dès que l'utilisateur touche le champ, on ne l'écrase plus (Done= de PACT93).
  const onTypeChange = (id) => {
    setTypePrime(id)
    if (!montantModifie) {
      const t = types.find((x) => String(x.id) === String(id))
      setMontant(t ? String(t.montant_defaut ?? '') : '')
    }
  }

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.createPrimeAttribuee({
        employe, type_prime: typePrime,
        annee: Number(annee), mois: Number(mois),
        montant: montant || '0', motif: motif || '',
      })
      toast.success('Prime attribuée.')
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.detail || data?.non_field_errors?.[0] || 'Attribution impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Nouvelle attribution</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pa-employe">Employé</Label>
              <select id="pa-employe" value={employe} onChange={(e) => setEmploye(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm">
                <option value="">— Choisir —</option>
                {employes.map((e) => <option key={e.id} value={e.id}>{e.nom} {e.prenom}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pa-type">Type de prime</Label>
              <select id="pa-type" value={typePrime} onChange={(e) => onTypeChange(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm">
                <option value="">— Choisir —</option>
                {types.map((t) => <option key={t.id} value={t.id}>{t.libelle}</option>)}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pa-annee">Année</Label>
              <Input id="pa-annee" type="number" step="any" value={annee} onChange={(e) => setAnnee(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pa-mois">Mois</Label>
              <Input id="pa-mois" type="number" step="any" min="1" max="12" value={mois} onChange={(e) => setMois(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pa-montant">Montant (MAD)</Label>
              <Input id="pa-montant" type="number" step="any" value={montant}
                onChange={(e) => { setMontant(e.target.value); setMontantModifie(true) }} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pa-motif">Motif (optionnel)</Label>
            <Input id="pa-motif" value={motif} onChange={(e) => setMotif(e.target.value)} />
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!valide || saving}>{saving ? 'Enregistrement…' : 'Attribuer'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function TypeDialog({ onClose, onSaved }) {
  const [code, setCode] = useState('')
  const [libelle, setLibelle] = useState('')
  const [nature, setNature] = useState('prime')
  const [montantDefaut, setMontantDefaut] = useState('0')
  const [imposable, setImposable] = useState(true)
  const [actif, setActif] = useState(true)
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(code || libelle)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const valide = Boolean(code.trim() && libelle.trim())

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.createTypePrime({
        code: code.trim(), libelle: libelle.trim(), nature,
        montant_defaut: montantDefaut || '0', imposable, actif,
      })
      toast.success('Type créé.')
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.detail || data?.code?.[0] || 'Création impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Nouveau type de prime/indemnité</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="tp-code">Code</Label>
              <Input id="tp-code" autoFocus value={code} onChange={(e) => setCode(e.target.value)} placeholder="Ex. PANIER" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="tp-libelle">Libellé</Label>
              <Input id="tp-libelle" value={libelle} onChange={(e) => setLibelle(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="tp-nature">Nature</Label>
              <select id="tp-nature" value={nature} onChange={(e) => setNature(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm">
                <option value="prime">Prime</option>
                <option value="indemnite">Indemnité</option>
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="tp-montant">Montant par défaut (MAD)</Label>
              <Input id="tp-montant" type="number" step="any" value={montantDefaut} onChange={(e) => setMontantDefaut(e.target.value)} />
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Checkbox id="tp-imposable" checked={imposable} onCheckedChange={setImposable} />
              <Label htmlFor="tp-imposable">Imposable (indicatif)</Label>
            </div>
            <div className="flex items-center gap-2">
              <Checkbox id="tp-actif" checked={actif} onCheckedChange={setActif} />
              <Label htmlFor="tp-actif">Actif</Label>
            </div>
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!valide || saving}>{saving ? 'Création…' : 'Créer'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
