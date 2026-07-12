// Onglet « Statuts » de la page Paramètres (N58).
// Permet de RENOMMER, RÉORDONNER et MASQUER les statuts métier — chantier, SAV
// et bon de commande — par société. Couche PUREMENT D'AFFICHAGE : les clés
// canoniques et la machine à états restent figées côté serveur ; l'entonnoir
// du lead (STAGES.py) n'est NI touché NI exposé ici.
//
// Section autonome (comme les listes gérées) : elle charge sa propre config,
// gère son propre état d'édition et s'enregistre via l'endpoint dédié
// (parametresApi.saveStatuts). Tant que rien n'est modifié, l'affichage reste
// identique aux libellés codés en dur.
import { useEffect, useState } from 'react'
import { ChevronUp, ChevronDown, Eye, EyeOff, RotateCcw, Save, CheckCircle2 } from 'lucide-react'
import parametresApi from '../../api/parametresApi'
import { Card, CardContent, Input, IconButton, Button, Spinner, Badge } from '../../ui'
import { SectionTitle } from './peComponents'
import { toast } from '../../ui/confirm'

// Les 3 domaines configurables (libellés FR). L'ordre d'apparition à l'écran.
const DOMAINES = [
  {
    key: 'chantier',
    label: 'Statuts de chantier',
    hint: 'Étapes de réalisation des chantiers (réalisation physique). '
      + 'Renommer ou réordonner ne change que l’affichage : les chantiers '
      + 'existants et les transitions restent intacts.',
    icon: <><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /><polyline points="9 22 9 12 15 12 15 22" /></>,
  },
  {
    key: 'sav',
    label: 'Statuts SAV (tickets)',
    hint: 'Cycle de vie des tickets de service après-vente. Couche '
      + 'd’affichage uniquement : les tickets existants ne changent pas.',
    icon: <><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" /></>,
  },
  {
    key: 'bon_commande',
    label: 'Statuts de bon de commande',
    hint: 'Suivi des bons de commande fournisseur. Renommer/réordonner '
      + 'n’affecte que l’affichage.',
    icon: <><path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" /></>,
  },
]

// Une sous-liste éditable pour UN domaine. Charge l'effectif, édite en local,
// enregistre via l'endpoint bulk. Réordonne par flèches ; masque par l'œil.
function DomaineList({ domaine, label, hint, icon }) {
  const [rows, setRows] = useState(null) // null = en cours de chargement
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    parametresApi.getStatutsEffective(domaine)
      .then(r => setRows((r.data?.results ?? []).map(x => ({ ...x }))))
      .catch(() => setRows([]))
  }, [domaine])

  const setLibelle = (cle, libelle) =>
    setRows(rs => rs.map(r => (r.cle === cle ? { ...r, libelle } : r)))
  const toggleActif = (cle) =>
    setRows(rs => rs.map(r => (r.cle === cle ? { ...r, actif: !r.actif } : r)))
  const resetLibelle = (row) =>
    setRows(rs => rs.map(r => (r.cle === row.cle ? { ...r, libelle: r.libelle_defaut } : r)))

  // Réordonne (échange visuel) puis renumérote `ordre` sur la liste affichée.
  const move = (index, delta) => {
    setRows(rs => {
      const arr = [...rs]
      const j = index + delta
      if (j < 0 || j >= arr.length) return rs
      const tmp = arr[index]; arr[index] = arr[j]; arr[j] = tmp
      return arr.map((r, i) => ({ ...r, ordre: i }))
    })
  }

  const save = async () => {
    if (!rows) return
    setSaving(true)
    try {
      const payload = rows.map((r, i) => ({
        cle: r.cle,
        libelle: (r.libelle || '').trim() || r.libelle_defaut,
        ordre: i,
        actif: !!r.actif,
      }))
      const res = await parametresApi.saveStatuts(domaine, payload)
      setRows((res.data?.results ?? payload).map(x => ({ ...x })))
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Enregistrement impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <CardContent className="pt-4 sm:pt-5">
        <SectionTitle label={label} icon={icon} />
        <p className="mb-3.5 text-[11.5px] text-muted-foreground">{hint}</p>

        {rows === null ? (
          <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
            <Spinner className="size-4 text-primary" /> Chargement…
          </div>
        ) : (
          <>
            <div className="mb-3 flex flex-col gap-1.5">
              {rows.map((r, i) => (
                <div key={r.cle} className="flex items-center gap-1.5">
                  {/* Réordonnancement */}
                  <div className="flex flex-col">
                    <IconButton size="sm" variant="ghost" label="Monter"
                      disabled={i === 0} onClick={() => move(i, -1)}>
                      <ChevronUp className="size-3.5" aria-hidden="true" />
                    </IconButton>
                    <IconButton size="sm" variant="ghost" label="Descendre"
                      disabled={i === rows.length - 1} onClick={() => move(i, 1)}>
                      <ChevronDown className="size-3.5" aria-hidden="true" />
                    </IconButton>
                  </div>
                  {/* Libellé éditable */}
                  <Input
                    className={['flex-1', r.actif ? '' : 'opacity-50'].join(' ')}
                    value={r.libelle}
                    aria-label={`Libellé du statut ${r.cle}`}
                    onChange={e => setLibelle(r.cle, e.target.value)}
                  />
                  {/* Clé canonique (figée) en repère discret */}
                  <span className="hidden w-[120px] shrink-0 truncate font-mono text-[10.5px] text-muted-foreground sm:inline">
                    {r.cle}
                  </span>
                  {r.personnalise && <Badge tone="info">modifié</Badge>}
                  {/* Réinitialiser le libellé par défaut */}
                  {r.libelle !== r.libelle_defaut && (
                    <IconButton size="sm" variant="ghost" label="Rétablir le libellé par défaut"
                      title={`Rétablir « ${r.libelle_defaut} »`}
                      onClick={() => resetLibelle(r)}>
                      <RotateCcw className="size-3.5" aria-hidden="true" />
                    </IconButton>
                  )}
                  {/* Visibilité (masquage d'affichage — n'affecte pas les transitions) */}
                  <IconButton size="sm" variant="ghost"
                    label={r.actif ? 'Masquer ce statut' : 'Afficher ce statut'}
                    title={r.actif ? 'Masquer (affichage uniquement)' : 'Afficher'}
                    onClick={() => toggleActif(r.cle)}>
                    {r.actif
                      ? <Eye className="size-3.5" aria-hidden="true" />
                      : <EyeOff className="size-3.5 text-muted-foreground" aria-hidden="true" />}
                  </IconButton>
                </div>
              ))}
            </div>

            <Button type="button" size="sm" onClick={save} loading={saving}
              disabled={saving} variant={saved ? 'success' : 'default'}>
              {saved
                ? <><CheckCircle2 className="size-4" aria-hidden="true" /> Enregistré !</>
                : <><Save className="size-4" aria-hidden="true" /> Enregistrer</>}
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  )
}

export default function StatutsSection() {
  return (
    <>
      <div className="rounded-xl border border-border bg-muted/30 px-4 py-3 text-[12.5px] leading-relaxed text-muted-foreground">
        Renommez, réordonnez ou masquez les statuts de chantier, de SAV et de
        bon de commande. Ces réglages ne changent que l’<strong>affichage</strong> :
        les clés internes, les transitions et les données existantes restent
        intactes. L’entonnoir des leads est géré séparément.
      </div>
      {DOMAINES.map(d => (
        <DomaineList key={d.key} domaine={d.key} label={d.label}
          hint={d.hint} icon={d.icon} />
      ))}
    </>
  )
}
