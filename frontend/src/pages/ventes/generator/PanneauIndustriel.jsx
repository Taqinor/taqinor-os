// QJR101 — PANNEAU DE MARCHÉ : INDUSTRIEL.
// ---------------------------------------------------------------------------
// Quatre panneaux sortent de `DevisGenerator.jsx` : chacun ne monte que les
// champs de SON marché. L'industriel n'a ni catégorie commerciale ni pompage.
//
// QJR241 — le panneau se retire lui-même hors de son marché via `CLE`
// (constante locale) — le même patron que `DevisOffresTailles`.
// `modeInstallation` ne vaut jamais qu'une des quatre clés (le reducer refuse
// toute autre valeur, `modeDepuisTypeInstallation`), donc exactement un
// panneau rend.
//
// CIQ125/CIQ126 — UNE seule saisie de consommation : le profil déclaré C&I
// (`CarteProfilCi`, partagée avec le commercial) et le résultat du moteur
// serveur. Les factures hiver/été et la facture réelle résidentielles ne sont
// plus montées ici (elles ne dimensionnaient pas le C&I).
//
// CIQ135 — la carte INDUSTRIELLE (`CarteIndustrielleMt`) : équipes, registres
// MT, cos φ connu, import d'une courbe mesurée. Aucun calcul : le serveur
// rend la méthode retenue et les alertes (les internes « vendeur seulement »).
//
// AUCUNE LOGIQUE ICI : l'état et les gestes arrivent en props. Chaque
// `<input type="number">` garde `step="any"` (règle fondateur : aucun champ
// ne snappe jamais) et le `noValidate` est resté sur le formulaire porteur.
import { useState } from 'react'
import { Gauge } from 'lucide-react'
import { Card, CardContent, Input, Label } from '../../../ui'
import { MONTHS_FR } from '../../../features/ventes/solar'
import { EQUIPES, COLONNES_REGISTRE_MT } from '../../../features/ventes/quote/profilCi'
import { alertesAffichables } from '../../../features/ventes/etudeCiPreview'
import { CarteProfilCi } from './BlocEtudeReseau'
import { GenCardHeader } from './CarteMetrique'
// CIQ223 — la carte « Économies » servie par le serveur (`economie_ci`).
import CarteEconomieCi from './CarteEconomieCi'

const CLE = 'industriel'

const SELECT = 'form-control form-control-sm'
const METHODES = {
  courbe_mesuree: 'courbe mesurée',
  registres_mt: 'registres de la facture MT',
  declare: 'profil déclaré',
  archetype: 'profil type (estimation)',
}
// Les codes d'alerte de CIQ132/CIQ134 mis en avant sous la grille.
const CODES_MIS_EN_AVANT = ['incoherence_equipes_registres', 'cos_phi_apres_pv', 'cos_phi_non_evalue']

/** Lit un fichier de courbe (texte CSV) ; le PARSEUR reste côté serveur. */
function lireFichierTexte(fichier) {
  return new Promise((resolve, reject) => {
    const lecteur = new FileReader()
    lecteur.onload = () => resolve(String(lecteur.result || ''))
    lecteur.onerror = () => reject(lecteur.error)
    lecteur.readAsText(fichier)
  })
}

export function CarteIndustrielleMt({ profilCi, setChampCi, apercuCi }) {
  const p = profilCi || {}
  const donnees = apercuCi?.donnees || null
  const methode = donnees?.profil_charge?.methode || donnees?.methode || null
  const alertes = alertesAffichables(donnees || {}).filter((a) => CODES_MIS_EN_AVANT.includes(a.code))
  const [erreurFichier, setErreurFichier] = useState(null)
  const importer = async (e) => {
    const fichier = e.target.files && e.target.files[0]
    if (!fichier) return
    setErreurFichier(null)
    if (/\.xlsx?$/i.test(fichier.name)) {
      setErreurFichier("Fichier Excel : enregistrez-le d'abord au format CSV, puis importez-le.")
      return
    }
    try {
      const contenu = await lireFichierTexte(fichier)
      setChampCi('courbe', { contenu, source: fichier.name })
    } catch {
      setErreurFichier('Fichier illisible.')
    }
  }
  return (
    <Card>
      <GenCardHeader icon={Gauge} title="Équipes, registres MT et courbe mesurée" />
      <CardContent className="pt-4 grid gap-4" data-testid="ci-industriel-mt">
        <fieldset className="grid gap-4 sm:grid-cols-3">
          <legend className="text-sm font-semibold">Équipes</legend>
          <div className="grid gap-1.5">
            <Label htmlFor="gen-ci-equipes">Équipes de travail</Label>
            <select id="gen-ci-equipes" className={SELECT} value={p.equipes || ''}
                    onChange={(e) => setChampCi('equipes', e.target.value)}>
              <option value="">—</option>
              {EQUIPES.map((q) => <option key={q.value} value={q.value}>{q.label}</option>)}
            </select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="gen-ci-debut-equipe">Heure de début (h)</Label>
            <Input id="gen-ci-debut-equipe" type="number" min="0" step="any" placeholder="ex: 6"
                   value={p.debutEquipeH ?? ''}
                   onChange={(e) => setChampCi('debutEquipeH', e.target.value)} />
          </div>
        </fieldset>

        <fieldset className="grid gap-2">
          <legend className="text-sm font-semibold">Registres de la facture MT (12 mois)</legend>
          <div className="overflow-x-auto">
            <table className="w-full text-xs" data-testid="ci-registres-mt">
              <thead>
                <tr>
                  <th className="text-left">Mois</th>
                  {COLONNES_REGISTRE_MT.map((c) => <th key={c.cle}>{c.libelle}</th>)}
                </tr>
              </thead>
              <tbody>
                {MONTHS_FR.map((m, i) => (
                  <tr key={m}>
                    <td>{m}</td>
                    {COLONNES_REGISTRE_MT.map((c) => (
                      <td key={c.cle}>
                        <input type="number" min="0" step="any" className="form-control form-control-sm"
                               aria-label={`${c.libelle} ${m}`}
                               data-testid={`gen-ci-reg-${i}-${c.cle}`}
                               value={p.registresMt?.[i]?.[c.cle] ?? ''}
                               onChange={(e) => setChampCi(`registresMt.${i}.${c.cle}`, e.target.value)} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="grid gap-1.5">
              <Label htmlFor="gen-ci-cos-phi">cos φ connu</Label>
              <Input id="gen-ci-cos-phi" type="number" min="0" step="any" placeholder="ex: 0.85"
                     value={p.cosPhi ?? ''} onChange={(e) => setChampCi('cosPhi', e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="gen-ci-cos-phi-prov">Source du cos φ</Label>
              <select id="gen-ci-cos-phi-prov" className={SELECT} value={p.cosPhiProvenance || ''}
                      onChange={(e) => setChampCi('cosPhiProvenance', e.target.value)}>
                <option value="">—</option>
                <option value="facture">Lu sur la facture</option>
                <option value="mesure">Mesuré en visite</option>
                <option value="declare">Déclaré par le client</option>
              </select>
            </div>
          </div>
        </fieldset>

        <fieldset className="grid gap-2">
          <legend className="text-sm font-semibold">Courbe de charge mesurée (CSV)</legend>
          <input type="file" accept=".csv,.txt,.tsv,.xls,.xlsx" data-testid="gen-ci-courbe-fichier"
                 aria-label="Importer une courbe de charge" onChange={importer} />
          {p.courbe && (
            <p className="text-xs text-muted-foreground" data-testid="ci-courbe-importee">
              Courbe importée : {p.courbe.source || 'fichier'} — analysée par le serveur.{' '}
              <button type="button" className="underline" data-testid="gen-ci-courbe-retirer"
                      onClick={() => setChampCi('courbe', null)}>Retirer</button>
            </p>
          )}
          {erreurFichier && (
            <p className="text-xs text-destructive" data-testid="ci-courbe-erreur">{erreurFichier}</p>
          )}
        </fieldset>

        {methode && (
          <p className="text-xs" data-testid="ci-methode-retenue">
            Méthode retenue : <strong>{METHODES[methode] || methode}</strong>
          </p>
        )}
        {alertes.length > 0 && (
          <ul className="text-xs grid gap-1" data-testid="ci-alertes-industriel">
            {alertes.map((a) => (
              <li key={a.cle} className="text-warning">
                {a.interne && <strong>Vendeur seulement — </strong>}
                {a.message}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

// `carte` = les props de la carte C&I (profil, aperçu, tarif, erreurs).
export default function PanneauIndustriel({ marche, ...carte }) {
  if (marche !== CLE) return null
  return (
    <>
      <CarteProfilCi {...carte} />
      <CarteIndustrielleMt profilCi={carte.profilCi} setChampCi={carte.setChampCi} apercuCi={carte.apercuCi} />
      <CarteEconomieCi apercu={carte.apercuEcoCi} eco={carte.ecoCi} setEcoChamp={carte.setEcoChamp} />
    </>
  )
}
