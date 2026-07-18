// NTDMO10 — toggle « Mode présentation » dans Paramètres → Société.
// Visible UNIQUEMENT si la société courante est une société de démonstration
// (`company_est_demo`). L'état est persisté côté serveur (PATCH company) puis
// re-synchronisé via /auth/me → il survit au rafraîchissement.
import { useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Eye } from 'lucide-react'
import demoApi from '../../api/demoApi'
import { fetchMe } from '../../features/auth/store/authSlice'
import { Card, CardContent } from '../../ui'
import { toast } from '../../ui/confirm'
import { SectionTitle } from './peComponents'

export default function PresentationModeToggle() {
  const user = useSelector((s) => s.auth.user)
  const dispatch = useDispatch()
  const [busy, setBusy] = useState(false)

  // Jamais affiché pour une société non-démo.
  if (!user?.company_est_demo) return null

  const active = !!user.company_mode_presentation_actif

  const onToggle = async () => {
    setBusy(true)
    try {
      await demoApi.setPresentationMode(user.company_id, !active)
      // Re-synchronise l'état serveur → persiste après rafraîchissement.
      await dispatch(fetchMe())
      toast.success(active ? 'Mode présentation désactivé.'
        : 'Mode présentation activé.')
    } catch {
      toast.error('Impossible de changer le mode présentation.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card data-testid="presentation-mode-card">
      <CardContent className="pt-4 sm:pt-5">
        <SectionTitle
          label="Mode présentation"
          icon={<><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z" /><circle cx="12" cy="12" r="3" /></>}
        />
        <p className="mb-3 text-[12px] text-muted-foreground">
          Masque les coordonnées (email, téléphone, adresse) des clients et
          pistes lors d'une démonstration devant un prospect. N'affecte jamais
          les documents officiels.
        </p>
        <label className="flex cursor-pointer items-center gap-2 text-[13px] font-medium">
          <input
            type="checkbox"
            checked={active}
            disabled={busy}
            onChange={onToggle}
            aria-label="Activer le mode présentation"
          />
          <Eye className="size-4" aria-hidden="true" />
          {active ? 'Activé' : 'Désactivé'}
        </label>
      </CardContent>
    </Card>
  )
}
