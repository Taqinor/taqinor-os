# Fiche d'invariant — classe `K-ANNEE-MOYENNE` (en météo pluriannuelle, « par an » veut dire une année moyenne)

- **Invariant** : « Quand la société simule sur une fenêtre de N années (`production.total.annees_fenetre = N`), toute
  grandeur publiée comme annuelle — énergie (`*_kwh`), compte d'heures (`heures*`), profil mensuel — est la MOYENNE d'une
  année (somme ÷ N) ; une série qui n'est plus horaire (agrégée au jour au-delà de 366 jours) le DIT partout où elle est
  lue (export, carte, fonction qui exige l'heure) et dit le geste qui la rend horaire. En année type (N = 1), rien ne change. »
- **Née de** (tour 2, lot C) : T2-F2-CONSO-012 et T2-F2-RESU-b-011 (consommation 17 530 kWh/an pour 1 752 ; 121 976,8 kWh au
  rapport pour 12 197,68), T2-F2-CONSO-007 et T2-F2-RESU-b-001 (74 649 h et 79 919 h « sans import » pour une année de 8 760 h),
  reprise d'ACAL736 (`energie_ecretee_kwh` = 10 × la perte), reprise d'ACAL781, ACAL832 (« contredit ») ; branche « série
  agrégée au jour » : T2-F2-SIMU-a-008, T2-F2-RESU-019, T2-F2-RESU-b-015, T2-F2-SIMU-b-003, T2-F2-CONSO-015. Antécédent : ACAL54
  (P50 dix fois trop grand, corrigé) puis R3-01 / R3-17 (`annee_moyenne.py`, liste FERMÉE de clés) — chaque correction s'est
  faite clé par clé, sans garde de couverture : c'est la racine commune.
- **Où il peut être violé** — greps lancés le 23/11 sur la tête `f2f2348ec` :
  - `git grep -n -E "_par_an\(|annees_de_la_fenetre|publier_a_l_annee_moyenne|CLES_ENERGIE_CASCADE" -- backend/django_core/apps/calepinage/services`
    (les endroits qui divisent) ; `git grep -n -E "'heures_[a-z_]+'|'total_kwh'|kwh_an|profil_mensuel" -- backend/django_core/apps/calepinage/services`
    (les grandeurs annuelles publiées) ; `git grep -n "tronquee\|JOURS_MAX_SERIE_PERSISTEE\|agrégée au jour" -- backend/django_core/apps/calepinage frontend/src/features/calepinage`.

  | Endroit | Viole aujourd'hui ? | Couvert par la garde ? |
  |---|---|---|
  | `services/courbe_charge.py::construire_courbe_charge` (`total_kwh`, `charges[].kwh_an`, `kwh_hors_production_an`, `profil_mensuel`, `total_base_kwh`, `total_charges_kwh`) | oui, lue (CONSO-012, RESU-b-011) | non — ACAL1603 |
  | `services/rapport/consommation.py` (lit `total_kwh`, `profil_mensuel`) | oui, par sa source | non — corrigé par ACAL1603 |
  | `services/etapes/batterie.py::autonomie` → `heures_sans_import` (publié par `etapes/autoconsommation.py` et `etapes/batterie.py`) | oui, lue (CONSO-007, RESU-b-001) | non — ACAL1604 |
  | `services/etapes/hors_reseau.py::_publier` (`heures_defaillantes`, heures des `par_mois` : seules les clés `_kwh` sont divisées) | probable | non — ACAL1604 |
  | `services/etapes/autoconsommation.py::appliquer` (`heures_ecretees` du plafond et de ses plages) | probable | non — ACAL1604 |
  | `services/annee_moyenne.py::publier_a_l_annee_moyenne` (`energie_ecretee_kwh` de l'histogramme d'onduleur hors de `CLES_ENERGIE_CASCADE`) | oui, lue (ACAL736) | non — ACAL1605 |
  | `services/export_csv.py::_export_horaire` (série déjà agrégée exportée au pas « heure » sans ligne « Pas de temps ») | oui, lue (RESU-019, SIMU-a-008) | non — ACAL1614 |
  | `frontend/.../production/serieHoraire.js::lireCsvHoraire` (`tronquee: null` : le motif ne s'affiche pas) | probable (RESU-b-015) | non — ACAL1664 |
  | `services/cible_couverture.py::lire_socle` (409 sans le geste) | oui, lue (SIMU-b-003) | non — ACAL1628 |
  | `tasks.py::balayer_calepinage` + `atelier/PanneauOptimiser.jsx` (refus en clé brute, exception nue) | oui, lue (CONSO-015) | non — ACAL1629 |
  | `etapes/autoconsommation.py` énergies, `etapes/hors_reseau.py` énergies et `_groupe_par_an`, `etapes/batterie.py` totaux, P50 / mensuel / par pan (`chaine_pertes.py::_bloc_production`), production par module (`simulation_modules.py`) | non (tiennent) | non — ACAL1670 les fige |
- **Matrice champ × condition** :
  | Grandeur publiée | année type (N = 1) | fenêtre 2 ans | fenêtre 2014-2023 (N = 10) | avec batterie | hors réseau | rapport d'étude | export CSV |
  |---|---|---|---|---|---|---|---|
  | consommation annuelle et mensuelle | tient | casse (probable) | casse (CONSO-012, RESU-b-011) | casse | casse | casse (RESU-b-011) | n/a — non exportée |
  | énergie d'une charge à venir (`kwh_an`) | tient | casse (probable) | casse (CONSO-012) | casse | casse | casse | n/a |
  | heures sans import | tient | casse (probable) | casse (CONSO-007, RESU-b-001) | casse | n/a | ? | n/a |
  | heures défaillantes, heures mensuelles hors réseau | tient | ? | probable | n/a | probable | ? | n/a |
  | heures écrêtées du plafond | tient | ? | probable | ? | n/a | ? | n/a |
  | énergie écrêtée par l'onduleur (histogramme) | tient | ? | casse (ACAL736) | ? | ? | ? | n/a |
  | énergies d'autoconsommation, batterie, hors réseau, P50, mensuel, par pan | tient | tient | tient | tient | tient | tient | tient |
  | pas de la série (horaire / jour) dit | tient | casse (pas dit) | casse (RESU-019, RESU-b-015) | casse (ACAL447 : motif dit, ok) | ? | n/a | casse (SIMU-a-008) |
  | fonction qui exige l'heure (objectif de couverture, Optimiser) | tient | casse (409 muet) | casse (SIMU-b-003, CONSO-015) | n/a | n/a | n/a | n/a |
- **Garde** (UNE, famille existante) : test d'invariant dans `backend/django_core/apps/calepinage/tests/test_acal_annee_moyenne.py`
  (tâche ACAL1670) : une série de DEUX années identiques ; pour chaque grandeur annuelle publiée (liste dérivée en parcourant le
  résultat : toute clé `*_kwh`, `heures*`, `kwh_an`, `profil_mensuel[].kwh`), la valeur égale celle de la série d'une année, à
  l'arrondi ; une clé neuve non ramenée échoue. Écrite après ACAL1603-1605 et ACAL1623, rouge attendue sur `f2f2348ec`
  (consommation, heures) — NON exécutée ici (aucune commande de test lancée par la consolidation).
- **Cible du tour suivant** : oui — relecteurs de production : société en « pluriannuel » ET en année type, lire chaque tuile
  « par an » (≤ 8 760 h, consommation ≈ facture annuelle) et chaque export.
- **Propriétaire** : calepinage (`backend/django_core/apps/calepinage/services`, `frontend/src/features/calepinage/production`).
- **Ce qu'elle ne couvre pas** : la justesse d'une année ; le CHOIX de persister une année horaire de la fenêtre (§ 3 de `lot-C.md`).
- **Question de sortie** : « le système l'attraperait-il tout seul la prochaine fois ? » — non aujourd'hui (liste fermée sans
  garde) → oui une fois ACAL1670 construite.
