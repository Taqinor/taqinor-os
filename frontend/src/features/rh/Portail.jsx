import { useEffect, useState } from 'react'
import {
  CalendarDays, Receipt, FileText, Plane, HardHat, ShieldCheck,
  GraduationCap, Smile,
} from 'lucide-react'
import {
  Card, Stat, Segmented, Badge, EmptyState, Skeleton, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Button, Label, Input, Textarea,
} from '../../ui'
import { formatMAD, formatNumber, formatDate } from '../../lib/format'
import rhApi from '../../api/rhApi'
import { StatutConge, StatutNoteFrais, StatutMission } from './constants.jsx'
import ExternalLink from '../../ui/ExternalLink'

/* ============================================================================
   UX28 — Portail self-service (tous rôles).
   ----------------------------------------------------------------------------
   Tableau de bord du collaborateur connecté : ses infos, ses soldes de congés,
   ses demandes de congé, ses notes de frais, ses ordres de mission, ses
   documents/bulletins. TOUT est résolu côté serveur à partir du dossier lié au
   compte appelant — un collaborateur ne voit JAMAIS les données d'un autre.
   Si aucun dossier n'est lié au compte, le portail l'indique clairement.
   ========================================================================== */

const VUES = [
  { value: 'conges', label: 'Mes congés' },
  { value: 'frais', label: 'Mes frais' },
  { value: 'missions', label: 'Mes missions' },
  { value: 'documents', label: 'Mes documents' },
  { value: 'demandes', label: 'Mes demandes' },
  { value: 'epi', label: 'Mes EPI' },
  { value: 'habilitations', label: 'Mes habilitations' },
  { value: 'quiz', label: 'Mes quiz' },
  { value: 'evaluations', label: 'Mes évaluations' },
]

export default function Portail() {
  const [vue, setVue] = useState('conges')
  const [infos, setInfos] = useState(null)
  const [soldes, setSoldes] = useState([])
  const [conges, setConges] = useState([])
  const [frais, setFrais] = useState([])
  const [missions, setMissions] = useState([])
  const [bulletins, setBulletins] = useState([])
  const [demandes, setDemandes] = useState([])
  const [epi, setEpi] = useState([])
  const [habilitations, setHabilitations] = useState([])
  const [quizDispo, setQuizDispo] = useState([])
  const [tentatives, setTentatives] = useState([])
  const [evaluations, setEvaluations] = useState([])
  const [pulse, setPulse] = useState([])
  const [loading, setLoading] = useState(true)
  const [sansDossier, setSansDossier] = useState(false)
  const [reloadTick, setReloadTick] = useState(0)

  // Dialogues self-service.
  const [attestationOpen, setAttestationOpen] = useState(false)
  const [quizFor, setQuizFor] = useState(null)
  const [autoEvalFor, setAutoEvalFor] = useState(null)

  const recharger = () => setReloadTick((t) => t + 1)

  useEffect(() => {
    let vivant = true
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    setLoading(true)
    setSansDossier(false)
    rhApi.getMesInfos()
      .then((res) => { if (vivant) setInfos(res.data) })
      .catch((err) => {
        if (!vivant) return
        // 404 = aucun dossier employé lié au compte.
        if (err?.response?.status === 404) setSansDossier(true)
        else toast.error('Impossible de charger votre portail.')
      })

    Promise.allSettled([
      rhApi.getMesSoldes(),
      rhApi.getMesConges(),
      rhApi.getMesFrais(),
      rhApi.getOrdresMission(),
      rhApi.getMesBulletins(),
      rhApi.getMesDemandes(),
      rhApi.getMesEpi(),
      rhApi.getMesHabilitations(),
      rhApi.getQuizDisponibles(),
      rhApi.getMesTentativesQuiz(),
      rhApi.getMesEvaluations(),
      rhApi.getCampagnesPulse(),
    ]).then((r) => {
      if (!vivant) return
      const [s, c, f, m, b, dm, ep, ha, qz, tt, ev, pl] = r
      if (s.status === 'fulfilled') setSoldes(unwrap(s.value.data))
      if (c.status === 'fulfilled') setConges(unwrap(c.value.data))
      if (f.status === 'fulfilled') setFrais(unwrap(f.value.data))
      if (m.status === 'fulfilled') setMissions(unwrap(m.value.data))
      if (b.status === 'fulfilled') setBulletins(unwrap(b.value.data))
      if (dm.status === 'fulfilled') setDemandes(unwrap(dm.value.data))
      if (ep.status === 'fulfilled') setEpi(unwrap(ep.value.data))
      if (ha.status === 'fulfilled') setHabilitations(unwrap(ha.value.data))
      if (qz.status === 'fulfilled') setQuizDispo(unwrap(qz.value.data))
      if (tt.status === 'fulfilled') setTentatives(unwrap(tt.value.data))
      if (ev.status === 'fulfilled') setEvaluations(unwrap(ev.value.data))
      if (pl.status === 'fulfilled') setPulse(unwrap(pl.value.data))
      setLoading(false)
    })
    return () => { vivant = false }
  }, [reloadTick])

  if (loading) {
    return (
      <div className="page flex flex-col gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-32 w-full" />
      </div>
    )
  }

  if (sansDossier) {
    return (
      <div className="page">
        <EmptyState
          title="Aucun dossier employé lié à votre compte"
          description="Contactez les ressources humaines pour associer votre dossier à ce compte."
        />
      </div>
    )
  }

  const soldeTotal = soldes.reduce((acc, s) => acc + Number(s.disponible ?? 0), 0)
  const fraisEnCours = frais.filter((f) => f.statut === 'soumise').length

  return (
    <div className="page flex flex-col gap-6">
      <div className="page-header">
        <h2>Mon portail RH</h2>
        {infos && (
          <span className="text-sm text-muted-foreground">
            {infos.nom} {infos.prenom} · {infos.poste || '—'}
          </span>
        )}
      </div>

      {/* Bandeau KPI personnel. */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="p-4"><Stat label="Solde congés" value={`${formatNumber(soldeTotal, { decimals: 1 })} j`} hint="Disponible" icon={CalendarDays} /></Card>
        <Card className="p-4"><Stat label="Demandes en cours" value={formatNumber(conges.filter((c) => c.statut === 'soumise').length)} hint="Congés soumis" icon={CalendarDays} /></Card>
        <Card className="p-4"><Stat label="Frais soumis" value={formatNumber(fraisEnCours)} hint="En attente de remboursement" icon={Receipt} /></Card>
        <Card className="p-4"><Stat label="Bulletins" value={formatNumber(bulletins.length)} hint="Disponibles" icon={FileText} /></Card>
      </div>

      {/* XRH32 — invitation au baromètre eNPS anonyme (première campagne active). */}
      {pulse.length > 0 && <PulsePrompt campagne={pulse[0]} onDone={recharger} />}

      <Segmented options={VUES} value={vue} onChange={setVue} aria-label="Vue portail" />

      {vue === 'conges' && (
        <PortailListe
          rows={conges}
          empty="Aucune demande de congé."
          renderRow={(c) => (
            <RowLine
              title={`${formatDate(c.date_debut)} → ${formatDate(c.date_fin)}`}
              meta={`${c.type_absence_code || ''} · ${formatNumber(c.jours ?? 0, { decimals: 1 })} j`}
              right={<StatutConge status={c.statut} label={c.statut_display} />}
            />
          )}
        />
      )}
      {vue === 'frais' && (
        <PortailListe
          rows={frais}
          empty="Aucune note de frais."
          renderRow={(f) => (
            <RowLine
              title={f.libelle || f.categorie_display || 'Note de frais'}
              meta={`${formatMAD(f.montant)}${f.date_frais ? ` · ${formatDate(f.date_frais)}` : ''}`}
              right={<StatutNoteFrais status={f.statut} label={f.statut_display} />}
            />
          )}
        />
      )}
      {vue === 'missions' && (
        <PortailListe
          rows={missions}
          empty="Aucun ordre de mission."
          renderRow={(m) => (
            <RowLine
              title={m.destination || m.reference || 'Mission'}
              meta={`${m.motif || ''}${m.date_depart ? ` · ${formatDate(m.date_depart)}` : ''}`}
              right={<StatutMission status={m.statut} label={m.statut_display} />}
              icon={Plane}
            />
          )}
        />
      )}
      {vue === 'documents' && (
        <PortailListe
          rows={bulletins}
          empty="Aucun bulletin de paie."
          renderRow={(b) => (
            <RowLine
              title={`Bulletin ${String(b.mois).padStart(2, '0')}/${b.annee}`}
              meta={b.filename || '—'}
              right={b.url
                ? <ExternalLink className="link-blue text-xs" href={b.url}>Ouvrir</ExternalLink>
                : <Badge tone="neutral">Indisponible</Badge>}
            />
          )}
        />
      )}

      {/* XRH9 — mes demandes RH (attestations) + bouton de demande. */}
      {vue === 'demandes' && (
        <div className="flex flex-col gap-3">
          <div className="flex justify-end">
            <Button size="sm" onClick={() => setAttestationOpen(true)}>Demander une attestation</Button>
          </div>
          <PortailListe
            rows={demandes}
            empty="Aucune demande RH."
            renderRow={(d) => (
              <RowLine
                title={d.type_demande_display || d.type_demande || 'Demande'}
                meta={d.date_creation ? formatDate(d.date_creation) : ''}
                icon={FileText}
                right={d.attachment
                  ? <ExternalLink className="link-blue text-xs" href={`/api/django${rhApi.telechargerDemandeUrl(d.id)}`}>Télécharger</ExternalLink>
                  : <Badge tone={d.statut === 'traitee' ? 'success' : 'info'}>{d.statut_display || d.statut || 'En cours'}</Badge>}
              />
            )}
          />
        </div>
      )}

      {/* ZRH13 — mes EPI attribués. */}
      {vue === 'epi' && (
        <PortailListe
          rows={epi}
          empty="Aucun EPI attribué."
          renderRow={(e) => (
            <RowLine
              title={e.epi_designation || `EPI ${e.epi}`}
              meta={`${e.taille ? `Taille ${e.taille} · ` : ''}${e.date_dotation ? `remis le ${formatDate(e.date_dotation)}` : ''}`}
              icon={HardHat}
              right={e.perime ? <Badge tone="danger">Périmé</Badge> : <Badge tone="success">OK</Badge>}
            />
          )}
        />
      )}

      {/* Mes habilitations. */}
      {vue === 'habilitations' && (
        <PortailListe
          rows={habilitations}
          empty="Aucune habilitation."
          renderRow={(h) => (
            <RowLine
              title={h.type_habilitation_display || h.type_habilitation}
              meta={`${h.organisme || ''}${h.date_validite ? ` · valide jusqu’au ${formatDate(h.date_validite)}` : ''}`}
              icon={ShieldCheck}
              right={<Badge tone={h.valide ? 'success' : 'danger'}>{h.valide ? 'Valide' : 'Expirée'}</Badge>}
            />
          )}
        />
      )}

      {/* XRH34 — quiz disponibles (à passer) + mes tentatives. */}
      {vue === 'quiz' && (
        <div className="flex flex-col gap-4">
          <PortailListe
            rows={quizDispo}
            empty="Aucun quiz disponible."
            renderRow={(q) => (
              <RowLine
                title={q.intitule}
                meta={q.description || `${Array.isArray(q.questions) ? q.questions.length : (q.questions_count ?? '?')} question(s)`}
                icon={GraduationCap}
                right={<Button size="sm" variant="outline" onClick={() => setQuizFor(q)}>Passer</Button>}
              />
            )}
          />
          {tentatives.length > 0 && (
            <PortailListe
              rows={tentatives}
              empty="Aucune tentative."
              renderRow={(t) => (
                <RowLine
                  title={t.quiz_intitule || `Quiz ${t.quiz}`}
                  meta={`${t.score != null ? `Score ${t.score}` : ''}${t.date_creation ? ` · ${formatDate(t.date_creation)}` : ''}`}
                  right={t.reussi
                    ? <ExternalLink className="link-blue text-xs" href={`/api/django${rhApi.attestationQuizUrl(t.id)}`}>Attestation</ExternalLink>
                    : <Badge tone="danger">Échoué</Badge>}
                />
              )}
            />
          )}
        </div>
      )}

      {/* XRH26 — mes entretiens d'évaluation (auto-évaluation). */}
      {vue === 'evaluations' && (
        <PortailListe
          rows={evaluations}
          empty="Aucun entretien d’évaluation."
          renderRow={(e) => (
            <RowLine
              title={e.campagne_intitule || `Campagne ${e.campagne}`}
              meta={`${e.date_entretien ? formatDate(e.date_entretien) : ''}${e.statut_display ? ` · ${e.statut_display}` : ''}`}
              icon={Smile}
              right={<Button size="sm" variant="outline" onClick={() => setAutoEvalFor(e)}>Mon auto-évaluation</Button>}
            />
          )}
        />
      )}

      {attestationOpen && (
        <AttestationDialog
          onClose={() => setAttestationOpen(false)}
          onSaved={() => { setAttestationOpen(false); recharger() }}
        />
      )}
      {quizFor && (
        <QuizDialog
          quiz={quizFor}
          onClose={() => setQuizFor(null)}
          onDone={() => { setQuizFor(null); recharger() }}
        />
      )}
      {autoEvalFor && (
        <AutoEvalDialog
          evaluation={autoEvalFor}
          onClose={() => setAutoEvalFor(null)}
          onSaved={() => { setAutoEvalFor(null); recharger() }}
        />
      )}
    </div>
  )
}

/* ── XRH32 — Baromètre eNPS anonyme (vote 0-10). ── */
function PulsePrompt({ campagne, onDone }) {
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)
  const voter = async (score) => {
    setBusy(true)
    try {
      await rhApi.repondrePulse(campagne.id, { score })
      setDone(true)
      toast.success('Merci pour votre retour anonyme !')
      onDone?.()
    } catch (err) {
      if (err?.response?.status === 409) {
        setDone(true)
        toast.message('Vous avez déjà répondu à ce baromètre.')
      } else {
        toast.error('Vote impossible.')
      }
    } finally {
      setBusy(false)
    }
  }
  if (done) return null
  return (
    <Card className="p-4">
      <p className="text-sm font-medium">{campagne.intitule || 'Baromètre interne'}</p>
      <p className="mb-3 text-xs text-muted-foreground">
        Recommanderiez-vous l’entreprise comme employeur ? (0 = pas du tout, 10 = tout à fait) — anonyme
      </p>
      <div className="flex flex-wrap gap-1.5">
        {Array.from({ length: 11 }).map((_u, n) => (
          <Button key={n} size="sm" variant="outline" disabled={busy} onClick={() => voter(n)}>{n}</Button>
        ))}
      </div>
    </Card>
  )
}

/* ── XRH9 — Demander une attestation ── */
function AttestationDialog({ onClose, onSaved }) {
  const [type, setType] = useState('attestation_travail')
  const [motif, setMotif] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const TYPES = [
    { value: 'attestation_travail', label: 'Attestation de travail' },
    { value: 'attestation_salaire', label: 'Attestation de salaire' },
    { value: 'domiciliation', label: 'Attestation de domiciliation' },
    { value: 'autre', label: 'Autre' },
  ]

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.demanderAttestation({ type_demande: type, motif: motif || '' })
      toast.success('Demande envoyée.')
      onSaved?.()
    } catch (err) {
      setServerError(err?.response?.data?.detail || 'Envoi de la demande impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose?.() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Demander une attestation</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="at-type">Type de document</Label>
            <select id="at-type" value={type} onChange={(e) => setType(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm">
              {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="at-motif">Motif (optionnel)</Label>
            <Textarea id="at-motif" value={motif} onChange={(e) => setMotif(e.target.value)} rows={2} />
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Envoi…' : 'Envoyer la demande'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/* ── XRH34 — Passer un quiz (correction côté serveur) ── */
function QuizDialog({ quiz, onClose, onDone }) {
  const questions = Array.isArray(quiz.questions) ? quiz.questions : []
  const [reponses, setReponses] = useState(() => questions.map(() => ''))
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const setRep = (i, val) => setReponses((r) => r.map((v, j) => (j === i ? val : v)))

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setServerError(null)
    try {
      const res = await rhApi.passerQuiz(quiz.id, { reponses })
      const t = res?.data
      if (t?.reussi) toast.success(`Quiz réussi (score ${t.score ?? ''}).`)
      else toast.message(`Quiz non réussi (score ${t?.score ?? ''}). Vous pouvez réessayer.`)
      onDone?.()
    } catch (err) {
      setServerError(err?.response?.data?.detail || 'Envoi du quiz impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose?.() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>{quiz.intitule}</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          {questions.length === 0 && (
            <p className="text-sm text-muted-foreground">Ce quiz n’a pas de question consultable.</p>
          )}
          {questions.map((q, i) => (
            <div key={i} className="flex flex-col gap-1.5">
              <Label htmlFor={`q-${i}`}>{q.libelle || q.question || `Question ${i + 1}`}</Label>
              {Array.isArray(q.choix) && q.choix.length > 0 ? (
                <select id={`q-${i}`} value={reponses[i]} onChange={(e) => setRep(i, e.target.value)}
                  className="h-9 rounded-md border border-border bg-card px-3 text-sm">
                  <option value="">— Choisir —</option>
                  {q.choix.map((c, k) => <option key={k} value={c}>{c}</option>)}
                </select>
              ) : (
                <Input id={`q-${i}`} value={reponses[i]} onChange={(e) => setRep(i, e.target.value)} />
              )}
            </div>
          ))}
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Envoi…' : 'Valider mes réponses'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/* ── XRH26 — Saisir son auto-évaluation ── */
function AutoEvalDialog({ evaluation, onClose, onSaved }) {
  const [texte, setTexte] = useState(evaluation.auto_evaluation || '')
  const [note, setNote] = useState(evaluation.note_auto ?? '')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.saisirAutoEvaluation(evaluation.id, {
        auto_evaluation: texte,
        ...(note === '' ? {} : { note_auto: Number(note) }),
      })
      toast.success('Auto-évaluation enregistrée.')
      onSaved?.()
    } catch (err) {
      setServerError(err?.response?.data?.detail || 'Enregistrement impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose?.() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Mon auto-évaluation</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ae-texte">Bilan personnel</Label>
            <Textarea id="ae-texte" value={texte} onChange={(e) => setTexte(e.target.value)} rows={4} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ae-note">Note (auto, 1-5)</Label>
            <Input id="ae-note" type="number" step="any" min="1" max="5" value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function PortailListe({ rows, empty, renderRow }) {
  if (!rows.length) {
    return <EmptyState title="Rien à afficher" description={empty} />
  }
  return (
    <ul className="flex flex-col gap-2">
      {rows.map((r, i) => (
        <li key={r.id ?? i} className="rounded-lg border border-border bg-card px-4 py-3">
          {renderRow(r)}
        </li>
      ))}
    </ul>
  )
}

function RowLine({ title, meta, right, icon: Icon }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="flex min-w-0 items-center gap-2">
        {Icon && <Icon size={16} strokeWidth={1.75} aria-hidden="true" className="text-muted-foreground" />}
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{title}</p>
          {meta && <p className="truncate text-xs text-muted-foreground">{meta}</p>}
        </div>
      </div>
      <div className="shrink-0">{right}</div>
    </div>
  )
}

function unwrap(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.results)) return data.results
  return []
}
