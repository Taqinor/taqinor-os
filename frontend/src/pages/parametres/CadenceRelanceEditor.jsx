// MRY28 — Paramètres → CRM : éditeur des trois cadences de relance nommées
// (gabarit `parametres.CadenceRelanceEtape`, MRY4 — contrat `cadence_relance_v2`
// de MRY25). Édition EN PLACE des lignes seedées par cadence.
//
// CAD53 (décision fondateur du 21/09/2026) — l'éditeur OUVRE l'ajout et la
// suppression d'un barreau, et expose la case « Autorisée le dimanche
// (16 h-19 h) » que le moteur lit déjà (`dimanche_ok`). Garde-fou décisif :
// **jamais rétroactif**. Le gabarit est copié barreau par barreau à
// l'initialisation d'un plan (`initialiser_plan_relance`), donc un plan DÉJÀ
// lancé garde ses touches, ses libellés et ses dates — l'écran le rappelle en
// toutes lettres plutôt que de laisser la commerciale le deviner.
//
// CAD113 — un refus serveur ne part plus en toast générique : le sérialiseur
// renvoie ses erreurs PAR CHAMP (`validate_delai_minutes`,
// `validate_libelle`…), donc `detail` était `undefined` et le message EXACT
// était jeté. Le message s'affiche SOUS le champ fautif, avec un bandeau qui
// le NOMME et y renvoie (règle fondateur du 08/09/2026).
import { useEffect, useState } from 'react'
import { Plus, Trash2, Info, AlertTriangle } from 'lucide-react'
import parametresApi from '../../api/parametresApi'
import {
  Input, Switch, Spinner, Label, Button, IconButton, FormErrorSummary,
  Tabs, TabsList, TabsTrigger, TabsContent,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { ConfirmDialog } from '../../ui/ConfirmDialog'
import { toast } from '../../ui/confirm'

const CADENCES = [
  { value: 'contact', label: 'Contact' },
  { value: 'apres_devis', label: 'Après devis' },
  { value: 'reveil', label: 'Réveil' },
]

// L'enum du GABARIT de cadence, jamais `crm.Canal` (source du lead).
//
// CAD114 — `visite` n'est PLUS proposé à la configuration : la ligne de
// relance ne teste `etape.canal` que pour `appel` et les canaux de message,
// jamais pour `visite` ; une touche de canal « Visite » affichait donc un
// badge et proposait Appeler/WhatsApp comme les autres — un canal qui ne
// déclenche rien. Garde-fou du round 2 : on n'y câble SURTOUT PAS la modale
// de planification. Le seul barreau de canal visite est le J+35 générique,
// porté par des leads legacy souvent SANS devis : l'ouvrir
// institutionnaliserait la visite AVANT le devis, contre la doctrine du
// 15/09 (`PanneauProposerVisite` est gaté `apres_devis`).
const CANAUX = [
  { value: 'appel', label: 'Appel' },
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'email', label: 'E-mail' },
]

// CAD114 — un barreau EXISTANT qui porte déjà `visite` (le J+35 générique)
// doit continuer d'afficher sa valeur : elle est montrée en lecture, désactivée
// et étiquetée pour ce qu'elle est. Rien n'est réécrit en base — le canal se
// change vers un canal qui, lui, fait quelque chose.
const CANAL_VISITE_HERITE = {
  value: 'visite', label: 'Visite (héritée — ne déclenche rien)',
}

// Sentinel pour l'option « aucun » : Radix Select n'autorise pas la valeur ''.
const NONE = '__none__'

const asList = (data) => (Array.isArray(data) ? data : (data?.results ?? []))

// CAD53 — la phrase que l'écran doit dire, et qu'il ne disait pas : modifier
// le gabarit ne touche AUCUN plan en cours.
const AVERTISSEMENT_NON_RETROACTIF = (
  'Ces réglages ne s’appliquent qu’aux relances à venir : un plan déjà lancé '
  + 'garde ses touches, ses libellés et ses dates.'
)

// CAD113 — une cadence dont TOUS les barreaux sont désactivés devient muette
// sans un mot : plus aucune relance n'en naîtra. L'écran le dit.
const AVERTISSEMENT_CADENCE_MUETTE = (
  'Tous les barreaux de cette cadence sont désactivés : elle ne programmera '
  + 'plus aucune relance.'
)

// CAD113 — libellé FR de chaque champ, pour que le bandeau NOMME le champ
// fautif au lieu de citer sa clé technique. `id` = celui du champ à l'écran,
// pour que le clic du bandeau y renvoie.
const LIBELLES_CHAMPS = {
  libelle: ['Libellé', 'lib'],
  delai_jours: ['Délai (j)', 'jours'],
  delai_minutes: ['Délai (min)', 'min'],
  heure_cible: ['Heure cible', 'heure'],
  canal: ['Canal', 'canal'],
  template_cle: ['Gabarit de message', 'gab'],
  dimanche_ok: ['Autorisée le dimanche', 'dim'],
  actif: ['Active', 'actif'],
  ordre: ['Rang', 'ordre'],
}

/** CAD113 — le message du serveur, SOUS le champ. */
function ErreurChamp({ id, message }) {
  if (!message) return null
  return (
    <p id={id} role="alert" className="text-xs text-destructive">{message}</p>
  )
}

function CadenceTable({ cadence, gabarits }) {
  const [rows, setRows] = useState(null)
  // CAD53 — suppression d'un barreau : confirmation explicite, jamais un
  // `window.confirm` (patron maison `ConfirmDialog`).
  const [aSupprimer, setASupprimer] = useState(null)
  const [suppression, setSuppression] = useState(false)
  const [ajout, setAjout] = useState(false)
  // CAD113 — erreurs serveur PAR LIGNE puis PAR CHAMP : { [id]: { champ: msg } }
  const [erreurs, setErreurs] = useState({})

  useEffect(() => {
    let cancelled = false
    parametresApi.getCadenceRelance(cadence)
      .then(r => { if (!cancelled) setRows(asList(r.data)) })
      .catch(() => { if (!cancelled) setRows([]) })
    return () => { cancelled = true }
  }, [cadence])

  const recharger = () => parametresApi.getCadenceRelance(cadence)
    .then(r => setRows(asList(r.data)))
    .catch(() => { /* la liste affichée reste celle qu'on avait */ })

  const ajouter = async () => {
    setAjout(true)
    try {
      // `ordre` est calculé par le serveur (le seul à connaître la cadence
      // entière) ; le libellé est modifiable juste après, en place.
      await parametresApi.createCadenceRelanceEtape({
        cadence, libelle: 'Nouveau barreau', delai_jours: 1,
        delai_minutes: 0, canal: 'appel', template_cle: '',
        dimanche_ok: false, actif: true,
      })
      await recharger()
    } catch (e) {
      const data = e?.response?.data
      toast.error(data?.ordre ?? data?.detail ?? 'Ajout impossible.')
    } finally {
      setAjout(false)
    }
  }

  const confirmerSuppression = async () => {
    if (!aSupprimer) return
    setSuppression(true)
    try {
      await parametresApi.deleteCadenceRelanceEtape(aSupprimer.id)
      setASupprimer(null)
      await recharger()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Suppression impossible.')
    } finally {
      setSuppression(false)
    }
  }

  const patch = async (row, data) => {
    const prev = rows
    // Optimiste : reflète tout de suite, revient en arrière si le serveur refuse.
    setRows(rs => rs.map(r => (r.id === row.id ? { ...r, ...data } : r)))
    setErreurs(e => ({ ...e, [row.id]: {} }))
    try {
      await parametresApi.updateCadenceRelanceEtape(row.id, data)
    } catch (e) {
      setRows(prev)
      // CAD113 — le serveur renvoie ses refus PAR CHAMP
      // (`validate_delai_minutes`, `validate_libelle`…) : `detail` est alors
      // `undefined` et le toast générique jetait le message EXACT. Une 400 de
      // VALIDATION s'affiche désormais SOUS le champ fautif, avec un bandeau
      // qui le NOMME (règle fondateur du 08/09/2026, patron CKP4 de
      // `PlanifierVisiteModal`). Toute autre erreur (réseau, 500) garde une
      // phrase claire — jamais un « Modification impossible » muet.
      const corps = e?.response?.data
      if (e?.response?.status === 400 && corps && typeof corps === 'object'
          && !Array.isArray(corps)) {
        const parChamp = {}
        for (const [champ, messages] of Object.entries(corps)) {
          parChamp[champ] = Array.isArray(messages)
            ? String(messages[0]) : String(messages)
        }
        setErreurs(er => ({ ...er, [row.id]: parChamp }))
      } else {
        toast.error(corps?.detail
          ?? 'La modification n’a pas pu être enregistrée — réessayez.')
      }
    }
  }

  if (rows === null) return <Spinner />
  // CAD113 — helpers de rendu des erreurs serveur.
  const erreurDe = (row, champ) => erreurs[row.id]?.[champ] ?? ''
  const bandeau = (row) => Object.entries(erreurs[row.id] ?? {}).map(
    ([champ, message]) => {
      const [libelle, suffixe] = LIBELLES_CHAMPS[champ] ?? [champ, null]
      return {
        field: suffixe ? `cre-${suffixe}-${row.id}` : undefined,
        message: `${libelle} : ${message}`,
      }
    })
  // CAD113 — la cadence est-elle devenue MUETTE (tous ses barreaux inactifs) ?
  const muette = rows.length > 0 && rows.every(r => !r.actif)
  const entete = (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <p className="flex items-start gap-1.5 text-xs text-muted-foreground"
         role="note">
        <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
        {AVERTISSEMENT_NON_RETROACTIF}
      </p>
      <Button size="sm" variant="outline" onClick={ajouter} disabled={ajout}>
        <Plus className="size-3.5" /> Ajouter un barreau
      </Button>
    </div>
  )
  if (rows.length === 0) {
    return (
      <div className="space-y-2" data-testid={`cadence-table-${cadence}`}>
        {entete}
        <p className="py-2 text-xs text-muted-foreground">Aucune étape pour cette cadence.</p>
      </div>
    )
  }
  return (
    <div className="space-y-2" data-testid={`cadence-table-${cadence}`}>
      {entete}
      {muette && (
        <p role="alert"
           className="flex items-start gap-1.5 rounded-md border border-warning/40 px-3 py-2 text-xs text-foreground">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          {AVERTISSEMENT_CADENCE_MUETTE}
        </p>
      )}
      {rows.map(row => (
        <div key={row.id}
             className="flex flex-wrap items-end gap-2 border rounded-md px-3 py-2">
          <div className="w-8 shrink-0 pb-2 text-sm text-muted-foreground">
            #{row.ordre}
          </div>
          {/* CAD113 — le bandeau NOMME le champ fautif et y renvoie ; le
              message exact du serveur est répété sous le champ. */}
          {bandeau(row).length > 0 && (
            <div className="w-full">
              <FormErrorSummary errors={bandeau(row)} />
            </div>
          )}
          <div className="flex flex-col gap-1">
            <Label className="text-xs" htmlFor={`cre-lib-${row.id}`}>Libellé</Label>
            <Input id={`cre-lib-${row.id}`} className="w-40" defaultValue={row.libelle}
                   aria-invalid={!!erreurDe(row, 'libelle') || undefined}
                   aria-describedby={erreurDe(row, 'libelle') ? `cre-lib-${row.id}-err` : undefined}
                   onBlur={e => {
                     const v = e.target.value.trim()
                     if (v && v !== row.libelle) patch(row, { libelle: v })
                   }} />
            <ErreurChamp id={`cre-lib-${row.id}-err`} message={erreurDe(row, 'libelle')} />
          </div>
          <div className="flex flex-col gap-1">
            <Label className="text-xs" htmlFor={`cre-jours-${row.id}`}>Délai (j)</Label>
            <Input id={`cre-jours-${row.id}`} className="w-16" type="number" min="0" step="1"
                   defaultValue={row.delai_jours}
                   aria-invalid={!!erreurDe(row, 'delai_jours') || undefined}
                   aria-describedby={erreurDe(row, 'delai_jours') ? `cre-jours-${row.id}-err` : undefined}
                   onBlur={e => {
                     const v = Math.max(0, Math.trunc(Number(e.target.value) || 0))
                     if (v !== row.delai_jours) patch(row, { delai_jours: v })
                   }} />
            <ErreurChamp id={`cre-jours-${row.id}-err`} message={erreurDe(row, 'delai_jours')} />
          </div>
          <div className="flex flex-col gap-1">
            <Label className="text-xs" htmlFor={`cre-min-${row.id}`}>Délai (min)</Label>
            <Input id={`cre-min-${row.id}`} className="w-16" type="number" min="0" max="1439" step="1"
                   defaultValue={row.delai_minutes}
                   aria-invalid={!!erreurDe(row, 'delai_minutes') || undefined}
                   aria-describedby={erreurDe(row, 'delai_minutes') ? `cre-min-${row.id}-err` : undefined}
                   onBlur={e => {
                     const v = Math.max(0, Math.trunc(Number(e.target.value) || 0))
                     if (v !== row.delai_minutes) patch(row, { delai_minutes: v })
                   }} />
            <ErreurChamp id={`cre-min-${row.id}-err`} message={erreurDe(row, 'delai_minutes')} />
          </div>
          <div className="flex flex-col gap-1">
            <Label className="text-xs" htmlFor={`cre-heure-${row.id}`}>Heure cible</Label>
            <Input id={`cre-heure-${row.id}`} className="w-28" type="time"
                   defaultValue={row.heure_cible ? row.heure_cible.slice(0, 5) : ''}
                   onBlur={e => {
                     const v = e.target.value || null
                     if (v !== (row.heure_cible ? row.heure_cible.slice(0, 5) : null)) {
                       patch(row, { heure_cible: v })
                     }
                   }} />
          </div>
          <div className="flex flex-col gap-1">
            <Label className="text-xs" id={`cre-canal-lbl-${row.id}`}>Canal</Label>
            <Select value={row.canal} onValueChange={v => patch(row, { canal: v })}>
              <SelectTrigger className="w-32" aria-labelledby={`cre-canal-lbl-${row.id}`}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CANAUX.map(c => (
                  <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>
                ))}
                {/* CAD114 — proposé à AUCUNE nouvelle configuration ; présent
                    seulement pour que le barreau qui le porte déjà affiche sa
                    valeur au lieu d'un champ vide. */}
                {row.canal === CANAL_VISITE_HERITE.value && (
                  <SelectItem value={CANAL_VISITE_HERITE.value} disabled>
                    {CANAL_VISITE_HERITE.label}
                  </SelectItem>
                )}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <Label className="text-xs" id={`cre-gab-lbl-${row.id}`}>Gabarit de message</Label>
            <Select value={row.template_cle || NONE}
                    onValueChange={v => patch(row, { template_cle: v === NONE ? '' : v })}>
              <SelectTrigger className="w-48" aria-labelledby={`cre-gab-lbl-${row.id}`}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>— Aucun —</SelectItem>
                {gabarits.map(g => (
                  <SelectItem key={g.cle} value={g.cle}>{g.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {/* CAD53 — la case que le moteur lit déjà (`dimanche_ok`) : seule
              une touche marquée ainsi peut tomber un dimanche, dans la
              fenêtre 16 h-19 h du protocole v3. Elle était invisible ici. */}
          <label className="flex items-center gap-1.5 pb-2 text-sm text-foreground">
            <Switch checked={!!row.dimanche_ok}
                    onCheckedChange={v => patch(row, { dimanche_ok: v })}
                    aria-label={`Autorisée le dimanche (16 h-19 h) — étape ${row.ordre}`} />
            Dimanche
          </label>
          <label className="flex items-center gap-1.5 pb-2 text-sm text-foreground">
            <Switch checked={row.actif} onCheckedChange={v => patch(row, { actif: v })}
                    aria-label={`Active — étape ${row.ordre}`} />
            Active
          </label>
          <IconButton className="mb-1" variant="ghost" size="sm"
                      aria-label={`Supprimer le barreau ${row.ordre}`}
                      onClick={() => setASupprimer(row)}>
            <Trash2 className="size-4" />
          </IconButton>
        </div>
      ))}
      <ConfirmDialog
        open={aSupprimer != null}
        onOpenChange={o => { if (!o) setASupprimer(null) }}
        title="Supprimer ce barreau de la cadence ?"
        description={
          `« ${aSupprimer?.libelle ?? ''} » ne sera plus posé sur les futurs `
          + `plans. ${AVERTISSEMENT_NON_RETROACTIF}`
        }
        confirmLabel="Supprimer"
        loading={suppression}
        onConfirm={confirmerSuppression}
      />
    </div>
  )
}

// CAD143 (21/09/2026) — la cadence « Générique » (`Cadence.GENERIQUE`, 5
// barreaux J+2/5/10/20/35) n'a pas d'onglet d'édition alors qu'elle reste
// LUE et actionnable côté fiche : des leads d'avant le protocole v3 tournent
// encore dessus (`materialiser_touche_suivante` ne l'exclut pas). Aucun
// appelant ne DÉMARRE plus de cadence générique (round 2) — cet onglet est
// donc en LECTURE SEULE, pour que le fondateur puisse au moins la voir ; rien
// n'est réorganisé, les trois onglets ci-dessus sont inchangés.
const CADENCE_GENERIQUE = {
  value: 'generique',
  label: 'Générique — historique, ne plus assigner',
}

function CadenceTableReadOnly({ cadence }) {
  const [rows, setRows] = useState(null)

  useEffect(() => {
    let cancelled = false
    parametresApi.getCadenceRelance(cadence)
      .then(r => { if (!cancelled) setRows(asList(r.data)) })
      .catch(() => { if (!cancelled) setRows([]) })
    return () => { cancelled = true }
  }, [cadence])

  if (rows === null) return <Spinner />
  if (rows.length === 0) {
    return <p className="py-2 text-xs text-muted-foreground">Aucune étape pour cette cadence.</p>
  }
  return (
    <div className="space-y-2" data-testid={`cadence-table-${cadence}`}>
      {rows.map(row => (
        <div key={row.id}
             className="flex flex-wrap items-center gap-4 border rounded-md px-3 py-2 text-sm text-muted-foreground">
          <span className="w-8 shrink-0">#{row.ordre}</span>
          <span className="text-foreground">{row.libelle}</span>
          <span>J+{row.delai_jours}</span>
          <span>{CANAUX.find(c => c.value === row.canal)?.label ?? row.canal}</span>
          <span>{row.actif ? 'Active' : 'Inactive'}</span>
        </div>
      ))}
    </div>
  )
}

export default function CadenceRelanceEditor() {
  const [tab, setTab] = useState('contact')
  const [gabarits, setGabarits] = useState([])

  useEffect(() => {
    parametresApi.getMessages()
      .then(r => setGabarits(asList(r.data).map(m => ({ cle: m.cle, label: m.label }))))
      .catch(() => setGabarits([]))
  }, [])

  return (
    <Tabs value={tab} onValueChange={setTab} data-testid="cadence-relance-editor">
      <TabsList>
        {CADENCES.map(c => (
          <TabsTrigger key={c.value} value={c.value}>{c.label}</TabsTrigger>
        ))}
        <TabsTrigger value={CADENCE_GENERIQUE.value}>{CADENCE_GENERIQUE.label}</TabsTrigger>
      </TabsList>
      {CADENCES.map(c => (
        <TabsContent key={c.value} value={c.value}>
          {c.value === 'reveil' && (
            // CAD68 — le moteur (apps.crm.services._adapter_gabarits_reveil)
            // remplace le gabarit choisi ici selon le dossier du lead : le
            // texte réglé pour la ligne J60 ne part donc jamais tel quel.
            <p className="mb-2 text-xs text-muted-foreground"
               data-testid="reveil-gabarit-note">
              Gabarit choisi selon que le lead a déjà reçu un devis : à J30, « reveil_a1 »
              part s'il en a déjà reçu un, « reveil_a2 » sinon ; à J60, tous reçoivent
              « reveil_a3 » — le gabarit réglé ici pour la ligne J60 ne part jamais tel quel.
            </p>
          )}
          <CadenceTable cadence={c.value} gabarits={gabarits} />
        </TabsContent>
      ))}
      <TabsContent value={CADENCE_GENERIQUE.value}>
        <CadenceTableReadOnly cadence={CADENCE_GENERIQUE.value} />
      </TabsContent>
    </Tabs>
  )
}
