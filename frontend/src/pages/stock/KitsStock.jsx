import { useCallback, useEffect, useState } from 'react'
import { Plus, Trash2, Copy, Pencil, History, Boxes } from 'lucide-react'
import {
  Button, Input,
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
} from '../../ui'
import { EnteteStock, BandeauxStock } from './EnteteStock'
import kitsApi from '../../features/stock/api/kitsApi'
import { messageServeur } from '../../features/stock/api/erreurs'
import { formatDateTime } from '../../lib/format'

/* ASTK229 — écran « Nomenclatures de stock (kits) » (contrat kits_stock.json).

   Créer, éditer (composants, quantités, taux de perte), supprimer (AlertDialog),
   dupliquer, remplacer un composant dans tous les kits, consulter révisions et
   disponibilité. Le formulaire renvoie TOUJOURS `taux_perte_pct` de chaque
   composant relu : enregistrer sans toucher rend le même objet serveur. Les
   400 serveur sont affichés mot pour mot. Un kit ne porte aucun prix propre
   (aucun prix d'achat ici). Distinct des kits d'OUTILLAGE (KitsSection,
   Paramètres — autre modèle). */

const liste = (d) => (Array.isArray(d) ? d : d?.results ?? [])
const selectCls = 'h-9 rounded-md border border-[var(--border)] bg-[var(--background)] px-2 text-sm'
const LIGNE_VIDE = { produit: '', quantite: '1', taux_perte_pct: '0' }
const FORM_VIDE = { id: null, nom: '', sku: '', description: '', composants: [{ ...LIGNE_VIDE }] }

const Carte = ({ titre, children }) => (
  <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
    {titre && <h2 className="mb-3 text-sm font-semibold">{titre}</h2>}
    {children}
  </section>
)

// Kit relu → formulaire (les valeurs serveur sont gardées telles quelles).
function versFormulaire(kit) {
  return {
    id: kit.id,
    nom: kit.nom ?? '',
    sku: kit.sku ?? '',
    description: kit.description ?? '',
    composants: (kit.composants ?? []).map((c) => ({
      produit: c.produit != null ? String(c.produit) : '',
      composant_kit: c.composant_kit ?? null,
      quantite: c.quantite ?? '1',
      taux_perte_pct: c.taux_perte_pct ?? '0',
    })),
  }
}

// Formulaire → corps POST/PUT : chaque composant porte son taux de perte.
function versCorps(form) {
  return {
    nom: form.nom.trim(),
    sku: form.sku.trim() || null,
    description: form.description,
    composants: form.composants
      .filter((c) => c.produit || c.composant_kit)
      .map((c) => ({
        ...(c.composant_kit ? { composant_kit: c.composant_kit } : { produit: Number(c.produit) }),
        quantite: c.quantite,
        taux_perte_pct: c.taux_perte_pct === '' ? '0' : c.taux_perte_pct,
      })),
  }
}

export default function KitsStock() {
  const [kits, setKits] = useState([])
  const [produits, setProduits] = useState([])
  const [form, setForm] = useState(null)
  const [aSupprimer, setASupprimer] = useState(null)
  const [revisions, setRevisions] = useState({})
  const [dispos, setDispos] = useState({})
  const [remplacement, setRemplacement] = useState({ ancien: '', nouveau: '', apercu: null })
  const [erreur, setErreur] = useState(null)
  const [info, setInfo] = useState(null)
  const [occupe, setOccupe] = useState(false)

  const charger = useCallback(async () => {
    try {
      const { data } = await kitsApi.listKits({ ordering: 'nom' })
      setKits(liste(data))
    } catch (err) { setErreur(messageServeur(err, 'Chargement des kits impossible.')) }
  }, [])

  useEffect(() => {
    Promise.resolve().then(charger)
    kitsApi.listProduits({ page_size: 1000 })
      .then((r) => setProduits(liste(r.data))).catch(() => {})
  }, [charger])

  const ouvrir = async (kit) => {
    setErreur(null); setInfo(null)
    try {
      const { data } = await kitsApi.getKit(kit.id)
      setForm(versFormulaire(data))
    } catch (err) { setErreur(messageServeur(err, 'Ouverture du kit impossible.')) }
  }

  const enregistrer = async (ev) => {
    ev.preventDefault()
    if (!form.nom.trim()) { setErreur('Nommez le kit.'); return }
    setOccupe(true); setErreur(null); setInfo(null)
    try {
      const corps = versCorps(form)
      if (form.id) await kitsApi.modifierKit(form.id, corps)
      else await kitsApi.creerKit(corps)
      setForm(null)
      setInfo('Kit enregistré.')
      await charger()
    } catch (err) { setErreur(messageServeur(err, "Le kit n'a pas pu être enregistré.")) } finally { setOccupe(false) }
  }

  const supprimer = async () => {
    const kit = aSupprimer
    setASupprimer(null); setErreur(null); setInfo(null)
    try {
      await kitsApi.supprimerKit(kit.id)
      setInfo(`Kit « ${kit.nom} » supprimé.`)
      await charger()
    } catch (err) { setErreur(messageServeur(err, 'Suppression du kit impossible.')) }
  }

  const dupliquer = async (kit) => {
    setErreur(null); setInfo(null)
    try {
      const { data } = await kitsApi.dupliquerKit(kit.id)
      setInfo(`Kit dupliqué : « ${data.nom} ».`)
      await charger()
    } catch (err) { setErreur(messageServeur(err, 'Duplication impossible.')) }
  }

  const voirRevisions = async (kit) => {
    try {
      const { data } = await kitsApi.revisions(kit.id)
      setRevisions((r) => ({ ...r, [kit.id]: data?.revisions ?? [] }))
    } catch (err) { setErreur(messageServeur(err, 'Révisions indisponibles.')) }
  }

  const voirDisponibilite = async (kit) => {
    try {
      const { data } = await kitsApi.disponibilite(kit.id)
      setDispos((d) => ({ ...d, [kit.id]: data }))
    } catch (err) { setErreur(messageServeur(err, 'Disponibilité indisponible.')) }
  }

  const remplacer = async (dryRun) => {
    if (!remplacement.ancien || !remplacement.nouveau) {
      setErreur('Choisissez le produit à remplacer et son remplaçant.'); return
    }
    setErreur(null); setInfo(null)
    try {
      const { data } = await kitsApi.remplacerComposant({
        produit_ancien: Number(remplacement.ancien),
        produit_nouveau: Number(remplacement.nouveau),
        ratio_quantite: 1,
        dry_run: dryRun,
      })
      if (dryRun) setRemplacement((r) => ({ ...r, apercu: data }))
      else {
        setRemplacement({ ancien: '', nouveau: '', apercu: null })
        setInfo(`Composant remplacé dans ${data.nb_total ?? 0} kit(s).`)
        await charger()
      }
    } catch (err) { setErreur(messageServeur(err, 'Remplacement impossible.')) }
  }

  const setLigne = (idx, patch) => setForm((f) => ({
    ...f, composants: f.composants.map((c, i) => (i === idx ? { ...c, ...patch } : c)),
  }))
  const optionsProduits = produits.map((p) => (
    <option key={p.id} value={p.id}>{p.nom}{p.sku ? ` (${p.sku})` : ''}</option>
  ))

  return (
    <div className="ui-root flex flex-col gap-4 px-4 py-5 sm:px-5">
      <EnteteStock
        icon={Boxes}
        title="Nomenclatures de stock (kits)"
        subtitle="Composition des kits vendables : composants, quantités, taux de perte."
        actions={!form && (
          <Button onClick={() => { setErreur(null); setInfo(null); setForm({ ...FORM_VIDE, composants: [{ ...LIGNE_VIDE }] }) }}>
            <Plus /> Nouveau kit
          </Button>
        )}
      />
      <BandeauxStock erreur={erreur} info={info} />

      {form && (
        <Carte titre={form.id ? `Modifier « ${form.nom} »` : 'Nouveau kit'}>
          <form onSubmit={enregistrer} noValidate className="flex flex-col gap-3">
            <div className="flex flex-wrap gap-2">
              <label className="flex flex-col gap-1 text-xs">
                <span>Nom</span>
                <Input aria-label="Nom du kit" value={form.nom} className="w-64"
                       onChange={(e) => setForm((f) => ({ ...f, nom: e.target.value }))} />
              </label>
              <label className="flex flex-col gap-1 text-xs">
                <span>Référence (SKU)</span>
                <Input aria-label="Référence du kit" value={form.sku} className="w-40"
                       onChange={(e) => setForm((f) => ({ ...f, sku: e.target.value }))} />
              </label>
            </div>
            <table className="w-full text-sm">
              <thead className="text-xs text-[var(--muted-foreground)]">
                <tr>
                  <th className="py-1 text-left">Composant</th>
                  <th className="py-1 text-left">Quantité</th>
                  <th className="py-1 text-left">Taux de perte (%)</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {form.composants.map((c, idx) => (
                  <tr key={idx}>
                    <td className="py-1">
                      {c.composant_kit ? (
                        <span>Sous-kit #{c.composant_kit}</span>
                      ) : (
                        <select aria-label={`Produit du composant ${idx + 1}`} className={selectCls}
                                value={c.produit} onChange={(e) => setLigne(idx, { produit: e.target.value })}>
                          <option value="">—</option>
                          {optionsProduits}
                        </select>
                      )}
                    </td>
                    <td className="py-1">
                      <Input aria-label={`Quantité du composant ${idx + 1}`} type="number" step="any"
                             className="w-24" value={c.quantite}
                             onChange={(e) => setLigne(idx, { quantite: e.target.value })} />
                    </td>
                    <td className="py-1">
                      <Input aria-label={`Taux de perte du composant ${idx + 1}`} type="number" step="any"
                             className="w-24" value={c.taux_perte_pct}
                             onChange={(e) => setLigne(idx, { taux_perte_pct: e.target.value })} />
                    </td>
                    <td className="py-1">
                      <Button type="button" size="sm" variant="ghost"
                              aria-label={`Retirer le composant ${idx + 1}`}
                              onClick={() => setForm((f) => ({ ...f, composants: f.composants.filter((_, i) => i !== idx) }))}>
                        <Trash2 className="size-4" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="outline" size="sm"
                      onClick={() => setForm((f) => ({ ...f, composants: [...f.composants, { ...LIGNE_VIDE }] }))}>
                <Plus /> Ajouter un composant
              </Button>
              <Button type="submit" disabled={occupe}>Enregistrer le kit</Button>
              <Button type="button" variant="ghost" onClick={() => setForm(null)}>Annuler</Button>
            </div>
          </form>
        </Carte>
      )}

      <Carte titre="Kits">
        {kits.length === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">Aucun kit.</p>
        ) : (
          <ul className="space-y-3 text-sm">
            {kits.map((k) => (
              <li key={k.id} className="rounded-md border border-[var(--border)] p-3">
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                  <strong>{k.nom}</strong>
                  {k.sku && <span className="text-[var(--muted-foreground)]">{k.sku}</span>}
                  <span>{k.nb_composants ?? (k.composants ?? []).length} composant(s)</span>
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <Button size="sm" variant="outline" onClick={() => ouvrir(k)}><Pencil className="size-4" /> Éditer</Button>
                  <Button size="sm" variant="outline" onClick={() => dupliquer(k)}><Copy className="size-4" /> Dupliquer</Button>
                  <Button size="sm" variant="outline" onClick={() => voirRevisions(k)}><History className="size-4" /> Révisions</Button>
                  <Button size="sm" variant="outline" onClick={() => voirDisponibilite(k)}>Disponibilité</Button>
                  <Button size="sm" variant="destructive" onClick={() => setASupprimer(k)}>
                    <Trash2 className="size-4" /> Supprimer
                  </Button>
                </div>
                {dispos[k.id] && (
                  <p className="mt-2 text-[var(--muted-foreground)]">
                    {dispos[k.id].kits_assemblables} kit(s) assemblable(s)
                    {(dispos[k.id].goulots ?? []).length > 0
                      && ` — goulot : ${dispos[k.id].goulots.map((g) => g.designation).join(', ')}`}
                  </p>
                )}
                {revisions[k.id] && (
                  revisions[k.id].length === 0 ? (
                    <p className="mt-2 text-[var(--muted-foreground)]">Aucune révision.</p>
                  ) : (
                    <ul className="mt-2 space-y-1 text-[var(--muted-foreground)]">
                      {revisions[k.id].map((r) => (
                        <li key={r.id}>
                          Révision {r.numero} — {formatDateTime(r.date_creation)}
                          {r.user_nom ? ` — ${r.user_nom}` : ''} — {(r.composition ?? []).length} composant(s)
                        </li>
                      ))}
                    </ul>
                  )
                )}
              </li>
            ))}
          </ul>
        )}
      </Carte>

      <Carte titre="Remplacer un composant dans tous les kits">
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-xs">
            <span>Produit remplacé</span>
            <select aria-label="Produit remplacé" className={selectCls} value={remplacement.ancien}
                    onChange={(e) => setRemplacement((r) => ({ ...r, ancien: e.target.value, apercu: null }))}>
              <option value="">—</option>
              {optionsProduits}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>Remplaçant</span>
            <select aria-label="Produit remplaçant" className={selectCls} value={remplacement.nouveau}
                    onChange={(e) => setRemplacement((r) => ({ ...r, nouveau: e.target.value, apercu: null }))}>
              <option value="">—</option>
              {optionsProduits}
            </select>
          </label>
          <Button variant="outline" onClick={() => remplacer(true)}>Aperçu</Button>
          {remplacement.apercu && (
            <Button onClick={() => remplacer(false)}>
              Remplacer dans {remplacement.apercu.nb_total ?? 0} kit(s)
            </Button>
          )}
        </div>
      </Carte>

      <AlertDialog open={!!aSupprimer} onOpenChange={(o) => { if (!o) setASupprimer(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer le kit ?</AlertDialogTitle>
            <AlertDialogDescription>
              Le kit « {aSupprimer?.nom} » et sa composition seront supprimés. Les produits du
              catalogue ne sont pas touchés.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction onClick={supprimer}>Supprimer</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
