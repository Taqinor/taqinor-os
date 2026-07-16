// Onglet « Sécurité du compte » de la page Paramètres (N96) — double
// authentification (2FA TOTP), STRICTEMENT optionnelle. Section AUTONOME :
// elle charge et pilote son propre état via les endpoints /auth/2fa/*.
//
// Garantie : tant que l'utilisateur n'active pas le 2FA lui-même, sa connexion
// reste exactement comme avant. Activer = scanner le QR (ou saisir le secret)
// dans une application d'authentification, puis confirmer un code à 6 chiffres.
// Des codes de secours à usage unique sont alors affichés UNE seule fois.
import { useEffect, useState } from 'react'
import { ShieldCheck, ShieldAlert, KeyRound, Copy, CheckCircle2, Monitor, LogOut, Lock } from 'lucide-react'
import api from '../../api/axios'
import { formatDateTime } from '../../lib/format'
import { renderTrustedSvg } from '../../lib/trustedSvg'
import { Card, CardContent, Button, Input, Spinner } from '../../ui'
import { SectionTitle } from './peComponents'

// ── Sessions actives (N96) — liste des appareils connectés + révocation ──────
function SessionsActives() {
  const [loading, setLoading] = useState(true)
  const [sessions, setSessions] = useState([])
  const [error, setError] = useState(null)
  const [revoking, setRevoking] = useState(null)

  const load = () => {
    setLoading(true)
    api.get('/auth/sessions/')
      .then(r => { setSessions(Array.isArray(r.data) ? r.data : []); setError(null) })
      .catch(() => setError('Impossible de charger les sessions.'))
      .finally(() => setLoading(false))
  }

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load() }, [])

  const revoke = async (s) => {
    setError(null); setRevoking(s.id)
    try {
      await api.post(`/auth/sessions/${s.id}/revoke/`)
      // Révoquer l'appareil courant nous déconnecte : on recharge la page.
      if (s.is_current) { window.location.reload(); return }
      load()
    } catch {
      setError('Impossible de révoquer cette session.')
    } finally { setRevoking(null) }
  }

  const fmt = (iso) => formatDateTime(iso)

  return (
    <Card>
      <CardContent className="pt-4 sm:pt-5">
        <SectionTitle
          label="Sessions actives"
          icon={<><rect x="2" y="3" width="20" height="14" rx="2" /><path d="M8 21h8M12 17v4" /></>}
        />
        <p className="mb-4 text-[11.5px] text-muted-foreground">
          Les appareils actuellement connectés à votre compte. Révoquez une
          session si vous ne la reconnaissez pas : l'appareil concerné sera
          déconnecté.
        </p>

        {error && (
          <div className="mb-3 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            <ShieldAlert className="size-4 shrink-0" /> <span>{error}</span>
          </div>
        )}

        {loading ? (
          <div className="flex items-center gap-2">
            <Spinner /> <span className="text-xs text-muted-foreground">Chargement…</span>
          </div>
        ) : sessions.length === 0 ? (
          <p className="text-[12px] text-muted-foreground">Aucune session active.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {sessions.map(s => (
              <li key={s.id}
                  className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2">
                <div className="flex min-w-0 items-start gap-2">
                  <Monitor className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-[12.5px] font-medium">
                        {s.user_agent || 'Appareil inconnu'}
                      </span>
                      {s.is_current && (
                        <span className="shrink-0 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
                          cet appareil
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] text-muted-foreground">
                      {s.ip_address || 'IP inconnue'} · vu le {fmt(s.last_seen_at)}
                    </div>
                  </div>
                </div>
                <Button type="button" variant="outline" size="sm"
                        onClick={() => revoke(s)}
                        loading={revoking === s.id}
                        disabled={revoking === s.id}>
                  <LogOut className="size-4" /> Révoquer
                </Button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

// ── Changement de mot de passe (N96) — sert aussi à la rotation forcée ───────
function MotDePasse() {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError(null); setDone(false)
    if (next !== confirm) {
      setError('Les deux nouveaux mots de passe ne correspondent pas.')
      return
    }
    setBusy(true)
    try {
      await api.post('/auth/change-password/', {
        current_password: current,
        new_password: next,
      })
      setCurrent(''); setNext(''); setConfirm(''); setDone(true)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Impossible de changer le mot de passe.')
    } finally { setBusy(false) }
  }

  return (
    <Card>
      <CardContent className="pt-4 sm:pt-5">
        <SectionTitle
          label="Mot de passe"
          icon={<><rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></>}
        />
        <p className="mb-4 text-[11.5px] text-muted-foreground">
          Choisissez un mot de passe fort et unique. Si un administrateur vous a
          demandé de le changer, faites-le ici.
        </p>

        {error && (
          <div className="mb-3 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            <ShieldAlert className="size-4 shrink-0" /> <span>{error}</span>
          </div>
        )}
        {done && (
          <div className="mb-3 flex items-center gap-2 rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            <CheckCircle2 className="size-4 shrink-0" /> <span>Mot de passe mis à jour.</span>
          </div>
        )}

        <form onSubmit={submit} className="flex max-w-sm flex-col gap-3">
          <div>
            <div className="mb-1 text-[11px] text-muted-foreground">Mot de passe actuel</div>
            <Input type="password" value={current}
                   onChange={e => setCurrent(e.target.value)}
                   autoComplete="current-password" placeholder="••••••••"
                   aria-label="Mot de passe actuel" />
          </div>
          <div>
            <div className="mb-1 text-[11px] text-muted-foreground">Nouveau mot de passe</div>
            <Input type="password" value={next}
                   onChange={e => setNext(e.target.value)}
                   autoComplete="new-password" placeholder="••••••••"
                   aria-label="Nouveau mot de passe" />
          </div>
          <div>
            <div className="mb-1 text-[11px] text-muted-foreground">Confirmer le nouveau mot de passe</div>
            <Input type="password" value={confirm}
                   onChange={e => setConfirm(e.target.value)}
                   autoComplete="new-password" placeholder="••••••••"
                   aria-label="Confirmer le nouveau mot de passe" />
          </div>
          <div>
            <Button type="submit" loading={busy}
                    disabled={busy || !current || !next || !confirm}>
              <Lock className="size-4" /> Mettre à jour le mot de passe
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

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

  // VX201 — les codes de secours 2FA copiés restaient en clair sur le
  // presse-papiers indéfiniment (souvent synchronisé cloud sur certains OS) :
  // vidage best-effort ~60 s après la copie (on écrase par une chaîne vide ;
  // best-effort car on ne peut pas vérifier que l'utilisateur n'a rien copié
  // d'autre entre-temps — micro-avertissement affiché pour que ce ne soit
  // jamais une surprise).
  const copyRecovery = () => {
    if (!recovery) return
    try {
      navigator.clipboard?.writeText(recovery.join('\n'))
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
      setTimeout(() => {
        try { navigator.clipboard?.writeText('') } catch { /* ignore */ }
      }, 60000)
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
    <div className="flex flex-col gap-4">
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
            {copied && (
              <p className="mt-1.5 text-[10.5px] text-amber-700">
                Le presse-papiers sera vidé automatiquement dans ~60 s.
              </p>
            )}
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
              {/* VX120 — SVG rendu CÔTÉ SERVEUR (`qr_svg` dans la réponse de
                  `/auth/2fa/setup/`), plus aucun appel à un service tiers : la
                  graine TOTP ne quitte jamais notre origine. */}
              {renderTrustedSvg(setup.qr_svg) ? (
                <div
                  role="img"
                  aria-label="QR code de configuration 2FA"
                  className="size-40 shrink-0 overflow-hidden rounded border border-border bg-white p-1 [&>svg]:size-full"
                  dangerouslySetInnerHTML={renderTrustedSvg(setup.qr_svg)}
                />
              ) : (
                <div className="flex size-40 shrink-0 items-center justify-center rounded border border-border bg-muted p-2 text-center text-[11px] text-muted-foreground">
                  QR indisponible — utilisez la clé manuelle ci-contre.
                </div>
              )}
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

    {/* Sessions actives & révocation (N96) */}
    <SessionsActives />

    {/* Changement / rotation du mot de passe (N96) */}
    <MotDePasse />
    </div>
  )
}
