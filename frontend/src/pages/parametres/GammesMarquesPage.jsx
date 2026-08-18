import { useEffect, useState } from 'react'
import { Layers, Tags } from 'lucide-react'
import ventesApi from '../../api/ventesApi'
import { PRODUCT_CATEGORIES } from '../../features/ventes/solar'
import { Button, Card, CardContent, Input, Label, Spinner, Switch } from '../../ui'
import { toast } from '../../ui/confirm'

/* ============================================================================
   PVMRQ (fondateur 18/08/2026) — Paramètres → Gammes & marques
   (`ventes.ParametresGammes`, singleton par société, endpoint SANS id dans
   l'URL — `ventesApi.getParametresGammes`/`updateParametresGammes`, même
   patron get-or-create que `ParametresTresorerieView`/AchatsParametresPage).

   Deux réglages, un seul écran :
   (a) « offre à deux gammes » : bascule + libellés RENOMMABLES (le fondateur
       peut appeler « Premium » → « Luxe » sans toucher au code — les clés
       internes de `marques` restent les SLOTS FIXES 'Essentielle'/'Premium',
       jamais le libellé affiché, exactement comme documenté sur le modèle
       backend `ParametresGammes`) ;
   (b) marque préférée PAR GAMME ET PAR RÔLE de composition automatique — les
       rôles sont rendus depuis `PRODUCT_CATEGORIES` (solar.js), le MIROIR
       frontend exact de `ROLES_AUTO_COMPOSITION` (backend). Un champ vide =
       « aucune préférence, choisir comme aujourd'hui » (comportement
       historique inchangé) ; une marque texte GAGNE TOUJOURS côté générateur
       (`autoFillLines`) — zéro correspondance en stock ⇒ zéro produit sur
       cette ligne, JAMAIS un repli silencieux sur une autre marque.

   Quand « deux gammes » est désactivé, seule la colonne Essentielle est
   éditable : la carte Premium reste en base (jamais supprimée) mais inactive
   — même règle que documentée sur le modèle (`marques` garde ses deux clés,
   le sélecteur de lecture ignore juste celle qui n'est pas utilisée).
   ========================================================================== */

const SLOT_ESSENTIELLE = 'Essentielle'
const SLOT_PREMIUM = 'Premium'

const emptyForm = {
  deux_gammes: false,
  nom_essentielle: SLOT_ESSENTIELLE,
  nom_premium: SLOT_PREMIUM,
  marques: { [SLOT_ESSENTIELLE]: {}, [SLOT_PREMIUM]: {} },
}

function frErr(err, fallback = 'Une erreur est survenue.') {
  const data = err?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  return fallback
}

function normalizeMarques(marques) {
  const src = marques && typeof marques === 'object' ? marques : {}
  return {
    [SLOT_ESSENTIELLE]: { ...(src[SLOT_ESSENTIELLE] || {}) },
    [SLOT_PREMIUM]: { ...(src[SLOT_PREMIUM] || {}) },
  }
}

export default function GammesMarquesPage() {
  const [id, setId] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let active = true
    ventesApi.getParametresGammes()
      .then((r) => {
        if (!active) return
        const data = r.data ?? {}
        setId(data.id ?? null)
        setForm({
          deux_gammes: !!data.deux_gammes,
          nom_essentielle: data.nom_essentielle || SLOT_ESSENTIELLE,
          nom_premium: data.nom_premium || SLOT_PREMIUM,
          marques: normalizeMarques(data.marques),
        })
      })
      .catch(() => toast.error('Chargement des réglages « Gammes & marques » impossible.'))
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const setField = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const setMarque = (slot, role, value) => setForm((f) => ({
    ...f,
    marques: {
      ...f.marques,
      [slot]: { ...(f.marques[slot] || {}), [role]: value },
    },
  }))

  const submit = (e) => {
    e.preventDefault()
    setSaving(true)
    ventesApi.updateParametresGammes(form)
      .then((r) => {
        const data = r.data ?? {}
        setId(data.id ?? id)
        setForm((f) => ({
          ...f,
          deux_gammes: data.deux_gammes ?? f.deux_gammes,
          nom_essentielle: data.nom_essentielle || f.nom_essentielle,
          nom_premium: data.nom_premium || f.nom_premium,
          marques: data.marques ? normalizeMarques(data.marques) : f.marques,
        }))
        toast.success('Réglages « Gammes & marques » enregistrés.')
      })
      .catch((err) => toast.error(frErr(err, "L'enregistrement a échoué.")))
      .finally(() => setSaving(false))
  }

  if (loading) {
    return (
      <div className="page">
        <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground">
          <Spinner /> Chargement…
        </p>
      </div>
    )
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Gammes &amp; marques</h1>
        <div className="page-subtitle">
          Offre à une ou deux gammes, libellés affichés, et marque préférée par
          gamme et par rôle de composition automatique du devis.
        </div>
      </div>

      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <Card>
          <CardContent className="flex flex-col gap-3 pt-4 sm:pt-5">
            <h2 className="flex items-center gap-1.5 text-sm font-semibold">
              <Layers className="size-4 text-muted-foreground" aria-hidden="true" />
              Offre à deux gammes
            </h2>
            <label className="flex items-center gap-2 text-sm text-foreground">
              <Switch
                id="gm-deux-gammes"
                aria-label="Activer l'offre à deux gammes"
                checked={form.deux_gammes}
                onCheckedChange={(v) => setField('deux_gammes', v)}
              />
              Proposer systématiquement DEUX gammes de devis (une paire de
              devis frères) plutôt qu'une seule
            </label>
            <p className="text-xs text-muted-foreground">
              Désactivé par défaut — comportement historique (une seule
              gamme, aucun choix affiché au client).
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <Label htmlFor="gm-nom-essentielle">Libellé de la gamme Essentielle</Label>
                <Input id="gm-nom-essentielle" value={form.nom_essentielle}
                       onChange={(e) => setField('nom_essentielle', e.target.value)} />
              </div>
              <div>
                <Label htmlFor="gm-nom-premium">Libellé de la gamme Premium</Label>
                <Input id="gm-nom-premium" value={form.nom_premium}
                       onChange={(e) => setField('nom_premium', e.target.value)} />
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              Renommer un libellé (ex. « Premium » → « Luxe ») ne touche à
              aucune marque déjà réglée ci-dessous — les préférences restent
              attachées à la gamme, pas à son nom affiché.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex flex-col gap-3 pt-4 sm:pt-5">
            <h2 className="flex items-center gap-1.5 text-sm font-semibold">
              <Tags className="size-4 text-muted-foreground" aria-hidden="true" />
              Marques préférées par rôle
            </h2>
            <p className="text-xs text-muted-foreground">
              Un champ vide = aucune préférence (le générateur choisit comme
              aujourd'hui). Une marque saisie GAGNE TOUJOURS : si aucun produit
              de cette marque n'est en stock pour ce rôle, la ligne reste SANS
              produit — jamais une autre marque à la place.
            </p>
            {!form.deux_gammes && (
              <p className="text-xs text-muted-foreground">
                Offre à une seule gamme : seule la colonne « {form.nom_essentielle} »
                est active. La colonne « {form.nom_premium} » reste enregistrée
                mais inactive tant que « Offre à deux gammes » est désactivé.
              </p>
            )}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-muted-foreground">
                    <th className="py-1 pr-3 font-medium">Rôle</th>
                    <th className="py-1 pr-3 font-medium">{form.nom_essentielle}</th>
                    {form.deux_gammes && (
                      <th className="py-1 pr-3 font-medium">{form.nom_premium}</th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {PRODUCT_CATEGORIES.map(([role, label]) => (
                    <tr key={role} className="border-t border-border/60">
                      <td className="py-1.5 pr-3 text-foreground">{label}</td>
                      <td className="py-1.5 pr-3">
                        <Input
                          aria-label={`Marque ${form.nom_essentielle} — ${label}`}
                          placeholder="Pas de préférence"
                          value={form.marques[SLOT_ESSENTIELLE]?.[role] ?? ''}
                          onChange={(e) => setMarque(SLOT_ESSENTIELLE, role, e.target.value)}
                        />
                      </td>
                      {form.deux_gammes && (
                        <td className="py-1.5 pr-3">
                          <Input
                            aria-label={`Marque ${form.nom_premium} — ${label}`}
                            placeholder="Pas de préférence"
                            value={form.marques[SLOT_PREMIUM]?.[role] ?? ''}
                            onChange={(e) => setMarque(SLOT_PREMIUM, role, e.target.value)}
                          />
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-end">
          <Button type="submit" loading={saving}>
            {saving ? 'Enregistrement…' : 'Enregistrer'}
          </Button>
        </div>
      </form>
    </div>
  )
}
