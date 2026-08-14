// NTRET8 — Onglet « Point de vente » (Paramètres → Point de vente).
//
// Regroupe la config retail : taux horaire main-d'œuvre comptoir (distinct
// du taux SAV), boutiques actives (EmplacementStock marqués « point de vente
// physique » avec adresse/horaires/surface pour le reçu et le tableau de
// bord retail NTRET16). Le seuil de remise ligne comptoir (T17) et la config
// imprimante/TPE (XPOS18) ne sont PAS dupliqués ici — un repère renvoie vers
// leurs onglets existants.
import { useEffect, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import api from '../../api/axios'
import { toast } from '../../ui/confirm'
import {
  Card, CardContent, Input, Button, IconButton, Switch, Spinner,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem, Label,
} from '../../ui'
import { SectionTitle } from './peComponents'

const cfErr = (e, fallback) => {
  const d = e?.response?.data
  if (!d) return fallback
  if (typeof d === 'string') return d
  if (d.detail) return d.detail
  const first = Object.values(d)[0]
  return Array.isArray(first) ? first[0] : (first || fallback)
}

export default function PointDeVenteSection() {
  const [loading, setLoading] = useState(true)
  const [tauxHoraire, setTauxHoraire] = useState('')
  const [busyTaux, setBusyTaux] = useState(false)
  const [boutiques, setBoutiques] = useState([])
  const [emplacements, setEmplacements] = useState([])
  const [nouvelEmplacement, setNouvelEmplacement] = useState('')
  const [busyAjout, setBusyAjout] = useState(false)

  const load = () => {
    Promise.all([
      api.get('/parametres/pos/'),
      api.get('/parametres/pos-boutiques/'),
      api.get('/stock/emplacements/'),
    ]).then(([params, boutiquesRes, emplacementsRes]) => {
      setTauxHoraire(params.data.taux_horaire_comptoir ?? '')
      const rows = boutiquesRes.data?.results ?? boutiquesRes.data ?? []
      setBoutiques(Array.isArray(rows) ? rows : [])
      const emps = emplacementsRes.data?.results ?? emplacementsRes.data ?? []
      setEmplacements(Array.isArray(emps) ? emps : [])
    }).catch(() => {
      setBoutiques([])
      setEmplacements([])
    }).finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const enregistrerTaux = async () => {
    setBusyTaux(true)
    try {
      await api.patch('/parametres/pos/update/', {
        taux_horaire_comptoir: tauxHoraire === '' ? null : tauxHoraire,
      })
      toast.success('Taux horaire comptoir enregistré.')
    } catch (e) {
      toast.error(cfErr(e, "L'enregistrement a échoué."))
    } finally {
      setBusyTaux(false)
    }
  }

  const emplacementsDisponibles = emplacements.filter(
    (e) => !boutiques.some((b) => b.emplacement === e.id))

  const ajouterBoutique = async () => {
    if (!nouvelEmplacement) return
    setBusyAjout(true)
    try {
      await api.post('/parametres/pos-boutiques/', { emplacement: nouvelEmplacement })
      setNouvelEmplacement('')
      load()
    } catch (e) {
      toast.error(cfErr(e, "L'ajout a échoué."))
    } finally {
      setBusyAjout(false)
    }
  }

  const majBoutique = async (b, patch) => {
    try {
      await api.patch(`/parametres/pos-boutiques/${b.id}/`, patch)
      load()
    } catch (e) {
      toast.error(cfErr(e, 'La modification a échoué.'))
    }
  }

  const supprimerBoutique = async (b) => {
    if (!window.confirm(`Retirer « ${b.emplacement_nom} » des boutiques actives ?`)) return
    try {
      await api.delete(`/parametres/pos-boutiques/${b.id}/`)
      load()
    } catch (e) {
      toast.error(cfErr(e, 'La suppression a échoué.'))
    }
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center gap-2 pt-4 text-sm text-muted-foreground">
          <Spinner className="size-4 text-primary" /> Chargement…
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="grid gap-4">
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Main-d'œuvre comptoir" />
          <p className="mb-3.5 text-[11.5px] text-muted-foreground">
            Taux horaire main-d'œuvre spécifique au comptoir — distinct du taux SAV
            (onglet Sécurité &amp; terrain). Vide = aucun taux configuré (comportement
            actuel inchangé).
          </p>
          <div className="flex flex-wrap items-end gap-2">
            <div className="grid gap-1.5">
              <Label htmlFor="pos-taux-horaire">Taux horaire (MAD/heure)</Label>
              <Input
                id="pos-taux-horaire"
                type="number"
                step="any"
                className="w-40"
                value={tauxHoraire}
                onChange={(e) => setTauxHoraire(e.target.value)}
              />
            </div>
            <Button type="button" loading={busyTaux} onClick={enregistrerTaux}>
              Enregistrer
            </Button>
          </div>
          <p className="mt-3 text-[11px] text-muted-foreground">
            Le seuil de remise ligne comptoir réutilise le seuil d'approbation des
            devis (onglet Devis &amp; Factures). La configuration imprimante/TPE se
            règle depuis l'écran caisse (Point de vente → Configuration matériel).
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Boutiques actives" />
          <p className="mb-3.5 text-[11.5px] text-muted-foreground">
            Marquez les emplacements de stock qui sont des points de vente physiques.
            L'adresse et les horaires alimentent le reçu de caisse ; la surface
            alimente le KPI « ventes au m² » du tableau de bord retail.
          </p>

          {boutiques.length === 0 ? (
            <p className="mb-3 text-sm text-muted-foreground" data-testid="boutiques-empty">
              Aucune boutique active pour l'instant.
            </p>
          ) : (
            <div className="mb-3 grid gap-2" data-testid="boutiques-liste">
              {boutiques.map((b) => (
                <div key={b.id} className="flex flex-wrap items-center gap-1.5 rounded-md border border-border p-2">
                  <span className="min-w-[140px] flex-1 text-sm font-medium">{b.emplacement_nom}</span>
                  <Input
                    className="min-w-[160px] flex-[1_1_160px]"
                    placeholder="Adresse"
                    defaultValue={b.adresse}
                    onBlur={(e) => {
                      if (e.target.value !== b.adresse) majBoutique(b, { adresse: e.target.value })
                    }}
                  />
                  <Input
                    className="min-w-[140px] flex-[1_1_140px]"
                    placeholder="Horaires"
                    defaultValue={b.horaires}
                    onBlur={(e) => {
                      if (e.target.value !== b.horaires) majBoutique(b, { horaires: e.target.value })
                    }}
                  />
                  <Input
                    type="number"
                    step="any"
                    className="w-24"
                    placeholder="Surface m²"
                    defaultValue={b.surface_m2 ?? ''}
                    onBlur={(e) => {
                      const v = e.target.value === '' ? null : e.target.value
                      if (v !== (b.surface_m2 ?? null)) majBoutique(b, { surface_m2: v })
                    }}
                  />
                  <Switch
                    checked={!!b.actif}
                    onCheckedChange={(v) => majBoutique(b, { actif: !!v })}
                    aria-label={b.actif ? 'Désactiver la boutique' : 'Réactiver la boutique'}
                  />
                  <IconButton size="md" variant="outline" label="Retirer la boutique"
                              className="text-destructive hover:text-destructive"
                              onClick={() => supprimerBoutique(b)}>
                    <Trash2 className="size-4" aria-hidden="true" />
                  </IconButton>
                </div>
              ))}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-1.5">
            <div className="w-56">
              <Select value={nouvelEmplacement} onValueChange={setNouvelEmplacement}>
                <SelectTrigger><SelectValue placeholder="Choisir un emplacement…" /></SelectTrigger>
                <SelectContent>
                  {emplacementsDisponibles.map((e) => (
                    <SelectItem key={e.id} value={String(e.id)}>{e.nom}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button type="button" loading={busyAjout} disabled={!nouvelEmplacement}
                    onClick={ajouterBoutique}>
              <Plus className="size-4" aria-hidden="true" /> Ajouter
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
