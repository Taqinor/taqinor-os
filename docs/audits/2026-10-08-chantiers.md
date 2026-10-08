# Audit J2 « chantiers » — dossier d'évaluation (L2, 08/10/2026)

Unité **J2** du registre (`docs/audits/unites.yml`), groupe **ACHT**, niveau **L2** (défaut : P=3, I=4, score 12 ; auto-pick
go-deep : sous-domaine support, saisie propagée devis → chantier → stock → parc SAV, documents client — PV, bon de livraison,
compte-rendu ⇒ L2). Fichier du propriétaire : `docs/plans/PLAN_AUDIT_CHANTIERS.md` (`docs/ownership.yml` › `chantiers`, qui
prime). Claim : branche `audit-J2`. Méthode v2. Sorties brutes : scratchpad (`j2/`).

## 0. Préconditions (phase 0)

- **SHA.** Lecture à `origin/main` `d169957da` (08/10/2026). Pile locale `erp-agentique-*` (code monté depuis
  `C:\dev\taqinor-os`, migré à `d096f2233` ; commits intermédiaires = docs).
- **Groupes voisins à ne pas redire** : ASTK (stock ↔ chantier : réservations, sorties, double décompte — 16 tâches dans ce
  fichier), ADOC (GED / PV), ACAL (feu vert visite → calepinage), ASEC (multi-société), AFAC (BC / facture), APDF (PV, BL,
  compte-rendu imprimés : photos, intervenant, ICE, prestations listées comme composants).

## 1. Charte (phase 1)

- **Système et frontière.** Devis accepté → chantier (création par `devis_accepted`, nomenclature figée, étapes) → achats et
  réception fournisseur → kitting / livraison → interventions (planification, équipe, terrain hors-ligne, compte-rendu, photos,
  signature) → réception du chantier → bascule de la nomenclature en parc SAV (`sweep_bom_to_parc`) → rapport de production.
  Outillage (prêt / retour d'outils) et paramètres chantier (étapes, check-lists, équipe terrain, modèles de fiche).
- **Objet.** Objectifs 1 (une V2 de devis met à jour le chantier comme décidé ; une intervention se corrige après coup),
  2 (une seule nomenclature), 3, 4 (PV / compte-rendu justes). Contrat J2 (METHODE §D.6).
- **Personas réelles** : Administrateur, Responsable, Technicien responsable, Technicien ; client (PV, page publique de
  compte-rendu). **Niveau** L2 ; **jeu** `demo` ; prod en lecture seule.
- **Critères** : C1, C2, C3, C4, C5, C6, C7, C9, C10, C12, C13.
- **Étapes.** P1 création : P1.1 `devis_accepted` → chantier · P1.2 nomenclature figée · P1.3 V2 / révision du devis · P1.4
  annulation. P2 achats : P2.1 demande d'achat · P2.2 réception fournisseur. P3 kitting / livraison. P4 interventions : P4.1
  planification · P4.2 terrain hors-ligne / synchro · P4.3 compte-rendu, photos, signature · P4.4 correction après coup.
  P5 réception → parc SAV, commissioning, rapport de production. P6 outillage et paramètres. P7 coutures : événements,
  multi-société, tâches Celery.
- **Non-objectifs.** Intérieur du stock (J3), des PDF (X4 vient de passer), de la GED (J6) ; apps parquées.

## 2. Spécification (phase 2)

- H×H S-1 : un devis accepté crée UN chantier (rejeu de l'événement, double acceptation ⇒ pas de doublon).
- H×H S-2 : une révision V2 acceptée met à jour la nomenclature du chantier selon la règle décidée, sans écraser une saisie
  terrain ni perdre une réservation.
- H×M S-3 : une intervention terminée se corrige / se rouvre avec trace ; une synchro hors-ligne rejouée n'écrase pas une
  correction plus récente.
- H×M S-4 : la réception du chantier crée le parc SAV une fois, avec les vrais numéros de série et la garantie à partir de la
  réception.
- M×H S-5 : chaque viewset / action / tâche / page publique à jeton borne la société ; un technicien ne voit que ses chantiers
  si la portée le dit.
- M×M S-6 : statuts du chantier : machine d'états respectée (pas de saut, pas de retour silencieux) ; annulation propagée.

Seuils : S1 perte / fuite locataire / document client faux ; S2 saisie écrasée, geste cassé ; S3 contournement ; S4 cosmétique.

## 3. Plan des lanes (phase 3)

| Ronde | Lanes |
|---|---|
| Scout | détecteurs + dédoublonnage (haiku/low) |
| R2 (8) | CCRE création / révision / annulation (opus/high) · CACH achats / réception (sonnet/medium) · CKIT kitting / livraison (sonnet/medium) · CINT interventions et terrain (sonnet/medium) · CREC réception → parc, commissioning, rapport (sonnet/medium) · CTEN multi-société / permissions / tâches (opus/high) · CFRONT écrans (sonnet/medium) · COUT outillage + paramètres chantier (sonnet/medium) |
| R3 | un vérificateur FRAIS opus/high par lane, sondes en transaction annulée |
| Rédaction | 2 rédacteurs opus/high, fourchettes d'ID disjointes |
| Live | orchestrateur : écrans chantiers / interventions / outillage (Playwright `demo_admin`) |

## 4. Exécution et manifeste de couverture (phase 4)

- **Scout** (haiku, `j2/scout.md`) : `check_parked_apps`, `check_services_appeles`, `check_ecrans_atteignables`,
  `check_api_contract` verts ; 9 `@receiver` dans `installations/receivers.py` ; tâches ouvertes sur les chemins J2 : ACAL274,
  ADOC73, ADOC172, ASTK129, AACQ5 ; préfixe ACHT libre.
- **Lanes R2** (8, notes `j2/<LANE>.md` avec lus / non lus ; `services.py` 6 823 l. découpé par sous-flux) : **85 constats bruts**.
- **Run live** (`j2/live.md`) : 7 écrans (chantiers, approvisionnement, demandes d'achat, import, interventions, outillage,
  paramètres) et le détail d'un chantier (7 onglets) : 0 `console.error`, 0 4xx/5xx ; la démo n'a aucune intervention.
- **Écart de pile déclaré et corrigé.** Le conteneur monte la checkout `C:\dev\taqinor-os`, ramenée entre-temps à `8b0b9b491` par une
  autre session, alors que `origin/main` (`8e3c69636`) porte depuis ASEC32 (FK d'intervention bornées), ASEC33 (emplacements du
  kitting), ASTK177 (réalignement V2) et ASEC11-revue sur 4 fichiers J2. **Contre-vérification** (vérificateur frais opus, copie
  du code `origin/main` dans le conteneur) des 40 constats qui citent ces fichiers : **40/40 TIENNENT** — 19 sondes rejouées sur le
  code de main, 21 hors des blocs modifiés (lecture du diff) ; ASTK177 ignore les chantiers annulés et les réservations consommées
  (CCRE-1/6/7 tiennent), ASEC32 laisse `facture_id`, `annule`, `date_reception` modifiables (CINT-14, CCRE-5, CREC-5).

## 5. Registre des constats (phase 4 → 6)

85 constats bruts → **70 constats par cause racine** (82 REPRO, 3 STATIQUE, 0 réfuté). Gravités : S1 4 · S2 41 · S3 25.
**Seconde lentille** sur les 4 S1 (réfuteur frais, sondes différentes, grand livre des mouvements) : 4 MAINTENUS — C-ACHT-001 élargi
(pose partielle + V2 qui n'ajoute qu'un câble ⇒ 18 panneaux sortis pour 8 posés ; BC confirmé après F11 ⇒ 20 pour 10) ;
C-ACHT-002 nuancé (les étapes CH2 amorcées bloquent sur exigences, pas sur adjacence ; aucune société locale n'en a) ;
C-ACHT-043 (création par un responsable avec l'outil d'une autre société : nom et n° de série renvoyés ; canal latéral sur
l'état d'étalonnage) ; C-ACHT-052 (exactement 6 champs, témoins `Equipe.chef` / `ProjetTache.assigne` correctement bornés).

| ID | lanes | crit. | grav. | verdict | titre | tâche(s) |
|---|---|---|---|---|---|---|
| C-ACHT-001 | CCRE-1+CCRE-6 | C7 | S1 | REPRO + L2 maintenu | Le « déjà sorti » d'un chantier n'est pas lu à sa source : F11 libère au lieu de solder (V2 prix seul, réactivation | ACHT1 |
| C-ACHT-002 | CCRE-2 | C7 | S1 | REPRO + L2 maintenu | Machine d'états du chantier gardée côté écran seulement : saut par-dessus « Installé » (PATCH, mise-en-service, cré | ACHT2, ACHT3 |
| C-ACHT-003 | CCRE-3 | C6 | S2 | REPRO | Un chantier annulé avance jusqu'à « Réceptionné » : parc, événement, activité SAV, rappel de solde | ACHT2, ACHT3 |
| C-ACHT-004 | CCRE-4 | C6 | S2 | REPRO | Second chantier pour la même affaire (creer-depuis-devis sur V1 remplacée, POST, PATCH devis) | ACHT4, ACHT5 |
| C-ACHT-005 | CCRE-5+CINT-14 | C3 | S3 | REPRO | Champs posés par le serveur inscriptibles en PATCH (fields='__all__' + liste noire) : annulation sans effets ni gar | ACHT6 |
| C-ACHT-006 | CCRE-7 | C2 | S2 | REPRO | V2 acceptée pendant l'annulation : réactivation sur la nomenclature V1 | ACHT7 |
| C-ACHT-007 | CACH-1 | C3 | S2 | REPRO | Besoin matériel / BCF / gate d'approvisionnement relisent devis.lignes au lieu de la nomenclature gelée | ACHT8, ACHT9 |
| C-ACHT-008 | CACH-2 | C6 | S3 | REPRO | « Commander le besoin » non idempotent, ne retranche pas le déjà commandé | ACHT9 |
| C-ACHT-009 | CACH-3+CACH-5 | C6 | S2 | REPRO | Lignes de demande d'achat sans bornes : int() tronque, 0/négatif/prix négatif acceptés, CSV NaN/Infinity ⇒ 500 | ACHT10, ACHT11 |
| C-ACHT-010 | CACH-4 | C6 | S2 | REPRO | Demande d'achat modifiable après soumission/approbation/commande : seuil et budget contournés | ACHT12 |
| C-ACHT-011 | CACH-6 | C7 | S2 | REPRO | Refus par étape / boîte d'approbations sans libération du budget | ACHT13 |
| C-ACHT-012 | CACH-7 | C10 | S2 | REPRO | BCF généré depuis une DA de chantier sans chantier_origine : réception non réservée | ACHT10, ACHT11 |
| C-ACHT-013 | CACH-8 | C7 | S2 | REPRO | Registre des séries entrepôt : séries en trop et séries restées « retournées » | ACHT14 |
| C-ACHT-014 | CACH-9 | C6 | S3 | REPRO | DA archivée soumise et restée archivée | ACHT15 |
| C-ACHT-015 | CACH-10 | C8 | S3 | REPRO | Prix estimés de DA servis sans prix_achat_voir (recopiés comme prix d'achat du BCF) | ACHT16, ACHT90 |
| C-ACHT-016 | CKIT-1 | C2 | S2 | REPRO | En-tête d'ordre d'assemblage modifié sans réalignement des lignes | ACHT17 |
| C-ACHT-017 | CKIT-2+CKIT-3 | C7 | S2 | REPRO | Aucune table de transitions pour ordres et livraisons ; double notification « livrée » | ACHT18, ACHT19 |
| C-ACHT-018 | CKIT-4+CKIT-5 | C2 | S2 | REPRO | Livraison : grand livre dérivé des lignes courantes (correction après expédition, expédition partielle silencieuse) | ACHT20 |
| C-ACHT-019 | CKIT-6 | C7 | S2 | REPRO | Retours de livraison sans plafond cumulé, et validés comme entrée de stock | ACHT21 |
| C-ACHT-020 | CKIT-7 | C1 | S2 | REPRO | Bon de livraison : adresse du chantier au lieu de l'adresse saisie ; BL annulé sans mention | ACHT22 |
| C-ACHT-021 | CKIT-8 | C3 | S2 | REPRO | « Assembler à la commande » lit les lignes brutes (options, ×N, kit en double, révision) | ACHT23 |
| C-ACHT-022 | CKIT-9 | C7 | S2 | REPRO | Annulation d'un ordre sous-traité : composants laissés chez le sous-traitant et sortis du rapport | ACHT24 |
| C-ACHT-023 | CKIT-10 | C6 | S3 | REPRO | Kit sans composant : composite fabriqué sans consommation | ACHT25 |
| C-ACHT-024 | CKIT-11+CKIT-12 | C6 | S2 | REPRO | Contrôle qualité d'assemblage non validé et forçage de clôture non tracé | ACHT26 |
| C-ACHT-025 | CINT-1 | C5 | S2 | REPRO | Synchro hors-ligne hors portée de visibilité | ACHT27 |
| C-ACHT-026 | CINT-2+CINT-4 | C6 | S2 | REPRO | Signature d'intervention sans service unique : URL acceptée par la synchro, re-signature silencieuse | ACHT28 |
| C-ACHT-027 | CINT-3 | C1 | S2 | REPRO | Compte-rendu PDF sans la signature recueillie | ACHT29 |
| C-ACHT-028 | CINT-5 | C2 | S2 | REPRO | Synchro modifie une consommation / intervention validée | ACHT30 |
| C-ACHT-029 | CINT-6 | C10 | S2 | REPRO | Synchro sans horodatage de saisie ni base : instants faux, correction écrasée | ACHT31, ACHT32, ACHT33, ACHT91 |
| C-ACHT-030 | CINT-7 | C7 | S2 | REPRO | Intervention annulée clôturable (synchro, PATCH) avec ses effets | ACHT34 |
| C-ACHT-031 | CINT-8 | C7 | S2 | REPRO | PATCH avec statut : champs modifiés non tracés ; compte-rendu non suivi | ACHT35 |
| C-ACHT-032 | CINT-9 | C2 | S2 | REPRO | Réouverture d'intervention : date périmée, événement rejoué, recul par synchro, lien public servi | ACHT36 |
| C-ACHT-033 | CINT-10 | C10 | S2 | REPRO | Correction de série après poussée au parc : parc divergent | ACHT37 |
| C-ACHT-034 | CINT-11 | C13 | S3 | REPRO | GET compte-rendu écrit au parc ; doublon de série ⇒ 500 | ACHT37 |
| C-ACHT-035 | CINT-12 | C13 | S3 | REPRO | confirmer-rdv : date invalide ⇒ 500 ; report sans remise à zéro de la confirmation | ACHT38 |
| C-ACHT-036 | CINT-13 | C3 | S3 | REPRO | Planification : interventions annulées comptées, duree_jours ignoré | ACHT39 |
| C-ACHT-040 | CINT-15 | C7 | S3 | REPRO | Suppression de pièces de preuve d'intervention (photo, série, mémo, ligne) sans trace ni garde de statut | ACHT41 |
| C-ACHT-041 | CINT-16 | C1 | S3 | REPRO | Compte-rendu : « Équipe non renseignée » alors que technicien ou équipe canonique existent | ACHT42 |
| C-ACHT-042 | CINT-17 | C3 | S3 | REPRO | Checkin / départ synchronisés n'évaluent ni la fenêtre de RDV ni le GPS (jumeau vue/synchro) | ACHT43 |
| C-ACHT-043 | CREC-1 | C5 | S1 | REPRO + L2 maintenu | instrument_id de recette non borné : nom et n° de série d'un outil d'une autre société renvoyés | ACHT44, ACHT53 |
| C-ACHT-044 | CREC-2 | C7 | S3 | REPRO | Les prestations (Installation, Transport, Suivi) entrent au parc SAV à la réception | ACHT45, ACHT94 |
| C-ACHT-045 | CREC-3 | C3 | S2 | REPRO | Deux écrivains du parc d'un chantier : fantôme sans série, parc dépendant de l'ordre, deux dates de garantie | ACHT46, ACHT47 |
| C-ACHT-046 | CREC-4 | C13 | S2 | REPRO | Série en double : compte-rendu en 500 durable, écriture au parc déclenchée par un GET | ACHT47 |
| C-ACHT-047 | CREC-5 | C2 | S2 | REPRO | date_reception corrigée sans recalage des garanties du parc | ACHT46, ACHT48 |
| C-ACHT-048 | CREC-6+CREC-7 | C6 | S3 | REPRO | Rapport de production : paramètres non validés, défauts substitués, PDF à zéros sans puissance | ACHT49 |
| C-ACHT-049 | CTEN-1 | C5 | S2 | REPRO | Portée équipe contournée par le calendrier des interventions et le Gantt des chantiers | ACHT50, ACHT79 |
| C-ACHT-050 | CTEN-2 | C1 | S2 | REPRO | Intervention annulée encore annoncée au client (rappel J-1, page publique, lien, ma tournée, météo) | ACHT51 |
| C-ACHT-051 | CTEN-3 | C5 | S3 | REPRO | Beats rappel J-1 et météo J+3 balaient les sociétés suspendues | ACHT51 |
| C-ACHT-052 | CTEN-4 | C5 | S1 | REPRO + L2 maintenu | FK même-app / utilisateur d'une autre société acceptées dans le corps (6 champs) | ACHT52, ACHT53 |
| C-ACHT-053 | CTEN-5 | C5 | S2 | REPRO | Un Technicien sans achats_commander crée un BCF via la demande d'achat qu'il approuve | ACHT54 |
| C-ACHT-054 | CTEN-6 | C5 | S2 | REPRO | Gardes inline is_responsable : Admin RH / Commercial terrain écrivent réserves, recette, pack, approbation BCF | ACHT55, ACHT79 |
| C-ACHT-055 | CTEN-7 | C5 | S2 | REPRO | Signature client d'intervention posée avec une permission de lecture (Viewer) | ACHT56, ACHT79 |
| C-ACHT-056 | CFRONT-1+CFRONT-2 | C2 | S2 | REPRO | Fiche chantier : PATCH complet périmé (recul de statut, dates effacées, clôturé impossible à enregistrer) | ACHT57, ACHT58 |
| C-ACHT-057 | CFRONT-3+CFRONT-4 | C13 | S2 | REPRO | Dérogations serveur sans émetteur écran (re-signature BL, acompte, réouverture) | ACHT59, ACHT60 |
| C-ACHT-058 | CFRONT-5 | C13 | S3 | REPRO | Ma journée lit mal la forme réelle du refus de statut (raison perdue, toast rouge) | ACHT61 |
| C-ACHT-059 | CFRONT-6 | C13 | S2 | REPRO | Sept écrans opérationnels lisent la page 1 seulement (50 lignes) | ACHT62 |
| C-ACHT-060 | CFRONT-7 | C3 | S3 | REPRO | Demandes d'achat : colonne et détail Chantier toujours « — » | ACHT63 |
| C-ACHT-061 | CFRONT-8 | C6 | S3 | REPRO | Création de DA non atomique : orpheline + doublon au nouvel essai | ACHT63 |
| C-ACHT-062 | CFRONT-9 | C13 | S3 | STATIQUE | Action groupée chantiers : « N mis à jour » même si tout est refusé | ACHT64 |
| C-ACHT-063 | CFRONT-10 | C13 | S3 | STATIQUE | Routes mortes /btp-chantier/* et paramètre ?installation= non lu | ACHT65 |
| C-ACHT-064 | CFRONT-11 | C3 | S3 | REPRO | Alerte « Devis modifié » : jumeau local de _freeze_bom, fausse alerte sur devis à 2 options | ACHT40, ACHT66, ACHT67 |
| C-ACHT-065 | CFRONT-12 | C8 | S3 | REPRO | Page publique du compte-rendu : photos vers un endpoint authentifié (401) | ACHT68 |
| C-ACHT-066 | CFRONT-13 | C2 | S2 | REPRO | Outbox terrain : toute erreur HTTP traitée comme réseau, file bloquée sans échec visible | ACHT69 |
| C-ACHT-067 | CFRONT-14 | C2 | S3 | STATIQUE | Checklist hors-ligne : la série saisie est effacée et jamais synchronisée | ACHT40, ACHT70, ACHT71 |
| C-ACHT-068 | COUT-1+COUT-2+COUT-3 | C3 | S2 | REPRO | Retour d'outillage sans notion de prêt : statuts écrasés, double prêt, re-confirmation périmée | ACHT72 |
| C-ACHT-069 | COUT-4+COUT-8+COUT-10 | C3 | S2 | REPRO | Suppression de référentiels en usage acceptée (outil, étape, équipe, champ / gabarit de fiche) | ACHT73, ACHT77 |
| C-ACHT-070 | COUT-5 | C2 | S2 | REPRO | Prochaine calibration jamais dérivée hors « calibrer » ; badge et filtre contradictoires | ACHT74 |
| C-ACHT-071 | COUT-6 | C3 | S3 | REPRO | Notification de calibration morte (type d'événement non déclaré) | ACHT75 |
| C-ACHT-072 | COUT-7 | C4 | S3 | REPRO | Doublon de clé / nom dans six écrans de paramètres chantier = 500 | ACHT76, ACHT77 |
| C-ACHT-073 | COUT-9 | C9 | S3 | REPRO | Modèle de checklist : ajout rétroactif (même sur clôturé), renommage jamais propagé | ACHT78, ACHT95 |

## 6. Constats OPTIONNELS (hors tâches)

- QC : exiger une photo pour un item photo_requise (le service accepte photo, la vue ne la transmet pas, l'écran AteliersPage n'en envoie pas) — demande un envoi de fichier côté écran (CKIT-11).
- Image de la signature dans le JSON de la page publique du compte-rendu (intervention_rapport_public_payload) + rendu dans InterventionRapportPublicPage.jsx : contrat M0 + moitié front (CINT-3 ; nom et date déjà servis).
- Garde de classe : un test qui échoue si un lecteur chantier (stock, kitting) relit devis.lignes au lieu de la nomenclature gelée (action corrective CACH-1).
- Étendre la garde ASTK14 (masquage des prix d'achat) au routeur installations (propriétaire stock ; CACH-10).
- marquer_commandee sans BCF laisse l'engagement budgétaire actif au lieu de consommé (statique, frère CACH-6).
- Dérogation tracée d'un saut de statut chantier par un Directeur (règle non décidée ; ACHT2 refuse tout saut).
- Ordre d'assemblage planifié → terminé sans démarrer (règle à trancher ; CKIT-2).
- Dates de jalon chantier (date_mise_en_service, date_reception) inscriptibles en PATCH : écriture écran non vérifiée (frère CCRE-5).
- Inscrire annule, motif_annulation, bom, devis, bon_commande, facture_id, rdv_*, arrivee_dans_fenetre dans la liste déclarative ASEC19 (PLAN_AUDIT_SECURITE).
- Défense en profondeur dans apps/sav/pdf.py : n'accepter qu'une data-URL comme <img src> (propriétaire sav ; CINT-2).
- Motif obligatoire et dialogue de réouverture d'une intervention ; dialogue de motif de re-signature à l'écran d'intervention (CINT-4, CINT-9).
- Reprise des données démo : société 6, 5 chantiers « receptionne » portant 12 réservations actives non consommées (CCRE-2, lecture CAAT).
- seed_reservations_assemblage (services.py:3448) peut réactiver une réservation libérée par F11 (non sondé, frère CCRE-1).
- Lien OrdreAssemblage.chantier jamais posé par depuis-devis ni lu ailleurs (frère CKIT-8).
- RetourLivraisonLigne / RetourMaterielLigne modifiables selon leur propre statut (non sondés, frère CKIT-4).
- BL du module documents (documents/builders.py) : adresse de livraison non vérifiée (frère CKIT-7).
- Remise en brouillon d'une DA soumise (geste à vérifier, utile après ACHT12).
- CFRONT-15 (S4 au verdict) : SignatureLivraisonDialog filtre les champs vides (SignatureLivraisonDialog.jsx:38-47) ; vider fonction / société / co-signataire est ignoré ; latent tant que la re-signature est bloquée — à faire dans l
- RecettePompage.instrument_id (CharField libre, models_chantier.py:491, serializers_commissioning.py:244) : aucune validation société ; non rendu au portail, non sondé (frère de CREC-1).
- ParcInstallePage.jsx:74 (RapportEnergieModal) : vérifier que le 400 d'ACHT49 est lu dans la réponse blob et affiché.
- Rapport de production : rendement par défaut 1 600 kWh/kWc au lieu de la production du devis accepté (D-ACAL « production client = celle du devis ») — non sondé.
- Réception annulée puis refaite : _stamp_statut_dates ne re-pose pas date_reception (garantie calée sur la première réception) — non sondé.
- Reprise des données de production : équipements de prestation déjà au parc et relevés de série en conflit — rapport en lecture seule puis dry-run (règle « re-confirmer les réparations visibles client »).
- Recalcul de date_prochaine_calibration des outils existants (ACHT74 ne recalcule qu'à la prochaine écriture).
- DA : refus serveur de soumettre une demande sans ligne (aggravant de CFRONT-8, views/demande_achat.py) ; endpoint d'écriture imbriquée demande + lignes.
- Motifs de dérogation au glisser Kanban et dans les actions groupées (frère de CFRONT-4).
- Garde frontend générique : toute cible statique de navigate() doit être une route enregistrée (classe de CFRONT-10).
- frontend/src/pages/parametres/KitsSection.jsx:43 (getOutils() page 1, propriétaire stock) et stockApi.getEmplacements() sans page (OutillagePage.jsx:95).
- Garde statique interdisant user.is_responsable dans apps/*/views (allowlist décroissante, propriétaire scripts = deploy) — classe de CTEN-6 hors J2 (reporting, stock, roles).
- Extension du balai runtime backend/django_core/tests/test_tenant_sweep.py aux ids étrangers dans le corps (propriétaire sécurité) — classe de CTEN-4.
- /installations/sync/ refuse (403) un compte « technicien hérité » sans palier responsable alors qu'il lit les interventions : décider si ce profil terrain doit synchroniser (CFRONT-13).
- Interventions annulées dans conflits_affectation et planning_camionnettes (selectors.py:1140, :1351) : filtrer par Intervention.objects.actives() (ACHT51) — non sondé ; selectors.py est un producteur PACT11, à poser dans une tâche
- Agrégats nominatifs (plan-de-charge, conflits-affectation, nivellement-charge, planning-camionnettes, taux-ponctualite) : portée équipe à sonder ; gelés dans le passif d'ACHT79.

## 7. Vérification adversariale (phase 5)

- **Porte empirique** : 8 vérificateurs frais opus/high, sondes par endpoints réels en transactions annulées (`j2/sondes/`),
  non-persistance prouvée ; 0 réfuté sur 85 ⇒ seconde lentille sur les S1 (ci-dessus). Prévalence locale des S1 : 0 cas réel
  (défauts latents atteignables depuis l'écran) ; prod non consultée pour cette unité.
- **Fable** : aucun appel (L2).

## 8. Non-risques consignés

- Sans geste intermédiaire, F11 puis « Installé » sort exactement la quantité vendue (témoin des sondes : 10 et 1).
- `Equipe.chef` et `ProjetTache.assigne` refusent un utilisateur d'une autre société (400) ; les sérialiseurs
  `EtapeApprobationAchat` et `RevisionKit` sont en lecture seule.
- Étapes CH2 amorcées : un saut vers « réceptionné » sans recette ni check-list est refusé (400).

## 9. Conclusion (phase 6)

- **Couverture.** 8 surfaces ; 4 détecteurs verts ; 85 constats reproduits, 4 S1 repassés en seconde lentille ; live : 8 écrans.
  **Non couvert** : jeu `anon`, prévalence prod, interventions en écran (aucune en démo).
- **Ce qui ne tient pas** : le stock d'un chantier peut sortir deux fois (V2, réactivation, BC confirmé, reserver-stock après une
  pose terrain) ; le serveur laisse sauter « Installé » (le matériel posé ne sort jamais) ; des clés étrangères d'une autre
  société sont acceptées dans 6 champs et l'outil d'étalonnage d'une autre société est lisible ; et 66 autres constats S2/S3
  (tableau §5).
- **Registre** : J2 → `audité`, groupe `ACHT`, **84 tâches** : `PLAN_AUDIT_CHANTIERS.md` 76 · `PLAN_AUDIT_SAV.md` 3 · `PLAN_AUDIT_STOCK.md` 2 · `PLAN_AUDIT_LEAD.md` 1 · `PLAN_AUDIT_DEPLOY.md` 1 · `PLAN_AUDIT_TRANSVERSE.md` 1.
- **Coût.** Scout 1 (haiku) ; lanes 8 (CCRE, CTEN opus/high ; 6 sonnet/medium) ; vérificateurs 8 (opus/high) ; seconde lentille 1
  (opus/high) ; rédacteurs 2 (opus/high) ; ≈ 5,0 M jetons de sous-agents ; Fable : aucun.
