// VT8 — Revue bureau d'études : visites `terminee` à revoir, viewer photos
// par catégorie, mesures récapitulées, Valider (feu vert calepinage) /
// Renvoyer (sélection slots/mesures à refaire + motif OBLIGATOIRE). Après
// validation, « Ouvrir l'atelier 3D » ouvre ToitureDesign en mode lead.
//
// `statut` fait partie de la forme LISTE du contrat (id, lead, lead_nom,
// ville, statut, date_prevue, complet, manquants_count) : le filtre
// `terminee` est donc appliqué sur des données déjà renvoyées par le
// serveur, jamais une invention de paramètre de requête hors contrat.
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import visitesApi from '../../api/visitesApi'
import PageHeader from '../../components/layout/PageHeader'
import {
  Button, Card, Spinner, EmptyState, Badge, Checkbox, Textarea, Label,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../ui'
import { toast } from '../../ui/confirm'
import { MESURES_SCHEMA, trierCategories, STATUT_VISITE_LABEL } from './visiteHelpers'

function MesuresRecap({ mesures, checklist }) {
  const categories = trierCategories(checklist)
  return (
    <div className="space-y-3">
      {categories.map((c) => {
        const schema = MESURES_SCHEMA[c.categorie] ?? []
        if (schema.length === 0) return null
        const valeurs = mesures?.[c.categorie] ?? {}
        return (
          <div key={c.categorie}>
            <p className="text-sm font-medium">{c.libelle}</p>
            <dl className="mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs">
              {schema.map((champ) => (
                <div key={champ.key} className="contents">
                  <dt className="text-muted-foreground">{champ.label}</dt>
                  <dd>
                    {valeurs[champ.key] == null || valeurs[champ.key] === ''
                      ? '—'
                      : champ.type === 'bool' ? (valeurs[champ.key] ? 'Oui' : 'Non')
                        : `${valeurs[champ.key]}${champ.unite ? ` ${champ.unite}` : ''}`}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        )
      })}
    </div>
  )
}

function PhotosParCategorie({ checklist }) {
  const categories = trierCategories(checklist)
  return (
    <div className="space-y-3">
      {categories.map((c) => (
        <div key={c.categorie}>
          <p className="text-sm font-medium">{c.libelle}</p>
          {c.slots.map((slot) => (
            <div key={slot.code} className="mt-1">
              <p className="text-xs text-muted-foreground">{slot.libelle}</p>
              {slot.photos.length === 0 ? (
                <p className="text-xs text-muted-foreground">Aucune photo.</p>
              ) : (
                <div className="mt-1 flex flex-wrap gap-2">
                  {slot.photos.map((p) => (
                    <a key={p.id} href={p.url} target="_blank" rel="noreferrer">
                      <img src={p.url} alt={p.filename} className="size-20 rounded-md border border-border object-cover" />
                    </a>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}

// Sélection des slots/mesures à refaire + motif obligatoire (VT8).
function RenvoyerDialog({ open, onOpenChange, visite, onRenvoye }) {
  const [photos, setPhotos] = useState([])
  const [mesures, setMesures] = useState([])
  const [motif, setMotif] = useState('')
  const [envoi, setEnvoi] = useState(false)

  const toutSlots = (visite?.checklist ?? []).flatMap((c) => c.slots.map((s) => ({ ...s, categorie: c.categorie, categorieLibelle: c.libelle })))
  const toutMesures = trierCategories(visite?.checklist ?? [])
    .flatMap((c) => (MESURES_SCHEMA[c.categorie] ?? []).map((champ) => ({ ...champ, categorie: c.categorie, categorieLibelle: c.libelle })))

  const togglePhoto = (code) => setPhotos((prev) => (
    prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
  ))
  const toggleMesure = (categorie, champ) => setMesures((prev) => {
    const exists = prev.some((m) => m.categorie === categorie && m.champ === champ)
    return exists
      ? prev.filter((m) => !(m.categorie === categorie && m.champ === champ))
      : [...prev, { categorie, champ }]
  })

  const envoyer = async () => {
    setEnvoi(true)
    try {
      await visitesApi.renvoyerVisite(visite.id, { photos, mesures, motif })
      toast.success('Visite renvoyée au commercial.')
      onRenvoye?.()
      onOpenChange(false)
    } catch {
      toast.error('Renvoi impossible.')
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Renvoyer la visite</DialogTitle></DialogHeader>
        <div className="max-h-[50vh] space-y-3 overflow-y-auto">
          <div>
            <p className="text-sm font-medium">Photos à refaire</p>
            {toutSlots.map((s) => (
              <label key={s.code} className="flex min-h-9 items-center gap-2 text-sm">
                <Checkbox checked={photos.includes(s.code)} onCheckedChange={() => togglePhoto(s.code)} />
                {s.categorieLibelle} — {s.libelle}
              </label>
            ))}
          </div>
          <div>
            <p className="text-sm font-medium">Mesures à refaire</p>
            {toutMesures.map((m) => (
              <label key={`${m.categorie}-${m.key}`} className="flex min-h-9 items-center gap-2 text-sm">
                <Checkbox
                  checked={mesures.some((x) => x.categorie === m.categorie && x.champ === m.key)}
                  onCheckedChange={() => toggleMesure(m.categorie, m.key)}
                />
                {m.categorieLibelle} — {m.label}
              </label>
            ))}
          </div>
          <div>
            <Label htmlFor="visite-renvoi-motif">Motif (obligatoire)</Label>
            <Textarea
              id="visite-renvoi-motif"
              value={motif}
              onChange={(e) => setMotif(e.target.value)}
              placeholder="Ce qui doit être repris et pourquoi…"
            />
          </div>
        </div>
        <DialogFooter>
          <Button
            type="button"
            disabled={!motif.trim() || (photos.length === 0 && mesures.length === 0) || envoi}
            onClick={envoyer}
          >
            Renvoyer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function DetailVisite({ visite, onRetour, onChanged }) {
  const navigate = useNavigate()
  const [renvoiOuvert, setRenvoiOuvert] = useState(false)
  const [validant, setValidant] = useState(false)

  const valider = async () => {
    setValidant(true)
    try {
      await visitesApi.validerVisite(visite.id)
      toast.success('Visite validée — feu vert calepinage.')
      onChanged()
    } catch {
      toast.error('Validation impossible.')
    } finally {
      setValidant(false)
    }
  }

  // VT8 — ouvre l'atelier 3D EN MODE LEAD (route existante `/devis-design/:id`,
  // `ToitureDesign.jsx`). Les mesures VRAIMENT saisies (jamais une valeur
  // inventée pour un champ absent) partent en query params optionnels que
  // l'atelier lit best-effort (voir ToitureDesign.jsx, section VT8/VT11) —
  // le paramètre est simplement omis si la mesure n'a pas été prise.
  const ouvrirAtelier = () => {
    const toiture = visite.mesures?.toiture ?? {}
    const params = new URLSearchParams({ visite: String(visite.id) })
    if (toiture.pente_deg != null) params.set('pente', String(toiture.pente_deg))
    if (toiture.orientation) params.set('orientation', String(toiture.orientation))
    if (toiture.longueur_m != null) params.set('longueur', String(toiture.longueur_m))
    if (toiture.largeur_m != null) params.set('largeur', String(toiture.largeur_m))
    navigate(`/devis-design/${visite.lead}?${params.toString()}`)
  }

  return (
    <div className="space-y-4">
      <Button type="button" variant="ghost" onClick={onRetour}>← Retour à la liste</Button>
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold">{visite.client_panel?.lead_nom ?? `Visite #${visite.id}`}</h3>
        <Badge tone="neutral">{STATUT_VISITE_LABEL[visite.statut] ?? visite.statut}</Badge>
      </div>

      <Card className="p-3"><PhotosParCategorie checklist={visite.checklist} /></Card>
      <Card className="p-3"><MesuresRecap mesures={visite.mesures} checklist={visite.checklist} /></Card>

      {visite.statut === 'terminee' && (
        <div className="flex flex-wrap gap-2">
          <Button type="button" onClick={valider} disabled={validant}>Valider (feu vert)</Button>
          <Button type="button" variant="outline" onClick={() => setRenvoiOuvert(true)}>Renvoyer</Button>
        </div>
      )}
      {visite.statut === 'validee' && (
        <Button type="button" onClick={ouvrirAtelier}>Ouvrir l’atelier 3D</Button>
      )}

      <RenvoyerDialog
        open={renvoiOuvert}
        onOpenChange={setRenvoiOuvert}
        visite={visite}
        onRenvoye={onChanged}
      />
    </div>
  )
}

export default function VisiteBureauEtudesPage() {
  const [visites, setVisites] = useState([])
  const [loading, setLoading] = useState(true)
  const [detailId, setDetailId] = useState(null)
  const [detail, setDetail] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    visitesApi.getVisites({})
      .then((res) => {
        const rows = res.data?.results ?? res.data ?? []
        setVisites(rows.filter((v) => v.statut === 'terminee'))
      })
      .catch(() => toast.error('Chargement des visites impossible.'))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement initial au montage
  useEffect(() => { load() }, [load])

  const ouvrir = (id) => {
    setDetailId(id)
    visitesApi.getVisite(id).then((res) => setDetail(res.data)).catch(() => toast.error('Visite introuvable.'))
  }

  const surChangement = () => {
    visitesApi.getVisite(detailId).then((res) => setDetail(res.data))
    load()
  }

  if (detailId && detail) {
    return (
      <div className="page max-w-[760px]">
        <DetailVisite
          visite={detail}
          onRetour={() => { setDetailId(null); setDetail(null) }}
          onChanged={surChangement}
        />
      </div>
    )
  }

  return (
    <div className="page max-w-[760px]">
      <PageHeader title="Revue technique" subtitle="Visites terminées, en attente du feu vert bureau d'études" />
      {loading ? (
        <Spinner />
      ) : visites.length === 0 ? (
        <EmptyState title="Aucune visite à revoir" description="Toutes les visites terminées ont été traitées." />
      ) : (
        <ul className="space-y-2">
          {visites.map((v) => (
            <li key={v.id}>
              <Card
                role="button" tabIndex={0}
                className="flex min-h-11 cursor-pointer items-center justify-between gap-3 p-3"
                onClick={() => ouvrir(v.id)}
                onKeyDown={(e) => { if (e.key === 'Enter') ouvrir(v.id) }}
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{v.lead_nom}</p>
                  <p className="text-xs text-muted-foreground">{v.ville}</p>
                </div>
                <Badge tone={v.complet ? 'success' : 'neutral'}>À revoir</Badge>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
