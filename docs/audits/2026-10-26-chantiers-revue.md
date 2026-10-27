# Revue L3 « chantier vécu de bout en bout » — dossier (26-27/10/2026)

Demande du fondateur (26/10/2026) : « use it as I will use it » — après l'acceptation du devis, démarrer le
chantier, acheter ce qui manque, suivre les techniciens (GPS), photos avant/après, numéro de série et
caractéristiques de chaque article, puis tester comme un humain. Niveau L3 (go-deep). Unité J2 `chantiers`,
groupe ACHT (tâches ACHT104-110 dans `docs/plans/PLAN_AUDIT_CHANTIERS.md`). PR #1066.

## 1. Méthode

- **R1 comprendre** — 7 lanes de lecture (devis→chantier, achats, terrain, GPS + droit marocain, réception→parc,
  benchmark web, écrans/pile) + run live `demo_admin` sur la pile locale (`main` 0533a15e5) : 30 problèmes numérotés.
- **R2 creuser/construire** — contrats d'abord (PACT10 : `chantier_approvisionnement.json`,
  `intervention_serials_attendus.json`, puis `gps_mon_consentement.json`, `intervention_presence.json`,
  `chantier_avertissements_cloture.json`), 7 lanes de construction file-disjointes sur une même branche.
- **R3 valider** — 4 vérificateurs frais (opus, lecture seule) : 7 écarts S2 + 9 S3 → 4 lanes correctrices ; gardes
  CI jouées en local puis en CI ; aller-retour EN DIRECT sur une pile à part (conteneur `docker run` du worktree :8010 +
  `vite preview` :5180, base locale partagée) — voir §4.
- **R4 revue finale** — ce dossier + rapport au fondateur.

## 2. Décisions (à confirmer par le fondateur)

- **Suivi GPS « sans que les techniciens le sachent » : non construit.** Loi 09-08 (art. 3-5-7-12) et délibération
  CNDP 17-2014 : information préalable (responsable, finalités, données, destinataires, droits, n° de récépissé),
  déclaration CNDP, jamais hors temps de travail, conservation ≤ 1 an, accès du salarié à ses données. La docstring
  `models_gps_tracking.py` portait déjà la décision fondateur « ENFORCED : pas d'interrupteur ». Construit : suivi
  AUTOMATIQUE pendant en route / sur site après accord de la notice dans l'app, bandeau visible, purge 30 j,
  « mes positions ». Le n° de récépissé CNDP se saisit dans Suivi GPS → Consentements.
- **« Matériel commandé » = BCF ENVOYÉS** (un brouillon ne sécurise rien) ; l'avancement automatique à la création
  des brouillons reste pour les sociétés sans étapes de cycle de vie.
- **P24** (un placeholder parc par unité au lieu d'un par produit) : conflit avec ACHT46 → question fondateur, non
  construit.

## 3. Ce qui a été construit (ACHT104-110)

| Besoin fondateur | Avant | Après |
|---|---|---|
| Savoir quoi acheter | onglet Matériel + bouton « Calculer le besoin », réservé = total société, BCF invisibles, brouillon = manque effacé | `/approvisionnement/` chargé seul : requis / déjà sorti / réservé (ce chantier) / dispo / en commande (brouillon à part) / reçu / manque net ; BCF du chantier avec réception ; DA ; réservations ; « Prêt à poser » + raisons |
| Commander | un BCF chez le fournisseur du premier produit | un BCF brouillon par fournisseur, surcharges, sans-fournisseur signalés, Signé → Matériel commandé à l'envoi |
| Réception fournisseur | aucune série saisissable | n° de série / lot par ligne ; BCF → chantier d'origine cliquable ; DA → « Générer le BCF » + étapes d'approbation |
| Planifier | interventions standard seulement depuis Planification ; formulaire sans technicien | boutons dans la fiche + technicien ; « Voir le chantier » après acceptation |
| Techniciens GPS | interrupteur à activer par le technicien à chaque session ; pings sans intervention acceptés ; alerte par ping ; purge jamais lancée | notice acceptée une fois, suivi auto, gardes du ping, ping-lot hors-ligne persistant, une sortie ouverte notifiée, rayon par chantier, présence serveur, carte 15 min + tracé, purge quotidienne |
| Photos avant/après | créneaux OK ; pairage Comparer par ordre ; photo d'intervention sans position | photos géolocalisées, Comparer par sujet, checklist : photo obligatoire appliquée + erreurs visibles |
| Séries + caractéristiques | désignation libre → jamais au parc ; pas de scan ; « au moins une série » | liste fermée des produits sériables avec jauge N/M, Scanner (BarcodeDetector), caractéristiques, doublon refusé, poussée au parc, avertissement « séries manquantes » |
| Fin de chantier | pièce garanties du pack en cercle ; PV/BL invisibles au portail ; clôture sans contrôle | garanties prévues par produit ; PV/BL partagés au client ; avertissements de clôture consultatifs |

## 4. Aller-retour en direct (27/10/2026, pile à part, `demo_admin` / `demo_tech`)

Joué par l'orchestrateur avec Playwright MCP (oracles qa-explorer : 0 console.error applicatif ; les 5xx observés sont
tous « too many clients already » de Postgres pendant des runs de tests parallèles d'autres sessions, hors code).

| Étape | Observé |
|---|---|
| Aperçu chantier 11 | carte « Prêt à poser ? » (aucun manque, prêt) ; bannière « Matériel couvert : planifier la pose » |
| Manque mis en scène (batterie 0, panneaux 5) | « 2 manques », « Pas encore prêt », table manque 9 + 1 |
| « Commander les manques (2) » | 2 BCF brouillons (Electra, SunPro), toast « Chantier passé à Matériel commandé », colonne « brouillon N », manque inchangé |
| BCF-…-0007 « Envoyer au fournisseur » (écran stock, chantier d'origine affiché) | retour fiche : « 9 en route », manque « — », 1 manque restant (batterie, brouillon) |
| Interventions : formulaire avec Technicien | Pose du jour créée pour demo_tech ; bouton interventions standard désactivé (chantier non vierge) |
| Suivi GPS → consentement demo_tech | « Actif · En attente d'accord du technicien · Notice v1 · récépissé CNDP non encore déclaré » |
| demo_tech → Ma journée | Pose visible ; Prépa : 10 lignes, batterie « Manquant », panneaux non manquants (BCF envoyé) ; « Tout est chargé » → Prête |
| Départ dépôt | En route ; notice loi 09-08 affichée ; « J'ai lu et j'accepte » → bandeau « Position partagée… » (position indisponible : navigateur sans GPS) |
| Ping API (device) | 201, distance 1,217 km, hors périmètre, aucune alerte (en route) |
| Check-in | Sur site 23:58 ; « compléter les photos obligatoires » |
| Photos | 6 créneaux obligatoires remplis → « faire signer le client » |
| N° série | « 0/17 relevés » ; onduleur + caractéristiques → 1/17, 1/1 ; doublon « N° de série déjà relevé » ; « Scanner non disponible sur ce navigateur » |
| Signature + Retour dépôt | « Signé par le client » ; Terminée ; « confirmer le retour d'outillage » |
| demo_admin après | Équipements : onduleur HW10K… « En service, garantie jusqu'au 27/10/2027 » ; Comparer : 2 paires par sujet + 2 « Après » sans « Avant » ; Carte live : « demo_tech · il y a 6 min » |
| Statuts Planifié → En cours → Installé | un pas à la fois, « Planifier la réception » |

Non joué en direct (voir rapport) : signature de réception + portail client, replanification, rattrapage hors-ligne.

## 5. Écarts restants / questions

- Séries : l'avertissement « séries manquantes » au passage à Terminée est renvoyé par l'API mais pas encore affiché
  dans « Ma journée » (consultatif).
- Portée technicien : `GET chantiers/<id>/` répond 404 au technicien responsable du chantier (pré-existant), l'onglet
  « Infos client » de l'intervention est donc vide pour lui.
- `seed_demo` refuse sur une base locale dont la société démo n'a pas `est_demo=True` (flag non rétro-rempli).
