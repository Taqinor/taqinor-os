import { useEffect, useMemo, useState } from 'react'
import { Send } from 'lucide-react'
import einvoiceApi from '../../api/einvoiceApi'
import PageHeader from '../../components/layout/PageHeader'
import { Badge, Card, CardContent, EmptyState, Segmented, Skeleton } from '../../ui'
import { formatDateTime } from '../../lib/format'

/* ============================================================================
   PACT54 — Historique des transmissions DGI (NTMAR7).
   ----------------------------------------------------------------------------
   `einvoice.TransmissionDGI` est la file d'attente de transmission Simpl : une
   ligne par e-facture, avec son statut (en attente / envoyé / accepté /
   rejeté), le compteur de tentatives, la prochaine tentative planifiée et la
   RÉPONSE BRUTE de la DGI. Elle est INERTE tant qu'aucune credential DGI n'est
   configurée — le serveur enregistre l'intention sans aucun appel réseau — mais
   elle était jusqu'ici totalement invisible.

   Cet écran est la moitié « historique » ; la moitié « déclencher » vit dans
   `components/EinvoiceActions.jsx` (Contrôler + Transmettre), sur la fiche
   facture. Lecture SEULE ici : le viewset serveur n'accepte que GET.
   ========================================================================== */

const FILTRES = [
  { value: 'tous', label: 'Toutes' },
  { value: 'en_attente', label: 'En attente' },
  { value: 'envoye', label: 'Envoyées' },
  { value: 'accepte', label: 'Acceptées' },
  { value: 'rejete', label: 'Rejetées' },
]

const LIBELLE_STATUT = {
  en_attente: 'En attente', envoye: 'Envoyé',
  accepte: 'Accepté', rejete: 'Rejeté',
}
const TONE_STATUT = {
  en_attente: 'warning', envoye: 'info', accepte: 'success', rejete: 'danger',
}

// Réponse DGI : toujours du TEXTE lisible, jamais un objet brut jeté à l'écran.
function resumeReponse(reponse) {
  if (!reponse || typeof reponse !== 'object') return null
  const message = reponse.detail ?? reponse.message ?? reponse.erreur
  if (typeof message === 'string' && message.trim()) return message
  const cles = Object.keys(reponse)
  return cles.length > 0 ? `Réponse DGI reçue (${cles.length} champ(s)).` : null
}

export default function TransmissionsDGIPage() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)
  const [filtre, setFiltre] = useState('tous')

  useEffect(() => {
    let actif = true
    einvoiceApi.transmissions()
      .then((r) => {
        if (!actif) return
        const data = r.data
        setRows(Array.isArray(data) ? data : (data?.results || []))
        setErreur(false)
      })
      .catch(() => { if (actif) { setRows([]); setErreur(true) } })
      .finally(() => { if (actif) setLoading(false) })
    return () => { actif = false }
  }, [])

  const affiches = useMemo(
    () => (filtre === 'tous' ? rows : rows.filter((t) => t.statut === filtre)),
    [rows, filtre],
  )

  return (
    <div className="page">
      <PageHeader
        title="Transmissions DGI"
        subtitle="File d'attente des e-factures transmises à la DGI (Simpl). Inerte tant qu'aucune credential DGI n'est configurée : les intentions sont enregistrées, aucun appel réseau n'est émis."
      />

      <Segmented
        options={FILTRES}
        value={filtre}
        onChange={setFiltre}
        aria-label="Filtrer les transmissions par statut"
      />

      <Card className="mt-4">
        <CardContent className="p-0">
          {loading && <Skeleton className="m-4 h-24" />}
          {!loading && erreur && (
            <EmptyState
              title="Chargement impossible"
              description="L'historique des transmissions n'a pas pu être chargé."
            />
          )}
          {!loading && !erreur && affiches.length === 0 && (
            <EmptyState
              icon={Send}
              title="Aucune transmission"
              description="Aucune e-facture n'a encore été transmise à la DGI pour ce filtre."
            />
          )}
          {!loading && !erreur && affiches.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm"
                     aria-label="Historique des transmissions DGI">
                <thead>
                  <tr className="border-b border-border">
                    {['E-facture', 'Statut', 'Tentatives', 'Prochaine tentative',
                      'Créée le', 'Réponse DGI'].map((c) => (
                        <th key={c} scope="col"
                            className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          {c}
                        </th>
                      ))}
                  </tr>
                </thead>
                <tbody>
                  {affiches.map((t) => (
                    <tr key={t.id} className="border-b border-border/60 last:border-b-0">
                      <td className="px-3 py-2 text-foreground">#{t.einvoice}</td>
                      <td className="px-3 py-2">
                        <Badge tone={TONE_STATUT[t.statut] || 'neutral'}>
                          {LIBELLE_STATUT[t.statut] || t.statut}
                        </Badge>
                      </td>
                      <td className="px-3 py-2 text-foreground">{t.tentatives ?? 0}</td>
                      <td className="px-3 py-2 text-foreground">
                        {t.prochaine_tentative ? formatDateTime(t.prochaine_tentative) : '—'}
                      </td>
                      <td className="px-3 py-2 text-foreground">
                        {t.date_creation ? formatDateTime(t.date_creation) : '—'}
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {resumeReponse(t.reponse_json) || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
