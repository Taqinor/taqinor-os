// Onglet « Modèles de documents » de la page Paramètres (D2/N60/N67/N26/N59).
// Édite les portions de TEXTE du devis premium : validité de l'offre, conditions
// générales (titre + puces), garanties, bloc « Bon pour accord » et libellé du
// tampon d'acceptation. Couche purement ÉDITORIALE : laisser un champ VIDE = le
// moteur applique le littéral historique, donc le PDF reste identique tant que
// rien n'est saisi. Aucun statut de devis ni montant n'est touché.
//
// Section autonome (comme StatutsSection) : charge ses propres réglages, édite
// en local, enregistre via parametresApi.updateDocumentTemplates.
import { useEffect, useState } from 'react'
import { Save, CheckCircle2, Plus, Trash2 } from 'lucide-react'
import parametresApi from '../../api/parametresApi'
import { Card, CardContent, Input, Textarea, Button, IconButton, Spinner } from '../../ui'
import { SectionTitle } from './peComponents'
import { toast } from '../../ui/confirm'

// Aperçu (placeholder) du littéral historique de chaque champ. Affiché en
// indice quand le champ est vide : c'est EXACTEMENT le texte imprimé par défaut.
const DEFAULTS = {
  validite_badge_p1: 'Validité : 30 jours',
  validite_onepage: '· Validité : 30 jours',
  cgv_titre: 'Conditions générales du devis',
  garantie_titre: 'Garanties jusqu’à 30 ans',
  garantie_detail:
    'Structure 20 ans, panneaux 12 ans produit + 30 ans performance (87,4 %), onduleur 10 ans. Sérénité totale.',
  garantie_perf_label: 'Performance panneau (87,4 %)',
  bpa_titre: 'Bon pour accord',
  bpa_mention: 'Lu et approuvé — Signature précédée de « Bon pour accord »',
  acceptance_stamp: 'Accepté le {date} par {nom}',
}

// Puces des conditions générales (défaut historique). {acompte}/{materiel}/
// {solde}/{tva_note} sont remplis automatiquement sur le PDF.
const DEFAULT_BULLETS = [
  'Validité de l’offre : 30 jours',
  'Acompte à la commande : {acompte}%',
  '{materiel}% à la réception du matériel',
  '{solde}% après la mise en marche',
  'Délai d’installation : 7–14 jours ouvrés',
  '{tva_note}',
  'Tarifs de référence : barème ONEE/SRM',
]

// Un champ texte mono-ligne avec libellé + indice du défaut.
function TextField({ label, value, hint, onChange, multiline }) {
  return (
    <label className="block">
      <span className="mb-1 block text-[12.5px] font-medium text-foreground">{label}</span>
      {multiline ? (
        <Textarea rows={3} value={value} placeholder={hint}
          onChange={e => onChange(e.target.value)} />
      ) : (
        <Input value={value} placeholder={hint}
          onChange={e => onChange(e.target.value)} />
      )}
      <span className="mt-1 block text-[11px] text-muted-foreground">
        Vide = texte par défaut : <em>{hint}</em>
      </span>
    </label>
  )
}

export default function DocumentsSection() {
  const [form, setForm] = useState(null) // null = chargement
  const [bullets, setBullets] = useState(null)
  const [version, setVersion] = useState(1)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    parametresApi.getDocumentTemplates()
      .then(r => {
        const d = r.data || {}
        setForm({
          validite_badge_p1: d.validite_badge_p1 || '',
          validite_onepage: d.validite_onepage || '',
          cgv_titre: d.cgv_titre || '',
          garantie_titre: d.garantie_titre || '',
          garantie_detail: d.garantie_detail || '',
          garantie_perf_label: d.garantie_perf_label || '',
          bpa_titre: d.bpa_titre || '',
          bpa_mention: d.bpa_mention || '',
          acceptance_stamp: d.acceptance_stamp || '',
        })
        setBullets(Array.isArray(d.cgv_bullets) && d.cgv_bullets.length
          ? d.cgv_bullets : null)
        setVersion(d.version || 1)
      })
      .catch(() => {
        setForm({
          validite_badge_p1: '', validite_onepage: '', cgv_titre: '',
          garantie_titre: '', garantie_detail: '', garantie_perf_label: '',
          bpa_titre: '', bpa_mention: '', acceptance_stamp: '',
        })
        setBullets(null)
      })
  }, [])

  const set = (key, val) => setForm(f => ({ ...f, [key]: val }))

  // Puces : null = défaut moteur. Première édition → copie du défaut pour éditer.
  const editedBullets = bullets ?? DEFAULT_BULLETS
  const setBullet = (i, val) =>
    setBullets(b => (b ?? DEFAULT_BULLETS).map((x, j) => (j === i ? val : x)))
  const addBullet = () => setBullets(b => [...(b ?? DEFAULT_BULLETS), ''])
  const removeBullet = (i) =>
    setBullets(b => (b ?? DEFAULT_BULLETS).filter((_, j) => j !== i))
  const resetBullets = () => setBullets(null)

  const save = async () => {
    if (!form) return
    setSaving(true)
    try {
      const payload = { ...form }
      // Puces : on envoie la liste seulement si elle a été personnalisée
      // (sinon null = repli sur les puces historiques côté moteur).
      payload.cgv_bullets = bullets && bullets.length ? bullets : null
      const res = await parametresApi.updateDocumentTemplates(payload)
      setVersion(res.data?.version || version)
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Enregistrement impossible.')
    } finally {
      setSaving(false)
    }
  }

  if (form === null) {
    return (
      <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
        <Spinner className="size-4 text-primary" /> Chargement…
      </div>
    )
  }

  return (
    <>
      <div className="rounded-xl border border-border bg-muted/30 px-4 py-3 text-[12.5px] leading-relaxed text-muted-foreground">
        Personnalisez les <strong>textes</strong> imprimés sur le devis (proposition).
        Laisser un champ <strong>vide</strong> conserve le texte par défaut : le PDF
        reste alors strictement identique. Les montants, les statuts et la mise en
        page ne changent pas. <span className="whitespace-nowrap">Révision actuelle : v{version}.</span>
      </div>

      {/* Validité de l'offre */}
      <Card>
        <CardContent className="space-y-3 pt-4 sm:pt-5">
          <SectionTitle label="Validité de l’offre"
            icon={<><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></>} />
          <TextField label="Badge (page 1)" hint={DEFAULTS.validite_badge_p1}
            value={form.validite_badge_p1} onChange={v => set('validite_badge_p1', v)} />
          <TextField label="Format une page" hint={DEFAULTS.validite_onepage}
            value={form.validite_onepage} onChange={v => set('validite_onepage', v)} />
        </CardContent>
      </Card>

      {/* Conditions générales */}
      <Card>
        <CardContent className="space-y-3 pt-4 sm:pt-5">
          <SectionTitle label="Conditions générales du devis"
            icon={<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /></>} />
          <TextField label="Titre" hint={DEFAULTS.cgv_titre}
            value={form.cgv_titre} onChange={v => set('cgv_titre', v)} />
          <div>
            <span className="mb-1 block text-[12.5px] font-medium text-foreground">Puces</span>
            <p className="mb-2 text-[11px] text-muted-foreground">
              Les marqueurs <code>{'{acompte}'}</code>, <code>{'{materiel}'}</code>,
              {' '}<code>{'{solde}'}</code> et <code>{'{tva_note}'}</code> sont remplis
              automatiquement sur le PDF.
            </p>
            <div className="flex flex-col gap-1.5">
              {editedBullets.map((b, i) => (
                <div key={i} className="flex items-center gap-1.5">
                  <Input className="flex-1" value={b}
                    aria-label={`Puce ${i + 1}`}
                    onChange={e => setBullet(i, e.target.value)} />
                  <IconButton size="sm" variant="ghost" label="Supprimer cette puce"
                    onClick={() => removeBullet(i)}>
                    <Trash2 className="size-3.5" aria-hidden="true" />
                  </IconButton>
                </div>
              ))}
            </div>
            <div className="mt-2 flex gap-2">
              <Button type="button" size="sm" variant="outline" onClick={addBullet}>
                <Plus className="size-4" aria-hidden="true" /> Ajouter une puce
              </Button>
              {bullets && (
                <Button type="button" size="sm" variant="ghost" onClick={resetBullets}>
                  Rétablir les puces par défaut
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Garanties */}
      <Card>
        <CardContent className="space-y-3 pt-4 sm:pt-5">
          <SectionTitle label="Garanties"
            icon={<><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></>} />
          <TextField label="Titre" hint={DEFAULTS.garantie_titre}
            value={form.garantie_titre} onChange={v => set('garantie_titre', v)} />
          <TextField label="Détail" hint={DEFAULTS.garantie_detail} multiline
            value={form.garantie_detail} onChange={v => set('garantie_detail', v)} />
          <TextField label="Libellé performance" hint={DEFAULTS.garantie_perf_label}
            value={form.garantie_perf_label} onChange={v => set('garantie_perf_label', v)} />
        </CardContent>
      </Card>

      {/* Bon pour accord + tampon d'acceptation */}
      <Card>
        <CardContent className="space-y-3 pt-4 sm:pt-5">
          <SectionTitle label="Signature & acceptation"
            icon={<><path d="M12 19l7-7 3 3-7 7-3-3z" /><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z" /><path d="M2 2l7.586 7.586" /></>} />
          <TextField label="Titre « Bon pour accord »" hint={DEFAULTS.bpa_titre}
            value={form.bpa_titre} onChange={v => set('bpa_titre', v)} />
          <TextField label="Mention manuscrite" hint={DEFAULTS.bpa_mention} multiline
            value={form.bpa_mention} onChange={v => set('bpa_mention', v)} />
          <TextField label="Libellé du tampon d’acceptation"
            hint={DEFAULTS.acceptance_stamp}
            value={form.acceptance_stamp} onChange={v => set('acceptance_stamp', v)} />
          <p className="text-[11px] text-muted-foreground">
            Le tampon n’apparaît que lorsqu’un devis est accepté (nom + date saisis).
            Les marqueurs <code>{'{date}'}</code> et <code>{'{nom}'}</code> sont remplis automatiquement.
          </p>
        </CardContent>
      </Card>

      <Button type="button" size="sm" onClick={save} loading={saving}
        disabled={saving} variant={saved ? 'success' : 'default'}>
        {saved
          ? <><CheckCircle2 className="size-4" aria-hidden="true" /> Enregistré !</>
          : <><Save className="size-4" aria-hidden="true" /> Enregistrer</>}
      </Button>
    </>
  )
}
