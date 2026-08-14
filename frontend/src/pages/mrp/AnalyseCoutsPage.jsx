// NTMFG11 — Rapport interne « Analyse des écarts de production » (coût de
// revient standard vs réel). Admin/responsable UNIQUEMENT — AUCUN prix/coût
// n'apparaît jamais dans un document client (DC28).
import { useEffect, useState } from 'react'
import { Calculator } from 'lucide-react'
import mrpApi from '../../api/mrpApi'
import { Card, CardContent, Spinner, EmptyState, Badge } from '../../ui'
import { PageHeader } from '../../ui/PageHeader'

export default function AnalyseCoutsPage() {
  const [rapport, setRapport] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    mrpApi.getAnalyseCouts({})
      .then((resp) => setRapport(resp.data || []))
      .catch(() => setErreur("Accès réservé responsable/admin ou aucune donnée."))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div>
      <PageHeader
        title="Analyse des écarts de production"
        subtitle="Coût standard vs réel — matière / main-d'œuvre / rendement. Interne, jamais client-facing."
        icon={Calculator}
      />
      {loading && <Spinner />}
      {!loading && erreur && <EmptyState title={erreur} />}
      {!loading && !erreur && rapport.length === 0 && (
        <EmptyState title="Aucun OF terminé avec un coût standard figé sur la période." />
      )}
      {!loading && !erreur && rapport.map((ligne) => (
        <Card key={ligne.produit_id} className="mb-3">
          <CardContent>
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-medium">{ligne.produit_nom}</h3>
              <Badge tone="neutral">{ligne.nb_of} OF</Badge>
            </div>
            <div className="grid grid-cols-3 gap-3 text-sm">
              <div>
                <div className="text-muted-foreground">Matière</div>
                <div>Std {ligne.cout_matiere_standard} / Réel {ligne.cout_matiere_reel}</div>
                <Badge tone={Number(ligne.ecart_matiere) > 0 ? 'danger' : 'success'}>
                  Écart {ligne.ecart_matiere}
                </Badge>
              </div>
              <div>
                <div className="text-muted-foreground">Main-d'œuvre</div>
                <div>Std {ligne.cout_main_oeuvre_standard} / Réel {ligne.cout_main_oeuvre_reel}</div>
                <Badge tone={Number(ligne.ecart_main_oeuvre) > 0 ? 'danger' : 'success'}>
                  Écart {ligne.ecart_main_oeuvre}
                </Badge>
              </div>
              <div>
                <div className="text-muted-foreground">Rendement</div>
                <Badge tone={Number(ligne.ecart_rendement) < 0 ? 'danger' : 'success'}>
                  Écart {ligne.ecart_rendement}
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
