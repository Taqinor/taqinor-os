import { useCallback, useEffect, useMemo, useState } from 'react'
import { Play, Save, Trash2 } from 'lucide-react'
import {
  Badge, Button, Card, Checkbox, EmptyState, Input, toast,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import PageHeader from '../../components/layout/PageHeader'
import coreApi from '../../api/coreApi'

/* ============================================================================
   PACT122 — écran « Explorateur de données » (`/donnees/explorateur`).
   ----------------------------------------------------------------------------
   `core.SavedQuery` + son ViewSet (catalogue de datasets, exécution, requêtes
   sauvegardées personnelles ou de société) existaient, testés, SANS écran.

   FAIT AFFICHÉ HONNÊTEMENT, PAS MASQUÉ : un seul dataset est enregistré en
   production aujourd'hui (`sav_tickets`). Le moteur marche de bout en bout,
   mais le catalogue sera mince au lancement — l'écran affiche donc le nombre
   RÉEL de jeux de données et invite les apps à en déclarer d'autres. Aucune
   liste factice, aucun dataset codé en dur côté client.

   Le constructeur reste volontairement SIMPLE (champs projetés, un
   regroupement, une agrégation, une limite) : la spec est opaque pour `core`
   (`data_explorer.run_query`), et tout champ hors liste blanche est refusé
   côté serveur — l'écran ne rejoue aucune de ces règles.
   ========================================================================== */

const AGREGATS = [
  ['count', 'Nombre'],
  ['sum', 'Somme'],
  ['avg', 'Moyenne'],
  ['min', 'Minimum'],
  ['max', 'Maximum'],
]

function listeDe(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.results)) return data.results
  return []
}

function messageErreur(err, repli) {
  const data = err?.response?.data
  if (typeof data?.detail === 'string') return data.detail
  if (typeof data === 'string' && data) return data
  return repli
}

/* Construit la spec envoyée au moteur. Une clé absente est OMISE plutôt
   qu'envoyée vide : `run_query` traite `[]` et l'absence pareillement, mais
   un corps minimal est plus lisible dans les journaux serveur. */
function construireSpec({ select, groupBy, aggFn, aggField, limite }) {
  const spec = {}
  const champs = Array.isArray(select) ? select.filter(Boolean) : []
  if (champs.length > 0) spec.select = champs
  if (groupBy) spec.group_by = [groupBy]
  if (aggFn) {
    const agg = { alias: aggField ? `${aggFn}_${aggField}` : aggFn, fn: aggFn }
    if (aggField) agg.field = aggField
    spec.aggregates = [agg]
  }
  const n = Number(String(limite ?? '').trim())
  if (String(limite ?? '').trim() !== '' && Number.isFinite(n) && n > 0) {
    spec.limit = n
  }
  return spec
}

/* Colonnes du tableau de résultats : union ORDONNÉE des clés des lignes
   (le moteur renvoie des dicts, pas un schéma). */
function colonnesDe(rows) {
  const cols = []
  for (const row of Array.isArray(rows) ? rows : []) {
    if (!row || typeof row !== 'object') continue
    for (const cle of Object.keys(row)) {
      if (!cols.includes(cle)) cols.push(cle)
    }
  }
  return cols
}

function cellule(valeur) {
  if (valeur === null || valeur === undefined) return '—'
  if (typeof valeur === 'object') return JSON.stringify(valeur)
  return String(valeur)
}

export default function ExplorateurDonneesPage() {
  const [datasets, setDatasets] = useState([])
  const [requetes, setRequetes] = useState([])
  const [chargement, setChargement] = useState(true)
  const [erreur, setErreur] = useState('')
  const [dataset, setDataset] = useState('')
  const [select, setSelect] = useState([])
  const [groupBy, setGroupBy] = useState('')
  const [aggFn, setAggFn] = useState('')
  const [aggField, setAggField] = useState('')
  const [limite, setLimite] = useState('50')
  const [lignes, setLignes] = useState(null)
  const [titre, setTitre] = useState('')
  const [partage, setPartage] = useState(false)
  const [occupe, setOccupe] = useState(false)

  const chargerRequetes = useCallback(async () => {
    try {
      const res = await coreApi.savedQueries.list()
      setRequetes(listeDe(res?.data))
    } catch {
      setRequetes([])
    }
  }, [])

  useEffect(() => {
    let vivant = true
    coreApi.savedQueries.datasets()
      .then((res) => {
        if (!vivant) return
        setDatasets(listeDe(res?.data))
        setErreur('')
      })
      .catch((err) => {
        if (!vivant) return
        setDatasets([])
        setErreur(messageErreur(err, 'Catalogue de jeux de données indisponible.'))
      })
      .finally(() => { if (vivant) setChargement(false) })
    // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
    chargerRequetes()
    return () => { vivant = false }
  }, [chargerRequetes])

  const champs = useMemo(() => {
    const d = datasets.find((x) => x.name === dataset)
    return Array.isArray(d?.fields) ? d.fields : []
  }, [datasets, dataset])

  function choisirDataset(nom) {
    setDataset(nom)
    setSelect([])
    setGroupBy('')
    setAggFn('')
    setAggField('')
    setLignes(null)
  }

  function basculerChamp(champ) {
    setSelect((s) => (s.includes(champ) ? s.filter((c) => c !== champ) : [...s, champ]))
  }

  async function executer() {
    if (!dataset || occupe) return
    setOccupe(true)
    try {
      const res = await coreApi.savedQueries.runAdhoc(
        dataset,
        construireSpec({ select, groupBy, aggFn, aggField, limite }),
      )
      setLignes(Array.isArray(res?.data?.rows) ? res.data.rows : [])
    } catch (err) {
      toast.error(messageErreur(err, 'Exécution impossible.'))
    } finally {
      setOccupe(false)
    }
  }

  async function sauvegarder() {
    if (!dataset || occupe) return
    const nom = titre.trim()
    if (!nom) {
      toast.error('Donnez un titre à la requête.')
      return
    }
    setOccupe(true)
    try {
      await coreApi.savedQueries.create({
        titre: nom,
        dataset,
        spec: construireSpec({ select, groupBy, aggFn, aggField, limite }),
        partage,
      })
      toast.success(
        partage ? `« ${nom} » enregistrée pour la société.` : `« ${nom} » enregistrée en personnel.`,
      )
      setTitre('')
      chargerRequetes()
    } catch (err) {
      toast.error(messageErreur(err, 'Enregistrement impossible.'))
    } finally {
      setOccupe(false)
    }
  }

  async function executerSauvegardee(requete) {
    if (occupe) return
    setOccupe(true)
    try {
      const res = await coreApi.savedQueries.run(requete.id)
      setLignes(Array.isArray(res?.data?.rows) ? res.data.rows : [])
    } catch (err) {
      toast.error(messageErreur(err, 'Exécution impossible.'))
    } finally {
      setOccupe(false)
    }
  }

  async function supprimer(requete) {
    try {
      await coreApi.savedQueries.remove(requete.id)
      toast.success('Requête supprimée.')
      chargerRequetes()
    } catch (err) {
      toast.error(messageErreur(err, 'Suppression impossible.'))
    }
  }

  const colonnes = colonnesDe(lignes)

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Explorateur de données"
        subtitle="Construisez une requête sur un jeu de données enregistré, exécutez-la et sauvegardez-la (FG382)."
      />

      <Card className="flex flex-col gap-3 p-4 sm:p-5">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-medium text-foreground">Jeux de données</h3>
          <Badge tone="neutral" data-testid="expl-nb-datasets">
            {datasets.length} enregistré(s)
          </Badge>
        </div>
        {/* Honnêteté d'affichage : on annonce le catalogue tel qu'il est. */}
        <p className="text-xs text-muted-foreground">
          Le catalogue ne contient que les jeux de données réellement déclarés
          par les modules ; il s&apos;étoffera à mesure qu&apos;ils en publient.
        </p>

        {chargement && <p className="text-sm text-muted-foreground">Chargement du catalogue…</p>}
        {!chargement && erreur && <EmptyState title="Erreur" description={erreur} />}
        {!chargement && !erreur && datasets.length === 0 && (
          <EmptyState
            title="Aucun jeu de données"
            description="Aucun module n'a encore déclaré de jeu de données interrogeable."
          />
        )}
        {!chargement && !erreur && datasets.length > 0 && (
          <div className="flex flex-wrap gap-2" data-testid="expl-datasets">
            {datasets.map((d) => (
              <Button
                key={d.name}
                type="button"
                size="sm"
                variant={dataset === d.name ? 'default' : 'secondary'}
                aria-pressed={dataset === d.name}
                onClick={() => choisirDataset(d.name)}
              >
                {d.label || d.name}
              </Button>
            ))}
          </div>
        )}
      </Card>

      {dataset && (
        <Card className="flex flex-col gap-4 p-4 sm:p-5" data-testid="expl-constructeur">
          <h3 className="text-sm font-medium text-foreground">Construire la requête</h3>

          <div className="flex flex-col gap-2">
            <span className="text-xs text-muted-foreground">Champs affichés</span>
            <div className="flex flex-wrap gap-3">
              {champs.map((c) => (
                <label key={c} className="flex items-center gap-2 text-sm">
                  <Checkbox
                    aria-label={`Champ ${c}`}
                    checked={select.includes(c)}
                    onCheckedChange={() => basculerChamp(c)}
                  />
                  {c}
                </label>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <Select value={groupBy} onValueChange={setGroupBy}>
              <SelectTrigger className="sm:w-56" aria-label="Regrouper par">
                <SelectValue placeholder="Regrouper par (optionnel)" />
              </SelectTrigger>
              <SelectContent>
                {champs.map((c) => (
                  <SelectItem key={c} value={c}>{c}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={aggFn} onValueChange={setAggFn}>
              <SelectTrigger className="sm:w-48" aria-label="Agrégation">
                <SelectValue placeholder="Agrégation (optionnel)" />
              </SelectTrigger>
              <SelectContent>
                {AGREGATS.map(([valeur, libelle]) => (
                  <SelectItem key={valeur} value={valeur}>{libelle}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={aggField} onValueChange={setAggField}>
              <SelectTrigger className="sm:w-56" aria-label="Champ agrégé">
                <SelectValue placeholder="Champ agrégé (optionnel)" />
              </SelectTrigger>
              <SelectContent>
                {champs.map((c) => (
                  <SelectItem key={c} value={c}>{c}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              className="sm:w-28"
              inputMode="numeric"
              step="any"
              aria-label="Limite"
              value={limite}
              onChange={(e) => setLimite(e.target.value)}
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button onClick={executer} disabled={occupe} data-testid="expl-executer">
              <Play /> Exécuter
            </Button>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <Input
              className="sm:flex-1"
              placeholder="Titre de la requête"
              aria-label="Titre de la requête"
              value={titre}
              onChange={(e) => setTitre(e.target.value)}
            />
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                aria-label="Partager avec la société"
                checked={partage}
                onCheckedChange={(v) => setPartage(v === true)}
              />
              Visible par toute la société
            </label>
            <Button
              variant="secondary"
              onClick={sauvegarder}
              disabled={occupe}
              data-testid="expl-sauvegarder"
            >
              <Save /> Sauvegarder
            </Button>
          </div>
        </Card>
      )}

      {lignes !== null && (
        <Card className="flex flex-col gap-3 p-4 sm:p-5" data-testid="expl-resultat">
          <h3 className="text-sm font-medium text-foreground">
            Résultat — {lignes.length} ligne(s)
          </h3>
          {lignes.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucune ligne pour cette requête.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr>
                    {colonnes.map((c) => (
                      <th key={c} className="border-b border-border px-2 py-1 text-left font-medium">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {lignes.map((row, i) => (
                    <tr key={i}>
                      {colonnes.map((c) => (
                        <td key={c} className="border-b border-border px-2 py-1">
                          {cellule(row?.[c])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      <Card className="flex flex-col gap-3 p-4 sm:p-5">
        <h3 className="text-sm font-medium text-foreground">Requêtes sauvegardées</h3>
        {requetes.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Aucune requête sauvegardée pour l&apos;instant.
          </p>
        ) : (
          <ul className="flex flex-col gap-2" data-testid="expl-sauvegardees">
            {requetes.map((r) => (
              <li
                key={r.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border p-3"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{r.titre}</span>
                  <Badge tone="neutral">{r.dataset}</Badge>
                  <Badge tone={r.partage ? 'info' : 'outline'}>
                    {r.partage ? 'Société' : 'Personnelle'}
                  </Badge>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => executerSauvegardee(r)}
                    data-testid={`expl-run-${r.id}`}
                  >
                    Exécuter
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => supprimer(r)}>
                    <Trash2 /> Supprimer
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
