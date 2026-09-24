import { useMemo, useState } from 'react'
import { BookOpen } from 'lucide-react'
import { PageHeader } from '../../ui/PageHeader'
import { Input } from '../../ui/Input'
import useDocumentTitle from '../../hooks/useDocumentTitle'

/* VX247(d) — glossaire métier statique : aucun onboarding n'expliquait le
   vocabulaire (kWc, chantier, DSO, FEC…) à un nouvel employé qui ne le
   connaît pas déjà. Page statique — les `<HelpTip>` (VX47) pointent ICI
   au lieu de dupliquer une définition détaillée dans chaque bulle.
   Contenu 100 % français, aucun appel réseau. */

// Termes métier (solaire + ERP), ORDRE ALPHABÉTIQUE (collation française,
// sans tenir compte des accents ni de la casse — le test l'affirme).
// CALX396 — les mots que les écrans du CALEPINAGE affichent désormais (PR,
// P50/P75/P90, GCR, TSRF, PVGIS, TMY, azimut, tilt, albédo, bifacialité,
// MPPT, écrêtage, calepinage, ombrière, horizon lointain, LID, mismatch) :
// chaque définition est courte, en français, et n'affirme JAMAIS une valeur
// (aucun chiffre) — un nombre se lit sur l'écran qui l'a calculé, pas ici.
const TERMES = [
  { mot: 'Albédo', def: "Part de la lumière que le sol ou une surface voisine renvoie ; elle éclaire la face arrière des modules bifaciaux." },
  { mot: 'Autoconsommation', def: "Part de l'électricité produite consommée directement sur place, sans revente au réseau." },
  { mot: 'Azimut', def: "Orientation horizontale d'un pan ou d'un module, mesurée depuis le nord dans le sens des aiguilles d'une montre." },
  { mot: 'Balance âgée', def: "État qui classe les factures clients impayées par ancienneté (0-30 j, 30-60 j, etc.)." },
  { mot: 'Bifacialité', def: "Capacité d'un module à produire aussi par sa face arrière, grâce à la lumière renvoyée par le sol (albédo)." },
  { mot: 'Bon de commande', def: "Document généré après acceptation d'un devis, qui déclenche l'approvisionnement du matériel." },
  { mot: 'Calepinage', def: "Plan de pose des modules sur une toiture ou un terrain : emplacements, rangées, espacements et obstacles évités." },
  { mot: 'Chantier', def: "L'installation physique du système chez le client, du démarrage des travaux à la mise en service." },
  { mot: 'Chatter', def: "Journal d'activité horodaté d'un enregistrement (modifications automatiques + notes manuelles)." },
  { mot: 'Devis', def: 'Proposition commerciale chiffrée envoyée au client, avant acceptation — distinct de la facture.' },
  { mot: 'DSO (délai moyen de recouvrement)', def: "Nombre moyen de jours entre l'émission d'une facture et son encaissement réel." },
  { mot: 'Écrêtage', def: "Énergie perdue quand la puissance du champ dépasse ce que l'onduleur peut convertir : le surplus est plafonné." },
  { mot: "Encours échu", def: "Montant total des factures clients dont l'échéance est dépassée sans avoir été payées." },
  { mot: "Étude d'autoconsommation", def: "Analyse chiffrée du taux de couverture et des économies pour un projet industriel/commercial." },
  { mot: 'Facture', def: 'Document comptable définitif réclamant le paiement — émis après le devis, jamais modifiable a posteriori.' },
  { mot: 'FEC (fichier des écritures comptables)', def: "Export normalisé exigé par l'administration fiscale en cas de contrôle." },
  { mot: "GCR (taux d'occupation du sol)", def: "Rapport entre la surface des modules et la surface qu'ils occupent au sol : plus il est élevé, plus les rangées s'ombragent entre elles." },
  { mot: 'GED (gestion électronique des documents)', def: 'Module de stockage et de classement centralisé des documents de la société.' },
  { mot: 'HMT (hauteur manométrique totale)', def: "Hauteur équivalente qu'une pompe doit fournir pour vaincre les pertes de charge d'une installation de pompage." },
  { mot: 'Horizon lointain', def: "Relief et constructions éloignés (montagnes, immeubles) qui masquent le soleil bas sur l'horizon et réduisent la production." },
  { mot: 'Injection réseau', def: 'Électricité produite en surplus, renvoyée vers le réseau électrique public.' },
  { mot: 'IS (impôt sur les sociétés)', def: "Impôt calculé sur le bénéfice de l'entreprise." },
  { mot: 'kWc (kilowatt-crête)', def: "Puissance nominale maximale d'une installation photovoltaïque, mesurée dans des conditions standard." },
  { mot: 'Lead', def: 'Prospect intéressé par une offre, avant sa transformation en client signé.' },
  { mot: 'Liasse fiscale', def: "Synthèse annuelle des comptes de la société, transmise au comptable ou à l'administration." },
  { mot: 'LID (dégradation induite par la lumière)', def: "Baisse de rendement d'un module lors de ses premières heures au soleil, déclarée par le fabricant sur sa fiche." },
  { mot: 'Mise en service', def: "Le moment où l'installation est raccordée et commence effectivement à produire de l'électricité." },
  { mot: 'Mismatch (désappariement)', def: "Perte due aux petites différences entre les modules d'une même chaîne : la chaîne suit le module le plus faible." },
  { mot: 'MPPT (suivi du point de puissance maximale)', def: "Fonction de l'onduleur qui ajuste en continu la tension d'une chaîne pour en tirer la puissance maximale." },
  { mot: 'Ombrière', def: 'Structure qui couvre un parking ou une terrasse et dont la toiture porte des modules photovoltaïques.' },
  { mot: 'Onduleur', def: 'Équipement qui convertit le courant continu produit par les panneaux en courant alternatif utilisable.' },
  { mot: 'P50 / P75 / P90', def: "Productions annuelles qui ont respectivement une chance sur deux, trois chances sur quatre et neuf chances sur dix d'être dépassées." },
  { mot: 'Pipeline', def: "Ensemble des affaires commerciales en cours, ni signées ni perdues." },
  { mot: 'PR (ratio de performance)', def: "Rapport entre l'énergie réellement produite et celle qu'aurait donnée l'ensoleillement reçu sans aucune perte : il résume toutes les pertes." },
  { mot: 'PVGIS', def: "Base de données publique de la Commission européenne qui fournit l'ensoleillement et la température heure par heure d'un site." },
  { mot: 'RC décennale', def: "Assurance obligatoire couvrant les dommages à l'ouvrage pendant dix ans après la réception des travaux." },
  { mot: 'SAV (service après-vente)', def: 'Suivi des tickets et interventions techniques après la mise en service.' },
  { mot: 'Stage (étape du funnel)', def: "Position d'un lead dans le parcours commercial (nouveau, contacté, devis envoyé, signé…)." },
  { mot: 'Tilt (inclinaison)', def: "Angle que font les modules avec l'horizontale." },
  { mot: 'TMY (année météorologique type)', def: "Année fictive assemblée à partir de mois réels représentatifs, qui sert à simuler une production typique." },
  { mot: 'TSRF (facteur d’ensoleillement total)', def: "Part du rayonnement disponible qu'un module reçoit réellement, compte tenu de son orientation, de son inclinaison et des ombrages." },
  { mot: 'TVA', def: 'Taxe sur la valeur ajoutée — appliquée sur les ventes, récupérable sur les achats.' },
]

export default function LexiquePage() {
  useDocumentTitle('Lexique')
  const [q, setQ] = useState('')

  const filtered = useMemo(() => {
    const query = q.trim().toLowerCase()
    if (!query) return TERMES
    return TERMES.filter((t) =>
      t.mot.toLowerCase().includes(query) || t.def.toLowerCase().includes(query))
  }, [q])

  return (
    <div className="page">
      <PageHeader
        icon={BookOpen}
        title="Lexique métier"
        subtitle="Le vocabulaire du solaire et de l'ERP, en clair — pointé depuis les bulles d'aide (?) de l'application."
      />

      <div className="mb-4 max-w-sm">
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Rechercher un terme…"
          aria-label="Rechercher un terme du lexique"
        />
      </div>

      {filtered.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">
          Aucun terme ne correspond à « {q} ».
        </p>
      ) : (
        <dl className="flex flex-col divide-y divide-border rounded-lg border border-border bg-card">
          {filtered.map((t) => (
            <div key={t.mot} className="p-4">
              <dt className="font-medium text-foreground">{t.mot}</dt>
              <dd className="mt-1 text-sm leading-relaxed text-muted-foreground">{t.def}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  )
}
