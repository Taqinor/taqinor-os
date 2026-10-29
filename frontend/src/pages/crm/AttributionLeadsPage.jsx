import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import crmApi from '../../api/crmApi'
import { Card, CardContent, Badge, Button, Spinner } from '../../ui'
import ReglesAttributionEditor from '../parametres/ReglesAttributionEditor'
import { apiErrorMessage } from '../../lib/apiError'

/* ============================================================================
   Attribution des leads (fondateur, 27/10/2026) — `/crm/attribution`.
   Le responsable de l'équipe commerciale décide qui reçoit chaque nouveau lead.
   Haut : le lead courant en entier. Bas : les membres, le proposé présélectionné.
   Entrée = attribuer au membre sélectionné ; ←/→ = changer de membre ; clic sur
   une carte = attribuer à ce membre. Lit `GET /crm/dispatch/` (contrat
   `apps/crm/contract_samples/dispatch_leads.json`).
   ========================================================================== */

const RAFRAICHISSEMENT_MS = 30000

const heure = (iso) => {
  if (!iso) return null
  try {
    return new Intl.DateTimeFormat('fr-FR', {
      timeZone: 'Africa/Casablanca', hour: '2-digit', minute: '2-digit',
    }).format(new Date(iso))
  } catch { return null }
}

function Info({ label, children }) {
  if (children === null || children === undefined || children === '') return null
  return (
    <div className="min-w-0">
      <div className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="break-words text-sm text-foreground">{children}</div>
    </div>
  )
}

// Les raccourcis ne partent jamais d'un champ de saisie ni d'une fenêtre ouverte.
function toucheIgnoree(e) {
  const t = e.target
  if (t && t.closest && t.closest('input, textarea, select, [contenteditable="true"], [role="dialog"], [data-reglages-panel]')) return true
  return Boolean(document.querySelector('[role="dialog"]'))
}

// Réglages des équipes que l'appelant peut configurer (responsable, directeur
// commercial, Direction/Admin) : interrupteur, délai et règles de proposition.
function ReglagesAttribution({ equipes, onSaveReglages }) {
  const [ouvert, setOuvert] = useState(false)
  const [erreur, setErreur] = useState(null)

  const enregistrer = (equipe, patch) =>
    onSaveReglages(equipe, patch)
      .then(() => setErreur(null))
      .catch((e) => setErreur(apiErrorMessage(e, 'L’enregistrement des réglages a échoué.')))

  return (
    <div data-reglages-panel>
      <Button type="button" variant="outline" size="sm" aria-expanded={ouvert}
              onClick={() => setOuvert((o) => !o)}>
        Réglages de l’attribution
      </Button>
      {ouvert && (
        <Card className="mt-2"><CardContent className="space-y-4 pt-4">
          {erreur && <p role="alert" className="text-sm text-destructive">{erreur}</p>}
          {equipes.map((eq) => (
            <div key={eq.id}>
              <h3 className="text-sm font-semibold text-foreground">{eq.nom}</h3>
              {/* Membres fournis par /crm/dispatch/ (un responsable au rôle
                  Commercial n'a pas accès à la liste des comptes). */}
              <ReglesAttributionEditor equipe={eq} onSaveReglages={enregistrer}
                                       membres={(eq.membres ?? []).map((m) => ({ id: m.id, username: m.nom }))} />
            </div>
          ))}
        </CardContent></Card>
      )}
    </div>
  )
}

export default function AttributionLeadsPage() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [message, setMessage] = useState(null)
  const [choix, setChoix] = useState({ leadId: null, id: null })
  const occupe = useRef(false)

  const charger = useCallback(() =>
    crmApi.getDispatch()
      .then((r) => { setData(r.data); setError(null) })
      .catch((e) => setError(apiErrorMessage(e, 'Impossible de charger les leads à attribuer.'))),
  [])

  useEffect(() => {
    charger()
    const t = setInterval(charger, RAFRAICHISSEMENT_MS)
    return () => clearInterval(t)
  }, [charger])

  const lead = data?.leads?.[0] ?? null
  const membres = useMemo(() => data?.membres ?? [], [data])
  const leadId = lead?.id
  const proposeId = lead?.propose?.id ?? null

  // Nouveau lead à l'écran : la sélection repart du membre proposé.
  const selected = choix.leadId === leadId ? choix.id : (proposeId ?? membres[0]?.id ?? null)

  const attribuer = useCallback(async (membreId) => {
    if (!lead || membreId == null || occupe.current) return
    occupe.current = true
    try {
      await crmApi.attribuerLead(lead.id, membreId)
      setMessage(null)
    } catch (e) {
      setMessage(e?.response?.status === 409
        ? 'Ce lead vient déjà d’être attribué.'
        : apiErrorMessage(e, 'L’attribution a échoué.'))
    }
    // Verrou gardé jusqu'au rechargement : un 2e Entrée ne vise jamais le
    // lead suivant avant qu'il soit affiché (revue Fable 27/10).
    try { await charger() } finally { occupe.current = false }
  }, [lead, charger])

  useEffect(() => {
    const onKey = (e) => {
      if (!lead || membres.length === 0 || e.altKey || e.ctrlKey || e.metaKey) return
      if (toucheIgnoree(e)) return
      if (e.key === 'Enter') {
        // Touche maintenue : jamais plusieurs leads d'affilée ; bouton
        // focalisé : son propre clic attribue déjà.
        if (e.repeat || e.target?.tagName === 'BUTTON') return
        e.preventDefault()
        attribuer(selected)
      } else if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
        e.preventDefault()
        const i = membres.findIndex((m) => m.id === selected)
        const pas = e.key === 'ArrowRight' ? 1 : -1
        const next = membres[(Math.max(i, 0) + pas + membres.length) % membres.length]
        setChoix({ leadId, id: next.id })
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [lead, leadId, membres, selected, attribuer])

  const reglerEquipe = useCallback(async (equipe, patch) => {
    await crmApi.saveReglagesDispatch(equipe.id, patch)
    await charger()
  }, [charger])

  if (!data && !error) {
    return <div className="flex justify-center p-10"><Spinner /></div>
  }

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-3 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-foreground">
          Attribution des leads{data?.equipe ? ` — ${data.equipe.nom}` : ''}
        </h1>
        {data && <Badge tone="neutral">{data.en_attente} en attente</Badge>}
      </div>

      {data?.equipes_reglables?.length > 0 && (
        <ReglagesAttribution equipes={data.equipes_reglables} onSaveReglages={reglerEquipe} />
      )}

      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {message && <p role="alert" className="text-sm text-destructive">{message}</p>}

      {data && !lead && (
        <Card><CardContent className="py-10 text-center text-sm text-muted-foreground">
          {data.equipe ? 'Aucun lead en attente' : 'Vous ne dirigez aucune équipe commerciale qui confirme ses leads.'}
        </CardContent></Card>
      )}

      {lead && (
        <Card>
          <CardContent className="space-y-4 pt-4 sm:pt-5">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-xl font-semibold text-foreground">{lead.nom}</h2>
              <span className="text-xs text-muted-foreground">
                Reçu à {heure(lead.cree_le)} · en attente depuis {lead.attente_minutes} min
                {heure(lead.auto_le) && ` · attribution automatique à ${heure(lead.auto_le)}`}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <Info label="Téléphone">{lead.telephone}</Info>
              <Info label="WhatsApp">{lead.whatsapp}</Info>
              <Info label="E-mail">{lead.email}</Info>
              <Info label="Ville">{lead.ville}</Info>
              <Info label="Type de client">{lead.type_installation_label}</Info>
              <Info label="Source">{lead.source_label}</Info>
              <Info label="Facture mensuelle">
                {lead.facture_mensuelle_dh != null ? `${lead.facture_mensuelle_dh} DH` : null}
              </Info>
            </div>
            {lead.message && (
              <p className="rounded-md bg-muted/40 p-2.5 text-sm text-foreground">{lead.message}</p>
            )}
            {lead.propose && (
              <p className="text-sm text-muted-foreground">
                Proposition : <strong className="text-foreground">{lead.propose.nom}</strong>
                {lead.propose.raison ? ` — ${lead.propose.raison}` : ''}
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {lead && (
        <div>
          <div role="listbox" aria-label="Membres de l'équipe" className="flex flex-wrap gap-2">
            {membres.map((m) => {
              const actif = m.id === selected
              return (
                <button key={m.id} type="button" role="option" aria-selected={actif}
                        onClick={() => attribuer(m.id)}
                        className={[
                          'min-w-[9rem] flex-1 rounded-lg border p-3 text-left transition-colors sm:flex-none',
                          actif ? 'border-primary bg-primary/10 ring-2 ring-primary' : 'border-border hover:bg-muted/40',
                        ].join(' ')}>
                  <div className="font-medium text-foreground">{m.nom}</div>
                  <div className="text-xs text-muted-foreground">{m.fonction}</div>
                  <div className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
                    {m.leads_ouverts} lead(s) ouvert(s)
                    {m.au_plafond && <Badge tone="warning">au plafond</Badge>}
                    {m.est_responsable && <Badge tone="neutral">Responsable</Badge>}
                  </div>
                </button>
              )
            })}
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Entrée : attribuer au membre sélectionné · ← → : changer de membre · clic : attribuer à ce membre
          </p>
        </div>
      )}
    </div>
  )
}
