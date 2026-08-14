import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import crmApi from '../../../api/crmApi'
import aiGovernanceApi from '../../../api/aiGovernanceApi'
import LeadWorkspace from '../../../features/crm/workspace/LeadWorkspace'
import LeadMaturiteBadge from './LeadMaturiteBadge'
import { Spinner, EmptyState, Button, toast } from '../../../ui'
import { frenchError } from '../../../lib/frenchError'

const CANAL_OPTIONS = [
  ['email', 'E-mail'],
  ['whatsapp', 'WhatsApp'],
  ['sms', 'SMS'],
]

/* VX22 — Une vraie page lead : route `/crm/leads/:id`.
   ----------------------------------------------------------------------------
   Jusqu'ici la fiche lead ne vivait QUE comme overlay de `LeadsPage`
   (`?lead=<id>` dépendant du cache de la liste déjà chargée) : pas de
   deep-link fiable, F5 pouvait retomber sur une liste vide selon le filtre,
   et un ctrl-clic depuis Kanban/Liste ouvrait un nouvel onglet... sur la
   liste, pas la fiche.

   Cette page est ADRESSABLE : elle charge le lead via `crmApi.getLead(id)`
   (jamais depuis le cache Redux de la liste, qui peut être vide/filtré/absent
   au premier chargement), rend le même `LeadForm` qu'ailleurs, et `onClose`
   ramène vers `/crm/leads` (la liste). Le flux overlay rapide du Kanban reste
   inchangé (LeadsPage garde `?lead=`) — cette page est l'ADRESSE canonique,
   pas un remplacement du panneau rapide. */
export default function LeadDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [lead, setLead] = useState(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    let cancelled = false
    // eslint-disable-next-line react-hooks/set-state-in-effect -- init loading au changement d'id
    setLoading(true)
    setNotFound(false)
    setLead(null)
    crmApi.getLead(id)
      .then((r) => { if (!cancelled) setLead(r.data) })
      .catch(() => { if (!cancelled) setNotFound(true) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [id])

  const backToList = () => navigate('/crm/leads')

  // PACT141 — brouillon de relance/réponse ASSISTÉ (NTAI11) : l'endpoint
  // aplatit le fil + les activités du lead et renvoie un brouillon FR
  // éditable, JAMAIS envoyé automatiquement. Sans clé LLM configurée, le
  // serveur répond 503 « rédaction manuelle requise » sans appel réseau
  // supplémentaire — ce message REMPLACE le bouton, jamais un bouton mort
  // ni une erreur brute.
  const [canal, setCanal] = useState('email')
  const [intention, setIntention] = useState('')
  const [brouillon, setBrouillon] = useState('')
  const [generating, setGenerating] = useState(false)
  const [indisponible, setIndisponible] = useState('')

  const genererBrouillon = async () => {
    setGenerating(true)
    try {
      const res = await aiGovernanceApi.rediger({
        content_type: 'crm.lead', object_id: id, canal, intention,
      })
      setBrouillon(res.data?.brouillon || '')
    } catch (err) {
      if (err?.response?.status === 503) {
        setIndisponible(err.response.data?.detail || 'Rédaction manuelle requise.')
      } else {
        toast.error(frenchError(err, 'Impossible de générer un brouillon.'))
      }
    } finally {
      setGenerating(false)
    }
  }

  if (loading) {
    return (
      <p className="page-loading"><Spinner /> Chargement du lead…</p>
    )
  }

  if (notFound || !lead) {
    return (
      <EmptyState
        title="Lead introuvable"
        description="Ce lead n'existe pas ou a été supprimé."
        action={<Button size="sm" onClick={backToList}>Retour à la liste</Button>}
      />
    )
  }

  return (
    // LW13 — la route détail rend le LeadWorkspace en PLEINE PAGE (parité de
    // fonctionnalités avec le flux liste : même cockpit, mêmes rails).
    <>
      <div
        style={{
          display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap',
          padding: '8px 16px', borderBottom: '1px solid #e2e8f0',
        }}
      >
        {/* NTMKT18/19 — score de maturité marketing (chaud/tiède/froid),
            invisible si le module est désactivé pour la société. */}
        <LeadMaturiteBadge leadId={id} />
        <select value={canal} onChange={(e) => setCanal(e.target.value)} aria-label="Canal du brouillon">
          {CANAL_OPTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <input
          placeholder="Intention (ex. relancer après devis envoyé)"
          value={intention}
          onChange={(e) => setIntention(e.target.value)}
          aria-label="Intention du brouillon"
          style={{ minWidth: 260 }}
        />
        {indisponible ? (
          <span style={{ color: '#64748b' }}>{indisponible}</span>
        ) : (
          <Button type="button" variant="outline" onClick={genererBrouillon} disabled={generating}>
            {generating ? 'Génération…' : 'Générer un brouillon de relance'}
          </Button>
        )}
        {brouillon && (
          <div style={{ width: '100%' }}>
            <textarea
              aria-label="Brouillon éditable"
              value={brouillon}
              onChange={(e) => setBrouillon(e.target.value)}
              rows={4}
              style={{ width: '100%' }}
            />
            <p style={{ fontSize: 12, color: '#64748b', margin: '4px 0 0' }}>
              Brouillon éditable — jamais envoyé automatiquement.
            </p>
          </div>
        )}
      </div>
      <LeadWorkspace
        variant="page"
        lead={lead}
        onClose={backToList}
        onSaved={() => {
          // Recharge la fiche depuis le serveur pour refléter la modification
          // (ex. devis créé inline) — même logique que LeadsPage.onSaved, mais
          // ciblée sur CE lead plutôt qu'un refetch de liste.
          crmApi.getLead(id).then((r) => setLead(r.data)).catch(() => {})
        }}
      />
    </>
  )
}
