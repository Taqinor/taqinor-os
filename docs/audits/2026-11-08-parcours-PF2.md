# Audit PF2 « socle » — 2026-11-08 — L3
<!-- dossier-v3 | groupe: ASOC | base: 31a4bce | fraicheur: 86b4067 | constats: 55 | taches: 70 | decisions: 8 -->

## 1. Charte
| Champ | Valeur |
|---|---|
| Périmètre | parcours PF2 (le socle partagé) : lu `core/{events,dsr,feature_flags,calendar,tasks,trash}`, `apps/{parametres,notifications,publicapi,portail,ged,semantic,reporting,audit,tiers,automation}`, abonnés `receivers` des modules métier, `frontend/src/pages/{parametres,crm,ventes}` ; aucune table `PF2.json` |
| Niveau | L3 — le socle se comporte mal pour tous : abonné qui casse l'émetteur, réglage lu à deux endroits, alerte au mauvais destinataire, effacement incomplet ; la sécurité est rendue à PF1 |
| Données | demo (21 sondes en transaction annulée, vraies routes, moteur PDF réel) ; anon : non requis ; prod lecture seule le 08/11 : e-mail transactionnel non configuré, 2 inactifs sans push, 28 brouillons ; 34 devis envoyés sans échéancier propre, réglage jamais changé ; parrainage activé, 0 parrainage |
| Critères retenus | C1, C3, C5, C6, C7, C8, C9, C10, C13, C17, C18 |
| Étapes | PF2.1 bus et webhooks · PF2.2 notifications · PF2.3 balayages, calendrier, fuseau · PF2.4 réglages société sur devis et facture · PF2.5 portail et GED · PF2.6 loi 09-08 · PF2.7 métriques · PF2.8 parrainage · PF2.9 journaux et corbeille (parcours : PF2) |
| NE PAS REFAIRE | groupe ASEC ; parcours PF1 (APFS40, APFS45, APFS68) ; AMON5, AMON84, AMON85, AMON35 ; ACON7, ACON41, ACON91 ; ACSV66, ACSV96, ACSV98, ACSV100 ; NTPLT11 ; ADOC128, ADOC148 ; ACRM56 ; AMET1, AMET2, AMET25 |
| Non-objectifs | écrans en navigateur ; expéditeur des e-mails par société (§7) ; salle de vente et apporteurs parqués (portes vérifiées fermées) ; droits et rôles (PF1) |

## 2. Couverture
| Lane | Modèle/effort | Chemins lus | Chemins NON lus (raison) |
|---|---|---|---|
| découverte : bus d'événements | opus/high | 85 signaux de `core/events/`, ~110 abonnés des `receivers.py`, émetteurs de production | abonnés `publicapi` à 5 signaux (câblage seul) |
| découverte : notifications | opus/high | `apps/notifications`, tous les `notify(` hors tests, 3 détecteurs | expéditeur par société, reprises d'e-mail |
| découverte : réglages société, GED, portail | opus/high | `ventes/{utils,domain}`, `parametres`, `portail`, `ged`, numérotation | coffres GED confidentiels |
| découverte : loi 09-08, analyse, parrainage | opus/high | `core/dsr.py`, fournisseurs DSR, rétention, `reporting`, `semantic`, parrainage, salle de vente | rapports, RH et paie, `grc` |
| sondes (3 séries) | opus/high | 19 constats rejoués, injection de faute, `captureOnCommitCallbacks` | `sav` et `monitoring` désinstallés |
| seconde lentille | opus/high | 2 S1 candidats rejoués par les gestes réels (signature client, relances de 08:15) | production |
| critique de complétude | fable/high | 8 trous lus : calendriers, journal, réglages hors paramètres, langue, fuseau, pré-échéance, corbeille, escompte | aucun sondé |
| rédaction des tâches | opus/high | 70 tâches v3 (3 rédacteurs), 12 plans | — |
| dossier et registre | sonnet/high | ce dossier, `unites.yml`, `decisions.yml`, clauses « Constat » de 38 tâches | — |
Détecteurs : `scripts/check_notify_point_unique.py`, `check_liens_client_absolus.py` (1 gelé, `/suivi/` hors `ROUTES_CLIENT`), `check_date_jour_utc.py` → OK @31a4bce · non exécutés : `event_coverage.py` (exige Django), `check_parcours.py` et `rejouer_parcours.py` (pas de table PF2), `audit_tache.py` (greps équivalents).
Live : 21 sondes `docs/audits/sondes/ASOC/` (REPRO, transaction annulée, base inchangée, 0 e-mail réel, 0 tâche Celery), dont 2 de seconde lentille · prévus non joués : écrans en navigateur · prod : voir §1, aucun objet touché aujourd'hui.

## 3. Constats
| C-id | Étape | Critère | Grav. | fichier::symbole | Observé → attendu | Sonde | Tâche(s) |
|---|---|---|---|---|---|---|---|
| C-ASOC-001 | PF2.2 | C8 | S2 | `apps/notifications/services.py::notify` | devis expiré, accepté ou relancé (e-mail direct de 08:15, hors `notify`) d'un vendeur inactif : alerte, push, e-mail vers lui, 0 au responsable actif ; prod : e-mail non configuré (S1 dès qu'il l'est) → destinataire actif, rien hors app | `docs/audits/sondes/ASOC/C-ASOC-001.py` | ASOC1, ASOC90, ASOC91 |
| C-ASOC-002 | PF2.1 | C10 | S3 | `apps/installations/receivers.py::_creer_chantier_on_devis_accepted` | module Chantiers désinstallé : `accepter/` 200, 1 chantier et 10 panneaux réservés dans un module qui répond 404 ; contrat SAV pareil → abonné muet si le module est inactif (D-ASOC-2) | `docs/audits/sondes/ASOC/C-ASOC-002.py` | ASOC2 |
| C-ASOC-003 | PF2.1 | C13 | S3 | `apps/crm/receivers_cadence.py::_arreter_cadence_on_stage_change` | erreur base dans l'arrêt de cadence : `accepter/` 500, devis resté `envoye`, 0 chantier ; le jumeau à point de sauvegarde passe (200) → un point de sauvegarde dans chaque abonné best-effort | `docs/audits/sondes/ASOC/C-ASOC-003.py` | ASOC6 |
| C-ASOC-004 | PF2.2 | C9 | S3 | `apps/ventes/coherence/notification.py::notifier_nouvelles_violations` | préférence « Récapitulatif » (`digest`) coupée : violation de cohérence et demande portail de contrat → 0 ligne, `is_action('digest')` faux → une clé de type par alerte | `docs/audits/sondes/ASOC/C-ASOC-004.py` | ASOC20, ASOC92, ASOC93 |
| C-ASOC-005 | PF2.2 | C10 | S3 | `apps/automation/services.py::request_more_info` | `approval_info_requested` absent d'`EventType` : soumission, complément demandé et rang suivant → 0 notification (`approval_decided` notifie) → prévenir la personne qui doit agir | `docs/audits/sondes/ASOC/C-ASOC-005.py` | ASOC21 |
| C-ASOC-006 | PF2.3 | C6 | S3 | `apps/notifications/sweeps.py::_sweep_warranty_expiring` | balayages à J, J+1, J+2 : 3 alertes de garantie au technicien pour la même fin, 6 `chantier_due` pour 2 responsables ; « facture en retard » rejouée n'en émet qu'une → un marqueur par occurrence | `docs/audits/sondes/ASOC/C-ASOC-006.py` | ASOC23 |
| C-ASOC-007 | PF2.3 | C7 | S3 | `apps/ventes/selectors_facturation.py::factures_echues` | brouillon de tranche échu J-5 : `jours_retard` 5 et alerte « en retard » ; récap « Paiements en retard » 0 même pour une facture émise échue → exclure le brouillon, une définition | `docs/audits/sondes/ASOC/C-ASOC-007.py` | ASOC24, ASOC94 |
| C-ASOC-040 | PF2.4 | C9 | S1 | `apps/ventes/domain/modifiabilite.py::empreinte_visible` | devis envoyé sans échéancier propre, jalons 30 → 40 % : page client 30 puis 40 %, empreinte identique, signature 200, acompte facturé 8 920 au lieu de 6 690 → empreinte sur les tranches effectives, échéancier figé à l'envoi (D-ASOC-1) | `docs/audits/sondes/ASOC/C-ASOC-040.py` | ASOC40, ASOC95 |
| C-ASOC-041 | PF2.4 | C9 | S2 | `apps/ventes/utils/expiry.py::date_expiration` | validité lue en direct et comptée depuis la création : devis créé le 19/10, envoyé le 08/11, PDF « valable jusqu'au 18/11 » ; réglage 30 → 15 j : acceptation refusée `expiree`, statut `expire` → validité posée à l'envoi | `docs/audits/sondes/ASOC/C-ASOC-041.py` | ASOC41 |
| C-ASOC-042 | PF2.4 | C9 | S3 | `apps/ventes/domain/envoi.py::figer_reglages_rendu` | devis accepté puis profil changé : le re-rendu `/proposal` porte la nouvelle raison sociale et le nouvel ICE, sans trace de ceux de l'envoi (la facture est figée) → identité vendeur figée à l'envoi | `docs/audits/sondes/ASOC/C-ASOC-042.py` | ASOC42, ASOC96 |
| C-ASOC-043 | PF2.4 | C9 | S2 | `apps/portail/views_client.py::MesFacturesPortailViewSet.payer` | facture émise avec le RIB R1, société passée à R2 : PDF R1 ; « Payer » du portail et page publique de paiement R2 → un seul virement, celui de la facture, servi par une fonction | `docs/audits/sondes/ASOC/C-ASOC-043.py` | ASOC43, ASOC97 |
| C-ASOC-044 | PF2.5 | C17 | S2 | `apps/portail/views.py::DemandeTicketPortailViewSet` | ticket SAV résolu puis clôturé : la demande du client reste « Prise en charge » à vie ; `statut` en lecture seule, aucun refus côté SAV → la demande suit le ticket, action « Refuser » motivée | `docs/audits/sondes/ASOC/C-ASOC-044.py` | ASOC44, ASOC98 |
| C-ASOC-048 | PF2.4 | C9 | S3 | `apps/ventes/domain/gammes.py::create_devis_from_reserve` | profil 14 % / EUR : `generer-devis-reserve/` crée 20,00 / MAD, `generer-devis/` 14,00 / EUR ; aucun écran n'appelle la route → TVA et devise par défaut de la société (import compris) | `docs/audits/sondes/ASOC/C-ASOC-048.py` | ASOC48 |
| C-ASOC-060 | PF2.6 | C17 | S2 | `apps/crm/dsr_provider.py::anonymiser_client` | effacement 09-08 : client « Anonymisé » mais son `Tiers` miroir garde nom, e-mail, téléphone, CIN, ICE (fournisseur idem), retrouvé par le téléphone → `anonymiser_tiers` appelé à l'effacement | `docs/audits/sondes/ASOC/C-ASOC-060.py` | ASOC60, ASOC100, ASOC101 |
| C-ASOC-061 | PF2.6 | C7 | S2 | `apps/crm/dsr_provider.py::anonymiser_lead` | effacement ou rétention : lead « Anonymisé » qui garde GPS, contact secondaire, trois notes ; `SiteProfile` garde GPS et note ; chatter lu : valeurs d'identité en clair → scrub étendu, valeurs caviardées (D-ASOC-3) | `docs/audits/sondes/ASOC/C-ASOC-061.py` | ASOC61, ASOC62 |
| C-ASOC-062 | PF2.6 | C1 | S3 | `apps/crm/cadence_messages.py::_nom_prescripteur` | message d'un filleul dont le parrain est effacé : « Anonymisé nous a parlé de vous », aucun champ manquant signalé ; locataire idem → phrase omise pour un prescripteur anonymisé | `docs/audits/sondes/ASOC/C-ASOC-062.py` | ASOC63 |
| C-ASOC-063 | PF2.6 | C17 | S2 | `core/dsr.py::traiter_demande` | fournisseur qui lève : demande « traitée » (terminal), erreur enfouie dans `resultat`, 2e `traiter` 409, identité déjà effacée, aucun contournement → « partielle » relançable (D-ASOC-6) | `docs/audits/sondes/ASOC/C-ASOC-063.py` | ASOC64, ASOC65, ASOC103 |
| C-ASOC-064 | PF2.6 | C7 | S2 | `apps/notifications/models.py::WhatsAppMessageLog` | 3 messages WhatsApp gardent numéro et texte nominatif après effacement ; `dsr.exporter` ne les liste pas ; 11 politiques de rétention, aucune pour ce journal → fournisseur DSR et purge par âge | `docs/audits/sondes/ASOC/C-ASOC-064.py` | ASOC66, ASOC67, ASOC102 |
| C-ASOC-065 | PF2.7 | C7 | S2 | `apps/reporting/metriques_ca.py::ca_ht` | F1 10 000 HT avec avoir 2 000, F2 1 000 HT soldée par avoir : métriques `ca_ht` 11 000, panier 6 600 ; tableau de bord : encaissé 0, en attente 8 000 → CA net d'avoirs partout (D-ASOC-5) | `docs/audits/sondes/ASOC/C-ASOC-065.py` | ASOC73 |
| C-ASOC-130 | PF2.1 | C17 | S3 | `apps/publicapi/signals.py::devis_post_save` | dés-acceptation : `statut = ENVOYE` puis `save` ⇒ webhook `devis.sent` pour un devis qui revient d'accepté ou refusé ; aucun abonné à `devis_acceptation_annulee` (API seule) → pas de `devis.sent` sur un retour d'état | STATIQUE (lecture) | ASOC3 |
| C-ASOC-131 | PF2.1 | C10 | S3 | `apps/publicapi/signals.py::intervention_post_save` | saut direct en « validée » : `intervention.completed` jamais livré, `cloturee_notifiee_le` posé ensuite ; le bus, lui, émet → même borne que le bus (terminée ou validée) | STATIQUE (lecture) | ASOC4 |
| C-ASOC-132 | PF2.1 | C10 | S3 | `apps/reporting/journal_problemes.py::_outbox_en_echec` | outbox fiable sans producteur (`emit_reliable`, `subscribe_durable` sans appelant) : le résumé des problèmes sert une liste vide, le triage y voit une couverture → dire si l'outbox est alimentée | STATIQUE (lecture) | ASOC5 |
| C-ASOC-133 | PF2.1 | C5 | S4 | `apps/crm/receivers_cadence.py::_retour_lead_on_visite_validee` | trois abonnés visite lisent `Lead.objects.filter(pk=lead_id)` sans société (`lead_id` validé à la création : hygiène) → filtre société | STATIQUE (lecture) | ASOC7 |
| C-ASOC-134 | PF2.1 | C3 | S4 | `apps/facturation/views/facture_documents.py::FactureDocumentsActionsMixin.generer_pdf` | audit « PDF facture généré » écrit à la mise en file, pas au rendu (le devis émet après rendu) → journaliser depuis la tâche, au nom du demandeur | STATIQUE (lecture) | ASOC8 |
| C-ASOC-135 | PF2.2 | C1 | S3 | `apps/sav/notifications_client.py::build_ticket_transition_message` | e-mail client « ticket résolu ou planifié » construit hors requête : lien relatif `/suivi/<jeton>` ; la garde `ROUTES_CLIENT` ne voit pas `/suivi/` → lien absolu, garde étendue | STATIQUE (lecture) | ASOC26 |
| C-ASOC-136 | PF2.2 | C10 | S3 | `apps/installations/services.py::_notifier_client_jalon_atteint` | 4 types `PORTAIL_*` déclarés, 0 émetteur ; e-mails client par `send_mail` direct, hors préférences et journal ; 0 compte portail en prod → helper unique par `notify` | STATIQUE (lecture) | ASOC27 |
| C-ASOC-137 | PF2.2 | C10 | S3 | `apps/stock/services.py::_notifier_candidature_fournisseur` | `fournisseur_candidature` et `trust_center_audit_expire` émis mais absents d'`EventType` : `notify` rend `None`, administrateurs jamais prévenus → les cataloguer | STATIQUE (lecture) | ASOC28 |
| C-ASOC-138 | PF2.2 | C10 | S3 | `core/tasks.py::verifier_fraicheur_trust_center_task` | entrée Trust Center marquée « alertée » et compteur incrémenté sans aucune notification créée (type inconnu), plus jamais relancée → marquer seulement si une notification existe | STATIQUE (lecture) | ASOC29 |
| C-ASOC-139 | PF2.2 | C8 | S3 | `apps/stock/tasks.py::_recipients_reappro` | alertes de réapprovisionnement : filtre `role_legacy`, repli « tous les actifs » sans filtre interne (comptes portail compris) → `resolve_recipients` | STATIQUE (lecture) | ASOC30 |
| C-ASOC-140 | PF2.2 | C13 | S4 | `apps/notifications/services.py::notify_security_change` | création sans point de sauvegarde et e-mail synchrone hors `on_commit` ; appelants en autocommit aujourd'hui → point de sauvegarde, envoi au commit | STATIQUE (lecture) | ASOC31 |
| C-ASOC-141 | PF2.3 | C9 | S3 | `apps/notifications/digests.py::_run_digest` | récap 07:30 et balayage 08:00 tous les jours, week-end et fériés compris, empilés le lundi ; le jumeau des relances saute les jours non ouvrés → garde jour ouvré de la société | STATIQUE (lecture) | ASOC22 |
| C-ASOC-142 | PF2.3 | C6 | S4 | `apps/outillage/tasks.py::notifier_calibration_proche` | dédoublonnage lu sur la présence d'une `Notification` : in-app coupé ⇒ e-mail chaque matin → marqueur d'émission (outil, destinataire, échéance) | STATIQUE (lecture) | ASOC32 |
| C-ASOC-143 | PF2.3 | C9 | S3 | `apps/sav/services.py::compute_sla_reponse_due_at` | SLA SAV en jours ouvrés sur `core/calendar.py` (week-end et fériés marocains codés en dur), pas sur le calendrier de la société : trois sources de jours ouvrés → un calendrier par société | STATIQUE (lecture) | ASOC80 |
| C-ASOC-144 | PF2.3 | C9 | S3 | `apps/crm/horaires.py::_local` | `fuseau_horaire` lu pour l'affichage seul, l'onboarding accepte Dakar ou Paris ; fenêtres, report des notifications et « aujourd'hui » raisonnent en Casablanca → fuseau de la société (D-ASOC-8) | STATIQUE (lecture) | ASOC84 |
| C-ASOC-145 | PF2.3 | C3 | S3 | `apps/ventes/scheduled.py::pre_echeance_reminders` | rappel seulement si `date_echeance == today + N` : beat raté, réglage changé ou délai < N ⇒ jamais rappelée, alors que le marqueur permettrait une fenêtre → fenêtre bornée par le marqueur | STATIQUE (lecture) | ASOC85 |
| C-ASOC-146 | PF2.4 | C3 | S3 | `frontend/src/pages/ventes/NoteDebitDialog.jsx::NoteDebitDialog` | modale de note de débit sur `useState('20')` : facture à 14 % ouverte sur 20, envoyé tel quel (le serveur prendrait le taux de la facture) → taux de la facture à chaque ouverture | STATIQUE (lecture) | ASOC49 |
| C-ASOC-147 | PF2.4 | C9 | S4 | `apps/facturation/views/facture.py::FactureViewSet.perform_create` | `escompte_pct_defaut` et `escompte_jours_defaut` lus par la seule facture manuelle, aucun écran ; acompte et tranches d'un devis signé sans escompte → les appliquer à toutes les factures | STATIQUE (lecture) | ASOC87 |
| C-ASOC-148 | PF2.5 | C1 | S3 | `apps/portail/views_client.py::tableau_de_bord_client` | carte « Tickets SAV ouverts » compte les tickets, l'écran qu'elle ouvre liste les demandes : 1 demande et 0 ticket ⇒ 0 ; la garde de parité ne compare que devis et factures → même définition | STATIQUE (lecture) | ASOC45 |
| C-ASOC-149 | PF2.5 | C10 | S3 | `apps/portail/views_client.py::MesDemandesSavPortailViewSet.create` | demande SAV ou justificatif déposé par le client : audit seul, personne n'est prévenu côté équipe → type dédié `portail_demande_client` | STATIQUE (lecture) | ASOC46 |
| C-ASOC-150 | PF2.5 | C3 | S3 | `apps/ged/services.py::resolve_partage_public` | lien public d'un document « obsolète » encore servi ; le portail et la corbeille le ferment → 404 indistinct, comme les jumeaux | STATIQUE (lecture) | ASOC47 |
| C-ASOC-151 | PF2.5 | C6 | S4 | `apps/ged/services.py::router_document_module` | idempotence « une référence = un document » cherchée dans le dossier résolu : changer le dossier cible duplique le document → chercher par (société, référence) | STATIQUE (lecture) | ASOC50 |
| C-ASOC-152 | PF2.5 | C1 | S3 | `apps/parametres/i18n_resolver.py::resolve_langue_sortie` | langue du client résolue par le PDF et la cadence, jamais par un e-mail ou un WhatsApp SAV, livraison, rappel de RDV : PDF arabe joint à un e-mail français → chaque sortie client résout la langue | STATIQUE (lecture) | ASOC83 |
| C-ASOC-153 | PF2.5 | C1 | S3 | `apps/parametres/serializers_email.py::EmailTemplateSerializer` | colonnes `sujet_en/ar`, `corps_en/ar` lues par `get_template`, ni servies ni éditables (0 occurrence dans `frontend/src`) → les exposer à l'écran Paramètres › E-mails | STATIQUE (lecture) | ASOC99 |
| C-ASOC-154 | PF2.6 | C18 | S2 | `frontend/src/pages/parametres/ConfidentialiteSection.jsx::DsrRequests` | « Traiter » POSTe sans confirmation, même un effacement ; `resultat` jamais lu : l'accès n'est ni affiché ni livré ; états « en vérification » et « partielle » sans libellé → geste complet | STATIQUE (lecture) | ASOC64 |
| C-ASOC-155 | PF2.6 | C10 | S3 | `core/dsr.py::exporter` | export d'accès limité à 4 fournisseurs (calepinage, crm, stock, ventes) : ni factures et avoirs, tickets SAV, chantiers, visites, documents portail, chatter, consentements, Tiers → compléter | STATIQUE (lecture) | ASOC67 |
| C-ASOC-156 | PF2.6 | C7 | S3 | `apps/crm/dsr_provider.py::prospects_hors_duree` | rétention 3 ans : `client__isnull=True` exigé, or le client naît au premier devis ⇒ tout prospect devisé gardé à vie, clients sans rétention → client sans facture = prospect (D-ASOC-4) | STATIQUE (lecture) | ASOC74 |
| C-ASOC-157 | PF2.7 | C7 | S3 | `apps/reporting/services.py::taux_gain` | métrique gouvernée `taux_conversion` = signés ÷ toutes les pistes : 25 % contre 33,3 % pour le taux de gain (gagnés ÷ non perdus) sur 1 signé, 1 perdu, 2 ouverts → un seul taux (D-AANA-1) | STATIQUE (lecture) | ASOC72 |
| C-ASOC-158 | PF2.8 | C10 | S3 | `frontend/src/pages/crm/ParrainagePage.jsx::ParrainagePage` | parrainage saisi à l'écran : ni `filleul_lead` ni `filleul_client` envoyés, jamais « Converti » à la signature du filleul (contournement : sélecteur de statut) → poser le filleul | STATIQUE (lecture) | ASOC68 |
| C-ASOC-159 | PF2.8 | C3 | S3 | `apps/crm/clients_pilotage.py::handle_parrainage_signup` | récompense par défaut posée à la saisie manuelle seulement ; parrainages du site sans `recompense`, absents du total des récompenses dues → même fonction de création | STATIQUE (lecture) | ASOC69 |
| C-ASOC-160 | PF2.8 | C9 | S3 | `apps/crm/clients_pilotage.py::handle_parrainage_signup` | `referral_enabled` sans lecteur dans crm : parrainages et notifications créés même éteint ; prod : réglage déjà allumé, 0 parrainage → câbler le réglage (D-ASOC-7) | STATIQUE (lecture) | ASOC70, ASOC104 |
| C-ASOC-161 | PF2.8 | C6 | S3 | `apps/crm/serializers_clients.py::ParrainageSerializer` | `filleul_client` = `parrain` ou second parrainage du même filleul acceptés par l'API ; aucune unicité, `.first()` à la conversion (API seule, avenant non rejoué) → refus 400 | STATIQUE (lecture) | ASOC71 |
| C-ASOC-162 | PF2.8 | C3 | S4 | `frontend/src/pages/crm/ParrainagePage.jsx::ParrainagePage` | colonne « Filleul » affiche le texte saisi `filleul_nom`, pas `filleul_display_nom` servi (lead ou client lié d'abord) → afficher le nom servi | STATIQUE (lecture) | ASOC75 |
| C-ASOC-163 | PF2.9 | C3 | S3 | `apps/audit/signals.py::_on_post_save` | écritures d'argent du système hors requête sans ligne d'audit (passage en retard de 00:30, relances automatiques) ; `NoteDebit` hors `TRACKED_MODELS` → journal « système », note de débit suivie | STATIQUE (lecture) | ASOC81 |
| C-ASOC-164 | PF2.9 | C3 | S3 | `apps/sav/views.py::SavSlaSettingsViewSet.create` | réglages SLA SAV, routage des notifications, jours ouvrés et supervision modifiés sans ligne au « Journal des réglages » (qui ne lit que `SettingsAuditLog`) → journaliser les quatre | STATIQUE (lecture) | ASOC82 |
| C-ASOC-165 | PF2.9 | C6 | S4 | `core/trash.py::restaurer` | lead supprimé puis restauré : ni ligne de chatter « restauré » ni prochaine étape, contrairement à l'archive ; le restaurateur `crm.lead` promis par le registre n'existe pas → abonné à la restauration | STATIQUE (lecture) | ASOC86 |

## 4. Réfutés, requalifiés, fusionnés
| Constat | Verdict | Argument (sonde ou fichier::symbole) |
|---|---|---|
| C-ASOC-040 | maintenu S1, élargi | seconde lentille : la signature client passe malgré le changement ; `empreinte_visible` compare l'échéancier STOCKÉ, jamais les jalons société lus ; 34 devis envoyés en prod |
| C-ASOC-001 | élargi, abaissé | seconde lentille : relance de 08:15 en e-mail direct hors `notify`, push d'engagement vers l'inactif ; jambe `notify` abaissée ; prod : e-mail non configuré → S2, S1 dès qu'il l'est |
| C-ASOC-004, 005, 042, 062 | requalifiés S2 → S3 | préférence coupée par l'utilisateur, statut visible aux approbations, seul le re-rendu dérive (exemplaire signé séparé), aperçu corrigeable avant WhatsApp : aucune écriture fausse |
| C-ASOC-060 | requalifié S1 → S2 | aucun montant ni écriture comptable ; obligation d'effacement non tenue, sans contournement à l'écran |
| C-ASOC-061 | élargi | chatter du lead : 11 champs d'identité suivis avec anciennes et nouvelles valeurs, `crm.LeadActivity` déclaré « historique conservé » ; lu, non rejoué ; D-ASOC-3 : caviarder ; fusionné ici |
| C-ASOC-064 | élargi | même journal à exporter, effacer et purger par âge ; titres de `Notification` nominatifs : jumeau lu (§7) |
| C-ASOC-065, 154 | maintenus S2 | 065 : indicateur faux sans écriture (S1 si les KPI de pilotage valent argent) ; 154 : lu, recoupé par la sonde C-ASOC-063, critère C18 sans sonde obligatoire |
| C-ASOC-132 | borné | pas de tâche de migration : NTPLT11 la garde ; neuf ici = l'affirmation de couverture du résumé et de la consigne du triage |
Porte : 0 constat réfuté sur 56 candidats bruts (2 fusionnés dans un autre constat, 1 scindé en deux) ; 55 constats : 19 prouvés par sonde (2 rejouées en seconde lentille), 36 lus (S2 1, S3 27, S4 8) · seconde lentille sur 2 S1 candidats : 1 maintenu, 1 abaissé en S2 conditionnel, 2 élargis, 0 réfuté.

## 5. Non-risques
| Zone | Preuve | Valide tant que |
|---|---|---|
| notification en transaction annulée | `notify` écrit sous point de sauvegarde et diffère le hors-app à `on_commit` ; la ligne différée est annulée avec l'émetteur | `notify_security_change` suit ce chemin (C-ASOC-140) |
| livraison différée | réclamation atomique `UPDATE … WHERE programmee_pour IS NOT NULL` ; préférences, module et `is_active` relus au réveil | le compte est relu au réveil |
| effets externes et doubles émissions | webhooks, automatisation, WhatsApp, CAPI et `lead_erased` à `on_commit` ; `facture_payee` sous verrou ; `intervention_completed` borné | webhook aligné sur le bus (C-ASOC-131) |
| salle de vente et apporteurs parqués | réglage éteint : liste, détail, lien public, widget, signal fermés ; commission gardée par `apporteurs_actifs` | D-ACRM-6 inchangée |
| numérotation, identité de la facture | `create_numbered` partout, facture numérotée à l'émission ; vendeur et acheteur figés : un effacement ne réécrit pas une facture émise | RIB lu du figé (C-ASOC-043) |
| gel à l'envoi du devis | CGV, barème, fiches produit, ville de calcul figés ; GED : pas de version sous signature en attente, PDF signé figé | l'échéancier et l'identité rejoignent le gel (C-ASOC-040, 042) |
| rétention et imports | tout en lecture seule tant que `RETENTION_AUTO_APPLY` et `CRM_LEAD_RETENTION_ACTIF` sont faux (choix fondateur) ; `_journaliser_maj` trace chaque écrasement | armement : lire C-ASOC-156 avant |

## 6. Décisions
| D-id (`docs/audits/decisions.yml`) | Question (une ligne) | Statut | Tâches |
|---|---|---|---|
| D-ASOC-1 | devis envoyé sans échéancier propre : le réglage société change avant l'acceptation — quelle règle | figer_a_l_envoi | ASOC95 |
| D-ASOC-2 | module Chantiers désinstallé : un devis accepté crée chantier et réservations — quelle règle | rien_creer | ASOC2 |
| D-ASOC-3 | effacement 09-08 : l'historique du lead garde les valeurs d'identité — quelle règle | caviarder | ASOC62 |
| D-ASOC-4 | rétention 3 ans : tout prospect devisé a un client et reste gardé à vie — quelle règle | client_sans_facture_est_prospect | ASOC74 |
| D-ASOC-5 | métriques de CA ignorent les avoirs que le tableau de bord déduit — qu'est-ce que le CA | net_d_avoirs | ASOC73 |
| D-ASOC-6 | effacement partiellement échoué marqué « traitée » et terminal — quelle règle | statut_partielle | ASOC65 |
| D-ASOC-7 | réglage « parrainage activé » sans lecteur — le câbler ou le retirer | cabler_le_reglage | ASOC70 |
| D-ASOC-8 | fuseau de la société en affichage seul, fenêtres en Casablanca — quelle règle | fuseau_de_la_societe | ASOC84 |

## 7. Optionnel (jamais une tâche)
- Dépôt du client sur son portail : il part en GED sans accès de lecture pour son auteur, absent de « Mes documents » ; lu, plus aucun identifiant libre (ASOC149 ne notifie que l'équipe).
- « Aujourd'hui » de la facturation et heures des beats : `date.today()` des balayages et beats en Casablanca fixe ; impact nul tant que l'heure du beat ne bouge pas ; hors du périmètre de D-ASOC-8 (fenêtres, appels, report).
- Consigne `problemes-prod` : affirme que l'outbox couvre « ce que personne ne vit encore » ; sans propriétaire, ASOC5 n'ajoute que le drapeau `outbox_alimentee` ; à reformuler à la main.
- Expéditeur : tous les e-mails partent de `DEFAULT_FROM_EMAIL`, sans `reply_to` société (question fondateur ouverte) ; `pay_page` sert la devise `MAD` en dur ; le sceau du PDF signé n'inclut pas l'identité vendeur : lus, non vérifiés.
- Re-acceptation d'un devis dés-accepté : règles d'automatisation rejouées faute de marqueur d'occurrence (ambigu) ; titres de `Notification` nominatifs ; fichier MinIO orphelin possible si le routage GED échoue.

## 8. Limites, non couvert, écarts
- Non couvert : écrans en navigateur (confidentialité, parrainage, note de débit, portail) ; `sav` et `monitoring` désinstallés (jumeaux de C-ASOC-002 lus) ; rapports, `insights`, `compta`, RH et paie, `grc` ; montant du `SlaCredit` (C-ASOC-143 passerait S2) ; `core/trash.py::restaurer` contre `apps/trash`.
- Écart à la méthode : 36 constats sans sonde, dont 1 S2 sur le critère C18 non soumis à sonde (C-ASOC-154) → ponctuel : les rejouer au `vérifie ASOC`.
- Écart à la méthode : sondes jouées dans le conteneur monté sur c38868a62, ancêtre de la base ; diff des fichiers sondés lu, aucun hunk sur les mécanismes → ponctuel : conteneur du jour.
- Écart à la méthode : pas de table `PF2.json` ni de rejeu de parcours (étapes = couches du socle) → ponctuel : les rattacher au `vérifie ASOC`.
- Limites des sondes : e-mail et push remplacés par des enregistreurs ; les autres balayages jumeaux de C-ASOC-006 et les autres `try` nus de C-ASOC-003 non rejoués un par un.
- Fraîcheur : `main` a avancé de 31a4bce à 86b4067 (11 commits, docs seulement : audit PF1) pendant l'audit ; aucun fichier ancré modifié, aucun correctif mergé.
- Incident prod : aucun incident ouvert ; avant ASOC95, trancher le sort des 34 devis déjà envoyés (le gel ne vaut que pour les nouveaux envois) ; avant ASOC74, compter les prospects hors durée.

## 9. Coût et routage
Coût : H0 S1 O14 F1 · jetons sous-agents ≈ 5,5 M · tâches 70 (P0 2 P2 19 P3 49 GATED 0) · constats S1 1 S2 10 S3 36 S4 8.
Fable : une critique de complétude, 8 trous tous lus (S3 et S4) ; elle a trouvé les couches transverses laissées de côté par les lanes de module : trois calendriers de jours ouvrés concurrents (C-ASOC-143), journal aveugle aux gestes d'argent du système (C-ASOC-163), langue et fuseau de la société ignorés (C-ASOC-152, C-ASOC-144).
Routage : `PLAN_AUDIT_*.md` LEAD 15 · PARAMETRES 13 · TRANSVERSE 8 · DOCUMENTS 7 · DEVIS 6 · ANALYSE 5 · FACTURATION 5 · SECURITE 4 · MOTEUR 2 · SAV 2 · STOCK 2 · CHANTIERS 1 · priorité : S1 → P0 (ASOC40, ASOC95), S2 → P2, S3 et S4 → P3 · aucune tâche d'acceptation posée · PR #1304.
