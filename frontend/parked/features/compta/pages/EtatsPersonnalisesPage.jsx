import { useEffect, useState } from 'react'
import { Plus, Trash2, PlayCircle } from 'lucide-react'
import { ListShell } from '../../../ui/module'
import { Button, EmptyState, Input, Label, Textarea, toast } from '../../../ui'
import { formatMAD } from '../../../lib/format'
import ComptaTable from '../ComptaTable'
import comptaApi from '../../../api/comptaApi'
import useComptaList from '../components/useComptaList.js'

/* ============================================================================
   WIR280 / WIR279 (XACC19) — États financiers PARAMÉTRABLES.
   ----------------------------------------------------------------------------
   Le modèle (`EtatPersonnalise` + `LigneEtatPersonnalise` à formule +
   `ColonneEtatPersonnalise` période/N-1/budget/écart %), la validation de
   formule et l'évaluation (`selectors.evaluer_etat_personnalise`) existaient
   côté services sans AUCUN écran. DISTINCT des états FIGÉS (GL/balance/CPC/
   bilan, `EtatsPage`) : ceci est un état ADDITIONNEL, entièrement défini en
   données par l'utilisateur — jamais fusionné avec les états figés.

   `evaluer/` renvoie EXACTEMENT la forme du contrat committé
   (`apps/compta/contract_samples/etat_personnalise_evaluer.json`) :
   `{etat, libelle, colonnes:[{id,libelle,type_colonne}],
   lignes:[{id,libelle,type_ligne,valeurs:{<id_colonne>: "montant"}}]}` — une
   ligne « titre » porte un `valeurs` VIDE (jamais des zéros inventés) ; les
   montants sont du TEXTE (Decimal côté serveur), affichés tels quels, jamais
   recalculés ici.
   ========================================================================== */

const TYPES_LIGNE = [
  ['titre', 'Titre de section'],
  ['total', 'Ligne calculée (formule)'],
]
const TYPES_COLONNE = [
  ['periode', 'Période'],
  ['comparatif_n1', 'Comparatif N-1'],
  ['budget', 'Budget'],
  ['ecart_pct', 'Écart % (vs colonne précédente)'],
]

const ligneVide = () => ({ libelle: '', type_ligne: 'total', formule: '' })
const colonneVide = () => ({ libelle: '', type_colonne: 'periode', date_debut: '', date_fin: '', budget: '' })

function messageErreur(err, repli) {
  const d = err?.response?.data
  return typeof d === 'string' ? d : (d?.detail || repli)
}

function listeDe(res) {
  return Array.isArray(res?.data) ? res.data : (res?.data?.results || [])
}

export default function EtatsPersonnalisesPage() {
  const list = useComptaList(comptaApi.etatsPersonnalises.list, undefined)
  const [budgets, setBudgets] = useState([])
  const [construction, setConstruction] = useState(false)
  const [libelle, setLibelle] = useState('')
  const [description, setDescription] = useState('')
  const [lignes, setLignes] = useState([ligneVide()])
  const [colonnes, setColonnes] = useState([colonneVide()])
  const [saving, setSaving] = useState(false)
  const [evalue, setEvalue] = useState(null)
  const [evaluating, setEvaluating] = useState(null)

  useEffect(() => {
    comptaApi.budgets.list().then((res) => setBudgets(listeDe(res))).catch(() => setBudgets([]))
  }, [])

  function resetConstruction() {
    setLibelle('')
    setDescription('')
    setLignes([ligneVide()])
    setColonnes([colonneVide()])
    setConstruction(false)
  }

  const majLigne = (index, patch) => setLignes(
    (prev) => prev.map((l, i) => (i === index ? { ...l, ...patch } : l)))
  const ajouterLigne = () => setLignes((prev) => [...prev, ligneVide()])
  const retirerLigne = (index) => setLignes((prev) => prev.filter((_, i) => i !== index))

  const majColonne = (index, patch) => setColonnes(
    (prev) => prev.map((c, i) => (i === index ? { ...c, ...patch } : c)))
  const ajouterColonne = () => setColonnes((prev) => [...prev, colonneVide()])
  const retirerColonne = (index) => setColonnes((prev) => prev.filter((_, i) => i !== index))

  const peutEnregistrer = libelle.trim()
    && lignes.every((l) => l.libelle.trim() && (l.type_ligne !== 'total' || l.formule.trim()))
    && colonnes.every((c) => c.libelle.trim())

  async function enregistrer(e) {
    e.preventDefault()
    if (!peutEnregistrer || saving) return
    setSaving(true)
    try {
      await comptaApi.etatsPersonnalises.create({
        libelle: libelle.trim(),
        description: description.trim(),
        lignes: lignes.map((l, ordre) => ({
          ordre,
          libelle: l.libelle.trim(),
          type_ligne: l.type_ligne,
          formule: l.type_ligne === 'total' ? l.formule.trim() : '',
        })),
        colonnes: colonnes.map((c, ordre) => ({
          ordre,
          libelle: c.libelle.trim(),
          type_colonne: c.type_colonne,
          date_debut: c.date_debut || null,
          date_fin: c.date_fin || null,
          budget: c.type_colonne === 'budget' ? (c.budget || null) : null,
        })),
      })
      toast.success('État personnalisé créé.')
      resetConstruction()
      list.reload()
    } catch (err) {
      toast.error(messageErreur(err, "Création de l'état impossible (formule invalide ?)."))
    } finally {
      setSaving(false)
    }
  }

  async function supprimer(id) {
    try {
      await comptaApi.etatsPersonnalises.remove(id)
      toast.success('État supprimé.')
      setEvalue((prev) => (prev?.etat === id ? null : prev))
      list.reload()
    } catch (err) {
      toast.error(messageErreur(err, 'Suppression impossible.'))
    }
  }

  async function evaluer(etat) {
    setEvaluating(etat.id)
    try {
      const res = await comptaApi.etatsPersonnalises.evaluer(etat.id)
      setEvalue(res.data)
    } catch (err) {
      toast.error(messageErreur(err, 'Évaluation impossible.'))
    } finally {
      setEvaluating(null)
    }
  }

  const columns = [
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
    { id: 'description', header: 'Description', accessor: (r) => r.description || '—' },
    { id: 'lignes', header: 'Lignes', searchable: false, accessor: (r) => (r.lignes || []).length },
    { id: 'colonnes', header: 'Colonnes', searchable: false, accessor: (r) => (r.colonnes || []).length },
  ]

  const rowActions = (row) => [
    {
      id: 'evaluer',
      label: evaluating === row.id ? 'Évaluation…' : 'Évaluer',
      icon: PlayCircle,
      onClick: () => evaluer(row),
    },
    { id: 'supprimer', label: 'Supprimer', icon: Trash2, onClick: () => supprimer(row.id) },
  ]

  // WIR280 — colonnes DYNAMIQUES (une par colonne de l'état), reprises telles
  // que renvoyées par le serveur (`evaluer/`) — jamais un axe recalculé côté
  // client. Une ligne « titre » n'affiche aucune valeur (jamais un 0 inventé).
  const evalueColonnes = evalue ? [
    { key: 'libelle', label: 'Ligne', cell: (l) => l.libelle },
    ...(evalue.colonnes || []).map((c) => ({
      key: `col-${c.id}`,
      label: c.libelle,
      align: 'right',
      numeric: true,
      cell: (l) => {
        if (l.type_ligne === 'titre') return ''
        const v = l.valeurs?.[String(c.id)]
        return v === undefined || v === null ? '—' : formatMAD(Number(v))
      },
    })),
  ] : []

  return (
    <div className="page">
      <div className="page-header">
        <h2>États paramétrables</h2>
        <div className="page-header-actions">
          <Button onClick={() => (construction ? resetConstruction() : setConstruction(true))}>
            <Plus /> {construction ? 'Annuler' : 'Nouvel état'}
          </Button>
        </div>
      </div>

      <ListShell
        hideHeader
        title="États personnalisés"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={rowActions}
        exportName="etats-personnalises"
        emptyTitle="Aucun état personnalisé"
        emptyDescription="Un état financier défini en données (lignes à formule + colonnes période/N-1/budget)."
      />

      {construction && (
        <form
          onSubmit={enregistrer}
          className="mt-4 flex flex-col gap-4 rounded-xl border border-border p-4"
        >
          <div className="flex flex-col gap-1">
            <Label htmlFor="etat-libelle" required>Libellé</Label>
            <Input id="etat-libelle" value={libelle} onChange={(e) => setLibelle(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="etat-description">Description</Label>
            <Textarea
              id="etat-description" value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <fieldset className="flex flex-col gap-2">
            <legend className="text-sm font-medium">Lignes</legend>
            {lignes.map((l, i) => (
              <div key={i} className="flex flex-wrap items-end gap-2">
                <div className="flex flex-col gap-1">
                  <Label htmlFor={`ligne-libelle-${i}`}>Libellé</Label>
                  <Input
                    id={`ligne-libelle-${i}`} value={l.libelle}
                    onChange={(e) => majLigne(i, { libelle: e.target.value })}
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <Label htmlFor={`ligne-type-${i}`}>Type</Label>
                  <select
                    id={`ligne-type-${i}`} value={l.type_ligne}
                    onChange={(e) => majLigne(i, { type_ligne: e.target.value })}
                    className="h-9 rounded-md border border-border bg-card px-3 text-sm"
                  >
                    {TYPES_LIGNE.map(([v, lbl]) => <option key={v} value={v}>{lbl}</option>)}
                  </select>
                </div>
                {l.type_ligne === 'total' && (
                  <div className="flex flex-col gap-1">
                    <Label htmlFor={`ligne-formule-${i}`}>Formule (ex. +70,+71,-60)</Label>
                    <Input
                      id={`ligne-formule-${i}`} value={l.formule}
                      onChange={(e) => majLigne(i, { formule: e.target.value })}
                    />
                  </div>
                )}
                <Button
                  type="button" variant="ghost" size="sm" onClick={() => retirerLigne(i)}
                  disabled={lignes.length <= 1}
                >
                  Retirer
                </Button>
              </div>
            ))}
            <div>
              <Button type="button" variant="outline" size="sm" onClick={ajouterLigne}>
                <Plus className="size-3.5" /> Ajouter une ligne
              </Button>
            </div>
          </fieldset>

          <fieldset className="flex flex-col gap-2">
            <legend className="text-sm font-medium">Colonnes</legend>
            {colonnes.map((c, i) => (
              <div key={i} className="flex flex-wrap items-end gap-2">
                <div className="flex flex-col gap-1">
                  <Label htmlFor={`colonne-libelle-${i}`}>Libellé</Label>
                  <Input
                    id={`colonne-libelle-${i}`} value={c.libelle}
                    onChange={(e) => majColonne(i, { libelle: e.target.value })}
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <Label htmlFor={`colonne-type-${i}`}>Type</Label>
                  <select
                    id={`colonne-type-${i}`} value={c.type_colonne}
                    onChange={(e) => majColonne(i, { type_colonne: e.target.value })}
                    className="h-9 rounded-md border border-border bg-card px-3 text-sm"
                  >
                    {TYPES_COLONNE.map(([v, lbl]) => <option key={v} value={v}>{lbl}</option>)}
                  </select>
                </div>
                {(c.type_colonne === 'periode' || c.type_colonne === 'comparatif_n1') && (
                  <>
                    <div className="flex flex-col gap-1">
                      <Label htmlFor={`colonne-debut-${i}`}>Début</Label>
                      <Input
                        id={`colonne-debut-${i}`} type="date" value={c.date_debut}
                        onChange={(e) => majColonne(i, { date_debut: e.target.value })}
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <Label htmlFor={`colonne-fin-${i}`}>Fin</Label>
                      <Input
                        id={`colonne-fin-${i}`} type="date" value={c.date_fin}
                        onChange={(e) => majColonne(i, { date_fin: e.target.value })}
                      />
                    </div>
                  </>
                )}
                {c.type_colonne === 'budget' && (
                  <div className="flex flex-col gap-1">
                    <Label htmlFor={`colonne-budget-${i}`}>Budget</Label>
                    <select
                      id={`colonne-budget-${i}`} value={c.budget}
                      onChange={(e) => majColonne(i, { budget: e.target.value })}
                      className="h-9 rounded-md border border-border bg-card px-3 text-sm"
                    >
                      <option value="">—</option>
                      {budgets.map((b) => (
                        <option key={b.id} value={b.id}>{b.libelle || `Budget ${b.annee}`}</option>
                      ))}
                    </select>
                  </div>
                )}
                <Button
                  type="button" variant="ghost" size="sm" onClick={() => retirerColonne(i)}
                  disabled={colonnes.length <= 1}
                >
                  Retirer
                </Button>
              </div>
            ))}
            <div>
              <Button type="button" variant="outline" size="sm" onClick={ajouterColonne}>
                <Plus className="size-3.5" /> Ajouter une colonne
              </Button>
            </div>
          </fieldset>

          <div className="flex gap-2">
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Enregistrement…' : "Enregistrer l'état"}
            </Button>
            <Button type="button" variant="outline" onClick={resetConstruction}>Annuler</Button>
          </div>
        </form>
      )}

      {evalue && (
        evalue.lignes?.length ? (
          <div className="mt-4 flex flex-col gap-2">
            <h3 className="text-sm font-medium">Rendu évalué — {evalue.libelle}</h3>
            <ComptaTable
              aria-label={`État évalué — ${evalue.libelle}`}
              exportName={`etat-${evalue.libelle}`}
              rows={evalue.lignes}
              getRowKey={(l) => l.id}
              columns={evalueColonnes}
            />
          </div>
        ) : (
          <EmptyState
            className="mt-4"
            title="État vide"
            description="Aucune ligne à afficher pour cet état."
          />
        )
      )}
    </div>
  )
}
