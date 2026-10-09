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
import RecettePompageDialog from './RecettePompageDialog'
import { RECETTE_TRI_ETAT, RECETTE_RESULTATS } from '../../features/installations/statuses'

/* ── WIR202/CH3 — fiche de recette IEC 62446-1 : formulaire de SAISIE ───────
   Le bouton « Ouvrir la fiche de recette » créait un enregistrement VIDE
   (`resultat = en_cours`) que rien ne pouvait ensuite remplir : le gate
   « Mise en service » restait bloqué à jamais. Il ouvre désormais ce
   formulaire ; l'enregistrement n'est créé qu'à la PREMIÈRE sauvegarde.
   Aucun montant, aucun prix d'achat n'apparaît ici — essais uniquement. */

// Les essais sont des booléens NULLABLES (non renseigné ≠ non conforme).
const TRI_ETAT = RECETTE_TRI_ETAT

const RESULTATS = RECETTE_RESULTATS

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

// AGR613 — la fiche pompage n'a pas de `resultat_display` : libellé local.
const RESULTAT_LIBELLES = Object.fromEntries(RESULTATS.map((o) => [o.value, o.label]))

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

/* ── CIQ636 — sections C&I de la fiche (contrat `recette_ci.json`) ───────────
   Le serveur sert chaque valeur À PLAT (champ écrit) ET groupée (section du
   contrat) : on lit le champ plat, puis la section groupée. Les essais
   `limitation_injection` / `decouplage` ne concernent que le MT. */
const ETATS_ESSAI = [
  { value: 'sans_objet', label: 'Sans objet' },
  { value: 'a_faire', label: 'À faire' },
  { value: 'ok', label: 'Conforme' },
  { value: 'non_ok', label: 'Non conforme' },
]

const SOURCES_IRRADIANCE = [
  { value: '', label: 'Non renseignée' },
  { value: 'mesuree', label: 'Mesurée' },
  { value: 'estimee', label: 'Estimée' },
]

// [clé écrite, libellé, lecture de la valeur groupée]
const CI_NOMBRES = [
  ['irradiance_poa_wm2', 'Irradiance dans le plan des modules (W/m²)', (r) => r.irradiance?.irradiance_poa_wm2],
  ['temperature_module_c', 'Température des modules (°C)', (r) => r.irradiance?.temperature_module_c],
  ['irradiation_kwh_m2', 'Irradiation mesurée sur la fenêtre (kWh/m²)', (r) => r.irradiance?.irradiation_kwh_m2],
  ['energie_mesuree_kwh', 'Énergie mesurée (kWh)', (r) => r.energie?.energie_mesuree_kwh],
  ['terre_installation_ohm', 'Terre de l’installation (Ω)', (r) => r.terre_installation_ohm],
]

const CI_DATES_HEURE = [
  ['energie_fenetre_debut', 'Début de la fenêtre d’énergie', (r) => r.energie?.fenetre_debut],
  ['energie_fenetre_fin', 'Fin de la fenêtre d’énergie', (r) => r.energie?.fenetre_fin],
]

// [section, libellé, champ état, champ texte, libellé du texte, sous-clé du texte]
const CI_MT_ESSAIS = [
  ['limitation_injection', 'Limitation d’injection', 'limitation_injection_etat', 'limitation_injection_consigne', 'Consigne', 'consigne'],
  ['decouplage', 'Découplage', 'decouplage_etat', 'decouplage_piece', 'Pièce (réglages imposés)', 'piece'],
]

// `datetime-local` n'affiche que « AAAA-MM-JJTHH:MM » : la valeur d'origine
// du serveur est conservée telle quelle tant que le champ n'est pas modifié
// (un enregistrement sans retouche renvoie exactement le même PATCH).
const heureLocale = (v) => (v ? String(v).slice(0, 16) : '')

const lire = (record, cle, groupee) => {
  const plat = record?.[cle]
  if (plat !== undefined && plat !== null) return plat
  const g = record ? groupee?.(record) : undefined
  return g ?? null
}

function etatDepuisRecord(record) {
  const etat = {
    date_essai: record?.date_essai ?? record?.date_recette ?? '',
    technicien: record?.technicien ?? '',
    observations: record?.observations ?? '',
    reserves_choisi: record?.resultat === 'reserves',
    irradiance_source: lire(record, 'irradiance_source', (r) => r.irradiance?.source) ?? '',
    thermographie_faite: boolVersTexte(
      lire(record, 'thermographie_faite', (r) => r.thermographie?.faite)),
    thermographie_constats: lire(
      record, 'thermographie_constats', (r) => r.thermographie?.constats) ?? '',
  }
  for (const section of SECTIONS) {
    for (const [cle] of section.essais) etat[cle] = boolVersTexte(record?.[cle])
    for (const [cle] of section.mesures) etat[cle] = record?.[cle] ?? ''
  }
  for (const [cle, , groupee] of CI_NOMBRES) etat[cle] = lire(record, cle, groupee) ?? ''
  for (const [cle, , groupee] of CI_DATES_HEURE) {
    etat[cle] = heureLocale(lire(record, cle, groupee))
  }
  for (const [section, , cleEtat, cleTexte, , sousCle] of CI_MT_ESSAIS) {
    etat[cleEtat] = record?.[cleEtat] ?? record?.[section]?.etat ?? 'sans_objet'
    etat[cleTexte] = record?.[cleTexte] ?? record?.[section]?.[sousCle] ?? ''
  }
  return etat
}

function payloadDepuisEtat(etat, record, { industriel, mt }) {
  const payload = {
    date_essai: etat.date_essai || null,
    technicien: etat.technicien || null,
    observations: etat.observations || null,
  }
  // Résultat calculé côté serveur : seule la valeur « reserves » part du client.
  if (etat.reserves_choisi) payload.resultat = 'reserves'
  for (const section of SECTIONS) {
    for (const [cle] of section.essais) payload[cle] = texteVersBool(etat[cle])
    for (const [cle] of section.mesures) payload[cle] = nombreOuNull(etat[cle])
  }
  if (industriel) {
    payload.irradiance_source = etat.irradiance_source || null
    payload.thermographie_faite = texteVersBool(etat.thermographie_faite)
    payload.thermographie_constats = etat.thermographie_constats || null
    for (const [cle] of CI_NOMBRES) payload[cle] = nombreOuNull(etat[cle])
    for (const [cle, , groupee] of CI_DATES_HEURE) {
      const origine = lire(record, cle, groupee)
      payload[cle] = etat[cle] === heureLocale(origine)
        ? (origine ?? null) : (etat[cle] || null)
    }
    if (mt) {
      for (const [, , cleEtat, cleTexte] of CI_MT_ESSAIS) {
        payload[cleEtat] = etat[cleEtat]
        payload[cleTexte] = etat[cleTexte] || null
      }
    }
  }
  return payload
}

const tousEssaisVrais = (etat) => SECTIONS.every(
  (s) => s.essais.every(([cle]) => etat[cle] === 'true'))

const reserveRecetteOuverte = (reserves) => reserves.some(
  (r) => r.statut === 'ouverte' && r.origine === 'recette')

// Les erreurs 400 DRF `{champ: [msg]}` se rangent sous le champ fautif.
function erreursParChamp(data) {
  if (!data || typeof data !== 'object' || data.detail) return null
  const out = {}
  for (const [k, v] of Object.entries(data)) {
    out[k] = Array.isArray(v) ? v.join(' ') : String(v)
  }
  return out
}

function ComparaisonRecette({ comparaison, energie }) {
  if (!comparaison && !energie) return null
  const promesse = comparaison?.promesse_figee
  const ecart = comparaison?.ecart_iv_pmax_pct
  const seuil = comparaison?.seuil_ecart_pmax_pct
  const pr = energie?.pr_mesure
  return (
    <section className="flex flex-col gap-1 rounded-lg border border-border p-3 text-sm"
             data-testid="recette-comparaison">
      <h4 className="m-0 text-sm font-semibold">Comparaison au devis</h4>
      {promesse ? (
        <span>
          Promesse figée au devis : {promesse.production_annuelle_kwh} kWh/an
          {promesse.pr_modelise != null && `, PR modélisé ${promesse.pr_modelise}`}
          {promesse.source && ` (${promesse.source})`}
        </span>
      ) : (
        <span className="text-muted-foreground">Aucune promesse figée sur ce devis.</span>
      )}
      <span>
        PR mesuré : {pr != null ? pr : '—'}{' '}
        <span className="text-muted-foreground">
          {energie?.libelle || 'à titre d’information'}
        </span>
      </span>
      <span>
        Écart I-V (Pmax) : {ecart != null ? `${ecart} %` : '—'}
        {ecart != null && seuil == null && (
          <span className="text-muted-foreground"> — seuil non saisi en Paramètres</span>
        )}
        {ecart != null && seuil != null && comparaison?.defaut_detecte != null && (
          <Badge tone={comparaison.defaut_detecte ? 'danger' : 'neutral'} className="ml-2">
            {comparaison.defaut_detecte ? 'Défaut détecté' : 'Dans le seuil'}
          </Badge>
        )}
      </span>
    </section>
  )
}

function ReservesPanel({ installationId, reserves, ficheOuverte, onChange }) {
  const [desc, setDesc] = useState('')
  const [bloquante, setBloquante] = useState(false)
  const [echeance, setEcheance] = useState('')
  const [responsable, setResponsable] = useState('')
  const [busy, setBusy] = useState(false)
  const [erreur, setErreur] = useState(null)

  const recharger = async () => {
    const r = await installationsApi.getReservesChantier(installationId)
    onChange(Array.isArray(r.data) ? r.data : [])
  }

  const ajouter = async () => {
    setBusy(true)
    setErreur(null)
    try {
      await installationsApi.ajouterReserveChantier(installationId, {
        description: desc,
        origine: 'recette',
        bloquante,
        date_echeance: echeance || null,
        responsable: responsable || '',
      })
      setDesc(''); setBloquante(false); setEcheance(''); setResponsable('')
      await recharger()
    } catch (err) {
      const d = err?.response?.data
      setErreur(d?.description || d?.date_echeance || d?.detail
        || "La réserve n'a pas pu être ajoutée.")
    } finally {
      setBusy(false)
    }
  }

  const lever = async (id) => {
    setBusy(true)
    setErreur(null)
    try {
      await installationsApi.leverReserveChantier(installationId, id)
      await recharger()
    } catch (err) {
      setErreur(err?.response?.data?.detail || "La réserve n'a pas pu être levée.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="flex flex-col gap-2 rounded-lg border border-border p-3"
             data-testid="recette-reserves">
      <h4 className="m-0 text-sm font-semibold">Réserves</h4>
      {reserves.length === 0 && (
        <p className="m-0 text-sm text-muted-foreground">Aucune réserve.</p>
      )}
      {reserves.length > 0 && (
        <ul className="m-0 flex list-none flex-col gap-1 p-0">
          {reserves.map((r) => (
            <li key={r.id} data-statut={r.statut}
                className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
              <span className="font-medium">{r.description}</span>
              {r.bloquante && <Badge tone="danger">Bloquante</Badge>}
              <Badge tone={r.statut === 'ouverte' ? 'warning' : 'success'}>
                {r.statut === 'ouverte' ? 'Ouverte' : 'Levée'}
              </Badge>
              {r.date_echeance && (
                <span className="text-muted-foreground">échéance {r.date_echeance}</span>
              )}
              {r.responsable && (
                <span className="text-muted-foreground">responsable {r.responsable}</span>
              )}
              {r.statut === 'ouverte' && (
                <Button type="button" size="sm" variant="outline" disabled={busy}
                        aria-label={`Lever la réserve ${r.description}`}
                        onClick={() => lever(r.id)}>
                  Lever
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {ficheOuverte ? (
        <div className="grid gap-3 sm:grid-cols-4">
          <div className="flex flex-col gap-1.5 sm:col-span-2">
            <Label htmlFor="reserve-description">Réserve à ajouter</Label>
            <Input id="reserve-description" value={desc}
                   onChange={(e) => setDesc(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="reserve-echeance">Échéance</Label>
            <Input id="reserve-echeance" type="date" value={echeance}
                   onChange={(e) => setEcheance(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="reserve-responsable">Responsable</Label>
            <Input id="reserve-responsable" value={responsable}
                   onChange={(e) => setResponsable(e.target.value)} />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={bloquante}
                   onChange={(e) => setBloquante(e.target.checked)} />
            Bloquante
          </label>
          <div>
            <Button type="button" size="sm" variant="outline" loading={busy}
                    onClick={ajouter}>
              Ajouter la réserve
            </Button>
          </div>
        </div>
      ) : (
        <p className="m-0 text-sm text-muted-foreground">
          Enregistrez d’abord la fiche pour y ajouter des réserves.
        </p>
      )}
      {erreur && <p className="form-error" role="alert">{String(erreur)}</p>}
    </section>
  )
}

function RecetteDialog({
  installationId, record, installation, comparaison, reserves: reservesInit,
  onClose, onSaved,
}) {
  const industriel = installation?.type_installation === 'industriel'
  const mt = industriel && installation?.niveau_tension === 'mt'
  const [etat, setEtat] = useState(() => etatDepuisRecord(record))
  const [ficheId, setFicheId] = useState(record?.id ?? null)
  const [releves, setReleves] = useState(record?.iv_readings ?? [])
  const [reserves, setReserves] = useState(reservesInit ?? record?.reserves ?? [])
  const [iv, setIv] = useState(IV_VIDE)
  const [busy, setBusy] = useState(false)
  const [ivBusy, setIvBusy] = useState(false)
  const [erreur, setErreur] = useState(null)
  const [erreurs, setErreurs] = useState({})
  // Le résultat est AFFICHÉ (calculé par le serveur), jamais saisi.
  const [resultat, setResultat] = useState(record?.resultat ?? 'en_cours')
  const resultatLibelle = RESULTAT_LIBELLES[resultat] ?? resultat
  const energie = record?.energie

  const champ = (cle) => (valeur) => setEtat((p) => ({ ...p, [cle]: valeur }))
  const erreurSous = (cle) => (erreurs[cle]
    ? <p className="form-error" role="alert">{erreurs[cle]}</p> : null)

  const reservesPossible = tousEssaisVrais(etat) && reserveRecetteOuverte(reserves)

  const enregistrer = async () => {
    setBusy(true)
    setErreur(null)
    setErreurs({})
    try {
      let id = ficheId
      // La fiche n'est créée qu'ICI (première sauvegarde), jamais à
      // l'ouverture du formulaire.
      if (!id) {
        const cree = await installationsApi.ouvrirRecette(installationId)
        id = cree.data?.id
        setFicheId(id)
      }
      const r = await installationsApi.updateRecette(
        id, payloadDepuisEtat(etat, record, { industriel, mt }))
      if (r.data?.resultat) setResultat(r.data.resultat)
      onSaved?.(r.data)
    } catch (err) {
      const parChamp = erreursParChamp(err?.response?.data)
      if (parChamp) {
        setErreurs(parChamp)
      } else {
        setErreur(err?.response?.data?.detail
          || "L'enregistrement de la fiche a échoué — vérifiez les valeurs saisies.")
      }
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
            Essais de mise en service. Le résultat est calculé par le serveur à
            partir des essais : « Conforme » ou « Conforme avec réserves »
            débloque le gate « Mise en service ». Un essai laissé vide reste
            « non renseigné » — il n’est jamais présumé conforme.
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
              {erreurSous('date_essai')}
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="recette-technicien">Technicien</Label>
              <Input id="recette-technicien" value={etat.technicien}
                     onChange={(e) => champ('technicien')(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-medium">Résultat (calculé)</span>
              <span data-testid="recette-resultat" className="text-sm">
                <Badge tone={['conforme', 'reserves'].includes(resultat) ? 'success'
                  : resultat === 'non_conforme' ? 'danger' : 'outline'}>
                  {resultatLibelle}
                </Badge>
              </span>
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
                    {erreurSous(cle)}
                  </div>
                ))}
                {section.mesures.map(([cle, libelle]) => (
                  <div key={cle} className="flex flex-col gap-1.5">
                    <Label htmlFor={`recette-${cle}`}>{libelle}</Label>
                    <Input id={`recette-${cle}`} type="number" step="any"
                           value={etat[cle]}
                           onChange={(e) => champ(cle)(e.target.value)} />
                    {erreurSous(cle)}
                  </div>
                ))}
              </div>
            </section>
          ))}

          {industriel && (
            <>
              <section className="flex flex-col gap-2" data-testid="recette-ci">
                <h4 className="text-sm font-semibold">Irradiance, énergie et terre</h4>
                <div className="grid gap-3 sm:grid-cols-3">
                  {CI_NOMBRES.map(([cle, libelle]) => (
                    <div key={cle} className="flex flex-col gap-1.5">
                      <Label htmlFor={`recette-${cle}`}>{libelle}</Label>
                      <Input id={`recette-${cle}`} type="number" step="any"
                             value={etat[cle]}
                             onChange={(e) => champ(cle)(e.target.value)} />
                      {erreurSous(cle)}
                    </div>
                  ))}
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="recette-irradiance_source">Source de l’irradiance</Label>
                    <select id="recette-irradiance_source" className="form-control"
                            value={etat.irradiance_source}
                            onChange={(e) => champ('irradiance_source')(e.target.value)}>
                      {SOURCES_IRRADIANCE.map((o) => (
                        <option key={o.value} value={o.value}>{o.label}</option>
                      ))}
                    </select>
                  </div>
                  {CI_DATES_HEURE.map(([cle, libelle]) => (
                    <div key={cle} className="flex flex-col gap-1.5">
                      <Label htmlFor={`recette-${cle}`}>{libelle}</Label>
                      <Input id={`recette-${cle}`} type="datetime-local" value={etat[cle]}
                             onChange={(e) => champ(cle)(e.target.value)} />
                      {erreurSous(cle)}
                    </div>
                  ))}
                </div>
              </section>

              <section className="flex flex-col gap-2">
                <h4 className="text-sm font-semibold">Thermographie</h4>
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="recette-thermographie_faite">Thermographie réalisée</Label>
                    <select id="recette-thermographie_faite" className="form-control"
                            value={etat.thermographie_faite}
                            onChange={(e) => champ('thermographie_faite')(e.target.value)}>
                      {TRI_ETAT.map((o) => (
                        <option key={o.value} value={o.value}>{o.label}</option>
                      ))}
                    </select>
                  </div>
                  <div className="flex flex-col gap-1.5 sm:col-span-2">
                    <Label htmlFor="recette-thermographie_constats">Constats</Label>
                    <Textarea id="recette-thermographie_constats" rows={2}
                              value={etat.thermographie_constats}
                              onChange={(e) => champ('thermographie_constats')(e.target.value)} />
                  </div>
                </div>
              </section>

              {mt && (
                <section className="flex flex-col gap-2" data-testid="recette-mt">
                  <h4 className="text-sm font-semibold">Limitation d’injection et découplage (MT)</h4>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {CI_MT_ESSAIS.map(([cle, libelle, cleEtat, cleTexte, libelleTexte]) => (
                      <div key={cle} className="flex flex-col gap-1.5">
                        <Label htmlFor={`recette-${cleEtat}`}>{libelle}</Label>
                        <select id={`recette-${cleEtat}`} className="form-control"
                                value={etat[cleEtat]}
                                onChange={(e) => champ(cleEtat)(e.target.value)}>
                          {ETATS_ESSAI.map((o) => (
                            <option key={o.value} value={o.value}>{o.label}</option>
                          ))}
                        </select>
                        <Label htmlFor={`recette-${cleTexte}`}>{libelleTexte}</Label>
                        <Input id={`recette-${cleTexte}`} value={etat[cleTexte]}
                               onChange={(e) => champ(cleTexte)(e.target.value)} />
                      </div>
                    ))}
                  </div>
                </section>
              )}

              <ComparaisonRecette comparaison={comparaison ?? record?.comparaison}
                                  energie={energie} />
            </>
          )}

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="recette-observations">Observations</Label>
            <Textarea id="recette-observations" rows={3} value={etat.observations}
                      onChange={(e) => champ('observations')(e.target.value)} />
          </div>

          {/* Le seul choix humain : « conforme avec réserves », quand TOUS les
              essais sont conformes ET qu'une réserve de recette est ouverte. */}
          <div className="flex flex-col gap-1">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={etat.reserves_choisi}
                     disabled={!reservesPossible && !etat.reserves_choisi}
                     onChange={(e) => champ('reserves_choisi')(e.target.checked)} />
              Conforme avec réserves
            </label>
            {!reservesPossible && (
              <p className="m-0 text-xs text-muted-foreground">
                Possible quand tous les essais sont conformes et qu’une réserve
                de recette est ouverte (panneau Réserves ci-dessous).
              </p>
            )}
            {erreurSous('resultat')}
          </div>

          <ReservesPanel installationId={installationId} reserves={reserves}
                         ficheOuverte={Boolean(ficheId)} onChange={setReserves} />

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
  const {
    libelle, courante, satisfait, bloquant, raisons, statut_legacy: statutLegacy,
    avertissements, sans_objet: sansObjet,
  } = etape
  return (
    <li
      data-testid="ch6-stage"
      data-cle={etape.cle}
      data-courante={courante ? 'true' : 'false'}
      data-sans-objet={sansObjet ? 'true' : 'false'}
      className={`relative flex gap-3 pb-4 ${isLast ? '' : 'border-l border-border ml-2.5 pl-4'} ${sansObjet ? 'opacity-60' : ''}`}
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
          {sansObjet && <Badge tone="neutral">Sans objet (hors réseau)</Badge>}
          {!sansObjet && bloquant && <Badge tone="outline">Gate bloquant</Badge>}
          {!sansObjet && !bloquant && <Badge tone="neutral">Consultative</Badge>}
          {statutLegacy && (
            <span className="text-[11px] text-muted-foreground">({statutLegacy})</span>
          )}
        </div>
        {/* AGR604 — avertissements CONSULTATIFS : style info, jamais un blocage
            (le serveur ne les compte pas dans `raisons`). */}
        {avertissements?.length > 0 && (
          <ul className="flex flex-col gap-0.5 text-xs text-info" data-testid="ch6-avertissements">
            {avertissements.map((a) => <li key={a}>ℹ {a}</li>)}
          </ul>
        )}
        {!sansObjet && !satisfait && raisons?.length > 0 && (
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
  // ACHT60 — dérogation « acompte non reçu » : étape refusée à rejouer + motif.
  const [derniereCle, setDerniereCle] = useState(undefined)
  const [motifAcompte, setMotifAcompte] = useState('')

  // CH3 — recette de mise en service (IEC 62446-1).
  const [recette, setRecette] = useState(null)
  // WIR202 — le formulaire de saisie ; ouvert par le bouton, il ne crée
  // AUCUN enregistrement tant que rien n'est sauvegardé.
  const [recetteOuverte, setRecetteOuverte] = useState(false)

  // CH4 — pack de remise client.
  const [pack, setPack] = useState(null)
  const [packBusy, setPackBusy] = useState(false)

  // AGR613 — chantier agricole : recette POMPAGE (IEC 62253) à la place de la
  // fiche IEC 62446-1 du PV raccordé.
  const agricole = installation?.type_installation === 'agricole'

  const load = () => {
    setLoading(true)
    installationsApi.getEtapesChantier(installationId)
      .then((r) => { setData(r.data); setError(null) })
      .catch(() => setError('Étapes indisponibles.'))
      .finally(() => setLoading(false))
    ;(agricole ? installationsApi.getRecettePompage : installationsApi.getRecette)(installationId)
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

  const avancer = async (cle, motif) => {
    setBusy(true)
    setBlockedReasons(null)
    setDerniereCle(cle)
    try {
      await (motif
        ? installationsApi.avancerEtape(installationId, cle, motif)
        : installationsApi.avancerEtape(installationId, cle))
      setMotifAcompte('')
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

  const libelleRecette = agricole
    ? 'Recette de pompage (IEC 62253)'
    : 'Recette de mise en service (IEC 62446-1)'

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

  // CAD177 — la recette (CH3 / AGR613) et le pack de remise (CH4) sont des
  // documents du chantier, pas des étapes du parcours : ils restent
  // accessibles même quand la société n'a pas amorcé son cycle (AUD313 — la
  // lecture n'amorce plus rien). Sans cela, aucune fiche de recette ne
  // pouvait être saisie à l'écran tant que le Directeur n'avait pas amorcé.
  const recetteEtPack = (
    <>
      {/* ── CH3 — recette de mise en service (IEC 62446-1), gate mis en avant ── */}
      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border p-3" data-testid="ch6-recette">
        <ClipboardCheck className="size-4 text-muted-foreground" aria-hidden="true" />
        <span className="text-sm font-semibold">{libelleRecette}</span>
        {recetteRecord ? (
          <Badge tone={(recetteRecord.passe
            ?? ['conforme', 'reserves'].includes(recetteRecord.resultat))
            ? 'success' : 'outline'}>
            {recetteRecord.resultat_display
              ?? RESULTAT_LIBELLES[recetteRecord.resultat]
              ?? recetteRecord.resultat}
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

      {recetteOuverte && agricole && (
        <RecettePompageDialog
          installationId={installationId}
          record={recetteRecord}
          onClose={() => setRecetteOuverte(false)}
          onSaved={(enveloppe) => {
            setRecette(enveloppe)
            load()
            onAdvanced?.()
          }}
        />
      )}
      {recetteOuverte && !agricole && (
        <RecetteDialog
          installationId={installationId}
          installation={installation}
          record={recetteRecord}
          comparaison={recette?.comparaison}
          reserves={recette?.reserves}
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
    </>
  )

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
        {recetteEtPack}
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
          {blockedReasons.some((r) => /acompte/i.test(r)) && (
            <div className="mt-1 flex flex-col gap-1 text-foreground">
              <label htmlFor="ch6-motif-acompte">Motif (acompte non reçu)</label>
              <input id="ch6-motif-acompte" value={motifAcompte}
                     className="rounded-md border border-input bg-background px-2 py-1"
                     onChange={(e) => setMotifAcompte(e.target.value)} />
              <Button size="sm" variant="outline" disabled={busy || !motifAcompte.trim()}
                      onClick={() => avancer(derniereCle, motifAcompte.trim())}>
                Réessayer avec ce motif
              </Button>
            </div>
          )}
        </div>
      )}

      {/* APX26 — les jalons datés (ex-section « Timeline ») vivent maintenant
          dans CE stepper : une seule timeline dans la fiche. */}
      <JalonsBand installation={installation} />

      {recetteEtPack}
    </div>
  )
}
