// PACT140 — Écran GÉNÉRIQUE des enregistrements d'un objet personnalisé
// (XPLT16 / NTEXT2 / NTEXT3).
//
// Un SEUL écran sert TOUS les objets personnalisés : il ne connaît aucun champ
// à l'avance. Il lit les deux schémas AUTO-GÉNÉRÉS par le serveur —
//   • `…/custom-objects/<code>/vue-liste/`      → colonnes + données paginées ;
//   • `…/custom-objects/<code>/vue-formulaire/` → champs du formulaire ;
// puis rend la liste et le formulaire à partir d'eux. Ajouter un champ dans
// Paramètres → Objets personnalisés le fait donc apparaître ici sans une ligne
// de code de plus.
//
// Aucun second moteur de champs : la définition des champs reste celle des
// `CustomFieldDef` (module `custom:<code>`), la validation reste côté serveur
// (`validate_custom_data`) — le front n'en est jamais l'autorité.
//
// Multi-tenant : la société vient de `request.user` côté serveur ; l'URL ne
// porte que le code de l'objet. `company` n'est jamais envoyée.
import { useCallback, useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Boxes, Plus, Trash2, ArrowLeft } from 'lucide-react'
import api from '../../api/axios'
import { toast } from '../../ui/confirm'
import {
  Button, IconButton, Input, Spinner, EmptyState, Card, CardContent,
} from '../../ui'

// Rendu d'une valeur de cellule selon le formatage annoncé par le serveur.
function afficherValeur(valeur, formatage) {
  if (valeur === null || valeur === undefined || valeur === '') return '—'
  if (formatage === 'oui_non') return valeur ? 'Oui' : 'Non'
  if (typeof valeur === 'object') return JSON.stringify(valeur)
  return String(valeur)
}

// Valeur initiale d'un champ du formulaire, selon son type.
function valeurVide(type) {
  return type === 'boolean' ? false : ''
}

function formulaireVide(champs) {
  const out = {}
  champs.forEach((c) => { out[c.code] = valeurVide(c.type) })
  return out
}

export default function CustomObjectRecordsPage() {
  const { code } = useParams()

  const [colonnes, setColonnes] = useState([])
  const [champs, setChamps] = useState([])
  const [lignes, setLignes] = useState([])
  const [loading, setLoading] = useState(true)
  const [introuvable, setIntrouvable] = useState(false)
  const [busy, setBusy] = useState(false)
  const [draft, setDraft] = useState({})
  const [editionId, setEditionId] = useState(null)

  const charger = useCallback(() => Promise.all([
    api.get(`/custom-fields/custom-objects/${code}/vue-liste/`),
    api.get(`/custom-fields/custom-objects/${code}/vue-formulaire/`),
  ])
    .then(([liste, formulaire]) => {
      setColonnes(liste.data?.colonnes ?? [])
      setLignes(liste.data?.results ?? [])
      const schema = formulaire.data?.champs ?? []
      setChamps(schema)
      setDraft(formulaireVide(schema))
      setIntrouvable(false)
    })
    .catch(() => setIntrouvable(true))
    .finally(() => setLoading(false)), [code])

  useEffect(() => { charger() }, [charger])

  const majDraft = (champCode, valeur) => {
    setDraft((d) => ({ ...d, [champCode]: valeur }))
  }

  const enregistrer = async () => {
    setBusy(true)
    try {
      if (editionId) {
        await api.patch(
          `/custom-fields/custom-objects/${code}/records/${editionId}/`,
          { data: draft })
      } else {
        await api.post(`/custom-fields/custom-objects/${code}/records/`,
          { data: draft })
      }
      setEditionId(null)
      setDraft(formulaireVide(champs))
      charger()
    } catch (e) {
      const d = e?.response?.data
      const premier = d && typeof d === 'object' ? Object.values(d)[0] : null
      toast.error(
        (Array.isArray(premier) ? premier[0] : premier)
        ?? d?.detail ?? 'Enregistrement impossible.')
    } finally { setBusy(false) }
  }

  const editer = (ligne) => {
    setEditionId(ligne.id)
    setDraft({ ...formulaireVide(champs), ...(ligne.data || {}) })
  }

  const annulerEdition = () => {
    setEditionId(null)
    setDraft(formulaireVide(champs))
  }

  const supprimer = async (ligne) => {
    if (!window.confirm('Supprimer cet enregistrement ?')) return
    try {
      await api.delete(`/custom-fields/custom-objects/${code}/records/${ligne.id}/`)
      if (editionId === ligne.id) annulerEdition()
      charger()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Suppression impossible.')
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-[1100px] p-6">
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner className="size-4 text-primary" /> Chargement…
        </p>
      </div>
    )
  }

  if (introuvable) {
    return (
      <div className="mx-auto max-w-[1100px] p-6">
        <EmptyState icon={Boxes} title="Objet personnalisé introuvable"
          description="Cet objet n'existe pas, n'est plus actif, ou vous n'y avez pas accès."
          className="py-8" />
        <Link to="/parametres/objets-personnalises"
          className="text-sm text-primary hover:underline">
          Retour aux objets personnalisés
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto flex max-w-[1100px] flex-col gap-4 p-6">
      <div>
        <Link to="/parametres/objets-personnalises"
          className="mb-1 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-3.5" aria-hidden="true" /> Objets personnalisés
        </Link>
        <h2 className="font-display text-xl font-bold tracking-tight text-foreground">
          {code}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Liste et saisie générées automatiquement à partir des champs définis
          pour cet objet. Ajoutez ou retirez un champ dans Paramètres → Objets
          personnalisés : cet écran suit.
        </p>
      </div>

      {champs.length === 0 && (
        <EmptyState title="Aucun champ défini pour cet objet"
          description="Ajoutez d'abord des champs dans Paramètres → Objets personnalisés."
          className="py-8" />
      )}

      {champs.length > 0 && (
        <>
          {/* ── Liste, colonnes issues du schéma serveur ─────────────────── */}
          <Card>
            <CardContent className="pt-4 sm:pt-5">
              {lignes.length === 0 ? (
                <EmptyState icon={Boxes} title="Aucun enregistrement"
                  description="Saisissez le premier enregistrement ci-dessous."
                  className="py-6" />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm" data-testid="table-enregistrements">
                    <thead>
                      <tr className="border-b border-border text-left">
                        {colonnes.map((col) => (
                          <th key={col.code} scope="col"
                            className="px-2 py-1.5 text-xs font-medium text-muted-foreground">
                            {col.libelle}
                          </th>
                        ))}
                        <th scope="col" className="px-2 py-1.5" />
                      </tr>
                    </thead>
                    <tbody>
                      {lignes.map((ligne) => (
                        <tr key={ligne.id} data-testid={`enregistrement-${ligne.id}`}
                          className="border-b border-border last:border-0">
                          {colonnes.map((col) => (
                            <td key={col.code} className="px-2 py-1.5">
                              {afficherValeur((ligne.data || {})[col.code], col.formatage)}
                            </td>
                          ))}
                          <td className="px-2 py-1.5">
                            <div className="flex items-center justify-end gap-1">
                              <Button type="button" size="sm" variant="outline"
                                onClick={() => editer(ligne)}>
                                Modifier
                              </Button>
                              <IconButton size="sm" variant="outline"
                                label="Supprimer l'enregistrement"
                                className="text-destructive hover:text-destructive"
                                onClick={() => supprimer(ligne)}>
                                <Trash2 className="size-4" aria-hidden="true" />
                              </IconButton>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>

          {/* ── Formulaire, champs issus du schéma serveur ───────────────── */}
          <Card>
            <CardContent className="pt-4 sm:pt-5">
              <h3 className="mb-3 text-sm font-semibold tracking-tight text-foreground">
                {editionId ? "Modifier l'enregistrement" : 'Nouvel enregistrement'}
              </h3>
              <div className="flex flex-col gap-2">
                {champs.map((champ) => (
                  <div key={champ.code} className="flex flex-col gap-1">
                    <label className="text-xs font-medium text-foreground"
                      htmlFor={`champ-${champ.code}`}>
                      {champ.libelle}{champ.obligatoire ? ' *' : ''}
                    </label>
                    {champ.type === 'boolean' ? (
                      <input id={`champ-${champ.code}`} type="checkbox"
                        className="size-4"
                        checked={Boolean(draft[champ.code])}
                        onChange={(e) => majDraft(champ.code, e.target.checked)} />
                    ) : champ.type === 'choice' ? (
                      <select id={`champ-${champ.code}`}
                        className="h-[var(--control-h)] rounded-md border border-input bg-card px-[var(--control-px)] text-sm"
                        value={draft[champ.code] ?? ''}
                        onChange={(e) => majDraft(champ.code, e.target.value)}>
                        <option value="">—</option>
                        {(champ.options || []).map((o) => (
                          <option key={o} value={o}>{o}</option>
                        ))}
                      </select>
                    ) : (
                      <Input id={`champ-${champ.code}`}
                        type={champ.type === 'number' ? 'number'
                          : champ.type === 'date' ? 'date' : 'text'}
                        step={champ.type === 'number' ? 'any' : undefined}
                        value={draft[champ.code] ?? ''}
                        onChange={(e) => majDraft(champ.code, e.target.value)} />
                    )}
                  </div>
                ))}
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-1.5">
                <Button type="button" onClick={enregistrer} disabled={busy}>
                  <Plus className="size-4" aria-hidden="true" />
                  {editionId ? 'Enregistrer' : "Ajouter l'enregistrement"}
                </Button>
                {editionId && (
                  <Button type="button" variant="outline" onClick={annulerEdition}>
                    Annuler
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
