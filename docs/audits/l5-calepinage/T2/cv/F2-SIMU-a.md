# Contre-vérification — F2-SIMU-a — Simulation : météo, pertes, ombrage, réglages de simulation

22 corrections livrées (première moitié de la liste, S1-S2 d'abord) sans preuve en direct, S1-S2 d'abord. Pour chacune : rejoue la « preuve », regarde l'écran, écris UN verdict (ok / partiel / non-fait / faux / regression / deja-present).
Le texte complet d'une tâche (constat d'origine, Given/When/Then) : `grep -n "<id> —" docs/plans/PLAN_AUDIT_CALEPINAGE.md` dans le worktree en lecture.

- **ACAL404** (S2) — Compiler le profil de départ (données) : chaque valeur de `data/profil_depart.json` vient d'une page PUBLIÉE relue par la lane (URL, date de lecture) ; une clé sans source vérifiable reste ABSENTE et figure dans `sans_source` avec
  - Preuve : une seconde lane indépendante relit 100 % des URL et signale tout écart (revue de données, sans écran).
- **ACAL692** (S2) — Nommer, dans `validation`, le plus gros poste de pertes de la cascade quand la chaîne perd plus que PVGIS et produit moins (`validation.poste_principal`), et aligner l'échantillon sur les clés réellement servies ; fini quand la rè
  - Preuve : revue de données sans écran : simuler un calepinage de démo à pertes déclarées inégales et lire `validation.poste_principal` dans `GET resultat/`.
- **ACAL693** (S2) — Servir `production.duree_de_vie` (horizon, motif d'omission du tableau pluriannuel et garantie de production du fabricant à 10 et 25 ans) à côté de `production.projection` ; fini quand le test et les deux échantillons le portent e
  - Preuve : revue de données sans écran : `GET resultat/` d'un calepinage simulé avec fiche garantie : `production.duree_de_vie.garantie.pct_a_25_ans` égale la fiche.
- **ACAL695** (S2) — Servir `cascade.postes_lisibles` : la cascade regroupée en cinq postes lisibles (Ombres proches, Poussière, Chaleur, Câbles et onduleur, Autres pertes) par une table de correspondance étape → poste testée contre `ORDRE_ETAPES` ; f
  - Preuve : revue de données sans écran : `GET resultat/` d'un calepinage de démo : `cascade.postes_lisibles` à cinq postes, `autres` « partiel » avec `spectral` et `diodes` nommés.
- **ACAL699** (S2) — Servir `cascade.a_renseigner` : pour chaque étape omise faute de réglage société ou de champ de fiche, la clé ou le champ à renseigner, le libellé, la phrase « où lire la valeur » SANS chiffre et le compte « étapes comptées sur ét
  - Preuve : revue de données sans écran : un calepinage de société neuve : `cascade.a_renseigner.lignes` nomme salissure, vieillissement/LID et mismatch, chacun avec sa page à lire.
- **ACAL701** (S2) — Compiler `plages_usuelles` (données) : pour chaque étape de la cascade, la bande de perte imprimée par une page PUBLIÉE relue par la lane (URL, date de lecture, grandeur) ; une étape sans bande sourcée reste ABSENTE ; fini quand c
  - Preuve : une seconde lane indépendante relit 100 % des URL et signale tout écart (revue de données, sans écran).
- **ACAL702** (S2) — Publier `cascade.plages` : pour chaque étape appliquée qui a une bande sourcée, « dans la plage » ou « inhabituel » avec la bande et sa page ; fini quand une perte hors bande est marquée « inhabituel » et qu'une étape sans bande n
  - Preuve : revue de données sans écran : `GET resultat/` d'un calepinage de démo : `cascade.plages.etapes` ne contient que les étapes dont la page publie une bande.
- **ACAL704** (S2) — Remplacer la borne codée en dur du rendement spécifique (600 ; 2 400 kWh/kWc) par deux réglages société sourcés (sans valeur) : l'avertissement ne part que si la société a saisi sa borne ; fini quand un rendement hors d'une borne 
  - Preuve : revue de données : société sans borne saisie, rendement 2 650 : aucun avertissement ; avec la borne saisie dans Réglages simulation : l'avertissement apparaît.
- **ACAL705** (S2) — Servir `production.bilan_mensuel` : température ambiante moyenne et indice de performance (PR) par mois, à côté de l'irradiation du plan ; fini quand les 12 lignes se lisent sur l'exemple et que la somme pondérée des mois retrouve
  - Preuve : revue de données : `GET resultat/` du golden : douze PR autour du PR annuel, un mois d'été à température plus haute.
- **ACAL706** (S2) — Servir `production.gain_inclinaison` : l'irradiation horizontale par mois (une requête PVGIS à 0°, même base et même fenêtre) et le gain d'inclinaison du plan des modules ; fini quand le gain égale le rapport de deux irradiations 
  - Preuve : revue de données : `GET resultat/` d'un calepinage de démo : `gain_pct` positif pour un toit incliné, motif nommé pour un fichier déposé sans horizontale.
- **ACAL758** (S2) — Faire servir par l'étape IAM sa table « angle d'incidence, facteur » (0 à 90°, pas de 10°) calculée par la loi retenue ; fini quand `cascade.etapes[iam].entree.table_iam` porte 10 lignes égales à la formule de Fresnel écrite dans 
  - Preuve : revue de données : simuler un calepinage de démo, lire `cascade.etapes` à l'étape `iam` dans `GET resultat/` et comparer le facteur à 60° à la valeur du test.
- **ACAL786** (S2) — Admettre à l'enregistrement les réglages de secours et de commande que la simulation lit déjà (`appareils`, `duree_secours_h`, `fenetres`, `part_effacable_pct`, `plafond_effacable_kw`) ; fini quand `POST entree-electrique/` avec `
  - Preuve : PA2.5 — poster ce corps sur un calepinage de démo avec batterie du stock, relancer, lire la réserve.
- **ACAL790** (S2) — Refuser à l'enregistrement un seuil de protection hors réseau mal formé en nommant `hors_reseau.seuils.<seuil>` ; fini quand `POST entree-electrique/` avec une veille sous l'arrêt rend 400 sous `hors_reseau.seuils.veille_pct` et q
  - Preuve : PA2.5 — poster une veille sous l'arrêt sur un calepinage de démo : 400 sous `hors_reseau.seuils.veille_pct`.
- **ACAL736** (S?) — Servir l'histogramme de l'énergie par classe de puissance dans l'entrée de l'étape `ecretage` (`entree.distribution`) avec l'énergie écrêtée et sa part ; fini quand, sur 5 heures de puissances connues, les classes, l'énergie écrêt
  - Preuve : PA2.5 — calepinage à ratio DC/AC élevé : `GET resultat/`, étape `ecretage`, `entree.distribution` non nul.
- **ACAL740** (S?) — Appliquer le déclassement thermique de l'onduleur à la borne d'écrêtage heure par heure avec la température d'air `t2m_c` servie ; fini quand, sur 4 heures de températures connues, la borne et l'énergie écrêtée égalent la formule 
  - Preuve : PA2.5 — fiche d'onduleur renseignée, site chaud : étape `ecretage` plus bas qu'avec la fiche vide.
- **ACAL742** (S?) — Déclarer au registre des réglages société deux clés sans valeur, « nettoyages par an » et « inclinaison d'autonettoyage », typées et sourcées ; fini quand le registre servi les liste avec leur type et qu'aucune valeur n'est prérem
  - Preuve : PA2.5 — Réglages simulation : les deux lignes apparaissent vides, avec leur référence.
- **ACAL744** (S?) — Comparer l'irradiation incidente de la base PVGIS utilisée avec celle de l'AUTRE base (SARAH3 / ERA5) sur le même pan et les mêmes années, et publier l'écart annuel et mensuel dans `meteo.comparaison_base` ; fini quand deux séries
  - Preuve : PA2.5 — simuler un calepinage de démo : `GET resultat/`, `meteo.comparaison_base.ecart_pct` non nul.
- **ACAL749** (S?) — Servir la liste « ce que cette simulation ne modélise pas » (`cascade.limites_connues`, texte sans chiffre) ; fini quand le test affirme chaque limite contre le code et que l'ombrage du diffus n'est servi que si son étape est abse
  - Preuve : PA2.5 — `GET resultat/` : `cascade.limites_connues` non vide.
- **ACAL751** (S?) — Imprimer les limites connues et les étapes non comptées à l'annexe « Hypothèses » du rapport d'étude interne ; fini quand l'annexe d'un résultat servi contient la liste, dans la langue du rapport, et qu'un résultat sans `limites_c
  - Preuve : PA2.5 — rapport d'étude PDF d'un calepinage simulé : l'annexe contient la liste.
- **ACAL752** (S?) — Écrire la colonne `p_dc_kw` (puissance continue à l'entrée de l'onduleur) sur chaque point de la série à l'étape « onduleur », aujourd'hui toujours `null` dans la série persistée ; fini quand la série d'une simulation réelle porte
  - Preuve : PA2.5 — simuler un calepinage, `GET export-csv/?quoi=horaire&colonnes=…,p_dc_kw` ⇒ la colonne est remplie.
- **ACAL470** (S3) — Saisir une cible de production annuelle (kWh/an) qui fixe le nombre de panneaux à poser ; fini quand taper un objectif dans « Production visée » règle « Panneaux nécessaires » sur le plus petit nombre dont l'énergie annuelle affic
  - Preuve : PA2.5 — toit plat : saisir 12 000 kWh/an, lire N et l'énergie de la carte ≥ 12 000 ; objectif irréaliste : phrase du maximum.
- **ACAL711** (S3) — Servir, pour chaque chaîne touchée par l'ombre, ses deux bornes de perte, leur écart et ses modules ombrés, et garder les chaînes des DEUX pans quand la cascade somme plusieurs pans ; fini quand `entree.chaines[]` de l'étape `mism
  - Preuve : pile locale — calepinage à deux pans avec accès solaire par module et `seuil_derivation_acces` saisi : simuler puis lire `GET …/resultat/` ; `cascade.etapes` (étape `mismatch_ombrage`) `.entree.chaines` porte les chaînes des deux pans (PA2.5).
