import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Scale } from 'lucide-react'
import juridiqueApi from '../../api/juridiqueApi'
import { Card, CardContent } from '../../ui'
import { formatMAD } from '../../lib/format'

/* ============================================================================
   NTJUR24 — Carte « Risques juridiques » du cockpit direction.
   ----------------------------------------------------------------------------
   Lecture SEULE de l'agrégat serveur ``/juridique/dossiers/tableau-bord/``.

   AUCUNE FUITE PAR AGRÉGAT : le filtrage de confidentialité est appliqué
   CÔTÉ SERVEUR (``selectors.tableau_bord_juridique`` exclut les dossiers
   ``confidentiel`` du périmètre d'un rôle non autorisé) — l'écran affiche donc
   déjà des totaux amputés pour ce rôle, sans avoir à le savoir. Rien n'est
   recalculé ici, aucun montant n'est dérivé : on n'affiche que ce que le
   serveur a compté.

   Dégrade EN SILENCE (la carte disparaît) si l'appel échoue (403, module
   désactivé) ou si la société n'a aucun dossier — jamais un 0 trompeur sur un
   cockpit de direction.
   ========================================================================== */

export default function RisquesJuridiquesCard() {
  const navigate = useNavigate()
  const [bord, setBord] = useState(null) // null = en cours, false = indisponible

  useEffect(() => {
    let alive = true
    juridiqueApi.tableauBord()
      .then((res) => { if (alive) setBord(res.data ?? false) })
      .catch(() => { if (alive) setBord(false) })
    return () => { alive = false }
  }, [])

  if (!bord || !bord.nombre_dossiers) return null

  const aller = () => navigate('/juridique')
  const onKeyGo = (e) => { if (e.key === 'Enter') aller() }

  const tuiles = [
    {
      id: 'dossiers',
      label: 'Dossiers ouverts',
      valeur: String(bord.nombre_dossiers ?? 0),
      detail: (bord.par_nature || [])
        .map((n) => `${n.nombre} ${n.nature}`)
        .join(' · '),
    },
    {
      id: 'montant',
      label: 'Montant total en jeu',
      valeur: formatMAD(bord.montant_en_jeu_total),
      detail: 'Dossiers non clos',
    },
    {
      id: 'provisions',
      label: 'Provisions',
      valeur: `${bord.provisions_comptabilisees ?? 0} comptabilisée(s)`,
      detail: `${bord.provisions_proposees ?? 0} proposée(s), non comptabilisée(s)`,
    },
    {
      id: 'prescriptions',
      label: 'Prescriptions < 30 j',
      valeur: String(bord.echeances_prescription_30j ?? 0),
      detail: 'Délais en cours qui expirent bientôt',
    },
  ]

  return (
    <div data-testid="juridique-risques-card">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-foreground">
        <Scale size={16} strokeWidth={1.75} aria-hidden="true" />
        Risques juridiques
      </div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-4">
        {tuiles.map((t) => (
          <Card
            key={t.id}
            role="button"
            tabIndex={0}
            onClick={aller}
            onKeyDown={onKeyGo}
            className="cursor-pointer"
          >
            <CardContent className="py-4">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                {t.label}
              </p>
              <p className="num mt-1 text-2xl font-semibold text-foreground">
                {t.valeur}
              </p>
              {t.detail && (
                <p className="mt-1 text-xs text-muted-foreground">{t.detail}</p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
