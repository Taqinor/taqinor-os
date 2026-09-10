// VT5 — Écran visite terrain (mobile-first) : wizard par catégorie (toiture →
// tableau → local onduleur → cheminement [optionnel] → général), tuiles photo
// par slot avec état serveur (manquant/ok/à refaire + motif), capture via
// CameraCapture (PWA), texte-guide par slot, barre de progression PHOTOS
// dérivée des champs serveur (`progressionPhotos`, jamais la décision
// « complet » elle-même — toujours `completude.complet`, serveur).
//
// VT6 ajoute le formulaire de mesures par catégorie (VisiteMesuresForm).
// VT7 ajoute le panneau client+devis (VisiteClientDevisPanel).
import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import crmApi from '../../../api/crmApi'
import PageHeader from '../../../components/layout/PageHeader'
import CameraCapture from '../../../features/pwa/CameraCapture'
import {
  Button, Card, Spinner, Badge, ChecklistProgress,
  Tabs, TabsList, TabsTrigger, TabsContent,
} from '../../../ui'
import { toast } from '../../../ui/confirm'
import {
  trierCategories, progressionPhotos,
  ETAT_SLOT_LABEL, ETAT_SLOT_TONE, STATUT_VISITE_LABEL,
} from './visiteHelpers'
import VisiteMesuresForm from './VisiteMesuresForm'
import VisiteClientDevisPanel from './VisiteClientDevisPanel'

// Une tuile photo — état/motif/guide TOUJOURS tels que renvoyés par le
// serveur, jamais reformulés ici (RÈGLE fondateur : erreurs/motifs = texte
// serveur exact).
function SlotTile({ visiteId, slot, onChanged }) {
  const [ouvert, setOuvert] = useState(false)
  const [envoi, setEnvoi] = useState(false)

  const capturer = async (file, geo) => {
    setEnvoi(true)
    try {
      await crmApi.uploadVisitePhoto(visiteId, {
        slotCode: slot.code,
        fichier: file,
        gpsLat: geo?.latitude,
        gpsLng: geo?.longitude,
      })
      onChanged()
    } catch {
      toast.error(`Envoi de la photo « ${slot.libelle} » impossible.`)
    } finally {
      setEnvoi(false)
    }
  }

  const supprimer = async (mediaId) => {
    try {
      await crmApi.deleteVisitePhoto(visiteId, mediaId)
      onChanged()
    } catch {
      toast.error('Suppression de la photo impossible.')
    }
  }

  return (
    <Card className="p-3" data-testid={`visite-slot-${slot.code}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-medium">
            {slot.libelle}{!slot.requis && <span className="text-muted-foreground"> (optionnel)</span>}
          </p>
          {slot.guide && <p className="text-xs text-muted-foreground">{slot.guide}</p>}
        </div>
        <Badge tone={ETAT_SLOT_TONE[slot.etat] ?? 'neutral'} className="shrink-0">
          {ETAT_SLOT_LABEL[slot.etat] ?? slot.etat}
        </Badge>
      </div>

      {slot.etat === 'a_refaire' && slot.photos.some((p) => p.a_refaire) && (
        <p role="alert" className="mt-1.5 text-xs text-destructive">
          {slot.photos.find((p) => p.a_refaire)?.motif_refaire}
        </p>
      )}

      {slot.photos.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2" aria-label={`Photos — ${slot.libelle}`}>
          {slot.photos.map((p) => (
            <div key={p.id} className="relative">
              <img
                src={p.url} alt={p.filename}
                className="size-16 rounded-md border border-border object-cover"
              />
              <button
                type="button"
                aria-label={`Supprimer la photo ${p.filename}`}
                className="absolute -right-1.5 -top-1.5 grid size-5 place-items-center rounded-full bg-destructive text-[10px] text-destructive-foreground"
                onClick={() => supprimer(p.id)}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      {ouvert ? (
        <div className="mt-2">
          <CameraCapture
            multiple
            filename={`${slot.code}.jpg`}
            onCapture={capturer}
            onClose={() => setOuvert(false)}
          />
        </div>
      ) : (
        <Button
          type="button" size="sm" variant="outline" className="mt-2"
          disabled={envoi}
          onClick={() => setOuvert(true)}
        >
          Ajouter une photo
        </Button>
      )}
    </Card>
  )
}

export default function VisiteWizardPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [visite, setVisite] = useState(null)
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(null)
  const [terminant, setTerminant] = useState(false)
  const [categorieActive, setCategorieActive] = useState(null)

  const recharger = useCallback(() => {
    crmApi.getVisite(id)
      .then((res) => {
        setVisite(res.data)
        setCategorieActive((prev) => prev ?? trierCategories(res.data.checklist)[0]?.categorie)
      })
      .catch(() => setErreur('Visite introuvable ou inaccessible.'))
      .finally(() => setLoading(false))
  }, [id])

  useEffect(() => { recharger() }, [recharger])

  const terminer = async () => {
    setTerminant(true)
    try {
      const res = await crmApi.terminerVisite(id)
      setVisite(res.data)
      toast.success('Visite terminée — envoyée au bureau d’études.')
    } catch (err) {
      const data = err?.response?.data
      if (data?.manquants) {
        toast.error(data.message || 'Il manque encore des éléments.')
      } else {
        toast.error('Impossible de terminer la visite.')
      }
      recharger()
    } finally {
      setTerminant(false)
    }
  }

  if (loading) return <div className="page"><Spinner /></div>
  if (erreur || !visite) return <div className="page"><p role="alert" className="text-sm text-destructive">{erreur}</p></div>

  const categories = trierCategories(visite.checklist)
  const { done, total } = progressionPhotos(visite.checklist)
  const lectureSeule = !visite.modifiable

  return (
    <div className="page max-w-[820px] pb-24">
      <PageHeader
        title={visite.client_panel?.lead_nom ?? `Visite #${visite.id}`}
        subtitle={STATUT_VISITE_LABEL[visite.statut] ?? visite.statut}
        actions={<Button type="button" variant="ghost" onClick={() => navigate('/crm/visites')}>Retour</Button>}
      />

      {lectureSeule && visite.raison_lecture_seule && (
        <p role="status" className="mb-3 rounded-lg border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
          {visite.raison_lecture_seule}
        </p>
      )}

      <div className="mb-3">
        <ChecklistProgress done={done} total={total} noun="photo" />
      </div>

      <VisiteClientDevisPanel clientPanel={visite.client_panel} devis={visite.devis} />

      <Tabs value={categorieActive} onValueChange={setCategorieActive} className="mt-3">
        <TabsList className="flex-wrap">
          {categories.map((c) => (
            <TabsTrigger key={c.categorie} value={c.categorie}>{c.libelle}</TabsTrigger>
          ))}
        </TabsList>
        {categories.map((c) => (
          <TabsContent key={c.categorie} value={c.categorie} className="space-y-3 pt-3">
            {c.slots.map((slot) => (
              <SlotTile key={slot.code} visiteId={id} slot={slot} onChanged={recharger} />
            ))}
            <VisiteMesuresForm
              visiteId={id}
              categorie={c.categorie}
              libelle={c.libelle}
              valeurs={visite.mesures?.[c.categorie]}
              lectureSeule={lectureSeule}
              onSaved={recharger}
            />
          </TabsContent>
        ))}
      </Tabs>

      {(visite.completude?.manquants?.length ?? 0) > 0 && (
        <div role="alert" className="mt-4 rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm" data-testid="visite-manquants">
          <p className="font-medium">Il manque encore :</p>
          <ul className="mt-1 list-disc pl-5">
            {visite.completude.manquants.map((m, i) => (
              <li key={`${m.type}-${m.categorie}-${m.code ?? i}`}>{m.libelle}</li>
            ))}
          </ul>
        </div>
      )}

      {!lectureSeule && (
        <div className="fixed inset-x-0 bottom-0 border-t border-border bg-background p-3">
          <Button
            type="button" className="w-full"
            disabled={!visite.completude?.complet || terminant}
            onClick={terminer}
          >
            {visite.completude?.complet ? 'Terminer la visite' : 'Il manque des éléments'}
          </Button>
        </div>
      )}
    </div>
  )
}
