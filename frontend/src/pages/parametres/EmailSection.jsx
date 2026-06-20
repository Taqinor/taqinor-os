// Onglet « Email » de la page Paramètres (N87/N88) — compte d'envoi & capture.
// Section AUTONOME, informative : elle affiche l'état du compte d'envoi email
// (configuré ou non) et l'adresse expéditrice, sans rien modifier. La
// configuration réelle (clé Brevo, expéditeur, capture entrante) se fait par
// variables d'environnement côté serveur ; tant qu'aucune clé n'est posée,
// l'envoi reste un NO-OP qui préserve le comportement actuel (aucun email réel
// n'est envoyé). Aucun secret n'est affiché ici.
import { useEffect, useState } from 'react'
import { CheckCircle2, AlertCircle, Mail, Inbox } from 'lucide-react'
import ventesApi from '../../api/ventesApi'
import { Card, CardContent, Spinner } from '../../ui'
import { SectionTitle } from './peComponents'

export default function EmailSection() {
  const [config, setConfig] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    ventesApi.getEmailConfig()
      .then(res => { if (alive) setConfig(res.data) })
      .catch(() => { if (alive) setConfig({ configured: false, from_email: '', inbound_configured: false }) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [])

  if (loading) {
    return (
      <Card><CardContent className="pt-4 sm:pt-5">
        <Spinner /> <span className="text-xs text-muted-foreground">Chargement…</span>
      </CardContent></Card>
    )
  }

  const sortant = !!config?.configured
  const entrant = !!config?.inbound_configured

  return (
    <>
      {/* Compte d'envoi (sortant) */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Compte d'envoi email" icon={<Mail className="size-4" />} />
          <p className="mb-3 text-[11.5px] text-muted-foreground">
            Envoi des documents clients (devis, factures) et des relances par
            email. Tant qu'aucune clé n'est configurée, l'envoi reste inactif :
            aucun email réel n'est expédié (le comportement actuel est préservé).
          </p>
          <div className="flex items-center gap-2 text-sm">
            {sortant ? (
              <><CheckCircle2 className="size-4 text-emerald-600" />
                <span>Compte d'envoi configuré.</span></>
            ) : (
              <><AlertCircle className="size-4 text-amber-600" />
                <span>Aucun compte d'envoi configuré — envoi inactif (NO-OP).</span></>
            )}
          </div>
          <div className="mt-2 text-[11.5px] text-muted-foreground">
            Adresse expéditrice : <code>{config?.from_email || '—'}</code>
          </div>
          <p className="mt-3 text-[11px] text-muted-foreground">
            Activation (administrateur serveur) : définir
            {' '}<code>EMAIL_BACKEND</code>,{' '}<code>BREVO_API_KEY</code> et
            {' '}<code>DEFAULT_FROM_EMAIL</code> dans l'environnement.
          </p>
        </CardContent>
      </Card>

      {/* Capture entrante */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Capture des emails entrants" icon={<Inbox className="size-4" />} />
          <p className="mb-3 text-[11.5px] text-muted-foreground">
            Rattache automatiquement les réponses des clients au bon fil
            (devis/facture) lorsqu'une référence est reconnue. Inactive tant
            qu'aucune boîte de réception n'est configurée.
          </p>
          <div className="flex items-center gap-2 text-sm">
            {entrant ? (
              <><CheckCircle2 className="size-4 text-emerald-600" />
                <span>Capture entrante configurée.</span></>
            ) : (
              <><AlertCircle className="size-4 text-amber-600" />
                <span>Capture entrante inactive (NO-OP).</span></>
            )}
          </div>
        </CardContent>
      </Card>
    </>
  )
}
