import { useEffect, useMemo, useState } from 'react'
import { FlaskConical, ShieldQuestion } from 'lucide-react'
import coreApi from '../../api/coreApi'
import {
  Card, CardContent, Badge, Input, Label, Spinner,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { formatMAD } from '../../lib/format'
import { resoudreMatriceSimulee } from './matriceResolution'

/* ============================================================================
   NTWFL32 — Simulateur « what-if » de la matrice d'approbation.
   ----------------------------------------------------------------------------
   Écran ADMIN pur GET : charge les lignes réelles de `MatriceApprobation` de
   la société (NTWFL1, `GET /core/matrices-approbation/`, lecture ouverte à
   tout utilisateur authentifié côté serveur) puis résout, ENTIÈREMENT côté
   client (`matriceResolution.js`, port fidèle de `core.selectors.
   resoudre_matrice`), quelle chaîne de paliers s'appliquerait à un type
   d'objet + montant + département FICTIFS — sans jamais écrire ni créer
   d'instance réelle. Toute règle affichée provient de données réellement
   chargées ; rien n'est simulé côté données, seule la RÉSOLUTION l'est.
   ========================================================================== */

export default function MatriceSimulator() {
  const [regles, setRegles] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [typeObjet, setTypeObjet] = useState('__all')
  const [montant, setMontant] = useState('')
  const [departement, setDepartement] = useState('')

  useEffect(() => {
    let alive = true
    coreApi.matricesApprobation.list()
      .then((r) => {
        if (!alive) return
        const rows = r.data?.results ?? r.data ?? []
        setRegles(Array.isArray(rows) ? rows : [])
      })
      .catch(() => { if (alive) setError('Chargement des règles impossible.') })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [])

  const typesObjet = useMemo(
    () => [...new Set(regles.map((r) => r.type_objet).filter(Boolean))].sort(),
    [regles],
  )

  const montantSimule = montant.trim() === '' ? null : montant

  const resultat = useMemo(
    () => resoudreMatriceSimulee(
      regles,
      typeObjet === '__all' ? null : typeObjet,
      montantSimule,
      departement.trim() || null,
    ),
    [regles, typeObjet, montantSimule, departement],
  )

  const candidatesConcurrentes = useMemo(() => {
    if (typeObjet === '__all') return []
    return regles.filter((r) => r.actif && r.type_objet === typeObjet)
  }, [regles, typeObjet])

  if (loading) {
    return (
      <div className="page">
        <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground">
          <Spinner /> Chargement des règles…
        </p>
      </div>
    )
  }

  return (
    <div className="page flex flex-col gap-6">
      <div className="page-header">
        <h1 className="page-title flex items-center gap-2">
          <FlaskConical className="size-5 text-muted-foreground" aria-hidden="true" />
          Simulateur de matrice d&apos;approbation
        </h1>
        <div className="page-subtitle">
          Testez un type d&apos;objet, un montant et un département FICTIFS
          avant de publier une nouvelle règle — aucune donnée n&apos;est
          écrite ni créée par cet écran (lecture seule).
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card>
        <CardContent className="grid gap-4 pt-4 sm:grid-cols-3 sm:pt-5">
          <div>
            <Label htmlFor="matsim-type">Type d&apos;objet</Label>
            <Select value={typeObjet} onValueChange={setTypeObjet}>
              <SelectTrigger id="matsim-type"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__all">— Choisir un type —</SelectItem>
                {typesObjet.map((t) => (
                  <SelectItem key={t} value={t}>{t}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="matsim-montant">Montant simulé (MAD)</Label>
            <Input
              id="matsim-montant" type="number" step="any" noValidate
              placeholder="ex. 25000"
              value={montant}
              onChange={(e) => setMontant(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="matsim-departement">Département simulé (optionnel)</Label>
            <Input
              id="matsim-departement" type="text"
              placeholder="ex. Achats"
              value={departement}
              onChange={(e) => setDepartement(e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="flex flex-col gap-3 pt-4 sm:pt-5">
          <h2 className="text-sm font-semibold">Chaîne résolue</h2>
          {typeObjet === '__all' && (
            <p className="text-sm text-muted-foreground">
              Choisissez un type d&apos;objet pour lancer la simulation.
            </p>
          )}
          {typeObjet !== '__all' && !resultat && (
            <p className="flex items-center gap-2 text-sm text-muted-foreground" data-testid="matsim-aucune-regle">
              <ShieldQuestion className="size-4" aria-hidden="true" />
              Aucune règle active ne couvre ce triplet — aucune chaîne
              d&apos;approbation ne s&apos;appliquerait.
            </p>
          )}
          {resultat && (
            <div data-testid="matsim-resultat" className="rounded-lg border border-border p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{resultat.type_objet}</span>
                <Badge tone="info">
                  {resultat.departement ? `Département : ${resultat.departement}` : 'Tous départements'}
                </Badge>
                <Badge tone="outline">
                  {resultat.montant_min != null || resultat.montant_max != null
                    ? [
                      resultat.montant_min != null ? `≥ ${formatMAD(resultat.montant_min)}` : null,
                      resultat.montant_max != null ? `≤ ${formatMAD(resultat.montant_max)}` : null,
                    ].filter(Boolean).join(' · ')
                    : 'Montant illimité'}
                </Badge>
              </div>
              <ol className="mt-3 flex flex-col gap-1.5 text-sm">
                {(resultat.chaine_paliers || []).map((p, i) => (
                  <li key={p.palier ?? i} className="flex items-center gap-2">
                    <Badge>{p.palier ?? i + 1}</Badge>
                    <span>{p.role_requis || '—'}</span>
                    <span className="text-muted-foreground">
                      ({p.nombre_approbateurs_requis ?? 1} approbateur·s)
                    </span>
                  </li>
                ))}
                {(!resultat.chaine_paliers || resultat.chaine_paliers.length === 0) && (
                  <li className="text-muted-foreground">Aucun palier défini sur cette règle.</li>
                )}
              </ol>
            </div>
          )}

          {candidatesConcurrentes.length > 1 && (
            <p className="text-xs text-muted-foreground">
              {candidatesConcurrentes.length} règle(s) active(s) pour ce type
              d&apos;objet — le montant/département simulé détermine laquelle
              gagne (spécificité décroissante).
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
