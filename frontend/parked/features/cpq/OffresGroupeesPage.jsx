import { useCallback, useEffect, useState } from 'react'
import { Package, Plus, Trash2 } from 'lucide-react'
import {
  Badge, Button, Card, Checkbox, EmptyState, Input, toast,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import PageHeader from '../../components/layout/PageHeader'
import cpqApi from '../../api/cpqApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import useBulkEditCible from '../core/useBulkEditCible'

/* ============================================================================
   PACT127 — écran « Offres groupées » (`/cpq/offres-groupees`).
   ----------------------------------------------------------------------------
   Le bundle NTCPQ3 existait sans écran : prix total optionnel réparti au
   prorata, lignes en mode FIXE / REMISE_PCT / PRIX_COMPOSANT, et une action
   serveur qui INSÈRE les lignes dans un devis existant. Cet écran compose un
   ensemble avec ses lignes puis l'applique à un devis — c'est le serveur qui
   valorise (`services.appliquer_offre_groupee`), l'écran n'a AUCUNE copie de
   la règle de prix.

   Aucun prix d'achat / aucune marge n'est affiché ici (règle du repo :
   `Produit.prix_achat` ne sort jamais vers un écran client-facing).
   ========================================================================== */

const MODES = [
  ['FIXE', 'Prix fixe (bundle)'],
  ['REMISE_PCT', 'Remise %'],
  ['PRIX_COMPOSANT', 'Prix composant imposé'],
]

const LIBELLE_MODE = Object.fromEntries(MODES)

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

function ligneVide() {
  return { produit: '', quantite: '1', mode_prix: 'FIXE', valeur: '' }
}

/* Corps `lignes` du sérialiseur imbriqué : une ligne sans produit est ignorée
   (jamais un 400 pour une ligne restée vide dans le formulaire). `valeur` part
   à `null` quand elle est vide — le champ est nullable côté modèle. */
function lignesPayload(lignes) {
  return lignes
    .filter((l) => String(l.produit || '').trim() !== '')
    .map((l) => {
      const qte = Number(String(l.quantite || '').replace(',', '.'))
      const val = String(l.valeur || '').trim().replace(',', '.')
      const valeurNum = Number(val)
      return {
        produit: Number(l.produit),
        quantite: Number.isFinite(qte) && qte > 0 ? qte : 1,
        mode_prix: l.mode_prix,
        valeur: val === '' || Number.isNaN(valeurNum) ? null : valeurNum,
      }
    })
}

export default function OffresGroupeesPage() {
  const [offres, setOffres] = useState([])
  const [produits, setProduits] = useState([])
  const [devis, setDevis] = useState([])
  const [chargement, setChargement] = useState(true)
  const [erreur, setErreur] = useState('')
  const [nom, setNom] = useState('')
  const [prixTotal, setPrixTotal] = useState('')
  const [lignes, setLignes] = useState([ligneVide()])
  const [devisCible, setDevisCible] = useState({})
  const [occupe, setOccupe] = useState(false)
  // PACT118 — cette liste n'a PAS d'endpoint de mise à jour en masse propre :
  // elle consomme le registre GÉNÉRIQUE du socle (`core.bulk_edit`), dont les
  // cibles sont déclarées par `apps/cpq/bulk_targets.py`. Si la cible n'est
  // pas enregistrée, `disponible` est faux et aucune action n'est affichée.
  const masse = useBulkEditCible('cpq.offre-groupee')
  const [selectionMasse, setSelectionMasse] = useState([])

  const charger = useCallback(async () => {
    setChargement(true)
    try {
      const res = await cpqApi.getOffresGroupees()
      setOffres(listeDe(res?.data))
      setErreur('')
    } catch (err) {
      setErreur(messageErreur(err, 'Offres groupées indisponibles.'))
      setOffres([])
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
    ventesApi.getDevis({ page_size: 100 })
      .then((res) => { if (vivant) setDevis(listeDe(res?.data)) })
      .catch(() => { if (vivant) setDevis([]) })
    return () => { vivant = false }
  }, [])

  function majLigne(index, champ, valeur) {
    setLignes((ls) => ls.map((l, i) => (i === index ? { ...l, [champ]: valeur } : l)))
  }

  async function creer() {
    if (occupe) return
    const titre = nom.trim()
    if (!titre) {
      toast.error("Le nom de l'offre est obligatoire.")
      return
    }
    const payloadLignes = lignesPayload(lignes)
    if (payloadLignes.length === 0) {
      toast.error('Ajoutez au moins une ligne avec un produit.')
      return
    }
    const total = String(prixTotal).trim().replace(',', '.')
    const totalNum = Number(total)
    setOccupe(true)
    try {
      await cpqApi.createOffreGroupee({
        nom: titre,
        prix_total: total === '' || Number.isNaN(totalNum) ? null : totalNum,
        actif: true,
        lignes: payloadLignes,
      })
      toast.success(`Offre « ${titre} » créée (${payloadLignes.length} ligne(s)).`)
      setNom('')
      setPrixTotal('')
      setLignes([ligneVide()])
      charger()
    } catch (err) {
      toast.error(messageErreur(err, "Impossible de créer cette offre."))
    } finally {
      setOccupe(false)
    }
  }

  async function appliquer(offre) {
    const devisId = devisCible[offre.id]
    if (!devisId || occupe) return
    setOccupe(true)
    try {
      const res = await cpqApi.appliquerOffreGroupee(offre.id, devisId)
      const data = res?.data || {}
      const nb = Array.isArray(data.lignes_creees) ? data.lignes_creees.length : 0
      toast.success(data.detail || `Offre appliquée (${nb} ligne(s) ajoutée(s)).`)
    } catch (err) {
      toast.error(messageErreur(err, "Application au devis impossible."))
    } finally {
      setOccupe(false)
    }
  }

  function basculerMasse(id) {
    setSelectionMasse((s) => (
      s.includes(id) ? s.filter((x) => x !== id) : [...s, id]
    ))
  }

  async function appliquerMasse(actif) {
    if (selectionMasse.length === 0) return
    try {
      const n = await masse.appliquer(selectionMasse, { actif })
      toast.success(`${n} offre(s) modifiée(s).`)
      setSelectionMasse([])
      charger()
    } catch (err) {
      toast.error(messageErreur(err, 'Modification en masse impossible.'))
    }
  }

  async function supprimer(offre) {
    try {
      await cpqApi.deleteOffreGroupee(offre.id)
      toast.success('Offre supprimée.')
      charger()
    } catch (err) {
      toast.error(messageErreur(err, 'Suppression impossible.'))
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Offres groupées"
        subtitle="Bundles produit à prix cascadé (NTCPQ3) : composez un ensemble puis appliquez-le à un devis existant."
      />

      <Card className="flex flex-col gap-3 p-4 sm:p-5">
        <h3 className="text-sm font-medium text-foreground">Nouvelle offre groupée</h3>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <Input
            className="sm:flex-1"
            placeholder="Nom de l'offre (ex. Pack autoconsommation 6 kWc)"
            aria-label="Nom de l'offre"
            value={nom}
            onChange={(e) => setNom(e.target.value)}
          />
          <Input
            className="sm:w-56"
            inputMode="decimal"
            step="any"
            placeholder="Prix total du bundle (optionnel)"
            aria-label="Prix total du bundle"
            value={prixTotal}
            onChange={(e) => setPrixTotal(e.target.value)}
          />
        </div>

        <div className="flex flex-col gap-2" data-testid="cpq-offre-lignes">
          {lignes.map((l, i) => (
            <div
              key={i}
              className="flex flex-col gap-2 rounded-md border border-border p-3 sm:flex-row sm:items-center"
            >
              <Select
                value={l.produit}
                onValueChange={(v) => majLigne(i, 'produit', v)}
              >
                <SelectTrigger className="sm:flex-1" aria-label={`Produit de la ligne ${i + 1}`}>
                  <SelectValue placeholder="Produit" />
                </SelectTrigger>
                <SelectContent>
                  {produits.map((p) => (
                    <SelectItem key={p.id} value={String(p.id)}>{p.nom}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Input
                className="sm:w-24"
                inputMode="decimal"
                step="any"
                aria-label={`Quantité de la ligne ${i + 1}`}
                value={l.quantite}
                onChange={(e) => majLigne(i, 'quantite', e.target.value)}
              />
              <Select
                value={l.mode_prix}
                onValueChange={(v) => majLigne(i, 'mode_prix', v)}
              >
                <SelectTrigger className="sm:w-56" aria-label={`Mode de prix de la ligne ${i + 1}`}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {MODES.map(([valeur, libelle]) => (
                    <SelectItem key={valeur} value={valeur}>{libelle}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Input
                className="sm:w-32"
                inputMode="decimal"
                step="any"
                placeholder="Valeur"
                aria-label={`Valeur de la ligne ${i + 1}`}
                value={l.valeur}
                onChange={(e) => majLigne(i, 'valeur', e.target.value)}
              />
              <Button
                variant="ghost"
                size="sm"
                disabled={lignes.length === 1}
                onClick={() => setLignes((ls) => ls.filter((_, j) => j !== i))}
              >
                <Trash2 /> Retirer
              </Button>
            </div>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            onClick={() => setLignes((ls) => [...ls, ligneVide()])}
            data-testid="cpq-offre-ajouter-ligne"
          >
            <Plus /> Ajouter une ligne
          </Button>
          <Button onClick={creer} disabled={occupe} data-testid="cpq-offre-creer">
            <Package /> Créer l&apos;offre
          </Button>
        </div>
      </Card>

      {chargement && <p className="text-sm text-muted-foreground">Chargement des offres…</p>}
      {!chargement && erreur && <EmptyState title="Erreur" description={erreur} />}
      {!chargement && !erreur && offres.length === 0 && (
        <EmptyState
          title="Aucune offre groupée"
          description="Composez un ensemble ci-dessus pour le proposer sur vos devis."
        />
      )}

      {!chargement && !erreur && offres.length > 0 && masse.disponible && (
        <Card
          className="flex flex-wrap items-center gap-3 p-4 sm:p-5"
          data-testid="cpq-offre-masse"
        >
          <span className="text-sm font-medium text-foreground">Modifier en masse</span>
          <span className="text-sm text-muted-foreground">
            {selectionMasse.length} offre(s) sélectionnée(s)
          </span>
          {masse.champs.includes('actif') && (
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                disabled={masse.enCours || selectionMasse.length === 0}
                onClick={() => appliquerMasse(true)}
                data-testid="cpq-offre-masse-activer"
              >
                Activer
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={masse.enCours || selectionMasse.length === 0}
                onClick={() => appliquerMasse(false)}
                data-testid="cpq-offre-masse-desactiver"
              >
                Désactiver
              </Button>
            </div>
          )}
        </Card>
      )}

      {!chargement && !erreur && offres.length > 0 && (
        <ul className="flex flex-col gap-3" data-testid="cpq-offre-liste">
          {offres.map((o) => (
            <li key={o.id}>
              <Card className="flex flex-col gap-3 p-4 sm:p-5">
                <div className="flex flex-wrap items-center gap-2">
                  {masse.disponible && (
                    <Checkbox
                      aria-label={`Sélectionner ${o.nom}`}
                      checked={selectionMasse.includes(o.id)}
                      onCheckedChange={() => basculerMasse(o.id)}
                    />
                  )}
                  <span className="font-medium">{o.nom}</span>
                  <Badge tone="neutral">{(o.lignes || []).length} ligne(s)</Badge>
                  {o.prix_total != null && o.prix_total !== '' && (
                    <Badge tone="info">Prix bundle {o.prix_total}</Badge>
                  )}
                  {!o.actif && <Badge tone="warning">Inactive</Badge>}
                </div>

                {(o.lignes || []).length > 0 && (
                  <ul className="flex flex-col gap-1 text-sm text-muted-foreground">
                    {o.lignes.map((l) => (
                      <li key={l.id}>
                        {nomProduit(produits, l.produit)} × {l.quantite} —{' '}
                        {LIBELLE_MODE[l.mode_prix] || l.mode_prix}
                        {l.valeur != null && l.valeur !== '' ? ` (${l.valeur})` : ''}
                      </li>
                    ))}
                  </ul>
                )}

                <div className="flex flex-wrap items-end gap-2">
                  <Select
                    value={devisCible[o.id] || ''}
                    onValueChange={(v) => setDevisCible((d) => ({ ...d, [o.id]: v }))}
                  >
                    <SelectTrigger className="w-64" aria-label={`Devis cible pour ${o.nom}`}>
                      <SelectValue placeholder="Choisir un devis" />
                    </SelectTrigger>
                    <SelectContent>
                      {devis.map((d) => (
                        <SelectItem key={d.id} value={String(d.id)}>
                          {d.reference || `Devis #${d.id}`}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button
                    onClick={() => appliquer(o)}
                    disabled={occupe || !devisCible[o.id]}
                    data-testid={`cpq-offre-appliquer-${o.id}`}
                  >
                    Appliquer au devis
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => supprimer(o)}>
                    <Trash2 /> Supprimer
                  </Button>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
