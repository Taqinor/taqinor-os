# C2 — « Tous mes devis se calculent seuls, avec les bonnes hypothèses »

Enquête en lecture seule, 23/11/2026, branche `claude/calpinage-module-l5-aadbde` (HEAD 38a6bf7941). Aucun test lancé,
aucun conteneur, rien vers la production. Question du fondateur : « should only need the bill and one consumption
profil picked as what is hapening in my CRM ». Cause « lue » = fonction ouverte ; « probable » = non ouverte.
Aucun des fichiers ci-dessous n'a été touché par la campagne du jour (`git log bfb859c90..HEAD` vide pour
`crm/devis_auto.py`, `ventes/domain/creation_auto*.py`, `taille.py`, `suppositions_ci.py`, `calepinage/services/
consommation.py`, `chaine_pertes.py`, `data/profil_depart.json`).

## 1. Verdict par marché (facture + profil choisi, rien d'autre)

Chemin : bouton « Devis automatique » → garde `crm/devis_views.py::LeadViewSet.devis_auto` (`crm/devis_auto.py::champs_requis`)
→ `POST /ventes/devis/auto/` (`ventes/views/devis.py::DevisViewSet.auto`) → `ventes/domain/creation_auto.py::build_devis_auto`
qui aiguille vers le moteur du marché → devis BROUILLON → PDF `/proposal`.

| Marché | Profil « choisi » au CRM | Aboutit ? | S'arrête à (dans l'ordre) | Voulu par |
|---|---|---|---|---|
| Résidentiel | `occupation_jour` (vide ⇒ présence) | **Oui**, si la ville est reconnue ou le GPS posé | `ville` (refus `localisation_inconnue`, absent de la garde CRM) ; catalogue | ville : aucun défaut décidé |
| Commercial | `categorie_commerciale` (archétype BDEW/ComStock ; hammam et autre : aucun) | **Non** | `contrat_electricite` (la facture en MAD ne compte qu'avec un contrat BT) ; `raccordement` (phase) ; prix des postes fixes C&I | contrat : D-CIQ-23 ; phase : **aucune décision lue** (ADEV89) ; prix : D-ACI-6 |
| Industriel | `secteur_industriel` : ne sert que si la société a SAISI un profil pour ce secteur (D-ACI-7) ; aucun profil livré dans le code | **Non** | facture MAD comptée seulement si tension BT DÉCLARÉE + contrat BT ; `jours_ouverture` + (`heure_debut`/`heure_fin` ou `regime_equipes`) ; `raccordement` | D-CIQ-1 (aucun archétype industriel), D-ACI-5, D-CIQ-23 |
| Agricole | sans objet : la facture ne dimensionne rien | **Non** (voulu) | `pompe_hmt_m` ; débit souhaité ou besoin m³/j ; `raccordement` (refusé par le moteur, absent de la garde CRM) ; niveau statique + débit du forage (visite) | D-AGQ-5, D-AGR-3, D-AGR-4, AGQ7 |

Causes lues : `crm/devis_auto.py::champs_requis`, `::_rempli`, `::_facture_mad_compte`, `::_contrat_bt_declare`,
`::_groupes_rythme` ; `ventes/moteur_ci/charge.py::profil_charge_prerequis` (dès que des plages existent, les jours sont
exigés, même en 3x8) ; `ventes/moteur_ci/profils.py::forme_archetype` (`CATEGORIES_SANS_ARCHETYPE`) ;
`ventes/domain/etude_ci.py::refus_devis_auto_ci` ; `ventes/domain/taille.py::_panneaux_dimensionnement_horaire` ;
`ventes/domain/creation_auto_agricole.py::_build_devis_auto_agricole`.

## 2. Table des entrées (ce que le calcul lit, son défaut, sa source, s'il est DIT)

Règle du 17/11 (`docs/claude-memory/calculateur-suppositions-dites.md`) : toute supposition est dite avec le champ de la fiche.

| Marché | Entrée (champ) | Défaut dans le code | Source du défaut | Dit ? |
|---|---|---|---|---|
| Rés. | conso : `facture_hiver` (MAD) | inversée au barème ONEE de la société, sinon national — `quote_engine/bareme.py`, `domain/entrees.py::_reglages_tarifaires_de` | factures réelles du fondateur + D5 (en-tête de `bareme.py`) | non au journal du devis auto (lu : seule alerte résidentielle = taille demandée, `creation_auto_residentiel.py::_alerter_taille_demandee`) |
| Rés. | `facture_ete` | facture d'hiver répétée sur 12 mois si `ete_differente` faux (`taille.py::_panneaux_dimensionnement_horaire`, docstring) | CLAUDE.md (« comportement simulateur ») | non (probable) |
| Rés. | profil : `occupation_jour` | présence en journée — `courbes_journalieres.py::occupation_du_lead`, `DEFAUT_RESIDENTIEL` | D4 29/08 + décision 23/10 (`dimensionnement-decisions-2310.md`) | en partie : bandeau `BANDEAU_PROFIL_SUPPOSE` « Profil supposé, à confirmer » SANS nom de champ (lu) |
| Rés. | inclinaison / orientation | 30° plein sud — `parametres/pvgis_profils.py::PVGIS_ANGLE_DEG`, `PVGIS_ASPECT_DEG` | D-RES-2710-1 / QJR107 (champs du lead jamais câblés) | non (probable : aucun libellé résidentiel trouvé dans `quote_engine/builder.py` ni `i18n_labels.py`) |
| Rés. | pertes système | 20 % au total — `quote_engine/pricing.py::SYSTEM_LOSS_TOTAL` (14 % PVGIS inclus, `PVGIS_LOSS_PCT`) | « fondateur 18/08 » cité en commentaire seulement ; 14 % « usuelles », sans lien | non vérifié |
| Rés. | puissance du panneau de repli | 710 Wc — `taille.py::_AUTO_PANEL_WATT` (remplacé par le wattage du balayage) | sans source lue (« cf. solar.js ») | non |
| Rés. | batterie (`batterie_souhaitee`) | vide ⇒ les deux options | U2, fondateur 20/08 (commentaire de `_build_devis_auto_residentiel`) | oui (deux options au PDF) |
| Rés. | `ville` / `gps_lat`,`gps_lng` | aucun : refus | — | refus nommé |
| C&I | conso | kWh > relevé > MAD (MAD ⇒ contrat BT exigé) | D-CIQ-4 (tarifs sourcés) | oui : « Consommation estimée à partir de la facture en dirhams » (`suppositions_ci.py::HYPOTHESES_ESTIMEES`, lu) |
| C&I | `contrat_electricite` | aucun : refus « tarif omis » | D-CIQ-23 | refus nommé |
| C&I | `raccordement` | aucun : refus | ADEV89, aucune décision du fondateur lue | refus nommé |
| C&I | profil commercial | archétype de la catégorie (le plus proche si besoin) | fichier vendorisé, licences vérifiées (`moteur_ci/profils.py`) ; D-CIQ-1 | PDF : « profil type… estimation » (`quote_engine/ci/synthese.py::METHODES`, lu) ; journal : NON — `profil_estime` est de niveau `info` et `_build_devis_auto_ci` ne garde que `alerte`/`bloquant` (lu) |
| C&I | talon de nuit (`equipements_hors_horaires`) | borne conservatrice, ou archétype ; option batterie retenue | 17/11 + « talon par activité » 26-27/10 | oui (`talon_non_declare`, champ nommé) |
| C&I | `compteur_puissance_kva` | non vérifiée | — | oui (`puissance_souscrite_inconnue`) |
| C&I | `surface_toiture_m2` | toit non borné | — | oui (`contenance_toit_inconnue`) |
| C&I | inclinaison / azimut | 30° plein sud | constantes PVGIS | **non sans GPS** : `moteur_ci/production.py::traces_production` pose `statut: source` quand la série horaire manque, et `suppositions_ci.py::alertes_pour_la_commerciale` ne dit que les `estimation` (lu) |
| C&I | type de pose | toit plat lesté (`moteur_ci/composition.py::TYPE_POSE_DEFAUT`) | fondateur 26/10 ; CORC5 « prise pour le fondateur, à revoir » | oui (« pose estimée ») |
| C&I | longueurs de câble | 10 m AC / 30 m DC, plancher 10 mm² | 17/11 | oui (`longueurs_non_relevees`) |
| C&I | `tva_recuperable` | inconnue ⇒ HT et TTC tous deux servis (`economie_ci.py::base_economique`) | D-CIQ-3 | oui |
| Agr. | `mode_pompe` | neuve, étiqueté « par défaut » (`crm/devis_auto.py::mode_pompe_du_lead`) | D-AGQ-10 | oui |
| Agr. | heures de pompage | réglage société `agricole_pump_hours` ou heures-pic PVGIS ; 7 h | CLAUDE.md | probable (non ouvert : `domain/pompage.py`) |

## 3. Arrêts (refus, blocages, devis vides)

1. Garde CRM (409 « Manque : … ») — `crm/devis_auto.py::message_manquants` : voulu (D-ACI-5 pour le C&I, AGR403 pour l'agricole).
2. Résidentiel `localisation_inconnue` (ville/GPS) — `taille.py::_REFUS_DIMENSIONNEMENT` : la garde CRM dit « prêt » alors que le moteur refuse (lu : `champs_requis` résidentiel = `facture_hiver` seule). Défaut manquant.
3. Résidentiel kWh tapé contredit par les factures — `creation_auto_residentiel.py::_build_devis_auto_residentiel` : voulu (règle 30/09, `kwh-declare-vs-factures`).
4. C&I contrat absent / facture MAD sans contrat BT (`MESSAGE_MAD_SANS_CONTRAT`) : voulu (D-CIQ-23).
5. C&I phase absente (`etude_ci.py::refus_devis_auto_ci`, `PHASES_DECLAREES`) : **aucune décision du fondateur lue**.
6. C&I jours/heures (industriel, commercial hammam/autre) : voulu (D-CIQ-1, D-ACI-5, D-ACI-7).
7. C&I postes fixes sans prix (« Prix à renseigner ») : voulu (D-ACI-6) ; dépend du catalogue, pas du lead.
8. C&I visite (D-CIQ-5) : NE bloque pas — devis « estimation sous réserve de visite » (`crm/devis_auto.py::visite_avant_devis`).
9. Agricole HMT, débit, phase (« jamais tri par défaut »), visite du point d'eau (`MESSAGE_RELEVE_POINT_EAU`) : voulus (D-AGQ-5, D-AGQ-1, AGQ7, D-AGR-4) ; la phase est absente de la garde CRM (écart garde/moteur).
10. Tunnel du site : refusé au C&I et à l'agricole (`creation_auto.py::build_devis_auto`) — voulu (D-CIQ-0, D-AGR-1).

## 4. Le calepinage dans ce chemin

- **Reçoit du lead** (lu, `calepinage/services/consommation.py::_profil_depuis_lead`) : `facture_hiver`, `facture_ete`,
  `ete_differente`, `conso_mensuelle_kwh`. **Ne reçoit PAS le profil choisi** : la forme horaire est UNIFORME
  (`::_depuis_profil_mensuel`, `AVIS_FORME_UNIFORME`) là où le devis prend la présence en journée (résidentiel) ou
  l'archétype (commercial) — deux formes pour un même lead.
- **Lead C&I** : la classe tarifaire n'est déduite que pour résidentiel et agricole (`CLASSE_DU_TYPE_INSTALLATION`) ;
  un lead commercial ou industriel est refusé « classe non saisie » (`::_classe_saisie`, lu).
- **Toujours « incomplet » au premier jour** : `chaine_pertes.py::SOCLE_PHYSIQUE` (salissure, mismatch, LID, ohmique DC,
  ohmique AC, qualité module, indisponibilité) ; le profil de départ ne fournit que mismatch (2 %) et qualité module
  (règle du quart), sources PVsyst citées dans `data/profil_depart.json` ; D-ACAL-82 (ouverte) nomme les quatre trous.
- **Conséquence lue sur le devis** : `calepinage/selectors_devis.py` pose `pertes_et_ombrage_inclus = complete` et
  `ventes/horaire/productible_pose.py::base_depuis_servi` rejette un résultat incomplet ⇒ la production de la POSE RÉELLE
  (D-ACAL-36, 44, 46) n'atteint aucun devis tant que D-ACAL-82 n'est pas tranchée ; le devis garde la production de la ville.

## 5. Valeurs par défaut manquantes pour un résultat complet au premier jour

| Poste | Clé | Valeur de référence publiée trouvée dans le dépôt | Sinon |
|---|---|---|---|
| Salissure | `salissure_mensuelle_pct` | aucune (PVsyst : « less than 1% » en climat pluvieux seulement — `profil_depart.json`, `sans_source`) | à donner par le fondateur |
| Dégradation initiale (LID) | `lid_par_techno` | PVsyst : fourchette 1 à 3 %, défaut suggéré 2 % non lié à une techno (`profil_depart.json`, `sans_source`) | valeur unique à confirmer par le fondateur |
| Indisponibilité | `indisponibilite_fenetres` | aucune (PVsyst ne publie pas de défaut) | à donner par le fondateur |
| Pertes de câbles DC/AC | aucune clé (D-ACAL-82) ; calculées seulement si norme choisie + câbles connus (`services/etapes/ohmique_dc.py`) | aucune (PVsyst ≈ 60 % de la fraction STC = rapport, pas un défaut ; OpenSolar 0,1 % = repère micro-onduleur) | à donner par le fondateur |
| Forme horaire du lead | — | celle du moteur du devis (présence / archétype), déjà sourcée | à brancher (tâche T4) |

Repère existant à mettre sous les yeux du fondateur : le devis applique déjà 20 % de pertes totales (« fondateur 18/08 »,
`pricing.py::SYSTEM_LOSS_TOTAL`) — une enveloppe, pas une valeur par poste.

## 6. Tâches proposées (non inscrites)

- **T1 — La garde CRM dit tout ce que le moteur exige, aussi en résidentiel et agricole.** Constat : « prêt » sans ville/GPS
  (résidentiel) ni phase (agricole), refus ensuite. Fichiers : `crm/devis_auto.py::champs_requis`. Fini quand : un lead « prêt »
  ne reçoit jamais `localisation_inconnue` ni `raccordement` du moteur (test dans le module existant). Propriétaire : **lead**.
  Étend le principe de D-ACI-5=a hors C&I : à confirmer.
- **T2 — Le devis automatique résidentiel dit ses suppositions avec le champ.** Constat : journal limité à la taille demandée ;
  bandeau sans champ. Fichiers : `ventes/domain/creation_auto_residentiel.py`, `ventes/courbes_journalieres.py::BANDEAU_PROFIL_SUPPOSE`.
  Fini quand : présence supposée (`occupation_jour`), été = hiver (`facture_ete`), kWh tirés des MAD (`conso_mensuelle_kwh`),
  30° plein sud (`inclinaison_deg`/`orientation`) apparaissent dans `journal_auto['alertes']` avec `champ_lead`. Propriétaire : **devis**.
- **T3 — C&I : deux suppositions tues.** Fichiers : `ventes/moteur_ci/production.py::traces_production` (30° sud sur le repli
  sans GPS dit `estimation`), `ventes/domain/creation_auto.py::_build_devis_auto_ci` (garder `profil_estime`). Fini quand :
  les deux sortent au journal avec leur champ. Propriétaire : **devis**.
- **T4 — Le calepinage prend le profil choisi du CRM.** Fichiers : `calepinage/services/consommation.py::_depuis_lead`,
  `::_classe_saisie` (lecture par `apps.ventes.selectors`/`apps.crm.selectors`). Fini quand : même forme horaire que le devis,
  classe d'un lead C&I déduite de son contrat déclaré (correspondance à valider). Propriétaire : **calepinage**. Lié à C1.
- **T5 — Valeurs de départ des quatre pertes** (GATED D-ACAL-82). Fichier : `calepinage/data/profil_depart.json` (+ clé de
  réglage des câbles). Fini quand : « Démarrage rapide » donne un résultat complet, chaque valeur étiquetée « supposé ». Propriétaire : **calepinage**.
- **T6 — Profil industriel par secteur** (GATED Q3). Fichiers : selon la réponse (`moteur_ci/charge.py` ou saisie Paramètres).
  Propriétaire : **devis**.

## 7. Questions au fondateur (chacune change un chiffre vu par le client)

- **Q1 — Contrat absent (C&I).** D-CIQ-23 refuse ; le 22/11 vous demandez « facture + profil ». (a) garder le refus ;
  (b) supposer le tarif BT de la tension déclarée, dit avec `contrat_electricite`, devis marqué estimation ; (c) refuser
  seulement si la facture est en MAD (les kWh n'ont pas besoin du contrat pour la taille). Recommandé : (b).
- **Q2 — Phase absente (C&I).** Refus sans décision lue. (a) garder ; (b) supposer triphasé pour tout C&I, dit avec
  `raccordement` ; (c) supposer triphasé au-delà d'un seuil que vous donnez. Change les onduleurs du devis.
- **Q3 — Profil industriel.** Aucun archétype sourcé (D-CIQ-1). (a) garder « jours et heures exigés » ; (b) vous saisissez un
  profil par secteur dans Paramètres (déjà lu, D-ACI-7) ; (c) le régime d'équipes choisi suffit, jours ouvrés supposés (à
  donner : lun-ven ou lun-sam), dit. Change taille et autoconsommation.
- **Q4 — Ville non reconnue sans GPS (résidentiel).** (a) refus actuel ; (b) productible de la ville du siège de la société,
  dit avec `ville`. Change la production et la taille.
- **Q5 — D-ACAL-82 (quatre pertes).** (a) vous donnez les quatre valeurs ; (b) valeurs publiées citées (seule trouvée : LID 2 %
  suggéré par PVsyst) et le reste vous ; (c) répartir l'enveloppe de 20 % déjà appliquée au devis ; (d) rester incomplet —
  mais alors la pose réelle n'atteint jamais le devis (section 4). Change la production du rapport et, par D-ACAL-36, du PDF.

## 8. Non couvert

- Écran `/ventes/devis/nouveau` et `solar.js` : seul l'appel serveur `autoQuote.js` → `POST /ventes/devis/auto/` a été vu ;
  l'affichage des alertes du journal à l'écran n'est pas vérifié.
- PDF résidentiel : absence de mention 30° sud établie par recherche de texte, pas par rendu.
- Défauts internes de `ventes/domain/pompage.py` (heures, rendements, plafonds) non lus ; moteur C&I lu en partie (taille, onduleurs non ouverts).
- Données de production : combien de leads ont contrat, phase, ville reconnue — non mesuré (aucune lecture prod).
- Aucun test exécuté ; aucune vérification en direct.
