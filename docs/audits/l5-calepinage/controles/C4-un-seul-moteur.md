# C4 — Un seul moteur dans l'ERP, ses résultats rangés sur le lead (conception, 23/11/2026)

Conception seule : aucun code n'est écrit ici. À construire dans une session neuve (D-ACAL-97). Calibrage : « lu » =
symbole ouvert dans cette session ; « probable » = déduit du nom, d'une docstring voisine ou d'un appelant ; ancres
`fichier::symbole`, chemins relatifs à `backend/django_core/` sauf `frontend/` et `apps/web/`. Fondé sur C1, C2, C3,
`lane-moteur-unique.md` (vague C) et `lanes-vague-D.md` (vague D, en cours, non redemandée ici).

## 1. Le principe en dix lignes

1. « there should be one engine that should be the CRM one » : le moteur est celui que la fiche du lead lance déjà
   par « Devis automatique » — les noyaux de `apps/ventes` (horaire résidentiel, `moteur_ci`, pompage).
2. « one engine calculating every number » : chaque valeur lue par un utilisateur ou un client a UN calcul.
3. « no more then one number for each value » : un écran ne montre jamais deux chiffres pour la même valeur ;
   l'unique exception est l'écart avec un devis ENVOYÉ, nommé, avec « Réviser le devis » (D-ACAL-96).
4. « you keep the most realistic number » : quand le toit est tracé, ses entrées (géométrie, ombre, pose) priment
   sur les valeurs par défaut — même moteur, entrées plus riches.
5. « i dont want calpinage to always take it design from sent quote » : le calepinage lit le moteur, plus le devis.
6. « what if we dont have a sent quote » : sans devis, rien ne change — le moteur tourne sur le lead.
7. « if the engine was used somewhere we just keep its values and use them everywhere » : résultat RANGÉ, relu.
8. « no need to recompute and specially using some other engine » : aucun écran ne recalcule ; les calculs du
   calepinage, de l'écran devis et du navigateur qui doublonnent sont retirés.
9. « should only need the bill and one consumption profil » : toute autre entrée a un défaut, DIT avec son champ.
10. « On the lead », « Recalculate on an input change, and say it », « Design it now, build it in a fresh session ».

## 2. La table des valeurs

Demain, toutes les lignes passent par UN point d'entrée, `apps/ventes/conception/moteur.py::calculer_conception`
(à créer, §3), dont l'étape nommée appelle le noyau GARDÉ indiqué. « Rés. » = résidentiel, « Agr. » = agricole.

| Valeur | Qui la calcule AUJOURD'HUI | DEMAIN (étape → noyau gardé) | Le plus réaliste, et pourquoi |
|---|---|---|---|
| Taille (panneaux, kWc) | Rés. `dimensionnement.py::recommander_taille` (via `domain/taille.py::_panneaux_dimensionnement_horaire`, `domain/pipeline.py::decider_taille`, `selectors.py::cible_depuis_lead`) — lus ; C&I `moteur_ci/taille.py::dimensionner_ci` (lu) ; cible calepinage `domain/lignes.py::cible_depuis_lignes` + `calepinage/services/devis_retenu.py::cible_de_l_option_retenue` (lus), `calepinage/services/cible_couverture.py::plus_petit_nombre_pour_couverture` (lu) ; navigateur `roofPro11/cible.ts::repartirCibleVendue`, `roofPro11/cibleProduction.ts::panneauxPourCible` (lus) ; écran `solar.js::panneauxPourKwc` | étape `taille` → rés. `recommander_taille`, C&I `dimensionner_ci`, agr. `core/pompage/conception.py::conception` (le champ découle de la pompe) | Taille de la facture, bornée par la contenance du toit tracé ; une pose ajustée à la main ou une taille souhaitée est SOUVERAINE (comme `CibleDevis` aujourd'hui) : le moteur ne la redimensionne pas, il calcule tout le reste pour elle |
| Module | Rés. `domain/etape_composer.py::composer` → `domain/composition_residentielle.py::composition_residentielle` (signature lue) ; C&I `moteur_ci/composition.py::composer_ci` (signature lue) ; calepinage `services/electrique.py::resoudre_materiel` (saisie > lignes du devis, C1 lu) | étape `materiel` → mêmes noyaux par marché | Désignation humaine (calepinage ou écran devis) = entrée imposée ; sinon le choix du catalogue |
| Onduleur(s) et nombre | Rés. `solar_design.py::match_inverter` ; C&I `moteur_ci/onduleurs.py::combiner_onduleurs` (lu) ; calepinage `core/electrique/onduleurs.py::dimensionner_onduleurs` ; AO `core/calepinage/electrique.py::dimensionner` (60 kWc) | étape `materiel` → rés. `match_inverter`, C&I `combiner_onduleurs` | La combinaison du moteur ; le plafond AO 60 kWc ne s'applique qu'aux dossiers d'appel d'offres |
| Chaînes et longueur | Rés./devis `electrical_service.py` → `core/electrique/chaines.py::concevoir_chaines` (import lu) ; `solar_design.py::string_design` ; C&I `moteur_ci/chaines_ci.py::concevoir_chaines_ci` ; calepinage `services/chaines.py::concevoir_par_pan` (importe `concevoir_chaines`, lu) ; AO `core/calepinage/electrique.py::chainer` (16) | étape `electrique` → `core/electrique/chaines.py::concevoir_chaines` ; toit tracé : un groupe par pan via `concevoir_par_pan` (adaptateur du document) ; sinon un groupe virtuel | Par pan réel quand le toit est tracé (orientations et nombres réels) |
| Tension à froid | Rés./C&I `core/electrique/types.py::TEMP_FROID_DEFAUT_C` (−5 °C, C1) ; calepinage `services/electrique.py::temperatures_site` (saisie > TMY > −5) | étape `electrique` → la politique UNIQUE de `core/electrique/` posée par ADEV122/ACAL1553 (vague D, nom choisi par elle) | Minimum de l'année type du lieu (D-ACAL-80) ; sans lieu, −5 °C, dit |
| Rapport panneaux / onduleur | `core/electrique/onduleurs.py::bornes_dc_ac` (1,35), `::SEUIL_ALERTE_DC_AC` (1,5), `::BORNES_RATIO_AC_DC` ; `solar_design.py::MAX_DC_AC` ; `domain/composition_imposee.py::RATIO_DC_AC` ; C&I `moteur_ci/onduleurs.py::_capacite_kwc` (D-HYB-1) ; calepinage `services/ratio_devis.py::juger_ratio` (lu) ; AO `core/calepinage/electrique.py::BORNES_RATIO_AC_DC` | étape `electrique` → `core/electrique/onduleurs.py::ratios` + `::capacite_publiee_hybride` (lus en signature) ; verdict servi, jamais rejugé | Règle du devis (D-ACAL-91) ; hybride à sa capacité publiée (D-HYB-1) |
| Production annuelle et mensuelle | Rés. `etude_horaire.py::calculer_etude_horaire` (signature lue ; base `horaire/productible_pose.py::base_de_production`, lu) ; C&I `moteur_ci/production.py::bloc_production_ci` ; calepinage `services/simulation.py::simuler_calepinage` (lu) ; écran `solar.js::productibleForCity` + `calc/roi.js::computeROI` (lus) ; navigateur `result.annualKwh` (C1) | étape `production` → toit tracé et pose complète : `calepinage/services/simulation.py::simuler_calepinage` appelé PAR le moteur ; sinon le chemin actuel par marché (§9 Q1 : converger sur la même simulation, plan par défaut) | La simulation de la pose (PVGIS horaire par pan, cascade de pertes D-ACAL-82, ombre sur les panneaux posés D-ACAL-83, chaleur par pose D-ACAL-84) |
| Autoconsommation, couverture | Rés. `calculer_etude_horaire` ; C&I `moteur_ci/autoconso.py::bilan_horaire` ; calepinage `services/autoconsommation.py::bilan_autoconsommation` ; `solar_design.py::hourly_self_consumption` ; `quote_engine/pricing.py::autoconso_avec_ratio` ; écran `calc/roi.js::computeROI` | étape `bilan` → rés. `calculer_etude_horaire`, C&I `bilan_horaire` | Bilan heure par heure sur la forme du profil choisi et la production retenue ci-dessus |
| Économies | Rés. bloc `etude_horaire` + `quote_engine/pricing.py` ; C&I `economie_ci.py::valoriser` (signature lue) ; navigateur `lib/estimatorBrainV2.ts::annualSavingsMad` (lu en signature) ; écran `calc/roi.js::computeROI` | étape `economie` → rés. bloc horaire, C&I `valoriser` | Barème de la société appliqué au bilan horaire |
| Payback | `dimensionnement.py::_payback` (balayage) ; `quote_engine/pricing.py::compute_cashflow_payback`, `::payback_publiable` ; écran `calc/roi.js::paybackMoteurHoraire` ; C&I dans `economie_ci.py` (probable) | étape `economie` → `pricing.py::payback_publiable` (probable : le nom dit « publiable » ; à confirmer à l'étape 2) avec l'investissement en ENTRÉE | Prix du devis de référence du lead quand il existe (le plus réel), sinon prix catalogue de la composition ; la source est dite (« au prix du devis DEV-… ») |
| Consommation et forme horaire | Rés. `horaire/conso.py::profil_depuis_factures` + `courbes_journalieres.py::occupation_du_lead` (présence par défaut, lus) ; C&I `domain/etude_ci.py::_consommation`, `moteur_ci/charge.py`, `moteur_ci/profils.py::forme_archetype` ; calepinage `services/consommation.py::_profil_depuis_lead`, `::_depuis_profil_mensuel` (forme UNIFORME, C2) ; écran `solar.js::estimerMois`, `calc/tarifs.js::consoAnnuelleDepuisFactures` | étape `consommation` → rés. `profil_depuis_factures` + `occupation_du_lead` ; C&I `_consommation` + charge | La facture et le profil choisi au CRM (présence, archétype, régime d'équipes) ; une courbe mesurée prime (C&I `courbe_mesuree` déjà lue) |
| Pompage : pompe, variateur, m³/jour | `domain/pompage.py::etudier_pompage` (signature lue) sur `core/pompage/selection.py::selection_pompe`, `::selection_variateur`, `core/pompage/volumes.py::production_mensuelle` ; calepinage `services/pompage.py::volumes_mensuels` (mêmes noyaux, lu) ; navigateur `lib/estimatorAgricole.ts` (probable) | étape `pompage` → `etudier_pompage` | Débit sur la courbe de la pompe ; m³/jour jamais calculé sans courbe (D-AMOT-7) |
| Suppositions | Rés. `courbes_journalieres.py::BANDEAU_PROFIL_SUPPOSE` (sans champ, lu) ; C&I `domain/suppositions_ci.py` ; calepinage `services/suppositions.py` (importe `MODULES_PAR_CHAINE`, lu) | sortie `suppositions` du moteur, une liste `{code, champ, valeur, source, message}` | Règle du 17/11 : tout défaut est dit avec le champ de la fiche |

## 3. Le moteur unique

**Où.** Un paquet neuf `apps/ventes/conception/` (propriétaire `devis` selon `check_ownership.py`). Pourquoi
`ventes` : les trois noyaux par marché, la composition au catalogue, les barèmes et les économies y vivent déjà ;
le calepinage lit déjà `ventes` par sélecteurs (`selectors.py::cible_depuis_lead`, `selectors_calepinage.py`,
`domain/chiffrage_conception.py::chiffrer_conception`), le CRM aussi (`crm/roof_selectors.py` → `conception_pour_lead`).
Pas `core/` : il faut lire le lead, le catalogue et les réglages, et `core` n'importe aucune app. Pas `crm` : le CRM
n'a aucun noyau de calcul et grossirait de tout le moteur. Import-linter (lu) : seule l'indépendance des modules
`*.models` entre `crm`, `ventes`, `stock`, `sav`, `installations`, `visites` est verrouillée, plus
`calepinage.models` → aucun modèle métier ; un modèle `ventes` avec une clé étrangère en chaîne `'crm.Lead'` le
respecte. Les règles pures partagées restent dans `core/electrique/` et `core/pompage/`.

**Point d'entrée unique, sans écriture** :

```python
calculer_conception(lead, company, *, entrees=None, toit=None, imposes=None, investissement=None) -> ResultatConception
# entrees  : EntreesConception déjà lues (sinon lues ici par l'adaptateur unique)
# toit     : PoseServie | None — lue par apps.calepinage.selectors (calepinage ouvert du lead, variante retenue)
# imposes  : {nb_panneaux?, module_id?, onduleur_id?, nombre_onduleurs?, batterie?} posés par un humain
# sortie   : {etat: complet|refus, refus?: {code, champ, message}, marche, options: {sans, avec?},
#             option_retenue, valeurs (table §2 par option), blocs (etude_horaire / etude_ci / etude_pompage /
#             dimensionnement, forme ACTUELLE des clés du devis), suppositions, entrees_utilisees, empreinte,
#             niveau_regles, version_moteur}
```

Étapes, dans l'ordre : `entrees` → `consommation` → `taille` → `materiel` → `electrique` → `production` → `bilan`
→ `economie` (→ `pompage` au lieu de `taille`/`materiel`/`bilan` en agricole). L'ordre est celui de
`domain/pipeline.py::ETAPES` (lu) sans l'écriture de lignes.

**Ce qu'il compose.** Entrées : `domain/entrees.py::EntreesMoteur` + `::entrees_depuis_lead` + `::empreinte_entrees`
(lus — déjà « l'adaptateur unique lead → moteur », avec empreinte et `VERSION_MOTEUR_ENTREES`), `etude_ci.py::
resoudre_entrees` (C&I, `CHEMINS_LEAD` lu), `domain/pompage.py::resoudre_entrees` ; réunis dans un
`EntreesConception`. Calculs : les noyaux gardés de la table §2. Production avec toit : `simuler_calepinage`
(cascade de pertes D-ACAL-82, ombre D-ACAL-83, P90 D-ACAL-85), appelé par une façade de `apps/calepinage/services`.
Règles : `core/electrique/onduleurs.py::capacite_publiee_hybride` (D-HYB-1), politique de froid (vague D).

**Ce qui cesse d'exister** (détail §7) : tout calcul d'une valeur de la table hors du moteur — le second bilan et
la lecture de facture du calepinage, son dimensionnement d'onduleurs et ses constantes d'AO hors AO, les maths
locales de l'écran devis (`solar.js`, `calc/roi.js`), les estimations de production et d'économies du navigateur
en mode ERP, `domain/chiffrage_conception.py` (devient une lecture du résultat rangé), et le rôle de
`selectors_calepinage.py::conception_retenue_du_devis` comme SOURCE de conception du calepinage.

**Ce que devient la vague C.** ACAL1950 (`conception_retenue_du_devis`) est GARDÉ, comme lecteur d'un devis FIGÉ :
il sert la comparaison « devis envoyé ↔ conception courante ». ACAL1951 (cible), ACAL1952 (matériel), ACAL1953
(longueur de chaîne) et ACAL1956 (Résultats) sont GÉNÉRALISÉS : leur source devient la conception courante du lead ;
le devis envoyé n'y est plus qu'une comparaison. ACAL1954 (`services/ratio_devis.py`, D-HYB-1 dans `core`) est GARDÉ
tel quel (le moteur et le calepinage partagent la règle). ACAL1955 (re-liaison à l'envoi) est GARDÉ (les documents
du calepinage suivent le devis envoyé). ALEA67 est GÉNÉRALISÉ : la garde du CRM lit la liste des manques du moteur
(une règle). Vague D : ADEV121/122 et ACAL1553 posent des règles dans `core` — gardées ; ACAL1967 (forme du profil
lue par le calepinage) et ACAL1987 (simulation à l'enregistrement) deviennent transitoires : l'étape 6 les remplace
par « la pose est une entrée du moteur ».

## 4. Le résultat rangé sur le lead

Modèle `ConceptionLead` dans `apps/ventes/models_conception.py` (à créer ; module voisin de `models_coherence.py`,
`models_preuves.py`, enregistrement dans `models.py` probable comme eux).

| Champ | Type | Rôle |
|---|---|---|
| `company` | FK société | multi-société ; forcé côté serveur, jamais lu d'un corps |
| `lead` | FK `'crm.Lead'` (chaîne), `CASCADE`, nullable (§9 Q3, décidée le 23/11) | le porteur |
| `calepinage_id` | entier nullable | porteur quand il n'y a pas de lead (Q3, décidée : « On the calepinage itself ») et calepinage dont la pose a servi |
| `version` | entier | par porteur, plus haut utilisé + 1 sous point de sauvegarde (jamais `count()+1`) |
| `courante` | booléen | une seule courante par porteur (contrainte unique conditionnelle) |
| `etat` / `refus` | texte / JSON | `complet` ou `refus` nommé `{code, champ, message}` (ex. `localisation_inconnue`) |
| `marche`, `option_retenue` | texte | `residentiel|commercial|industriel|agricole` ; `sans|avec` |
| `valeurs` | JSON | la table §2 par option, chaque valeur `{valeur, unite, source}` |
| `blocs` | JSON | les blocs d'étude dans la forme ACTUELLE des clés du devis (`etude_horaire`, `etude_horaire_sans`, `etude_ci`, `etude_pompage`, `dimensionnement`) — copiés tels quels dans `Devis.etude_params` |
| `entrees_utilisees` | JSON | entrées résolues avec provenance (`lead`, `calepinage`, `réglage société`, `défaut`) |
| `suppositions` | JSON | `[{code, champ, valeur, source, message}]` |
| `empreinte` | texte 64 | hash des entrées + `version_moteur` + `niveau_regles` + empreinte de la pose |
| `empreinte_pose` | texte 64 | empreinte de la pose utilisée (`Calepinage.layout_hash` probable) |
| `niveau_regles`, `version_moteur` | entier, texte | `domain/regles_calcul.py::REGLES_COURANTES` (lu : 14 ; le 15 est déclaré, pas courant) |
| `declencheur` | JSON | `{raison, champs: [{champ, avant, apres}], origine}` — la phrase « pourquoi » |
| `calcule_le`, `calcule_par` | horodatage, FK utilisateur nullable | auteur ; `None` = tâche du moteur |

Interdits dans `valeurs`/`blocs` : `prix_achat`, marge (parcours récursif, comme `etude_ci.py::CLES_INTERDITES`, lu).

**Historique.** Une nouvelle version passe l'ancienne à `courante=False` ; rien n'est supprimé (le journal se lit par
version, diff des `entrees_utilisees`). Une ligne au chatter du lead (`crm.LeadActivity`, par un service de `crm`).

**Écrivain unique** : `apps/ventes/conception/service.py::relancer(lead, *, company, declencheur, auteur=None,
forcer=False)` — calcule, compare l'empreinte (égale ⇒ rien, sauf `forcer`), écrit la version, émet
`core/events` `conception_recalculee`. **Lecteurs** : `apps/ventes/selectors_conception.py` (à créer, ré-exporté par
`selectors.py`) — `conception_courante(company, lead_id)`, `historique_conception(...)`, `manques_du_moteur(lead)`,
`ecart_devis(devis)` ; la vue `GET /api/django/ventes/conception/<lead_id>/` et le contrat
`apps/ventes/contract_samples/conception_lead.json`.

**Avec le devis.** À la création, le devis REÇOIT la conception : taille et matériel en `CibleDevis` imposée
(`pipeline.py::CibleDevis`, lu), blocs copiés dans `etude_params`, pointeur `etude_params['conception'] = {id,
version, empreinte}`. Les quatre études du devis voient des blocs « à jour » parce que l'empreinte est la même
(mécanisme QJR43 de `domain/etudes.py`, lu en signature) : aucun recalcul. À l'envoi rien ne change : `etude_params`
et `electrical_design` restent ce que le devis a FIGÉ (règle du 08/10, niveaux de règles). Le PDF `/proposal` lit
toujours le devis (règle n° 4 : il ne fait que rendre). **Avec le calepinage.** `Calepinage.resultat` garde le
DÉTAIL technique de la simulation (cascade, diagrammes, par pan) écrit par le même passage du moteur ; une valeur
affichée vient toujours de `ConceptionLead.valeurs`, le détail est montré seulement si son `hash_entree` est celui
que la version courante a utilisé.

## 5. Quand il recalcule

**Relance** (une fois par changement, tâche dédupliquée par `(porteur, empreinte)` dans la file existante —
`core/jobs.py` probable) quand change une entrée lue par les adaptateurs :
- consommation : facture d'hiver, facture d'été, « été différent », kWh mensuels déclarés, relevé de factures,
  tranche déclarée, courbe mesurée ;
- profil : présence en journée et les équipements du lead (`crm.selectors.equipements_pour_lead`) ; C&I catégorie
  commerciale et réponses, secteur industriel, jours ouverts, plages, régime d'équipes, début d'équipe, fermetures,
  talon de nuit ;
- lieu : ville, GPS, épingle du toit ; marché (`type_installation`) ; contrat d'électricité, tension, puissance
  souscrite, raccordement (phase, « aucun » = isolé) ; TVA récupérable ;
- souhaits : batterie souhaitée, puissance souhaitée ; toit déclaré (surface utile, couverture, pente, azimut) ;
- pompage : HMT, débit souhaité ou besoin m³/j, mois d'irrigation, mode de pompe, relevé du point d'eau ;
- toit tracé (calepinage ouvert du lead) : contenance, géométrie des pans, obstacles et ombre, pose (nombre et
  place des panneaux, pose ajustée à la main), réglages de pertes du calepinage ;
- matériel imposé (désignation du calepinage ou de l'écran devis) ; catalogue et réglages société qui entrent dans
  l'empreinte (barème, profils société, prix) ; `niveau_regles` ou `version_moteur` qui montent.
La liste exacte des colonnes est posée au contrat (étape 1) et gardée par un test : un adaptateur qui lit un champ
absent de la liste est rouge.

**Ne relance PAS** : nom, téléphone, notes, étape du pipeline, propriétaire, relances, tags ; le prix négocié, la
remise ou le texte d'un devis (le payback les lit en entrée au moment de l'affichage, sans relancer le moteur) ;
ouvrir un écran ; un enregistrement du calepinage sans changement d'empreinte (ACAL1407 / ACAL1987 : déjà vrai
pour la simulation).

**Comment c'est dit.** Chaque lecteur reçoit `declencheur` et `calcule_le` : « Recalculé le 23/11 à 14 h 05 :
facture d'hiver 900 → 1 200 MAD ». Pendant le calcul : valeurs de la version courante + « Recalcul en cours —
facture d'hiver modifiée ». En lecture, une empreinte des entrées différente de la version courante (filet de
sécurité si un événement a été manqué) relance la tâche et affiche le même bandeau.

**Devis envoyé (D-ACAL-96).** Jamais touché. Si `ecart_devis(devis)` trouve une valeur différente, la fiche du lead,
le calepinage et l'écran du devis disent les deux chiffres, chacun nommé, et proposent « Réviser le devis »
(`domain/revision.py`, existant). Brouillon : §9 Q2.

## 6. Les lecteurs

| Lecteur | Ce qu'il lit demain | Le calcul local qu'il perd |
|---|---|---|
| Fiche du lead (`frontend/src/pages/crm/leads/LeadDetailPage.jsx`, `features/crm/workspace/LeadWorkspace.jsx`) | carte « Conception » : taille, production, économies, payback, suppositions, historique | `crm/roof_selectors.py` → `conception_pour_lead` (kWc lu sur le dernier devis ou le calepinage) devient un sélecteur de la conception |
| Bouton « Devis automatique » (`crm/devis_auto.py::champs_requis`, `domain/creation_auto.py::build_devis_auto`) | garde = `manques_du_moteur(lead)` ; création = conception courante | la garde recopiée (ALEA67) et le dimensionnement dans `build_devis_auto` |
| Création de devis (`domain/pipeline.py::appliquer`, cinq origines) | `IntentionDevis.cible` + composition imposée + blocs de la conception | `decider_taille` sur le lead et les études du premier passage |
| Écran `/ventes/devis/nouveau` (`frontend/src/pages/ventes/DevisGenerator.jsx`) | conception servie ; aperçu d'une saisie non enregistrée par `calculer_conception` sans écriture | `calc/roi.js::computeROI`, `solar.js::productibleForCity`, `EFFICIENCY`, `GHI`, `KWH_PRICE` |
| PDF `/proposal` | inchangé : le devis | rien (règle n° 4) |
| Calepinage — cible, matériel, contrôles, Résultats, documents, rapport d'étude | `conception_courante` du lead (+ `ecart_devis` du devis lié envoyé) | `cible_depuis_lignes`/`cible_de_l_option_retenue` comme source, `resoudre_materiel` sur les lignes du devis, `consommation.py::_profil_depuis_lead`, `autoconsommation.py` sur le chemin lead, `core/calepinage/electrique.py` hors AO |
| Atelier dans le navigateur (`apps/web/src/scripts/roofPro11/`) | en mode ERP : valeurs servies (`affichageErp.ts::serviNb`, lu) ; panneaux et kWc posés = géométrie, gardés | production et économies locales (`estimatorBrainV2.ts::annualSavingsMad`, `result.annualKwh`) masquées en ERP ; gardées sur le site public (pas de lead) ; hors ligne : « valeurs du dernier calcul, hors ligne » |
| « Montrer au client » (`frontend/src/features/calepinage/atelier/coque/BarreProjet.jsx`) | la conception courante (complète par défauts dits — D-ACAL-82, D-ACAL-88) | toute estimation propre |
| Assistant (`apps/ventes/agent_actions.py` `creer_auto`, `apps/calepinage/agent_actions.py`) | sélecteurs de la conception | rien de neuf : il passe par les mêmes services |

## 7. Ce qui est retiré, dans l'ordre

1. Après l'étape 4 (devis créé depuis la conception, parité prouvée) : le dimensionnement de
   `domain/creation_auto*.py` ; `domain/chiffrage_conception.py` devient un lecteur de `ConceptionLead`.
2. Après l'étape 5 : dans `apps/calepinage`, la lecture des lignes du devis comme source (`services/electrique.py::
   _produits_du_devis`, `services/devis_retenu.py::cible_de_l_option_retenue`), `services/consommation.py::
   _profil_depuis_lead` et `::_depuis_profil_mensuel` sur le chemin lead (la saisie CSV / appareils devient une
   entrée du lead, `releve_conso` probable), `services/autoconsommation.py` sur le chemin lead,
   `services/cible_couverture.py` (lit le bilan rangé). `core/calepinage/electrique.py` (`MODULES_PAR_CHAINE`,
   `PLAFOND_DC_PAR_ONDULEUR_KWC`, `BORNES_RATIO_AC_DC`) n'est plus importé que par les dossiers AO :
   `services/suppositions.py` et `services/electrique.py` cessent de le lire pour un calepinage de lead.
3. Après l'étape 7 : `solar.js` (`PRODUCTIBLE_PAR_VILLE`, `DEFAULT_PRODUCTIBLE`, `EFFICIENCY`, `GHI`, `KWH_PRICE`,
   `SYSTEM_LOSS_TOTAL`, `PVGIS_BUILTIN_LOSS`, `PRODUCTIBLE_NET_FACTOR`, `estimerMois`) et `calc/roi.js::computeROI`,
   `::paybackMoteurHoraire` ; les tables miroir côté serveur qu'ils doublaient restent (elles sont dans le moteur).
4. Après l'étape 7 : estimations du navigateur en mode ERP (`optimizer.ts::economieAffichee` probable).
5. Après l'étape 8 : `solar_design.py::hourly_self_consumption` et `pricing.py::autoconso_avec_ratio` si plus aucun
   appelant (grep à l'étape) ; une garde `scripts/check_moteur_unique.py` interdit tout nouvel appel des noyaux
   hors de `apps/ventes/conception/` et des fichiers listés.

## 8. Le chemin

| # | Livre | Preuve | Taille | Risque | Débloque |
|---|---|---|---|---|---|
| 1 | CONTRAT seul sur `main` : `conception_lead.json`, forme des événements, liste des champs d'entrée | `check_api_shapes.py` vert ; contrat relu | 3 | faible | tout (PACT10) |
| 2 | Modèle `ConceptionLead` (migration additive), `calculer_conception` qui APPELLE les noyaux tels quels, écrivain `relancer`, sélecteurs ; aucun lecteur branché | PARITÉ : pour les leads des goldens, les blocs rangés = ceux qu'écrit `build_devis_auto` aujourd'hui | 8 | moyen (forme des blocs) | 3, 4 |
| 3 | Déclencheurs : `lead_entrees_modifiees` (crm), `pose_enregistree` (calepinage), file dédupliquée, filet d'empreinte, historique + phrase « pourquoi » ; commande de remplissage (liste d'abord, `--appliquer` ensuite) | test : changer la facture crée UNE version ; changer le nom aucune ; remplissage listé | 6 | moyen (tempêtes d'événements à l'import) | 4, 5, 7 |
| 4 | Devis automatique et création de devis lisent la conception ; pointeur `etude_params.conception` ; garde CRM = manques du moteur ; un brouillon que personne n'a retouché suit seul la nouvelle conception et le dit, un brouillon retouché garde ses valeurs et propose « Mettre à jour » (Q2, décidée le 23/11) | PARITÉ : 104 goldens `tests/golden/moteur/build_quote_data` + `split_dm_auto*` identiques ; aucun devis envoyé modifié | 7 | élevé (règle n° 4, chemins de création) | 5, 7 |
| 5 | Calepinage lit la conception (généralise la vague C) ; devis lié envoyé = comparaison + « Réviser » | tests des trois états (sans devis, brouillon, envoyé) ; lead 1742 rejoué : 35 panneaux, Huawei, plus d'écart 16 | 6 | moyen | 6, 8 |
| 6 | La pose est une entrée : le moteur appelle la simulation de la pose ; pose ajustée souveraine ; niveau 15 rendu courant après la liste d'ACAL1000 lue par le fondateur (ACAL1001) | dry-run des écarts de production des brouillons ; un enregistrement de pose = une version | 5 | élevé (chiffre client) | 8, 9 |
| 7 | Écrans : fiche du lead, `/ventes/devis/nouveau`, atelier ERP, « Montrer au client » lisent la conception ; aperçu sans écriture ; pendant le dessin, avant l'enregistrement, l'atelier ne montre que les panneaux et le kWc posés, la production arrive du moteur à l'enregistrement (Q4, décidée le 23/11) | tests de rendu ; acceptation en direct (règle 3-bis) | 6 | moyen | 8 |
| 8 | Retraits §7 + garde `check_moteur_unique.py` | garde verte ; suites `apps.calepinage`, `apps.ventes`, `apps.crm` | 5 | moyen | — |
| 9 | (Q1, décidée le 23/11 : « Same simulation, default roof ») Production sans toit = même simulation sur un toit supposé (30° plein sud ou pente déclarée du lead) | liste des écarts montrée au fondateur AVANT la bascule | 2 | élevé | — |

## 9. Risques, et réponses du fondateur du 23/11/2026

Risques : coût d'un calcul (H3 lu : ~1,9 s et ~28 requêtes pour une taille résidentielle ; appels PVGIS) ⇒ calcul en
tâche, jamais dans la requête de l'écran ; import de leads en masse ⇒ déduplication et regroupement ; fichiers de plus
de 2 000 lignes (`etude_ci.py`, `pipeline.py`) à ne pas grossir ⇒ paquet neuf ; cycle d'appels `ventes` ↔
`calepinage` ⇒ imports locaux, comme aujourd'hui ; un devis envoyé qui bougerait ⇒ test de non-modification à
chaque étape ; `prix_achat` ⇒ parcours interdit sur `valeurs`.

- **Q1 — Production sans toit tracé.** Aujourd'hui : enveloppe de 20 % (résidentiel, `pricing.py::SYSTEM_LOSS_TOTAL`)
  ou jours types PVGIS (C&I). (a) même simulation que la pose, sur un plan par défaut (30° sud ou pente du lead) avec
  les pertes D-ACAL-82 ; (b) garder le chemin actuel sans toit. **Réponse du fondateur : « Same simulation, default
  roof »** — la même simulation horaire que pour un toit tracé, sur un toit supposé (30° plein sud, ou la pente déclarée
  du lead) avec les quatre pertes ; la production des NOUVEAUX devis change ; la liste des écarts lui est montrée AVANT
  la bascule (étape 9).
- **Q2 — Brouillon de devis quand la conception change.** (a) mis à jour seul s'il n'a pas été retouché à la main,
  « Mettre à jour » proposé sinon ; (b) toujours proposé ; (c) toujours seul. **Réponse du fondateur : « Update unless
  hand-edited »** — un brouillon que personne n'a retouché suit la nouvelle conception de lui-même, et le dit ; un
  brouillon retouché garde ses valeurs et propose « Mettre à jour » (étape 4).
- **Q3 — Calepinage sans lead** (dossier d'appel d'offres, client seul). (a) même table, porteur = calepinage ; (b) un
  lead obligatoire. **Réponse du fondateur : « On the calepinage itself »** — même résultat rangé, porté par le
  calepinage ; les dossiers d'appel d'offres gardent leurs règles de cahier des charges (16 modules par chaîne, 60 kWc
  par onduleur) hors du moteur (modèle, §4).
- **Q4 — Pendant le dessin, avant enregistrement.** (a) l'atelier ERP montre panneaux et kWc posés, la production
  arrive du moteur à l'enregistrement ; (b) une estimation locale nommée « estimation de l'atelier ». **Réponse du
  fondateur : « Panels and kWc only »** — l'atelier montre le nombre de panneaux et le kWc posés ; la production arrive
  du moteur dès l'enregistrement (la simulation part seule) (étape 7).

## 10. Ce que je n'ai pas lu

Corps de `simuler_calepinage`, `construire_contexte` (la faisabilité d'un plan virtuel est « probable ») ;
`composition_residentielle`, `match_inverter`, `combiner_onduleurs` au-delà des signatures ; `economie_ci.py` (payback
C&I) ; `domain/etudes.py` au-delà des signatures (mécanisme d'empreinte des blocs) ; `core/jobs.py` ; forme de
`Devis.electrical_design` ; `crm.selectors.entrees_ci_du_lead`, `equipements_pour_lead`, `entrees_pompage_du_lead`
(colonnes exactes) ; `Lead.save` et les points d'écriture du lead (où émettre l'événement) ; `estimatorBrainV6/7/8`,
`consumption.ts`, `estimatorAgricole.ts` ; `regles_calcul` niveaux 1-12 ; écrans React au-delà des chemins ; aucune
mesure de production, aucun test lancé.
