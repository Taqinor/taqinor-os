import { useCallback, useEffect, useState } from 'react'
import { Link2, FileDown, Plus, Pencil, Upload } from 'lucide-react'
import {
  Card, Button, IconButton, Spinner, EmptyState, Badge, DataTable, Tabs,
  TabsList, TabsTrigger, TabsContent, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DialogFooter, Form, FormField, Input, Textarea,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
import { filenameFromResponse } from '../../../utils/downloadBlob'
import gestionProjetApi from '../../../api/gestionProjetApi'
import {
  errMessage, StatutRisque, StatutAction, PrioriteAction, StatutLot,
  CATEGORIES_RISQUE, TYPES_DOC, CIBLE_TYPES,
} from '../constants'
import ProjetPicker from '../components/ProjetPicker'
import RiskHeatmap from '../components/RiskHeatmap'

// WIR87 — le carnet lit/écrit désormais le référentiel sous-traitant UNIFIÉ
// DC34 (`installations/sous-traitants/` = stock.Fournisseur type=service +
// SousTraitantProfile), jamais `gestion_projet.SousTraitant` (régression DC34
// constatée par ARC22). Miroir de `stock.SousTraitantProfile.Metier`.
// source-choix: stock.SousTraitantProfile.metier
const METIERS_SOUS_TRAITANT = [
  { value: 'terrassement', label: 'Terrassement' },
  { value: 'genie_civil', label: 'Génie civil' },
  { value: 'electricite', label: 'Électricité' },
  { value: 'levage', label: 'Levage' },
  { value: 'transport', label: 'Transport' },
  { value: 'autre', label: 'Autre' },
]

// ── Dialog création/édition — carnet de sous-traitants (master DC34) ───────
function SousTraitantForm({ sousTraitant, onClose, onSaved }) {
  const isNew = !sousTraitant?.id
  const [fields, setFields] = useState({
    raison_sociale: sousTraitant?.raison_sociale ?? '',
    metier: sousTraitant?.metier ?? 'autre',
    contact_nom: sousTraitant?.contact_nom ?? '',
    telephone: sousTraitant?.telephone ?? '',
    email: sousTraitant?.email ?? '',
    actif: sousTraitant?.actif ?? true,
  })
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const setField = (k, v) => setFields((f) => ({ ...f, [k]: v }))

  const submit = async (ev) => {
    ev.preventDefault()
    if (!fields.raison_sociale.trim()) { setError('La raison sociale est requise.'); return }
    setSaving(true)
    setError(null)
    try {
      const payload = {
        raison_sociale: fields.raison_sociale.trim(),
        metier: fields.metier,
        contact_nom: fields.contact_nom.trim() || null,
        telephone: fields.telephone.trim() || null,
        email: fields.email.trim() || null,
        actif: fields.actif,
      }
      if (isNew) await gestionProjetApi.createSousTraitantMaster(payload)
      else await gestionProjetApi.updateSousTraitantMaster(sousTraitant.id, payload)
      onSaved?.()
      onClose()
    } catch (err) {
      setError(errMessage(err, "L'enregistrement a échoué."))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{isNew ? 'Nouveau sous-traitant' : `Sous-traitant — ${sousTraitant.raison_sociale}`}</DialogTitle>
          <DialogDescription>
            Référentiel unifié (DC34) — le même que la fiche fournisseur stock. Donnée interne.
          </DialogDescription>
        </DialogHeader>
        <Form onSubmit={submit} className="gap-4">
          <FormField label="Raison sociale" required htmlFor="st-nom" fullWidth>
            <Input id="st-nom" value={fields.raison_sociale}
                   onChange={(e) => setField('raison_sociale', e.target.value)} />
          </FormField>
          <FormField label="Métier" htmlFor="st-metier">
            <Select value={fields.metier} onValueChange={(v) => setField('metier', v)}>
              <SelectTrigger id="st-metier"><SelectValue /></SelectTrigger>
              <SelectContent>
                {METIERS_SOUS_TRAITANT.map((m) => (
                  <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormField>
          <FormField label="Contact" htmlFor="st-contact">
            <Input id="st-contact" value={fields.contact_nom}
                   onChange={(e) => setField('contact_nom', e.target.value)} />
          </FormField>
          <FormField label="Téléphone" htmlFor="st-tel">
            <Input id="st-tel" value={fields.telephone}
                   onChange={(e) => setField('telephone', e.target.value)} />
          </FormField>
          <FormField label="Email" htmlFor="st-email">
            <Input id="st-email" type="email" value={fields.email}
                   onChange={(e) => setField('email', e.target.value)} />
          </FormField>
          <FormField label="Statut" htmlFor="st-actif">
            <Select value={fields.actif ? '1' : '0'} onValueChange={(v) => setField('actif', v === '1')}>
              <SelectTrigger id="st-actif"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="1">Actif</SelectItem>
                <SelectItem value="0">Inactif</SelectItem>
              </SelectContent>
            </Select>
          </FormField>
          {error && (
            <div role="alert" className="sm:col-span-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
          <DialogFooter className="sm:col-span-2">
            <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
            <Button type="submit" loading={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
          </DialogFooter>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

/* ── WIR203 — Écriture des 6 ressources UX42 ──────────────────────────────────
   L'onglet était 100 % lecture seule : 16 fonctions CRUD de `gestionProjetApi`
   (risques, actions, comptes-rendus, documents + dépôt de version,
   commentaires, lots de sous-traitance) n'avaient AUCUN appelant — on pouvait
   consulter un registre de risques qu'aucun écran ne permettait de remplir.
   `projet` est TOUJOURS pré-rempli depuis le projet sélectionné (jamais saisi),
   et `company`/`auteur`/`criticite` restent posés côté serveur. Après chaque
   écriture, la page recharge — donc la matrice P × I est recalculée par le
   serveur, jamais dérivée côté client. */

const STATUTS_RISQUE_OPT = [
  { value: 'ouvert', label: 'Ouvert' },
  { value: 'surveille', label: 'Surveillé' },
  { value: 'maitrise', label: 'Maîtrisé' },
  { value: 'clos', label: 'Clos' },
]
const STATUTS_ACTION_OPT = [
  { value: 'a_faire', label: 'À faire' },
  { value: 'en_cours', label: 'En cours' },
  { value: 'fait', label: 'Fait' },
  { value: 'annule', label: 'Annulé' },
]
const PRIORITES_ACTION_OPT = [
  { value: 'basse', label: 'Basse' },
  { value: 'moyenne', label: 'Moyenne' },
  { value: 'haute', label: 'Haute' },
]
const STATUTS_LOT_OPT = [
  { value: 'prevu', label: 'Prévu' },
  { value: 'en_cours', label: 'En cours' },
  { value: 'receptionne', label: 'Réceptionné' },
  { value: 'annule', label: 'Annulé' },
]

/* Spécification déclarative des 6 formulaires : titre, champs, payload et
   appels API. Une seule mécanique de dialogue au lieu de six copies. */
const SPECS = {
  risque: {
    titre: 'risque',
    defauts: { libelle: '', categorie: 'technique', probabilite: '3', impact: '3', statut: 'ouvert', mitigation: '' },
    champs: [
      { k: 'libelle', label: 'Libellé', required: true },
      { k: 'categorie', label: 'Catégorie', options: CATEGORIES_RISQUE },
      { k: 'probabilite', label: 'Probabilité (1–5)', type: 'number' },
      { k: 'impact', label: 'Impact (1–5)', type: 'number' },
      { k: 'statut', label: 'Statut', options: STATUTS_RISQUE_OPT },
      { k: 'mitigation', label: 'Mitigation', textarea: true },
    ],
    // `criticite` est CALCULÉE serveur : jamais envoyée.
    payload: (f, projetId) => ({
      projet: projetId, libelle: f.libelle.trim(), categorie: f.categorie,
      probabilite: Number(f.probabilite) || 1, impact: Number(f.impact) || 1,
      statut: f.statut, mitigation: f.mitigation || '',
    }),
    create: (d) => gestionProjetApi.createRisque(d),
    update: (id, d) => gestionProjetApi.updateRisque(id, d),
  },
  action: {
    titre: 'action',
    defauts: { libelle: '', priorite: 'moyenne', statut: 'a_faire', echeance: '', description: '' },
    champs: [
      { k: 'libelle', label: 'Libellé', required: true },
      { k: 'priorite', label: 'Priorité', options: PRIORITES_ACTION_OPT },
      { k: 'statut', label: 'Statut', options: STATUTS_ACTION_OPT },
      { k: 'echeance', label: 'Échéance', type: 'date' },
      { k: 'description', label: 'Description', textarea: true },
    ],
    payload: (f, projetId) => ({
      projet: projetId, libelle: f.libelle.trim(), priorite: f.priorite,
      statut: f.statut, echeance: f.echeance || null,
      description: f.description || '',
    }),
    create: (d) => gestionProjetApi.createAction(d),
    update: (id, d) => gestionProjetApi.updateAction(id, d),
  },
  cr: {
    titre: 'compte-rendu',
    defauts: { titre: '', date_reunion: '', lieu: '', ordre_du_jour: '', decisions: '' },
    champs: [
      { k: 'titre', label: 'Titre', required: true },
      { k: 'date_reunion', label: 'Date de réunion', type: 'date' },
      { k: 'lieu', label: 'Lieu' },
      { k: 'ordre_du_jour', label: 'Ordre du jour', textarea: true },
      { k: 'decisions', label: 'Décisions', textarea: true },
    ],
    // `redacteur` est posé côté serveur — jamais envoyé.
    payload: (f, projetId) => ({
      projet: projetId, titre: f.titre.trim(),
      date_reunion: f.date_reunion || null, lieu: f.lieu || '',
      ordre_du_jour: f.ordre_du_jour || '', decisions: f.decisions || '',
    }),
    create: (d) => gestionProjetApi.createCompteRendu(d),
    update: (id, d) => gestionProjetApi.updateCompteRendu(id, d),
  },
  document: {
    titre: 'document',
    defauts: { nom: '', type_doc: 'plan', description: '' },
    champs: [
      { k: 'nom', label: 'Nom', required: true },
      { k: 'type_doc', label: 'Type', options: TYPES_DOC },
      { k: 'description', label: 'Description', textarea: true },
    ],
    // `derniere_version` est posée serveur au dépôt : jamais envoyée ici.
    payload: (f, projetId) => ({
      projet: projetId, nom: f.nom.trim(), type_doc: f.type_doc,
      description: f.description || '',
    }),
    create: (d) => gestionProjetApi.createDocument(d),
  },
  commentaire: {
    titre: 'commentaire',
    defauts: { texte: '', cible_type: 'projet', cible_id: '' },
    champs: [
      { k: 'texte', label: 'Commentaire', required: true, textarea: true },
      { k: 'cible_type', label: 'Cible', options: CIBLE_TYPES },
      { k: 'cible_id', label: 'Id de la cible (optionnel)', type: 'number' },
    ],
    // `auteur` est posé côté serveur — jamais envoyé.
    payload: (f, projetId) => ({
      projet: projetId, texte: f.texte.trim(), cible_type: f.cible_type,
      cible_id: f.cible_id ? Number(f.cible_id) : null,
    }),
    create: (d) => gestionProjetApi.createCommentaire(d),
  },
  lot: {
    titre: 'lot de sous-traitance',
    defauts: { libelle: '', sous_traitant: '', montant: '', statut: 'prevu', date_debut: '', date_fin: '' },
    champs: [
      { k: 'libelle', label: 'Libellé', required: true },
      { k: 'sous_traitant', label: 'Sous-traitant', source: 'sousTraitants' },
      { k: 'montant', label: 'Montant (interne)', type: 'number' },
      { k: 'statut', label: 'Statut', options: STATUTS_LOT_OPT },
      { k: 'date_debut', label: 'Début', type: 'date' },
      { k: 'date_fin', label: 'Fin', type: 'date' },
    ],
    payload: (f, projetId) => ({
      projet: projetId, libelle: f.libelle.trim(),
      sous_traitant: f.sous_traitant ? Number(f.sous_traitant) : null,
      montant: f.montant || null, statut: f.statut,
      date_debut: f.date_debut || null, date_fin: f.date_fin || null,
    }),
    create: (d) => gestionProjetApi.createLotSousTraitance(d),
    update: (id, d) => gestionProjetApi.updateLotSousTraitance(id, d),
  },
}

function RessourceForm({ kind, projetId, initial, sousTraitants, onClose, onSaved }) {
  const spec = SPECS[kind]
  const isNew = !initial?.id
  const [fields, setFields] = useState(() => {
    const base = { ...spec.defauts }
    Object.keys(base).forEach((k) => {
      const v = initial?.[k]
      if (v !== undefined && v !== null) base[k] = String(v)
    })
    return base
  })
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const setField = (k, v) => setFields((f) => ({ ...f, [k]: v }))

  const submit = async (ev) => {
    ev.preventDefault()
    const requis = spec.champs.find((c) => c.required)
    if (requis && !String(fields[requis.k] || '').trim()) {
      setError(`${requis.label} est requis.`)
      return
    }
    setSaving(true)
    setError(null)
    try {
      const payload = spec.payload(fields, projetId)
      if (isNew) await spec.create(payload)
      else await spec.update(initial.id, payload)
      onSaved?.()
      onClose()
    } catch (err) {
      setError(errMessage(err, "L'enregistrement a échoué."))
    } finally { setSaving(false) }
  }

  const listes = { sousTraitants }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{isNew ? `Nouveau ${spec.titre}` : `Modifier le ${spec.titre}`}</DialogTitle>
          <DialogDescription>
            Le projet sélectionné est pré-rempli ; la société et les champs
            dérivés sont posés côté serveur.
          </DialogDescription>
        </DialogHeader>
        <Form onSubmit={submit} className="gap-4">
          {spec.champs.map((c) => (
            <FormField key={c.k} label={c.label} required={c.required}
                       htmlFor={`wr-${kind}-${c.k}`} fullWidth={Boolean(c.textarea)}>
              {c.options ? (
                <Select value={fields[c.k]} onValueChange={(v) => setField(c.k, v)}>
                  <SelectTrigger id={`wr-${kind}-${c.k}`}><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {c.options.map((o) => (
                      <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : c.source ? (
                <Select value={fields[c.k]} onValueChange={(v) => setField(c.k, v)}>
                  <SelectTrigger id={`wr-${kind}-${c.k}`}><SelectValue placeholder="— Choisir —" /></SelectTrigger>
                  <SelectContent>
                    {(listes[c.source] ?? []).map((o) => (
                      <SelectItem key={o.id} value={String(o.id)}>
                        {o.raison_sociale || o.nom}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : c.textarea ? (
                <Textarea id={`wr-${kind}-${c.k}`} rows={3} value={fields[c.k]}
                          onChange={(e) => setField(c.k, e.target.value)} />
              ) : (
                <Input id={`wr-${kind}-${c.k}`} type={c.type || 'text'}
                       step={c.type === 'number' ? 'any' : undefined}
                       value={fields[c.k]}
                       onChange={(e) => setField(c.k, e.target.value)} />
              )}
            </FormField>
          ))}
          {error && (
            <div role="alert" className="sm:col-span-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
          <DialogFooter className="sm:col-span-2">
            <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
            <Button type="submit" loading={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
          </DialogFooter>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

/* WIR203 — dépôt d'une RÉVISION de document (multipart). Le numéro de version
   et l'auteur sont posés côté serveur ; le client n'envoie que le fichier. */
function DeposerVersionForm({ document: doc, onClose, onSaved }) {
  const [fichier, setFichier] = useState(null)
  const [commentaire, setCommentaire] = useState('')
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const submit = async (ev) => {
    ev.preventDefault()
    if (!fichier) { setError('Un fichier est obligatoire.'); return }
    setSaving(true)
    setError(null)
    try {
      await gestionProjetApi.deposerVersionDocument(doc.id, { fichier, commentaire })
      onSaved?.()
      onClose()
    } catch (err) {
      setError(errMessage(err, 'Le dépôt a échoué.'))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Déposer une version — {doc.nom}</DialogTitle>
        </DialogHeader>
        <Form onSubmit={submit} className="gap-4">
          <FormField label="Fichier" required htmlFor="wr-doc-fichier" fullWidth>
            <input id="wr-doc-fichier" type="file"
                   onChange={(e) => setFichier(e.target.files?.[0] ?? null)} />
          </FormField>
          <FormField label="Commentaire de révision" htmlFor="wr-doc-com" fullWidth>
            <Input id="wr-doc-com" value={commentaire}
                   onChange={(e) => setCommentaire(e.target.value)} />
          </FormField>
          {error && (
            <div role="alert" className="sm:col-span-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
          <DialogFooter className="sm:col-span-2">
            <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
            <Button type="submit" loading={saving}>{saving ? 'Dépôt…' : 'Déposer'}</Button>
          </DialogFooter>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

/* UX42 — Risques, actions & CR : registre des risques, plan d'actions,
   comptes-rendus, documents/commentaires, modèles de projet, sous-traitants &
   lots. Tout est groupé sous onglets. Le `montant` des lots est INTERNE. */

const CAT_RISQUE = Object.fromEntries(CATEGORIES_RISQUE.map((c) => [c.value, c.label]))
const TYPE_DOC = Object.fromEntries(TYPES_DOC.map((c) => [c.value, c.label]))

export default function RisquesPage() {
  const [projetId, setProjetId] = useState('')
  const [state, setState] = useState({
    risques: [], actions: [], crs: [], documents: [], commentaires: [],
    modeles: [], sousTraitants: [], lots: [],
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [matrice, setMatrice] = useState(null)
  const [csatBusy, setCsatBusy] = useState(false)
  const [pdfBusy, setPdfBusy] = useState(false)
  // WIR87 — édition du carnet (master DC34) : null = fermé, {} = création,
  // objet = édition.
  const [stEditing, setStEditing] = useState(null)
  // WIR203 — écriture des 6 ressources : { kind, initial } ; null = fermé.
  const [editing, setEditing] = useState(null)
  const [deposerFor, setDeposerFor] = useState(null)

  const asList = (r) => (Array.isArray(r.data) ? r.data : r.data?.results ?? [])

  // WIR87 — le carnet lit le référentiel UNIFIÉ DC34 (`installations/
  // sous-traitants/`), plus jamais `gestion_projet.SousTraitant` (régression
  // DC34, ARC22) : société-scopé, indépendant du projet, rechargé seul après
  // création/édition (pas besoin de recharger tout le reste de la page).
  const reloadSousTraitants = useCallback(async () => {
    const st = await gestionProjetApi.getSousTraitantsMaster()
    setState((s) => ({ ...s, sousTraitants: asList(st) }))
  }, [])

  const load = useCallback(async (pid) => {
    setLoading(true)
    setError(null)
    try {
      // Modèles & sous-traitants sont société-scopés (indépendants du projet).
      const params = pid ? { projet: pid } : undefined
      const [ri, ac, cr, doc, com, mod, st, lo, mat] = await Promise.all([
        pid ? gestionProjetApi.getRisques(params) : Promise.resolve({ data: [] }),
        pid ? gestionProjetApi.getActions(params) : Promise.resolve({ data: [] }),
        pid ? gestionProjetApi.getComptesRendus(params) : Promise.resolve({ data: [] }),
        pid ? gestionProjetApi.getDocuments(params) : Promise.resolve({ data: [] }),
        pid ? gestionProjetApi.getCommentaires(params) : Promise.resolve({ data: [] }),
        gestionProjetApi.getModeles(),
        gestionProjetApi.getSousTraitantsMaster(),
        pid ? gestionProjetApi.getLotsSousTraitance(params) : Promise.resolve({ data: [] }),
        pid ? gestionProjetApi.getMatriceRisques(pid).catch(() => ({ data: null })) : Promise.resolve({ data: null }),
      ])
      setState({
        risques: asList(ri), actions: asList(ac), crs: asList(cr),
        documents: asList(doc), commentaires: asList(com), modeles: asList(mod),
        sousTraitants: asList(st), lots: asList(lo),
      })
      setMatrice(mat.data)
    } catch (err) {
      setError(errMessage(err, 'Chargement impossible.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let alive = true
    ;(async () => { if (alive) await load(projetId) })()
    return () => { alive = false }
  }, [projetId, load])

  // ZPRJ7 — Lien tokenisé d'évaluation CSAT (idempotent, à envoyer au client
  // à la clôture du projet). Copié au presse-papier.
  const copierLienEvaluation = async () => {
    setCsatBusy(true)
    try {
      const res = await gestionProjetApi.getLienEvaluation(projetId)
      const base = (import.meta.env.VITE_PUBLIC_SITE_URL || 'https://taqinor.ma').replace(/\/+$/, '')
      const url = `${base}/gestion-projet/portail/evaluation/${res.data.token}/`
      try { await navigator.clipboard?.writeText(url) } catch { /* presse-papier indispo */ }
      toast.success('Lien d\'évaluation CSAT copié.')
    } catch (err) {
      toast.error(errMessage(err, 'Génération du lien impossible.'))
    } finally {
      setCsatBusy(false)
    }
  }

  // ZPRJ9 — PDF interne « Point d'avancement projet » (WeasyPrint legacy,
  // jamais le moteur premium /proposal réservé aux devis client — règle #4).
  const telechargerRapportPdf = async () => {
    setPdfBusy(true)
    try {
      const res = await gestionProjetApi.getRapportAvancementPdf(projetId)
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.target = '_blank'
      a.rel = 'noopener'
      a.download = filenameFromResponse(res, `avancement-projet-${projetId}.pdf`)
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      setTimeout(() => URL.revokeObjectURL(url), 10000)
    } catch (err) {
      toast.error(errMessage(err, 'Génération du PDF impossible.'))
    } finally {
      setPdfBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight">Risques, actions & CR</h1>
          <p className="text-sm text-muted-foreground">Registre des risques, plan d'actions, réunions, documents, modèles & sous-traitance.</p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <ProjetPicker value={projetId} onChange={setProjetId} />
          {projetId && (
            <>
              <Button size="sm" variant="outline" disabled={csatBusy} onClick={copierLienEvaluation} title="Copier le lien d'évaluation CSAT (ZPRJ7)">
                <Link2 className="size-3.5" aria-hidden="true" /> Lien CSAT
              </Button>
              <Button size="sm" variant="outline" disabled={pdfBusy} onClick={telechargerRapportPdf} title="Télécharger le rapport d'avancement PDF (ZPRJ9)">
                <FileDown className="size-3.5" aria-hidden="true" /> Rapport PDF
              </Button>
            </>
          )}
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center p-10"><Spinner /></div>
      ) : error ? (
        <EmptyState title="Erreur" description={error} action={<Button variant="outline" onClick={() => load(projetId)}>Réessayer</Button>} />
      ) : (
        <Tabs defaultValue="risques">
          <TabsList className="flex-wrap">
            <TabsTrigger value="risques">Risques</TabsTrigger>
            <TabsTrigger value="heatmap">Matrice P × I</TabsTrigger>
            <TabsTrigger value="actions">Actions</TabsTrigger>
            <TabsTrigger value="cr">Comptes-rendus</TabsTrigger>
            <TabsTrigger value="documents">Documents</TabsTrigger>
            <TabsTrigger value="modeles">Modèles</TabsTrigger>
            <TabsTrigger value="sous-traitance">Sous-traitance</TabsTrigger>
          </TabsList>

          <TabsContent value="risques">
            <Card className="p-4 sm:p-5">
              <EnTeteEcriture titre="Registre des risques" libelle="Nouveau risque"
                              projetId={projetId} onClick={() => setEditing({ kind: 'risque' })} />
              <DataTable
                data={state.risques}
                rowActions={(r) => [
                  { id: 'edit', label: 'Modifier', icon: Pencil, onClick: () => setEditing({ kind: 'risque', initial: r }) },
                ]}
                getRowId={(r) => r.id}
                columns={[
                  { id: 'libelle', header: 'Risque', accessor: (r) => r.libelle, cell: (v) => <span className="font-medium">{v}</span> },
                  { id: 'categorie', header: 'Catégorie', searchable: false, accessor: (r) => CAT_RISQUE[r.categorie] ?? r.categorie },
                  { id: 'proba', header: 'P', align: 'right', numeric: true, searchable: false, accessor: (r) => r.probabilite },
                  { id: 'impact', header: 'I', align: 'right', numeric: true, searchable: false, accessor: (r) => r.impact },
                  { id: 'criticite', header: 'Criticité', align: 'right', numeric: true, searchable: false, accessor: (r) => r.criticite, cell: (v) => <Badge tone={v >= 15 ? 'danger' : v >= 8 ? 'warning' : 'neutral'}>{v}</Badge> },
                  { id: 'statut', header: 'Statut', searchable: false, accessor: (r) => r.statut, cell: (v) => <StatutRisque status={v} /> },
                ]}
                exportName="risques"
                emptyTitle="Aucun risque"
                emptyDescription={projetId ? 'Aucun risque enregistré pour ce projet.' : 'Sélectionnez un projet.'}
              />
            </Card>
          </TabsContent>

          <TabsContent value="heatmap">
            <Card className="p-4 sm:p-5">
              {!projetId ? (
                <EmptyState title="Aucun projet sélectionné" description="Choisissez un projet pour afficher sa matrice des risques." />
              ) : (
                <RiskHeatmap grille={matrice?.grille ?? []} topRisques={matrice?.top_risques ?? []} />
              )}
            </Card>
          </TabsContent>

          <TabsContent value="actions">
            <Card className="p-4 sm:p-5">
              <EnTeteEcriture titre="Plan d’actions" libelle="Nouvelle action"
                              projetId={projetId} onClick={() => setEditing({ kind: 'action' })} />
              <DataTable
                data={state.actions}
                rowActions={(a) => [
                  { id: 'edit', label: 'Modifier', icon: Pencil, onClick: () => setEditing({ kind: 'action', initial: a }) },
                ]}
                getRowId={(a) => a.id}
                columns={[
                  { id: 'libelle', header: 'Action', accessor: (a) => a.libelle, cell: (v) => <span className="font-medium">{v}</span> },
                  { id: 'priorite', header: 'Priorité', searchable: false, accessor: (a) => a.priorite, cell: (v) => <PrioriteAction status={v} /> },
                  { id: 'statut', header: 'Statut', searchable: false, accessor: (a) => a.statut, cell: (v) => <StatutAction status={v} /> },
                  { id: 'echeance', header: 'Échéance', searchable: false, accessor: (a) => a.echeance || '', cell: (v) => v ? formatDate(v) : '—' },
                ]}
                exportName="actions"
                emptyTitle="Aucune action"
                emptyDescription={projetId ? 'Aucune action pour ce projet.' : 'Sélectionnez un projet.'}
              />
            </Card>
          </TabsContent>

          <TabsContent value="cr">
            <Card className="p-4 sm:p-5">
              <EnTeteEcriture titre="Comptes-rendus de réunion" libelle="Nouveau compte-rendu"
                              projetId={projetId} onClick={() => setEditing({ kind: 'cr' })} />
              {state.crs.length ? (
                <ul className="flex flex-col gap-2">
                  {state.crs.map((c) => (
                    <li key={c.id} className="rounded-md border border-border p-3 text-sm">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{c.titre}</span>
                        <span className="ml-auto text-xs text-muted-foreground">{c.date_reunion ? formatDate(c.date_reunion) : ''}</span>
                      </div>
                      {c.lieu && <p className="text-xs text-muted-foreground">Lieu : {c.lieu}</p>}
                      {c.decisions && <p className="mt-1 whitespace-pre-wrap text-sm">{c.decisions}</p>}
                      <div className="mt-2 flex justify-end">
                        <Button size="sm" variant="ghost"
                                onClick={() => setEditing({ kind: 'cr', initial: c })}>
                          <Pencil className="size-3.5" aria-hidden="true" /> Modifier
                        </Button>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : <EmptyState title="Aucun compte-rendu" description={projetId ? 'Aucune réunion enregistrée.' : 'Sélectionnez un projet.'} />}
            </Card>
          </TabsContent>

          <TabsContent value="documents">
            <Card className="p-4 sm:p-5">
              <EnTeteEcriture titre="Documents versionnés" libelle="Nouveau document"
                              projetId={projetId} onClick={() => setEditing({ kind: 'document' })} />
              <DataTable
                data={state.documents}
                rowActions={(d) => [
                  { id: 'deposer', label: 'Déposer une version', icon: Upload, onClick: () => setDeposerFor(d) },
                ]}
                getRowId={(d) => d.id}
                columns={[
                  { id: 'nom', header: 'Document', accessor: (d) => d.nom, cell: (v) => <span className="font-medium">{v}</span> },
                  { id: 'type', header: 'Type', searchable: false, accessor: (d) => TYPE_DOC[d.type_doc] ?? d.type_doc, cell: (v) => <Badge tone="info">{v}</Badge> },
                  { id: 'version', header: 'Version', align: 'right', numeric: true, searchable: false, accessor: (d) => d.derniere_version ?? 0 },
                  { id: 'nb', header: 'Révisions', align: 'right', numeric: true, searchable: false, accessor: (d) => (d.versions ?? []).length },
                ]}
                exportName="documents"
                emptyTitle="Aucun document"
                emptyDescription={projetId ? 'Aucun document versionné.' : 'Sélectionnez un projet.'}
              />
              <div className="mt-4 border-t border-border pt-3">
                <EnTeteEcriture titre="Commentaires" libelle="Nouveau commentaire"
                                projetId={projetId} onClick={() => setEditing({ kind: 'commentaire' })} />
              </div>
              {state.commentaires.length > 0 && (
                <div className="mt-2">
                  <p className="mb-2 text-sm font-medium">Commentaires récents</p>
                  <ul className="flex flex-col gap-1 text-sm">
                    {state.commentaires.slice(0, 8).map((cm) => (
                      <li key={cm.id} className="flex gap-2">
                        <span className="text-muted-foreground">{cm.auteur_nom || '—'} :</span>
                        <span>{cm.texte}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </Card>
          </TabsContent>

          <TabsContent value="modeles">
            <Card className="p-4 sm:p-5">
              <DataTable
                data={state.modeles}
                getRowId={(m) => m.id}
                columns={[
                  { id: 'nom', header: 'Modèle', accessor: (m) => m.nom, cell: (v) => <span className="font-medium">{v}</span> },
                  { id: 'type', header: 'Type installation', searchable: false, accessor: (m) => m.type_installation_display || m.type_installation },
                  { id: 'nb', header: 'Tâches-types', align: 'right', numeric: true, searchable: false, accessor: (m) => m.nb_taches ?? (m.taches ?? []).length },
                  { id: 'actif', header: 'Actif', searchable: false, accessor: (m) => m.actif, cell: (v) => <Badge tone={v ? 'success' : 'neutral'}>{v ? 'Actif' : 'Inactif'}</Badge> },
                ]}
                exportName="modeles-projet"
                emptyTitle="Aucun modèle"
                emptyDescription="Créez des modèles de projet par type d'installation."
              />
            </Card>
          </TabsContent>

          <TabsContent value="sous-traitance">
            <Card className="p-4 sm:p-5">
              <div className="mb-2 flex items-center justify-between">
                <h3 className="font-display text-base font-semibold">Carnet de sous-traitants</h3>
                <Button size="sm" onClick={() => setStEditing({})}>
                  <Plus className="size-4" /> Nouveau sous-traitant
                </Button>
              </div>
              {/* WIR87 — référentiel unifié DC34 (stock.Fournisseur type=service +
                  SousTraitantProfile) : plus jamais `gestion_projet.SousTraitant`
                  (régression DC34 constatée par ARC22). Le champ `metier` (enum
                  fermé côté master) remplace le `specialite` texte libre local. */}
              <DataTable
                data={state.sousTraitants}
                getRowId={(s) => s.id}
                onRowClick={(s) => setStEditing(s)}
                columns={[
                  { id: 'raison_sociale', header: 'Sous-traitant', accessor: (s) => s.raison_sociale, cell: (v) => <span className="font-medium">{v}</span> },
                  { id: 'metier', header: 'Métier', accessor: (s) => s.metier_display || s.metier || '—' },
                  { id: 'contact', header: 'Contact', accessor: (s) => s.contact_nom || '—' },
                  { id: 'tel', header: 'Téléphone', searchable: false, accessor: (s) => s.telephone || '—' },
                  { id: 'actif', header: 'Actif', searchable: false, accessor: (s) => s.actif, cell: (v) => <Badge tone={v ? 'success' : 'neutral'}>{v ? 'Actif' : 'Inactif'}</Badge> },
                  { id: 'actions', header: '', searchable: false, sortable: false,
                    cell: (_v, s) => (
                      <IconButton size="sm" variant="ghost" label="Modifier"
                                  onClick={(e) => { e.stopPropagation(); setStEditing(s) }}>
                        <Pencil className="size-4" aria-hidden="true" />
                      </IconButton>
                    ) },
                ]}
                exportName="sous-traitants"
                emptyTitle="Aucun sous-traitant"
                emptyDescription="Ajoutez des sous-traitants avec « Nouveau sous-traitant »."
              />
              <div className="mb-2 mt-5 flex items-center justify-between">
                <h3 className="font-display text-base font-semibold">Lots de sous-traitance</h3>
                <Button size="sm" disabled={!projetId} onClick={() => setEditing({ kind: 'lot' })}>
                  <Plus className="size-4" aria-hidden="true" /> Nouveau lot
                </Button>
              </div>
              <DataTable
                data={state.lots}
                getRowId={(l) => l.id}
                rowActions={(l) => [
                  { id: 'edit', label: 'Modifier', icon: Pencil, onClick: () => setEditing({ kind: 'lot', initial: l }) },
                ]}
                columns={[
                  { id: 'libelle', header: 'Lot', accessor: (l) => l.libelle, cell: (v) => <span className="font-medium">{v}</span> },
                  { id: 'st', header: 'Sous-traitant', accessor: (l) => l.sous_traitant_nom || `#${l.sous_traitant}` },
                  { id: 'montant', header: 'Montant (interne)', align: 'right', numeric: true, searchable: false, accessor: (l) => Number(l.montant ?? 0), cell: (_v, l) => (l.montant ? formatMAD(l.montant) : '—') },
                  { id: 'statut', header: 'Statut', searchable: false, accessor: (l) => l.statut, cell: (v) => <StatutLot status={v} /> },
                ]}
                exportName="lots-sous-traitance"
                emptyTitle="Aucun lot"
                emptyDescription={projetId ? 'Aucun lot confié pour ce projet.' : 'Sélectionnez un projet.'}
              />
            </Card>
          </TabsContent>
        </Tabs>
      )}

      {stEditing && (
        <SousTraitantForm sousTraitant={stEditing.id ? stEditing : null}
                          onClose={() => setStEditing(null)}
                          onSaved={reloadSousTraitants} />
      )}
      {/* WIR203 — après chaque écriture, `load(projetId)` recharge TOUT, y
          compris la matrice P × I : elle est recalculée par le serveur. */}
      {editing && (
        <RessourceForm
          kind={editing.kind}
          projetId={projetId}
          initial={editing.initial}
          sousTraitants={state.sousTraitants}
          onClose={() => setEditing(null)}
          onSaved={() => load(projetId)}
        />
      )}
      {deposerFor && (
        <DeposerVersionForm
          document={deposerFor}
          onClose={() => setDeposerFor(null)}
          onSaved={() => load(projetId)}
        />
      )}
    </div>
  )
}

/* WIR203 — en-tête d'une section écrivable : le bouton reste DÉSACTIVÉ tant
   qu'aucun projet n'est choisi (le `projet` est pré-rempli, jamais saisi). */
function EnTeteEcriture({ titre, libelle, projetId, onClick }) {
  return (
    <div className="mb-2 flex items-center justify-between">
      <h3 className="font-display text-base font-semibold">{titre}</h3>
      <Button size="sm" disabled={!projetId} onClick={onClick}>
        <Plus className="size-4" aria-hidden="true" /> {libelle}
      </Button>
    </div>
  )
}
