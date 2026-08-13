import { useEffect, useState } from 'react'
import { Users, AlertTriangle, Download, Plus } from 'lucide-react'
import api from '../../api/axios'
import PageHeader from '../../components/layout/PageHeader'
import {
  Badge, Button, Card, CardContent, EmptyState, Input, Label, Skeleton,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Select, SelectTrigger, SelectContent, SelectItem, SelectValue,
} from '../../ui'
import { formatDate, toNumber } from '../../lib/format'
import { toast, useConfirmDialog } from '../../ui/confirm'

/* ============================================================================
   PACT52 — Registre des bénéficiaires effectifs (UBO, NTMAR30/31).
   ----------------------------------------------------------------------------
   Registre légal marocain : nom, pièce d'identité, nationalité, pourcentage de
   détention, contrôle direct ou indirect. OBLIGATION DE CONFORMITÉ — le modèle
   et ses deux actions serveur (`registre` avec alerte de complétude,
   `export-declaration` au format attendu par l'OMPIC) existaient sans aucun
   écran ni wrapper client.

   RÈGLE DE LA TÂCHE : tant que la somme des pourcentages déclarés est SOUS le
   seuil, l'alerte de complétude est AFFICHÉE — jamais masquée, jamais réduite
   à une pastille discrète. Le seuil et le verdict viennent du serveur
   (`complet`), jamais d'un calcul refait ici.

   Endpoints (apps/fiscal/views.py, IsResponsableOrAdmin, company-scopé) :
     GET    /fiscal/beneficiaires-effectifs/registre/
     GET    /fiscal/beneficiaires-effectifs/export-declaration/
     POST   /fiscal/beneficiaires-effectifs/
     DELETE /fiscal/beneficiaires-effectifs/{id}/
   ========================================================================== */

const TYPES_CONTROLE = [
  { value: 'direct', label: 'Contrôle direct' },
  { value: 'indirect', label: 'Contrôle indirect' },
]

export default function BeneficiairesEffectifsPage() {
  const { confirmDelete } = useConfirmDialog()
  const [registre, setRegistre] = useState(null)
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)
  const [busy, setBusy] = useState(false)

  // ── Déclaration d'un bénéficiaire ──
  const [ouverte, setOuverte] = useState(false)
  const [nom, setNom] = useState('')
  const [cin, setCin] = useState('')
  const [nationalite, setNationalite] = useState('')
  const [pourcentage, setPourcentage] = useState('')
  const [typeControle, setTypeControle] = useState('direct')
  const [dateDeclaration, setDateDeclaration] = useState('')

  const charger = () => api.get('/fiscal/beneficiaires-effectifs/registre/')
    .then((r) => { setRegistre(r.data); setErreur(false) })
    .catch(() => { setRegistre(null); setErreur(true) })
    .finally(() => setLoading(false))

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { charger() }, [])

  const ouvrir = () => {
    setOuverte(true)
    setNom(''); setCin(''); setNationalite('')
    setPourcentage(''); setTypeControle('direct'); setDateDeclaration('')
  }

  const declarer = async () => {
    setBusy(true)
    try {
      // `company` est imposée par le serveur (CompanyScopedModelViewSet).
      await api.post('/fiscal/beneficiaires-effectifs/', {
        nom,
        cin_passeport: cin,
        nationalite,
        pourcentage_detention: pourcentage,
        type_controle: typeControle,
        date_declaration: dateDeclaration || null,
      })
      toast.success('Bénéficiaire effectif déclaré.')
      setOuverte(false)
      setLoading(true)
      await charger()
    } catch {
      toast.error('Déclaration impossible.')
    } finally { setBusy(false) }
  }

  const supprimer = async (ubo) => {
    const ok = await confirmDelete({
      title: `Retirer ${ubo.nom} du registre ?`,
      description: 'Le registre légal sera recalculé ; l\'alerte de complétude '
        + 'peut réapparaître.',
    })
    if (!ok) return
    try {
      await api.delete(`/fiscal/beneficiaires-effectifs/${ubo.id}/`)
      setLoading(true)
      await charger()
    } catch {
      toast.error('Suppression impossible.')
    }
  }

  // Export au format attendu par l'OMPIC — dépôt MANUEL par le dirigeant :
  // aucune transmission automatique n'existe (et n'est souhaitée).
  const exporter = async () => {
    try {
      const res = await api.get('/fiscal/beneficiaires-effectifs/export-declaration/')
      const lignes = res.data?.lignes ?? []
      const entetes = ['nom', 'cin_passeport', 'nationalite',
        'pourcentage_detention', 'type_controle', 'date_declaration']
      const echapper = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`
      const csv = [
        entetes.map(echapper).join(';'),
        ...lignes.map((l) => entetes.map((c) => echapper(l[c])).join(';')),
      ].join('\r\n')
      const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'beneficiaires-effectifs-ompic.csv'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      setTimeout(() => URL.revokeObjectURL(url), 10000)
    } catch {
      toast.error('Export indisponible.')
    }
  }

  const beneficiaires = registre?.beneficiaires ?? []
  const total = toNumber(registre?.total_pourcentage) || 0
  const complet = !!registre?.complet

  return (
    <div className="page">
      <PageHeader
        title="Bénéficiaires effectifs (UBO)"
        subtitle="Registre légal marocain des bénéficiaires effectifs — obligation de conformité. L'export reprend la structure attendue par l'OMPIC pour un dépôt manuel."
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Button onClick={ouvrir}>
          <Plus /> Déclarer un bénéficiaire
        </Button>
        <Button variant="outline" onClick={exporter}>
          <Download /> Export OMPIC (CSV)
        </Button>
      </div>

      {/* ALERTE DE COMPLÉTUDE — affichée tant que le serveur ne déclare pas le
          registre complet. Jamais masquée : c'est l'exigence de la tâche. */}
      {!loading && !erreur && registre && !complet && (
        <Card className="mb-4 flex items-start gap-2 border-destructive/40 p-3 text-sm"
              role="alert">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive"
                         aria-hidden="true" />
          <div>
            <p className="m-0 font-semibold text-destructive">
              Registre incomplet — {total}&nbsp;% de détention déclarés
            </p>
            <p className="m-0 text-muted-foreground">
              La somme des pourcentages déclarés reste sous le seuil légal de
              complétude. Déclarez les bénéficiaires manquants avant tout dépôt.
            </p>
          </div>
        </Card>
      )}
      {!loading && !erreur && registre && complet && (
        <p className="mb-4 text-sm">
          <Badge tone="success">Registre complet</Badge>{' '}
          <span className="text-muted-foreground">
            {total}&nbsp;% de détention déclarés.
          </span>
        </p>
      )}

      <Card>
        <CardContent className="p-0">
          {loading && <Skeleton className="m-4 h-24" />}
          {!loading && erreur && (
            <EmptyState
              title="Chargement impossible"
              description="Le registre des bénéficiaires effectifs n'a pas pu être chargé."
            />
          )}
          {!loading && !erreur && beneficiaires.length === 0 && (
            <EmptyState
              icon={Users}
              title="Aucun bénéficiaire déclaré"
              description="Le registre est vide : déclarez les personnes physiques détenant ou contrôlant la société."
            />
          )}
          {!loading && !erreur && beneficiaires.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm"
                     aria-label="Registre des bénéficiaires effectifs">
                <thead>
                  <tr className="border-b border-border">
                    {['Nom', 'CIN / Passeport', 'Nationalité', '% détention',
                      'Contrôle', 'Déclaré le', ''].map((c, i) => (
                        <th key={c || `col${i}`} scope="col"
                            className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          {c}
                        </th>
                      ))}
                  </tr>
                </thead>
                <tbody>
                  {beneficiaires.map((u) => (
                    <tr key={u.id} className="border-b border-border/60 last:border-b-0">
                      <td className="px-3 py-2 text-foreground">{u.nom}</td>
                      <td className="px-3 py-2 text-foreground">{u.cin_passeport || '—'}</td>
                      <td className="px-3 py-2 text-foreground">{u.nationalite || '—'}</td>
                      <td className="px-3 py-2 tabular-nums text-foreground">
                        {u.pourcentage_detention}&nbsp;%
                      </td>
                      <td className="px-3 py-2 text-foreground">
                        {u.type_controle === 'indirect' ? 'Indirect' : 'Direct'}
                      </td>
                      <td className="px-3 py-2 text-foreground">
                        {u.date_declaration ? formatDate(u.date_declaration) : '—'}
                      </td>
                      <td className="px-3 py-2 text-right">
                        <Button size="sm" variant="ghost"
                                onClick={() => supprimer(u)}
                                aria-label={`Retirer ${u.nom} du registre`}>
                          Retirer
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={ouverte} onOpenChange={(o) => { if (!o) setOuverte(false) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Déclarer un bénéficiaire effectif</DialogTitle>
            <DialogDescription>
              Personne physique détenant ou contrôlant la société, directement
              ou indirectement.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="ubo-nom">Nom</Label>
              <Input id="ubo-nom" value={nom} onChange={(e) => setNom(e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="ubo-cin">CIN / Passeport</Label>
              <Input id="ubo-cin" value={cin} onChange={(e) => setCin(e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="ubo-nationalite">Nationalité</Label>
              <Input id="ubo-nationalite" value={nationalite}
                     onChange={(e) => setNationalite(e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="ubo-pourcentage">% de détention</Label>
              <Input id="ubo-pourcentage" type="number" step="any"
                     value={pourcentage}
                     onChange={(e) => setPourcentage(e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="ubo-controle">Type de contrôle</Label>
              <Select value={typeControle} onValueChange={setTypeControle}>
                <SelectTrigger id="ubo-controle" aria-label="Type de contrôle">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TYPES_CONTROLE.map((t) => (
                    <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="ubo-date">Date de déclaration</Label>
              <Input id="ubo-date" type="date" value={dateDeclaration}
                     onChange={(e) => setDateDeclaration(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOuverte(false)}>Annuler</Button>
            <Button loading={busy} disabled={!nom || !pourcentage} onClick={declarer}>
              Déclarer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
