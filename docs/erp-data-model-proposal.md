# Proposition — Modèle de données ERP TAQINOR

**Pour : Reda (fondateur)**
**Date : 2026-06-13**
**Nature : document de réflexion / feuille de route. Aucune ligne de code n'est modifiée ici.**

> Ce document fait l'inventaire honnête de ce que notre base de données sait
> faire aujourd'hui, de ce qui manque pour piloter une entreprise d'installation
> solaire au Maroc de bout en bout (du lead jusqu'au SAV 20 ans plus tard), et
> propose un ordre de construction. Les noms de champs restent en forme « code »
> (ex. `puissance_souscrite_kva`) pour que la session technique suivante puisse
> les reprendre tels quels. Le reste est en langage simple.

---

## 1. Résumé exécutif — les plus gros trous, classés par impact commercial

Aujourd'hui le système s'arrête **à la signature**. Tout ce qui fait gagner ou
reperdre un client *après* la vente (le chantier, la mise en service, la
garantie, le SAV) n'existe nulle part. Voilà les manques classés par ce qu'ils
coûtent réellement.

1. **Aucun modèle Installation / Projet / Chantier.** Une fois le devis signé,
   plus rien ne suit le dossier. Pas de planning de pose, pas de statut
   « installé / en service », pas d'historique de réalisation. C'est le trou
   numéro un : sans lui il n'y a pas d'« après-vente » possible. *Impact : on ne
   sait pas dire à un client où en est son chantier.*

2. **Aucun parc équipements avec numéros de série.** On ne sait pas quels
   panneaux/onduleurs/batteries (avec leur n° de série, marque, date de pose)
   sont physiquement chez quel client. *Impact direct : impossible de gérer une
   réclamation de garantie fabricant — c'est le n° de série qui ouvre le
   dossier. C'est de l'argent qu'on laisse au fabricant.*

3. **Aucun SAV / ticket de maintenance.** Pas de demande d'intervention, pas de
   suivi panne→réparation, pas de maintenance préventive (nettoyage,
   contrôle annuel). *Impact : la maintenance est un revenu récurrent qu'on ne
   peut ni vendre ni facturer aujourd'hui.*

4. **Aucun cycle de vie de garantie.** La garantie produit (`Produit.garantie`)
   est un simple texte sur le catalogue ; rien ne calcule une date d'expiration
   par équipement posé. *Impact : on ne peut pas alerter avant la fin de
   garantie, ni prouver une couverture.*

5. **Aucun suivi de mise en service / conformité 82-21.** La régularisation
   Loi 82-21 est un simple `regularisation_8221` (oui/non) sur le lead. Le
   décret d'application est paru le 09/03/2026 : il y a désormais une vraie
   procédure (convention de raccordement, capacité réseau, basse/moyenne
   tension). *Impact : c'est une obligation réglementaire qui devient un
   argument de vente — « on gère votre raccordement ONEE ».*

6. **Profil société non conforme Maroc.** `CompanyProfile` porte `siret`
   (France) et `tva_intra` (UE), inutiles ici, et **n'a pas** ICE/IF/RC/Patente/
   CNSS. *Impact : nos factures ne sont pas pleinement conformes — l'ICE
   vendeur est obligatoire sur facture depuis 2016, l'ICE client en B2B depuis
   2019.*

7. **`puissance souscrite` / abonnement ONEE en texte libre.** Donnée
   technique clé (dimensionnement, 82-21, mono/triphasé) coincée dans
   `Lead.tranche_onee` (texte libre). *Impact : impossible de filtrer, de
   dimensionner proprement, ou de faire des statistiques.*

8. **Aucun système de champs personnalisés.** Chaque besoin métier nouveau de
   Reda exige aujourd'hui une intervention développeur. *Impact : l'outil ne
   peut pas évoluer sans nous — c'est le sujet de la session prochaine.*

**À noter (déjà résolu cette session) :** la facturation et les **paiements**
sont en cours de construction ce soir (modèle `Paiement`, FK directe
`Devis→Facture`, acompte/échéancier piloté par `PAYMENT_TERMS_BY_MODE`). On
**construit dessus**, on ne les re-propose pas.

---

## 2. Méthode & sources

J'ai lu le code actuel (cité avec chemins/lignes plus bas, source de vérité)
puis recherché les modèles de données de référence des ERP matures de
field-service et solaire, et les spécificités marocaines.

ERP / FSM de référence :
- Odoo Field Service (FSM) — classification des tâches (Installation / Repair /
  Diagnostic / Preventive Maintenance / RMA), work orders, worksheets :
  https://apps.odoo.com/apps/modules/18.0/bb_fsm et
  https://www.odoo.com/app/maintenance
- Odoo Maintenance — registre d'équipements (n° série + date d'expiration de
  garantie), demandes préventives/correctives, MTBF/MTTR :
  https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/maintenance/maintenance_setup.html
  et https://www.cybrosys.com/blog/how-to-manage-preventive-and-corrective-maintenance-in-odoo-17-maintenance-app
- Odoo Studio / champs personnalisés — `ir.model.fields`, préfixe
  `x_studio_`, propriétés stockées en JSONB :
  https://www.odoo.com/documentation/19.0/applications/studio/fields.html et
  https://www.dasolo.ai/blog/odoo-data-api-5/custom-fields-odoo-guide-131

Solaire — traçabilité & garanties :
- Blu Banyan, suivi d'actifs solaires en ERP (créer l'« asset planifié » dès
  l'achat) : https://blubanyan.com/solar-asset-tracking-best-practices-cloud-erp/
- Scanflow, pourquoi le n° de série panneau pilote les réclamations de
  garantie : https://www.scanflow.ai/solar-serial-traceability-warranty-claims/
- Modèle de registre d'actifs (ID, marque/modèle, n° série, date d'achat,
  expiration garantie, criticité) :
  https://oxmaint.com/industries/manufacturing-plant/equipment-asset-register-template-manufacturing-free-excel

Maroc — fiscalité & énergie :
- Identifiants entreprise ICE/IF/RC/TP(Patente)/CNSS et obligation ICE sur
  facture : https://clicpaie.ma/blogs/ice-maroc/ et
  https://creation-entreprise-casablanca.com/numeros-dentreprise-au-maroc/
- Loi 82-21 (autoproduction), décret d'application publié au BO le 09/03/2026,
  raccordement BT/MT pour 11 kW–5 MW, capacité réseau ONEE/ANRE :
  https://medias24.com/2025/10/28/lautoproduction-electrique-au-maroc-une-revolution-au-ralenti
  et https://www.les-energies-renouvelables.eu/article/actualites/energies/produire-sa-propre-electricite-au-maroc-les-nouvelles-regles-du-solaire-475/

> Note : je n'ai pas copié ces modèles. Odoo sépare CRM / Vente / Stock /
> Compta / Projet / FSM / Maintenance en briques distinctes mais reliées ;
> nous suivrons le même principe d'**entités reliées plutôt que de gros
> champs fourre-tout**, en restant adaptés au solaire marocain.

---

## 3. Analyse par module

Légende des décisions :
- 🚪 **Porte à sens unique (irréversible)** — un choix de structure difficile à
  défaire une fois qu'il y a des données en production. À trancher avec soin.
- 🔁 **Réversible** — un ajout de champ/option qu'on peut changer plus tard sans
  douleur.

---

### 3.1 CRM / Leads

**(a) Ce qui existe déjà.** `apps/crm/models.py` — `Lead` est déjà très riche :
contact complet (nom/prénom/société/email/téléphone/whatsapp/adresse/ville/
GPS), pipeline (stage depuis `STAGES.py`, owner, canal, priorité, tags,
motif_perte, relance, type_installation), profil énergie
(facture hiver/été, conso, `tranche_onee`, raccordement mono/triphasé,
`regularisation_8221`), pompage (cv/hmt/débit), toiture, visite, et intake
site web (utm_*, fbclid, consent). Chatter `LeadActivity` (création/
modification/note). Très bon socle, au-dessus de la moyenne des CRM solaires.

**(b) Manques classés.**
1. **`tranche_onee` à structurer** (voir module Conformité). Texte libre =
   inexploitable en stats/dimensionnement. *Commercial : segmenter et
   dimensionner juste.*
2. **Pas de score / probabilité de closing** ni de **valeur estimée** du lead.
   *Commercial : prioriser l'effort commercial, prévoir le CA.*
3. **Pas de lien lead → concurrent / source de perte structurée** (motif_perte
   existe en texte ; manque « perdu au profit de qui / à quel prix »).
   *Commercial : comprendre pourquoi on perd.*
4. **Pas de rendez-vous/tâches datés** reliés au lead (la visite est un seul
   champ). *Commercial : ne rien laisser tomber dans les mailles.*

**(c) À l'écran vs caché.** À l'écran : pipeline, relance, contact, facture
moyenne, type d'installation. À cacher/replier par défaut : utm_*/fbclid/
fbclid/consent (techniques, utiles seulement au marketing) et les champs
toiture détaillés (les ouvrir au moment de l'étude).

**(d) Décisions.** Restructurer `tranche_onee` → 🚪 (migration de données
existantes à prévoir, on ne garde pas deux formats). Ajout score/valeur → 🔁.

---

### 3.2 Contacts / Clients

**(a) Existe.** `crm.Client` (nom, prénom, email unique par société,
téléphone, adresse, **ice**). Le client est résolu depuis le lead via
`apps/crm/services.resolve_client_for_lead` (pas de doublon).

**(b) Manques classés.**
1. **Pas de distinction Particulier / Entreprise** sur le client. Une
   entreprise a un ICE/IF/RC, un particulier a une CIN. *Commercial :
   facturation B2B conforme, et le client résidentiel n'a pas d'ICE.*
2. **Pas d'adresses multiples** (facturation ≠ site d'installation). Très
   fréquent : on facture le siège, on pose à l'usine/à la ferme.
   *Commercial : indispensable dès le premier client multi-sites.*
3. **Pas de contacts multiples** par client entreprise (acheteur, technique,
   comptable). *Commercial : B2B sérieux.*
4. **Champs Maroc manquants** : `if_fiscal`, `rc`, `cin` (particulier).

**(c) À l'écran vs caché.** Particuliers : masquer ICE/IF/RC ; afficher CIN.
Entreprises : l'inverse. Adapter le formulaire au `type_client`.

**(d) Décisions.** Adresse de site séparée → 🚪 (le site d'installation
deviendra la clé du parc équipements et du SAV ; à modéliser proprement
maintenant). `type_client` → 🔁.

---

### 3.3 Fournisseurs / Achats

**(a) Existe.** `stock.Fournisseur` (nom, contact, email, téléphone, adresse).
`Produit.fournisseur` (FK) et `Produit.prix_achat`.

**(b) Manques classés.**
1. **Aucun bon de commande fournisseur / approvisionnement.** On achète des
   panneaux mais rien ne le trace côté achat. *Commercial : marge réelle,
   gestion de trésorerie, délais d'appro qui conditionnent la date de
   chantier.*
2. **Pas de réception de marchandise → n° de série.** C'est ici, à la
   réception, qu'on devrait saisir les n° de série (cf. Blu Banyan : créer
   l'actif dès l'achat). *Commercial : socle de la garantie.*
3. **Fournisseur sans identifiants Maroc** (ICE) ni conditions de paiement.
4. **Pas de multi-fournisseur par produit** ni d'historique de prix d'achat.
   *Commercial : acheter au meilleur prix.*

**(c) À l'écran vs caché.** Garder `prix_achat` **strictement interne** (déjà
la règle : indicateur de marge générateur uniquement, jamais sur PDF client).

**(d) Décisions.** Modèle d'achat (PO + réception) → 🚪 si on veut qu'il
alimente le stock et le parc série ; gros morceau, à phaser.

---

### 3.4 Catalogue / Produits / Stock

**(a) Existe.** `stock.Produit` très complet (sku, prix achat/vente, stock,
seuil, catégorie, fournisseur, tva, marque, garantie, archivage, **champs
pompage** cv/hmt/débit/kw/tension, `courbe_pompe` JSON). `Categorie`,
`MouvementStock` (entrée/sortie/transfert/ajustement avec
quantité_avant/après).

**(b) Manques classés.**
1. **Produit « suivi en série » vs « en vrac ».** Un panneau/onduleur doit être
   suivi à l'unité (série) ; les câbles/vis non. Manque un flag
   `suivi_serie`. *Commercial : prérequis du parc équipements.*
2. **Garantie en texte libre** (`garantie`) au lieu d'une **durée structurée**
   (`garantie_mois`, + garantie de production séparée pour les panneaux,
   souvent 25 ans). *Commercial : calcul automatique d'expiration.*
3. **Fiche technique structurée** (puissance Wc, tension, courant, dimensions)
   éparpillée/absente — utile au dimensionnement et au SAV.
4. **Pas de multi-entrepôt** (`MouvementStock` n'a pas de lieu). *Commercial :
   stock par dépôt/véhicule.*

**(c) À l'écran vs caché.** Cacher prix_achat (interne). Les pompes sans prix
restent grisées « prix à renseigner » (déjà géré).

**(d) Décisions.** `suivi_serie` + `garantie_mois` → 🔁 (ajouts de champs).
Multi-entrepôt → 🚪 (touche tous les mouvements de stock).

---

### 3.5 Devis

**(a) Existe.** `ventes.Devis` (réf, client, **lead** FK, statut
brouillon/envoyé/accepté/refusé/expiré, validité, taux_tva, remise,
**mode_installation** résidentiel/industriel/agricole, **etude_params** JSON,
prix_cible_kwc) + `LigneDevis` avec **TVA par ligne** (réforme 10/20 %,
`ventes/models.py:124`). Statuts préservés 1:1, séparés du funnel STAGES.

**(b) Manques classés.**
1. **mono/triphasé absent du devis.** L'info vit sur `Lead.raccordement` et
   `Produit.tension_v`, jamais figée sur le devis vendu. *Commercial : c'est un
   engagement technique ; doit être gelé au devis, pas seulement au lead.*
2. **Pas de versionnage de devis** (révisions A/B/C). Aujourd'hui on recrée.
   *Commercial : suivre les négociations proprement.*
3. **Pas de date d'acceptation / signature** stockée (qui a signé, quand).
4. **Pas de conditions de garantie/installation** texte par devis (clauses).

**(c) À l'écran vs caché.** Garder l'écran de création 100 % TTC, `noValidate`,
`step="any"` (règle d'or : ne jamais rejeter une valeur tapée — voir mémoire).

**(d) Décisions.** Geler `raccordement` sur le devis → 🔁. Versionnage → 🚪
(change la clé de référence / l'unicité).

---

### 3.6 Commandes (Bons de commande)

**(a) Existe.** `ventes.BonCommande` (réf, **devis OneToOne**, client, statut
en_attente/confirmé/livré/annulé, date_livraison_prevue). **Pas de lignes
propres** — il s'appuie sur les lignes du devis.

**(b) Manques classés.**
1. **Pas de lignes de commande propres** : si la pose diffère du devis (un
   panneau substitué, une quantité ajustée sur chantier), on ne peut pas le
   refléter. *Commercial : la réalité chantier diverge souvent du devis.*
2. **Pas de lien commande → chantier/planning.** Le BC dit « livré » mais rien
   ne dit « installé ». *C'est le pont manquant vers le module Installation.*

**(c) À l'écran.** Le BC est surtout interne/logistique ; le garder simple.

**(d) Décisions.** Lignes propres au BC → 🚪 (duplication contrôlée du modèle
de lignes). À trancher : soit le BC reste un miroir du devis (simple), soit il
devient le document de vérité de ce qui est réellement posé (puissant mais plus
lourd). **Recommandation : le faire pointer vers l'Installation plutôt que de
dupliquer les lignes.**

---

### 3.7 Facturation / Paiements — *en cours (cette session)*

**(a) Existe / en cours ce soir.** `ventes.Facture` (réf, **bon_commande
OneToOne**, client, statut brouillon/émise/payée/en_retard/annulée, échéance,
taux_tva, remise) + `LigneFacture`. **Ajouts cette session** : modèle
`Paiement` (montant/date/mode/référence contre une Facture), **FK directe
Devis→Facture**, champs acompte/échéances sur Facture, échéancier piloté par
`PAYMENT_TERMS_BY_MODE` (résidentiel/agricole 30/60/10, industriel 50/40/10).
On **construit dessus**.

**(b) Manques restants classés.**
1. **`LigneFacture` n'a pas de TVA par ligne** alors que `LigneDevis` oui
   (`ventes/models.py:264-291`). *Trou connu : une facture issue d'un devis
   mixte 10/20 % ne peut pas reproduire fidèlement la TVA.* **À corriger en
   priorité** (cohérence avec le devis).
2. **Facture d'avoir / annulation** (note de crédit) absente. *Commercial :
   obligation comptable dès qu'on annule une facture émise.*
3. **Numérotation conforme** : utiliser `apps/ventes/utils/references.py`
   (jamais count()+1 — déjà la règle).

**(c) À l'écran.** Échéancier et reste-à-payer bien visibles (c'est le nerf de
la trésorerie).

**(d) Décisions.** Ajouter `taux_tva` sur `LigneFacture` → 🔁 (aligner sur
`LigneDevis`). Avoir/note de crédit → 🔁 (nouveau statut/modèle additif).

---

### 3.8 Installations / Projets / Mise en service — **NOUVEAU MODULE**

> C'est le chaînon manquant le plus important. Tout le « après-vente » s'y
> accroche. Inspiré d'Odoo FSM/Project : un **Projet** (le chantier) contenant
> des **interventions** (work orders).

**(a) Existe.** Rien. Le système s'arrête au BC/Facture.

**(b) Entités proposées (classées).**
1. **`Installation` / `Projet`** (le dossier chantier). Champs proposés :
   `company` FK, `client` FK, `site` (adresse de pose, cf. 3.2),
   `devis`/`bon_commande` FK, `statut` (à planifier → planifié → en cours →
   posé → en service → clôturé), `date_pose_prevue`, `date_pose_reelle`,
   `date_mise_en_service`, `puissance_installee_kwc`, `raccordement`
   (mono/tri — gelé ici), `technicien_responsable` FK user, GPS, notes,
   chatter. *Commercial : sans ça, on ne sait pas dire « où en est mon
   chantier ». C'est la colonne vertébrale du SAV et de la garantie.*
2. **`Intervention` / `WorkOrder`** rattachée au Projet : `type` (pose,
   raccordement, mise en service, contrôle, dépannage), `date_prevue`,
   `date_realisee`, `technicien`, `compte_rendu`, photos. *Commercial :
   planning terrain + traçabilité.*
3. **`MiseEnService`** (ou statut+champs dédiés sur Installation) :
   date, PV de mise en service, mesures (production test, tension), conformité
   82-21 (cf. module Maroc). *Commercial : preuve de bonne fin + déclenche le
   départ des garanties.*

**(c) À l'écran vs caché.** Vue planning (calendrier) en avant. Détails
techniques (mesures) repliés sauf pour les techniciens.

**(d) Décisions.** 🚪 **fortement irréversible** : choisir maintenant que
l'**Installation** est l'objet pivot auquel s'accrochent parc équipements,
garanties et tickets SAV. Ne pas accrocher le SAV directement à la Facture (la
Facture est comptable, pas physique). C'est LE choix de structure du projet —
à trancher avec Reda avant de coder.

---

### 3.9 SAV / Maintenance — **NOUVEAU MODULE**

> Inspiré d'Odoo Maintenance : préventif (planifié, récurrent) vs correctif
> (panne). Source de revenu récurrent.

**(a) Existe.** Rien.

**(b) Entités proposées (classées).**
1. **`TicketSAV` / `DemandeIntervention`** : `company`, `client`,
   `installation` FK (3.8), `equipement` FK (3.10) optionnel, `type`
   (correctif/préventif), `statut` (nouveau → planifié → en cours → résolu →
   clôturé), `priorite`, `description`, `technicien`, `date_ouverture`,
   `date_resolution`, `sous_garantie` (bool calculé), `cout`, chatter.
   *Commercial : structure le service après-vente — réputation + revenu.*
2. **`ContratMaintenance`** (préventif récurrent) : périodicité (annuelle…),
   prochaine échéance, prix, génère automatiquement des tickets préventifs.
   *Commercial : du revenu récurrent prévisible — un contrat d'entretien
   annuel par centrale posée.*
3. **Métriques** (à terme, comme Odoo) : délai moyen de résolution, nombre
   d'interventions par installation.

**(c) À l'écran vs caché.** File de tickets ouverts en avant ; échéances de
maintenance préventive en alerte (comme les relances lead).

**(d) Décisions.** Le ticket pointe vers `installation` (et idéalement
`equipement`) → 🚪 (dépend du choix 3.8). `ContratMaintenance` → 🔁 (additif
ultérieur).

---

### 3.10 Parc équipements / Garanties — **NOUVEAU MODULE**

> Le registre physique : quel matériel, avec quel n° de série, posé où, sous
> garantie jusqu'à quand. C'est ce qui transforme une réclamation de garantie
> fabricant en argent récupéré (Scanflow : le n° de série pilote la
> réclamation).

**(a) Existe.** Rien au niveau unitaire. `Produit.garantie` est un texte
catalogue (le *modèle*), pas l'unité posée.

**(b) Entités proposées (classées).**
1. **`Equipement`** (l'unité physique posée) : `company`, `produit` FK (le
   modèle), `numero_serie`, `installation` FK (3.8), `date_pose`,
   `date_fin_garantie` (calculée depuis `Produit.garantie_mois`),
   `date_fin_garantie_production` (panneaux, ~25 ans), `statut` (en service /
   remplacé / hors service). *Commercial : impossible de réclamer une garantie
   sans le n° de série — c'est de l'argent laissé au fabricant. Et ça permet
   un rappel « votre onduleur sort de garantie dans 3 mois » (vente de
   prolongation/remplacement).*
2. **Saisie des n° de série au bon moment** : idéalement à la réception
   fournisseur (3.3) ou à la pose (3.8), via scan code-barres/QR (Blu Banyan).
3. **`EvenementGarantie`** : réclamation, remplacement, lien au ticket SAV.

**(c) À l'écran vs caché.** Sur la fiche client/installation : liste du
matériel posé + compteurs « jours restants de garantie ». Saisie n° série
réservée aux techniciens.

**(d) Décisions.** Modéliser `Equipement` comme entité à part (pas un champ
JSON sur l'installation) → 🚪 : on veut interroger « tous les onduleurs
modèle X sous garantie » → c'est une vraie table indexée, pas du JSON.
Recommandé.

---

### 3.11 Conformité Maroc / ONEE / 82-21

**(a) Existe.** `Lead.raccordement` (mono/triphasé), `Lead.tranche_onee`
(texte libre), `Lead.regularisation_8221` (booléen). `Client.ice`. C'est tout.

**(b) Manques classés.**
1. **`puissance_souscrite_kva` + `type_abonnement` structurés** (au lieu de
   `tranche_onee` texte). *Commercial : dimensionnement juste, éligibilité
   82-21, statistiques.*
2. **Workflow 82-21 réel** (le booléen ne suffit plus depuis le décret du
   09/03/2026) : statut de démarche (à déposer → déposé → convention de
   raccordement → autorisé), niveau de tension (BT/MT — seuil clé 11 kW–5 MW),
   documents (convention, autorisation), dates. *Commercial : argument de vente
   « on gère votre raccordement ONEE » + obligation réglementaire.*
3. **mono/triphasé** propagé du lead → devis → installation (aujourd'hui mort
   sur le lead seulement).
4. **Identifiants société Maroc** sur `CompanyProfile` (voir 3.13).

**(c) À l'écran vs caché.** Bloc « Raccordement & 82-21 » visible dès qu'une
installation dépasse le seuil concerné ; masqué pour les petites installs
résidentielles non concernées.

**(d) Décisions.** Remplacer `tranche_onee` texte par champs structurés → 🚪
(migration des leads existants). Workflow 82-21 → 🔁 (additif, on peut enrichir
les statuts au fil des décisions ANRE).

---

### 3.12 Utilisateurs / Rôles / Sociétés

**(a) Existe.** `authentication.Company` (multi-tenant, tout est scopé par
société). `CustomUser` (role_legacy admin/responsable/normal + `role` FK,
company, phone, address). `roles.Role` (permissions JSON list, est_systeme).
Codes perm : stock_*, crm_*, ventes_*, parametres_*, users_*, roles_gerer,
reporting_voir. Socle propre.

**(b) Manques classés.**
1. **Pas de permissions pour les nouveaux modules** (installation_*,
   sav_*, equipements_*). À ajouter quand ils naîtront. *Commercial : un
   technicien voit le SAV mais pas la marge.*
2. **Pas de notion d'équipe / technicien terrain** distincte (utile au
   planning d'interventions).
3. **Pas de journal d'audit transverse** (le chatter existe sur le lead
   seulement).

**(c) À l'écran vs caché.** Masquer aux techniciens tout ce qui touche
prix_achat/marge.

**(d) Décisions.** Étendre la liste de permissions → 🔁. Garder le scoping
`company` partout (règle non négociable du repo).

---

### 3.13 Paramètres / Profil société

**(a) Existe.** `parametres.CompanyProfile` — `nom/adresse/email/telephone`,
**`siret`** (France ❌), **`tva_intra`** (UE ❌), rib, banque, couleur, logo,
signature (`parametres/models.py:21-22`).

**(b) Manques classés.**
1. **Identifiants Maroc absents** : `ice`, `if_fiscal`, `rc`, `patente`/
   `taxe_professionnelle`, `cnss`. *Commercial/légal : l'ICE vendeur est
   obligatoire sur facture depuis 2016 ; sans ces champs nos PDF ne sont pas
   pleinement conformes.*
2. **`siret`/`tva_intra` morts** (inutiles au Maroc) — à retirer ou réaffecter.

**(c) À l'écran.** Ces identifiants doivent apparaître en pied de facture PDF.

**(d) Décisions.** Ajouter les champs Maroc → 🔁. Retirer/renommer
`siret`/`tva_intra` → 🔁 (peu/pas de données réelles dedans). **Conseil :
ajouter les champs Maroc maintenant, garder siret/tva_intra inertes le temps
d'une migration douce.**

---

### 3.14 Reporting

**(a) Existe.** Pas de modèle (agrégats calculés). Permission `reporting_voir`.

**(b) Manques classés.** Tout dépend des modules ci-dessus : une fois
Installation/SAV/Parc en place, les rapports à forte valeur deviennent
possibles — **CA par étape**, **taux de transformation lead→signé**, **marge
réelle** (prix_achat vs vente), **interventions sous garantie vs payantes**,
**puissance kWc installée / mois**. *Commercial : piloter au lieu de deviner.*

**(c)/(d)** Réversible par nature (lecture seule). À traiter en dernier.

---

## 4. Système de CHAMPS PERSONNALISÉS (session prochaine)

**Le besoin de Reda.** Pouvoir ajouter soi-même un champ (ex. « Numéro de
compteur ONEE » sur un lead) sans appeler un développeur, choisir s'il
s'applique à **tous** les leads, et pouvoir **cacher** un champ standard ou le
**remettre par défaut**.

### 4.1 Parcours utilisateur visé
1. Sur n'importe quel écran, bouton « + Ajouter un champ ».
2. Choix du **type** : texte, nombre, oui/non, date, liste de choix, lien vers
   un autre objet.
3. **Question de portée (scope)** — la plus importante :
   « Appliquer à **tous les leads** de la société ? » (oui = visible partout) ou
   « seulement à ce lead / cette vue ? ». Pour un ERP multi-société, la portée
   est **toujours bornée à la société** (`company`) : jamais un champ d'une
   société ne fuit chez une autre.
4. Possibilité de **masquer** un champ standard (ex. cacher « FB click id »).
5. Bouton **« Réinitialiser par défaut »** qui ré-affiche les champs standard
   masqués (et propose d'archiver, pas supprimer, les champs perso pour ne pas
   perdre de données).

### 4.2 Modèle de données proposé
Deux briques :

- **Registre de définitions** — `CustomFieldDefinition` :
  `company` FK (portée), `model_cible` (lead/client/produit/installation…),
  `code` (slug), `libelle`, `type`, `options` (pour les listes), `obligatoire`,
  `visible` (pour masquer un standard via une entrée « override »), `ordre`,
  `est_standard` (distingue un champ natif masqué d'un champ ajouté).
- **Stockage des valeurs** — deux options, voir arbitrage ci-dessous.

### 4.3 Arbitrage EAV vs JSONField — honnête
- **EAV** (une table `CustomFieldValue` : objet + définition + valeur) :
  *avantage* requêtable/indexable proprement (« tous les leads où compteur =
  X »), typage par colonne. *Inconvénient* plus de tables, jointures, plus
  complexe à coder.
- **JSONField par enregistrement** (un champ `custom_data` JSON sur chaque
  objet, comme `Lead.etude_params` déjà utilisé) : *avantage* simple, zéro
  jointure, on a déjà ce pattern dans le repo. *Inconvénient* recherche/tri/
  index plus pénibles (Postgres JSONB aide mais reste moins net que des
  colonnes).

**Ce que fait Odoo** (référence) : champs personnalisés = vraies colonnes via
`ir.model.fields` (préfixe `x_studio_`), et JSONB seulement pour les
propriétés/traductions. C'est le plus robuste mais le plus lourd à reproduire.

**Recommandation pragmatique pour TAQINOR** : commencer par **JSONField
`custom_data` par enregistrement** + le registre de définitions pour piloter
l'affichage/validation. Simple, cohérent avec l'existant (`etude_params`),
suffisant pour 90 % des besoins (affichage, saisie, PDF). Réserver l'EAV (ou
de vraies colonnes générées) au jour où on aura besoin de **filtrer/rapporter
en masse** sur un champ perso. **C'est réversible** : on peut migrer du JSON
vers des colonnes plus tard ; l'inverse aussi.

### 4.4 Décisions
- Portée bornée à `company` → 🚪 (choix de sécurité multi-tenant, à ne jamais
  relâcher — règle non négociable du repo).
- JSONField d'abord → 🔁 (migrable vers EAV/colonnes ensuite).
- « Masquer » = override dans le registre, jamais supprimer le champ standard du
  code → 🔁 (toujours réversible via « réinitialiser »).
- Ne **jamais supprimer** les valeurs perso quand on retire un champ : archiver
  → 🚪 en pratique (perte de données si on supprime ; donc archiver).

---

## 5. Feuille de route — classement importance × effort

Échelles : Importance commerciale (★1–5), Effort de construction (◆1–5,
plus = plus lourd). Ordre conseillé regroupé en sessions.

| # | Chantier | Module | Import. | Effort | Type | Session conseillée |
|---|----------|--------|:------:|:------:|------|------|
| 1 | TVA par ligne sur `LigneFacture` (aligner sur LigneDevis) | Facturation | ★★★★★ | ◆ | 🔁 | **S1 — finir l'existant** |
| 2 | Identifiants Maroc sur `CompanyProfile` (ICE/IF/RC/Patente/CNSS) | Paramètres | ★★★★★ | ◆ | 🔁 | **S1** |
| 3 | `type_client` + CIN/ICE conditionnels + adresse de site séparée | Clients | ★★★★☆ | ◆◆ | 🚪 | **S1** |
| 4 | Structurer `puissance_souscrite_kva` + `type_abonnement` (remplace `tranche_onee`) | Conformité | ★★★★☆ | ◆◆ | 🚪 | **S1** |
| 5 | **Modèle Installation / Projet / Chantier** (objet pivot) | Installations | ★★★★★ | ◆◆◆ | 🚪 | **S2 — le pivot** |
| 6 | `Intervention`/WorkOrder + planning | Installations | ★★★★☆ | ◆◆◆ | 🔁 | **S2** |
| 7 | Mise en service + départ des garanties | Installations | ★★★★☆ | ◆◆ | 🔁 | **S2** |
| 8 | **Parc `Equipement` + n° série + dates de garantie** | Parc/Garanties | ★★★★★ | ◆◆◆ | 🚪 | **S3 — l'après-vente** |
| 9 | Saisie n° série à la pose (ou réception) | Parc/Achats | ★★★★☆ | ◆◆ | 🔁 | **S3** |
| 10 | **`TicketSAV`** correctif/préventif (rattaché à Installation/Equipement) | SAV | ★★★★★ | ◆◆◆ | 🚪 | **S3** |
| 11 | Workflow 82-21 (statuts + documents + BT/MT) | Conformité | ★★★★☆ | ◆◆ | 🔁 | **S4** |
| 12 | **Champs personnalisés** (registre + JSONField + masquer/réinit) | Paramètres | ★★★★☆ | ◆◆◆ | 🔁 | **S4 — déjà demandé** |
| 13 | `ContratMaintenance` (préventif récurrent → revenu) | SAV | ★★★★☆ | ◆◆◆ | 🔁 | **S5** |
| 14 | Achats fournisseur (PO + réception → stock + série) | Achats | ★★★☆☆ | ◆◆◆◆ | 🚪 | **S5** |
| 15 | Permissions des nouveaux modules + équipes terrain | Rôles | ★★★☆☆ | ◆◆ | 🔁 | au fil de l'eau |
| 16 | Versionnage des devis (révisions A/B/C) | Devis | ★★★☆☆ | ◆◆◆ | 🚪 | optionnel |
| 17 | Avoir / note de crédit | Facturation | ★★★☆☆ | ◆◆ | 🔁 | optionnel |
| 18 | Multi-entrepôt / stock par dépôt-véhicule | Stock | ★★☆☆☆ | ◆◆◆ | 🚪 | plus tard |
| 19 | Score/valeur de lead, concurrent perdu | CRM | ★★☆☆☆ | ◆◆ | 🔁 | plus tard |
| 20 | Reporting avancé (transformation, marge, kWc/mois, SAV) | Reporting | ★★★☆☆ | ◆◆ | 🔁 | **en dernier** (dépend de tout) |

**Logique de l'ordre.**
- **S1** = corriger/compléter ce qui existe déjà (rapide, conforme Maroc,
  bénéfice immédiat sur la facturation déjà en chantier ce soir).
- **S2** = construire le **pivot Installation** (rien d'autre ne tient sans
  lui). C'est la décision 🚪 la plus structurante du projet — à valider avec
  Reda avant de coder.
- **S3** = l'après-vente (Parc série + Garanties + SAV) qui s'accroche au
  pivot — c'est là que se trouvent le revenu récurrent et l'argent de garantie.
- **S4** = conformité 82-21 fine + champs personnalisés (autonomie de Reda).
- **S5+** = achats, contrats de maintenance, et le reste.

---

### Rappels structurants pour la session technique
- Tout nouveau modèle = FK `company` + queryset filtré par
  `request.user.company` + `company` forcé en `perform_create` (règle
  non négociable du repo).
- Statuts documents (devis/facture) et funnel `STAGES.py` restent **deux
  couches séparées** — ne jamais les fusionner.
- `prix_achat` ne doit **jamais** apparaître sur un PDF/sortie client.
- Le **choix du pivot Installation (3.8)** est la porte à sens unique la plus
  importante de tout ce document : à trancher en premier, avec Reda.
