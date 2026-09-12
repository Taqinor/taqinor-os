/* NTSUB24 — Réglages « Facturation récurrente » de la société.
   ----------------------------------------------------------------------------
   Les seuils du groupe NTSUB étaient des constantes codées en dur (J-3 avant
   fin d'essai, 30 jours avant expiration de carte, 80 % d'un quota d'usage).
   Cet écran les rend réglables PAR SOCIÉTÉ. Le singleton est créé
   paresseusement côté serveur au premier accès avec ces mêmes valeurs : une
   société qui n'ouvre jamais cet écran garde le comportement actuel.

   `company` n'apparaît jamais dans le corps : le serveur résout le réglage
   depuis l'utilisateur connecté. */
import { useEffect, useState } from 'react'
import { Save } from 'lucide-react'
import api from '../../api/axios'
import {
  Button, Card, Input, Label, Skeleton, toast,
} from '../../ui'

const listData = (res) => (
  Array.isArray(res.data) ? res.data : (res.data?.results ?? []))

function messageErreur(err, repli) {
  const d = err?.response?.data
  if (typeof d === 'string') return d
  if (d?.detail) return d.detail
  if (d && typeof d === 'object') {
    const [champ, valeur] = Object.entries(d)[0] || []
    if (champ) return `${champ} : ${Array.isArray(valeur) ? valeur[0] : valeur}`
  }
  return repli
}

export default function AbonnementsParametresPage() {
  const [params, setParams] = useState(null)
  const [sequences, setSequences] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let vivant = true
    Promise.all([
      api.get('/contrats/parametres-abonnement/courant/'),
      api.get('/contrats/sequences-dunning/').catch(() => ({ data: [] })),
    ])
      .then(([reglage, seq]) => {
        if (!vivant) return
        setParams(reglage.data)
        setSequences(listData(seq))
      })
      .catch(() => {
        if (vivant) toast.error('Réglages d’abonnement indisponibles.')
      })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }, [])

  const set = (champ, valeur) => setParams((p) => ({ ...p, [champ]: valeur }))

  const enregistrer = async () => {
    setSaving(true)
    try {
      const res = await api.patch(
        '/contrats/parametres-abonnement/courant/', {
          jours_alerte_fin_essai: Number(params.jours_alerte_fin_essai),
          jours_alerte_expiration_carte:
            Number(params.jours_alerte_expiration_carte),
          seuil_alerte_usage_pct_defaut:
            Number(params.seuil_alerte_usage_pct_defaut),
          sequence_dunning_defaut: params.sequence_dunning_defaut || null,
        })
      setParams(res.data)
      toast.success('Réglages enregistrés.')
    } catch (err) {
      toast.error(messageErreur(err, 'Enregistrement impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>Facturation récurrente</h2>
      </div>

      {loading || !params ? (
        <Card className="p-4 sm:p-5">
          <Skeleton className="h-4 w-48" />
          <Skeleton className="mt-3 h-9 w-full" />
          <Skeleton className="mt-3 h-9 w-full" />
        </Card>
      ) : (
        <Card className="flex flex-col gap-4 p-4 sm:p-5">
          <p className="text-sm text-muted-foreground">
            Ces réglages valent pour toute la société. Les valeurs affichées
            par défaut sont celles appliquées jusqu’ici : les laisser telles
            quelles ne change rien.
          </p>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-1">
              <Label htmlFor="pa-essai">Alerte avant fin d’essai (jours)</Label>
              <Input
                id="pa-essai" type="number" min="0" step="1"
                value={params.jours_alerte_fin_essai ?? ''}
                onChange={(e) => set('jours_alerte_fin_essai', e.target.value)}
              />
              <span className="text-xs text-muted-foreground">
                Le responsable est prévenu ce nombre de jours avant la fin
                d’une période d’essai.
              </span>
            </div>

            <div className="flex flex-col gap-1">
              <Label htmlFor="pa-carte">
                Alerte avant expiration de carte (jours)
              </Label>
              <Input
                id="pa-carte" type="number" min="0" step="1"
                value={params.jours_alerte_expiration_carte ?? ''}
                onChange={(e) => set('jours_alerte_expiration_carte', e.target.value)}
              />
            </div>

            <div className="flex flex-col gap-1">
              <Label htmlFor="pa-usage">
                Seuil d’alerte d’usage par défaut (%)
              </Label>
              <Input
                id="pa-usage" type="number" min="0" max="100" step="1"
                value={params.seuil_alerte_usage_pct_defaut ?? ''}
                onChange={(e) => set('seuil_alerte_usage_pct_defaut', e.target.value)}
              />
            </div>

            <div className="flex flex-col gap-1">
              <Label htmlFor="pa-dunning">Séquence de relance par défaut</Label>
              <select
                id="pa-dunning"
                value={params.sequence_dunning_defaut ?? ''}
                onChange={(e) => set('sequence_dunning_defaut', e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                <option value="">Aucune</option>
                {sequences.map((s) => (
                  <option key={s.id} value={s.id}>{s.nom}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <Button onClick={enregistrer} disabled={saving}>
              <Save className="size-4" /> Enregistrer
            </Button>
          </div>
        </Card>
      )}
    </div>
  )
}
