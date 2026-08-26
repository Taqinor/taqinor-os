// CH6 — Timeline de cycle de vie du chantier : remplace le simple sélecteur de
// statut par un parcours d'étapes/gates GUIDÉ (CH1/CH2), avec la recette de
// mise en service IEC 62446-1 (CH3) et le pack de remise client (CH4) mis en
// avant comme des gates de premier plan. Field/mobile-friendly : une seule
// colonne, gros boutons, raisons de blocage explicites en français.
// APX26 — la fiche chantier n'a plus DEUX timelines empilées : les jalons datés
// (ex-`ChantierTimeline`, rendu dans une section « Timeline » à part) sont
// fusionnés DANS ce stepper, sous une progression « 3/7 » en tête, et le
// bandeau « Prochaine action » passe sur `ui/NextActionBanner` (partagé avec
// « Ma journée »).
import { useEffect, useState } from 'react'
import { CheckCircle2, Circle, Lock, ClipboardCheck, PackageCheck } from 'lucide-react'
import installationsApi from '../../api/installationsApi'
import {
  Button, Badge, HelpTip, Spinner, Progress, NextActionBanner,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DialogFooter, Input, Textarea, Label,
} from '../../ui'
import ChantierTimeline from './ChantierTimeline'

/* ── WIR202/CH3 — fiche de recette IEC 62446-1 : formulaire de SAISIE ───────
   Le bouton « Ouvrir la fiche de recette » créait un enregistrement VIDE
   (`resultat = en_cours`) que rien ne pouvait ensuite remplir : le gate
   « Mise en service » restait bloqué à jamais. Il ouvre désormais ce
   formulaire ; l'enregistrement n'est créé qu'à la PREMIÈRE sauvegarde.
   Aucun montant, aucun prix d'achat n'apparaît ici — essais uniquement. */

// Les essais sont des booléens NULLABLES (non renseigné ≠ non conforme).
const TRI_ETAT = [
  { value: '', label: 'Non renseigné' },
  { value: 'true', label: 'Conforme' },
  { value: 'false', label: 'Non conforme' },
]

const RESULTATS = [
  { value: 'en_cours', label: 'En cours' },
  { value: 'conforme', label: 'Conforme' },
  { value: 'reserves', label: 'Conforme avec réserves' },
  { value: 'non_conforme', label: 'Non conforme' },
]

// Les 4 sections du sérialiseur `CommissioningRecordSerializer`.
const SECTIONS = [
  {
    titre: 'Documentation (§4)',
    essais: [
      ['doc_dossier_ok', 'Dossier as-built présent'],
      ['doc_schema_ok', 'Schéma électrique présent'],
      ['doc_datasheets_ok', 'Fiches techniques présentes'],
    ],
    mesures: [],
  },
  {
    titre: 'Inspection visuelle (§5)',
    essais: [
      ['visuel_structure_ok', 'Structure'],
      ['visuel_cablage_ok', 'Câblage'],
      ['visuel_terre_ok', 'Mise à la terre'],
    ],
    mesures: [],
  },
  {
    titre: 'Essais électriques (§6)',
    essais: [
      ['continuite_terre_ok', 'Continuité de terre'],
      ['polarite_ok', 'Polarité'],
      ['isolement_ok', 'Résistance d’isolement'],
    ],
    mesures: [
      ['continuite_terre_ohm', 'Continuité de terre (Ω)'],
      ['isolement_mohm', 'Résistance d’isolement (MΩ)'],
    ],
  },
  {
    titre: 'Performance et sécurité (§7)',
    essais: [
      ['performance_ok', 'Performance'],
      ['securite_coupure_ok', 'Dispositifs de coupure'],
      ['securite_signalisation_ok', 'Signalisation'],
    ],
    mesures: [
      ['production_test_kw', 'Production d’essai (kW)'],
      ['production_attendue_kw', 'Production attendue (kW)'],
    ],
  },
]

const IV_CHAMPS = [
  ['string_label', 'String', 'text'],
  ['n_modules_serie', 'Modules en série', 'number'],
  ['voc_mesure_v', 'Voc mesuré (V)', 'number'],
  ['isc_mesure_a', 'Isc mesuré (A)', 'number'],
  ['pmax_mesure_w', 'Pmax mesuré (W)', 'number'],
  ['voc_attendu_v', 'Voc attendu (V)', 'number'],
  ['isc_attendu_a', 'Isc attendu (A)', 'number'],
  ['pmax_attendu_w', 'Pmax attendu (W)', 'number'],
]

const IV_VIDE = Object.fromEntries(IV_CHAMPS.map(([k]) => [k, '']))

// Un booléen nullable ↔ la valeur textuelle du <select>.
const boolVersTexte = (v) => (v === true ? 'true' : v === false ? 'false' : '')
const texteVersBool = (v) => (v === 'true' ? true : v === 'false' ? false : null)
// Un nombre TAPÉ n'est jamais rogné ni arrondi : il part tel quel, ou null.
const nombreOuNull = (v) => (v === '' || v == null ? null : v)

function etatDepuisRecord(record) {
  const etat = {
    date_essai: record?.date_essai ?? '',
    technicien: record?.technicien ?? '',
    resultat: record?.resultat ?? 'en_cours',
    observations: record?.observations ?? '',
  }
  for (const section of SECTIONS) {
    for (const [cle] of section.essais) etat[cle] = boolVersTexte(record?.[cle])
    for (const [cle] of section.mesures) etat[cle] = record?.[cle] ?? ''
  }
  return etat
}

function payloadDepuisEtat(etat) {
  const payload = {
    date_essai: etat.date_essai || null,
    technicien: etat.technicien || null,
    resultat: etat.resultat,
    observations: etat.observations || null,
  }
  for (const section of SECTIONS) {
    for (const [cle] of section.essais) payload[cle] = texteVersBool(etat[cle])
    for (const [cle] of section.mesures) payload[cle] = nombreOuNull(etat[cle])
  }
  return payload
}

function RecetteDialog({ installationId, record, onClose, onSaved }) {
  const [etat, setEtat] = useState(() => etatDepuisRecord(record))
  const [ficheId, setFicheId] = useState(record?.id ?? null)
  const [releves, setReleves] = useState(record?.iv_readings ?? [])
  const [iv, setIv] = useState(IV_VIDE)
  const [busy, setBusy] = useState(false)
  const [ivBusy, setIvBusy] = useState(false)
  const [erreur, setErreur] = useState(null)

  const champ = (cle) => (valeur) => setEtat((p) => ({ ...p, [cle]: valeur }))

  const enregistrer = async () => {
    setBusy(true)
    setErreur(null)
    try {
      let id = ficheId
      // La fiche n'est créée qu'ICI (première sauvegarde), jamais à
      // l'ouverture du formulaire.
      if (!id) {
        const cree = await installationsApi.ouvrirRecette(installationId)
        id = cree.data?.id
        setFicheId(id)
      }
      const r = await installationsApi.updateRecette(id, payloadDepuisEtat(etat))
      onSaved?.(r.data)
    } catch (err) {
      setErreur(err?.response?.data?.detail
        || "L'enregistrement de la fiche a échoué — vérifiez les valeurs saisies.")
    } finally {
      setBusy(false)
    }
  }

  const ajouterReleve = async () => {
    if (!ficheId) return
    setIvBusy(true)
    setErreur(null)
    try {
      const corps = {}
      for (const [cle, , type] of IV_CHAMPS) {
        const v = iv[cle]
        if (v === '' || v == null) continue
        corps[cle] = type === 'number' ? v : v
      }
      const r = await installationsApi.ajouterReleveIv(ficheId, corps)
      setReleves((p) => [...p, r.data])
      setIv(IV_VIDE)
    } catch (err) {
      setErreur(err?.response?.data?.detail || "Le relevé I-V n'a pas pu être ajouté.")
    } finally {
      setIvBusy(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-h-[92vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Fiche de recette (IEC 62446-1)</DialogTitle>
          <DialogDescription>
            Essais de mise en service. Une fiche « Conforme » ou « Conforme avec
            réserves » débloque le gate « Mise en service ». Un essai laissé
            vide reste « non renseigné » — il n’est jamais présumé conforme.
          </DialogDescription>
        </DialogHeader>

        {/* Les nombres tapés ne sont NI rognés NI rejetés : formulaire
            `noValidate`, chaque champ numérique en `step="any"`. */}
        <form noValidate className="flex flex-col gap-5" onSubmit={(e) => e.preventDefault()}>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="recette-date">Date d’essai</Label>
              <Input id="recette-date" type="date" value={etat.date_essai}
                     onChange={(e) => champ('date_essai')(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="recette-technicien">Technicien</Label>
              <Input id="recette-technicien" value={etat.technicien}
                     onChange={(e) => champ('technicien')(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="recette-resultat">Résultat</Label>
              <select id="recette-resultat" className="form-control"
                      value={etat.resultat}
                      onChange={(e) => champ('resultat')(e.target.value)}>
                {RESULTATS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
          </div>

          {SECTIONS.map((section) => (
            <section key={section.titre} className="flex flex-col gap-2">
              <h4 className="text-sm font-semibold">{section.titre}</h4>
              <div className="grid gap-3 sm:grid-cols-3">
                {section.essais.map(([cle, libelle]) => (
                  <div key={cle} className="flex flex-col gap-1.5">
                    <Label htmlFor={`recette-${cle}`}>{libelle}</Label>
                    <select id={`recette-${cle}`} className="form-control"
                            value={etat[cle]}
                            onChange={(e) => champ(cle)(e.target.value)}>
                      {TRI_ETAT.map((o) => (
                        <option key={o.value} value={o.value}>{o.label}</option>
                      ))}
                    </select>
                  </div>
                ))}
                {section.mesures.map(([cle, libelle]) => (
                  <div key={cle} className="flex flex-col gap-1.5">
                    <Label htmlFor={`recette-${cle}`}>{libelle}</Label>
                    <Input id={`recette-${cle}`} type="number" step="any"
                           value={etat[cle]}
                           onChange={(e) => champ(cle)(e.target.value)} />
                  </div>
                ))}
              </div>
            </section>
          ))}

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="recette-observations">Observations</Label>
            <Textarea id="recette-observations" rows={3} value={etat.observations}
                      onChange={(e) => champ('observations')(e.target.value)} />
          </div>

          {/* ── Relevés I-V par string (FG275) ── */}
          <section className="flex flex-col gap-2 rounded-lg border border-border p-3">
            <h4 className="text-sm font-semibold">Relevés I-V par string</h4>
            {releves.length > 0 && (
              <ul className="flex flex-col gap-1" data-testid="recette-releves">
                {releves.map((r) => (
                  <li key={r.id} className="flex flex-wrap items-center gap-2 text-sm">
                    <span className="font-mono">{r.string_label || '—'}</span>
                    <span className="text-muted-foreground">
                      Voc {r.voc_mesure_v ?? '—'} V · Isc {r.isc_mesure_a ?? '—'} A ·
                      Pmax {r.pmax_mesure_w ?? '—'} W
                    </span>
                    {r.ecart_pmax_pct != null && (
                      <Badge tone={r.defaut_detecte ? 'danger' : 'neutral'}>
                        écart {r.ecart_pmax_pct} %
                      </Badge>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {ficheId ? (
              <>
                <div className="grid gap-3 sm:grid-cols-4">
                  {IV_CHAMPS.map(([cle, libelle, type]) => (
                    <div key={cle} className="flex flex-col gap-1.5">
                      <Label htmlFor={`iv-${cle}`}>{libelle}</Label>
                      <Input
                        id={`iv-${cle}`}
                        type={type}
                        {...(type === 'number' ? { step: 'any' } : {})}
                        value={iv[cle]}
                        onChange={(e) => setIv((p) => ({ ...p, [cle]: e.target.value }))}
                      />
                    </div>
                  ))}
                </div>
                <div>
                  <Button type="button" size="sm" variant="outline"
                          loading={ivBusy} onClick={ajouterReleve}>
                    Ajouter le relevé I-V
                  </Button>
                </div>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                Enregistrez d’abord la fiche pour y ajouter des relevés I-V.
              </p>
            )}
          </section>

          {erreur && (
            <p className="form-error" role="alert">{erreur}</p>
          )}
        </form>

        <DialogFooter className="flex-wrap">
          <Button type="button" variant="ghost" onClick={onClose}>Fermer</Button>
          <Button type="button" loading={busy} onClick={enregistrer}>
            Enregistrer la fiche
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function StageIcon({ satisfait, courante, bloquant }) {
  if (satisfait && !courante) {
    return <CheckCircle2 className="size-5 text-success" aria-hidden="true" />
  }
  if (!satisfait && bloquant) {
    return <Lock className="size-5 text-destructive" aria-hidden="true" />
  }
  return (
    <Circle
      className={`size-5 ${courante ? 'text-info' : 'text-muted-foreground'}`}
      aria-hidden="true"
    />
  )
}

// Une étape — carte compacte avec son état de gate + raisons de blocage.
function StageRow({ etape, isLast }) {
  const { libelle, courante, satisfait, bloquant, raisons, statut_legacy: statutLegacy } = etape
  return (
    <li
      data-testid="ch6-stage"
      data-cle={etape.cle}
      data-courante={courante ? 'true' : 'false'}
      className={`relative flex gap-3 pb-4 ${isLast ? '' : 'border-l border-border ml-2.5 pl-4'}`}
    >
      <span className="absolute -left-[10.5px] top-0 flex size-5 items-center justify-center rounded-full bg-background">
        <StageIcon satisfait={satisfait} courante={courante} bloquant={bloquant} />
      </span>
      <div className="flex flex-1 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`text-sm font-semibold ${courante ? 'text-info' : 'text-foreground'}`}>
            {libelle}
          </span>
          {courante && <Badge tone="info">Étape en cours</Badge>}
          {bloquant && <Badge tone="outline">Gate bloquant</Badge>}
          {!bloquant && <Badge tone="neutral">Consultative</Badge>}
          {statutLegacy && (
            <span className="text-[11px] text-muted-foreground">({statutLegacy})</span>
          )}
        </div>
        {!satisfait && raisons?.length > 0 && (
          <ul className="flex flex-col gap-0.5 text-xs text-destructive">
            {raisons.map((r) => <li key={r}>• {r}</li>)}
          </ul>
        )}
      </div>
    </li>
  )
}

// APX26 — bande des jalons datés : rendue UNIQUEMENT quand l'appelant fournit
// le chantier (la fiche le fait). Les surfaces qui ne passent que
// `installationId` gardent le rendu d'origine, au pixel près.
function JalonsBand({ installation }) {
  if (!installation) return null
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border p-3" data-testid="ch6-jalons">
      <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Jalons datés
      </span>
      <ChantierTimeline installation={installation} />
    </div>
  )
}

export default function ChantierGateTimeline({ installationId, installation, onAdvanced }) {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState(null) // { etape_courante, etapes: [] }
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [blockedReasons, setBlockedReasons] = useState(null)

  // CH3 — recette de mise en service (IEC 62446-1).
  const [recette, setRecette] = useState(null)
  // WIR202 — le formulaire de saisie ; ouvert par le bouton, il ne crée
  // AUCUN enregistrement tant que rien n'est sauvegardé.
  const [recetteOuverte, setRecetteOuverte] = useState(false)

  // CH4 — pack de remise client.
  const [pack, setPack] = useState(null)
  const [packBusy, setPackBusy] = useState(false)

  const load = () => {
    setLoading(true)
    installationsApi.getEtapesChantier(installationId)
      .then((r) => { setData(r.data); setError(null) })
      .catch(() => setError('Étapes indisponibles.'))
      .finally(() => setLoading(false))
    installationsApi.getRecette(installationId)
      .then((r) => setRecette(r.data)).catch(() => {})
    installationsApi.getPackRemise(installationId)
      .then((r) => setPack(r.data)).catch(() => {})
  }

  // Charge trois ressources indépendantes (étapes/recette/pack) au montage +
  // après chaque avancement, comme le fait déjà `checkDevisDivergence` plus
  // haut sur cette même page (même repli d'effet).
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [installationId])

  const stages = data?.etapes ?? []
  const courante = stages.find((s) => s.courante)
  const idx = stages.findIndex((s) => s.courante)
  const suivante = idx >= 0 ? stages[idx + 1] : undefined

  const avancer = async (cle) => {
    setBusy(true)
    setBlockedReasons(null)
    try {
      await installationsApi.avancerEtape(installationId, cle)
      load()
      onAdvanced?.()
    } catch (err) {
      const raisons = err?.response?.data?.raisons
      if (Array.isArray(raisons) && raisons.length) {
        setBlockedReasons(raisons)
      } else {
        setBlockedReasons([
          err?.response?.data?.detail || 'Avancement impossible.',
        ])
      }
    } finally {
      setBusy(false)
    }
  }

  // WIR202 — `GET recette/` renvoie DEUX formes : `{installation, record:null}`
  // quand aucune fiche n'existe, et la fiche À PLAT quand elle existe. L'écran
  // ne lisait que `recette.record` : une fiche réelle restait donc affichée
  // « Aucune fiche », gate bloqué. On accepte les deux formes.
  const recetteRecord = recette
    ? (Object.prototype.hasOwnProperty.call(recette, 'record')
      ? recette.record
      : (recette.id ? recette : null))
    : null

  const genererPack = async () => {
    setPackBusy(true)
    try {
      const r = await installationsApi.genererPackRemise(installationId)
      setPack(r.data)
    } catch { /* 403 si non Responsable/Admin */ }
    finally { setPackBusy(false) }
  }

  if (loading) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner /> Chargement du parcours…
      </p>
    )
  }

  if (error) {
    return <p className="text-sm text-muted-foreground">{error}</p>
  }

  // Dégradation propre : société sans étapes configurées (comportement
  // historique) — aucun parcours à afficher, le statut reste le seul pilote.
  if (stages.length === 0) {
    return (
      <div className="flex flex-col gap-3">
        <p className="text-sm text-muted-foreground">
          Aucune étape de cycle de vie configurée pour cette société
          (Paramètres → Chantiers). Le statut classique reste utilisé.
        </p>
        {/* APX26 — même sans parcours configuré, les jalons datés restent
            visibles : la fusion ne supprime aucun contenu. */}
        <JalonsBand installation={installation} />
      </div>
    )
  }

  // APX26 — progression du parcours en tête : « Étape 2/3 » + barre. Le rang de
  // l'étape courante (1-indexé) ; sans étape courante, on compte les satisfaites.
  const rang = idx >= 0 ? idx + 1 : stages.filter((s) => s.satisfait).length
  const pct = Math.round((rang / stages.length) * 100)

  return (
    <div className="flex flex-col gap-4" data-testid="ch6-gate-timeline">
      {/* APX26 — la progression manquait ici alors que la checklist en avait
          une : le parcours ne disait pas « où on en est » d'un coup d'œil. */}
      <div className="flex items-center gap-3" data-testid="ch6-progress">
        <Progress
          value={pct}
          tone={rang === stages.length ? 'success' : 'primary'}
          className="flex-1"
          aria-label="Progression du parcours de chantier"
        />
        <span className="text-sm font-semibold tabular-nums text-muted-foreground">
          {rang}/{stages.length}
        </span>
      </div>
      {/* VX47 — aide contextuelle : la distinction bloquant/consultatif n'est
          pas évidente pour un nouvel employé (un cadenas rouge n'est pas
          auto-explicatif). Une seule pose pour toute la liste, pas de
          re-layout. */}
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <span>Gates de chantier</span>
        <HelpTip label="Aide — gates de chantier">
          Un <strong>gate bloquant</strong> (cadenas) empêche de passer à
          l'étape suivante tant qu'il n'est pas satisfait — les raisons du
          blocage s'affichent en rouge sous l'étape. Un gate
          <strong> consultatif</strong> est informatif : il n'empêche pas
          d'avancer, il signale seulement un point à vérifier.
        </HelpTip>
      </div>
      <ol className="flex flex-col" data-testid="ch6-stage-list">
        {stages.map((s, i) => (
          <StageRow key={s.cle} etape={s} isLast={i === stages.length - 1} />
        ))}
      </ol>

      {/* ── Prochaine action explicite (APX26 — `ui/NextActionBanner` partagé
          avec « Ma journée » ; `data-testid` d'origine conservé) ── */}
      {suivante ? (
        <NextActionBanner
          data-testid="ch6-next-action"
          action={(
            <Button
              size="sm"
              className="self-start"
              loading={busy}
              onClick={() => avancer(suivante.cle)}
              data-testid="ch6-avancer-btn"
            >
              Avancer vers « {suivante.libelle} »
            </Button>
          )}
        >
          faire avancer le chantier vers « {suivante.libelle} ».
        </NextActionBanner>
      ) : (
        <div className="flex flex-col gap-2 rounded-lg border border-border p-3" data-testid="ch6-next-action">
          <p className="text-sm text-muted-foreground">
            {courante
              ? `Dernière étape déjà atteinte (${courante.libelle}).`
              : 'Aucune étape courante.'}
          </p>
        </div>
      )}
      {blockedReasons && (
        <div
          role="alert"
          className="flex flex-col gap-1 rounded-md border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive"
          data-testid="ch6-blocked-reasons"
        >
          <strong>Étape bloquée par un gate&nbsp;:</strong>
          <ul className="flex flex-col gap-0.5">
            {blockedReasons.map((r) => <li key={r}>• {r}</li>)}
          </ul>
        </div>
      )}

      {/* APX26 — les jalons datés (ex-section « Timeline ») vivent maintenant
          dans CE stepper : une seule timeline dans la fiche. */}
      <JalonsBand installation={installation} />

      {/* ── CH3 — recette de mise en service (IEC 62446-1), gate mis en avant ── */}
      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border p-3" data-testid="ch6-recette">
        <ClipboardCheck className="size-4 text-muted-foreground" aria-hidden="true" />
        <span className="text-sm font-semibold">Recette de mise en service (IEC 62446-1)</span>
        {recetteRecord ? (
          <Badge tone={recetteRecord.passe ? 'success' : 'outline'}>
            {recetteRecord.resultat_display ?? recetteRecord.resultat}
          </Badge>
        ) : (
          <Badge tone="neutral">Aucune fiche</Badge>
        )}
        {/* WIR202 — le bouton OUVRE le formulaire ; il ne crée plus une fiche
            vide que rien ne pouvait remplir. Une fiche existante se rouvre
            avec les mêmes essais pour correction. */}
        <Button
          size="sm"
          variant="outline"
          className="ml-auto"
          onClick={() => setRecetteOuverte(true)}
        >
          {recetteRecord ? 'Modifier la fiche de recette' : 'Ouvrir la fiche de recette'}
        </Button>
      </div>

      {recetteOuverte && (
        <RecetteDialog
          installationId={installationId}
          record={recetteRecord}
          onClose={() => setRecetteOuverte(false)}
          onSaved={(record) => {
            setRecette(record)
            // Le gate « Mise en service » dépend de cette fiche : on relit les
            // étapes pour que le déblocage soit visible immédiatement.
            load()
            onAdvanced?.()
          }}
        />
      )}

      {/* ── CH4 — pack de remise client, gate mis en avant ── */}
      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border p-3" data-testid="ch6-pack-remise">
        <PackageCheck className="size-4 text-muted-foreground" aria-hidden="true" />
        <span className="text-sm font-semibold">Pack de remise client</span>
        {pack?.complet ? (
          <Badge tone="success">Complet</Badge>
        ) : (
          <Badge tone="outline">
            {pack?.pieces
              ? `${pack.pieces.filter((p) => p.present).length}/${pack.pieces.length} pièce(s)`
              : 'À préparer'}
          </Badge>
        )}
        {!pack?.persiste && (
          <Button size="sm" variant="outline" className="ml-auto" loading={packBusy} onClick={genererPack}>
            Générer le pack de remise
          </Button>
        )}
      </div>
    </div>
  )
}
