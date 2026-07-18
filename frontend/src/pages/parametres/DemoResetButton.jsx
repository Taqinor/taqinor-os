// NTDMO7 — bouton « Réinitialiser les données de démonstration ».
// Visible UNIQUEMENT quand la société courante est une société de démonstration
// (`company_est_demo`, servi par /auth/me). Absent sur toute société réelle.
import { useState } from 'react'
import { useSelector } from 'react-redux'
import { RotateCcw } from 'lucide-react'
import demoApi from '../../api/demoApi'
import { Button, Card, CardContent } from '../../ui'
import { toast, useConfirmDialog } from '../../ui/confirm'
import { SectionTitle } from './peComponents'

export default function DemoResetButton() {
  const user = useSelector((s) => s.auth.user)
  const { confirm } = useConfirmDialog()
  const [busy, setBusy] = useState(false)

  // Garde stricte : rien ne s'affiche pour une société non-démo.
  if (!user?.company_est_demo) return null

  const onReset = async () => {
    const ok = await confirm({
      title: 'Réinitialiser les données de démonstration ?',
      body: 'Toutes les données de démonstration seront effacées puis '
        + 'régénérées à neuf. Les sociétés réelles ne sont jamais touchées.',
      confirmLabel: 'Réinitialiser',
      cancelLabel: 'Annuler',
      destructive: true,
    })
    if (!ok) return
    setBusy(true)
    try {
      await demoApi.resetDemo(user.company_id)
      toast.success('Données de démonstration réinitialisées.')
    } catch {
      toast.error('La réinitialisation a échoué.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card data-testid="demo-reset-card">
      <CardContent className="pt-4 sm:pt-5">
        <SectionTitle
          label="Démonstration"
          icon={<><path d="M3 12a9 9 0 1 0 9-9" /><polyline points="3 3 3 9 9 9" /></>}
        />
        <p className="mb-3 text-[12px] text-muted-foreground">
          Cette société est une société de démonstration. Vous pouvez
          régénérer un jeu de données complet à tout moment.
        </p>
        <Button
          type="button"
          variant="outline"
          disabled={busy}
          onClick={onReset}
        >
          <RotateCcw className="mr-1.5 size-4" aria-hidden="true" />
          Réinitialiser les données de démonstration
        </Button>
      </CardContent>
    </Card>
  )
}
