import { useState, useEffect, useRef } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Plus, X, Star, Trash2, Pencil, ImagePlus, Sparkles } from 'lucide-react'
import {
  createProduit,
  updateProduit,
  fetchCategories,
  fetchFournisseurs,
  createCategorie,
  createFournisseur,
} from '../../features/stock/store/stockSlice'
import { useIsAdmin } from '../../hooks/useHasPermission'
import stockApi from '../../api/stockApi'
// PACT143 — brouillon de description commerciale (`/ai/description-produit/`,
// NTAI13) : endpoint hors `stockApi`, appelé directement.
import api from '../../api/axios'
import { formatMAD, formatPercent } from '../../lib/format'
import {
  Button, Badge, Switch,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Form, FormSection, FormField, useDirtyGuard, confirmLeaveIfDirty,
  Input, Textarea, Label,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  toast,
} from '../../ui'
import { isDirty } from '../../ui/form-utils'
import { compressImage, validateFile } from '../../ui/file-utils'
import { useServerFieldErrors } from '../../hooks/useServerFieldErrors'
import CustomFieldsInput from '../../components/CustomFieldsInput'
// PVOND (fondateur 18/08) — la classification produit reste UNE seule
// source : la même que le générateur de devis, jamais réimplémentée ici.
import { classifyProduct, isPompe } from '../../features/ventes/solar.js'
import {
  MARQUEUR_PLAGE_BATTERIE,
  lirePlageBatterieDescription, ecrirePlageBatterieDescription, plageBatterieDeclaree,
  manquantesOnduleurLocal, typeFicheBackend, ficheFieldsVides,
  champsFicheDepuisServeur, champsFichePourType,
} from './pvondFicheTechnique.js'

// APX18 — photo produit : seules les images, bornées à 10 Mo — le MÊME
// plafond que la primitive plateforme `records.storage` côté serveur, pour
// qu'un refus se voie AVANT le réseau plutôt qu'en 400. `image/*` reste large
// à dessein : la compression VX77 réencode en JPEG (bord long 1600 px) ce que
// le navigateur sait décoder, HEIC d'iPhone compris, et le serveur reste
// l'autorité (octets magiques : PNG/JPEG/WebP).
// La photo est INTERNE : elle n'entre dans aucun PDF ni sortie client.
const PHOTO_ACCEPT = 'image/*'
const PHOTO_MAX_SIZE = 10 * 1024 * 1024

// VX92 — « Créer un autre » : persisté par utilisateur/poste (localStorage),
// défaut OFF (comportement historique inchangé). Un salon = 10 leads/produits
// créés d'affilée ; sans ce toggle chaque création coûte un cycle
// fermer/rouvrir (~10-30 s).
const CREER_UN_AUTRE_KEY = 'taqinor.produitForm.creerUnAutre'
function lireCreerUnAutre() {
  try {
    return window.localStorage.getItem(CREER_UN_AUTRE_KEY) === '1'
  } catch {
    return false
  }
}
function ecrireCreerUnAutre(v) {
  try {
    window.localStorage.setItem(CREER_UN_AUTRE_KEY, v ? '1' : '0')
  } catch {
    // localStorage indisponible (navigation privée, quota) : no-op silencieux.
  }
}

// VX93 — défaut intelligent : dernier taux de TVA saisi (création seulement),
// mémorisé par localStorage. Repli sur '20' (cas le plus courant) si absent.
const LAST_TVA_KEY = 'taqinor.produitForm.lastTva'
function lireLastTva() {
  try {
    return window.localStorage.getItem(LAST_TVA_KEY) || '20'
  } catch {
    return '20'
  }
}
function ecrireLastTva(v) {
  try {
    if (v !== '' && v != null) window.localStorage.setItem(LAST_TVA_KEY, String(v))
  } catch {
    // no-op silencieux.
  }
}

// VX171 — traduit le message SKU (contrainte d'unicité serveur) en phrase
// française lisible AVANT de le confier à useServerFieldErrors — les autres
// champs (nom, prix_vente…) sont mappés génériquement par le hook.
function frSkuMessage(msg) {
  return /unique|already exists|existe/i.test(msg)
    ? 'Ce SKU est déjà utilisé par un autre produit.'
    : msg
}

// N17 — listes de prix multi-fournisseurs par SKU. Le prix d'achat est INTERNE
// (jamais sur un document client). Le moins cher est proposé en rédigeant un
// bon de commande. Section éditable seulement en mode édition d'un produit.
function PrixFournisseursSection({ produitId, fournisseurs, isAdmin = false }) {
  const [rows, setRows] = useState([])
  const [fId, setFId] = useState('')
  const [prix, setPrix] = useState('')
  const [error, setError] = useState(null)
  const [editId, setEditId] = useState(null)   // ligne en édition
  const [editPrix, setEditPrix] = useState('')
  // WR4 / FG58 — comparaison des fournisseurs (endpoint dédié, admin).
  const [comparaison, setComparaison] = useState(null)
  const [comparBusy, setComparBusy] = useState(false)
  // NTSCM26 — coût total d'acquisition par fournisseur (colonne additionnelle).
  const [tco, setTco] = useState([])

  const load = () => stockApi.getProduitPrixFournisseurs(produitId)
    .then((r) => setRows(r.data ?? [])).catch(() => {})
  useEffect(() => { load() }, [produitId])  // eslint-disable-line react-hooks/exhaustive-deps

  const comparer = () => {
    setComparBusy(true); setError(null)
    stockApi.comparerFournisseurs(produitId)
      .then((r) => setComparaison(r.data ?? []))
      .catch((e) => setError(e?.response?.status === 403
        ? 'Comparaison réservée à l\'administrateur.'
        : 'Comparaison indisponible.'))
      .finally(() => setComparBusy(false))
    // NTSCM26 — colonne TCO ADDITIONNELLE : le prix nu reste la colonne de
    // référence, le TCO ajoute le coût du retard mesuré (NTSCM11) et le coût
    // qualité moyen (NTSCM9). Best-effort : indisponible = colonne « — »,
    // jamais un échec de la comparaison de prix elle-même.
    stockApi.comparerTcoFournisseurs(produitId)
      .then((r) => setTco(r.data?.fournisseurs ?? []))
      .catch(() => setTco([]))
  }

  const sorted = [...rows].sort((a, b) => Number(a.prix_achat) - Number(b.prix_achat))
  const used = new Set(rows.map((r) => String(r.fournisseur)))
  const dispo = (fournisseurs ?? []).filter((f) => !used.has(String(f.id)))
  const moinsCher = sorted.length ? Number(sorted[0].prix_achat) : 0

  const add = () => {
    setError(null)
    const p = parseFloat(prix)
    if (!fId) { setError('Choisissez un fournisseur.'); return }
    if (!Number.isFinite(p) || p <= 0) { setError('Prix d\'achat invalide.'); return }
    // Doublon de fournisseur : interdit (unicité ('produit','fournisseur')).
    if (used.has(String(fId))) {
      setError('Ce fournisseur a déjà un prix pour ce produit — modifiez-le.'); return
    }
    stockApi.createPrixFournisseur({ produit: produitId, fournisseur: fId, prix_achat: p })
      .then(() => { setFId(''); setPrix(''); return load() })
      .catch((e) => setError(e.response?.data?.detail
        ?? (e.response?.data?.fournisseur?.[0] && 'Ce fournisseur a déjà un prix pour ce produit.')
        ?? 'Échec de l\'ajout.'))
  }
  const remove = (id) => stockApi.deletePrixFournisseur(id).then(load).catch(() => {})

  const startEdit = (r) => { setEditId(r.id); setEditPrix(String(r.prix_achat)); setError(null) }
  const cancelEdit = () => { setEditId(null); setEditPrix('') }
  const saveEdit = (id) => {
    const p = parseFloat(editPrix)
    if (!Number.isFinite(p) || p <= 0) { setError('Prix d\'achat invalide.'); return }
    stockApi.updatePrixFournisseur(id, { prix_achat: p })
      .then(() => { cancelEdit(); return load() })
      .catch((e) => setError(e.response?.data?.detail ?? 'Échec de la modification.'))
  }

  // Date du dernier achat au format JJ/MM/AAAA (sinon « — »).
  const fmtAchatDate = (iso) => {
    if (!iso) return '—'
    const d = new Date(iso)
    return Number.isNaN(d.getTime())
      ? '—'
      : d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' })
  }

  return (
    <section className="sm:col-span-2 flex flex-col gap-2 border-t border-border pt-4">
      <div className="flex flex-col gap-0.5">
        <p className="text-sm font-medium text-foreground">Prix fournisseurs (interne)</p>
        <p className="text-xs text-muted-foreground">
          Plusieurs fournisseurs possibles ; le moins cher est proposé à la commande.
          Mis à jour automatiquement à la réception d&apos;un bon de commande.
        </p>
      </div>
      {sorted.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[30rem] text-sm">
            <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left font-semibold">Fournisseur</th>
                <th className="px-3 py-2 text-left font-semibold">Prix d&apos;achat HT</th>
                <th className="px-3 py-2 text-left font-semibold">Dernier achat</th>
                <th className="w-10 px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {sorted.map((r, i) => {
                const ecart = (i > 0 && moinsCher > 0)
                  ? ((Number(r.prix_achat) - moinsCher) / moinsCher) * 100
                  : null
                return (
                  <tr key={r.id} className="border-t border-border">
                    <td className="px-3 py-2">
                      <span className="inline-flex items-center gap-1">
                        {r.fournisseur_nom}
                        {i === 0 && <Star className="size-3.5 fill-warning text-warning" aria-label="Le moins cher" />}
                      </span>
                    </td>
                    <td className="px-3 py-2 tabular-nums">
                      {editId === r.id ? (
                        <Input type="number" min="0" step="any" inputMode="decimal" className="h-8 w-28"
                               value={editPrix} onChange={(e) => setEditPrix(e.target.value)} />
                      ) : (
                        <span className="inline-flex items-center gap-1.5">
                          {formatMAD(r.prix_achat, { withSymbol: false })} DH
                          {ecart != null && ecart > 0 && (
                            <span className="text-xs text-warning">+{formatPercent(ecart, { decimals: 0 })} vs le moins cher</span>
                          )}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">{fmtAchatDate(r.date_dernier_achat)}</td>
                    <td className="px-3 py-2">
                      {editId === r.id ? (
                        <span className="flex gap-1">
                          <Button type="button" variant="outline" size="sm" onClick={() => saveEdit(r.id)}>OK</Button>
                          <Button type="button" variant="ghost" size="sm" onClick={cancelEdit}>×</Button>
                        </span>
                      ) : (
                        <span className="flex gap-0.5">
                          <Button type="button" variant="ghost" size="icon" className="size-7"
                                  aria-label="Modifier le prix" onClick={() => startEdit(r)}>
                            <Pencil className="size-3.5" />
                          </Button>
                          <Button type="button" variant="ghost" size="icon" className="size-7"
                                  aria-label="Supprimer" onClick={() => remove(r.id)}>
                            <Trash2 className="text-destructive" />
                          </Button>
                        </span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-48 flex-1">
          <Select value={fId || '__none'} onValueChange={(v) => setFId(v === '__none' ? '' : v)}>
            <SelectTrigger><SelectValue placeholder="— Fournisseur —" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__none">— Fournisseur —</SelectItem>
              {dispo.map((f) => <SelectItem key={f.id} value={String(f.id)}>{f.nom}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <Input type="number" min="0" step="any" inputMode="decimal" className="w-40"
               placeholder="Prix d'achat HT" value={prix} onChange={(e) => setPrix(e.target.value)} />
        <Button type="button" variant="outline" onClick={add}>Ajouter</Button>
        {isAdmin && (
          <Button type="button" variant="ghost" loading={comparBusy} onClick={comparer}>
            Comparer (interne)
          </Button>
        )}
      </div>

      {comparaison && (
        comparaison.length === 0 ? (
          <p className="text-xs text-muted-foreground">Aucun prix fournisseur à comparer.</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[24rem] text-sm">
              <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left font-semibold">Rang</th>
                  <th className="px-3 py-2 text-left font-semibold">Fournisseur</th>
                  <th className="px-3 py-2 text-left font-semibold">Prix d&apos;achat HT</th>
                  {/* NTSCM26 — le TCO COMPLÈTE le prix nu, il ne le remplace jamais. */}
                  <th className="px-3 py-2 text-left font-semibold" title="Prix nu + coût du retard mesuré + coût qualité moyen">TCO (interne)</th>
                  <th className="px-3 py-2 text-left font-semibold">Dernier achat</th>
                </tr>
              </thead>
              <tbody>
                {comparaison.map((c, i) => (
                  <tr key={c.fournisseur_id} className="border-t border-border">
                    <td className="px-3 py-2 tabular-nums">
                      {i === 0 ? <Star className="size-3.5 fill-warning text-warning" aria-label="Le moins cher" /> : i + 1}
                    </td>
                    <td className="px-3 py-2">{c.fournisseur_nom}</td>
                    <td className="px-3 py-2 tabular-nums">{formatMAD(c.prix_achat, { withSymbol: false })} DH</td>
                    <td className="px-3 py-2 tabular-nums">
                      {(() => {
                        const t = tco.find((x) => x.fournisseur_id === c.fournisseur_id)
                        return t ? `${formatMAD(t.tco, { withSymbol: false })} DH` : '—'
                      })()}
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">
                      {c.date_dernier_achat
                        ? new Date(c.date_dernier_achat).toLocaleDateString('fr-FR')
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}
      {error && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-2 text-sm text-destructive">
          {error}
        </div>
      )}
    </section>
  )
}

export default function ProduitForm({ produit = null, onClose, onSaved }) {
  const dispatch = useDispatch()
  const { categories, fournisseurs, produits } = useSelector(s => s.stock)
  const isAdmin = useIsAdmin()
  const isEdit = !!produit

  const [saving, setSaving] = useState(false)
  // VX171 — vérité serveur → champ ; le rouge s'efface à la frappe.
  const { errors, setErrors, setFromResponse, clearField } = useServerFieldErrors()

  // VX92 — « Créer un autre » : uniquement pertinent à la création (jamais en
  // édition), persisté (localStorage), défaut OFF.
  const [creerUnAutre, setCreerUnAutre] = useState(() => !isEdit && lireCreerUnAutre())
  const nomRef = useRef(null)

  // VX249(b) — tva : 1 des 4 champs VX93 exactement (avec owner/ville sur
  // LeadForm.jsx et payMode sur FactureList.jsx). « Suggéré » n'a de sens
  // qu'à la création (VX93 ne pré-remplit jamais en édition).
  const [tvaTouched, setTvaTouched] = useState(false)
  const [tvaFocused, setTvaFocused] = useState(false)
  const tvaSuggested = !isEdit && !tvaTouched

  const [newCatName, setNewCatName] = useState('')
  const [showNewCat, setShowNewCat] = useState(false)
  const [catSaving, setCatSaving] = useState(false)
  const [catError, setCatError] = useState(null)
  const newCatRef = useRef(null)

  const [newFouName, setNewFouName] = useState('')
  const [showNewFou, setShowNewFou] = useState(false)
  const [fouSaving, setFouSaving] = useState(false)
  const [fouError, setFouError] = useState(null)
  const newFouRef = useRef(null)

  const initialFields = {
    nom:            produit?.nom            ?? '',
    sku:            produit?.sku            ?? '',
    // APX20 — `marque` et `garantie` (TEXTE) existaient au modèle et
    // alimentaient déjà les fiches produits des PDF de devis, mais AUCUN écran
    // ne permettait de les saisir : la création rapide promettait « vous
    // pourrez compléter (catégorie, marque, garantie…) plus tard depuis
    // Stock » et Stock ne le permettait pas. Promesse tenue ici.
    marque:         produit?.marque         ?? '',
    garantie:       produit?.garantie       ?? '',
    description:    produit?.description    ?? '',
    prix_vente:     String(produit?.prix_vente  ?? ''),
    prix_achat:     String(produit?.prix_achat  ?? '0'),
    // VX93 — nouveau produit : dernier taux TVA saisi (localStorage, défaut 20 %) ;
    // l'édition conserve la valeur existante (y compris « Sans TVA »).
    tva:            produit?.tva != null ? String(produit.tva) : (isEdit ? '' : lireLastTva()),
    quantite_stock: String(produit?.quantite_stock ?? '0'),
    seuil_alerte:   String(produit?.seuil_alerte  ?? '0'),
    categorie_id:   produit?.categorie?.id  ? String(produit.categorie.id) : '',
    fournisseur_id: produit?.fournisseur?.id ? String(produit.fournisseur.id) : '',
    garantie_mois:            produit?.garantie_mois != null ? String(produit.garantie_mois) : '',
    garantie_production_mois: produit?.garantie_production_mois != null ? String(produit.garantie_production_mois) : '',
  }
  const [initialFieldsSnapshot] = useState(initialFields)
  const [fields, setFields] = useState(initialFields)

  // WIR67 — champs personnalisés du module « produit » (le backend valide/
  // persiste `custom_data` du Produit, même motif que Lead/Client).
  const [customData, setCustomData] = useState(produit?.custom_data || {})

  // ── APX18 — photo produit ────────────────────────────────────────────────
  // `photoFile` = nouvelle image choisie (déjà compressée VX77) ; `photoRetiree`
  // = l'utilisateur a supprimé la photo existante. Les deux sont envoyés APRÈS
  // la création/mise à jour (un PATCH multipart séparé — le payload JSON ne
  // peut pas porter de fichier). Aucune des deux n'entre dans un PDF.
  const [photoFile, setPhotoFile] = useState(null)
  const [photoApercu, setPhotoApercu] = useState(null)   // objectURL local
  const [photoRetiree, setPhotoRetiree] = useState(false)
  const [photoErreur, setPhotoErreur] = useState(null)
  const photoInputRef = useRef(null)
  // URL servie par l'action authentifiée quand une photo est déjà enregistrée.
  const photoExistante = (!photoRetiree && !photoApercu) ? (produit?.image_url ?? null) : null

  // L'objectURL de l'aperçu est révoqué dès qu'il est remplacé/abandonné :
  // sans ça chaque essai de photo fuit un blob pour la durée de la session.
  useEffect(() => () => { if (photoApercu) URL.revokeObjectURL(photoApercu) }, [photoApercu])

  const choisirPhoto = async (file) => {
    setPhotoErreur(null)
    if (!file) return
    const check = validateFile(file, { accept: PHOTO_ACCEPT, maxSize: PHOTO_MAX_SIZE })
    if (!check.ok) { setPhotoErreur(check.message); return }
    // VX77 — compression cliente : une photo d'appareil moderne fait 4-8 Mo,
    // intenable sur la 3G rurale. Le helper est un passthrough silencieux si
    // le canvas n'est pas disponible — il ne fait JAMAIS échouer l'envoi.
    const compresse = await compressImage(file)
    setPhotoFile(compresse)
    setPhotoRetiree(false)
    setPhotoApercu((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return typeof URL.createObjectURL === 'function' ? URL.createObjectURL(compresse) : null
    })
  }

  const retirerPhoto = () => {
    setPhotoErreur(null)
    setPhotoFile(null)
    setPhotoApercu((prev) => { if (prev) URL.revokeObjectURL(prev); return null })
    // Ne marque « retirée » que s'il y avait bien une photo enregistrée :
    // annuler un choix local ne doit pas déclencher un PATCH de suppression.
    setPhotoRetiree(!!produit?.image_url)
    if (photoInputRef.current) photoInputRef.current.value = ''
  }

  // ── PVOND (fondateur 18/08) — section « Fiche technique » ──────────────────
  // Complétée en SECOND, après le produit, exactement comme la photo APX18 :
  // un échec d'enregistrement de la fiche ne perd JAMAIS le produit déjà
  // sauvegardé. `ficheId` = id de la `FicheTechnique` (PV5) existante, ou
  // `null` si ce produit n'en a pas encore. `ficheChargee` évite d'afficher
  // l'indicateur de complétude une fraction de seconde avec des champs
  // encore vides pendant le chargement (même garde que ProduitDetail.jsx).
  const [ficheId, setFicheId] = useState(null)
  const [ficheFields, setFicheFields] = useState(ficheFieldsVides())
  const [ficheChargee, setFicheChargee] = useState(!isEdit)

  useEffect(() => {
    if (!isEdit || !produit?.id) { setFicheChargee(true); return undefined }
    let active = true
    stockApi.getFichesTechniques(produit.id)
      .then((r) => {
        if (!active) return
        const liste = r.data?.results ?? r.data ?? []
        const f = liste[0] ?? null
        setFicheId(f?.id ?? null)
        setFicheFields(champsFicheDepuisServeur(f))
        setFicheChargee(true)
      })
      .catch(() => { if (active) setFicheChargee(true) })
    return () => { active = false }
  }, [isEdit, produit?.id])

  const setFicheField = (k, v) => setFicheFields((f) => ({ ...f, [k]: v }))

  // Type détecté depuis le NOM tapé — même classification que le générateur
  // de devis (`classifyProduct`, solar.js), jamais réimplémentée ici.
  const ficheType = classifyProduct(fields.nom)
  const estOnduleurHybride = ficheType === 'onduleur_hybride'
  const estOnduleur = estOnduleurHybride || ficheType === 'onduleur_reseau'
  const estPanneauFiche = ficheType === 'panneau'
  const estBatterieFiche = ficheType === 'batterie'
  const estPompeFiche = isPompe(fields.nom)
  const afficherFicheTechnique = estOnduleur || estPanneauFiche || estBatterieFiche || estPompeFiche

  // Plage de tension batterie : éditable ici UNIQUEMENT pour un onduleur
  // HYBRIDE (règle fondateur 18/08) — un onduleur réseau n'en porte jamais.
  // Elle vit dans une ligne marquée de `fields.description` (voir
  // pvondFicheTechnique.js) faute de champ dédié sur FicheTechnique ; pour un
  // onduleur réseau non-hybride, on retombe sur l'état SERVEUR déjà connu
  // (non éditable depuis cet écran).
  const plageBatterieActuelle = estOnduleurHybride ? lirePlageBatterieDescription(fields.description) : null
  const plageBatterieAbsente = estOnduleurHybride
    ? !plageBatterieDeclaree(fields.description)
    : (produit?.specs_solaire?.plage_batterie_v == null)
  // PVOND — verrou de complétude, recalculé EN LOCAL pendant la frappe :
  // l'exact miroir de la bannière « Onduleur(s) non chiffrable(s) » du
  // générateur de devis (`onduleurSpecsManquantes`, solar.js), qui ne lit
  // que le dernier état SERVEUR — remplir ce formulaire éteint donc
  // visiblement l'avertissement avant même l'enregistrement.
  const manquantesOnduleur = estOnduleur
    ? manquantesOnduleurLocal({ ficheFields, garantieTexte: fields.garantie, plageBatterieAbsente })
    : []

  const dirty = isDirty(initialFieldsSnapshot, fields)
  useDirtyGuard(dirty)

  useEffect(() => {
    dispatch(fetchCategories())
    dispatch(fetchFournisseurs())
  }, [dispatch])

  useEffect(() => {
    if (showNewCat) newCatRef.current?.focus()
  }, [showNewCat])

  useEffect(() => {
    if (showNewFou) newFouRef.current?.focus()
  }, [showNewFou])

  const handleCreateCategorie = async () => {
    const nom = newCatName.trim()
    if (!nom) return
    setCatSaving(true)
    setCatError(null)
    try {
      const result = await dispatch(createCategorie({ nom })).unwrap()
      setField('categorie_id', String(result.id))
      setNewCatName('')
      setShowNewCat(false)
    } catch (err) {
      setCatError(err?.nom?.[0] ?? err?.detail ?? 'Erreur lors de la création.')
    } finally {
      setCatSaving(false)
    }
  }

  const handleCreateFournisseur = async () => {
    const nom = newFouName.trim()
    if (!nom) return
    setFouSaving(true)
    setFouError(null)
    try {
      const result = await dispatch(createFournisseur({ nom })).unwrap()
      setField('fournisseur_id', String(result.id))
      setNewFouName('')
      setShowNewFou(false)
    } catch (err) {
      setFouError(err?.nom?.[0] ?? err?.detail ?? 'Erreur lors de la création.')
    } finally {
      setFouSaving(false)
    }
  }

  // VX171 — le rouge ne doit jamais mentir pendant que l'utilisateur corrige.
  const setField = (k, v) => { clearField(k); setFields(f => ({ ...f, [k]: v })) }

  // PACT143 — brouillon de description commerciale (NTAI13,
  // `POST /ai/description-produit/`). L'endpoint ne fait QUE proposer : rien
  // n'est jamais écrit tant que l'utilisateur n'a pas validé — la validation
  // ici ne fait que remplir `fields.description`, la sauvegarde réelle reste
  // le bouton « Enregistrer » existant du formulaire. Réservé à l'édition
  // (un produit pas encore créé n'a pas de `produit_id`).
  const [iaDialogOpen, setIaDialogOpen] = useState(false)
  const [iaLoading, setIaLoading] = useState(false)
  const [iaDraft, setIaDraft] = useState({ description: '', description_courte: '' })

  const genererDescriptionIA = async () => {
    if (!produit?.id) return
    setIaLoading(true)
    try {
      const res = await api.post('/ai/description-produit/', { produit_id: produit.id })
      setIaDraft({
        description: res.data?.description || '',
        description_courte: res.data?.description_courte || '',
      })
      setIaDialogOpen(true)
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Génération impossible.')
    } finally {
      setIaLoading(false)
    }
  }

  const appliquerDescriptionIA = () => {
    setField('description', iaDraft.description)
    setIaDialogOpen(false)
  }

  // Doublon de SKU détecté localement (unicité ('company','sku') côté serveur).
  // Le serveur reste l'autorité ; ceci évite un aller-retour pour un cas courant.
  const skuTrimmed = fields.sku.trim().toLowerCase()
  const skuDuplicate = skuTrimmed
    ? (produits ?? []).find(
        (p) => p.id !== produit?.id
          && (p.sku ?? '').trim().toLowerCase() === skuTrimmed,
      )
    : null

  const validate = () => {
    const e = {}
    if (!fields.nom.trim())               e.nom        = 'Nom requis'
    // Prix de vente : doit être strictement positif (0/négatif rejeté en JS au
    // submit, jamais via min/step HTML5 qui snapperait la saisie).
    if (!(parseFloat(fields.prix_vente) > 0))
                                           e.prix_vente = 'Prix de vente requis (> 0)'
    if (skuDuplicate)
      e.sku = `SKU déjà utilisé par « ${skuDuplicate.nom} »`
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    setSaving(true)
    try {
      const payload = {
        nom:            fields.nom.trim(),
        sku:            fields.sku.trim() || null,
        // APX20 — vidés → null (le modèle est nullable) : effacer une marque
        // doit vraiment l'effacer, pas y laisser une chaîne vide.
        marque:         fields.marque.trim() || null,
        garantie:       fields.garantie.trim() || null,
        description:    fields.description.trim() || null,
        prix_vente:     fields.prix_vente,
        prix_achat:     fields.prix_achat,
        tva:            fields.tva !== '' ? parseFloat(fields.tva) : null,
        quantite_stock: parseInt(fields.quantite_stock) || 0,
        seuil_alerte:   parseInt(fields.seuil_alerte)   || 0,
        categorie_id:   fields.categorie_id   ? parseInt(fields.categorie_id)   : null,
        fournisseur_id: fields.fournisseur_id ? parseInt(fields.fournisseur_id) : null,
        garantie_mois:            fields.garantie_mois            !== '' ? parseInt(fields.garantie_mois)            : null,
        garantie_production_mois: fields.garantie_production_mois !== '' ? parseInt(fields.garantie_production_mois) : null,
        // WIR67 — champs personnalisés du module « produit ».
        custom_data: customData,
      }
      let enregistre
      if (isEdit) {
        enregistre = await dispatch(updateProduit({ id: produit.id, data: payload })).unwrap()
      } else {
        enregistre = await dispatch(createProduit(payload)).unwrap()
        ecrireLastTva(fields.tva)  // VX93 — mémorise la TVA pour le prochain produit
      }
      // APX18 — la photo part en SECOND, en multipart, une fois l'id connu
      // (création) ou sur l'id existant (édition). Un échec d'upload ne perd
      // JAMAIS le produit déjà enregistré : on le signale sans annuler.
      const cibleId = enregistre?.id ?? produit?.id
      if (cibleId && (photoFile || photoRetiree)) {
        try {
          await stockApi.uploadProduitImage(cibleId, photoFile)
        } catch (errPhoto) {
          // Le serveur renvoie déjà un message français (format refusé,
          // fichier trop lourd…) : on le montre plutôt qu'un « échec ».
          const raison = errPhoto?.response?.data?.detail
          toast.error(raison
            ? `Produit enregistré, mais la photo a été refusée : ${raison}`
            : 'Produit enregistré, mais la photo n\'a pas pu être envoyée.')
        }
      }
      // PVOND (fondateur 18/08) — la fiche technique part en SECOND elle
      // aussi, même patron que la photo : un échec ne perd JAMAIS le produit
      // déjà enregistré. On n'écrit que si le type a un bloc FicheTechnique
      // ET qu'il y a quelque chose à écrire (au moins un champ rempli, ou une
      // fiche existante à mettre à jour — y compris pour la vider).
      const typeFicheServeur = typeFicheBackend(ficheType)
      if (cibleId && typeFicheServeur) {
        const payloadFiche = champsFichePourType(ficheType, ficheFields)
        const aDesDonnees = Object.values(payloadFiche).some((v) => v !== null)
        if (aDesDonnees || ficheId) {
          try {
            if (ficheId) {
              // `type_fiche` est reposé à chaque enregistrement : si le nom
              // tapé a changé de classification (onduleur → panneau…) entre
              // deux modifications, la fiche existante suit plutôt que de
              // rester étiquetée sur l'ancien type pendant que ces champs du
              // NOUVEAU type s'y écrivent.
              await stockApi.updateFicheTechnique(
                ficheId, { type_fiche: typeFicheServeur, ...payloadFiche })
            } else {
              const resFiche = await stockApi.createFicheTechnique({
                produit: cibleId, type_fiche: typeFicheServeur, ...payloadFiche,
              })
              setFicheId(resFiche.data?.id ?? null)
            }
          } catch {
            toast.error('Produit enregistré, mais la fiche technique n\'a pas pu être enregistrée.')
          }
        }
      }
      onSaved?.()
      // VX92 — « Créer un autre » (uniquement à la création) : on vide le
      // formulaire et on refocalise le champ 1 au lieu de fermer le dialog.
      if (!isEdit && creerUnAutre) {
        toast.success('Produit créé.')
        // VX93 — le formulaire vidé ré-applique la dernière TVA saisie.
        setFields({ ...initialFields, tva: lireLastTva() })
        setErrors({})
        // VX249(b) — le produit SUIVANT reçoit un NOUVEAU défaut TVA : «
        // suggéré » redevient vrai.
        setTvaTouched(false)
        // APX18 — le produit SUIVANT repart sans photo (sinon la photo du
        // précédent serait re-téléversée en boucle).
        retirerPhoto()
        // PVOND — le produit SUIVANT repart sans fiche technique (sinon
        // celle du précédent serait ré-écrite dessus).
        setFicheId(null)
        setFicheFields(ficheFieldsVides())
        nomRef.current?.focus()
      } else {
        onClose()
      }
    } catch (err) {
      // VX171 — mapping DRF générique (detail / {champ:[…]} / array) ; le
      // message SKU (contrainte d'unicité) reste traduit en français lisible.
      const skuMsg = err && typeof err === 'object'
        ? (Array.isArray(err.sku) ? err.sku[0] : err.sku)
        : null
      setFromResponse(
        typeof skuMsg === 'string' ? { ...err, sku: frSkuMessage(skuMsg) } : err,
      )
    } finally {
      setSaving(false)
    }
  }

  // Indicateur de marge — GÉNÉRATEUR/INTERNE uniquement (jamais client-facing).
  const venteN = parseFloat(fields.prix_vente)
  const achatN = parseFloat(fields.prix_achat)
  const tvaN   = fields.tva !== '' ? parseFloat(fields.tva) : null
  const marge  = (venteN > 0 && achatN > 0) ? ((venteN - achatN) / venteN) * 100 : null
  const margeNegative = venteN > 0 && achatN > 0 && venteN < achatN

  return (
    <Dialog open onOpenChange={(o) => { if (!o && confirmLeaveIfDirty(dirty)) onClose() }}>
      <DialogContent className="max-h-[92vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? `Éditer — ${produit.nom}` : 'Nouveau produit'}</DialogTitle>
          <DialogDescription>
            Les prix d&apos;achat et la marge sont internes — jamais sur un document client.
          </DialogDescription>
        </DialogHeader>

        <Form onSubmit={handleSubmit} className="gap-6">
          <FormSection>
            <FormField label="Nom" required htmlFor="pf-nom" error={errors.nom}>
              {/* VX240(b) — sans autofocus, la modale s'ouvrait sans qu'aucun
                  champ ne soit prêt à recevoir la frappe. */}
              <Input id="pf-nom" ref={nomRef} autoFocus invalid={!!errors.nom} value={fields.nom}
                     onChange={e => setField('nom', e.target.value)} placeholder="Nom du produit" />
            </FormField>
            <FormField label="SKU / Référence" htmlFor="pf-sku" error={errors.sku}>
              <Input id="pf-sku" invalid={!!errors.sku} value={fields.sku}
                     onChange={e => setField('sku', e.target.value)} placeholder="REF-001" />
            </FormField>

            {/* APX20 — marque : consommée par la fiche produit des PDF de devis
                (et par le groupement CATÉGORIE → MARQUE du catalogue). */}
            <FormField label="Marque" htmlFor="pf-marque" error={errors.marque}
                       hint="Apparaît sur la fiche produit des devis.">
              <Input id="pf-marque" invalid={!!errors.marque} value={fields.marque}
                     onChange={e => setField('marque', e.target.value)}
                     placeholder="JA Solar, Deye, VEICHI…" />
            </FormField>

            {/* Catégorie (avec création inline) */}
            <FormField label="Catégorie" htmlFor="pf-cat" error={catError}>
              {showNewCat ? (
                <div className="flex gap-1.5">
                  <Input
                    ref={newCatRef}
                    value={newCatName}
                    onChange={e => setNewCatName(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleCreateCategorie() } }}
                    placeholder="Nom de la catégorie"
                  />
                  <Button type="button" loading={catSaving} disabled={!newCatName.trim()}
                          onClick={handleCreateCategorie}>Créer</Button>
                  <Button type="button" variant="outline" size="icon" aria-label="Annuler"
                          onClick={() => { setShowNewCat(false); setNewCatName(''); setCatError(null) }}>
                    <X />
                  </Button>
                </div>
              ) : (
                <div className="flex gap-1.5">
                  <div className="flex-1">
                    <Select value={fields.categorie_id || '__none'}
                            onValueChange={v => setField('categorie_id', v === '__none' ? '' : v)}>
                      <SelectTrigger id="pf-cat"><SelectValue placeholder="— Aucune catégorie —" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__none">— Aucune catégorie —</SelectItem>
                        {categories.map(c => <SelectItem key={c.id} value={String(c.id)}>{c.nom}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <Button type="button" variant="outline" size="icon"
                          aria-label="Créer une nouvelle catégorie" title="Créer une nouvelle catégorie"
                          onClick={() => setShowNewCat(true)}>
                    <Plus />
                  </Button>
                </div>
              )}
            </FormField>

            {/* Fournisseur (avec création inline) */}
            <FormField label="Fournisseur" htmlFor="pf-fou" error={fouError}>
              {showNewFou ? (
                <div className="flex gap-1.5">
                  <Input
                    ref={newFouRef}
                    value={newFouName}
                    onChange={e => setNewFouName(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleCreateFournisseur() } }}
                    placeholder="Nom du fournisseur"
                  />
                  <Button type="button" loading={fouSaving} disabled={!newFouName.trim()}
                          onClick={handleCreateFournisseur}>Créer</Button>
                  <Button type="button" variant="outline" size="icon" aria-label="Annuler"
                          onClick={() => { setShowNewFou(false); setNewFouName(''); setFouError(null) }}>
                    <X />
                  </Button>
                </div>
              ) : (
                <div className="flex gap-1.5">
                  <div className="flex-1">
                    <Select value={fields.fournisseur_id || '__none'}
                            onValueChange={v => setField('fournisseur_id', v === '__none' ? '' : v)}>
                      <SelectTrigger id="pf-fou"><SelectValue placeholder="— Aucun fournisseur —" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__none">— Aucun fournisseur —</SelectItem>
                        {fournisseurs.map(f => <SelectItem key={f.id} value={String(f.id)}>{f.nom}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <Button type="button" variant="outline" size="icon"
                          aria-label="Créer un nouveau fournisseur" title="Créer un nouveau fournisseur"
                          onClick={() => setShowNewFou(true)}>
                    <Plus />
                  </Button>
                </div>
              )}
            </FormField>

            <FormField label="Description" htmlFor="pf-desc" fullWidth>
              <Textarea id="pf-desc" rows={2} value={fields.description}
                        onChange={e => setField('description', e.target.value)}
                        placeholder="Description optionnelle…" />
              {/* PACT143 — brouillon IA (NTAI13), réservé à l'édition : un
                  produit pas encore créé n'a pas de `produit_id` à transmettre.
                  Propose un brouillon + sa variante courte À VALIDER — rien
                  n'est jamais écrit tant que « Utiliser cette description »
                  n'a pas été cliqué. */}
              {isEdit && (
                <Button type="button" variant="outline" size="sm"
                        className="mt-1.5 self-start"
                        disabled={iaLoading}
                        onClick={genererDescriptionIA}>
                  <Sparkles className="size-4" aria-hidden="true" />
                  {iaLoading ? 'Génération…' : 'Générer avec l’IA'}
                </Button>
              )}
            </FormField>

            {/* APX18 — Photo produit. INTERNE : elle sert la vignette du
                catalogue et l'en-tête de la fiche, jamais un document client
                (aucun PDF ne la lit) et jamais à côté du prix d'achat. */}
            <FormField
              label="Photo du produit" htmlFor="pf-photo" fullWidth
              error={photoErreur}
              hint="Facultatif — affichée dans le catalogue et sur la fiche. Jamais sur un document client."
            >
              <div className="flex flex-wrap items-center gap-3">
                <div
                  className="pf-photo-apercu flex size-20 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-border bg-muted/40"
                  data-testid="pf-photo-apercu"
                >
                  {(photoApercu || photoExistante)
                    ? (
                      <img
                        src={photoApercu || photoExistante}
                        alt={`Photo de ${fields.nom || 'ce produit'}`}
                        className="size-full object-cover"
                      />
                    )
                    : <ImagePlus className="size-6 text-muted-foreground" aria-hidden="true" />}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    id="pf-photo"
                    ref={photoInputRef}
                    type="file"
                    accept={PHOTO_ACCEPT}
                    className="pf-photo-input"
                    onChange={(e) => choisirPhoto(e.target.files?.[0] ?? null)}
                  />
                  {(photoApercu || photoExistante) && (
                    <Button type="button" variant="ghost" size="sm" onClick={retirerPhoto}>
                      Retirer la photo
                    </Button>
                  )}
                </div>
              </div>
            </FormField>
          </FormSection>

          <FormSection title="Prix & TVA">
            <FormField label="Prix de vente HT" required htmlFor="pf-vente" error={errors.prix_vente}>
              {/* step="any" + saisie libre : ne jamais snapper/rejeter un nombre tapé. */}
              <Input id="pf-vente" type="number" min="0" step="any" inputMode="decimal"
                     invalid={!!errors.prix_vente} value={fields.prix_vente}
                     onChange={e => setField('prix_vente', e.target.value)} />
              {/* Avertissement marge négative — interne, jamais bloquant. */}
              {margeNegative && (
                <p className="mt-1 text-xs text-warning">
                  Marge négative : le prix de vente est inférieur au prix d&apos;achat (interne).
                </p>
              )}
            </FormField>
            <FormField label="Prix d'achat HT" htmlFor="pf-achat" hint="Interne — jamais sur un document client.">
              <Input id="pf-achat" type="number" min="0" step="any" inputMode="decimal"
                     value={fields.prix_achat} onChange={e => setField('prix_achat', e.target.value)} />
            </FormField>
            {/* VX249(b) — tva : 1 des 4 champs VX93 exactement. Contour
                pointillé + micro-libellé au focus tant que le dernier taux
                mémorisé n'a pas été touché — retiré dès la première
                modification. */}
            <FormField
              label="TVA (%)"
              htmlFor="pf-tva"
              hint={tvaSuggested && tvaFocused ? 'Suggéré — modifiable' : undefined}
            >
              <Select
                value={fields.tva || '__none'}
                onValueChange={v => { setField('tva', v === '__none' ? '' : v); setTvaTouched(true) }}
              >
                <SelectTrigger
                  id="pf-tva"
                  className={tvaSuggested ? 'vx-suggested-field' : undefined}
                  onFocus={() => setTvaFocused(true)}
                  onBlur={() => setTvaFocused(false)}
                >
                  <SelectValue placeholder="— Sans TVA —" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none">— Sans TVA —</SelectItem>
                  <SelectItem value="0">0%</SelectItem>
                  <SelectItem value="7">7%</SelectItem>
                  <SelectItem value="10">10%</SelectItem>
                  <SelectItem value="14">14%</SelectItem>
                  <SelectItem value="20">20%</SelectItem>
                </SelectContent>
              </Select>
            </FormField>

            {/* Récap TVA TTC + marge interne */}
            {(tvaN !== null && venteN > 0) || marge !== null ? (
              <div className="sm:col-span-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                {tvaN !== null && venteN > 0 && (
                  <span>
                    Vente TTC : <strong className="text-foreground">{formatMAD(venteN * (1 + tvaN / 100), { withSymbol: false })} DH</strong>
                    {achatN > 0 && <> · Achat TTC : {formatMAD(achatN * (1 + tvaN / 100), { withSymbol: false })} DH</>}
                  </span>
                )}
                {marge !== null && (
                  <Badge tone={marge >= 0 ? 'success' : 'danger'}>
                    Marge {formatMAD(venteN - achatN, { withSymbol: false })} DH · {formatPercent(marge, { decimals: 1 })} (interne)
                  </Badge>
                )}
              </div>
            ) : null}
          </FormSection>

          <FormSection title="Stock & alerte">
            <FormField
              label="Quantité en stock" htmlFor="pf-qte"
              hint={isEdit ? 'Modifiez via un mouvement de stock' : undefined}
            >
              <Input id="pf-qte" type="number" min="0" step="1" inputMode="numeric"
                     value={fields.quantite_stock}
                     onChange={e => setField('quantite_stock', e.target.value)}
                     disabled={isEdit}
                     title={isEdit ? 'Utilisez un mouvement de stock pour modifier la quantité' : ''} />
            </FormField>
            <FormField label="Seuil d'alerte" htmlFor="pf-seuil">
              <Input id="pf-seuil" type="number" min="0" step="1" inputMode="numeric"
                     value={fields.seuil_alerte}
                     onChange={e => setField('seuil_alerte', e.target.value)} />
            </FormField>
          </FormSection>

          <FormSection
            title="Garantie"
            description="Le texte part sur la fiche produit des devis ; les durées en mois alimentent les horloges de garantie du parc d'équipements. Tout est optionnel."
          >
            {/* APX20 — garantie TEXTE, distincte des durées numériques
                ci-dessous : c'est elle que lisent les fiches produits des PDF
                de devis, et aucun écran ne permettait de la saisir. */}
            <FormField label="Texte de garantie" htmlFor="pf-gar-txt" fullWidth
                       hint="Phrase constructeur telle qu'elle doit apparaître sur le devis.">
              <Input id="pf-gar-txt" value={fields.garantie}
                     onChange={e => setField('garantie', e.target.value)}
                     placeholder="ex : 12 ans produit, 25 ans performance" />
            </FormField>
            <FormField label="Garantie équipement (mois)" htmlFor="pf-gar"
                       hint="Laisser vide si non renseignée.">
              <Input id="pf-gar" type="number" min="0" step="1" inputMode="numeric"
                     value={fields.garantie_mois}
                     onChange={e => setField('garantie_mois', e.target.value)}
                     placeholder="ex : 120 (10 ans)" />
            </FormField>
            <FormField label="Garantie production (mois)" htmlFor="pf-garprod"
                       hint="Pour les panneaux. Optionnel.">
              <Input id="pf-garprod" type="number" min="0" step="1" inputMode="numeric"
                     value={fields.garantie_production_mois}
                     onChange={e => setField('garantie_production_mois', e.target.value)}
                     placeholder="ex : 300 (panneaux, 25 ans)" />
            </FormField>
          </FormSection>

          {/* PVOND (fondateur 18/08) — « Fiche technique » : la promesse de
              ProduitDetail.jsx (« se modifie depuis l'édition du produit »)
              enfin tenue. Section par TYPE, auto-détecté depuis le nom tapé —
              rien à cocher, rien à ouvrir en plus. Chargée en attendant
              `ficheChargee` pour ne jamais flasher un indicateur faux le
              temps du chargement (édition). */}
          {afficherFicheTechnique && ficheChargee && (
            <FormSection
              title="Fiche technique"
              description={estOnduleur
                ? "Ce que le générateur de devis exige pour chiffrer cet onduleur — les mêmes variables que sa bannière « à renseigner »."
                : 'Caractéristiques techniques, lues par le dimensionnement et les fiches produits des devis.'}
            >
              {estOnduleur && (
                <div className="sm:col-span-2">
                  {manquantesOnduleur.length === 0 ? (
                    <Badge tone="success">Chiffrable ✓</Badge>
                  ) : (
                    <Badge tone="warning">
                      Non chiffrable — il manque : {manquantesOnduleur.join(', ')}
                    </Badge>
                  )}
                </div>
              )}

              {estOnduleur && (
                <>
                  <FormField label="Puissance AC (kW)" htmlFor="pf-ft-ackw">
                    <Input id="pf-ft-ackw" type="number" min="0" step="any" inputMode="decimal"
                           value={ficheFields.ond_ac_kw}
                           onChange={e => setFicheField('ond_ac_kw', e.target.value)} />
                  </FormField>
                  <FormField label="Phases" htmlFor="pf-ft-phases">
                    <Select
                      value={ficheFields.ond_phases || '__none'}
                      onValueChange={v => setFicheField('ond_phases', v === '__none' ? '' : v)}
                    >
                      <SelectTrigger id="pf-ft-phases"><SelectValue placeholder="— Non renseigné —" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__none">— Non renseigné —</SelectItem>
                        <SelectItem value="1">Monophasé</SelectItem>
                        <SelectItem value="3">Triphasé</SelectItem>
                      </SelectContent>
                    </Select>
                  </FormField>
                  <FormField label="Nombre d'entrées MPPT" htmlFor="pf-ft-nmppt">
                    <Input id="pf-ft-nmppt" type="number" min="0" step="any" inputMode="decimal"
                           value={ficheFields.ond_n_mppt}
                           onChange={e => setFicheField('ond_n_mppt', e.target.value)} />
                  </FormField>
                  <FormField label="Courant maxi par MPPT (A)" htmlFor="pf-ft-imax">
                    <Input id="pf-ft-imax" type="number" min="0" step="any" inputMode="decimal"
                           value={ficheFields.ond_i_max_mppt_a}
                           onChange={e => setFicheField('ond_i_max_mppt_a', e.target.value)} />
                  </FormField>
                  <FormField label="Plage MPPT — tension mini (V)" htmlFor="pf-ft-mpptmin">
                    <Input id="pf-ft-mpptmin" type="number" min="0" step="any" inputMode="decimal"
                           value={ficheFields.ond_mppt_v_min}
                           onChange={e => setFicheField('ond_mppt_v_min', e.target.value)} />
                  </FormField>
                  <FormField label="Plage MPPT — tension maxi (V)" htmlFor="pf-ft-mpptmax">
                    <Input id="pf-ft-mpptmax" type="number" min="0" step="any" inputMode="decimal"
                           value={ficheFields.ond_mppt_v_max}
                           onChange={e => setFicheField('ond_mppt_v_max', e.target.value)} />
                  </FormField>
                  <FormField label="Tension DC maximale (V)" htmlFor="pf-ft-vmax">
                    <Input id="pf-ft-vmax" type="number" min="0" step="any" inputMode="decimal"
                           value={ficheFields.ond_v_max_abs}
                           onChange={e => setFicheField('ond_v_max_abs', e.target.value)} />
                  </FormField>
                  <FormField label="Rendement européen (%)" htmlFor="pf-ft-rend">
                    <Input id="pf-ft-rend" type="number" min="0" step="any" inputMode="decimal"
                           value={ficheFields.ond_rendement_euro_pct}
                           onChange={e => setFicheField('ond_rendement_euro_pct', e.target.value)} />
                  </FormField>
                  {!fields.garantie.trim() && (
                    <p className="sm:col-span-2 text-xs text-muted-foreground">
                      Garantie constructeur — renseignez le champ « Texte de garantie »
                      ci-dessus (section Garantie) : c&apos;est lui que lit le contrat.
                    </p>
                  )}

                  {/* Plage de tension batterie — HYBRIDE uniquement (règle
                      fondateur 18/08). Pas de champ dédié côté serveur :
                      cette valeur vit dans une ligne marquée de la
                      description ci-dessus (voir pvondFicheTechnique.js) —
                      ce mini-contrôle ne fait qu'éviter la faute de frappe
                      sur le format, la donnée reste la MÊME ligne de texte. */}
                  {estOnduleurHybride && (
                    <div className="sm:col-span-2 flex flex-col gap-2 border-t border-border pt-3">
                      <Label>Plage de tension batterie (hybride)</Label>
                      <label className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Switch
                          checked={!!plageBatterieActuelle?.aucune}
                          onCheckedChange={(v) => setField('description', ecrirePlageBatterieDescription(
                            fields.description,
                            { aucune: v, min: plageBatterieActuelle?.min, max: plageBatterieActuelle?.max },
                          ))}
                          aria-label="Aucune batterie compatible (onduleur réseau)"
                        />
                        Aucune batterie compatible
                      </label>
                      {!plageBatterieActuelle?.aucune && (
                        <div className="flex flex-wrap gap-2">
                          <Input
                            type="number" min="0" step="any" inputMode="decimal" className="w-32"
                            placeholder="mini (V)" aria-label="Plage batterie — tension mini (V)"
                            value={plageBatterieActuelle?.min ?? ''}
                            onChange={e => setField('description', ecrirePlageBatterieDescription(
                              fields.description,
                              { aucune: false, min: e.target.value, max: plageBatterieActuelle?.max },
                            ))}
                          />
                          <Input
                            type="number" min="0" step="any" inputMode="decimal" className="w-32"
                            placeholder="maxi (V)" aria-label="Plage batterie — tension maxi (V)"
                            value={plageBatterieActuelle?.max ?? ''}
                            onChange={e => setField('description', ecrirePlageBatterieDescription(
                              fields.description,
                              { aucune: false, min: plageBatterieActuelle?.min, max: e.target.value },
                            ))}
                          />
                        </div>
                      )}
                      <p className="text-xs text-muted-foreground">
                        Enregistrée comme une ligne dans la description ci-dessus
                        (« {MARQUEUR_PLAGE_BATTERIE} … ») — c&apos;est elle qui décide
                        quelle batterie s&apos;accroche à cet onduleur.
                      </p>
                    </div>
                  )}
                </>
              )}

              {estPanneauFiche && (
                <>
                  <FormField label="Puissance crête (Wc)" htmlFor="pf-ft-pmax">
                    <Input id="pf-ft-pmax" type="number" min="0" step="any" inputMode="decimal"
                           value={ficheFields.pmax_wc}
                           onChange={e => setFicheField('pmax_wc', e.target.value)} />
                  </FormField>
                  <FormField label="Longueur (mm)" htmlFor="pf-ft-long">
                    <Input id="pf-ft-long" type="number" min="0" step="any" inputMode="decimal"
                           value={ficheFields.longueur_mm}
                           onChange={e => setFicheField('longueur_mm', e.target.value)} />
                  </FormField>
                  <FormField label="Largeur (mm)" htmlFor="pf-ft-larg">
                    <Input id="pf-ft-larg" type="number" min="0" step="any" inputMode="decimal"
                           value={ficheFields.largeur_mm}
                           onChange={e => setFicheField('largeur_mm', e.target.value)} />
                  </FormField>
                  <p className="sm:col-span-2 text-xs text-muted-foreground">
                    Garantie produit/performance : champs « Texte de garantie » et
                    « Garantie production (mois) » ci-dessus.
                  </p>
                </>
              )}

              {estBatterieFiche && (
                <>
                  <FormField label="Capacité nominale (kWh)" htmlFor="pf-ft-kwhnom">
                    <Input id="pf-ft-kwhnom" type="number" min="0" step="any" inputMode="decimal"
                           value={ficheFields.bat_kwh_nominal}
                           onChange={e => setFicheField('bat_kwh_nominal', e.target.value)} />
                  </FormField>
                  <FormField label="Capacité utilisable (kWh)" htmlFor="pf-ft-kwhutil">
                    <Input id="pf-ft-kwhutil" type="number" min="0" step="any" inputMode="decimal"
                           value={ficheFields.bat_kwh_usable}
                           onChange={e => setFicheField('bat_kwh_usable', e.target.value)} />
                  </FormField>
                  <FormField label="Tension nominale (V)" htmlFor="pf-ft-vnom">
                    <Input id="pf-ft-vnom" type="number" min="0" step="any" inputMode="decimal"
                           value={ficheFields.bat_v_nominal}
                           onChange={e => setFicheField('bat_v_nominal', e.target.value)} />
                  </FormField>
                  <FormField label="Profondeur de décharge — plage utile (%)" htmlFor="pf-ft-dod">
                    <Input id="pf-ft-dod" type="number" min="0" step="any" inputMode="decimal"
                           value={ficheFields.bat_dod_pct}
                           onChange={e => setFicheField('bat_dod_pct', e.target.value)} />
                  </FormField>
                </>
              )}

              {estPompeFiche && (
                <div className="sm:col-span-2 flex flex-col gap-2">
                  {isEdit ? (
                    <div className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-lg border border-border p-3 text-sm sm:grid-cols-3">
                      {[
                        ['Puissance (CV)', produit?.pompe_cv],
                        ['HMT max (m)', produit?.hmt_m],
                        ['Débit indicatif (m³/j)', produit?.debit_m3j],
                        ['Puissance (kW)', produit?.pompe_kw],
                        ['Tension (V)', produit?.tension_v],
                      ].map(([label, valeur]) => (
                        <div key={label}>
                          <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
                          <p className={valeur != null && valeur !== '' ? 'text-foreground' : 'italic text-muted-foreground'}>
                            {valeur != null && valeur !== '' ? String(valeur) : 'Non renseigné'}
                          </p>
                        </div>
                      ))}
                      <div>
                        <p className="text-xs uppercase tracking-wide text-muted-foreground">Courbe constructeur</p>
                        <p className={produit?.courbe_pompe ? 'text-foreground' : 'italic text-muted-foreground'}>
                          {produit?.courbe_pompe?.debits_m3h?.length
                            ? `${produit.courbe_pompe.debits_m3h.length} points`
                            : 'Aucune'}
                        </p>
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground">
                      Courbe constructeur et caractéristiques de pompage — disponibles après
                      la création du produit (saisie via le catalogue).
                    </p>
                  )}
                  <p className="text-xs text-muted-foreground">
                    Lecture seule — ces valeurs viennent du catalogue (seed) et alimentent le
                    dimensionnement du mode Agricole.
                  </p>
                </div>
              )}
            </FormSection>
          )}

          {/* WIR67 — champs personnalisés (module « produit »). */}
          <CustomFieldsInput module="produit" value={customData} onChange={setCustomData} />

          {isEdit && (
            <PrixFournisseursSection produitId={produit.id} fournisseurs={fournisseurs} isAdmin={isAdmin} />
          )}

          {errors.submit && (
            <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {errors.submit}
            </div>
          )}

          <DialogFooter>
            <div className="mr-auto flex flex-col gap-1">
              {dirty && <span className="text-xs text-warning">Modifications non enregistrées</span>}
              {/* VX92 — « Créer un autre » : seulement à la création. */}
              {!isEdit && (
                <label className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Switch
                    checked={creerUnAutre}
                    onCheckedChange={(v) => { setCreerUnAutre(v); ecrireCreerUnAutre(v) }}
                    aria-label="Créer un autre"
                  />
                  Créer un autre
                </label>
              )}
            </div>
            <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
            <Button type="submit" loading={saving}>
              {saving ? 'Enregistrement…' : (isEdit ? 'Mettre à jour' : 'Créer le produit')}
            </Button>
          </DialogFooter>
        </Form>

        {/* PACT143 — validation du brouillon IA avant toute sauvegarde :
            « Utiliser cette description » ne fait que remplir le champ
            `description` du formulaire (le bouton « Enregistrer » ci-dessus
            reste le seul chemin d'écriture). La variante courte est
            affichée pour référence mais n'a pas de champ dédié — jamais
            fusionnée à la description longue. */}
        {iaDialogOpen && (
          <Dialog open onOpenChange={(o) => { if (!o) setIaDialogOpen(false) }}>
            <DialogContent className="max-w-lg" showClose={false}>
              <DialogHeader>
                <DialogTitle>Brouillon de description commerciale</DialogTitle>
                <DialogDescription>
                  Généré par l’IA à partir des informations produit — à valider avant sauvegarde.
                </DialogDescription>
              </DialogHeader>
              <div className="flex flex-col gap-4">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="pf-ia-desc">Description proposée</Label>
                  <Textarea
                    id="pf-ia-desc" rows={4}
                    value={iaDraft.description}
                    onChange={(e) => setIaDraft((d) => ({ ...d, description: e.target.value }))}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="pf-ia-courte">Variante courte</Label>
                  <Textarea id="pf-ia-courte" rows={2} value={iaDraft.description_courte} readOnly />
                </div>
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setIaDialogOpen(false)}>Fermer</Button>
                <Button type="button" onClick={appliquerDescriptionIA}>Utiliser cette description</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )}
      </DialogContent>
    </Dialog>
  )
}
