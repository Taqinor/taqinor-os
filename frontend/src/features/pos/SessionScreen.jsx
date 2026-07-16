import { useEffect, useMemo, useState } from 'react'
import posApi from '../../api/posApi'
import api from '../../api/axios'
import {
  Button, Input, Label, Badge, EmptyState,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  toast,
} from '../../ui'
import { formatMAD } from '../../lib/format'

/* XPOS4 — Session de caisse comptoir (route /pos/session).
   Ouverture (fond de caisse) → clôture (comptage espèces/TPE) → rapport Z.
   S'adosse à la caisse comptable existante (compta.Caisse / FG124) : on liste
   les caisses via /compta/caisses/ et on rattache la session à l'une d'elles. */
export default function SessionScreen() {
  const [sessions, setSessions] = useState([])
  const [caisses, setCaisses] = useState([])
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)

  // Ouverture
  const [ouvertureOpen, setOuvertureOpen] = useState(false)
  const [caisseId, setCaisseId] = useState('')
  const [fond, setFond] = useState('0')

  // Clôture
  const [clotureOpen, setClotureOpen] = useState(false)
  const [sessionEnCours, setSessionEnCours] = useState(null)
  const [montantCompte, setMontantCompte] = useState('')
  const [montantTpe, setMontantTpe] = useState('')
  const [commentaire, setCommentaire] = useState('')

  // Rapport Z
  const [rapport, setRapport] = useState(null)

  const chargerSessions = () =>
    posApi.getSessions().then((r) => {
      const data = r?.data?.results ?? r?.data ?? []
      setSessions(Array.isArray(data) ? data : [])
    }).catch(() => setSessions([]))

  useEffect(() => {
    Promise.all([
      chargerSessions(),
      api.get('/compta/caisses/').then((r) => {
        const data = r?.data?.results ?? r?.data ?? []
        setCaisses(Array.isArray(data) ? data : [])
      }).catch(() => setCaisses([])),
    ]).finally(() => setLoading(false))
  }, [])

  const sessionOuverte = useMemo(
    () => sessions.find((s) => s.statut === 'ouverte') || null, [sessions])

  const handleOuvrir = async () => {
    if (!caisseId) { toast.error('Choisissez une caisse.'); return }
    setBusy(true)
    try {
      await posApi.ouvrirSession({
        caisse_comptable: Number(caisseId),
        fond_ouverture: Number(fond) || 0,
      })
      toast.success('Session ouverte.')
      setOuvertureOpen(false)
      setCaisseId(''); setFond('0')
      await chargerSessions()
    } catch {
      toast.error("L'ouverture a échoué (une session est peut-être déjà ouverte).")
    } finally {
      setBusy(false)
    }
  }

  const ouvrirCloture = (session) => {
    setSessionEnCours(session)
    setMontantCompte(''); setMontantTpe(''); setCommentaire('')
    setClotureOpen(true)
  }

  const handleCloturer = async () => {
    if (!sessionEnCours) return
    setBusy(true)
    try {
      const payload = { montant_compte: Number(montantCompte) || 0 }
      if (montantTpe !== '') payload.montant_tpe_compte = Number(montantTpe) || 0
      if (commentaire.trim()) payload.commentaire = commentaire.trim()
      await posApi.cloturerSession(sessionEnCours.id, payload)
      toast.success('Session clôturée.')
      setClotureOpen(false)
      setSessionEnCours(null)
      await chargerSessions()
    } catch {
      toast.error('La clôture a échoué.')
    } finally {
      setBusy(false)
    }
  }

  const handleRapportZ = async (session) => {
    setBusy(true)
    try {
      const res = await posApi.rapportZ(session.id)
      setRapport({ session, ...res.data })
    } catch {
      toast.error('Le rapport Z est indisponible.')
    } finally {
      setBusy(false)
    }
  }

  const libelleCaisse = (id) =>
    caisses.find((c) => c.id === id)?.libelle || `Caisse #${id}`

  return (
    <div className="flex flex-col gap-4 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="font-display text-xl font-semibold">Sessions de caisse</h1>
        <Button type="button" disabled={!!sessionOuverte} onClick={() => setOuvertureOpen(true)}>
          Ouvrir une caisse
        </Button>
      </div>

      {loading ? (
        <div className="py-8 text-center text-sm text-muted-foreground">Chargement…</div>
      ) : sessions.length === 0 ? (
        <EmptyState title="Aucune session" description="Ouvrez une caisse pour démarrer la journée." />
      ) : (
        <ul className="flex flex-col gap-2" data-testid="sessions-liste">
          {sessions.map((s) => (
            <li key={s.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-card p-3">
              <div className="flex flex-col gap-0.5">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{libelleCaisse(s.caisse_comptable)}</span>
                  <Badge tone={s.statut === 'ouverte' ? 'success' : 'neutral'}>
                    {s.statut === 'ouverte' ? 'Ouverte' : 'Clôturée'}
                  </Badge>
                </div>
                <span className="text-xs tabular-nums text-muted-foreground">
                  Fond : {formatMAD(s.fond_ouverture, { withSymbol: false })} DH
                  {s.montant_compte_cloture != null &&
                    ` · Compté : ${formatMAD(s.montant_compte_cloture, { withSymbol: false })} DH`}
                  {s.ecart_tpe != null &&
                    ` · Écart TPE : ${formatMAD(s.ecart_tpe, { withSymbol: false })} DH`}
                </span>
              </div>
              <div className="flex gap-2">
                <Button type="button" variant="outline" size="sm" onClick={() => handleRapportZ(s)} disabled={busy}>
                  Rapport Z
                </Button>
                {s.statut === 'ouverte' && (
                  <Button type="button" size="sm" onClick={() => ouvrirCloture(s)} disabled={busy}>
                    Clôturer
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {rapport && (
        <div className="rounded-lg border border-border bg-card p-3" data-testid="rapport-z">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="font-medium">Rapport Z — session #{rapport.session.id}</h2>
            <button type="button" className="text-sm text-muted-foreground" onClick={() => setRapport(null)}>Fermer</button>
          </div>
          <div className="text-sm tabular-nums">
            <div>{rapport.nb_ventes} vente(s) — total {formatMAD(rapport.total, { withSymbol: false })} DH</div>
            <ul className="mt-1 flex flex-col gap-0.5 text-muted-foreground">
              {Object.entries(rapport.par_mode || {}).map(([mode, v]) => (
                <li key={mode}>{mode} : {formatMAD(v.total, { withSymbol: false })} DH ({v.nb})</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Ouverture de caisse */}
      <Dialog open={ouvertureOpen} onOpenChange={(o) => { if (!o) setOuvertureOpen(false) }}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Ouvrir une caisse</DialogTitle>
            <DialogDescription>Fond de caisse initial (espèces en tiroir).</DialogDescription>
          </DialogHeader>
          <form noValidate onSubmit={(e) => { e.preventDefault(); handleOuvrir() }} className="grid gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="session-caisse" required>Caisse</Label>
              <select
                id="session-caisse"
                value={caisseId}
                onChange={(e) => setCaisseId(e.target.value)}
                className="h-9 rounded-md border border-input bg-card px-2 text-sm"
              >
                <option value="">Choisir une caisse…</option>
                {caisses.map((c) => (
                  <option key={c.id} value={c.id}>{c.libelle}</option>
                ))}
              </select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="session-fond">Fond de caisse</Label>
              <Input id="session-fond" type="number" step="any" value={fond}
                     onChange={(e) => setFond(e.target.value)} />
            </div>
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setOuvertureOpen(false)}>Annuler</Button>
              <Button type="submit" loading={busy}>Ouvrir</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Clôture de caisse */}
      <Dialog open={clotureOpen} onOpenChange={(o) => { if (!o) setClotureOpen(false) }}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Clôturer la caisse</DialogTitle>
            <DialogDescription>Comptez les espèces (et le TPE si applicable).</DialogDescription>
          </DialogHeader>
          <form noValidate onSubmit={(e) => { e.preventDefault(); handleCloturer() }} className="grid gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="cloture-especes" required>Espèces comptées</Label>
              <Input id="cloture-especes" type="number" step="any" value={montantCompte}
                     onChange={(e) => setMontantCompte(e.target.value)} placeholder="Montant en tiroir" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="cloture-tpe">TPE compté — optionnel</Label>
              <Input id="cloture-tpe" type="number" step="any" value={montantTpe}
                     onChange={(e) => setMontantTpe(e.target.value)} placeholder="Total carte du terminal" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="cloture-commentaire">Commentaire</Label>
              <Input id="cloture-commentaire" value={commentaire}
                     onChange={(e) => setCommentaire(e.target.value)} placeholder="Écart justifié…" />
            </div>
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setClotureOpen(false)}>Annuler</Button>
              <Button type="submit" loading={busy}>Clôturer</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
