import { useCallback, useEffect, useState } from 'react'
import { Percent, Plus, Trash2 } from 'lucide-react'
import {
  Badge, Button, Card, EmptyState, Input, toast,
  Tabs, TabsList, TabsTrigger, TabsContent,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import PageHeader from '../../components/layout/PageHeader'
import cpqApi from '../../api/cpqApi'
import stockApi from '../../api/stockApi'

/* ============================================================================
   PACT130 — écran « Paramètres CPQ » (`/cpq/parametres`), DEUX onglets.
   ----------------------------------------------------------------------------
   Le regroupement n'est pas arbitraire : les deux ViewSets backend portent
   littéralement le commentaire « pour UN écran Paramètres CPQ, plus de
   dépendance au Django admin » (WIR105). Jusqu'ici ces deux réglages
   n'étaient administrables QUE depuis le Django admin.

     * Onglet « Seuils de marge » — `SeuilMargeFamille` : marge minimale par
       catégorie de produit. DONNÉE INTERNE : elle sert de garde-fou au
       générateur, elle ne doit JAMAIS apparaître dans un PDF ni dans une
       sortie client (même règle que `Produit.prix_achat`). Cet écran est un
       écran de paramétrage interne, gaté responsable/admin.
     * Onglet « Approbation des remises » — `RegleApprobationRemise` : palier
       d'approbation par intervalle de remise. Les bornes sont laissées à la
       validation SERVEUR (min ≤ max) : aucune règle métier dupliquée ici.
   ========================================================================== */

const NIVEAUX = [
  ['responsable', 'Responsable'],
  ['administrateur', 'Administrateur'],
  ['direction', 'Direction'],
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
  if (data && typeof data === 'object') {
    const premier = Object.values(data)[0]
    if (Array.isArray(premier) && typeof premier[0] === 'string') return premier[0]
  }
  return repli
}

function nombreOuNull(valeur) {
  const brut = String(valeur ?? '').trim().replace(',', '.')
  const n = Number(brut)
  return brut === '' || Number.isNaN(n) ? null : n
}

/* -------------------------------------------------------------------------- */
/* Onglet 1 — seuils de marge par famille (NTCPQ6)                             */
/* -------------------------------------------------------------------------- */

function SeuilsTab() {
  const [seuils, setSeuils] = useState([])
  const [categories, setCategories] = useState([])
  const [chargement, setChargement] = useState(true)
  const [erreur, setErreur] = useState('')
  const [categorie, setCategorie] = useState('')
  const [marge, setMarge] = useState('')
  const [occupe, setOccupe] = useState(false)

  const charger = useCallback(async () => {
    setChargement(true)
    try {
      const res = await cpqApi.getSeuilsMarge()
      setSeuils(listeDe(res?.data))
      setErreur('')
    } catch (err) {
      setErreur(messageErreur(err, 'Seuils de marge indisponibles.'))
      setSeuils([])
    } finally {
      setChargement(false)
    }
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { charger() }, [charger])

  useEffect(() => {
    let vivant = true
    stockApi.getCategories({ page_size: 200 })
      .then((res) => { if (vivant) setCategories(listeDe(res?.data)) })
      .catch(() => { if (vivant) setCategories([]) })
    return () => { vivant = false }
  }, [])

  async function creer() {
    if (occupe) return
    const pct = nombreOuNull(marge)
    if (!categorie || pct === null) {
      toast.error('Choisissez une catégorie et une marge minimale.')
      return
    }
    setOccupe(true)
    try {
      await cpqApi.createSeuilMarge({
        categorie: Number(categorie),
        marge_min_pct: pct,
      })
      toast.success('Seuil de marge enregistré.')
      setCategorie('')
      setMarge('')
      charger()
    } catch (err) {
      toast.error(messageErreur(err, "Impossible d'enregistrer ce seuil."))
    } finally {
      setOccupe(false)
    }
  }

  async function supprimer(seuil) {
    try {
      await cpqApi.deleteSeuilMarge(seuil.id)
      toast.success('Seuil supprimé.')
      charger()
    } catch (err) {
      toast.error(messageErreur(err, 'Suppression impossible.'))
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Card className="flex flex-col gap-3 p-4 sm:p-5">
        <h3 className="text-sm font-medium text-foreground">Ajouter un seuil</h3>
        <p className="text-xs text-muted-foreground">
          Garde-fou interne du générateur de devis : jamais imprimé sur un
          document client.
        </p>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <Select value={categorie} onValueChange={setCategorie}>
            <SelectTrigger className="sm:w-64" aria-label="Catégorie">
              <SelectValue placeholder="Catégorie de produit" />
            </SelectTrigger>
            <SelectContent>
              {categories.map((c) => (
                <SelectItem key={c.id} value={String(c.id)}>{c.nom}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            className="sm:w-48"
            inputMode="decimal"
            step="any"
            placeholder="Marge minimale (%)"
            aria-label="Marge minimale"
            value={marge}
            onChange={(e) => setMarge(e.target.value)}
          />
          <Button onClick={creer} disabled={occupe} data-testid="cpq-seuil-creer">
            <Plus /> Ajouter
          </Button>
        </div>
      </Card>

      {chargement && <p className="text-sm text-muted-foreground">Chargement…</p>}
      {!chargement && erreur && <EmptyState title="Erreur" description={erreur} />}
      {!chargement && !erreur && seuils.length === 0 && (
        <EmptyState
          title="Aucun seuil de marge"
          description="Aucune famille de produits n'a encore de marge plancher."
        />
      )}
      {!chargement && !erreur && seuils.length > 0 && (
        <ul className="flex flex-col gap-2" data-testid="cpq-seuil-liste">
          {seuils.map((s) => (
            <li
              key={s.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border p-3"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{s.categorie_nom || `Catégorie #${s.categorie}`}</span>
                <Badge tone="info">{s.marge_min_pct} % mini</Badge>
              </div>
              <Button variant="ghost" size="sm" onClick={() => supprimer(s)}>
                <Trash2 /> Supprimer
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Onglet 2 — paliers d'approbation de remise (NTCPQ7/8)                       */
/* -------------------------------------------------------------------------- */

const NOUVELLE_REGLE = {
  libelle: '', remise_min_pct: '', remise_max_pct: '',
  niveau_approbation: 'responsable', nombre_approbateurs: '1', priorite: '0',
}

function ApprobationsTab() {
  const [regles, setRegles] = useState([])
  const [chargement, setChargement] = useState(true)
  const [erreur, setErreur] = useState('')
  const [brouillon, setBrouillon] = useState(NOUVELLE_REGLE)
  const [occupe, setOccupe] = useState(false)

  const charger = useCallback(async () => {
    setChargement(true)
    try {
      const res = await cpqApi.getReglesApprobationRemise()
      setRegles(listeDe(res?.data))
      setErreur('')
    } catch (err) {
      setErreur(messageErreur(err, "Paliers d'approbation indisponibles."))
      setRegles([])
    } finally {
      setChargement(false)
    }
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { charger() }, [charger])

  async function creer() {
    if (occupe) return
    const min = nombreOuNull(brouillon.remise_min_pct)
    const max = nombreOuNull(brouillon.remise_max_pct)
    if (min === null && max === null) {
      toast.error('Renseignez au moins une borne de remise.')
      return
    }
    const nb = nombreOuNull(brouillon.nombre_approbateurs)
    const prio = nombreOuNull(brouillon.priorite)
    setOccupe(true)
    try {
      await cpqApi.createRegleApprobationRemise({
        libelle: brouillon.libelle.trim(),
        remise_min_pct: min,
        remise_max_pct: max,
        niveau_approbation: brouillon.niveau_approbation,
        nombre_approbateurs: nb === null ? 1 : nb,
        priorite: prio === null ? 0 : prio,
        actif: true,
      })
      toast.success('Palier enregistré.')
      setBrouillon(NOUVELLE_REGLE)
      charger()
    } catch (err) {
      // Les bornes incohérentes (min > max) sont refusées par le SERVEUR :
      // on remonte son message tel quel plutôt que d'en dupliquer la règle.
      toast.error(messageErreur(err, "Impossible d'enregistrer ce palier."))
    } finally {
      setOccupe(false)
    }
  }

  async function basculerActif(regle) {
    try {
      await cpqApi.updateRegleApprobationRemise(regle.id, { actif: !regle.actif })
      charger()
    } catch (err) {
      toast.error(messageErreur(err, 'Modification impossible.'))
    }
  }

  async function supprimer(regle) {
    try {
      await cpqApi.deleteRegleApprobationRemise(regle.id)
      toast.success('Palier supprimé.')
      charger()
    } catch (err) {
      toast.error(messageErreur(err, 'Suppression impossible.'))
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Card className="flex flex-col gap-3 p-4 sm:p-5">
        <h3 className="text-sm font-medium text-foreground">Ajouter un palier</h3>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <Input
            className="sm:flex-1"
            placeholder="Libellé (optionnel)"
            aria-label="Libellé du palier"
            value={brouillon.libelle}
            onChange={(e) => setBrouillon((b) => ({ ...b, libelle: e.target.value }))}
          />
          <Input
            className="sm:w-32"
            inputMode="decimal"
            step="any"
            placeholder="Remise min %"
            aria-label="Remise minimale"
            value={brouillon.remise_min_pct}
            onChange={(e) => setBrouillon((b) => ({ ...b, remise_min_pct: e.target.value }))}
          />
          <Input
            className="sm:w-32"
            inputMode="decimal"
            step="any"
            placeholder="Remise max %"
            aria-label="Remise maximale"
            value={brouillon.remise_max_pct}
            onChange={(e) => setBrouillon((b) => ({ ...b, remise_max_pct: e.target.value }))}
          />
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <Select
            value={brouillon.niveau_approbation}
            onValueChange={(v) => setBrouillon((b) => ({ ...b, niveau_approbation: v }))}
          >
            <SelectTrigger className="sm:w-56" aria-label="Niveau d'approbation">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {NIVEAUX.map(([valeur, libelle]) => (
                <SelectItem key={valeur} value={valeur}>{libelle}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            className="sm:w-40"
            inputMode="numeric"
            step="any"
            placeholder="Approbateurs"
            aria-label="Nombre d'approbateurs"
            value={brouillon.nombre_approbateurs}
            onChange={(e) => setBrouillon((b) => ({ ...b, nombre_approbateurs: e.target.value }))}
          />
          <Input
            className="sm:w-32"
            inputMode="numeric"
            step="any"
            placeholder="Priorité"
            aria-label="Priorité"
            value={brouillon.priorite}
            onChange={(e) => setBrouillon((b) => ({ ...b, priorite: e.target.value }))}
          />
          <Button onClick={creer} disabled={occupe} data-testid="cpq-palier-creer">
            <Plus /> Ajouter
          </Button>
        </div>
      </Card>

      {chargement && <p className="text-sm text-muted-foreground">Chargement…</p>}
      {!chargement && erreur && <EmptyState title="Erreur" description={erreur} />}
      {!chargement && !erreur && regles.length === 0 && (
        <EmptyState
          title="Aucun palier d'approbation"
          description="Aucune profondeur de remise n'exige encore d'approbation."
        />
      )}
      {!chargement && !erreur && regles.length > 0 && (
        <ul className="flex flex-col gap-2" data-testid="cpq-palier-liste">
          {regles.map((r) => (
            <li
              key={r.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border p-3"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{r.libelle || `Palier #${r.id}`}</span>
                <Badge tone="neutral">
                  {r.remise_min_pct ?? '—'} % → {r.remise_max_pct ?? '—'} %
                </Badge>
                <Badge tone="info">
                  {r.niveau_approbation_display || r.niveau_approbation}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {r.nombre_approbateurs} approbateur(s) · priorité {r.priorite}
                </span>
                {!r.actif && <Badge tone="warning">Inactif</Badge>}
              </div>
              <div className="flex items-center gap-2">
                <Button variant="secondary" size="sm" onClick={() => basculerActif(r)}>
                  {r.actif ? 'Désactiver' : 'Activer'}
                </Button>
                <Button variant="ghost" size="sm" onClick={() => supprimer(r)}>
                  <Trash2 /> Supprimer
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function ParametresCpqPage() {
  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Paramètres CPQ"
        subtitle="Seuils de marge par famille et paliers d'approbation de remise — plus aucun passage par le Django admin."
        actions={<Percent size={18} strokeWidth={1.75} aria-hidden="true" />}
      />
      <Tabs defaultValue="seuils">
        <TabsList>
          <TabsTrigger value="seuils">Seuils de marge</TabsTrigger>
          <TabsTrigger value="approbations">Approbation des remises</TabsTrigger>
        </TabsList>
        <TabsContent value="seuils">
          <SeuilsTab />
        </TabsContent>
        <TabsContent value="approbations">
          <ApprobationsTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}
