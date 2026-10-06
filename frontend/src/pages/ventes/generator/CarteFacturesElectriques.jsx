// QJR244 — LA CARTE « FACTURES ÉLECTRIQUES », PARTAGÉE.
// ---------------------------------------------------------------------------
// L'extraction QJR101 (les quatre panneaux de marché) a TRIPLÉ ~99 lignes
// verbatim de cette carte à travers les trois panneaux de marché RÉSEAU
// (Résidentiel, Industriel, Commercial — l'Agricole/pompage ne l'affiche pas)
// au lieu de la partager : trois copies à maintenir, exactement la classe de
// dette que l'extraction devait supprimer.
//
// DÉPLACEMENT PUR, AUCUN CHANGEMENT DE RENDU : le balisage partagé (factures
// mensuelles hiver/été + grille des 12 mois + bloc « facture réelle du
// client ») sort à l'octet. `children` est le SLOT qui laisse chaque panneau
// ajouter SON contenu propre APRÈS ce bloc, DANS LA MÊME `CardContent` —
// Industriel/Commercial y placent consommation/injection/raccordement MT (et
// Commercial, en plus, sa catégorie) ; Résidentiel n'y met rien. Le DOM reste
// donc byte-identique : une seule `<Card>`, un seul `<CardContent>`, jamais
// une carte supplémentaire.
import { Zap, BarChart3 } from 'lucide-react'
import {
  Card, CardContent, Button, Input, Label, HelpTip,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../../ui'
import { GenCardHeader } from './CarteMetrique'
import { MONTHS_FR } from '../../../features/ventes/solar'
import { formatNumber } from '../../../lib/format'

const fmtNum = (v) => (v !== null && v !== undefined) ? formatNumber(v) : 'N/A'

export default function CarteFacturesElectriques({
  fHiver, setFHiver, fEte, setFEte, syncBillEstimator,
  onHiverPaste, onEtePaste, handleEstimerMois, errors, monthly, setMonth,
  distributeur, setDistributeur, realBillMode, setRealBillMode,
  realBillMad, setRealBillMad, realBillKwh, setRealBillKwh,
  onRealBillPaste, consoAnnuelleReelle,
  children,
}) {
  return (
    <Card>
      <GenCardHeader icon={Zap} title="Factures Électriques" />
      <CardContent className="pt-4">
        <p className="text-sm text-muted-foreground">
          Renseignez vos factures mensuelles (MAD) ou estimez-les via les montants
          hiver/été. Ces valeurs servent au calcul ROI dans le devis.
        </p>
        <div className="mt-3 grid items-end gap-4 sm:grid-cols-3">
          <div className="grid gap-1.5">
            <Label htmlFor="gen-hiver">Facture Hiver moy. (MAD/mois)</Label>
            <Input id="gen-hiver" type="number" min="0" step="any"
                   placeholder="ex: 600" value={fHiver}
                   onChange={e => { setFHiver(e.target.value); syncBillEstimator(e.target.value, fEte) }}
                   onPaste={onHiverPaste} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="gen-ete">Facture Été moy. (MAD/mois)</Label>
            <Input id="gen-ete" type="number" min="0" step="any"
                   placeholder="ex: 400" value={fEte}
                   onChange={e => { setFEte(e.target.value); syncBillEstimator(fHiver, e.target.value) }}
                   onPaste={onEtePaste} />
          </div>
          <Button type="button" variant="outline" onClick={handleEstimerMois}>
            <BarChart3 /> Estimer 12 mois
          </Button>
        </div>
        {errors.bills && <p className="mt-1 text-xs text-destructive">{errors.bills}</p>}
        <div className="gen-monthly-grid">
          {MONTHS_FR.map((m, i) => (
            <div key={m} className="gen-month">
              <span className="gen-month-label">{m}</span>
              <input type="number" min="0" step="any" className="form-control form-control-sm"
                     value={monthly[i]}
                     onChange={e => setMonth(i, e.target.value)} />
            </div>
          ))}
        </div>

        {/* QF4 — distributeur réel + facture/consommation réelle : nourrit
            le calcul « deux factures » par tranche (backend QF2) avec les
            vrais chiffres du client au lieu des défauts. */}
        <div className="mt-4 rounded-lg border border-info/30 bg-info/5 p-3 sm:p-4">
          <div className="flex flex-wrap items-center gap-2">
            <Zap className="size-4 text-info" aria-hidden="true" />
            <span className="font-display text-sm font-semibold tracking-tight">
              Facture réelle du client (recommandé)
            </span>
            {/* VX47 — aide contextuelle : le calcul « par tranche » selon
                le distributeur n'est pas intuitif pour un nouvel employé. */}
            <HelpTip label="Aide — distributeur et tranches">
              Chaque distributeur (ONEE, Lydec, Redal) facture l'électricité
              par <strong>tranches</strong> : plus la consommation est
              élevée, plus le prix du kWh grimpe. En renseignant la facture
              ou consommation réelle du client, l'économie solaire est
              calculée avec le vrai barème du distributeur choisi — sans
              ces champs, une estimation par défaut est utilisée.
            </HelpTip>
            <span className="text-xs text-muted-foreground">
              affine les économies avec le barème par tranche du distributeur
            </span>
          </div>
          <div className="mt-3 grid gap-4 sm:grid-cols-3">
            <div className="grid gap-1.5">
              <Label htmlFor="gen-distributeur">Distributeur</Label>
              <Select value={distributeur} onValueChange={setDistributeur}>
                <SelectTrigger id="gen-distributeur"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="onee">ONEE</SelectItem>
                  <SelectItem value="lydec">Lydec (Casablanca)</SelectItem>
                  <SelectItem value="redal">Redal (Rabat-Salé-Kénitra)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="gen-realbill">
                {realBillMode === 'mad' ? 'Facture réelle (MAD/mois)' : 'Consommation réelle (kWh/mois)'}
              </Label>
              <div className="flex gap-2">
                <Input id="gen-realbill" type="number" min="0" step="any" className="flex-1"
                       placeholder={realBillMode === 'mad' ? 'ex: 850' : 'ex: 650'}
                       value={realBillMode === 'mad' ? realBillMad : realBillKwh}
                       onChange={e => (realBillMode === 'mad'
                         ? setRealBillMad(e.target.value)
                         : setRealBillKwh(e.target.value))}
                       onPaste={onRealBillPaste} />
                <Select value={realBillMode} onValueChange={setRealBillMode}>
                  <SelectTrigger className="w-24"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="mad">MAD</SelectItem>
                    <SelectItem value="kwh">kWh</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid gap-1.5">
              <Label>Consommation annuelle dérivée</Label>
              <div className="gen-kwp">
                {consoAnnuelleReelle != null ? `${fmtNum(consoAnnuelleReelle)} kWh/an` : '—'}
              </div>
            </div>
          </div>
        </div>
        {children}
      </CardContent>
    </Card>
  )
}
