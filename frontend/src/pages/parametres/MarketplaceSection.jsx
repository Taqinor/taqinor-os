// WIR159 — Onglet « Marketplace » : catalogue des packages d'extension (NTEXT13).
//
// Vue LECTURE SEULE du registre GLOBAL de packages installables
// (`GET /extensions/catalogue/`). Un package est un GABARIT décrivant ce qu'il
// poserait sur un tenant (objets/champs personnalisés, règles d'automatisation,
// rapports, gabarits de document) — décrit dans son `manifest` JSON, jamais
// matérialisé ici. L'INSTALLATION par tenant est une brique séparée non encore
// construite (NTEXT14) : cet écran se contente de faire PARCOURIR le catalogue,
// avec un bandeau clair rappelant que l'installation arrive plus tard.
//
// Fonctionnel uniquement — cartes/Card du kit UX1 (même gabarit que les autres
// sections de Paramètres), aucun travail de design.
import { useEffect, useMemo, useState } from 'react'
import { Package, Boxes, Zap, BarChart3, FileText } from 'lucide-react'
import api from '../../api/axios'
import { Card, CardContent, Badge, Spinner, EmptyState } from '../../ui'
import { SectionTitle } from './peComponents'

// Familles connues du manifest → libellé FR + icône (aucune icône non vérifiée).
const MANIFEST_FAMILIES = [
  ['custom_object_defs', 'Objets personnalisés', Boxes],
  ['automation_rules', "Règles d'automatisation", Zap],
  ['rapport_definitions', 'Rapports', BarChart3],
  ['branded_templates', 'Gabarits de document', FileText],
]

// Résume le manifest en compteurs lisibles (« 2 objets · 1 règle »). Ignore
// silencieusement toute clé inconnue — le manifest est documenté, jamais exécuté.
function resumeManifest(manifest) {
  if (!manifest || typeof manifest !== 'object') return []
  return MANIFEST_FAMILIES
    .map(([key, label, Icon]) => {
      const val = manifest[key]
      const count = Array.isArray(val) ? val.length : 0
      return count > 0 ? { key, label, Icon, count } : null
    })
    .filter(Boolean)
}

export default function MarketplaceSection() {
  const [packages, setPackages] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)

  useEffect(() => {
    let cancelled = false
    api.get('/extensions/catalogue/')
      .then((res) => {
        if (cancelled) return
        const rows = res.data?.results ?? res.data ?? []
        setPackages(Array.isArray(rows) ? rows : [])
        setLoadError(false)
      })
      .catch(() => { if (!cancelled) setLoadError(true) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  // Regroupement par catégorie (rendu déterministe, testable) — catégories
  // triées, packages triés par nom dans chaque catégorie.
  const groups = useMemo(() => {
    const byCategorie = {}
    packages.forEach((p) => {
      const cat = p.categorie || 'Général'
      ;(byCategorie[cat] ||= []).push(p)
    })
    return Object.keys(byCategorie).sort().map((categorie) => ({
      categorie,
      items: byCategorie[categorie].slice().sort((a, b) => (a.nom || '').localeCompare(b.nom || '')),
    }))
  }, [packages])

  if (loading) return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <Spinner className="size-4 text-primary" /> Chargement…
    </p>
  )
  if (loadError) {
    return (
      <EmptyState title="Impossible de charger le catalogue d'extensions"
        description="Une erreur est survenue lors du chargement." className="py-6" />
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-[11.5px] text-muted-foreground">
        Catalogue des packages d'extension disponibles. Chaque package décrit ce
        qu'il ajouterait à votre société (objets et champs personnalisés, règles
        d'automatisation, rapports, gabarits). L'installation par société arrivera
        dans une prochaine version — pour l'instant, ce catalogue est consultable.
      </p>

      {packages.length === 0 && (
        <EmptyState
          icon={Package}
          title="Aucun package d'extension"
          description="Le catalogue est vide pour le moment."
          className="py-6"
        />
      )}

      {groups.map((group) => (
        <Card key={group.categorie}>
          <CardContent className="pt-4 sm:pt-5">
            <SectionTitle label={group.categorie} />
            <div className="flex flex-col gap-2">
              {group.items.map((pkg) => {
                const resume = resumeManifest(pkg.manifest)
                return (
                  <div key={pkg.id ?? pkg.code} className="rounded-lg border border-border p-3"
                    data-testid={`extension-row-${pkg.code}`}>
                    <div className="flex flex-wrap items-center gap-2">
                      <Package className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                      <span className="min-w-[140px] flex-[1_1_140px] font-medium text-sm">
                        {pkg.nom || pkg.code}
                      </span>
                      <Badge tone="neutral">v{pkg.version || '1.0.0'}</Badge>
                    </div>
                    {pkg.description && (
                      <p className="mt-1 text-xs text-muted-foreground">{pkg.description}</p>
                    )}
                    {resume.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {resume.map((r) => {
                          const { key, label, Icon, count } = r
                          return (
                            <span key={key}
                              className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                              <Icon className="size-3" aria-hidden="true" />
                              {count} {label}
                            </span>
                          )
                        })}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
