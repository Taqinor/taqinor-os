// QJR101 — PANNEAU DE MARCHÉ : AGRICOLE (POMPAGE).
// ---------------------------------------------------------------------------
// Quatre panneaux sortent de `DevisGenerator.jsx` : chacun ne monte que les
// champs de SON marché. L'agricole ne montre AUCUNE facture électrique :
// il porte la pompe (CV, type, alimentation, HMT, débit, heures) et les
// données guidées de l'exploitation. Ni onduleur ni batterie n'existent ici.
//
// QJR241 — le panneau se retire lui-même hors de son marché via `CLE`
// (constante locale ; l'ex-module de stratégie `quote/marches/agricole.js`,
// devenu du code mort — aucun autre export que `cle` n'avait de consommateur
// de production — a été supprimé) — le même patron que `DevisOffresTailles`.
// `modeInstallation` ne vaut jamais qu'une des quatre clés (le reducer refuse
// toute autre valeur, `modeDepuisTypeInstallation`), donc exactement un
// panneau rend, à la place exacte qu'occupait la carte d'origine.
//
// AGR128 — les blocs suivent l'ordre des outils de référence : cas de pompe
// → besoin → point d'eau → hauteur (HMT) → équipement. Tous les champs
// démarrent VIDES (aucun défaut enregistré comme une saisie) ; la HMT
// calculée par le SERVEUR est affichée et surchargeable, la surcharge restant
// visible. Aucun calcul ici : l'aperçu vient de `useEtudePompagePreview`.
//
// AUCUNE LOGIQUE ICI : l'état et les gestes arrivent en props, tout le calcul
// reste dans l'écran porteur. Le balisage sort à l'octet — mêmes `id`, mêmes
// `placeholder`, mêmes classes, même ordre DOM. Chaque `<input type="number">`
// garde `step="any"` (règle fondateur : aucun champ ne snappe jamais) et le
// `noValidate` est resté sur le formulaire porteur.
import {
  Card, CardContent, Input, Label, Segmented,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../../ui'
import { Sprout } from 'lucide-react'
import { GenCardHeader } from './CarteMetrique'
import { formatNumber } from '../../../lib/format'
import { alertesAffichables } from '../../../features/ventes/etudePompagePreviewPur'
import CarteEconomiePompage from './CarteEconomiePompage'

const fmtNum = (v) => (v !== null && v !== undefined) ? formatNumber(v) : 'N/A'

// AGR128 — un champ nombre des blocs nouveaux : `step="any"` (aucun champ ne
// snappe jamais), valeur tapée transmise telle quelle (jamais arrondie).
function ChampNombre({ id, label, valeur, onChange, placeholder }) {
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} type="number" min="0" step="any"
             placeholder={placeholder} value={valeur ?? ''}
             onChange={e => onChange(e.target.value)} />
    </div>
  )
}

function ChampTexte({ id, label, valeur, onChange, type = 'text' }) {
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} type={type} value={valeur ?? ''}
             onChange={e => onChange(e.target.value)} />
    </div>
  )
}

function ChoixNatif({ id, label, valeur, onChange, options }) {
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <select id={id} value={valeur ?? ''}
              onChange={e => onChange(e.target.value)}
              className="h-9 rounded-md border border-input bg-card px-2 text-sm">
        <option value="">Non renseigné</option>
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </div>
  )
}

// AGR129 — pastille de couverture du mois : bornes = tolérance de conception
// -5 / +20 % (AGR110, source secondaire — contrôle de conception seulement).
function pastilleCouverture(pct) {
  if (pct === null || pct === undefined) return null
  if (pct < 95) return 'rouge'
  if (pct > 120) return 'orange'
  return 'vert'
}

const CLASSES_PASTILLE = {
  vert: 'bg-success/15 text-success',
  orange: 'bg-warning/15 text-warning',
  rouge: 'bg-destructive/15 text-destructive',
}

const LIBELLES_TAILLE = {
  recommandee: 'Recommandée', inferieure: 'Inférieure', superieure: 'Supérieure',
}
const LIBELLES_NON_INCLUS = { forage: 'forage', genie_civil: 'génie civil' }

// AGR129 — le RÉSULTAT SERVEUR en direct (aucune valeur calculée ici : tout
// vient de la réponse de l'aperçu AGR127).
function ResultatPompage({ donnees, saisie, majPompage }) {
  if (!donnees) return null
  const d = donnees
  const options = d.kit?.options || []
  const cochees = new Set(saisie?.options_cochees || [])
  const basculer = (cle) => {
    const suivant = new Set(cochees)
    if (suivant.has(cle)) suivant.delete(cle); else suivant.add(cle)
    majPompage?.('options_cochees', [...suivant])
  }
  const tailleChoisie = saisie?.taille || 'recommandee'
  const alertes = alertesAffichables(d)
  const prod = d.production?.m3_jour_mois || null
  const besoin = d.besoin?.m3_jour_mois || null
  const couv = d.couverture_pct_mois || null
  const moisCritique = d.conception?.mois_critique ?? null
  return (
    <div className="mt-4 grid gap-3" data-testid="resultat-pompage">
      <div className="rounded-lg border border-info/30 bg-info/10 p-3 text-sm">
        <div data-testid="resultat-pompe">
          <strong>Pompe proposée :</strong> {d.pompe?.nom || 'aucune'}
          {d.puissance_retenue?.kw != null && (
            <> · puissance retenue {fmtNum(d.puissance_retenue.kw)} kW
              {d.puissance_retenue.cv != null && <> ({fmtNum(d.puissance_retenue.cv)} CV)</>}</>
          )}
        </div>
        <div><strong>Variateur :</strong> {d.variateur?.nom || d.variateur?.motif || 'aucun'}</div>
        {d.champ && (
          <div data-testid="resultat-chaines">
            Champ {fmtNum(d.champ.kwc)} kWc ({fmtNum(d.champ.nb_panneaux)} panneaux) —
            chaînes {d.champ.chaines?.verifiable
              ? 'vérifiées'
              : `non vérifiables${d.champ.chaines?.motif ? ` : ${d.champ.chaines.motif}` : ''}`}
          </div>
        )}
      </div>

      {couv && (
        <table className="w-full text-xs" data-testid="resultat-mois">
          <thead>
            <tr><th className="text-left">Mois</th><th>Production (m³/j)</th>
              <th>Besoin (m³/j)</th><th>Couverture</th></tr>
          </thead>
          <tbody>
            {couv.map((pct, i) => {
              const pastille = pastilleCouverture(pct)
              return (
                <tr key={i} data-testid={`mois-${i + 1}`}
                    className={moisCritique === i + 1 ? 'font-semibold' : ''}>
                  <td>{MOIS[i][1]}{moisCritique === i + 1 ? ' (mois critique)' : ''}</td>
                  <td className="text-center">{prod ? fmtNum(prod[i]) : '—'}</td>
                  <td className="text-center">{besoin ? fmtNum(besoin[i]) : '—'}</td>
                  <td className="text-center">
                    {pct == null ? '—' : (
                      <span className={`rounded px-1.5 py-0.5 ${CLASSES_PASTILLE[pastille]}`}
                            data-pastille={pastille}>{pct} %</span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}

      <div className="grid gap-1 text-sm">
        <div data-testid="resultat-ha">
          Hectares irrigables : {d.ha_irrigables?.valeur != null
            ? <>{fmtNum(d.ha_irrigables.valeur)} ha{d.besoin?.source_et0 === 'EST.' ? ' (estimation)' : ''}</>
            : (d.ha_irrigables?.motif || '—')}
        </div>
        <div data-testid="resultat-autonomie">
          Autonomie du réservoir : {d.autonomie_reservoir_jours?.valeur != null
            ? <>{fmtNum(d.autonomie_reservoir_jours.valeur)} jours</>
            : (d.autonomie_reservoir_jours?.motif || '—')}
        </div>
      </div>

      {(d.tailles || []).length > 0 && (
        <div className="grid gap-2 sm:grid-cols-3" data-testid="resultat-tailles">
          {d.tailles.map((t) => (
            <button type="button" key={t.cle}
                    data-testid={`taille-${t.cle}`}
                    aria-pressed={tailleChoisie === t.cle}
                    onClick={() => majPompage?.('taille', t.cle)}
                    className={`rounded-lg border p-2 text-left text-xs ${
                      tailleChoisie === t.cle ? 'border-primary bg-primary/10' : 'border-border'}`}>
              <div className="font-semibold">{LIBELLES_TAILLE[t.cle] || t.cle}</div>
              <div>{t.pompe_nom}</div>
              <div>{fmtNum(t.champ_kwc)} kWc · {fmtNum(t.nb_panneaux)} panneaux</div>
              {t.couverture_mois_critique_pct != null && (
                <div>Couverture au mois critique : {t.couverture_mois_critique_pct} %</div>
              )}
              {!t.prix_connu && <div className="text-warning">prix à renseigner</div>}
            </button>
          ))}
          {(d.tailles_omises || []).map((t) => (
            <div key={t.cle} className="rounded-lg border border-dashed p-2 text-xs text-muted-foreground">
              {LIBELLES_TAILLE[t.cle] || t.cle} : {t.motif}
            </div>
          ))}
        </div>
      )}

      {options.length > 0 && (
        <div className="grid gap-1 text-sm" data-testid="resultat-options">
          <span className="font-semibold">Options du kit</span>
          {options.map((o) => (
            <label key={o.cle}
                   className={`flex items-center gap-2 ${o.prix_connu ? '' : 'text-muted-foreground'}`}>
              <input type="checkbox" data-testid={`option-${o.cle}`}
                     checked={cochees.has(o.cle)}
                     onChange={() => basculer(o.cle)} />
              {o.libelle}{!o.prix_connu && ` — ${o.motif || 'prix à renseigner'}`}
            </label>
          ))}
        </div>
      )}
      {(d.kit?.non_inclus || []).length > 0 && (
        <p className="text-xs text-muted-foreground" data-testid="resultat-non-inclus">
          Non inclus : {d.kit.non_inclus.map((c) => LIBELLES_NON_INCLUS[c] || c).join(', ')}
        </p>
      )}

      {(d.hypotheses || []).length > 0 && (
        <details className="text-xs" data-testid="resultat-hypotheses">
          <summary>Hypothèses ({d.hypotheses.length})</summary>
          <ul className="mt-1 grid gap-0.5">
            {d.hypotheses.map((h) => (
              <li key={h.cle}>
                {h.cle} = {String(h.valeur)} —{' '}
                {h.statut === 'estimation' ? 'EST.' : (h.source || 'EST.')}
              </li>
            ))}
          </ul>
        </details>
      )}

      {alertes.length > 0 && (
        <ul className="grid gap-1" data-testid="resultat-alertes">
          {alertes.map((a) => (
            <li key={a.cle} role="status" data-code={a.code}
                className="rounded-lg border border-warning/40 bg-warning/10 p-2 text-sm text-warning">
              {a.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// AGR212 — repère daté et SOURCÉ affiché À CÔTÉ du champ prix (AGR208) :
// une simple indication, jamais recopiée dans le champ (Q17).
const REPERE_PAR_ENERGIE = { butane: 'butane_12kg_detail', diesel: 'gasoil_litre' }

function EconomieDeclaree({ eco, majEco, reperes, moisCalendrier, coherenceAvertit }) {
  const e = eco || {}
  const maj = (cle) => (v) => majEco?.(cle, v)
  const carburant = e.energie === 'butane' || e.energie === 'diesel'
  const repere = (reperes || {})[REPERE_PAR_ENERGIE[e.energie]]
  const repereSource = repere && repere.valeur != null && String(repere.source || '').trim()
  const coches = new Set(Array.isArray(e.mois) ? e.mois : (moisCalendrier || []))
  const basculerMois = (m) => {
    const suivant = new Set(coches)
    if (suivant.has(m)) suivant.delete(m); else suivant.add(m)
    majEco?.('mois', [...suivant].sort((x, y) => x - y))
    majEco?.('moisProvenance', null)
  }
  const aujourdhui = new Date().toISOString().slice(0, 10)
  return (
    <div className="mt-4 grid gap-3 rounded-lg border p-3" data-testid="bloc-economie-declaree">
      <span className="font-display text-sm font-semibold">Énergie actuelle et dépense déclarée</span>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="grid gap-1.5">
          <Label htmlFor="gen-farm-fuel">Énergie actuelle</Label>
          <select id="gen-farm-fuel" value={e.energie || ''}
                  onChange={ev => majEco?.('energie', ev.target.value)}
                  className="h-9 rounded-md border border-input bg-card px-2 text-sm">
            <option value="">Non renseignée</option>
            <option value="aucune">Aucune (nouveau forage)</option>
            <option value="butane">Butane</option>
            <option value="diesel">Gasoil</option>
            <option value="electrique">Réseau électrique</option>
          </select>
        </div>
        <ChampTexte id="gen-eco-date" label="Date de déclaration" type="date"
                    valeur={e.dateDeclaration || aujourdhui} onChange={maj('dateDeclaration')} />
        <ChampNombre id="gen-eco-entretien" label="Entretien et réparations payés (MAD / an)"
                     valeur={e.entretien} onChange={maj('entretien')} />
      </div>
      {carburant && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" data-testid="bloc-consommation">
          <ChampNombre id="gen-eco-quantite" label="Consommation (quantité)"
                       valeur={e.quantite} onChange={maj('quantite')} />
          <ChoixNatif id="gen-eco-unite" label="Unité" valeur={e.unite}
                      onChange={maj('unite')}
                      options={[['bouteille_12kg', 'Bouteille 12 kg'], ['litre', 'Litre']]} />
          <ChoixNatif id="gen-eco-periode" label="Période" valeur={e.periode}
                      onChange={maj('periode')}
                      options={[['jour_irrigation', "Par jour d'irrigation"],
                        ['semaine', 'Par semaine'], ['mois', 'Par mois']]} />
          {e.periode === 'jour_irrigation' && (
            <ChampNombre id="gen-eco-jours" label="Jours d'irrigation par semaine"
                         valeur={e.joursSemaine} onChange={maj('joursSemaine')} />
          )}
          <div className="grid gap-1.5">
            <ChampNombre id="gen-eco-prix"
                         label={e.unite === 'litre' ? 'Prix payé (DH / L)' : 'Prix payé (DH / bouteille)'}
                         valeur={e.prix} onChange={maj('prix')} />
            {repereSource && (
              <p className="text-xs text-muted-foreground" data-testid="repere-energie">
                Repère : {fmtNum(repere.valeur)} DH — {repere.source}
                {repere.releve_le ? ` (relevé le ${repere.releve_le})` : ''}
              </p>
            )}
          </div>
        </div>
      )}
      {e.energie === 'electrique' && (
        <div className="grid gap-4 sm:grid-cols-3" data-testid="bloc-facture-reseau">
          <ChampNombre id="gen-eco-facture" label="Montant de la facture (MAD)"
                       valeur={e.factureMontant} onChange={maj('factureMontant')} />
          <ChoixNatif id="gen-eco-facture-periodicite" label="Périodicité"
                      valeur={e.facturePeriodicite} onChange={maj('facturePeriodicite')}
                      options={[['mensuelle', 'Mensuelle'], ['bimestrielle', 'Bimestrielle']]} />
          <ChampNombre id="gen-eco-part-fixe" label="Part fixe (MAD / mois)"
                       valeur={e.facturePartFixe} onChange={maj('facturePartFixe')} />
        </div>
      )}
      <fieldset className="grid gap-1" data-testid="mois-irrigation">
        <legend className="text-sm">
          Mois d'irrigation
          {!Array.isArray(e.mois) && (moisCalendrier || []).length > 0 && !e.confirme
            ? ' — pré-cochés par le calendrier de la culture' : ''}
        </legend>
        <div className="flex flex-wrap gap-2">
          {MOIS.map(([v, l]) => (
            <label key={v} className="flex items-center gap-1 text-xs">
              <input type="checkbox" data-testid={`mois-irr-${v}`}
                     checked={coches.has(Number(v))}
                     onChange={() => basculerMois(Number(v))} />
              {l.slice(0, 3)}
            </label>
          ))}
        </div>
        <label className="flex items-center gap-2 text-xs">
          <input type="checkbox" checked={Boolean(e.confirme)}
                 onChange={ev => majEco?.('confirme', ev.target.checked)} />
          Mois confirmés avec le client
        </label>
      </fieldset>
      {coherenceAvertit && (
        <label className="flex items-center gap-2 text-sm text-warning" data-testid="coherence-confirmee">
          <input type="checkbox" checked={Boolean(e.coherenceConfirmee)}
                 onChange={ev => majEco?.('coherenceConfirmee', ev.target.checked)} />
          Je confirme ce chiffre avec le client
        </label>
      )}
    </div>
  )
}

const MOIS = [['1', 'Janvier'], ['2', 'Février'], ['3', 'Mars'], ['4', 'Avril'],
  ['5', 'Mai'], ['6', 'Juin'], ['7', 'Juillet'], ['8', 'Août'],
  ['9', 'Septembre'], ['10', 'Octobre'], ['11', 'Novembre'], ['12', 'Décembre']]
// QJR241 — clé de marché de ce panneau (ex-`cle` de quote/marches/agricole.js,
// module supprimé faute de consommateur de production).
const CLE = 'agricole'

// AGR218 (contrat AGR200) — « Le client atteste l'usage exclusivement
// agricole » : case + date + signataire, écrits tels que saisis dans
// `etude_params.attestation_usage_agricole` (jamais cochée d'office).
function AttestationUsageAgricole({ attestation, majAttestation }) {
  const a = attestation || {}
  const maj = (cle) => (valeur) => majAttestation?.(cle, valeur)
  return (
    <div className="mt-4 rounded-lg border border-border p-3"
         data-testid="attestation-usage-agricole">
      <label className="flex items-center gap-2 text-sm font-medium">
        <input type="checkbox" id="gen-attestation-agricole"
               checked={!!a.attestee}
               onChange={e => maj('attestee')(e.target.checked)} />
        Le client atteste l’usage exclusivement agricole
      </label>
      <div className="mt-3 grid gap-4 sm:grid-cols-2">
        <ChampTexte id="gen-attestation-le" label="Date de l’attestation" type="date"
                    valeur={a.le} onChange={maj('le')} />
        <ChampTexte id="gen-attestation-signataire" label="Signataire"
                    valeur={a.signataire} onChange={maj('signataire')} />
      </div>
    </div>
  )
}

export default function PanneauAgricole({
  marche,
  // ── Pompe et forage ──
  pompeCv, setPompeCv, pompeType, setPompeType,
  pompeAlim, dispatchSizing, pompeHmt, setPompeHmt, pompeDebit, setPompeDebit,
  pompeProfondeur, setPompeProfondeur,
  pompeDistance, setPompeDistance,
  // ── Votre exploitation (toutes optionnelles) ──
  farmSurfaceHa, setFarmSurfaceHa, farmCrop, setFarmCrop,
  farmRegion, setFarmRegion, farmIrrigation, setFarmIrrigation,
  // ── AGR212 — économie DÉCLARÉE ──
  ecoPompage, majEco, reperesEnergie, moisCalendrier, coherenceAvertit,
  farmHmtStatic, setFarmHmtStatic, farmHmtDrawdown, setFarmHmtDrawdown,
  // ── AGR128 — blocs nouveaux (cas de pompe, besoin, point d'eau, HMT) ──
  pompageSaisie, majPompage, apercuPompage,
  // ── AGR213 — lignes de l'écran (investissement recalculé côté serveur) ──
  lignesDevis = [],
  // ── AGR218 — attestation d'usage agricole {attestee, le, signataire} ──
  attestation = null, majAttestation,
}) {
  if (marche !== CLE) return null
  const sp = pompageSaisie || {}
  const plaque = sp.plaque || {}
  const besoin = sp.besoin || {}
  const source = sp.source || {}
  const hmt = sp.hmt || {}
  const conduite = hmt.conduite || {}
  const maj = (chemin) => (valeur) => majPompage?.(chemin, valeur)
  const existante = sp.mode_pompe === 'existante'
  const hmtServeur = apercuPompage?.donnees?.hmt || null
  return (
    <Card>
      <GenCardHeader icon={Sprout} title="Pompage solaire" />
      <CardContent className="pt-4">
        {/* ── (1) Cas de pompe : neuve ou existante (D-AGR-7) ── */}
        <div className="grid gap-1.5" data-testid="bloc-cas-pompe">
          <Label>Cas de pompe</Label>
          <Segmented
            options={[
              { value: 'neuve', label: 'Pompe neuve' },
              { value: 'existante', label: 'Pompe existante conservée' },
            ]}
            value={sp.mode_pompe || ''}
            onChange={maj('mode_pompe')}
          />
        </div>
        {existante ? (
          <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-5" data-testid="bloc-plaque">
            <ChampNombre id="gen-plaque-kw" label="Plaque : puissance (kW)"
                         valeur={plaque.kw} onChange={maj('plaque.kw')} />
            <div className="grid gap-1.5">
              <Label htmlFor="gen-pompecv">Plaque : puissance (CV)</Label>
              <Input id="gen-pompecv" type="number" min="0" step="any"
                     value={pompeCv} onChange={e => setPompeCv(e.target.value)} />
            </div>
            <ChampNombre id="gen-plaque-tension" label="Plaque : tension (V)"
                         valeur={plaque.tension_v} onChange={maj('plaque.tension_v')} />
            <ChoixNatif id="gen-plaque-phases" label="Plaque : phases"
                        valeur={plaque.phases} onChange={maj('plaque.phases')}
                        options={[['mono', 'Monophasé'], ['tri', 'Triphasé']]} />
            <ChampNombre id="gen-plaque-courant" label="Plaque : courant (A)"
                         valeur={plaque.courant_a} onChange={maj('plaque.courant_a')} />
          </div>
        ) : (pompeCv !== '' && pompeCv != null && (
          <p className="mt-2 text-xs text-muted-foreground" data-testid="pompe-actuelle-info">
            Pompe actuelle du client : {pompeCv} CV (information — une pompe neuve
            est dimensionnée par le serveur).
          </p>
        ))}
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          <div className="grid gap-1.5">
            <Label>Type de pompe</Label>
            <Segmented
              options={[
                { value: 'immergee', label: 'Immergée' },
                { value: 'surface', label: 'Surface' },
              ]}
              value={pompeType}
              onChange={setPompeType}
            />
          </div>
          <div className="grid gap-1.5">
            <Label>Alimentation</Label>
            <Segmented
              options={[
                { value: 'mono', label: 'Mono 220V' },
                { value: 'tri', label: 'Tri 380V' },
              ]}
              value={pompeAlim}
              onChange={(v) => dispatchSizing({ type: 'SAISI', champ: 'pompeAlim', valeur: v })}
            />
          </div>
        </div>
        {/* ── (2) Besoin en eau : déclaré d'abord (D-AGR-3) ── */}
        <div className="mt-4 grid gap-1.5" data-testid="bloc-besoin">
          <Label>Besoin en eau</Label>
          <Segmented
            options={[
              { value: 'volume_declare', label: 'Volume déclaré' },
              { value: 'pompe_actuelle', label: 'Pompe actuelle' },
              { value: 'agronomique', label: 'Cultures' },
            ]}
            value={besoin.mode || ''}
            onChange={maj('besoin.mode')}
          />
        </div>
        {besoin.mode === 'volume_declare' && (
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            <ChampNombre id="gen-besoin-volume" label="Volume par jour (m³/jour)"
                         valeur={besoin.volume_m3_jour} onChange={maj('besoin.volume_m3_jour')} />
            <ChoixNatif id="gen-besoin-mois-pointe" label="Mois de pointe"
                        valeur={besoin.mois_pointe} onChange={maj('besoin.mois_pointe')}
                        options={MOIS} />
          </div>
        )}
        {besoin.mode === 'pompe_actuelle' && (
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            <ChampNombre id="gen-besoin-debit-actuel"
                         label="Débit de la pompe actuelle (m³/h) — déclaré par le client"
                         valeur={besoin.debit_actuel_m3h} onChange={maj('besoin.debit_actuel_m3h')} />
            <ChampNombre id="gen-besoin-heures-actuelles"
                         label="Heures de pompage actuelles / jour — déclaré par le client"
                         valeur={besoin.heures_actuelles_jour}
                         onChange={maj('besoin.heures_actuelles_jour')} />
          </div>
        )}

        {/* ── (3) Point d'eau ── */}
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3" data-testid="bloc-point-eau">
          <ChampNombre id="gen-source-debit" label="Débit d'exploitation du forage (m³/h)"
                       valeur={source.debit_exploitation_m3h}
                       onChange={maj('source.debit_exploitation_m3h')} />
          <ChoixNatif id="gen-source-debit-origine" label="Origine du débit"
                      valeur={source.debit_exploitation_origine}
                      onChange={maj('source.debit_exploitation_origine')}
                      options={[['essai', 'Essai de pompage'], ['foreur', 'Donné par le foreur'],
                        ['client', 'Estimation du client'], ['mesure_visite', 'Mesuré en visite']]} />
          <ChampTexte id="gen-source-debit-date" label="Date du débit" type="date"
                      valeur={source.debit_exploitation_date}
                      onChange={maj('source.debit_exploitation_date')} />
          <ChampNombre id="gen-source-debit-autorise" label="Débit autorisé ABH (m³/h)"
                       valeur={source.debit_autorise_m3h} onChange={maj('source.debit_autorise_m3h')} />
          <ChampNombre id="gen-source-volume-autorise" label="Volume annuel autorisé ABH (m³)"
                       valeur={source.volume_annuel_autorise_m3}
                       onChange={maj('source.volume_annuel_autorise_m3')} />
          <ChoixNatif id="gen-source-compteur" label="Compteur d'eau"
                      valeur={source.compteur} onChange={maj('source.compteur')}
                      options={[['oui', 'Oui'], ['non', 'Non']]} />
          <ChampNombre id="gen-source-niveau-dynamique" label="Niveau dynamique (m)"
                       valeur={source.niveau_dynamique_m} onChange={maj('source.niveau_dynamique_m')} />
          <ChampNombre id="gen-source-tubage" label="Diamètre de tubage (mm)"
                       valeur={source.diametre_tubage_mm} onChange={maj('source.diametre_tubage_mm')} />
          <ChampNombre id="gen-source-calage" label="Profondeur de calage (m)"
                       valeur={source.profondeur_calage_m} onChange={maj('source.profondeur_calage_m')} />
          <ChampNombre id="gen-source-reservoir" label="Réservoir (m³)"
                       valeur={source.volume_reservoir_m3} onChange={maj('source.volume_reservoir_m3')} />
        </div>

        {/* ── (4) Hauteur manométrique ── */}
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div className="grid gap-1.5">
            <Label htmlFor="gen-hmt">
              HMT saisie (m){hmtServeur?.source === 'calculee' && pompeHmt !== '' ? ' — surcharge' : ''}
            </Label>
            <Input id="gen-hmt" type="number" min="0" step="any"
                   placeholder="ex: 120" value={pompeHmt}
                   onChange={e => setPompeHmt(e.target.value)} />
            {hmtServeur?.valeur_m != null && (
              <p className="text-xs text-muted-foreground" data-testid="hmt-serveur">
                HMT retenue par le serveur : {fmtNum(hmtServeur.valeur_m)} m
                ({hmtServeur.source === 'saisie' ? 'saisie' : 'calculée'})
              </p>
            )}
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="gen-debit">Débit souhaité (m³/h)</Label>
            <Input id="gen-debit" type="number" min="0" step="any"
                   placeholder="ex: 30" value={pompeDebit}
                   onChange={e => setPompeDebit(e.target.value)} />
          </div>
          {/* AGNR26 — « Heures de pompage effectives / jour » retiré : plus rien
              ne le lisait (production heure par heure côté serveur). */}
          <div className="grid gap-1.5">
            <Label htmlFor="gen-profondeur">Profondeur forage (m) — optionnel</Label>
            <Input id="gen-profondeur" type="number" min="0" step="any"
                   value={pompeProfondeur}
                   onChange={e => setPompeProfondeur(e.target.value)} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="gen-distance">Distance champ → coffret (m)</Label>
            <Input id="gen-distance" type="number" min="0" step="any"
                   value={pompeDistance}
                   onChange={e => setPompeDistance(e.target.value)} />
          </div>
        </div>
        <label className="mt-3 flex items-center gap-2 text-sm">
          <input type="checkbox" data-testid="hmt-detail"
                 checked={Boolean(hmt.detail)}
                 onChange={e => majPompage?.('hmt.detail', e.target.checked)} />
          Détailler la HMT (dénivelé, conduite, pression)
        </label>
        {hmt.detail && (
          <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3" data-testid="bloc-hmt-detail">
            <ChampNombre id="gen-hmt-denivele" label="Dénivelé (m)"
                         valeur={hmt.denivele_m} onChange={maj('hmt.denivele_m')} />
            <ChoixNatif id="gen-hmt-materiau" label="Conduite : matériau"
                        valeur={conduite.materiau} onChange={maj('hmt.conduite.materiau')}
                        options={[['pehd', 'PEHD'], ['pvc', 'PVC'], ['acier', 'Acier'], ['autre', 'Autre']]} />
            <ChampNombre id="gen-hmt-diametre" label="Conduite : diamètre intérieur (mm)"
                         valeur={conduite.diametre_interieur_mm}
                         onChange={maj('hmt.conduite.diametre_interieur_mm')} />
            <ChampNombre id="gen-hmt-longueur" label="Conduite : longueur (m)"
                         valeur={conduite.longueur_m} onChange={maj('hmt.conduite.longueur_m')} />
            {conduite.materiau && !['pehd', 'pvc'].includes(conduite.materiau) && (
              <ChampNombre id="gen-hmt-c" label="Coefficient C de Hazen-Williams"
                           valeur={conduite.c_hazen_williams}
                           onChange={maj('hmt.conduite.c_hazen_williams')} />
            )}
            <ChampNombre id="gen-hmt-singulieres" label="Pertes singulières (m)"
                         valeur={hmt.pertes_singulieres_m} onChange={maj('hmt.pertes_singulieres_m')} />
            <ChampNombre id="gen-hmt-pression" label="Pression de service (bar)"
                         valeur={hmt.pression_service_bar} onChange={maj('hmt.pression_service_bar')} />
          </div>
        )}

        {/* ── Votre exploitation (données GUIDÉES, toutes optionnelles) ── */}
        {/* Encouragées : le besoin en eau FAO-56 qu'elles permettent d'estimer
            alimente bien le dimensionnement pompage du PDF (cartes HMT /
            Débit / Eau-par-jour du one-page). AGR316 — l'économie, elle,
            ne sort QUE des dépenses DÉCLARÉES (bloc AGR3, D-AGR-5) : le
            document 3 pages l'imprime, le une-page jamais (texte visible
            ci-dessous, preuve exécutée :
            apps/ventes/tests/test_qjr428_promesse_carburant_agricole.py).
            Aucune donnée n'est obligatoire — chacune a un défaut. */}
        <div className="mt-4 rounded-lg border border-success/30 bg-success/5 p-3 sm:p-4">
          <div className="flex flex-wrap items-center gap-2">
            <Sprout className="size-4 text-success" aria-hidden="true" />
            <span className="font-display text-sm font-semibold tracking-tight">
              Votre exploitation
            </span>
            <span className="text-xs text-muted-foreground">
              recommandé — affine le devis avec les données réelles du fermier
            </span>
          </div>
          <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div className="grid gap-1.5">
              <Label htmlFor="gen-farm-surface">
                Surface irriguée (ha)
              </Label>
              <Input id="gen-farm-surface" type="number" min="0" step="any"
                     placeholder="ex: 5" value={farmSurfaceHa}
                     onChange={e => setFarmSurfaceHa(e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="gen-farm-crop">Culture</Label>
              <Select value={farmCrop} onValueChange={setFarmCrop}>
                <SelectTrigger id="gen-farm-crop"><SelectValue placeholder="Non renseignée" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="agrumes">Agrumes</SelectItem>
                  <SelectItem value="maraichage">Maraîchage</SelectItem>
                  <SelectItem value="olivier">Olivier</SelectItem>
                  <SelectItem value="dattier">Dattier (palmier)</SelectItem>
                  <SelectItem value="cereales">Céréales</SelectItem>
                  <SelectItem value="luzerne">Luzerne / fourrage</SelectItem>
                  <SelectItem value="arganier">Arganier</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="gen-farm-region">Région</Label>
              <Select value={farmRegion} onValueChange={setFarmRegion}>
                <SelectTrigger id="gen-farm-region"><SelectValue placeholder="Non renseignée" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="souss-massa">Souss-Massa (Agadir)</SelectItem>
                  <SelectItem value="doukkala">Doukkala (El Jadida)</SelectItem>
                  <SelectItem value="tadla">Tadla (Béni Mellal)</SelectItem>
                  <SelectItem value="saiss">Saïss (Fès-Meknès)</SelectItem>
                  <SelectItem value="oriental">Oriental (Berkane)</SelectItem>
                  <SelectItem value="draa-tafilalet">Drâa-Tafilalet</SelectItem>
                  <SelectItem value="gharb-loukkos">Gharb-Loukkos</SelectItem>
                  <SelectItem value="haouz">Haouz (Marrakech)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="gen-farm-irrigation">Mode d'irrigation</Label>
              <Select value={farmIrrigation} onValueChange={setFarmIrrigation}>
                <SelectTrigger id="gen-farm-irrigation"><SelectValue placeholder="Non renseigné" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="goutte">Goutte-à-goutte</SelectItem>
                  <SelectItem value="aspersion">Aspersion</SelectItem>
                  <SelectItem value="gravitaire">Gravitaire</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="gen-farm-static">
                Niveau statique de l'eau (m) — optionnel
              </Label>
              <Input id="gen-farm-static" type="number" min="0" step="any"
                     placeholder="ex: 40" value={farmHmtStatic}
                     onChange={e => setFarmHmtStatic(e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="gen-farm-drawdown">
                Rabattement en pompage (m) — optionnel
              </Label>
              <Input id="gen-farm-drawdown" type="number" min="0" step="any"
                     placeholder="ex: 15" value={farmHmtDrawdown}
                     onChange={e => setFarmHmtDrawdown(e.target.value)} />
            </div>
          </div>

        </div>

        <EconomieDeclaree eco={ecoPompage} majEco={majEco}
                          reperes={reperesEnergie} moisCalendrier={moisCalendrier}
                          coherenceAvertit={coherenceAvertit} />
        {/* AGR316 — ce que le document imprime VRAIMENT de l'économie. */}
        <p className="mt-2 text-xs text-muted-foreground" data-testid="texte-economies-pdf">
          {'Les dépenses que le client DÉCLARE (datées) alimentent le bloc économies du document 3 pages ; sans déclaration, le bloc est omis. Le une-page n’imprime aucune économie.'}
        </p>

        {/* ── AGR213 — l'économie DÉCLARÉE en direct, servie par le serveur ── */}
        <CarteEconomiePompage eco={ecoPompage} moisCalendrier={moisCalendrier}
                              sortieEtude={apercuPompage?.donnees || null}
                              lignes={lignesDevis} majEco={majEco} />

        {/* ── AGR218 — attestation d'usage agricole (contrat AGR200) ── */}
        <AttestationUsageAgricole attestation={attestation}
                                  majAttestation={majAttestation} />

        {/* ── AGR129 — le résultat SERVEUR en direct (aperçu AGR127) ── */}
        {apercuPompage?.chargement && (
          <p className="mt-3 text-xs text-muted-foreground">Calcul du pompage…</p>
        )}
        {apercuPompage?.erreur && (
          <p className="mt-3 text-xs text-destructive" role="alert">{apercuPompage.erreur}</p>
        )}
        <ResultatPompage donnees={apercuPompage?.donnees}
                         saisie={pompageSaisie} majPompage={majPompage} />
      </CardContent>
    </Card>
  )
}
