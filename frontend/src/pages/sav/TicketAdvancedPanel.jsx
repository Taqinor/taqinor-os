import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bell, BellOff, Sparkles, Copy, GitMerge, PackagePlus, UserPlus2, Undo2,
} from 'lucide-react'
import savApi from '../../api/savApi'
import { Badge, Button, Input, Select, SelectTrigger, SelectValue, SelectContent, SelectItem, toast } from '../../ui'

/**
 * XSAV21 (résolutions similaires), XSAV28 (triage IA, propose→confirme,
 * jamais auto-appliqué), XSAV12 (fusion de doublon), XSAV27 (prêt
 * d'équipement / loaner), ZSAV8 (conversion en lead CRM), ZSAV9 (suivre/ne
 * plus suivre). Regroupés dans un seul panneau pour limiter la surface du
 * fichier TicketsPage.jsx (déjà volumineux).
 */
export default function TicketAdvancedPanel({ ticket, onNoteInsert }) {
  const ticketId = ticket.id

  // ── ZSAV9 — suivre/ne plus suivre ──
  // NOTE : TicketSerializer n'expose pas encore un drapeau « je suis abonné »
  // calculé côté serveur — l'état initial ne reflète donc que ce qui a été
  // basculé DANS CETTE SESSION (jamais un abonnement déjà posé avant
  // l'ouverture du ticket). Les appels POST/DELETE restent corrects et
  // idempotents côté serveur ; seul l'affichage initial peut être en retard.
  const [suivi, setSuivi] = useState(!!ticket.je_suis_abonne)
  const [suiviBusy, setSuiviBusy] = useState(false)
  const toggleSuivi = async () => {
    setSuiviBusy(true)
    try {
      if (suivi) { await savApi.neplusSuivreTicket(ticketId); setSuivi(false) }
      else { await savApi.suivreTicket(ticketId); setSuivi(true) }
    } catch {
      toast.error('Action impossible.')
    } finally { setSuiviBusy(false) }
  }

  // ── XSAV21 — tickets résolus similaires ──
  const [similaires, setSimilaires] = useState([])
  useEffect(() => {
    savApi.getTicketsSimilaires(ticketId).then((r) => setSimilaires(r.data?.results ?? []))
      .catch(() => {})
  }, [ticketId])

  // ── XSAV28 — triage IA (propose→confirme, GET pur, rien n'est écrit) ──
  const [triage, setTriage] = useState(null)
  const [triageLoading, setTriageLoading] = useState(false)
  const lancerTriage = async () => {
    setTriageLoading(true)
    try {
      const r = await savApi.getTriageIa(ticketId)
      setTriage(r.data)
    } catch {
      toast.error('Triage IA indisponible.')
    } finally { setTriageLoading(false) }
  }

  // ── XSAV12 — fusion de doublon ──
  const [doublonId, setDoublonId] = useState('')
  const [fusionBusy, setFusionBusy] = useState(false)
  const fusionner = async () => {
    if (!doublonId) return
    setFusionBusy(true)
    try {
      await savApi.fusionnerTicket(ticketId, doublonId)
      toast.success('Ticket fusionné')
      setDoublonId('')
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Fusion impossible.')
    } finally { setFusionBusy(false) }
  }

  // ── ZSAV8 — conversion en lead CRM ──
  const [leadBusy, setLeadBusy] = useState(false)
  const [leadId, setLeadId] = useState(ticket.lead_id_ext ?? null)
  const creerLead = async () => {
    setLeadBusy(true)
    try {
      const r = await savApi.creerLeadDepuisTicket(ticketId)
      setLeadId(r.data?.lead_id ?? null)
      toast.success(r.data?.created ? 'Lead CRM créé' : 'Lead CRM existant réutilisé')
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Conversion en lead impossible.')
    } finally { setLeadBusy(false) }
  }

  // ── XSAV27 — prêts d'équipement (loaner) ──
  const [prets, setPrets] = useState([])
  const loadPrets = () => {
    savApi.getPretsEquipement(ticketId).then((r) => setPrets(r.data ?? [])).catch(() => {})
  }
  useEffect(() => { loadPrets() }, [ticketId]) // eslint-disable-line react-hooks/exhaustive-deps
  const retournerPret = async (pretId) => {
    try {
      await savApi.retournerPretEquipement(ticketId, pretId)
      toast.success('Prêt retourné')
      loadPrets()
    } catch (err) { toast.error(err?.response?.data?.detail ?? 'Retour impossible.') }
  }

  // ── XSAV23 — macros (réponses types) ──
  const [macros, setMacros] = useState([])
  useEffect(() => {
    savApi.getReponsesType().then((r) => setMacros(r.data.results ?? r.data ?? [])).catch(() => {})
  }, [])

  return (
    <div className="flex flex-col gap-5" data-testid="ticket-advanced-panel">
      {/* ZSAV9 — suivre/ne plus suivre */}
      <div className="flex items-center gap-2">
        <Button type="button" size="sm" variant="outline" loading={suiviBusy} onClick={toggleSuivi}>
          {suivi ? <><BellOff /> Ne plus suivre</> : <><Bell /> Suivre ce ticket</>}
        </Button>
      </div>

      {/* XSAV23 — macro picker (insère dans la note du chatter) */}
      {macros.length > 0 && onNoteInsert && (
        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">Réponse type</span>
          <div className="flex flex-wrap gap-1.5">
            {macros.map((m) => (
              <Button key={m.id} type="button" size="sm" variant="outline"
                      onClick={() => onNoteInsert(m.id)}>
                <Copy /> {m.titre}
              </Button>
            ))}
          </div>
        </div>
      )}

      {/* XSAV28 — bannière triage IA */}
      <div className="flex flex-col gap-2 rounded-lg border border-border bg-card p-3">
        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-2 text-sm font-medium">
            <Sparkles className="size-4 text-muted-foreground" aria-hidden="true" />
            Triage IA
          </span>
          <Button type="button" size="sm" variant="outline" loading={triageLoading} onClick={lancerTriage}>
            Suggérer
          </Button>
        </div>
        {triage && !triage.disponible && (
          <p className="text-xs text-muted-foreground">Triage IA non configuré pour cette société.</p>
        )}
        {triage?.disponible && triage.suggestion && (
          <div className="flex flex-col gap-1 text-sm">
            <p><strong>Type de panne :</strong> {triage.suggestion.type_panne_suggere}</p>
            <p><strong>Priorité suggérée :</strong> {triage.suggestion.priorite_suggeree}</p>
            <p><strong>Résumé :</strong> {triage.suggestion.resume}</p>
            {triage.suggestion.brouillon_reponse && (
              <p className="text-muted-foreground">
                <strong>Brouillon de réponse :</strong> {triage.suggestion.brouillon_reponse}
              </p>
            )}
          </div>
        )}
        {triage?.disponible && !triage.suggestion && (
          <p className="text-xs text-muted-foreground">{triage.erreur ?? 'Aucune suggestion.'}</p>
        )}
      </div>

      {/* XSAV21 — résolutions similaires */}
      {similaires.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">Résolutions similaires</span>
          <ul className="flex flex-col gap-1">
            {similaires.map((s) => (
              <li key={s.id} className="text-sm">
                <Link to="/sav" className="text-primary hover:underline">{s.reference}</Link>
                {s.produit_nom ? ` — ${s.produit_nom}` : ''}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* XSAV12 — fusionner un doublon */}
      <div className="flex flex-col gap-1.5">
        <span className="flex items-center gap-2 text-sm font-medium">
          <GitMerge className="size-4 text-muted-foreground" aria-hidden="true" />
          Fusionner un ticket doublon
        </span>
        <div className="flex items-center gap-2">
          <Input type="number" placeholder="ID du ticket doublon" className="w-48"
                 value={doublonId} onChange={(e) => setDoublonId(e.target.value)} />
          <Button type="button" size="sm" variant="outline" loading={fusionBusy}
                  disabled={!doublonId} onClick={fusionner}>
            Fusionner
          </Button>
        </div>
      </div>

      {/* ZSAV8 — conversion en lead CRM */}
      <div className="flex items-center gap-2">
        {leadId ? (
          <Badge tone="success">Lead CRM #{leadId}</Badge>
        ) : (
          <Button type="button" size="sm" variant="outline" loading={leadBusy} onClick={creerLead}>
            <UserPlus2 /> Convertir en opportunité CRM
          </Button>
        )}
      </div>

      {/* XSAV27 — prêts d'équipement */}
      <div className="flex flex-col gap-1.5">
        <span className="flex items-center gap-2 text-sm font-medium">
          <PackagePlus className="size-4 text-muted-foreground" aria-hidden="true" />
          Prêts d'équipement
        </span>
        {prets.length === 0 ? (
          <p className="text-xs text-muted-foreground">Aucun prêt sur ce ticket.</p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {prets.map((p) => (
              <li key={p.id} className="flex items-center justify-between gap-2 text-sm">
                <span>
                  {p.produit_nom ?? 'Produit'} — sorti le {p.date_sortie}
                  {p.date_retour_reelle ? ` (retourné le ${p.date_retour_reelle})` : ''}
                </span>
                {!p.date_retour_reelle && (
                  <Button type="button" size="sm" variant="ghost" onClick={() => retournerPret(p.id)}>
                    <Undo2 /> Retourner
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
