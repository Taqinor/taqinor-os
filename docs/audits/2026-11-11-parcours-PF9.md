# Audit PF9 « doubles clics, gestes rejoués, courses » — 2026-11-11 — L2
<!-- dossier-v3 | groupe: ACNC | base: 3acfee4 | fraicheur: 93f8626 | constats: 33 | taches: 48 | decisions: 2 -->

## 1. Charte
| Champ | Valeur |
|---|---|
| Périmètre | parcours PF9 : tout geste d'écriture envoyé deux fois (double clic, nouvel essai après le délai de 20 s de l'écran, deux onglets) ou croisé avec un autre geste sur le même objet ; lu `backend/django_core/apps/**`, `backend/django_core/core/**`, `backend/fastapi_ia/**`, `frontend/src/**` et deux gardes de `scripts/` ; aucune table `PF9.json` |
| Niveau | L2 — argent, stock et numéros légaux, aucun S1 ; quatre surfaces indépendantes |
| Données | aucune démo (aucune pile ne servait `main`) ; anon : non requis ; prod : lue les 10 et 11/11 en lecture seule, comptages seulement (§2) |
| Critères retenus | C2, C6, C7, C13, C17, C18, C20 |
| Étapes | PF9.1 argent et documents de vente · PF9.2 stock, achats, chantiers, SAV · PF9.3 mécanismes transversaux (numérotation, événements, webhooks, imports, masse, hors ligne, gardes) · PF9.4 écran · PF9.5 trous de la critique (parcours : PF9) |
| Inventaire | 77 gestes d'argent et de vente ; 565 gestes routés stock, achats, chantiers, SAV ; ≈ 650 sites transversaux ; 1 260 écritures d'écran ; quatre lectures, quatre vérificateurs frais, une seconde lentille sur les candidats S1, une critique de complétude et son vérificateur |
| NE PAS REFAIRE | groupes ADRG, ALEC, APUB, ATST, AMSG, ASUP ; AARG74 (annulation d'un avoir, ouverte) ; AACQ30, ACVI34, AFAC8 tiennent sur leur critère |
| Non-objectifs | contenu des messages envoyés (PF8) ; lenteur (PF3) ; droits des rôles (PF4) ; aucune correction de code |

## 2. Couverture
| Lane | Modèle/effort | Chemins lus | Chemins NON lus (raison) |
|---|---|---|---|
| lecture : argent et documents de vente | opus/high | 77 gestes sur 197 points d'écriture énumérés (paiements, avoirs, notes de débit, encaissements, tranches, BC, devis) | — |
| lecture : stock, achats, chantiers, SAV | opus/high | 565 gestes routés, environ 60 lus un par un ; 59 transitions | mise au rebut, inventaire admin (dits idempotents, non revérifiés) |
| lecture : mécanismes transversaux | opus/high | 107 numérotations, 249 `get_or_create`, 23 `.delay`, 92 abonnés, 44 écritures publiques, gardes CI | apps listées au §8 |
| lecture : écran | sonnet/high | 1 260 écritures HTTP d'écran, environ 60 relues ; `api/axios.js`, `ui/Button.jsx` | 33 appels directs hors axios ; 10 boutons sans `loading` |
| vérificateurs frais (4) | opus/high | un par lecture ; fonctions réelles extraites et rejouées avec bouchons | — |
| seconde lentille S1 | opus/high | 5 candidats S1 : chaque PDF, transaction, verrou, événement et numéro du chemin | durées réelles (aucune pile) |
| critique de complétude | opus/high | 82 `perform_destroy`, 29 ViewSets PATCH et transition, 56 `+=`, 202 contraintes | — |
| vérification de la critique | opus/high | ses 6 trous, dont le PATCH concurrent (C-ACNC-007) | — |
| sondes, rédaction, édition | sonnet/high (sondes), opus/high (fusion, rédaction, édition) | 10 sondes hôte ; 48 tâches v3 (3 rédacteurs, 1 éditeur) | — |
Détecteurs : inventaires par scripts hors dépôt @3acfee4 (ast et grep) ; `scripts/check_read_modify_write.py` et `scripts/check_get_or_create.py` joués sur mutants (C-ACNC-026) · non exécutés : tests Django (aucune pile).
Live : aucun scénario joué · prévus non joués : rejeu par l'API et à l'écran des tâches P1 (ACNC56) · sondes : 10 sondes hôte jouées le 11/11 (vrai code, bouchons, sans Django), toutes `repro: True`, rejouées à l'édition sur 08d2229.
Prod (lue les 10 et 11/11, lecture seule) : 5 comptes internes actifs (2 Directeur, 2 Commercial, 1 Commercial responsable), 1 compte portail ; factures : 2 brouillon, 7 annulées, 3 émises, 1 payée, 6 en retard ; 36 devis envoyés ;
Prod (suite) : 7 paiements clients sur 4 factures, aucun doublon (7 groupes facture, montant, jour distincts) ; 2 avoirs `correction` saisis à la main puis annulés ; 0 note de débit ; 0 encaissement groupé ; 3 BC clients ;
Prod (suite) : 260 mouvements de stock (198 entrées, 61 sorties, 1 ajustement, 0 transfert) ; 5 bons fournisseur (4 envoyés), 0 réception, 0 facture fournisseur ; 0 pièce et 0 prêt SAV ;
Prod (suite) : aucun import ; 0 règle d'automatisation ; e-mail éteint ; clés CMI, WhatsApp Cloud, e-signature absentes ; assistant IA allumé, 0 action exécutée.

## 3. Constats
Ancres : serveur relatif à `backend/django_core/`, écran à `frontend/src/`, sinon depuis la racine.
| C-id | Étape | Critère | Grav. | fichier::symbole | Observé → attendu | Sonde | Tâche(s) |
|---|---|---|---|---|---|---|---|
| C-ACNC-001 | PF9.1 | C6 | S2 | `apps/ventes/domain/encaissements.py::encaisser_sur_facture` | paiement partiel, note de débit, avoir ou retour renvoyé après un délai ou en deux onglets = créé deux fois (aucune clé envoyée) → clé par dialogue · réel · prod : 7 paiements sans doublon, 2 avoirs saisis à la main | `docs/audits/sondes/ACNC/C-ACNC-001.py` | ACNC1, ACNC2, ACNC3, ACNC4, ACNC52, ACNC56 |
| C-ACNC-002 | PF9.1 | C7 | S2 | `apps/facturation/views/facture.py::FactureViewSet.perform_destroy` | « Supprimer » pendant « Émettre » efface une facture émise, numérotée, stock sorti (statut lu sur l'objet chargé) → relu sous verrou, 409 · réel · prod : 3 émises, 2 brouillons | `docs/audits/sondes/ACNC/C-ACNC-002.py` | ACNC5, ACNC6, ACNC7, ACNC50 |
| C-ACNC-003 | PF9.1 | C17 | S2 | `apps/ventes/domain/annulation_facture.py::annuler_facture` | acompte et solde d'une vente annulés en même temps : aucun ne rend le stock → verrou de la vente · réel, très peu probable · prod : 7 factures annulées | `docs/audits/sondes/ACNC/C-ACNC-003.py` | ACNC8 |
| C-ACNC-004 | PF9.2 | C2 | S2 | `apps/stock/serializers.py::BonCommandeFournisseurSerializer.update` | deux acheteurs : le 2e efface la ligne du 1er ; un PATCH croisé avec « Envoyer » remet le bon en brouillon → jeton de version, statut sous verrou · réel · prod : 5 bons, 4 envoyés | `docs/audits/sondes/ACNC/C-ACNC-004.py` | ACNC21, ACNC50 |
| C-ACNC-005 | PF9.2 | C6 | S2 | `apps/stock/views/mouvement.py::MouvementStockViewSet.perform_create` | mouvement ou transfert renvoyé après un délai = 2 mouvements ; latent pour réception, règlement, acompte, facture fournisseur → clé · réel · prod : 260 mouvements, 0 transfert | `docs/audits/sondes/ACNC/C-ACNC-005.py` | ACNC22, ACNC23 |
| C-ACNC-006 | PF9.2 | C6 | S2 | `apps/stock/services.py::apply_product_bulk` | « +10 % » en masse rejoué = + 21 % ; panne à mi-boucle = prix décalés (aucune transaction) → tout-ou-rien, rejouable, confirmé · réel · prod : usage non mesuré | `docs/audits/sondes/ACNC/C-ACNC-006.py` | ACNC24 |
| C-ACNC-007 | PF9.5 | C7 | S2 | `core/mixins.py::TenantMixin.perform_update` | un PATCH dont la fenêtre serveur (quelques ms) croise la transition d'un collègue la réécrit (ticket résolu remis en cours) → écriture bornée aux champs validés · réel, très peu probable · prod : 3 BC | `docs/audits/sondes/ACNC/C-ACNC-007.py` | ACNC25, ACNC41, ACNC50 |
| C-ACNC-008 | PF9.1 | C6 | S3 | `apps/ventes/domain/encaissements.py::affecter_encaissement_groupe` | encaissement groupé rejoué : tout le virement devient une avance (20 000 pour 10 000) → clé ; lot déjà soldé : D-ACNC-2 · latent, S2 dès le premier usage · prod : 0 | `docs/audits/sondes/ACNC/C-ACNC-008.py` | ACNC9, ACNC10 |
| C-ACNC-009 | PF9.1 | C6 | S3 | `apps/facturation/views/facture_recouvrement.py::FactureRecouvrementActionsMixin.relancer` | « Relancer » rejoué consigne une 2e relance → même niveau le même jour = la ligne existante · réel, journal seul | STATIQUE | ACNC11 |
| C-ACNC-010 | PF9.1 | C6 | S3 | `apps/ventes/views/devis_facturation.py::DevisFacturationActionsMixin.generer_facture` | avance, tranche suivante, proforma, renouvellement, variantes recréés à chaque envoi → clé, source sous verrou · latent : API seule, assistant 0 action | STATIQUE | ACNC12, ACNC13 |
| C-ACNC-011 | PF9.2 | C7 | S3 | `apps/sav/views.py::TicketViewSet.supprimer_piece` | pièce et prêt SAV lus hors verrou : deux « Retirer » croisés rendent deux fois le stock (16 au lieu de 13) → relus sous verrou · latent · prod : 0 pièce, 0 prêt | `docs/audits/sondes/ACNC/C-ACNC-011.py` | ACNC26, ACNC27 |
| C-ACNC-012 | PF9.2 | C6 | S3 | `apps/stock/services.py::apply_retour_fournisseur` | retour fournisseur non plafonné côté serveur : revalidé après une réponse perdue, il sort deux fois le stock → plafond reçu moins retourné · latent · prod : 0 réception | STATIQUE | ACNC28 |
| C-ACNC-013 | PF9.2 | C6 | S3 | `pages/stock/OcrStockImport.jsx::handleApply` | l'écran enchaîne créer puis agir : un nouvel essai recrée le bon fournisseur et sa réception → reprendre à l'étape échouée · latent · prod : 0 réception | STATIQUE | ACNC29 |
| C-ACNC-014 | PF9.2 | C7 | S3 | `apps/installations/views/demande_transfert.py::DemandeTransfertViewSet.executer` | deux « Exécuter » ou « Expédier » croisés = deux transferts → relu sous verrou, une transaction · latent : aucun écran | STATIQUE | ACNC30 |
| C-ACNC-015 | PF9.2 | C17 | S3 | `apps/installations/services.py::changer_statut_chantier` | deux changements de statut croisés émettent deux fois notes, webhooks, notifications → état avant relu sous verrou · réel, sans argent ni stock | STATIQUE | ACNC31, ACNC32 |
| C-ACNC-016 | PF9.2 | C6 | S3 | `apps/sav/views.py::TicketViewSet.creer_devis` | « Créer un devis » rejoué = 2e devis orphelin ; devis de réserve lu puis créé sans verrou → garde sous verrou · réel, brouillons | STATIQUE | ACNC33, ACNC34 |
| C-ACNC-017 | PF9.2 | C6 | S3 | `apps/sav/maintenance.py::generer_visites_dues` | « Générer les visites dues » cliqué deux fois ou croisé avec la tâche planifiée : deux tickets par contrat → contrat sous verrou, bouton occupé · réel, sans argent | STATIQUE | ACNC35 |
| C-ACNC-018 | PF9.3 | C6 | S3 | `backend/fastapi_ia/app/services/action_tools.py::confirm_proposal` | deux confirmations du même jeton exécutent deux fois un paiement ou une facture → jeton consommé d'un coup, clé transmise · latent : 0 action de l'assistant | `docs/audits/sondes/ACNC/C-ACNC-018.py` | ACNC42 |
| C-ACNC-019 | PF9.3 | C6 | S3 | `core/payment.py::marquer_paye` | deux « Rafraîchir » d'une transaction carte = deux paiements → relu sous verrou, unicité par transaction · latent : clé CMI absente | STATIQUE | ACNC14, ACNC43 |
| C-ACNC-020 | PF9.3 | C6 | S3 | `apps/offlinesync/services.py::_apply_one` | journal commité à part : deux vidages du même lot exécutent deux fois l'effet → une transaction · réel, sans effet aujourd'hui | STATIQUE | ACNC44 |
| C-ACNC-021 | PF9.3 | C6 | S3 | `apps/dataimport/services.py::_commit_raw` | deux « Importer » du même fichier dupliquent leads et documents ; un job en cours relancé repart → verrou du lot et du job · latent : aucun import | STATIQUE | ACNC45, ACNC46 |
| C-ACNC-022 | PF9.3 | C6 | S3 | `apps/automation/public_views.py::incoming_webhook` | chaque redélivrance relance toutes les actions de la règle → dédoublonnage signé · latent : 0 règle | STATIQUE | ACNC47 |
| C-ACNC-023 | PF9.3 | C6 | S3 | `apps/adsengine/whatsapp_webhook.py::WhatsAppCloudWebhookView._process` | deux livraisons du même message = deux leads (créé avant l'arbitrage) → créé après · latent : WhatsApp Cloud éteint | STATIQUE | ACNC48 |
| C-ACNC-024 | PF9.3 | C6 | S3 | `apps/crm/webhooks.py::assign_client_ref` | `client_ref` sans contrainte d'unicité, course assumée par le code → aucune tâche · réel, clé humaine | STATIQUE | sans tâche : résidu assumé par le code (§7) |
| C-ACNC-025 | PF9.3 | C7 | S3 | `core/workflow.py::approuver_etape` | approbation et rejet croisés : instance terminée et rejetée → relues sous verrou · latent | STATIQUE | ACNC49 |
| C-ACNC-026 | PF9.3 | C20 | S3 | `scripts/check_read_modify_write.py::_iter_services_files` | les gardes ne voient que `services*.py`, ni variable locale, ni garde en `return`, ni `core/` → surfaces étendues, dette gelée · réel, garde muette | STATIQUE | ACNC50, ACNC51 |
| C-ACNC-027 | PF9.4 | C13 | S3 | `api/axios.js::REQUEST_TIMEOUT_MS` | sur délai, « réessayez » invite à rejouer un geste peut-être appliqué → « vérifiez avant de recommencer » · réel | STATIQUE | ACNC52 |
| C-ACNC-028 | PF9.4 | C13 | S3 | `pages/ventes/FactureForm.jsx::handleSubmit` | ligne de facture expirée re-postée (« aucun doublon » faux) ; garde de deux onglets non bloquante → ligne relue, jeton de version · réel, brouillons | STATIQUE | ACNC15 |
| C-ACNC-029 | PF9.4 | C18 | S3 | `pages/crm/leads/LeadsPage.jsx::changeStage` | sortie de « Signé » aboutie, carte remise en « Signé » sur délai → relire le lead · réel, jusqu'au rechargement | STATIQUE | ACNC53 |
| C-ACNC-030 | PF9.5 | C7 | S3 | `apps/stock/views/avoir_fournisseur.py::AvoirFournisseurViewSet.perform_destroy` | suppression gardée hors verrou (imputation emportée, statut faux) → sous verrou · latent : 0 facture fournisseur | STATIQUE | ACNC36 |
| C-ACNC-031 | PF9.5 | C6 | S3 | `apps/ventes/inbound_email.py::capture_inbound_email` | aucune déduplication par `Message-ID` : deux relevés = deux journaux et notes → dédupliqué · latent : e-mail éteint | STATIQUE | ACNC16 |
| C-ACNC-032 | PF9.5 | C7 | S3 | `apps/crm/clients_identite.py::merge_clients` | deux fusions croisées : chaque fiche fusionnée dans l'autre → verrous dans un ordre fixe · latent : aucune route | STATIQUE | ACNC54 |
| C-ACNC-033 | PF9.5 | C6 | S3 | `apps/crm/webhooks.py::replay_website_lead_payload` | deux « Rejouer » simultanés d'un envoi sans téléphone ni clé = deux leads et deux devis → relu sous verrou · réel, étroit | STATIQUE | ACNC55 |

## 4. Réfutés, requalifiés, fusionnés
| Constat | Verdict | Argument (sonde ou fichier::symbole) |
|---|---|---|
| C-ACNC-001 | maintenu S2 ; avoir relevé réel | prod relue le 11/11 : 7 paiements = 7 groupes distincts, aucun doublon (pas de S1) ; les 2 avoirs `correction` sont des saisies manuelles (sonde 001) |
| C-ACNC-008, 011, 012, 013, 018 | ramenés S2 → S3 latent | geste jamais utilisé en production (0 encaissement groupé, 0 pièce ni prêt, 0 réception, 0 action de l'assistant) : « S2 dès le premier usage » |
| C-ACNC-016 | ramené S2 → S3 | brouillon orphelin, numéro interne (`apps/sav/views.py::TicketViewSet.creer_devis`) |
| C-ACNC-002 (tranche, remise) | emplacements ramenés S3, scénario corrigé | `apps/ventes/domain/facturation_vente.py::_exiger_couvertes_inchangees` arrête tout sauf « même montant » |
| C-ACNC-003 | relevé S3 → S2 | stock faussé à deux utilisateurs sur un geste utilisé (sonde 003) |
| C-ACNC-007 | maintenu S2, scénario corrigé | pas un formulaire ouvert depuis longtemps (ligne relue à chaque requête) mais une fenêtre serveur ; un PATCH partiel finit aussi par un `save()` complet (sonde 007) |
| C-ACNC-005 | facture fournisseur requalifiée | l'avertissement de doublon n'est jamais affiché (`pages/stock/FacturesFournisseur.jsx::submit`) |
| clé rejouée, lien de paiement concurrent | réfuté « 500 » → 409 | `core/exceptions.py::taqinor_exception_handler` |
| rejeu d'un envoi du site | réfuté sauf résidu (C-ACNC-033) | cache QW10, fenêtre de 60 s, AACQ30 |
| annulation d'un avoir ; intervention depuis un ticket | écartés | AARG74 ouverte ; plusieurs interventions par ticket voulues |
| fusions | 13 causes racines | jusqu'à cinq notes brutes par constat ; une cause chez deux propriétaires = un constat, deux tâches |
Porte : 8 pistes écartées ou réfutées / 33 retenus · seconde lentille : 5 candidats S1 → maintenus 0, gravité revue 5, élargis 0.

## 5. Non-risques
| Zone | Preuve | Valide tant que |
|---|---|---|
| numérotation | numéros légaux et internes par `core/numbering.py` (66 `create_with_reference`, 17 `create_numbered`) ; aucun `count()+1` ni `Max()+1` | les créations passent par ce module |
| acceptation interne et publique, commission | groupe de variantes verrouillé, statut relu sous verrou, ré-acceptation sans effet ; commission affectée, jamais cumulée | — |
| effets différés | aucun `.delay` dans une transaction ; aucun `post_save` ne crée argent, stock ou numéro ; 202 contraintes migrées | — |
| file hors ligne | `apps/installations/field_sync.py::_apply_one` : effet et journal ensemble ; aucune file ne porte d'argent | hors C-ACNC-020 |
| réseau et écran | `api/axios.js` ne rejoue qu'après un 401 ; nginx ne rejoue jamais un POST ; `ui/Button.jsx` bloque le double clic | hors C-ACNC-011 et 017 |
| chaîne achats et stock (services) | réception, facturation, retours, inventaires, transferts en deux temps, réservations : verrou et statut relu | — |

## 6. Décisions
| D-id (`docs/audits/decisions.yml`) | Question (une ligne) | Statut | Tâches |
|---|---|---|---|
| D-ACNC-1 | Un second paiement identique sans clé est-il accepté après confirmation ou refusé ? | ouverte | ACNC4 |
| D-ACNC-2 | Un encaissement groupé entièrement soldé est-il refusé ou gardé en avance ? | ouverte | ACNC10 |

## 7. Optionnel (jamais une tâche)
- C-ACNC-024 : `client_ref` sans unicité — résidu assumé par le code, clé humaine visible.
- Jumeaux non relus : `apps/stock/services.py::_fusionner` (comme 032), `apps/stock/services.py::generer_bcf_reappro` (comme 016).

## 8. Limites, non couvert, écarts
- Non couvert : aucune pile ne servait `main` : aucun test Django, aucun rejeu par l'API ni à l'écran ; les 10 sondes sont des sondes hôte (vrai code extrait, bouchons, entrelacement simulé pour les courses) ; 23 constats lus.
- Non vérifié : DRF 3.18.3 épinglé non relu (`save()` complet prouvé sur la 3.15.2 de l'hôte) ; durées serveur (fenêtre de 007, `apply_product_bulk`, arrêt du conteneur en déploiement) non mesurées.
- Usage prod non ventilé : part manuelle des 260 mouvements ; prix en masse ; tickets, interventions, contrats de maintenance ; acomptes fournisseur ; matrice d'approbation ; clé OCR ; boîte IMAP.
- Apps non parcourues geste par geste : accessreview, adminops, customfields, documents, identity, notifications, records, reporting, roles, semantic, statuspage, tiers, uxviews, parametres.
- Cochées dont le défaut reste sous course : VNT14, VNT67, AFAC16, ASTK84, ASTK62, ASTK88, ACSV52, ASAV23, ASTK53 ; NTPLT17 jamais adoptée par l'écran.
- Corrections à l'édition : ACNC25 autonome (écriture bornée locale, plus d'`@after` vers le plan sécurité) ; ACNC43 relevée P2 ; ACNC9 et ACNC10 citent la sonde 008.
- Forme de clé unique : champ `idempotency_key` du corps sur les routes de `ventesApi.js` (comme `Paiement.idempotency_key`), en-tête `Idempotency-Key` ailleurs ; l'assistant suit la route (ACNC42).
- Planification : `plan_lanes.py` signale PACT11 sur 9 tâches à moitié écran (stock, SAV) à cause d'APUB32 et d'ADRG72 ; refus déjà présent sur des tâches ADRG, ALEC, ASUP ; non bloquant.
- Écart à la méthode : aucun.
- Incident prod : aucun ; aucun paiement en double constaté.

## 9. Coût et routage
Coût : H0 S3 O15 F0 · jetons sous-agents ≈ 5,7 M · tâches 48 (M0 0 M1 11 M2 8 M3 27 GATED 2).
Routage : `PLAN_AUDIT_FACTURATION.md` 14 · `PLAN_AUDIT_STOCK.md` 7 · `PLAN_AUDIT_SAV.md` 5 · `PLAN_AUDIT_ANALYSE.md` 4 · `PLAN_AUDIT_CHANTIERS.md` 4 · `PLAN_AUDIT_DEPLOY.md` 3 · `PLAN_AUDIT_SECURITE.md` 3 · `PLAN_AUDIT_ACQUISITION.md` 2 · `PLAN_AUDIT_DEVIS.md` 2 · `PLAN_AUDIT_LEAD.md` 2 · `PLAN_AUDIT_PARAMETRES.md` 1 · acceptation ACNC56 · PR à venir.
Rapport : aucun défaut grave (S1), 7 défauts sérieux (S2), tous réels aujourd'hui ; aucun doublon d'argent constaté en production.
- Un paiement partiel, une note de débit, un avoir ou un retour renvoyé après un délai ou depuis deux onglets s'enregistre deux fois → ACNC1 à ACNC3.
- « Supprimer » pendant « Émettre » peut effacer une facture émise ; deux annulations croisées d'une vente perdent le retour de stock → ACNC5, ACNC8.
- Stock : bon fournisseur à deux onglets, mouvement renvoyé, « +10 % » en masse rejoué → ACNC21, ACNC22, ACNC24.
- Un PATCH peut réécrire le statut posé par un collègue dans la même fraction de seconde → ACNC41, ACNC25.
- 26 défauts mineurs (S3), dont 15 sur des gestes encore jamais utilisés ; 2 questions au fondateur, ouvertes.
