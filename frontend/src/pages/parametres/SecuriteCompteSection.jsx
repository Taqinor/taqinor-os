// Onglet « Sécurité du compte » de la page Paramètres (N96) — double
// authentification (2FA TOTP), STRICTEMENT optionnelle. Section AUTONOME :
// elle charge et pilote son propre état via les endpoints /auth/2fa/*.
//
// Garantie : tant que l'utilisateur n'active pas le 2FA lui-même, sa connexion
// reste exactement comme avant. Activer = scanner le QR (ou saisir le secret)
// dans une application d'authentification, puis confirmer un code à 6 chiffres.
// Des codes de secours à usage unique sont alors affichés UNE seule fois.
import { useEffect, useState } from 'react'
import { ShieldCheck, ShieldAlert, KeyRound, Copy, CheckCircle2 } from 'lucide-react'
import api from '../../api/axios'
import { Card, CardContent, Button, Input, Spinner } from '../../ui'
import { SectionTitle } from './peComponents'

export default function SecuriteCompteSection() {
  const [loading, setLoading] = useState(true)
  const [enabled, setEnabled] = useState(false)
  const [remaining, setRemaining] = useState(0)
  // Phase de configuration (après « Activer ») : secret + URI otpauth.
  const [setup, setSetup] = useState(null)
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  // Codes de secours montrés une seule fois après activation.
  const [recovery, setRecovery] = useState(null)
  // Désactivation : code TOTP ou mot de passe.
  const [disableCode, setDisableCode] = useState('')
  const [disablePwd, setDisablePwd] = useState('')
  const [copied, setCopied] = useState(false)

  const loadStatus = () => {
    setLoading(true)
    api.get('/auth/2fa/status/')
      .then(r => { setEnabled(!!r.data.enabled); setRemaining(r.data.recovery_codes_remaining || 0) })
      .catch(() => { setEnabled(false); setRemaining(0) })
      .finally(() => setLoading(false))
  }

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { loadStatus() }, [])

  const errMsg = (e, fallback) =>
    e?.response?.data?.detail || fallback

  // Démarre la configuration : récupère un secret + l'URI otpauth (QR).
  const startSetup = async () => {
    setError(null); setBusy(true); setRecovery(null)
    try {
      const r = await api.post('/auth/2fa/setup/', {})
      setSetup(r.data)
      setCode('')
    } catch (e) {
      setError(errMsg(e, 'Impossible de démarrer la configuration.'))
    } finally { setBusy(false) }
  }

  // Vérifie le premier code et active le 2FA. Affiche les codes de secours.
  const enable = async () => {
    setError(null); setBusy(true)
    try {
      const r = await api.post('/auth/2fa/enable/', { code: code.trim() })
      setRecovery(r.data.recovery_codes || [])
      setSetup(null); setCode('')
      loadStatus()
    } catch (e) {
      setError(errMsg(e, 'Code invalide.'))
    } finally { setBusy(false) }
  }

  const cancelSetup = () => { setSetup(null); setCode(''); setError(null) }

  // Désactive le 2FA (code TOTP/secours OU mot de passe).
  const disable = async () => {
    setError(null); setBusy(true)
    try {
      await api.post('/auth/2fa/disable/', {
        code: disableCode.trim() || undefined,
        password: disablePwd || undefined,
      })
      setDisableCode(''); setDisablePwd('')
      loadStatus()
    } catch (e) {
      setError(errMsg(e, 'Vérification requise pour désactiver.'))
    } finally { setBusy(false) }
  }

  const copyRecovery = () => {
    if (!recovery) return
    try {
      navigator.clipboard?.writeText(recovery.join('\n'))
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch { /* clipboard indisponible : l'utilisateur recopie à la main */ }
  }

  if (loading) {
    return (
      <Card><CardContent className="pt-4 sm:pt-5">
        <Spinner /> <span className="text-xs text-muted-foreground">Chargement…</span>
      </CardContent></Card>
    )
  }

  return (
    <Card>
      <CardContent className="pt-4 sm:pt-5">
        <SectionTitle
          label="Double authentification (2FA)"
          icon={<><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></>}
        />
        <p className="mb-4 text-[11.5px] text-muted-foreground">
          Renforce la sécurité de votre compte en demandant, à chaque connexion,
          un code à 6 chiffres généré par une application d'authentification
          (Google Authenticator, Authy, etc.). Cette protection est
          <strong> optionnelle</strong> : tant que vous ne l'activez pas, votre
          connexion reste inchangée.
        </p>

        {error && (
          <div className="mb-3 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            <ShieldAlert className="size-4 shrink-0" /> <span>{error}</span>
          </div>
        )}

        {/* État courant */}
        <div className="mb-4 flex items-center gap-2 text-sm">
          {enabled ? (
            <><ShieldCheck className="size-4 text-emerald-600" />
              <span>Double authentification <strong>activée</strong>.</span></>
          ) : (
            <><ShieldAlert className="size-4 text-amber-600" />
              <span>Double authentification désactivée.</span></>
          )}
        </div>

        {/* Codes de secours fraîchement générés (montrés une seule fois) */}
        {recovery && (
          <div className="mb-4 rounded-lg border border-amber-300 bg-amber-50 p-3">
            <div className="mb-1 flex items-center gap-2 text-sm font-semibold text-amber-800">
              <KeyRound className="size-4" /> Codes de secours
            </div>
            <p className="mb-2 text-[11.5px] text-amber-800">
              Conservez ces codes dans un endroit sûr. Chacun ne fonctionne
              qu'une seule fois et permet de vous connecter si vous perdez votre
              téléphone. <strong>Ils ne seront plus jamais affichés.</strong>
            </p>
            <div className="grid grid-cols-2 gap-1.5 font-mono text-sm">
              {recovery.map(c => (
                <code key={c} className="rounded bg-white px-2 py-1 text-center">{c}</code>
              ))}
            </div>
            <Button type="button" variant="outline" size="sm" className="mt-2"
                    onClick={copyRecovery}>
              {copied
                ? <><CheckCircle2 className="size-4" /> Copié</>
                : <><Copy className="size-4" /> Copier</>}
            </Button>
          </div>
        )}

        {/* ── Cas 1 : 2FA désactivé, pas en configuration → bouton Activer ── */}
        {!enabled && !setup && (
          <Button type="button" onClick={startSetup} loading={busy} disabled={busy}>
            Activer la double authentification
          </Button>
        )}

        {/* ── Cas 2 : configuration en cours → QR/secret + confirmation ── */}
        {!enabled && setup && (
          <div className="rounded-lg border border-border p-3">
            <p className="mb-2 text-[11.5px] text-muted-foreground">
              1. Scannez ce QR code avec votre application d'authentification,
              ou saisissez la clé manuellement.
            </p>
            <div className="mb-3 flex flex-col items-start gap-3 sm:flex-row sm:items-center">
              <img
                alt="QR code de configuration 2FA"
                className="size-40 rounded border border-border bg-white p-1"
                src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(setup.otpauth_uri)}`}
              />
              <div className="text-[11.5px]">
                <div className="mb-1 text-muted-foreground">Clé manuelle :</div>
                <code className="break-all rounded bg-muted px-2 py-1 font-mono text-sm">{setup.secret}</code>
              </div>
            </div>
            <p className="mb-2 text-[11.5px] text-muted-foreground">
              2. Saisissez le code à 6 chiffres affiché par l'application pour
              confirmer.
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <Input
                value={code}
                onChange={e => setCode(e.target.value)}
                placeholder="123456"
                inputMode="numeric"
                autoComplete="one-time-code"
                aria-label="Code à 6 chiffres"
                className="w-32 font-mono"
              />
              <Button type="button" onClick={enable} loading={busy} disabled={busy || !code.trim()}>
                Confirmer et activer
              </Button>
              <Button type="button" variant="ghost" onClick={cancelSetup} disabled={busy}>
                Annuler
              </Button>
            </div>
          </div>
        )}

        {/* ── Cas 3 : 2FA activé → désactivation (code OU mot de passe) ── */}
        {enabled && (
          <div className="rounded-lg border border-border p-3">
            {remaining > 0 && (
              <p className="mb-2 text-[11.5px] text-muted-foreground">
                {remaining} code(s) de secours restant(s).
              </p>
            )}
            <p className="mb-2 text-[11.5px] text-muted-foreground">
              Pour désactiver la double authentification, fournissez un code de
              votre application (ou votre mot de passe).
            </p>
            <div className="flex flex-wrap items-end gap-2">
              <div>
                <div className="mb-1 text-[11px] text-muted-foreground">Code 2FA</div>
                <Input
                  value={disableCode}
                  onChange={e => setDisableCode(e.target.value)}
                  placeholder="123456"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  aria-label="Code 2FA"
                  className="w-32 font-mono"
                />
              </div>
              <span className="pb-2 text-[11px] text-muted-foreground">ou</span>
              <div>
                <div className="mb-1 text-[11px] text-muted-foreground">Mot de passe</div>
                <Input
                  type="password"
                  value={disablePwd}
                  onChange={e => setDisablePwd(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  aria-label="Mot de passe"
                  className="w-44"
                />
              </div>
              <Button type="button" variant="destructive" onClick={disable}
                      loading={busy} disabled={busy || (!disableCode.trim() && !disablePwd)}>
                Désactiver
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
