import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  Download, FileBadge, RefreshCw, CheckCircle2, Wallet, FilePlus2, Calculator,
} from 'lucide-react'
import { DetailShell } from '../../ui/module'
import {
  Button, Card, Input, Spinner, EmptyState, Badge, toast,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../ui'
import { formatMAD } from '../../lib/format'
import { openPdfBlob } from '../../utils/pdfBlob'
import paieApi from '../../api/paieApi'
import { StatutBulletin } from './statuses.jsx'
import { BULLETIN_STATUTS } from './paieLogic.js'

/* ============================================================================
   UX11 — Bulletin (aperçu) : détail du calcul brut → cotisations → net.
   ----------------------------------------------------------------------------
   Décompose le snapshot immuable (CNSS/AMO/IR…) en lignes lisibles, permet
   d'importer les éléments variables RH de la période, de valider le bulletin,
   de télécharger le PDF, et l'attestation (salaire/travail/domiciliation) du
   profil. Aucun prix d'achat/marge. Montants via formatMAD.
   ========================================================================== */
export default function BulletinDetail() {
  const { id } = useParams()
  const [bulletin, setBulletin] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [attType, setAttType] = useState('travail')
  // WIR39 — cycle de vie du bulletin (rectification/marquer payé).
  const [rectifierOpen, setRectifierOpen] = useState(false)

  const load = () =>
    paieApi.getBulletin(id)
      .then((r) => setBulletin(r.data))
      .catch(() => toast.error('Bulletin introuvable.'))
      .finally(() => setLoading(false))

  useEffect(() => { load() }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  const telecharger = async () => {
    setBusy('pdf')
    try {
      const { data } = await paieApi.bulletinPdf(id)
      openPdfBlob(data, `bulletin_${id}.pdf`)
    } catch {
      toast.error('PDF indisponible (moteur de rendu).')
    } finally { setBusy('') }
  }

  const attestation = async () => {
    if (!bulletin?.profil) return
    setBusy('att')
    try {
      const { data } = await paieApi.attestationPdf(bulletin.profil, attType)
      openPdfBlob(data, `attestation_${attType}_${bulletin.profil}.pdf`)
    } catch (e) {
      toast.error(e?.response?.status === 400
        ? 'Attestation indisponible (données manquantes).'
        : 'Attestation indisponible.')
    } finally { setBusy('') }
  }

  const importerRh = async () => {
    if (!bulletin?.periode) return
    setBusy('rh')
    try {
      const { data } = await paieApi.importerElementsRh(bulletin.periode)
      toast.success(`${data?.importes ?? 0} élément(s) RH importé(s).`)
      // Recalcule le bulletin pour refléter les éléments importés.
      await paieApi.genererBulletin({
        periode: bulletin.periode, profil: bulletin.profil,
      }).catch(() => {})
      await load()
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Import RH impossible.')
    } finally { setBusy('') }
  }

  const valider = async () => {
    setBusy('valider')
    try {
      await paieApi.validerBulletin(id)
      await load()
      toast.success('Bulletin validé et figé.')
    } catch {
      toast.error('Validation impossible.')
    } finally { setBusy('') }
  }

  // WIR39 — marque le bulletin payé (décompte espèces/chèque, XPAI9).
  // Idempotent côté serveur (date d'origine conservée si déjà payé).
  const marquerPaye = async () => {
    setBusy('paye')
    try {
      await paieApi.marquerPayeBulletin(id)
      await load()
      toast.success('Bulletin marqué payé.')
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Marquage impossible.')
    } finally { setBusy('') }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-8 text-muted-foreground">
        <Spinner className="size-4" /> Chargement…
      </div>
    )
  }
  if (!bulletin) {
    return <EmptyState icon={FileBadge} title="Bulletin introuvable" />
  }

  const fige = bulletin.statut === BULLETIN_STATUTS.VALIDE

  return (
    <>
      <DetailShell
        title={`Bulletin #${bulletin.id}`}
        subtitle={`Période ${bulletin.periode} · Profil #${bulletin.profil}`}
        status={bulletin.statut}
        statusPill={StatutBulletin}
        backTo="/paie/bulletins"
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {!fige && (
              <Button variant="outline" onClick={importerRh} loading={busy === 'rh'}>
                <RefreshCw size={16} aria-hidden="true" /> Importer RH
              </Button>
            )}
            {!fige && (
              <Button variant="success" onClick={valider} loading={busy === 'valider'}>
                <CheckCircle2 size={16} aria-hidden="true" /> Valider
              </Button>
            )}
            {/* WIR39 — cycle de vie post-validation (rectification/paiement). */}
            {fige && bulletin.paye ? (
              <Badge tone="success">
                <Wallet size={14} aria-hidden="true" /> Payé
              </Badge>
            ) : fige && (
              <Button variant="outline" onClick={marquerPaye} loading={busy === 'paye'}>
                <Wallet size={16} aria-hidden="true" /> Marquer payé
              </Button>
            )}
            {fige && (
              <Button variant="outline" onClick={() => setRectifierOpen(true)}>
                <FilePlus2 size={16} aria-hidden="true" /> Rectifier
              </Button>
            )}
            <Button onClick={telecharger} loading={busy === 'pdf'}>
              <Download size={16} aria-hidden="true" /> PDF
            </Button>
          </div>
        }
        tabs={[
          {
            value: 'calcul',
            label: 'Calcul',
            content: <CalculCard b={bulletin} />,
          },
          {
            value: 'lignes',
            label: 'Lignes',
            content: <LignesCard lignes={bulletin.lignes || []} />,
          },
          {
            value: 'simulation',
            label: 'Simulation',
            content: <SimulationCard bulletin={bulletin} />,
          },
          {
            value: 'attestation',
            label: 'Attestation',
            content: (
              <Card className="flex flex-col gap-3 p-4 sm:p-5">
                <p className="text-sm text-muted-foreground">
                  Génère l’attestation PDF du profil (salaire = dernier bulletin
                  validé).
                </p>
                <div className="flex flex-wrap items-end gap-3">
                  <Select value={attType} onValueChange={setAttType}>
                    <SelectTrigger className="w-56"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="travail">Attestation de travail</SelectItem>
                      <SelectItem value="salaire">Attestation de salaire</SelectItem>
                      <SelectItem value="domiciliation">
                        Attestation de domiciliation
                      </SelectItem>
                    </SelectContent>
                  </Select>
                  <Button onClick={attestation} loading={busy === 'att'}>
                    <FileBadge size={16} aria-hidden="true" /> Générer
                  </Button>
                </div>
              </Card>
            ),
          },
        ]}
      />
      {rectifierOpen && (
        <RectifierDialog bulletin={bulletin} onClose={() => setRectifierOpen(false)} />
      )}
    </>
  )
}

/* Décomposition brut → cotisations → net (montants serveur, jamais recalculés). */
function CalculCard({ b }) {
  const rows = [
    ['Brut', b.brut, 'gain'],
    ['Brut imposable', b.brut_imposable, 'sub'],
    ['CNSS salariale', b.cnss_salariale, 'ret'],
    ['AMO salariale', b.amo_salariale, 'ret'],
    ['CIMR salariale', b.cimr_salariale, 'ret'],
    ['Frais professionnels', b.frais_professionnels, 'sub'],
    ['Net imposable', b.net_imposable, 'sub'],
    ['IR', b.ir, 'ret'],
    ['Autres retenues', b.retenues, 'ret'],
    ['Prime d’ancienneté', b.prime_anciennete, 'gain'],
    ['Net à payer', b.net_a_payer, 'total'],
  ]
  return (
    <Card className="p-4 sm:p-5">
      <dl className="flex flex-col divide-y divide-border">
        {rows.map(([label, val, kind]) => (
          <div
            key={label}
            className={cx(
              'flex items-center justify-between gap-4 py-2 text-sm',
              kind === 'total' && 'font-semibold text-base',
            )}
          >
            <dt className={cx(
              kind === 'ret' && 'text-destructive',
              kind === 'sub' && 'text-muted-foreground',
            )}>
              {kind === 'ret' ? '− ' : ''}{label}
            </dt>
            <dd className="tabular-nums">{formatMAD(val)}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-4 rounded-lg bg-muted/50 p-3 text-xs text-muted-foreground">
        Charges patronales : {formatMAD(b.charges_patronales)} · Allocations
        familiales : {formatMAD(b.allocations_familiales)} · Formation pro. :{' '}
        {formatMAD(b.formation_professionnelle)} · Provision congés :{' '}
        {formatMAD(b.provision_conges)}
      </div>
    </Card>
  )
}

function LignesCard({ lignes }) {
  if (!lignes.length) {
    return (
      <Card className="p-4 sm:p-5">
        <EmptyState icon={FileBadge} title="Aucune ligne"
          description="Le détail par rubrique apparaîtra après le calcul." />
      </Card>
    )
  }
  return (
    <Card className="p-4 sm:p-5">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-muted-foreground">
            <th className="py-2 font-medium">Code</th>
            <th className="py-2 font-medium">Libellé</th>
            <th className="py-2 font-medium">Type</th>
            <th className="py-2 text-right font-medium">Montant</th>
          </tr>
        </thead>
        <tbody>
          {lignes.map((l) => (
            <tr key={l.id} className="border-b border-border/60">
              <td className="py-2 tabular-nums">{l.code}</td>
              <td className="py-2">{l.libelle}</td>
              <td className="py-2 text-muted-foreground">{l.type}</td>
              <td className="py-2 text-right tabular-nums">
                {formatMAD(l.montant)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}

/* ── WIR39 — Simulation what-if (XPAI16) : rejoue le calcul en mémoire pour
   un salaire/prime/personnes à charge hypothétiques, SANS créer de bulletin
   ni toucher au bulletin réel. Période = celle du bulletin courant (fixe les
   paramètres légaux en vigueur). ── */
function SimulationCard({ bulletin }) {
  const [salaire, setSalaire] = useState('')
  const [prime, setPrime] = useState('0')
  const [pac, setPac] = useState(String(bulletin.personnes_a_charge ?? 0))
  const [resultat, setResultat] = useState(null)
  const [busy, setBusy] = useState(false)

  const simuler = async () => {
    setBusy(true)
    try {
      const { data } = await paieApi.simulationBulletin(bulletin.profil, {
        periode: bulletin.periode,
        ...(salaire !== '' ? { salaire } : {}),
        prime,
        personnes_a_charge: pac,
      })
      setResultat(data)
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Simulation impossible.')
    } finally { setBusy(false) }
  }

  return (
    <Card className="flex flex-col gap-4 p-4 sm:p-5">
      <p className="text-sm text-muted-foreground">
        Calcul what-if brut → net, sur les paramètres légaux de cette période —
        ne crée ni ne modifie aucun bulletin.
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted-foreground">Salaire (vide = réel du profil)</span>
          <Input type="number" step="any" value={salaire}
            onChange={(e) => setSalaire(e.target.value)} className="w-40" />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted-foreground">Prime</span>
          <Input type="number" step="any" value={prime}
            onChange={(e) => setPrime(e.target.value)} className="w-32" />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted-foreground">Personnes à charge</span>
          <Input type="number" step="any" value={pac}
            onChange={(e) => setPac(e.target.value)} className="w-28" />
        </label>
        <Button onClick={simuler} loading={busy}>
          <Calculator size={16} aria-hidden="true" /> Simuler
        </Button>
      </div>
      {resultat && (
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
      )}
    </Card>
  )
}

/* ── WIR39 — Rectification/rappel (PAIE36) : émet un NOUVEAU bulletin sur
   une période cible OUVERTE, lié à ce bulletin (figé, jamais modifié). ── */
function RectifierDialog({ bulletin, onClose }) {
  const [periodes, setPeriodes] = useState([])
  const [periodeCible, setPeriodeCible] = useState('')
  const [typeBulletin, setTypeBulletin] = useState('rectificatif')
  const [motif, setMotif] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    paieApi.getPeriodes({ ordering: '-annee,-mois' })
      .then((r) => setPeriodes(listOf(r.data).filter((p) => p.id !== bulletin.periode)))
      .catch(() => toast.error('Chargement des périodes impossible.'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const rectifier = async () => {
    if (!periodeCible) { toast.error('Choisissez la période cible.'); return }
    setBusy(true)
    try {
      const { data } = await paieApi.rectifierBulletin(bulletin.id, {
        periode_cible: Number(periodeCible),
        type_bulletin: typeBulletin,
        motif,
      })
      toast.success(
        `Bulletin ${typeBulletin} #${data.id} créé (net à payer : `
        + `${formatMAD(data.net_a_payer)}).`)
      onClose()
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Rectification impossible.')
    } finally { setBusy(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Rectifier le bulletin #{bulletin.id}</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted-foreground">
            Ce bulletin reste figé — un nouveau bulletin recalculé est émis sur
            la période cible.
          </p>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted-foreground">Nature</span>
            <Select value={typeBulletin} onValueChange={setTypeBulletin}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="rectificatif">Rectificatif</SelectItem>
                <SelectItem value="rappel">Rappel</SelectItem>
              </SelectContent>
            </Select>
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted-foreground">Période cible</span>
            <Select value={periodeCible} onValueChange={setPeriodeCible}>
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
              placeholder="Erreur de saisie, rappel de salaire…" />
          </label>
        </div>
        <DialogFooter>
          <Button onClick={rectifier} loading={busy}>Rectifier</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function cx(...cls) {
  return cls.filter(Boolean).join(' ')
}
function listOf(data) {
  return Array.isArray(data) ? data : (data?.results ?? [])
}
