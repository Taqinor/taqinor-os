// NTAI6 — Paramètres → IA : ce qui est ACTIF, ce qui ne l'est pas, et pourquoi.
//
// Jusqu'ici, « l'IA ne marche pas » n'avait aucune réponse lisible : il fallait
// ouvrir le `.env` du serveur. Cette carte dit, par capacité (OCR /
// transcription / vision / génération) : le fournisseur choisi, s'il est
// réellement actif, LE MOTIF quand il ne l'est pas, et ses mesures réelles
// (appels, latence médiane, dernière erreur) issues du journal d'usage.
//
// AUCUNE CLÉ N'EST AFFICHÉE — le serveur ne renvoie que le NOM du fournisseur.
// Aucun chiffre n'est inventé : une capacité jamais appelée affiche « aucune
// mesure », jamais « 0 ms » (qui se lirait comme « instantané »).
// Admin/Directeur uniquement (le backend applique la même règle).
import { useCallback, useEffect, useState } from 'react'
import { AlertCircle } from 'lucide-react'
import aiGovernanceApi from '../../api/aiGovernanceApi'
import {
  Card, CardContent, Button, Spinner, EmptyState, Badge,
} from '../../ui'

const LIBELLES = {
  ocr: 'OCR — lecture de documents',
  stt: 'Transcription audio',
  vision_qa: 'Contrôle vision (photos de chantier)',
  llm: 'Génération de texte',
}

export default function IaCapacites() {
  const [capacites, setCapacites] = useState(null) // null = chargement
  const [budget, setBudget] = useState(null)
  const [loadError, setLoadError] = useState(false)

  const load = useCallback(() => {
    setLoadError(false)
    setCapacites(null)
    aiGovernanceApi.capabilities()
      .then((res) => setCapacites(res.data || []))
      .catch(() => setLoadError(true))
    // Le budget est une information SÉPARÉE : son absence (aucun budget
    // défini) n'est pas une erreur, et ne doit pas masquer les capacités.
    aiGovernanceApi.budgetStatut()
      .then((res) => setBudget(res.data || null))
      .catch(() => setBudget(null))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement initial au montage
  useEffect(() => { load() }, [load])

  return (
    <div className="mx-auto max-w-[720px] p-6">
      <div className="mb-4">
        <h2 className="font-display text-xl font-bold tracking-tight text-foreground">
          Paramètres — IA : capacités actives
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          État réel de chaque capacité IA pour votre société. Aucune clé
          d'API n'est affichée ici.
        </p>
      </div>

      {loadError && (
        <EmptyState
          tone="error"
          icon={AlertCircle}
          title="État indisponible"
          description="Impossible de charger l'état des capacités IA (serveur ?)."
          action={<Button type="button" size="sm" variant="outline" onClick={load}>Réessayer</Button>}
        />
      )}

      {!loadError && capacites === null && (
        <p className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
          <Spinner /> Chargement…
        </p>
      )}

      {!loadError && capacites !== null && (
        <div className="flex flex-col gap-4">
          {budget?.configure && (
            <Card>
              <CardContent className="p-5">
                <h3 className="mb-2 text-sm font-semibold text-foreground">
                  Budget IA du mois
                </h3>
                <p className="text-sm text-muted-foreground">
                  {budget.depense_mad} MAD consommés sur {budget.plafond_mad} MAD
                  {' '}({Math.round(budget.pourcentage)} %).
                </p>
                {budget.depasse && (
                  <p className="mt-2 text-sm font-medium text-destructive">
                    Plafond atteint — la génération de texte est suspendue
                    jusqu'au relèvement du plafond.
                  </p>
                )}
              </CardContent>
            </Card>
          )}

          {capacites.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Aucune capacité déclarée.
            </p>
          )}

          {capacites.map((cap) => (
            <Card key={cap.capacite}>
              <CardContent className="p-5">
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-sm font-semibold text-foreground">
                    {LIBELLES[cap.capacite] || cap.capacite}
                  </h3>
                  <Badge tone={cap.configure ? 'success' : 'neutral'}>
                    {cap.configure ? 'Active' : 'Inactive'}
                  </Badge>
                </div>

                <p className="mt-2 text-xs text-muted-foreground">
                  Fournisseur : <span className="font-mono">{cap.fournisseur_actif || '—'}</span>
                </p>

                {!cap.configure && cap.motif && (
                  <p className="mt-2 text-sm text-muted-foreground">{cap.motif}</p>
                )}

                <p className="mt-2 text-xs text-muted-foreground">
                  {cap.appels == null
                    ? 'Aucune mesure pour le moment.'
                    : `${cap.appels} appel(s)`}
                  {cap.latence_p50_ms != null
                    && ` · latence médiane ${cap.latence_p50_ms} ms`}
                </p>

                {cap.derniere_erreur && (
                  <p className="mt-2 text-xs text-destructive">
                    Dernière erreur : {cap.derniere_erreur}
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
