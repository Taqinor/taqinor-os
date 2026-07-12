// F9–F19 + F23 — panneaux de capture/réconciliation terrain montés dans le
// volet détail d'une intervention (et dans « Ma journée », F22) :
//   * F9  — saisie de n° de série par composant (photo de plaque + OCR no-op) ;
//   * F11/F12 — réconciliation du matériel consommé (prévu vs utilisé) + revue
//     des dépassements ;
//   * F13/F14 — mémos vocaux (enregistrement navigateur) + transcription ;
//   * F16 — réserves (punch-list) ;
//   * F17 — retour d'outillage ;
//   * F18 — consignes de sécurité (sign-off) ;
//   * F19 — compte-rendu PDF (client-facing) ;
//   * F23 — code/QR de l'intervention.
// Tout le texte est en français ; thumb-reachable. Aucun service externe.
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Tag, Mic, Square, Trash2, ListChecks, ShieldCheck, FileText, QrCode,
  Wrench, AlertTriangle,
} from 'lucide-react'
import installationsApi from '../../api/installationsApi'
import {
  Button, Badge, Spinner, Checkbox, Input, Textarea, toast, ErrorBoundary,
} from '../../ui'
import { formatDateTime } from '../../lib/format'
import { withOfflineFallback, FIELD_OPS } from './offline/fieldOutbox'
import { compressImage } from '../../ui/file-utils'
import { renderTrustedSvg } from '../../lib/trustedSvg'

// N91/F21 — message commun quand une action a été MISE EN FILE (hors-ligne).
const QUEUED_MSG = 'Hors ligne — enregistré, synchro au retour du réseau.'

// VX205 — chaque panneau (monté comme un `TabsContent` indépendant du volet
// détail intervention) enveloppe SA PROPRE `ErrorBoundary` (déjà construite,
// `ui/ErrorBoundary.jsx`) : un throw dans UN panneau (ex. Mémos vocaux) ne
// fait plus disparaître tout le volet — les autres onglets (Réserves,
// Sécurité…) restent utilisables, quel que soit l'appelant.

// ── F9 — N° de série par composant ───────────────────────────────────────────
// VX227 — le garde-doublon des n° de série voit désormais l'UNION des deux
// sources du même chantier : les relevés déjà capturés côté intervention (F9)
// ET les séries connues du chantier (`knownSeries` — parc + saisies de la
// checklist N9). Une série saisie côté F9 est détectée en doublon côté N9 et
// réciproquement. Les deux magasins ne sont jamais fusionnés — seul le
// contrôle de doublon est unifié.
export function SerialsPanel({ intervention, onChanged, knownSeries = [] }) {
  const id = intervention.id
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [designation, setDesignation] = useState('')
  const [numero, setNumero] = useState('')
  const fileRef = useRef(null)
  // VX94 — refocus sur le premier champ après un ajout réussi (recette
  // `newCatRef` prouvée dans ProduitForm) : la saisie sérialisée au pouce
  // enchaîne sans viser « Ajouter » puis re-viser le champ.
  const firstFieldRef = useRef(null)

  const load = useCallback(() => installationsApi.getSerials(id)
    .then((r) => setRows(r.data || []))
    .catch(() => setRows([]))
    .finally(() => setLoading(false)), [id])
  useEffect(() => { load() }, [load])

  // Union des séries connues : relevés F9 déjà enregistrés + séries du chantier
  // (parc/checklist). La comparaison est insensible à la casse et aux espaces.
  const knownSerieSet = new Set([
    ...rows.map((s) => s.numero_serie),
    ...knownSeries,
  ].map((s) => String(s || '').trim().toLowerCase()).filter(Boolean))
  const isDoublon = (v) => {
    const t = (v || '').trim().toLowerCase()
    return !!t && knownSerieSet.has(t)
  }

  const add = async () => {
    setBusy(true)
    try {
      // VX77 — compresse la photo de plaque AVANT envoi (bord long ≤1600px,
      // JPEG q0.75) : évite les minutes/timeout sur la 3G rurale.
      const rawFile = fileRef.current?.files?.[0]
      const file = rawFile ? await compressImage(rawFile) : rawFile
      await installationsApi.ajouterSerial(id, {
        designation, numero_serie: numero, file })
      setDesignation(''); setNumero('')
      if (fileRef.current) fileRef.current.value = ''
      toast.success('N° de série enregistré.')
      firstFieldRef.current?.focus()
      await load(); onChanged?.()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Enregistrement impossible.')
    } finally { setBusy(false) }
  }
  const remove = async (sid) => {
    setBusy(true)
    try { await installationsApi.supprimerSerial(id, sid); await load() }
    catch { toast.error('Suppression impossible.') } finally { setBusy(false) }
  }

  if (loading) return <PanelLoading label="numéros de série" />
  return (
    <ErrorBoundary>
    <div className="flex flex-col gap-3 py-2 text-sm">
      <p className="text-[12px] text-muted-foreground">
        Photographiez la plaque signalétique et saisissez le numéro de série. Le
        numéro peut rester vide — il ne bloque jamais la suite.
      </p>
      <div className="flex flex-col gap-2 rounded border border-border p-2">
        <Input ref={firstFieldRef} placeholder="Composant (onduleur, panneau…)"
          value={designation} onChange={(e) => setDesignation(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); if (!busy) add() } }} />
        <Input placeholder="N° de série (optionnel)"
          value={numero} onChange={(e) => setNumero(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); if (!busy) add() } }} />
        {isDoublon(numero) && (
          <span className="text-[12px] text-destructive">
            Ce numéro de série existe déjà sur ce chantier (parc ou checklist).
          </span>
        )}
        <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp"
          className="text-[12px]" />
        <Button size="sm" disabled={busy} onClick={add}>
          <Tag className="size-4" aria-hidden="true" /> Ajouter le relevé
        </Button>
      </div>
      {rows.length === 0
        ? <span className="text-[12px] text-muted-foreground">Aucun relevé.</span>
        : rows.map((s) => (
          <div key={s.id} className="flex items-center justify-between gap-2 rounded border border-border p-2">
            <div className="min-w-0">
              <div className="truncate font-medium">{s.designation || s.produit_nom || '—'}</div>
              <div className="text-[12px] text-muted-foreground">
                {s.numero_serie || <em>Sans numéro</em>}
                {s.serie_ocr && <Badge tone="info" className="ml-1">OCR</Badge>}
              </div>
            </div>
            <div className="flex items-center gap-2">
              {s.plaque_url && (
                <a href={s.plaque_url} target="_blank" rel="noreferrer"
                   className="text-[11px] underline">plaque</a>)}
              <button type="button" disabled={busy} onClick={() => remove(s.id)}
                title="Supprimer" className="text-destructive disabled:opacity-50">
                <Trash2 className="size-4" aria-hidden="true" />
              </button>
            </div>
          </div>
        ))}
    </div>
    </ErrorBoundary>
  )
}

// ── F11/F12 — Réconciliation du matériel consommé ───────────────────────────
export function ConsommationPanel({ intervention, onChanged }) {
  const id = intervention.id
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [extra, setExtra] = useState({ designation: '', quantite_utilisee: '' })
  // VX94 — refocus sur le premier champ « hors devis » après un ajout réussi.
  const extraFirstRef = useRef(null)

  const load = useCallback(() => installationsApi.getConsommation(id)
    .then((r) => setData(r.data))
    .catch(() => setData(null))
    .finally(() => setLoading(false)), [id])
  useEffect(() => { load() }, [load])

  const patchLigne = async (payload) => {
    setBusy(true)
    try { await installationsApi.modifierLigneConsommation(id, payload); await load() }
    catch { toast.error('Mise à jour impossible.') } finally { setBusy(false) }
  }
  const addExtra = async () => {
    if (!extra.designation.trim()) return
    setBusy(true)
    try {
      await installationsApi.ajouterLigneConsommation(id, extra)
      setExtra({ designation: '', quantite_utilisee: '' })
      extraFirstRef.current?.focus()
      await load()
    } catch { toast.error('Ajout impossible.') } finally { setBusy(false) }
  }
  const valider = async () => {
    setBusy(true)
    try {
      await installationsApi.validerConsommation(id)
      toast.success('Consommation validée — stock mis à jour.')
      await load(); onChanged?.()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Validation impossible.')
    } finally { setBusy(false) }
  }

  if (loading) return <PanelLoading label="matériel consommé" />
  if (!data) return <PanelUnavailable label="Réconciliation indisponible." />

  return (
    <ErrorBoundary>
    <div className="flex flex-col gap-3 py-2 text-sm">
      {data.valide && <Badge tone="success">Validée — stock mis à jour</Badge>}
      {(data.lignes || []).map((li) => (
        <div key={li.id} className="rounded border border-border p-2">
          <div className="flex items-center justify-between gap-2">
            <span className="truncate font-medium">{li.designation}
              {li.hors_nomenclature && <Badge className="ml-1">hors devis</Badge>}</span>
            <span className="text-[12px] text-muted-foreground">Prévu : {li.quantite_prevue}</span>
          </div>
          <div className="mt-1 flex items-center gap-2">
            <label className="text-[12px] text-muted-foreground">Utilisé</label>
            <Input className="w-24" type="number" step="any" defaultValue={li.quantite_utilisee}
              disabled={data.valide || busy}
              onBlur={(e) => patchLigne({ ligne: li.id, quantite_utilisee: e.target.value })} />
            {li.justification_requise && (
              <Badge tone="danger" className="flex items-center gap-1">
                <AlertTriangle className="size-3" aria-hidden="true" /> Justifier l'écart
              </Badge>)}
          </div>
          {li.variance !== 0 && (
            <Textarea className="mt-1.5" rows={2} placeholder="Justification de l'écart"
              defaultValue={li.justification} disabled={data.valide || busy}
              onBlur={(e) => patchLigne({ ligne: li.id, justification: e.target.value })} />
          )}
        </div>
      ))}

      {!data.valide && (
        <div className="flex flex-col gap-2 rounded border border-dashed border-border p-2">
          <span className="text-[12px] font-medium text-muted-foreground">Ligne hors devis (câble, vis, MC4…)</span>
          <Input ref={extraFirstRef} placeholder="Désignation" value={extra.designation}
            onChange={(e) => setExtra({ ...extra, designation: e.target.value })}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); if (!busy) addExtra() } }} />
          <Input type="number" step="any" placeholder="Quantité utilisée"
            value={extra.quantite_utilisee}
            onChange={(e) => setExtra({ ...extra, quantite_utilisee: e.target.value })}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); if (!busy) addExtra() } }} />
          <Button size="sm" variant="outline" disabled={busy} onClick={addExtra}>Ajouter la ligne</Button>
        </div>
      )}

      {!data.valide && (
        <Button size="sm" disabled={busy} onClick={valider}>
          <ListChecks className="size-4" aria-hidden="true" /> Valider la consommation
        </Button>
      )}
    </div>
    </ErrorBoundary>
  )
}

// ── F13/F14 — Mémos vocaux ───────────────────────────────────────────────────
export function MemosPanel({ intervention, onChanged }) {
  const id = intervention.id
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [recording, setRecording] = useState(false)
  const recorder = useRef(null)
  const chunks = useRef([])

  const load = useCallback(() => installationsApi.getMemos(id)
    .then((r) => setRows(r.data || []))
    .catch(() => setRows([]))
    .finally(() => setLoading(false)), [id])
  useEffect(() => { load() }, [load])

  // F13 — libère le micro si le volet est fermé en cours d'enregistrement :
  // `onstop` ne se déclenche pas au démontage, donc on coupe ici toutes les
  // pistes du flux pour ne pas laisser le micro actif.
  useEffect(() => () => {
    const rec = recorder.current
    if (rec) {
      try { if (rec.state !== 'inactive') rec.stop() } catch { /* déjà arrêté */ }
      rec.stream?.getTracks().forEach((t) => t.stop())
    }
  }, [])

  const start = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const rec = new MediaRecorder(stream)
      chunks.current = []
      rec.ondataavailable = (e) => { if (e.data.size) chunks.current.push(e.data) }
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop())
        const blob = new Blob(chunks.current, { type: 'audio/webm' })
        const file = new File([blob], 'memo.webm', { type: 'audio/webm' })
        setBusy(true)
        try { await installationsApi.ajouterMemo(id, file); await load(); onChanged?.() }
        catch (err) {
          // VX105 — le mémo n'est PAS filé (pas d'outbox binaire — FG386) : un
          // échec réseau = mémo perdu. Message DISTINCT et persistant, jamais
          // l'illusion d'un envoi.
          const offline = navigator.onLine === false || !err?.response
          if (offline) {
            toast.error(
              'Mémo NON envoyé — réseau indisponible. Ré-enregistrez-le au retour du réseau.',
              { duration: Infinity })
          } else {
            toast.error(err?.response?.data?.detail ?? 'Mémo impossible.')
          }
        }
        finally { setBusy(false) }
      }
      recorder.current = rec
      rec.start(); setRecording(true)
    } catch { toast.error('Micro indisponible.') }
  }
  const stop = () => { recorder.current?.stop(); setRecording(false) }
  const remove = async (mid) => {
    setBusy(true)
    try { await installationsApi.supprimerMemo(id, mid); await load() }
    catch { toast.error('Suppression impossible.') } finally { setBusy(false) }
  }
  const saveTranscript = async (mid, transcript) => {
    try { await installationsApi.modifierMemo(id, mid, transcript); await load() }
    catch { toast.error('Édition impossible.') }
  }

  if (loading) return <PanelLoading label="mémos vocaux" />
  return (
    <ErrorBoundary>
    <div className="flex flex-col gap-3 py-2 text-sm">
      {recording
        ? <Button size="sm" variant="destructive" onClick={stop}>
            <Square className="size-4" aria-hidden="true" /> Arrêter l'enregistrement
          </Button>
        : <Button size="sm" disabled={busy} onClick={start}>
            <Mic className="size-4" aria-hidden="true" /> Enregistrer un mémo
          </Button>}
      {rows.length === 0
        ? <span className="text-[12px] text-muted-foreground">Aucun mémo.</span>
        : rows.map((m) => (
          <div key={m.id} className="rounded border border-border p-2">
            <div className="flex items-center justify-between gap-2">
              {m.audio_url && <audio src={m.audio_url} controls className="h-8 w-full max-w-[220px]" />}
              <button type="button" disabled={busy} onClick={() => remove(m.id)}
                title="Supprimer" className="text-destructive disabled:opacity-50">
                <Trash2 className="size-4" aria-hidden="true" />
              </button>
            </div>
            {!m.transcrit && <Badge className="mt-1">Non transcrit</Badge>}
            <Textarea className="mt-1.5" rows={2} defaultValue={m.transcript}
              placeholder="Transcription (éditable)"
              onBlur={(e) => saveTranscript(m.id, e.target.value)} />
          </div>
        ))}
    </div>
    </ErrorBoundary>
  )
}

// ── F16 — Réserves (punch-list) ──────────────────────────────────────────────
export function ReservesPanel({ intervention, onChanged }) {
  const id = intervention.id
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [desc, setDesc] = useState('')
  const [creerTicket, setCreerTicket] = useState(false)
  const [creerSuivi, setCreerSuivi] = useState(false)

  const load = useCallback(() => installationsApi.getReserves(id)
    .then((r) => setRows(r.data || []))
    .catch(() => setRows([]))
    .finally(() => setLoading(false)), [id])
  useEffect(() => { load() }, [load])

  const add = async () => {
    if (!desc.trim()) return
    setBusy(true)
    try {
      const r = await withOfflineFallback(
        () => installationsApi.ajouterReserve(id, {
          description: desc, creer_ticket: creerTicket, creer_suivi: creerSuivi }),
        FIELD_OPS.RESERVE, { intervention: id, description: desc })
      setDesc(''); setCreerTicket(false); setCreerSuivi(false)
      if (r.queued) toast.success(QUEUED_MSG)
      await load(); onChanged?.()
    } catch { toast.error('Ajout impossible.') } finally { setBusy(false) }
  }
  const resolve = async (rid) => {
    setBusy(true)
    try { await installationsApi.resoudreReserve(id, { reserve: rid, resolution: '' }); await load(); onChanged?.() }
    catch { toast.error('Résolution impossible.') } finally { setBusy(false) }
  }

  if (loading) return <PanelLoading label="réserves" />
  return (
    <ErrorBoundary>
    <div className="flex flex-col gap-3 py-2 text-sm">
      <div className="flex flex-col gap-2 rounded border border-border p-2">
        <Textarea rows={2} placeholder="Réserve à reprendre (câble manquant, réglage onduleur…)"
          value={desc} onChange={(e) => setDesc(e.target.value)} />
        <label className="flex items-center gap-2 text-[12px]">
          <Checkbox checked={creerSuivi} onCheckedChange={(v) => setCreerSuivi(!!v)} />
          Créer une intervention de suivi
        </label>
        <label className="flex items-center gap-2 text-[12px]">
          <Checkbox checked={creerTicket} onCheckedChange={(v) => setCreerTicket(!!v)} />
          Créer un ticket SAV
        </label>
        <Button size="sm" disabled={busy} onClick={add}>Ajouter la réserve</Button>
      </div>
      {rows.length === 0
        ? <span className="text-[12px] text-muted-foreground">Aucune réserve.</span>
        : rows.map((r) => (
          <div key={r.id} className="flex items-start justify-between gap-2 rounded border border-border p-2">
            <div className="min-w-0">
              <div className="truncate">{r.description}</div>
              <div className="text-[12px] text-muted-foreground">
                <Badge tone={r.statut === 'resolue' ? 'success' : 'warning'}>{r.statut_display}</Badge>
                {r.ticket && <span className="ml-1">· Ticket #{r.ticket}</span>}
              </div>
            </div>
            {r.statut !== 'resolue' && (
              <Button size="sm" variant="outline" disabled={busy} onClick={() => resolve(r.id)}>Résoudre</Button>)}
          </div>
        ))}
    </div>
    </ErrorBoundary>
  )
}

// ── F17 — Retour d'outillage ─────────────────────────────────────────────────
export function ToolReturnPanel({ intervention, onChanged }) {
  const id = intervention.id
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => installationsApi.getToolReturn(id)
    .then((r) => setRows(r.data || []))
    .catch(() => setRows([]))
    .finally(() => setLoading(false)), [id])
  useEffect(() => { load() }, [load])

  const toggle = async (line, rendu) => {
    setBusy(true)
    try { await installationsApi.cocherToolReturn(id, { ligne: line, rendu }); await load() }
    catch { toast.error('Mise à jour impossible.') } finally { setBusy(false) }
  }
  const confirm = async () => {
    setBusy(true)
    try {
      const r = await installationsApi.confirmerToolReturn(id)
      const nr = r.data?.non_rendus ?? []
      if (nr.length) toast.error(`Outils non rendus : ${nr.join(', ')}`)
      else toast.success("Retour d'outillage confirmé.")
      await load(); onChanged?.()
    } catch { toast.error('Confirmation impossible.') } finally { setBusy(false) }
  }

  if (loading) return <PanelLoading label="retour d'outillage" />
  if (rows.length === 0) return <PanelUnavailable label="Aucun outil dans le kit de préparation." />
  return (
    <ErrorBoundary>
    <div className="flex flex-col gap-2 py-2 text-sm">
      {rows.map((tr) => (
        <label key={tr.id} className="flex items-center gap-2 rounded border border-border p-2">
          <Checkbox checked={tr.rendu} disabled={busy}
            onCheckedChange={(v) => toggle(tr.id, !!v)} />
          <Wrench className="size-4 text-muted-foreground" aria-hidden="true" />
          <span className="flex-1">{tr.outil_nom}</span>
          {!tr.rendu && <Badge tone="warning">Non rendu</Badge>}
        </label>
      ))}
      <Button size="sm" disabled={busy} onClick={confirm}>Confirmer le retour</Button>
    </div>
    </ErrorBoundary>
  )
}

// ── F18 — Consignes de sécurité (sign-off) ───────────────────────────────────
export function SafetyPanel({ intervention, onChanged }) {
  const id = intervention.id
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => installationsApi.getSafety(id)
    .then((r) => setData(r.data))
    .catch(() => setData(null))
    .finally(() => setLoading(false)), [id])
  useEffect(() => { load() }, [load])

  const toggle = async (cle, coche) => {
    setBusy(true)
    try {
      const r = await withOfflineFallback(
        () => installationsApi.cocherSafety(id, cle, coche),
        FIELD_OPS.COCHER_SAFETY, { intervention: id, cle, coche })
      if (r.queued) toast.success(QUEUED_MSG)
      await load()
    } catch { toast.error('Mise à jour impossible.') } finally { setBusy(false) }
  }
  const sign = async () => {
    setBusy(true)
    try { await installationsApi.signerSafety(id); toast.success('Consignes signées.'); await load(); onChanged?.() }
    catch { toast.error('Signature impossible.') } finally { setBusy(false) }
  }

  if (loading) return <PanelLoading label="consignes de sécurité" />
  if (!data) return <PanelUnavailable label="Consignes indisponibles." />
  return (
    <ErrorBoundary>
    <div className="flex flex-col gap-2 py-2 text-sm">
      {(data.items || []).map((it) => (
        <label key={it.cle} className="flex items-center gap-2 rounded border border-border p-2">
          <Checkbox checked={it.coche} disabled={busy || data.signe}
            onCheckedChange={(v) => toggle(it.cle, !!v)} />
          <ShieldCheck className="size-4 text-muted-foreground" aria-hidden="true" />
          <span>{it.libelle}</span>
        </label>
      ))}
      {data.signe
        ? <Badge tone="success">Signé par {data.signe_par_nom} le {formatDateTime(data.signe_le)}</Badge>
        : <Button size="sm" disabled={busy} onClick={sign}>Signer les consignes</Button>}
    </div>
    </ErrorBoundary>
  )
}

// ── F19 — Compte-rendu PDF (client-facing) ───────────────────────────────────
export function CompteRenduButton({ intervention }) {
  const url = installationsApi.compteRenduUrl(intervention.id)
  return (
    <Button size="sm" variant="outline" asChild>
      <a href={url} target="_blank" rel="noreferrer">
        <FileText className="size-4" aria-hidden="true" /> Compte-rendu PDF
      </a>
    </Button>
  )
}

// ── F23 — Code/QR de l'intervention ──────────────────────────────────────────
export function CodePanel({ intervention }) {
  const id = intervention.id
  const [data, setData] = useState(null)
  useEffect(() => {
    installationsApi.getCode(id).then((r) => setData(r.data)).catch(() => setData(null))
  }, [id])
  if (!data) return null
  // VX201 — le SVG est sûr aujourd'hui (généré côté serveur), mais sans garde
  // contre une régression future de la source : renderTrustedSvg refuse tout
  // balisage suspect (<script>, on*=, javascript:) et rend `null` (aucun HTML
  // injecté) plutôt que d'afficher un SVG non fiable.
  const svgProps = renderTrustedSvg(data.qr_svg)
  return (
    <div className="flex flex-col items-center gap-1 py-2 text-sm">
      <span className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
        <QrCode className="size-4" aria-hidden="true" /> Code de l'intervention
      </span>
      {svgProps && <div className="w-32" dangerouslySetInnerHTML={svgProps} />}
      <code className="text-[11px] text-muted-foreground">{data.token}</code>
    </div>
  )
}

function PanelLoading({ label }) {
  return (
    <p className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
      <Spinner className="size-4" /> Chargement {label}…
    </p>
  )
}

function PanelUnavailable({ label }) {
  return <p className="py-4 text-sm text-muted-foreground">{label}</p>
}
