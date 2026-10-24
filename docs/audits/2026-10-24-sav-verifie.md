# Vérifie ASAV — contre-visite de clôture du groupe sav (J4), 24/10/2026

Commande `vérifie ASAV` (METHODE §C.4.2, skill audit §5), lancée par `loop audit`. `audit_registre.py --du` liste quatre
groupes dus en clôture (≥ 95 %) : ASAV 88/89, ACRM 64/66, APAR 63/65, APDF 53/54. Les dus se jouent par nombre de tâches
cochées décroissant, donc ASAV passe en premier. C'est la deuxième contre-visite du groupe. La précédente, du 11/10
(`docs/audits/2026-10-11-sav-verifie.md`), était à mi-parcours : 26 tâches, 26 ok.

Pour chaque tâche de l'échantillon, on rapproche le texte, le ou les commits, le test rouge nommé et le code de `main`
avec les 7 critères de `docs/claude-memory/lecons-construction-qjr5.md`. Chaque écart S1-S2 est prouvé par une sonde
exécutée en transaction annulée. Les écarts confirmés sont déposés en tâches v3 dans le plan du propriétaire des fichiers,
`PLAN_AUDIT_SAV.md` (apps/sav et frontend/src/pages/sav appartiennent à J4).

La contre-visite n'a rien construit, n'a lancé aucun deploy et n'a rien lu ni écrit en production.

## 0. Préconditions

- **SHA.** `origin/main` = `641a2266d` (PR #1014), re-fetch en début d'itération. Branche de claim : `verifie-asav-cloture`
  (commit vide `2194b8d54`, poussé).
- **Registre.** J4 `sav`, groupe ASAV, dossier `docs/audits/2026-10-08-sav.md`, statut calculé `vérifié` avant ce dépôt
  (88/89 cochées, 98 %, contre-visite du 11/10 sans écart S1-S2).
- **Inventaire (déterministe).** 90 tâches ASAV, 88 `[x]`. Restent : ASAV72 `[BLOCKED: sans objet]`, ASAV99 (acceptation
  en direct du groupe, jamais jouée).
- **Échantillon (graine = SHA `641a2266d9c6a9ce33fd2c0ca2eb7248c4e13326`).** Toutes les P0/S1 cochées (ASAV2 à ASAV7,
  ASAV95), plus 25 % du reste tirées par `random.Random(int(sha, 16)).sample` (20 sur 81). Total : **27 tâches**, toutes
  dans `PLAN_AUDIT_SAV.md`.
- **Pile des sondes.** Conteneur jetable `sonde-verifie-asav` sur l'image `erp-agentique-django_core`, avec le code de
  `main` copié par `git archive` (le conteneur de la pile locale montait le worktree d'une autre session ; il n'a pas été
  touché). Base de démo partagée : une migration en attente, `stock.0172` (catalogue C&I, sans lien avec sav), non appliquée.
  Chaque sonde tourne dans une transaction annulée : base inchangée, 0 mail, 0 tâche Celery.

## 1. Vérificateurs (9 agents frais, opus, effort élevé, lecture seule, même répertoire, 2 à 4 tâches chacun)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **18** | ASAV3, 6, 7, 13, 17, 19, 28, 34, 35, 38, 41, 42, 51, 58, 65, 68, 78, 95 |
| partiel | **9** | ASAV2 (S2), ASAV4 (S1 + S3), ASAV5 (S3), ASAV16 (S3 ×2), ASAV24 (S2), ASAV45 (S2 + S3), ASAV56 (S3), ASAV66 (S4), ASAV101 (S3) |
| non-fait / faux / régression / déjà-présent | 0 | — |

Changements postérieurs jugés voulus, pas des régressions : ASAV2 et ASAV66 répondent 409 au lieu de 400 (ERR-ENF11, refus
qui dépendent de l'état) ; ASAV6 `test_sans_chantier_reste_none` renommé (le chantier est toujours créé à l'acceptation) ;
ASAV17 « société sans SLA = jamais en retard » remplacé par D-ASAV-5-Q2 a (ASAV57).

## 2. Sondes (4 REPRO)

| Sonde | Tâche | Observé (code de `main`, transaction annulée) |
|---|---|---|
| `docs/audits/sondes/ASAV/C-ASAV-VER-001.py` | ASAV2 | rôle système Technicien : `is_responsable` vrai ; `facturer` sans override 403, avec override **201**, ligne 5000.00 |
| `docs/audits/sondes/ASAV/C-ASAV-VER-002.py` | ASAV4 | ticket ouvert le 25/08, contrat débuté le 24/10 : couverture **contrat**, ligne **0.00** au lieu de 5000.00 |
| `docs/audits/sondes/ASAV/C-ASAV-VER-003.py` | ASAV24 | ancien ticket de même texte ; envoi HEIC 400 puis renvoi sans photo **200** avec la référence de l'ancien ticket, 0 ticket créé |
| `docs/audits/sondes/ASAV/C-ASAV-VER-004.py` | ASAV45 | fin constructeur 28/08, fin effective 28/12 : registre `statut_garantie` **expiree**, clé `date_fin_garantie_effective` absente, `totaux.expirees` 1 |

## 3. Écarts retenus

| Constat | Tâche | Écart de | Crit. | Grav. | Emplacement | Observé → attendu | Sonde |
|---|---|---|---|---|---|---|---|
| C-ASAV-VER-002 | ASAV105 | ASAV4 | C7 | S1 | `apps/sav/models.py::ContratMaintenance.est_actif` | la date de début n'est jamais testée : un contrat signé après l'ouverture couvre le ticket à 0 → couverture jugée à l'ouverture (D-ASAV-6), `date_debut ≤ date de référence` | `docs/audits/sondes/ASAV/C-ASAV-VER-002.py` |
| C-ASAV-VER-001 | ASAV104 | ASAV2 | C5 | S2 | `apps/sav/services.py::decision_facturation` | `is_responsable` (vrai pour tout rôle à droit d'écriture) lève le refus récidive : un technicien facture → override au seul palier admin/responsable (`menu_tier`, comme l'écran) | `docs/audits/sondes/ASAV/C-ASAV-VER-001.py` |
| C-ASAV-VER-003 | ASAV106 | ASAV24 | C6 | S2 | `apps/sav/public_views.py::equipement_public_signaler` | clé anti-rejeu prise avant la validation de la photo, recherche d'un ticket par préfixe sans borne de fenêtre : le signalement est perdu → photo validée d'abord, rejeu = seul ticket de la fenêtre | `docs/audits/sondes/ASAV/C-ASAV-VER-003.py` |
| C-ASAV-VER-004 | ASAV107 | ASAV45 | C7 | S2 | `apps/sav/selectors.py::warranty_registry` | statut, alertes, totaux et prochaine échéance sur la seule date constructeur, clé effective lue par l'écran jamais servie → garantie effective (`Equipement.date_fin_garantie_effective`) | `docs/audits/sondes/ASAV/C-ASAV-VER-004.py` |
| C-ASAV-VER-005 | ASAV108 | ASAV5 | C7 | S3 | `apps/sav/views.py::TicketViewSet.perform_create` | `droits_restants` appelé sans `ticket=` après l'enregistrement : le ticket se compte lui-même, note « quota déjà atteint » sur le premier ticket couvert | STATIQUE |
| C-ASAV-VER-006 | ASAV109 | ASAV16 | C17 | S3 | `apps/sav/views.py::TicketViewSet.annuler` | annuler (unitaire et en lot) et réactiver ne closent pas la pause « en attente client » : l'échéance effective croît sur un ticket annulé | STATIQUE |
| C-ASAV-VER-007 | ASAV110 | ASAV16 | C15 | S3 | `apps/sav/views.py::TicketViewSet.attente_client` | aucune garde de statut : une pause redémarre sur un ticket résolu → refus hors statuts ouverts, bouton masqué | STATIQUE |
| C-ASAV-VER-008 | ASAV111 | ASAV45 | C3 | S3 | `frontend/src/pages/sav/TicketsPage.jsx::TicketDetail` | le bandeau recalcule expiré / jours restants avec la date du navigateur → lecture des seuls champs servis | STATIQUE |
| C-ASAV-VER-009 | ASAV112 | ASAV56 | C3 | S3 | `frontend/src/pages/sav/SavParametresPage.jsx::ServiceClientSection` | second interrupteur « heures ouvrées » sans éditeur d'horaires → une seule commande, celle de l'onglet SLA | STATIQUE |
| C-ASAV-VER-010 | ASAV113 | critique (règle AUD502) | C7 | S3 | `apps/sav/selectors.py::client_a_contrat_actif` | ce sélecteur, son jumeau en lot et `contrats_maintenance_facturables` lisent le drapeau `actif` seul : un contrat échu au-delà de la grâce bloque la proposition d'entretien à la réception et reste dans le MRR → `est_actif` | STATIQUE |

**Constats S1-S2 : 4** (1 S1, 3 S2), tous reproduits. ASAV114 clôt la section (acceptation en direct, jamais confiée à une
lane).

C-ASAV-VER-002 a trois emplacements fermés par la même correction (`est_actif` refuse une date de référence antérieure à
`date_debut`) : `Ticket._contrat_couvrant` (couverture, trois portes de facturation), `ContratMaintenance.valide_pour_client`
(avertissements à la création, colonne « couvert par le contrat ») et `ContratMaintenance.actif_pour_client` (un contrat qui
commence le mois prochain impose déjà son SLA).

Sans tâche : ASAV66 (S4, l'écran Production affiche un message générique au lieu du motif 409, optionnel) ; ASAV101 (S3,
preuve en direct absente et id hors de la dette gelée) est couvert par l'acceptation de groupe ASAV99, toujours ouverte.

## 4. Critique de complétude (1 appel Fable, effort élevé)

Un écart S1 subsistant, la critique Fable unique a été jouée (contexte frais, lecture seule).

- **C-ASAV-VER-002 confirmé.** Mécanisme confirmé. Le trou date d'AUD502 ; il devient atteignable parce qu'ASAV4 passe une
  date passée. Gravité maintenue à S1 (argent faux sur le chemin par défaut). La critique note qu'un « contrat signé pendant
  la panne couvre la panne » serait une politique possible. D-ASAV-6 tranche déjà : couverture jugée à la date d'ouverture,
  donc un contrat pas encore commencé ne couvre pas. Aucune décision nouvelle n'est ouverte ; si le fondateur veut l'autre
  politique, c'est une décision à part.
- **Spot-check des « ok » argent** (ASAV3, ASAV6, ASAV65) : aucune divergence.
- **Trous.** Trois sont rattachés aux constats existants : `perform_create` qui choisit le contrat au jour de lecture
  (rattaché à ASAV108) ; `actif_pour_client` qui applique le SLA d'un contrat futur (emplacement de C-ASAV-VER-002) ;
  `client_a_contrat_actif` / `contrats_maintenance_facturables` sur le drapeau seul, vérifié par lecture (C-ASAV-VER-010).
  Deux restent optionnels : la colonne `contrat_couvre_equipement` jugée au jour de lecture, et la mention de garantie du
  PDF d'intervention calculée à la date d'impression. Points vérifiés sans trou : la couverture posée à la main prime,
  `generer_facture_ticket_sav` ne recalcule rien, `creer_devis` refuse un ticket couvert.

## 5. Optionnel (non déposé)

- ASAV65 : `FleetPage.jsx` ne lit pas `sans_reference` (affiche « — »).
- ASAV66 : contrôle « vérifier puis créer » sans verrou ni bouton désactivé ; relevé AUTO de `sync_system` non dédoublonné
  contre une saisie manuelle (hors périmètre déclaré de la tâche).
- ASAV24 : fenêtre fixe `time // 300` (deux envois à cheval créent deux tickets) ; renvoi avec photo après un envoi sans
  photo : photo ignorée sans le dire.
- ASAV28 : `store_attachment(photo)` sans `company=` (clé MinIO sans préfixe société, antérieur à la tâche).
- ASAV34 : macro `{technicien}` remplie avec l'identifiant de connexion (API seule) ; `_chatter_payload` remplace toute
  adresse d'une note par le nom de l'auteur ; contrat `mes_tickets_fil.json` montre encore un identifiant.
- ASAV58 : `Dashboard.jsx` (« Mes tickets urgents », « SLA en retard ») renvoie vers `/sav` nu (hors pages sav).
- ASAV68 : l'écran O&M affiche un message générique et non le motif du 502.
- ASAV4 : `date_ouverture` reste modifiable (antidater rend un ticket couvert) ; la mention garantie du PDF d'intervention
  se juge à la date du jour.
- ASAV16/17 : `_sla_moitie_ecoulee` mélange jours calendaires et ouvrés ; corps de notification sur `sla_due_at` brut ;
  `Ticket.recompute_sla_breach` recopie la règle de `ticket_en_retard_sla`.
- ASAV45 : `contract_samples/ticket_detail.json` porte `sous_garantie_effectif: true` (le serveur sert 'oui'/'non'/…).

## 6. Couverture et non-couvert

- **Couvert.** 27 tâches sur 88 cochées (toutes les P0/S1 + 25 %), commits, tests nommés (lus, non exécutés), code de
  `main`, décisions D-ASAV-*. Quatre sondes rejouées sur le code de `main`.
- **Non couvert.** Les 61 autres tâches cochées ; aucun aller-retour en direct à l'écran (ASAV99 reste ouverte).
- **Statut du registre.** Après ce dépôt : 88 cochées sur 100 constructibles (88 %, ASAV104-114 ajoutées), contre-visite de
  clôture **avec 4 écarts S1-S2** → statut calculé `audité` ; le cycle n'est pas sorti (il faut deux contre-visites
  consécutives à zéro S1-S2).

## 7. Coût

- 9 vérificateurs opus (effort élevé) : ≈ 1,41 M de jetons, 267 appels d'outil. 1 critique Fable (effort élevé) :
  ≈ 0,15 M. 1 rédacteur opus : ≈ 0,25 M (11 tâches v3, clauses calculées par `audit_tache.py`, fronts au grep).
- Orchestrateur : échantillon déterministe, triage des 27 verdicts, lecture du code des 4 écarts S1-S2, 4 sondes écrites et
  jouées, rattachement des trous de la critique, rédaction.
- H0 S0 O10 F1 · jetons sous-agents ≈ 1,8 M

<!-- verifie | groupe: ASAV | pct: 98 | ecarts_s1_s2: 4 -->
