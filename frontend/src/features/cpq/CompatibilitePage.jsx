import { useCallback, useEffect, useState } from 'react'
import { Plus, ShieldAlert, Trash2, TriangleAlert } from 'lucide-react'
import {
  Badge, Button, Card, EmptyState, Input, toast,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import PageHeader from '../../components/layout/PageHeader'
import cpqApi from '../../api/cpqApi'
import stockApi from '../../api/stockApi'

/* ============================================================================
   PACT126 — écran « Compatibilité produits » (`/cpq/compatibilite`).
   ----------------------------------------------------------------------------
   Les contraintes NTCPQ1 (INCOMPATIBLE / REQUIERT / RECOMMANDE) et leur
   validateur existaient côté serveur sans aucun écran. Deux blocs :

     * la GRILLE des règles, éditable (créer / changer le type / supprimer) ;
     * le panneau « Tester » : on poste une liste de produits à
       `POST cpq/valider-compatibilite/` et on affiche SÉPARÉMENT ce que le
       serveur sépare déjà — `bloquantes` (INCOMPATIBLE + REQUIERT) d'un côté,
       `avertissements` (RECOMMANDE) de l'autre. Cette séparation n'est JAMAIS
       recalculée ici : elle vient du serveur, sinon deux définitions du mot
       « bloquant » divergeraient.
   ========================================================================== */

const TYPES = [
  ['INCOMPATIBLE', 'Incompatible'],
  ['REQUIERT', 'Requiert'],
  ['RECOMMANDE', 'Recommandé'],
]

const LIBELLE_TYPE = Object.fromEntries(TYPES)

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

function nomProduit(produits, id) {
  const p = produits.find((x) => String(x.id) === String(id))
  return p ? (p.nom || `Produit #${p.id}`) : `Produit #${id}`
}

function ListeViolations({ titre, violations, produits, ton, testId }) {
  return (
    <div className="flex flex-col gap-2" data-testid={testId}>
      <h4 className="text-sm font-medium text-foreground">
        {titre} <Badge tone={ton}>{violations.length}</Badge>
      </h4>
      {violations.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aucune.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {violations.map((v, i) => (
            <li
              key={`${v.produit_a}-${v.produit_b}-${i}`}
              className="rounded-md border border-border p-3 text-sm"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={ton}>{LIBELLE_TYPE[v.type] || v.type}</Badge>
                <span className="font-medium">{nomProduit(produits, v.produit_a)}</span>
                <span className="text-muted-foreground">→</span>
                <span className="font-medium">{nomProduit(produits, v.produit_b)}</span>
              </div>
              {v.message && (
                <p className="mt-1 text-muted-foreground">{v.message}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function CompatibilitePage() {
  const [regles, setRegles] = useState([])
  const [produits, setProduits] = useState([])
  const [chargement, setChargement] = useState(true)
  const [erreur, setErreur] = useState('')
  const [brouillon, setBrouillon] = useState({
    produit_a: '', produit_b: '', type: 'INCOMPATIBLE', message_utilisateur: '',
  })
  const [selection, setSelection] = useState([])
  const [resultat, setResultat] = useState(null)
  const [occupe, setOccupe] = useState(false)

  const charger = useCallback(async () => {
    setChargement(true)
    try {
      const res = await cpqApi.getContraintesCompatibilite()
      setRegles(listeDe(res?.data))
      setErreur('')
    } catch (err) {
      setErreur(messageErreur(err, 'Règles de compatibilité indisponibles.'))
      setRegles([])
    } finally {
      setChargement(false)
    }
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { charger() }, [charger])

  useEffect(() => {
    let vivant = true
    stockApi.getProduits({ page_size: 200 })
      .then((res) => { if (vivant) setProduits(listeDe(res?.data)) })
      .catch(() => { if (vivant) setProduits([]) })
    return () => { vivant = false }
  }, [])

  async function creer() {
    if (occupe) return
    if (!brouillon.produit_a || !brouillon.produit_b) {
      toast.error('Choisissez les deux produits de la règle.')
      return
    }
    if (brouillon.produit_a === brouillon.produit_b) {
      toast.error('Une règle relie DEUX produits différents.')
      return
    }
    setOccupe(true)
    try {
      await cpqApi.createContrainteCompatibilite({
        produit_a: Number(brouillon.produit_a),
        produit_b: Number(brouillon.produit_b),
        type: brouillon.type,
        message_utilisateur: brouillon.message_utilisateur.trim(),
      })
      toast.success('Règle enregistrée.')
      setBrouillon({
        produit_a: '', produit_b: '', type: 'INCOMPATIBLE', message_utilisateur: '',
      })
      charger()
    } catch (err) {
      toast.error(messageErreur(err, "Impossible d'enregistrer cette règle."))
    } finally {
      setOccupe(false)
    }
  }

  async function changerType(regle, type) {
    try {
      await cpqApi.updateContrainteCompatibilite(regle.id, { type })
      charger()
    } catch (err) {
      toast.error(messageErreur(err, 'Modification impossible.'))
    }
  }

  async function supprimer(regle) {
    try {
      await cpqApi.deleteContrainteCompatibilite(regle.id)
      toast.success('Règle supprimée.')
      charger()
    } catch (err) {
      toast.error(messageErreur(err, 'Suppression impossible.'))
    }
  }

  function basculerSelection(id) {
    setSelection((s) => (
      s.includes(id) ? s.filter((x) => x !== id) : [...s, id]
    ))
  }

  async function tester() {
    if (occupe) return
    setOccupe(true)
    try {
      const res = await cpqApi.validerCompatibilite(selection)
      setResultat(res?.data || {})
    } catch (err) {
      toast.error(messageErreur(err, 'Test impossible.'))
    } finally {
      setOccupe(false)
    }
  }

  const bloquantes = Array.isArray(resultat?.bloquantes) ? resultat.bloquantes : []
  const avertissements = Array.isArray(resultat?.avertissements)
    ? resultat.avertissements
    : []

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Compatibilité produits"
        subtitle="Règles entre deux produits (incompatible, requiert, recommandé) et test d'une sélection (NTCPQ1)."
      />

      <Card className="flex flex-col gap-3 p-4 sm:p-5">
        <h3 className="text-sm font-medium text-foreground">Ajouter une règle</h3>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <Select
            value={brouillon.produit_a}
            onValueChange={(v) => setBrouillon((b) => ({ ...b, produit_a: v }))}
          >
            <SelectTrigger className="sm:w-56" aria-label="Produit A">
              <SelectValue placeholder="Produit A" />
            </SelectTrigger>
            <SelectContent>
              {produits.map((p) => (
                <SelectItem key={p.id} value={String(p.id)}>{p.nom}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={brouillon.type}
            onValueChange={(v) => setBrouillon((b) => ({ ...b, type: v }))}
          >
            <SelectTrigger className="sm:w-44" aria-label="Type de règle">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TYPES.map(([valeur, libelle]) => (
                <SelectItem key={valeur} value={valeur}>{libelle}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={brouillon.produit_b}
            onValueChange={(v) => setBrouillon((b) => ({ ...b, produit_b: v }))}
          >
            <SelectTrigger className="sm:w-56" aria-label="Produit B">
              <SelectValue placeholder="Produit B" />
            </SelectTrigger>
            <SelectContent>
              {produits.map((p) => (
                <SelectItem key={p.id} value={String(p.id)}>{p.nom}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <Input
            className="sm:flex-1"
            placeholder="Message affiché à l'utilisateur (optionnel)"
            aria-label="Message utilisateur"
            value={brouillon.message_utilisateur}
            onChange={(e) => setBrouillon((b) => ({ ...b, message_utilisateur: e.target.value }))}
          />
          <Button onClick={creer} disabled={occupe} data-testid="cpq-compat-creer">
            <Plus /> Ajouter la règle
          </Button>
        </div>
      </Card>

      <Card className="flex flex-col gap-3 p-4 sm:p-5">
        <h3 className="text-sm font-medium text-foreground">Grille des règles</h3>
        {chargement && <p className="text-sm text-muted-foreground">Chargement…</p>}
        {!chargement && erreur && <EmptyState title="Erreur" description={erreur} />}
        {!chargement && !erreur && regles.length === 0 && (
          <EmptyState
            title="Aucune règle"
            description="Aucune contrainte de compatibilité n'est encore définie."
          />
        )}
        {!chargement && !erreur && regles.length > 0 && (
          <ul className="flex flex-col gap-2" data-testid="cpq-compat-grille">
            {regles.map((r) => (
              <li
                key={r.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border p-3"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{nomProduit(produits, r.produit_a)}</span>
                  <span className="text-muted-foreground">→</span>
                  <span className="font-medium">{nomProduit(produits, r.produit_b)}</span>
                  {r.bloquante && <Badge tone="danger">Bloquante</Badge>}
                  {r.message_utilisateur && (
                    <span className="text-xs text-muted-foreground">{r.message_utilisateur}</span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Select value={r.type} onValueChange={(v) => changerType(r, v)}>
                    <SelectTrigger
                      className="w-44"
                      aria-label={`Type de la règle ${r.id}`}
                    >
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {TYPES.map(([valeur, libelle]) => (
                        <SelectItem key={valeur} value={valeur}>{libelle}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button variant="ghost" size="sm" onClick={() => supprimer(r)}>
                    <Trash2 /> Supprimer
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="flex flex-col gap-3 p-4 sm:p-5">
        <h3 className="text-sm font-medium text-foreground">Tester une sélection</h3>
        {produits.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Aucun produit au catalogue : rien à tester pour l&apos;instant.
          </p>
        ) : (
          <div className="flex flex-wrap gap-2" data-testid="cpq-compat-selection">
            {produits.map((p) => (
              <Button
                key={p.id}
                type="button"
                size="sm"
                variant={selection.includes(p.id) ? 'default' : 'secondary'}
                aria-pressed={selection.includes(p.id)}
                onClick={() => basculerSelection(p.id)}
              >
                {p.nom}
              </Button>
            ))}
          </div>
        )}
        <div>
          <Button onClick={tester} disabled={occupe} data-testid="cpq-compat-tester">
            <ShieldAlert /> Tester
          </Button>
        </div>

        {resultat && (
          <div className="flex flex-col gap-4" data-testid="cpq-compat-resultat">
            <p className="flex items-center gap-2 text-sm">
              {resultat.valide ? (
                <Badge tone="success">Sélection valide</Badge>
              ) : (
                <Badge tone="danger">
                  <TriangleAlert size={12} aria-hidden="true" /> Sélection invalide
                </Badge>
              )}
            </p>
            <ListeViolations
              titre="Bloquantes"
              ton="danger"
              violations={bloquantes}
              produits={produits}
              testId="cpq-compat-bloquantes"
            />
            <ListeViolations
              titre="Avertissements"
              ton="warning"
              violations={avertissements}
              produits={produits}
              testId="cpq-compat-avertissements"
            />
          </div>
        )}
      </Card>
    </div>
  )
}
