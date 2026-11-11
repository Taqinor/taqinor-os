// NTDMO21 — widget « Ce que vous avez accompli ce mois-ci » (Dashboard démo).
// Visible UNIQUEMENT sur une société de démonstration (`company_est_demo`,
// servi par /auth/me) : aucun appel réseau et aucun rendu sur une société
// réelle. La phrase vient du serveur (cache nocturne NTDMO31) ; on n'affiche
// que ce qui est servi, et rien en cas d'échec (contrat demo_resume.json).
import { useEffect, useState } from 'react'
import { useSelector } from 'react-redux'
import { Sparkles } from 'lucide-react'
import reportingApi from '../api/reportingApi'
import { Card, CardContent } from '../ui'

export default function DemoResumeWidget() {
  const estDemo = useSelector((s) => !!s.auth.user?.company_est_demo)
  const [resume, setResume] = useState(null)

  useEffect(() => {
    if (!estDemo) return undefined
    let actif = true
    reportingApi.getDemoResume()
      .then((r) => { if (actif) setResume(r.data) })
      .catch(() => { if (actif) setResume(null) })
    return () => { actif = false }
  }, [estDemo])

  if (!estDemo || !resume?.phrase) return null

  return (
    <Card className="mb-4" data-testid="demo-resume-widget">
      <CardContent className="flex items-start gap-3 py-3">
        <Sparkles className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        <div>
          <p className="text-sm font-medium">Ce que vous avez accompli ce mois-ci</p>
          <p className="text-sm text-muted-foreground">{resume.phrase}</p>
        </div>
      </CardContent>
    </Card>
  )
}
