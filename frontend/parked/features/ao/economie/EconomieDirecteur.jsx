import { useCallback, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  Download, Lock, LockOpen, Trash2, Wallet,
} from 'lucide-react'
import aoApi, { aoRentabiliteApi } from '../../../api/aoApi'
import useResource from '../../../hooks/useResource'
import useVisibilityAwarePolling from '../../../hooks/useVisibilityAwarePolling'
import { unwrapList } from '../../../api/resource'
import {
  Badge, Button, Card, CardHeader, CardTitle, CardContent, Input, Label, Select,
  SelectTrigger, SelectValue, SelectContent, SelectItem, Textarea,
  EmptyState, Skeleton, toast,
} from '../../../ui'
import PageHeader from '../../../components/layout/PageHeader'
import { formatMAD } from '../../../lib/format'
import { getApiError } from '../../../lib/apiError'

/* ============================================================================
   PACT75 — Économie DIRECTEUR de l'AO : coût de revient et cibles de marge.
   ----------------------------------------------------------------------------
   Le client de rentabilité (`aoRentabiliteApi`) était déjà câblé au bon
   endpoint (AOF161) mais consommé par AUCUN écran : les routes
   `/ao/rentabilite` et `/ao/:id/rentabilite` rendaient un squelette « pas
   encore construit ». Sans fiche Économie, ses deux enfants n'en avaient pas
   non plus — `LigneCoutRevient` (poste, quantité, prix unitaire, régime TVA
   10 %/20 %) et `CibleFinanciere` (bénéfice net visé, VERSIONNÉE avec auteur
   et motif, seuils psychologiques).

   **RÈGLE #4 / en-tête du Groupe AOF : L'ÉCONOMIE EST RÉSERVÉE AU DIRECTEUR.**
   Ce fichier n'importe QUE `aoRentabiliteApi` (export SÉPARÉ, jamais mêlé à
   `aoApi`) — aucune donnée de marge ne traverse une vue non gardée. Les DEUX
   routes qui montent cet écran (`/ao/rentabilite`, `/ao/:id/rentabilite`)
   portent déjà `roles: ['admin']` + `perm: 'ao_rentabilite_voir'`
   (`module.config.jsx`, INCHANGÉ ici) — jamais mêlées aux vues AO générales,
   jamais client-facing.

   **AUCUN AGRÉGAT N'EST DÉRIVÉ ICI** (AOF94) : coût de revient, TVA nette à
   reverser, marge, contrôle de trésorerie viennent TOUS de
   `EconomieAOSerializer`, lus tels quels.

   Le VERROU de l'économie (`verrouillee`) désactive la création/suppression
   des lignes ET des cibles — une cascade de prix déjà propagée ne se modifie
   pas sous les pièces qui la citent (refusé côté serveur de toute façon,
   `_refuser_si_verrouillee`) ; l'écran le dit AVANT l'appel, pas après le 403.
   ========================================================================== */

const errMsg = (e, fallback) => getApiError(e, fallback).message

const POSTES = [
  ['panneaux', 'Panneaux'],
  ['structure', 'Structure'],
  ['onduleurs', 'Onduleurs et équipements'],
  ['garantie_onduleurs', 'Extension de garantie onduleurs'],
  ['cable_solaire', 'Câble solaire'],
  ['cable_ac', 'Câble AC'],
  ['main_oeuvre', "Main d'œuvre"],
  ['aleas', 'Aléas'],
  ['autre', 'Autre poste'],
]
const REGIMES_TVA = [
  ['reduit', 'Réduit (panneaux, 10 %)'],
  ['standard', 'Standard (20 %)'],
]

function Champ({ id, label, children }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
    </div>
  )
}

function Metrique({ label, value, fort = false }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={`tabular-nums ${fort ? 'font-display text-lg font-semibold' : 'text-sm font-medium'}`}>
        {value != null ? formatMAD(value) : '—'}
      </dd>
    </div>
  )
}

function SyntheseCard({ economie }) {
  return (
    <Card className="p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h2 className="font-display text-base font-semibold">Synthèse</h2>
        {economie.sous_seuil_psychologique === false && (
          <Badge tone="danger">au-dessus du seuil psychologique</Badge>
        )}
        {economie.verrouillee && <Badge tone="warning">Verrouillée</Badge>}
      </div>
      <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Metrique label="Coût de revient HT" value={economie.cout_revient_ht} />
        <Metrique label="TVA déductible" value={economie.tva_deductible} />
        <Metrique label="Bénéfice net cible HT" value={economie.benefice_net_cible_ht} />
        <Metrique label="Total HT" value={economie.total_ht} fort />
        <Metrique label="TVA collectée" value={economie.tva_collectee} />
        <Metrique label="Total TTC" value={economie.total_ttc} fort />
        <Metrique label="TVA nette à reverser" value={economie.tva_nette_a_reverser} />
        <div>
          <dt className="text-xs text-muted-foreground">Marge</dt>
          <dd className="text-sm font-medium tabular-nums">
            {economie.marge_pct != null ? `${economie.marge_pct} %` : '—'}
          </dd>
        </div>
        <Metrique label="Contrôle de trésorerie" value={economie.controle_tresorerie} />
        <Metrique label="Écart de trésorerie" value={economie.ecart_tresorerie} />
      </dl>
    </Card>
  )
}

function LigneCoutForm({ economieId, onCree, disabled }) {
  const [form, setForm] = useState({
    poste: 'autre', designation: '', quantite: '1', unite: 'U', prix_unitaire_ht: '', regime_tva: 'standard',
  })
  const [envoi, setEnvoi] = useState(false)
  const set = (champ) => (e) => setForm((p) => ({ ...p, [champ]: e.target.value }))

  const soumettre = async (e) => {
    e.preventDefault()
    if (!form.designation.trim()) return
    setEnvoi(true)
    try {
      await aoRentabiliteApi.lignesCoutRevient.create({
        economie: economieId,
        poste: form.poste,
        designation: form.designation.trim(),
        quantite: form.quantite === '' ? '1' : form.quantite,
        unite: form.unite || 'U',
        prix_unitaire_ht: form.prix_unitaire_ht === '' ? '0' : form.prix_unitaire_ht,
        regime_tva: form.regime_tva,
      })
      setForm({ poste: 'autre', designation: '', quantite: '1', unite: 'U', prix_unitaire_ht: '', regime_tva: 'standard' })
      onCree()
    } catch (e2) {
      toast.error(errMsg(e2, 'Poste non enregistré.'))
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <form onSubmit={soumettre} noValidate className="grid gap-3 sm:grid-cols-3">
      <Champ id="ao-eco-poste" label="Poste">
        <Select value={form.poste} onValueChange={(v) => setForm((p) => ({ ...p, poste: v }))} disabled={disabled}>
          <SelectTrigger id="ao-eco-poste"><SelectValue /></SelectTrigger>
          <SelectContent>{POSTES.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
        </Select>
      </Champ>
      <Champ id="ao-eco-designation" label="Désignation">
        <Input id="ao-eco-designation" value={form.designation} onChange={set('designation')} disabled={disabled} />
      </Champ>
      <Champ id="ao-eco-quantite" label="Quantité">
        <Input id="ao-eco-quantite" type="number" step="any" value={form.quantite} onChange={set('quantite')} disabled={disabled} />
      </Champ>
      <Champ id="ao-eco-unite" label="Unité">
        <Input id="ao-eco-unite" value={form.unite} onChange={set('unite')} disabled={disabled} />
      </Champ>
      <Champ id="ao-eco-prix" label="Coût unitaire HT (MAD)">
        <Input id="ao-eco-prix" type="number" step="any" value={form.prix_unitaire_ht} onChange={set('prix_unitaire_ht')} disabled={disabled} />
      </Champ>
      <Champ id="ao-eco-regime" label="Régime de TVA sur achat">
        <Select value={form.regime_tva} onValueChange={(v) => setForm((p) => ({ ...p, regime_tva: v }))} disabled={disabled}>
          <SelectTrigger id="ao-eco-regime"><SelectValue /></SelectTrigger>
          <SelectContent>{REGIMES_TVA.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
        </Select>
      </Champ>
      <div className="flex items-end">
        <Button type="submit" disabled={disabled || envoi || !form.designation.trim()}>
          {envoi ? 'Enregistrement…' : 'Ajouter le poste'}
        </Button>
      </div>
    </form>
  )
}

function LignesCoutSection({ economieId, verrouillee }) {
  const params = { economie: economieId }
  const { data: lignes, loading, error, refetch } = useResource(
    () => aoRentabiliteApi.lignesCoutRevient.list(params), JSON.stringify(params),
    { initialData: [], select: unwrapList, errorMessage: 'Impossible de charger les postes de coût.' },
  )

  const supprimer = async (ligne) => {
    try {
      await aoRentabiliteApi.lignesCoutRevient.remove(ligne.id)
      refetch()
    } catch (e) {
      toast.error(errMsg(e, 'Suppression refusée.'))
    }
  }

  return (
    <Card>
      <CardHeader><CardTitle>Coût de revient — postes</CardTitle></CardHeader>
      <CardContent className="flex flex-col gap-4">
        {verrouillee && (
          <p className="text-xs text-warning">
            Économie verrouillée : aucun poste ne peut être ajouté ni supprimé.
          </p>
        )}
        <LigneCoutForm economieId={economieId} onCree={refetch} disabled={verrouillee} />
        {loading && <Skeleton className="h-24 w-full" />}
        {error && <p className="text-sm text-destructive">{error}</p>}
        {!loading && !error && (
          lignes.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucun poste de coût enregistré.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[40rem] text-left text-sm">
                <thead className="text-xs text-muted-foreground">
                  <tr className="border-b border-border">
                    <th scope="col" className="px-2 py-1.5 font-medium">Poste</th>
                    <th scope="col" className="px-2 py-1.5 font-medium">Désignation</th>
                    <th scope="col" className="px-2 py-1.5 text-right font-medium">Quantité</th>
                    <th scope="col" className="px-2 py-1.5 text-right font-medium">PU HT</th>
                    <th scope="col" className="px-2 py-1.5 text-right font-medium">Montant HT</th>
                    <th scope="col" className="px-2 py-1.5 font-medium">TVA</th>
                    <th scope="col" className="px-2 py-1.5" />
                  </tr>
                </thead>
                <tbody>
                  {lignes.map((l) => (
                    <tr key={l.id} className="border-b border-border last:border-b-0">
                      <td className="px-2 py-1.5">{l.poste_display}</td>
                      <td className="px-2 py-1.5">{l.designation}</td>
                      <td className="px-2 py-1.5 text-right tabular-nums">{l.quantite} {l.unite}</td>
                      <td className="px-2 py-1.5 text-right tabular-nums">{formatMAD(l.prix_unitaire_ht)}</td>
                      <td className="px-2 py-1.5 text-right font-medium tabular-nums">{formatMAD(l.montant_ht)}</td>
                      <td className="px-2 py-1.5">{l.regime_tva_display}</td>
                      <td className="px-2 py-1.5 text-right">
                        <Button
                          size="icon-sm" variant="ghost" disabled={verrouillee}
                          aria-label={`Supprimer « ${l.designation} »`}
                          onClick={() => supprimer(l)}
                        >
                          <Trash2 aria-hidden="true" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}
      </CardContent>
    </Card>
  )
}

function CibleForm({ economieId, onCree, disabled }) {
  const [form, setForm] = useState({
    benefice_net_cible_ht: '', arrondi_psychologique: '0', seuil_psychologique: '', motif: '',
  })
  const [envoi, setEnvoi] = useState(false)
  const set = (champ) => (e) => setForm((p) => ({ ...p, [champ]: e.target.value }))

  const soumettre = async (e) => {
    e.preventDefault()
    if (!form.motif.trim()) return
    setEnvoi(true)
    try {
      const payload = {
        economie: economieId,
        benefice_net_cible_ht: form.benefice_net_cible_ht === '' ? '0' : form.benefice_net_cible_ht,
        arrondi_psychologique: form.arrondi_psychologique === '' ? '0' : form.arrondi_psychologique,
        motif: form.motif.trim(),
      }
      if (form.seuil_psychologique !== '') payload.seuil_psychologique = form.seuil_psychologique
      await aoRentabiliteApi.ciblesFinancieres.create(payload)
      toast.success('Nouvelle version de cible enregistrée.')
      setForm({ benefice_net_cible_ht: '', arrondi_psychologique: '0', seuil_psychologique: '', motif: '' })
      onCree()
    } catch (e2) {
      toast.error(errMsg(e2, 'Cible non enregistrée.'))
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <form onSubmit={soumettre} noValidate className="grid gap-3 sm:grid-cols-3">
      <Champ id="ao-cible-benefice" label="Bénéfice net visé HT (MAD)">
        <Input id="ao-cible-benefice" type="number" step="any" value={form.benefice_net_cible_ht} onChange={set('benefice_net_cible_ht')} disabled={disabled} />
      </Champ>
      <Champ id="ao-cible-arrondi" label="Pas d'arrondi des prix unitaires (MAD)">
        <Input id="ao-cible-arrondi" type="number" step="any" value={form.arrondi_psychologique} onChange={set('arrondi_psychologique')} disabled={disabled} />
      </Champ>
      <Champ id="ao-cible-seuil" label="Seuil psychologique TTC (MAD)">
        <Input id="ao-cible-seuil" type="number" step="any" value={form.seuil_psychologique} onChange={set('seuil_psychologique')} disabled={disabled} />
      </Champ>
      <div className="flex flex-col gap-1.5 sm:col-span-3">
        <Label htmlFor="ao-cible-motif">Motif de la version (obligatoire)</Label>
        <Textarea id="ao-cible-motif" rows={2} value={form.motif} onChange={set('motif')} disabled={disabled} />
      </div>
      <div className="flex items-end">
        <Button type="submit" disabled={disabled || envoi || !form.motif.trim()}>
          {envoi ? 'Enregistrement…' : 'Verser une nouvelle version'}
        </Button>
      </div>
    </form>
  )
}

function CiblesSection({ economieId, verrouillee }) {
  const params = { economie: economieId }
  const { data: cibles, loading, error, refetch } = useResource(
    () => aoRentabiliteApi.ciblesFinancieres.list(params), JSON.stringify(params),
    { initialData: [], select: unwrapList, errorMessage: 'Impossible de charger les cibles financières.' },
  )
  const active = cibles.find((c) => c.active) || null

  return (
    <Card>
      <CardHeader><CardTitle>Cibles financières — historique versionné</CardTitle></CardHeader>
      <CardContent className="flex flex-col gap-4">
        {active && (
          <p className="text-sm">
            Cible active : <strong className="tabular-nums">{formatMAD(active.benefice_net_cible_ht)}</strong>
            {' '}(v{active.version}{active.auteur_nom ? ` — ${active.auteur_nom}` : ''})
          </p>
        )}
        {verrouillee && (
          <p className="text-xs text-warning">Économie verrouillée : aucune nouvelle version ne peut être versée.</p>
        )}
        <CibleForm economieId={economieId} onCree={refetch} disabled={verrouillee} />
        {loading && <Skeleton className="h-20 w-full" />}
        {error && <p className="text-sm text-destructive">{error}</p>}
        {!loading && !error && cibles.length > 0 && (
          <ul className="flex flex-col gap-1.5">
            {cibles.map((c) => (
              <li key={c.id} className="flex flex-wrap items-center gap-2 rounded-md border border-border p-2 text-xs">
                <Badge tone={c.active ? 'success' : 'neutral'}>v{c.version}</Badge>
                <span className="tabular-nums">{formatMAD(c.benefice_net_cible_ht)}</span>
                <span className="text-muted-foreground">{c.auteur_nom || 'auteur inconnu'}</span>
                <span className="ml-auto text-muted-foreground">{c.motif}</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

const JOB_ACTIFS = new Set(['queued', 'running', 'en_file', 'en_cours'])

function ClasseurSection({ economieId }) {
  const [jobId, setJobId] = useState(null)
  const [etat, setEtat] = useState(null)
  const [lancement, setLancement] = useState(false)

  const sonder = useCallback(async () => {
    if (!jobId) return
    try {
      const res = await aoRentabiliteApi.statutClasseur(economieId, jobId)
      setEtat(res?.data ?? null)
    } catch {
      setEtat((p) => ({ ...p, detail: 'Suivi de la production interrompu.' }))
    }
  }, [economieId, jobId])

  useVisibilityAwarePolling(
    useMemo(() => [{ fn: sonder, intervalMs: 3000 }], [sonder]),
    { enabled: Boolean(jobId) && JOB_ACTIFS.has(etat?.statut) },
  )

  const produire = async () => {
    setLancement(true)
    try {
      const res = await aoRentabiliteApi.produireClasseur(economieId)
      setJobId(res?.data?.job ?? null)
      setEtat(res?.data ?? null)
    } catch (e) {
      toast.error(errMsg(e, 'Production du classeur impossible.'))
    } finally {
      setLancement(false)
    }
  }

  const telecharger = async () => {
    try {
      const res = await aoRentabiliteApi.download(economieId, jobId)
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = 'rentabilite.xlsx'
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      toast.error(errMsg(e, 'Téléchargement impossible.'))
    }
  }

  return (
    <Card className="flex flex-col gap-2 p-4">
      <h2 className="font-display text-base font-semibold">Classeur interne</h2>
      <p className="text-xs text-muted-foreground">
        Produit en tâche de fond — jamais un rendu synchrone. Réservé au directeur, jamais client-facing.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" onClick={produire} disabled={lancement || JOB_ACTIFS.has(etat?.statut)}>
          {lancement || JOB_ACTIFS.has(etat?.statut) ? 'Production…' : 'Produire le classeur'}
        </Button>
        {etat?.pret && (
          <Button size="sm" variant="outline" onClick={telecharger}>
            <Download className="size-3.5" aria-hidden="true" />
            Télécharger
          </Button>
        )}
        {etat?.message_erreur && <span className="text-xs text-destructive">{etat.message_erreur}</span>}
      </div>
    </Card>
  )
}

function AffaireSelector({ affaires, valeur, onChange }) {
  return (
    <Champ id="ao-eco-affaire" label="Affaire">
      <Select value={valeur} onValueChange={onChange}>
        <SelectTrigger id="ao-eco-affaire"><SelectValue placeholder="Choisir une affaire…" /></SelectTrigger>
        <SelectContent>
          {affaires.map((a) => (
            <SelectItem key={a.id} value={String(a.id)}>{a.reference || `#${a.id}`} — {a.objet}</SelectItem>
          ))}
        </SelectContent>
      </Select>
    </Champ>
  )
}

export default function EconomieDirecteur() {
  const routeParams = useParams()
  const [affaireChoisie, setAffaireChoisie] = useState('')
  const affaireId = routeParams.id ?? (affaireChoisie || null)
  const surRouteAffaire = Boolean(routeParams.id)

  const { data: affaires } = useResource(
    () => aoApi.affaires.list(), undefined,
    {
      initialData: [], select: unwrapList, errorMessage: 'Impossible de charger les affaires.',
      enabled: !surRouteAffaire,
    },
  )

  const { data: economies, loading, error, refetch } = useResource(
    () => aoRentabiliteApi.parAffaire(affaireId), affaireId,
    {
      initialData: [], select: unwrapList,
      errorMessage: 'Impossible de charger l’économie de cette affaire.',
      enabled: Boolean(affaireId),
    },
  )
  const economie = economies[0] || null

  const [creation, setCreation] = useState(false)
  const creerEconomie = async () => {
    setCreation(true)
    try {
      await aoRentabiliteApi.creer(affaireId)
      toast.success('Économie créée pour cette affaire.')
      refetch()
    } catch (e) {
      toast.error(errMsg(e, 'Création impossible.'))
    } finally {
      setCreation(false)
    }
  }

  const basculerVerrou = async () => {
    try {
      if (economie.verrouillee) await aoRentabiliteApi.deverrouiller(economie.id)
      else await aoRentabiliteApi.verrouiller(economie.id)
      refetch()
    } catch (e) {
      toast.error(errMsg(e, 'Verrou non modifié.'))
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Économie directeur"
        subtitle="Coût de revient et cibles de marge — réservé au directeur, jamais client-facing."
      />

      {!surRouteAffaire && (
        <Card className="p-4">
          <AffaireSelector affaires={affaires} valeur={affaireChoisie} onChange={setAffaireChoisie} />
        </Card>
      )}

      {!affaireId ? (
        <EmptyState icon={Wallet} title="Choisissez une affaire" description="L’économie se consulte affaire par affaire." />
      ) : loading ? (
        <div className="flex flex-col gap-3"><Skeleton className="h-8 w-64" /><Skeleton className="h-40 w-full" /></div>
      ) : error ? (
        <EmptyState icon={Wallet} tone="error" title="Économie indisponible" description={error} />
      ) : !economie ? (
        <EmptyState
          icon={Wallet}
          title="Aucune économie pour cette affaire"
          description="Rien n’a encore été chiffré."
          action={<Button onClick={creerEconomie} disabled={creation}>{creation ? 'Création…' : 'Créer l’économie'}</Button>}
        />
      ) : (
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-end">
            <Button size="sm" variant="outline" onClick={basculerVerrou}>
              {economie.verrouillee ? <LockOpen className="size-3.5" aria-hidden="true" /> : <Lock className="size-3.5" aria-hidden="true" />}
              {economie.verrouillee ? 'Déverrouiller' : 'Verrouiller'}
            </Button>
          </div>
          <SyntheseCard economie={economie} />
          <LignesCoutSection economieId={economie.id} verrouillee={economie.verrouillee} />
          <CiblesSection economieId={economie.id} verrouillee={economie.verrouillee} />
          <ClasseurSection economieId={economie.id} />
        </div>
      )}
    </div>
  )
}
