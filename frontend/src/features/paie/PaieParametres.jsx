import { useEffect, useState } from 'react'
import { Sprout, Plus, FileSignature, Download } from 'lucide-react'
import {
  Button, Card, Input, Spinner, EmptyState, Badge, toast,
  Tabs, TabsList, TabsTrigger, TabsContent,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { DataTable } from '../../ui'
import { formatMAD, formatPercent } from '../../lib/format'
import { openPdfBlob } from '../../utils/pdfBlob'
import paieApi from '../../api/paieApi'
import rhApi from '../../api/rhApi'

/* ============================================================================
   UX12 — Paramètres & barèmes de la paie.
   ----------------------------------------------------------------------------
   Constantes versionnées (SMIG/CNSS/AMO/frais pro, date_effet), barème IR,
   catalogue de rubriques (semis en un clic), profils par employé. Édition
   directe des lignes actives ; les montants via formatMAD, taux via
   formatPercent. Aucun prix d'achat/marge.
   ========================================================================== */
export default function PaieParametres() {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Paramètres de paie
        </h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Constantes légales, barème IR, rubriques et profils.
        </p>
      </div>
      <Tabs defaultValue="parametres">
        <TabsList className="flex-wrap">
          <TabsTrigger value="parametres">Paramètres sociaux</TabsTrigger>
          <TabsTrigger value="bareme">Barème IR</TabsTrigger>
          <TabsTrigger value="rubriques">Rubriques</TabsTrigger>
          <TabsTrigger value="profils">Profils</TabsTrigger>
          <TabsTrigger value="mutuelle">Mutuelle</TabsTrigger>
          <TabsTrigger value="simulateur">Simulateur net/brut</TabsTrigger>
        </TabsList>
        <TabsContent value="parametres"><ParametresTab /></TabsContent>
        <TabsContent value="bareme"><BaremeTab /></TabsContent>
        <TabsContent value="rubriques"><RubriquesTab /></TabsContent>
        <TabsContent value="profils"><ProfilsTab /></TabsContent>
        <TabsContent value="mutuelle"><MutuelleTab /></TabsContent>
        <TabsContent value="simulateur"><SimulateurTab /></TabsContent>
      </Tabs>
    </div>
  )
}

/* ── Paramètres sociaux versionnés ── */
function ParametresTab() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  const load = () =>
    paieApi.getParametres({ ordering: '-date_effet' })
      .then((r) => setRows(listOf(r.data)))
      .catch(() => toast.error('Chargement des paramètres impossible.'))
      .finally(() => setLoading(false))
  useEffect(() => { load() }, [])

  const seed = async () => {
    setBusy(true)
    try {
      await paieApi.seedParametresDefaults()
      toast.success('Valeurs légales 2026 provisionnées.')
      await load()
    } catch {
      toast.error('Semis impossible.')
    } finally { setBusy(false) }
  }

  const columns = [
    { id: 'date', header: 'Effet', accessor: (r) => r.date_effet },
    { id: 'smig', header: 'SMIG', align: 'right',
      accessor: (r) => Number(r.smig) || 0, cell: (_v, r) => formatMAD(r.smig) },
    { id: 'plafond', header: 'Plafond CNSS', align: 'right',
      accessor: (r) => Number(r.plafond_cnss) || 0,
      cell: (_v, r) => formatMAD(r.plafond_cnss) },
    { id: 'cnss', header: 'CNSS sal.', align: 'right',
      accessor: (r) => Number(r.taux_cnss_salarial) || 0,
      cell: (_v, r) => formatPercent(r.taux_cnss_salarial, { decimals: 2 }) },
    { id: 'amo', header: 'AMO sal.', align: 'right',
      accessor: (r) => Number(r.taux_amo_salarial) || 0,
      cell: (_v, r) => formatPercent(r.taux_amo_salarial, { decimals: 2 }) },
    { id: 'actif', header: 'État', accessor: (r) => r.actif,
      cell: (_v, r) => (
        <span className="flex items-center gap-1.5">
          {r.actif && <Badge tone="success">Actif</Badge>}
          {r.valide_par_fondateur
            ? <Badge tone="info">Validé</Badge>
            : <Badge tone="warning">À valider</Badge>}
        </span>
      ) },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button onClick={seed} loading={busy} variant="outline">
          <Sprout size={16} aria-hidden="true" /> Provisionner 2026
        </Button>
      </div>
      <Card className="p-4 sm:p-5">
        {loading ? <Loading /> : rows.length === 0 ? (
          <EmptyState icon={Sprout} title="Aucun paramètre"
            description="Provisionnez les valeurs légales 2026 pour démarrer." />
        ) : (
          <DataTable data={rows} columns={columns}
            exportName="parametres-paie" />
        )}
      </Card>
    </div>
  )
}

/* ── Barème IR ── */
function BaremeTab() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    paieApi.getBaremes({ ordering: '-date_effet' })
      .then((r) => setRows(listOf(r.data)))
      .catch(() => toast.error('Chargement du barème IR impossible.'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Card className="p-4"><Loading /></Card>
  if (!rows.length) {
    return (
      <Card className="p-4 sm:p-5">
        <EmptyState icon={Sprout} title="Aucun barème IR"
          description="Le barème IR est provisionné avec les paramètres 2026 (onglet Paramètres sociaux)." />
      </Card>
    )
  }
  return (
    <div className="flex flex-col gap-4">
      {rows.map((b) => (
        <Card key={b.id} className="p-4 sm:p-5">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h3 className="font-display font-semibold">{b.libelle}</h3>
            <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
              Effet {b.date_effet}
              {b.actif && <Badge tone="success">Actif</Badge>}
            </span>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="py-1.5 font-medium">De</th>
                <th className="py-1.5 font-medium">À</th>
                <th className="py-1.5 text-right font-medium">Taux</th>
                <th className="py-1.5 text-right font-medium">À déduire</th>
              </tr>
            </thead>
            <tbody>
              {(b.tranches || []).map((t) => (
                <tr key={t.id} className="border-b border-border/60">
                  <td className="py-1.5 tabular-nums">{formatMAD(t.borne_min)}</td>
                  <td className="py-1.5 tabular-nums">
                    {t.borne_max ? formatMAD(t.borne_max) : '∞'}
                  </td>
                  <td className="py-1.5 text-right tabular-nums">
                    {formatPercent(t.taux, { decimals: 0 })}
                  </td>
                  <td className="py-1.5 text-right tabular-nums">
                    {formatMAD(t.somme_a_deduire)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      ))}
    </div>
  )
}

/* ── Rubriques ── */
function RubriquesTab() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')

  const load = () =>
    paieApi.getRubriques({ ordering: 'ordre' })
      .then((r) => setRows(listOf(r.data)))
      .catch(() => toast.error('Chargement des rubriques impossible.'))
      .finally(() => setLoading(false))
  useEffect(() => { load() }, [])

  const seed = async (kind) => {
    setBusy(kind)
    try {
      if (kind === 'standard') await paieApi.seedRubriquesStandard()
      else await paieApi.seedRubriquesDefaults()
      toast.success('Rubriques provisionnées.')
      await load()
    } catch {
      toast.error('Semis impossible.')
    } finally { setBusy('') }
  }

  const columns = [
    { id: 'code', header: 'Code', width: 100, accessor: (r) => r.code },
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
    { id: 'type', header: 'Type', accessor: (r) => r.type,
      cell: (_v, r) => <Badge tone={r.type === 'retenue' ? 'danger' : 'success'}>
        {r.type}</Badge> },
    { id: 'imposable', header: 'Imposable', accessor: (r) => r.imposable,
      cell: (_v, r) => (r.imposable ? 'Oui' : 'Non') },
    { id: 'cnss', header: 'CNSS', accessor: (r) => r.soumis_cnss,
      cell: (_v, r) => (r.soumis_cnss ? 'Oui' : 'Non') },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap justify-end gap-2">
        <Button onClick={() => seed('defaut')} loading={busy === 'defaut'}
          variant="outline">
          <Sprout size={16} aria-hidden="true" /> Rubriques de base
        </Button>
        <Button onClick={() => seed('standard')} loading={busy === 'standard'}
          variant="outline">
          <Sprout size={16} aria-hidden="true" /> Catalogue standard
        </Button>
      </div>
      <Card className="p-4 sm:p-5">
        {loading ? <Loading /> : rows.length === 0 ? (
          <EmptyState icon={Sprout} title="Aucune rubrique"
            description="Provisionnez le catalogue en un clic." />
        ) : (
          <DataTable data={rows} columns={columns} searchable
            exportName="rubriques-paie" />
        )}
      </Card>
    </div>
  )
}

/* ── Profils de paie par employé ── */
function ProfilsTab() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [stcProfil, setStcProfil] = useState(null)
  const [regimeProfil, setRegimeProfil] = useState(null)
  // WIR3 — onboarding paie : création (profil=null) ou édition d'un ProfilPaie.
  const [profilDialogOpen, setProfilDialogOpen] = useState(false)
  const [editingProfil, setEditingProfil] = useState(null)

  const load = () =>
    paieApi.getProfils()
      .then((r) => setRows(listOf(r.data)))
      .catch(() => toast.error('Chargement des profils impossible.'))
      .finally(() => setLoading(false))
  useEffect(() => { load() }, [])

  const ouvrirCreation = () => { setEditingProfil(null); setProfilDialogOpen(true) }
  const ouvrirEdition = (r) => { setEditingProfil(r); setProfilDialogOpen(true) }

  const columns = [
    { id: 'employe', header: 'Employé', accessor: (r) => r.employe_nom || '',
      cell: (_v, r) => r.employe_nom || `Employé #${r.employe}` },
    { id: 'type', header: 'Rémunération', accessor: (r) => r.type_remuneration },
    { id: 'cnss', header: 'N° CNSS', accessor: (r) => r.numero_cnss || '' },
    { id: 'banque', header: 'Banque', accessor: (r) => r.banque || '' },
    { id: 'regime', header: 'Régime IR', accessor: (r) => r.regime_exoneration,
      cell: (_v, r) => (r.regime_exoneration && r.regime_exoneration !== 'aucun'
        ? <Badge tone="info">{r.regime_exoneration}</Badge>
        : <span className="text-muted-foreground">—</span>) },
    { id: 'actif', header: 'État', accessor: (r) => r.actif,
      cell: (_v, r) => (r.actif
        ? <Badge tone="success">Actif</Badge>
        : <Badge tone="neutral">Inactif</Badge>) },
  ]

  return (
    <>
      <div className="flex justify-end">
        <Button onClick={ouvrirCreation}>
          <Plus size={16} aria-hidden="true" /> Nouveau profil
        </Button>
      </div>
      <Card className="p-4 sm:p-5">
        {loading ? <Loading /> : rows.length === 0 ? (
          <EmptyState icon={Plus} title="Aucun profil de paie"
            description="Les profils rattachent chaque employé RH à ses règles de paie (salaire de base sensible, jamais exposé)." />
        ) : (
          <DataTable data={rows} columns={columns} searchable
            exportName="profils-paie"
            rowActions={(r) => [
              { id: 'editer', label: 'Éditer le profil', onClick: () => ouvrirEdition(r) },
              { id: 'stc', label: 'Solde de tout compte', icon: FileSignature,
                onClick: () => setStcProfil(r) },
              { id: 'regime', label: 'Régime d’exonération IR',
                onClick: () => setRegimeProfil(r) },
            ]} />
        )}
      </Card>
      {profilDialogOpen && (
        <ProfilDialog profil={editingProfil}
          onClose={() => setProfilDialogOpen(false)}
          onSaved={load} />
      )}
      {stcProfil && (
        <StcDialog profil={stcProfil} onClose={() => setStcProfil(null)} />
      )}
      {regimeProfil && (
        <RegimeExonerationDialog profil={regimeProfil}
          onClose={() => setRegimeProfil(null)}
          onSaved={load} />
      )}
    </>
  )
}

/* ── WIR3 — Onboarding paie : création/édition d'un ProfilPaie.
   Couvre type_remuneration/salaire_base/rib/banque + affiliations CNSS/AMO/
   CIMR — sans passer par Django admin. `employe` n'est choisi qu'à la
   création (OneToOne vers rh.DossierEmploye, immuable ensuite). ── */
function ProfilDialog({ profil, onClose, onSaved }) {
  const isEdit = Boolean(profil)
  const [employes, setEmployes] = useState([])
  const [employeId, setEmployeId] = useState(profil?.employe ? String(profil.employe) : '')
  const [typeRemuneration, setTypeRemuneration] = useState(
    profil?.type_remuneration || 'mensuel')
  const [salaireBase, setSalaireBase] = useState(String(profil?.salaire_base ?? '0'))
  const [rib, setRib] = useState(profil?.rib || '')
  const [banque, setBanque] = useState(profil?.banque || '')
  const [affilieCnss, setAffilieCnss] = useState(profil ? Boolean(profil.affilie_cnss) : true)
  const [numeroCnss, setNumeroCnss] = useState(profil?.numero_cnss || '')
  const [affilieAmo, setAffilieAmo] = useState(profil ? Boolean(profil.affilie_amo) : true)
  const [numeroAmo, setNumeroAmo] = useState(profil?.numero_amo || '')
  const [affilieCimr, setAffilieCimr] = useState(profil ? Boolean(profil.affilie_cimr) : false)
  const [numeroCimr, setNumeroCimr] = useState(profil?.numero_cimr || '')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (isEdit) return
    rhApi.getEmployes({ ordering: 'nom' })
      .then((r) => setEmployes(listOf(r.data)))
      .catch(() => toast.error('Chargement des employés impossible.'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const enregistrer = async () => {
    if (!isEdit && !employeId) { toast.error('Choisissez un employé.'); return }
    setBusy(true)
    try {
      await paieApi.saveProfil(profil?.id, {
        ...(isEdit ? {} : { employe: Number(employeId) }),
        type_remuneration: typeRemuneration,
        salaire_base: Number(salaireBase) || 0,
        rib,
        banque,
        affilie_cnss: affilieCnss,
        numero_cnss: numeroCnss,
        affilie_amo: affilieAmo,
        numero_amo: numeroAmo,
        affilie_cimr: affilieCimr,
        numero_cimr: numeroCimr,
      })
      toast.success(isEdit ? 'Profil de paie mis à jour.' : 'Profil de paie créé.')
      onSaved()
      onClose()
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Enregistrement impossible.')
    } finally { setBusy(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {isEdit
              ? `Profil de paie — ${profil.employe_nom || `Profil #${profil.id}`}`
              : 'Nouveau profil de paie'}
          </DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          {!isEdit && (
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-muted-foreground">Employé</span>
              <Select value={employeId} onValueChange={setEmployeId}>
                <SelectTrigger><SelectValue placeholder="Employé…" /></SelectTrigger>
                <SelectContent>
                  {employes.map((e) => (
                    <SelectItem key={e.id} value={String(e.id)}>
                      {`${e.nom || ''} ${e.prenom || ''}`.trim() || `Employé #${e.id}`}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </label>
          )}
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted-foreground">Type de rémunération</span>
            <Select value={typeRemuneration} onValueChange={setTypeRemuneration}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="mensuel">Mensuel</SelectItem>
                <SelectItem value="journalier">Journalier</SelectItem>
                <SelectItem value="forfait">Forfait</SelectItem>
                <SelectItem value="horaire">Horaire</SelectItem>
              </SelectContent>
            </Select>
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted-foreground">Salaire de base</span>
            <Input type="number" step="any" value={salaireBase}
              onChange={(e) => setSalaireBase(e.target.value)} />
          </label>
          <div className="flex gap-3">
            <label className="flex flex-1 flex-col gap-1 text-sm">
              <span className="text-muted-foreground">RIB</span>
              <Input value={rib} onChange={(e) => setRib(e.target.value)} />
            </label>
            <label className="flex flex-1 flex-col gap-1 text-sm">
              <span className="text-muted-foreground">Banque</span>
              <Input value={banque} onChange={(e) => setBanque(e.target.value)} />
            </label>
          </div>
          <div className="flex flex-col gap-2 rounded-lg border border-border p-3">
            <span className="text-sm font-medium">Affiliations sociales</span>
            <div className="flex items-center gap-2">
              <label className="flex w-24 items-center gap-1.5 text-sm">
                <input type="checkbox" checked={affilieCnss}
                  onChange={(e) => setAffilieCnss(e.target.checked)} /> CNSS
              </label>
              <Input value={numeroCnss} placeholder="N° CNSS" className="flex-1"
                onChange={(e) => setNumeroCnss(e.target.value)} />
            </div>
            <div className="flex items-center gap-2">
              <label className="flex w-24 items-center gap-1.5 text-sm">
                <input type="checkbox" checked={affilieAmo}
                  onChange={(e) => setAffilieAmo(e.target.checked)} /> AMO
              </label>
              <Input value={numeroAmo} placeholder="N° AMO" className="flex-1"
                onChange={(e) => setNumeroAmo(e.target.value)} />
            </div>
            <div className="flex items-center gap-2">
              <label className="flex w-24 items-center gap-1.5 text-sm">
                <input type="checkbox" checked={affilieCimr}
                  onChange={(e) => setAffilieCimr(e.target.checked)} /> CIMR
              </label>
              <Input value={numeroCimr} placeholder="N° CIMR" className="flex-1"
                onChange={(e) => setNumeroCimr(e.target.value)} />
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button onClick={enregistrer} loading={busy}>
            {isEdit ? 'Enregistrer' : 'Créer le profil'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/* ── XPAI18 — Régime d'exonération IR (stagiaire/ANAPEC/TAHFIZ) ── */
function RegimeExonerationDialog({ profil, onClose, onSaved }) {
  const [regime, setRegime] = useState(profil.regime_exoneration || 'aucun')
  const [dateDebut, setDateDebut] = useState(profil.regime_date_debut || '')
  const [dateFin, setDateFin] = useState(profil.regime_date_fin || '')
  const [plafond, setPlafond] = useState(
    String(profil.regime_plafond_mensuel ?? '6000'))
  const [busy, setBusy] = useState(false)

  const enregistrer = async () => {
    setBusy(true)
    try {
      await paieApi.saveProfil(profil.id, {
        regime_exoneration: regime,
        regime_date_debut: dateDebut || null,
        regime_date_fin: dateFin || null,
        regime_plafond_mensuel: Number(plafond) || 0,
      })
      toast.success('Régime d’exonération mis à jour.')
      onSaved()
      onClose()
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Enregistrement impossible.')
    } finally { setBusy(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            Régime d’exonération IR — {profil.employe_nom || `Profil #${profil.id}`}
          </DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted-foreground">Régime</span>
            <Select value={regime} onValueChange={setRegime}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="aucun">Aucun</SelectItem>
                <SelectItem value="stagiaire">Stagiaire</SelectItem>
                <SelectItem value="anapec">ANAPEC</SelectItem>
                <SelectItem value="tahfiz">TAHFIZ</SelectItem>
              </SelectContent>
            </Select>
          </label>
          <div className="flex gap-3">
            <label className="flex flex-1 flex-col gap-1 text-sm">
              <span className="text-muted-foreground">Date de début</span>
              <Input type="date" value={dateDebut || ''}
                onChange={(e) => setDateDebut(e.target.value)} />
            </label>
            <label className="flex flex-1 flex-col gap-1 text-sm">
              <span className="text-muted-foreground">Date de fin (fenêtre)</span>
              <Input type="date" value={dateFin || ''}
                onChange={(e) => setDateFin(e.target.value)} />
            </label>
          </div>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted-foreground">Plafond mensuel exonéré</span>
            <Input type="number" step="any" value={plafond}
              onChange={(e) => setPlafond(e.target.value)} />
          </label>
        </div>
        <DialogFooter>
          <Button onClick={enregistrer} loading={busy}>Enregistrer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/* ── XPAI1 — Solde de tout compte (STC) ──
   Génère (ou recalcule tant que non validé) le bulletin de sortie d'un
   profil sur une période cible, puis propose le reçu PDF. Ne touche à
   aucun statut RH (le motif de sortie reste piloté côté rh.DossierEmploye). */
function StcDialog({ profil, onClose }) {
  const [periodes, setPeriodes] = useState([])
  const [periodeId, setPeriodeId] = useState('')
  const [motif, setMotif] = useState('')
  const [moisPreavis, setMoisPreavis] = useState('1')
  const [pac, setPac] = useState('0')
  const [busy, setBusy] = useState(false)
  const [bulletin, setBulletin] = useState(null)

  useEffect(() => {
    paieApi.getPeriodes({ ordering: '-annee,-mois' })
      .then((r) => setPeriodes(listOf(r.data)))
      .catch(() => toast.error('Chargement des périodes impossible.'))
  }, [])

  const generer = async () => {
    if (!periodeId) { toast.error('Choisissez une période.'); return }
    setBusy(true)
    try {
      const { data } = await paieApi.stc(profil.id, {
        periode: Number(periodeId),
        motif,
        mois_preavis: Number(moisPreavis) || 1,
        personnes_a_charge: Number(pac) || 0,
      })
      setBulletin(data)
      toast.success('Bulletin de solde de tout compte généré.')
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'STC impossible.')
    } finally { setBusy(false) }
  }

  const telechargerRecu = async () => {
    setBusy(true)
    try {
      const { data } = await paieApi.stcPdf(profil.id)
      openPdfBlob(data, `stc_${profil.id}.pdf`)
    } catch {
      toast.error('Reçu STC indisponible (moteur de rendu).')
    } finally { setBusy(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            Solde de tout compte — {profil.employe_nom || `Profil #${profil.id}`}
          </DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted-foreground">Période de sortie</span>
            <Select value={periodeId} onValueChange={setPeriodeId}>
              <SelectTrigger><SelectValue placeholder="Période…" /></SelectTrigger>
              <SelectContent>
                {periodes.map((p) => (
                  <SelectItem key={p.id} value={String(p.id)}>
                    {p.libelle || `${p.mois}/${p.annee}`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted-foreground">Motif (facultatif)</span>
            <Input value={motif} onChange={(e) => setMotif(e.target.value)}
              placeholder="Démission, licenciement, fin de CDD…" />
          </label>
          <div className="flex gap-3">
            <label className="flex flex-1 flex-col gap-1 text-sm">
              <span className="text-muted-foreground">Mois de préavis</span>
              <Input type="number" step="any" value={moisPreavis}
                onChange={(e) => setMoisPreavis(e.target.value)} />
            </label>
            <label className="flex flex-1 flex-col gap-1 text-sm">
              <span className="text-muted-foreground">Personnes à charge</span>
              <Input type="number" step="any" value={pac}
                onChange={(e) => setPac(e.target.value)} />
            </label>
          </div>
          {bulletin && (
            <div className="rounded-lg bg-muted/50 p-3 text-sm">
              Net à payer : <strong>{formatMAD(bulletin.net_a_payer)}</strong>
            </div>
          )}
        </div>
        <DialogFooter>
          {bulletin && (
            <Button variant="outline" onClick={telechargerRecu} loading={busy}>
              <Download size={16} aria-hidden="true" /> Reçu PDF
            </Button>
          )}
          <Button onClick={generer} loading={busy}>
            <FileSignature size={16} aria-hidden="true" />
            {bulletin ? 'Recalculer' : 'Générer le STC'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/* ── XPAI3 — Mutuelle / prévoyance (régimes + adhésions) ── */
function MutuelleTab() {
  const [regimes, setRegimes] = useState([])
  const [adhesions, setAdhesions] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([paieApi.getRegimesMutuelle(), paieApi.getAdhesionsMutuelle()])
      .then(([r, a]) => {
        setRegimes(listOf(r.data))
        setAdhesions(listOf(a.data))
      })
      .catch(() => toast.error('Chargement de la mutuelle impossible.'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Card className="p-4"><Loading /></Card>

  const regimeCols = [
    { id: 'libelle', header: 'Régime', accessor: (r) => r.libelle },
    { id: 'mode', header: 'Mode', accessor: (r) => r.mode },
    { id: 'palier', header: 'Palier', accessor: (r) => r.palier || '' },
    { id: 'sal', header: 'Part salariale', align: 'right',
      accessor: (r) => Number(r.part_salariale) || 0,
      cell: (_v, r) => formatMAD(r.part_salariale) },
    { id: 'pat', header: 'Part patronale', align: 'right',
      accessor: (r) => Number(r.part_patronale) || 0,
      cell: (_v, r) => formatMAD(r.part_patronale) },
    { id: 'actif', header: 'État', accessor: (r) => r.actif,
      cell: (_v, r) => (r.actif
        ? <Badge tone="success">Actif</Badge>
        : <Badge tone="neutral">Inactif</Badge>) },
  ]
  const adhesionCols = [
    { id: 'profil', header: 'Profil', accessor: (r) => r.profil,
      cell: (_v, r) => `#${r.profil}` },
    { id: 'regime', header: 'Régime', accessor: (r) => r.regime,
      cell: (_v, r) => `#${r.regime}` },
    { id: 'debut', header: 'Depuis', accessor: (r) => r.date_debut || '' },
    { id: 'actif', header: 'État', accessor: (r) => r.actif,
      cell: (_v, r) => (r.actif
        ? <Badge tone="success">Actif</Badge>
        : <Badge tone="neutral">Inactif</Badge>) },
  ]

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-4 sm:p-5">
        <h3 className="mb-3 font-display font-semibold">Régimes de mutuelle</h3>
        {regimes.length === 0 ? (
          <EmptyState icon={Sprout} title="Aucun régime"
            description="Configurez les régimes de mutuelle/prévoyance/assurance groupe." />
        ) : (
          <DataTable data={regimes} columns={regimeCols}
            exportName="regimes-mutuelle" />
        )}
      </Card>
      <Card className="p-4 sm:p-5">
        <h3 className="mb-3 font-display font-semibold">Adhésions</h3>
        {adhesions.length === 0 ? (
          <EmptyState icon={Sprout} title="Aucune adhésion" />
        ) : (
          <DataTable data={adhesions} columns={adhesionCols}
            exportName="adhesions-mutuelle" />
        )}
      </Card>
    </div>
  )
}

/* ── XPAI16 — Simulateur brut pour net cible (lettres d'offre) ── */
function SimulateurTab() {
  const [periodes, setPeriodes] = useState([])
  const [periodeId, setPeriodeId] = useState('')
  const [netCible, setNetCible] = useState('')
  const [pac, setPac] = useState('0')
  const [affilieCnss, setAffilieCnss] = useState(true)
  const [affilieAmo, setAffilieAmo] = useState(true)
  const [affilieCimr, setAffilieCimr] = useState(false)
  const [tauxCimr, setTauxCimr] = useState('0')
  const [resultat, setResultat] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    paieApi.getPeriodes({ ordering: '-annee,-mois' })
      .then((r) => setPeriodes(listOf(r.data)))
      .catch(() => toast.error('Chargement des périodes impossible.'))
  }, [])

  const calculer = async () => {
    if (!periodeId || !netCible) {
      toast.error('Choisissez une période et un net cible.')
      return
    }
    setBusy(true)
    try {
      const { data } = await paieApi.brutPourNet(periodeId, {
        net_cible: netCible,
        personnes_a_charge: pac,
        affilie_cnss: affilieCnss,
        affilie_amo: affilieAmo,
        affilie_cimr: affilieCimr,
        taux_cimr: tauxCimr,
      })
      setResultat(data)
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Calcul impossible.')
    } finally { setBusy(false) }
  }

  return (
    <div className="flex flex-col gap-4">
      <Card className="flex flex-col gap-3 p-4 sm:p-5">
        <p className="text-sm text-muted-foreground">
          Calcul inverse « brut pour net cible » — utile pour préparer une
          lettre d’offre. Aucune persistance.
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted-foreground">Période (paramètres en vigueur)</span>
            <Select value={periodeId} onValueChange={setPeriodeId}>
              <SelectTrigger className="w-56"><SelectValue placeholder="Période…" /></SelectTrigger>
              <SelectContent>
                {periodes.map((p) => (
                  <SelectItem key={p.id} value={String(p.id)}>
                    {p.libelle || `${p.mois}/${p.annee}`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted-foreground">Net cible (MAD)</span>
            <Input type="number" step="any" value={netCible}
              onChange={(e) => setNetCible(e.target.value)} className="w-32" />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted-foreground">Personnes à charge</span>
            <Input type="number" step="any" value={pac}
              onChange={(e) => setPac(e.target.value)} className="w-28" />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted-foreground">Taux CIMR</span>
            <Input type="number" step="any" value={tauxCimr}
              onChange={(e) => setTauxCimr(e.target.value)} className="w-24" />
          </label>
        </div>
        <div className="flex flex-wrap gap-4 text-sm">
          <label className="flex items-center gap-1.5">
            <input type="checkbox" checked={affilieCnss}
              onChange={(e) => setAffilieCnss(e.target.checked)} /> CNSS
          </label>
          <label className="flex items-center gap-1.5">
            <input type="checkbox" checked={affilieAmo}
              onChange={(e) => setAffilieAmo(e.target.checked)} /> AMO
          </label>
          <label className="flex items-center gap-1.5">
            <input type="checkbox" checked={affilieCimr}
              onChange={(e) => setAffilieCimr(e.target.checked)} /> CIMR
          </label>
        </div>
        <div>
          <Button onClick={calculer} loading={busy}>Calculer</Button>
        </div>
      </Card>
      {resultat && (
        <Card className="p-4 sm:p-5">
          <dl className="flex flex-col divide-y divide-border">
            {Object.entries(resultat).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between py-2 text-sm">
                <dt className="text-muted-foreground">{k}</dt>
                <dd className="tabular-nums">
                  {typeof v === 'number' ? formatMAD(v) : String(v)}
                </dd>
              </div>
            ))}
          </dl>
        </Card>
      )}
    </div>
  )
}

function Loading() {
  return (
    <div className="flex items-center gap-2 py-6 text-muted-foreground">
      <Spinner className="size-4" /> Chargement…
    </div>
  )
}
function listOf(data) {
  return Array.isArray(data) ? data : (data?.results ?? [])
}
