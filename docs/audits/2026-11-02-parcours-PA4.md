# Audit PA4 « argent » — 2026-11-02 — L3
<!-- dossier-v3 | groupe: AARG | base: 56d5b62 | fraicheur: 56d5b62 | constats: 51 | taches: 57 | decisions: 5 -->

## 1. Charte
| Champ | Valeur |
|---|---|
| Périmètre | parcours PA4 (pilote facturation) : lu `backend/django_core/apps/ventes/**` (BC, factures, paiements, import de relevé, RAS, avoirs, notes de débit, pro-forma, DGI/UBL, relances, beats), `apps/facturation/**`, `apps/portail/views.py`, `core/views.py`, `core/payment.py`, `core/numbering.py`, `authentication/permissions.py`, `apps/crm/clients_identite.py`, `apps/crm/receivers_cadence.py`, `apps/installations/services.py`, `frontend/src/pages/ventes/**` ; table `apps/facturation/parcours/PA4.json` |
| Niveau | L3 — argent + sorties client (PDF, UBL, relances) + multi-société et rôles + parcours chaud |
| Données | demo ; anon : non requis (chaque sonde crée sa société) ; prod lecture seule : aucune |
| Critères retenus | C1, C2, C3, C4, C5, C6, C7, C9, C10, C14, C15, C16, C17, C19, C20 |
| Étapes | PA4.01 convertir en BC · PA4.02 confirmer · PA4.03 livrer · PA4.04 facture de BC · PA4.05 facturer par tranche · PA4.06 émettre · PA4.07 paiement · PA4.08 import de relevé · PA4.09 avoir · PA4.10 note de débit · PA4.11 RAS · PA4.12 mandat (parqué) · PA4.13 pro-forma · PA4.14 UBL/DGI · PA4.15 relances · PA4.16 autres portes de facture |
| NE PAS REFAIRE | ATOT40-53 (ligne déplacée, client/retenue modifiables, avoir de révision, TVA de complément, ND absentes du grand livre) ; AGNR49-61 ; ASEC55-64 (11 portes `encaisser` d'ASEC56) ; ATOT49 (bouton facture de BC) ; AFAC5/AFAC96 (doublon de ligne de relevé) ; AFAC9 (porte d'encaissement) ; AFAC55 (portée des portes groupées) ; ADEV14 (overrides à l'acceptation) ; VNT89 ; ATOT41/ATOT54 |
| Non-objectifs | mandat de paiement (parqué, aucune route) ; commissions (parquées, D-ACRM-6) ; compta (parquée) ; écrans hors API (l'acceptation en direct joue l'API) |

## 2. Couverture
| Lane | Modèle/effort | Chemins lus | Chemins NON lus (raison) |
|---|---|---|---|
| devis→BC→facture | opus/high | `views/bon_commande.py`, `views/devis_facturation.py`, `domain/facturation_ops.py` (BC, reliquat), `domain/revision.py`, `models_facturation.py` | `emettre_facture` (sortie de stock VNT21), `consume_reservations` (hors argent) |
| portes de facture | opus/high | `domain/facturation_vente.py`, `domain/facturation_ops.py`, `utils/echeancier.py`, `domain/imports.py`, `domain/encaissements.py::consolider_factures` | `modifiabilite.controler_echeancier_vente` (couvert par ATOT) |
| émission et gel | opus/high | `views/facture.py`, `views/facture_portes.py`, `views/facture_cycle.py`, `utils/pdf.py`, `domain/instantanes_facture.py`, `templates/pdf/facture.html` | vues portail facture (lane sécurité) |
| paiements, relevé, RAS | opus/high | `domain/encaissements.py`, `paiement_import.py`, `domain/annulation_facture.py`, `receivers.py`, `portail/services.py` | `remise_encaissement.py` (hors MVP) |
| avoirs, notes de débit | opus/high | `views/facture_rectificatifs.py`, `views/avoir.py`, `templates/pdf/avoir.html` | `crediter_ecart_de_vente` (ATOT43-45) |
| pro-forma, UBL/DGI | sonnet/high | `views/devis_facturation.py::proforma_pdf`, `dgi/*`, `utils/ubl.py`, `views/facture_documents.py` | `apps/einvoice` (bouchon) |
| relances, beats, perf | sonnet/medium | `scheduled.py`, `recouvrement.py`, `email_service.py`, `models.py::jours_retard` | autres beats (hors argent) |
| sécurité, 2 sociétés | opus/high | permissions des 16 étapes, `permissions_registre.py`, `core/scoping.py`, `paiement_import.py`, `recouvrement.py` | `dgi/transmission.py` (lane DGI) |
| passages de main, table | opus/high | `domain/cycle_vie.py`, `crm` sortie de « Signé », `installations/services.py`, `PA4.json`, `test_parcours_pa4.py` | `chantiers_a_facturer` (corps) |
Détecteurs : `scripts/check_parcours.py` (logique rejouée par la lane passages de main) → ancres résolues, 0 porte manquante au sens de la garde @56d5b62 · non exécutés : `scripts/rejouer_parcours.py PA4` (échec outil : compte toutes les tables et n'affiche que le bruit de fin — C-AARG-048).
Live : parcours heureux PA4 par l'API réelle sur un enregistrement (sonde `docs/audits/sondes/AARG/C-AARG-000.py` : accepter → convertir-bc → confirmer → creer-facture → emettre → paiement 50 % → avoir 1 ligne → relecture) : 9 étapes 2xx, TTC facture = TTC devis (12 000,00), dû exact, aucun `prix_achat` · prévus non joués : écrans (navigateur) · prod : aucune.

## 3. Constats
| C-id | Étape | Critère | Grav. | fichier::symbole | Observé → attendu | Sonde | Tâche(s) |
|---|---|---|---|---|---|---|---|
| C-AARG-001 | PA4.09 | C7 | S1 | `apps/ventes/domain/facturation_ops.py::creer_avoir_facture` | avoir 2 400 sur facture payée 12 000 (et `retour-client`) : dû 0, rien dû au client → avance client (D-AARG-1) | `docs/audits/sondes/AARG/C-AARG-001.py` | AARG1 |
| C-AARG-002 | PA4.09 | C17 | S1 | `apps/ventes/views/avoir.py::AvoirViewSet.annuler` | annuler l'avoir miroir : facture « payée », payé 0, dû 12 000, avance encore libre → recalcul + avance rattachée | `docs/audits/sondes/AARG/C-AARG-002.py` | AARG2 |
| C-AARG-003 | PA4.09 | C10 | S2 | `apps/ventes/selectors_facturation.py::acompte_paye_pour_devis` | avoir total sur acompte non encaissé → « payée » → chantier planifié → encaissé réel exigé | `docs/audits/sondes/AARG/C-AARG-003.py` | AARG3 |
| C-AARG-004 | PA4.07 | C6 | S2 | `apps/ventes/domain/encaissements.py::affecter_encaissement_groupe` | clés « id » et « 0id » : 2 paiements de 1 000 sur une facture de 1 000 → 409 | `docs/audits/sondes/AARG/C-AARG-004.py` | AARG5 |
| C-AARG-005 | PA4.11 | C7 | S1 | `apps/ventes/domain/encaissements.py::enregistrer_paiement_avec_retenue` | base RAS = TVA totale après avoir : RAS 200 au lieu de 100, facture payée avec 100 dus → TVA nette (D-AARG-2) | `docs/audits/sondes/AARG/C-AARG-005.py` | AARG4 |
| C-AARG-006 | PA4.08 | C3 | S2 | `apps/ventes/paiement_import.py::commit` | import de relevé : paiement 3 000 dans le délai légal J+7 (loi 31-08) → refusé comme la saisie manuelle | `docs/audits/sondes/AARG/C-AARG-006.py` | AARG6 |
| C-AARG-007 | PA4.07 | C5 | S1 | `backend/django_core/authentication/permissions.py::module_de_la_vue` | portail `rapprocher`, paiement en ligne, annuler rembourser/transferer, promesse : rôles sans `encaisser` (Technicien, RH) écrivent un Paiement → 403 | `docs/audits/sondes/AARG/C-AARG-007.py` | AARG7, AARG8, AARG11, AARG52 |
| C-AARG-008 | PA4.07 | C5 | S2 | `apps/ventes/views/paiement.py::PaiementViewSet.get_permissions` | Admin RH lit paiements, avoirs, ND, BC, promesses (200) ; factures 403 → même droit de lecture | `docs/audits/sondes/AARG/C-AARG-008.py` | AARG12 |
| C-AARG-009 | PA4.08 | C5 | S2 | `apps/ventes/paiement_import.py::_match_facture` | Commercial portée soi : paiement sur la facture d'un autre, facture de son BC, consolidation, promesse → 404 | `docs/audits/sondes/AARG/C-AARG-009.py` | AARG13 |
| C-AARG-010 | PA4.05 | C5 | S2 | `apps/ventes/views/devis_facturation.py::DevisFacturationActionsMixin.refus_avant_facturer` | Commercial `override_credit` → facture émise au-delà du plafond → `peut_passer_outre` | `docs/audits/sondes/AARG/C-AARG-010.py` | AARG14 |
| C-AARG-011 | PA4.05 | C7 | S3 | `apps/ventes/utils/echeancier.py::creer_facture_tranche` | override journalisé « débloqué » puis 403, aucune facture → override transmis à l'émission | `docs/audits/sondes/AARG/C-AARG-011.py` | AARG15 |
| C-AARG-012 | PA4.16 | C6 | S3 | `apps/ventes/domain/encaissements.py::consolider_factures` | brouillon d'acompte auto laissé vivant, aucun verrou de vente → verrou + retrait | `docs/audits/sondes/AARG/C-AARG-012.py` | AARG16 |
| C-AARG-013 | PA4.16 | C6 | S3 | `apps/ventes/domain/imports.py::creer_facture_import` | import : FAC- hors série configurée, aucun `facture_emise` → `create_numbered` + émission | `docs/audits/sondes/AARG/C-AARG-013.py` | AARG17 |
| C-AARG-014 | PA4.01 | C17 | S2 | `apps/ventes/views/devis_facturation.py::DevisFacturationActionsMixin.convertir_en_bc` | V1 remplacée encore acceptée → 2e BC → stock sorti 6 pour une vente de 3 → 409 | `docs/audits/sondes/AARG/C-AARG-014.py` | AARG18 |
| C-AARG-015 | PA4.04 | C6 | S2 | `apps/ventes/views/bon_commande.py::BonCommandeViewSet.perform_create` | BC client X + devis brouillon de Y → facture émise à X avec les lignes de Y → 409 | `docs/audits/sondes/AARG/C-AARG-015.py` | AARG19 |
| C-AARG-016 | PA4.14 | C3 | S2 | `apps/ventes/dgi/dgi_export.py::build_ubl_xml` | UBL transmis : en-tête 900, ligne 1 000, sans remise ; le correctif QX2 est sur le jumeau aperçu → un constructeur | `docs/audits/sondes/AARG/C-AARG-016.py` | AARG20 |
| C-AARG-017 | PA4.14 | C6 | S3 | `apps/ventes/dgi/transmission.py::transmettre_facture` | brouillon et facture annulée transmis « acceptée », conformité jamais appelée (dormant : interrupteur coupé) → 409 | `docs/audits/sondes/AARG/C-AARG-017.py` | AARG21 |
| C-AARG-018 | PA4.15 | C7 | S3 | `apps/ventes/recouvrement.py::facture_relancable` | D-AFAC-89 (a) jamais construite : facture contestée relancée → drapeau qui suspend | `docs/audits/sondes/AARG/C-AARG-018.py` | AARG22 |
| C-AARG-019 | PA4.15 | C1 | S2 | `apps/ventes/email_service.py::composer_relance_email` | mail de relance : ni montant (700) ni échéance, « ci-dessus », double « Bonjour » → montant dû et échéance | `docs/audits/sondes/AARG/C-AARG-019.py` | AARG24, AARG25 |
| C-AARG-020 | PA4.05 | C16 | S3 | `apps/ventes/domain/facturation_vente.py::retirer_acompte_automatique` | brouillon d'acompte saisi à la main (35 000) annulé à la sortie de « Signé » → 409 nommant la facture | `docs/audits/sondes/AARG/C-AARG-020.py` | AARG26 |
| C-AARG-021 | PA4.06 | C9 | S2 | `apps/ventes/domain/instantanes_facture.py::figer_a_l_emission` | client édité après émission : PDF et UBL re-rendus au nouveau nom/ICE, PDF envoyé écrasé → identité de l'acheteur figée | `docs/audits/sondes/AARG/C-AARG-021.py` | AARG27, AARG51 |
| C-AARG-022 | PA4.06 | C6 | S1 | `apps/ventes/views/facture_portes.py::refuser_portes_fermees` | `PATCH {devis: null}` (et `bon_commande`) sur facture émise → 2e facture émise pour la même vente → 409 | `docs/audits/sondes/AARG/C-AARG-022.py` | AARG28 |
| C-AARG-030 | PA4.03 | C17 | S3 | `apps/ventes/models_facturation.py::BonCommande.reliquat_par_ligne` | BC rattaché à V2 : livré oublié, reliquat plein → correspondance V1→V2 | STATIQUE | AARG29 |
| C-AARG-031 | PA4.06 | C9 | S3 | `apps/ventes/domain/facturation_ops.py::emettre_facture` | réémission redate le numéro légal (N daté après N+1) → date d'origine (D-AARG-4) | STATIQUE | AARG23 |
| C-AARG-032 | PA4.04 | C17 | S3 | `apps/ventes/domain/facturation_ops.py::creer_bon_commande` | BC ou facture de BC annulés bloquent la chaîne pour toujours → exclure ANNULÉ | STATIQUE | AARG30 |
| C-AARG-033 | PA4.01 | C5 | S3 | `apps/ventes/views/devis_facturation.py::DevisFacturationActionsMixin.convertir_en_bc` | société du BC = société de l'utilisateur → société du devis | STATIQUE | AARG31 |
| C-AARG-034 | PA4.16 | C20 | S3 | `apps/ventes/views/bon_commande.py::BonCommandeViewSet.creer_facture` | avertissement bloquant de vente sauté (porte BC, consolidation) → même garde | STATIQUE | AARG32 |
| C-AARG-035 | PA4.06 | C20 | S3 | `apps/ventes/views/facture_cycle.py::FactureCycleActionsMixin.emettre` | émettre exige `encaisser` sur une porte seulement → toutes (D-AARG-3) | STATIQUE | AARG9 |
| C-AARG-036 | PA4.08 | C2 | S3 | `apps/ventes/paiement_import.py::commit` | import partiel : le reste du fichier verrouillé pour toujours → idempotence par ligne | STATIQUE | AARG33 |
| C-AARG-037 | PA4.07 | C20 | S3 | `apps/ventes/domain/encaissements.py::enregistrer_paiement` | 9 sites de création de Paiement, invariants divergents → une primitive | STATIQUE | AARG34 |
| C-AARG-038 | PA4.09 | C17 | S3 | `apps/ventes/domain/annulation_facture.py::annuler_facture` | annulation avec directive : retenues orphelines, remboursement escompte compris → neutraliser | STATIQUE | AARG35 |
| C-AARG-039 | PA4.09 | C1 | S3 | `backend/django_core/templates/pdf/avoir.html` | avoir/ND multi-taux sans « Base HT (x %) », sans date de la facture d'origine → ventilation | STATIQUE | AARG36 |
| C-AARG-040 | PA4.09 | C1 | S3 | `apps/ventes/views/avoir.py::AvoirViewSet.annuler` | PDF d'un avoir annulé : « Statut : Émis » → régénéré | STATIQUE | AARG37 |
| C-AARG-041 | PA4.09 | C6 | S3 | `apps/ventes/views/facture_rectificatifs.py::FactureRectificatifsActionsMixin.creer_avoir` | lignes d'avoir de correction libres (TVA 0 sur ligne à 20 %) → contrôlées | STATIQUE | AARG38 |
| C-AARG-042 | PA4.09 | C20 | S3 | `apps/ventes/views/facture_rectificatifs.py::FactureRectificatifsActionsMixin.creer_avoir` | `contre_passation` = 2e porte d'annulation sans `facture_annulee` → délègue | STATIQUE | AARG39 |
| C-AARG-043 | PA4.14 | C5 | S3 | `apps/ventes/views/facture_documents.py::FactureDocumentsActionsMixin.ubl` | `ubl`, `dgi-conformite`, `dgi-transmettre` sans `ventes_export` → même droit | STATIQUE | AARG40 |
| C-AARG-044 | PA4.14 | C10 | S3 | `apps/ventes/dgi/dgi_export.py::build_ubl_xml` | aucun UBL d'avoir ni de ND (381/383) → types et référence | STATIQUE | AARG41 |
| C-AARG-045 | PA4.15 | C17 | S3 | `apps/ventes/scheduled.py::_reporter_relance` | échec d'envoi relancé chaque jour sans fin → plafond + alerte | STATIQUE | AARG42 |
| C-AARG-046 | PA4.15 | C14 | S3 | `apps/ventes/scheduled.py::relance_reminders` | ≈ 10 requêtes par facture dans les beats → prefetch + budget | STATIQUE | AARG43 |
| C-AARG-047 | PA4.05 | C15 | S3 | `backend/django_core/apps/facturation/parcours/PA4.json` | table décalée (entrée PA4.05, codes 400, porte `perform_create` absente, PA4.11 sans écran) → resynchronisée | STATIQUE | AARG44 |
| C-AARG-048 | PA4.01 | C19 | S3 | `scripts/rejouer_parcours.py::programme` | rejeu : compte toutes les tables, n'affiche que le bruit de fin → tables du parcours, vraie erreur | STATIQUE | AARG45 |
| C-AARG-049 | PA4.16 | C17 | S3 | `apps/installations/services.py::changer_statut_chantier` | retour RÉCEPTIONNÉ → INSTALLÉ : jalon de réception resté atteint → remis à faux | STATIQUE | AARG46 |
| C-AARG-050 | PA4.06 | C10 | S3 | `apps/crm/receivers_cadence.py::_tracer_facture_emise_sur_le_lead` | note « facture émise » sur le lead le plus récent → `Facture.lead` | STATIQUE | AARG47 |
| C-AARG-051 | PA4.06 | C9 | S3 | `apps/parametres/views_uploads.py::_delete_image` | logo figé supprimé → facture émise re-rendue au logo vivant → conservé | STATIQUE | AARG48 |
| C-AARG-052 | PA4.06 | C2 | S3 | `apps/ventes/views/facture.py::FactureViewSet.perform_update` | `libelle`, `date_livraison` modifiables après émission → figés | STATIQUE | AARG49 |
| C-AARG-053 | PA4.07 | C4 | S3 | `apps/ventes/receivers.py::_materialize_paiement_on_payment_captured` | pile carte FG370 vivante malgré D-AFAC-83 (a) → retirée | STATIQUE | AARG10 |
| C-AARG-060 | PA4.10 | C7 | S2 | `apps/ventes/domain/encaissements.py::recalculer_statut_paiement` | ND 500 sur facture payée (ou retenue libérée) : en retard 90 j, niveau 3, pénalité 117,75 → échéance propre | `docs/audits/sondes/AARG/C-AARG-060.py` | AARG53 |
| C-AARG-061 | PA4.06 | C7 | S3 | `backend/django_core/core/numbering.py::_period_segment` | période UTC : facture du 01/07 numérotée 202606 (latent, offset Casablanca) → date locale | `docs/audits/sondes/AARG/C-AARG-061.py` | AARG54 |
| C-AARG-062 | PA4.07 | C17 | S3 | `apps/ventes/domain/recouvrement.py::rejeter_paiement` | rejet : abandon auto 0,05 reste actif, paiement de 1 200 refusé → abandon annulé | `docs/audits/sondes/AARG/C-AARG-062.py` | AARG55 |
| C-AARG-063 | PA4.15 | C3 | S3 | `apps/ventes/domain/encaissements.py::recalculer_statut_paiement` | sans échéance : recalcul « émise », beat « en retard » → une seule règle | `docs/audits/sondes/AARG/C-AARG-063.py` | AARG56 |
| C-AARG-064 | PA4.07 | C7 | S3 | `apps/ventes/domain/encaissements.py::enregistrer_paiement` | escompte sans avoir : TVA et UBL au montant plein → avoir (D-AARG-5) | STATIQUE | AARG57 |

## 4. Réfutés, requalifiés, fusionnés
| Constat | Verdict | Argument (sonde ou fichier::symbole) |
|---|---|---|
| C-AARG-004 | requalifié S1 → S2 | seconde lentille : l'écran construit les clés par `Object.fromEntries` (pas de doublon) ; corps forgé requis, total encaissé gardé |
| C-AARG-012 | partiel | l'émission du brouillon fantôme est refusée (`motif_emission_hors_prix`) ; course non rejouable en une transaction |
| C-AARG-013 | partiel, S2 → S3 | `date_emission` posée par le défaut du modèle ; porte du kit de migration seulement |
| C-AARG-017 | S2 → S3 | `dgi_transmission_actif` coupé en prod, fournisseurs noop/mock seulement |
| C-AARG-019 | S3 → S2 | sortie client (lentille obligatoire) : le mail n'a ni montant ni échéance |
| C-AARG-020 | S2 → S3 | aucun montant perdu : l'échéancier réécrit reste, le brouillon est recréé à la réacceptation |
| C-AARG-063 | partiel | le paiement partiel ne rebascule pas (`encaisser_sur_facture` sans recalcul) ; seul le recalcul partagé le fait |
| lane pro-forma | fusionné | pro-forma : chiffres = devis (ATOT10), sans `prix_achat`, hors règle #4 (filigrane, série PF-, décision D1) |
Porte : 3 réfutés partiels / 57 bruts · seconde lentille : 6 S1 → maintenus 5, gravité revue 1 (C-AARG-004), élargis 3 (C-AARG-001 `retour-client`, C-AARG-007 cause racine `module_de_la_vue`, C-AARG-022 `bon_commande`).

## 5. Non-risques
| Zone | Preuve | Valide tant que |
|---|---|---|
| parcours heureux devis → avoir | `docs/audits/sondes/AARG/C-AARG-000.py` : 9 étapes 2xx, TTC au centime, dû exact | `copier_devis_sur_facture` et `TotauxDocumentMixin` restent la chaîne unique |
| `prix_achat` hors sorties PA4 | C-AARG-000 (aucune réponse ne le porte) ; `templates/pdf/proforma.html`, constructeurs UBL lus | aucun serializer facture ne passe à `fields='__all__'` sur Produit |
| doublon de ligne de relevé | AFAC5/AFAC96 (idempotence par ligne) | `ReleveLigne` garde sa clé |
| totaux multi-taux | `apps/facturation/totaux.py` noyau unique (critique de complétude) | un seul noyau |
| relances : statuts exclus, avoirs déduits | `recouvrement.py::STATUTS_NON_RELANCABLES`, `decomposition_du` | — |

## 6. Décisions
| D-id (`docs/audits/decisions.yml`) | Question (une ligne) | Statut | Tâches |
|---|---|---|---|
| D-AARG-1 | surplus d'un avoir sur facture payée | avance_client | AARG1 |
| D-AARG-2 | base de la RAS-TVA après avoir | tva_nette | AARG4 |
| D-AARG-3 | `encaisser` pour émettre | exiger_encaisser | AARG9 |
| D-AARG-4 | date à la réémission | garder_date | AARG23 |
| D-AARG-5 | comptabilisation de l'escompte | par_avoir | AARG57 |

## 7. Optionnel (jamais une tâche)
- `confirmer` d'un BC sans verrou : double notification CHT15 au double clic, stock non doublé.
- Quatre portes de PA4.16 sans appelant de production (`creer_facture_contrat`, `creer_facture_regie`, `creer_facture_acompte_situation`, `creer_facture_classique`) ; `creer_facture_contrat` à TVA 20 % codée.
- Pro-forma : une ligne de TVA sur devis multi-taux (montants exacts) ; nouveau numéro PF- à chaque clic (choix D1).
- `Facture.jours_retard` en date UTC (écart d'un jour entre 00 h et 01 h) ; `pre_echeance_reminders` à date exacte et sans mode manuel.
- Note de débit : pénalités rattrapées le jour même (relève de C-AARG-060 une fois l'échéance propre posée).

## 8. Limites, non couvert, écarts
- Non couvert : écrans en navigateur (le rejeu est API) ; tzdata de prod (C-AARG-061 dépend de l'offset réel de Casablanca) ; variantes K07 `paiements-en-ligne`/`annuler`/promesses avec les rôles Technicien et RH ; `transferer` de K02 ; lien de paiement public (page non localisée).
- Écart à la méthode : premier audit de PARCOURS — le registre n'a pas de place pour un parcours → entrée `PA4` ajoutée à `docs/audits/unites.yml` (groupe AARG, mot `argent`) ; `scripts/rejouer_parcours.py` inutilisable sous charge (C-AARG-048) → rejeu par sonde de parcours ; ponctuel, METHODE §D.1 inchangée.
- Écart machine : moteur Docker tombé deux fois (RAM 16 Go saturée par trois contre-visites parallèles) → sondes sérialisées par un verrou à deux créneaux ; aucune sonde comptée sur un échec d'infrastructure.
- Incident prod : aucun.

## 9. Coût et routage
Coût : H0 S3 O17 F1 · jetons sous-agents ≈ 4,5 M · tâches 57 (M0 0 M1 6 M2 14 M3 36 GATED 0).
Routage : `PLAN_AUDIT_FACTURATION.md` 49 · `PLAN_AUDIT_DEVIS.md` 2 · `PLAN_AUDIT_SECURITE.md` 3 · `PLAN_AUDIT_DOCUMENTS.md` 1 · `PLAN_AUDIT_DEPLOY.md` 1 · `PLAN_AUDIT_CHANTIERS.md` 1 · `PLAN_AUDIT_LEAD.md` 2 · `PLAN_AUDIT_PARAMETRES.md` 1 · acceptation AARG50 · PR #<n>.
