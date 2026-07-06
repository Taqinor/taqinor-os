// Onglet « Email » de la page Paramètres (N87/N88) — compte d'envoi & capture.
// Section AUTONOME, informative : elle affiche l'état du compte d'envoi email
// (configuré ou non) et l'adresse expéditrice, sans rien modifier. La
// configuration réelle (clé Brevo, expéditeur, capture entrante) se fait par
// variables d'environnement côté serveur ; tant qu'aucune clé n'est posée,
// l'envoi reste un NO-OP qui préserve le comportement actuel (aucun email réel
// n'est envoyé). Aucun secret n'est affiché ici.
import { useEffect, useState } from 'react'
import { CheckCircle2, AlertCircle, Mail, Inbox, Check, RotateCcw } from 'lucide-react'
import ventesApi from '../../api/ventesApi'
import parametresApi from '../../api/parametresApi'
import { Card, CardContent, Spinner, Textarea, Input, Button } from '../../ui'
import { SectionTitle, Field } from './peComponents'

export default function EmailSection() {
  const [config, setConfig] = useState(null)
  const [loading, setLoading] = useState(true)

  // ZSAL5 — modèles d'e-mail éditables par clé (envoi_devis, etc.), parité
  // WhatsApp (MessagesSection). Couche de RENDU uniquement — aucun statut
  // n'est touché ici ; `apps.ventes.email_service` résout ce modèle au moment
  // de l'envoi réel (fallback sur le défaut usine si rien n'est personnalisé).
  const [templates, setTemplates] = useState([])
  const [templatesSavedCle, setTemplatesSavedCle] = useState(null)

  useEffect(() => {
    let alive = true
    ventesApi.getEmailConfig()
      .then(res => { if (alive) setConfig(res.data) })
      .catch(() => { if (alive) setConfig({ configured: false, from_email: '', inbound_configured: false }) })
      .finally(() => { if (alive) setLoading(false) })
    parametresApi.getEmailTemplates()
      .then(res => { if (alive) setTemplates(res.data.results ?? res.data) })
      .catch(() => {})
    return () => { alive = false }
  }, [])

  const setTemplateField = (cle, field, value) =>
    setTemplates(ts => ts.map(t => (t.cle === cle ? { ...t, [field]: value } : t)))

  const saveTemplate = async (t) => {
    setTemplatesSavedCle(null)
    try {
      const res = await parametresApi.saveEmailTemplates([
        { cle: t.cle, sujet: t.sujet, corps: t.corps },
      ])
      setTemplates(res.data.results ?? res.data)
      setTemplatesSavedCle(t.cle)
    } catch {
      // Erreur (ex. placeholder non autorisé) — laissée visible côté saisie,
      // pas de message générique qui masquerait le détail serveur.
    }
  }

  // Réinitialise ce modèle au texte par défaut usine (round-trip serveur pour
  // rester la source de vérité — jamais de valeur devinée côté client).
  const resetTemplate = async (t) => {
    setTemplatesSavedCle(null)
    try {
      const res = await parametresApi.saveEmailTemplates([
        { cle: t.cle, sujet: t.sujet_defaut, corps: t.corps_defaut },
      ])
      setTemplates(res.data.results ?? res.data)
    } catch {
      // idem — pas de message générique.
    }
  }

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

      {/* ZSAL5 — Modèles d'e-mail éditables (sujet + corps, par clé). */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Modèles d'e-mail" icon={<Mail className="size-4" />} />
          <p className="mb-3.5 text-[11.5px] text-muted-foreground">
            Sujet et corps des e-mails envoyés aux clients (devis, factures,
            relances). Un champ laissé vide retombe sur le modèle par défaut —
            le comportement d'envoi actuel reste inchangé tant que rien n'est
            personnalisé ici.
          </p>
          {templates.map(t => (
            <div key={t.cle} className="mt-2.5 border-t border-border pt-2.5">
              <div className="mb-1 text-xs font-semibold text-foreground">
                {t.label}
                {t.placeholders?.length > 0 && (
                  <span className="ml-1.5 font-normal text-muted-foreground">
                    ({t.placeholders.join(' ')})
                  </span>
                )}
                {t.personnalise && (
                  <span className="ml-1.5 rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                    Personnalisé
                  </span>
                )}
              </div>
              <Field label="Sujet" htmlFor={`pe-email-sujet-${t.cle}`}>
                <Input id={`pe-email-sujet-${t.cle}`} value={t.sujet}
                       onChange={e => setTemplateField(t.cle, 'sujet', e.target.value)} />
              </Field>
              <Field label="Corps" htmlFor={`pe-email-corps-${t.cle}`}>
                <Textarea id={`pe-email-corps-${t.cle}`} className="min-h-[80px] resize-y"
                          value={t.corps}
                          onChange={e => setTemplateField(t.cle, 'corps', e.target.value)} />
              </Field>
              <div className="mt-0.5 flex flex-wrap items-center gap-1.5">
                <Button type="button" size="sm"
                        variant={templatesSavedCle === t.cle ? 'success' : 'default'}
                        onClick={() => saveTemplate(t)}>
                  {templatesSavedCle === t.cle ? (
                    <><Check className="size-3.5" aria-hidden="true" /> Enregistré</>
                  ) : 'Enregistrer'}
                </Button>
                <Button type="button" size="sm" variant="outline"
                        onClick={() => resetTemplate(t)}>
                  <RotateCcw className="size-3.5" aria-hidden="true" /> Réinitialiser au modèle par défaut
                </Button>
              </div>
            </div>
          ))}
          {templates.length === 0 && (
            <p className="text-xs text-muted-foreground">Chargement…</p>
          )}
        </CardContent>
      </Card>
    </>
  )
}
