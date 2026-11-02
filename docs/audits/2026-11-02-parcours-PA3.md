# Audit PA3 « devis → signature » — 2026-11-02 — L3
<!-- dossier-v3 | groupe: ADVS | base: 1dfa7986c | fraicheur: d04e9830f | constats: 38 | taches: 44 | decisions: 5 -->

## 1. Charte
| Champ | Valeur |
|---|---|
| Périmètre | parcours PA3 (pilote devis) : lu `apps/ventes/**` (vues devis, `domain/`, `public/`, `quote_engine/**`, `utils/`), `apps/portail/views_client.py`, `apps/crm/receivers*.py`, `apps/crm/fiche_selectors.py`, `apps/installations/receivers.py`, `apps/calepinage/services/devis.py`, `frontend/src/pages/ventes/**`, `frontend/src/features/ventes/**` ; table `PA3.json` |
| Niveau | L3 — chiffres client (écran, PDF, page publique) + PDF client (règle #4) + page publique de signature + multi-société et rôles + parcours chaud |
| Données | demo ; anon : non requis (chaque sonde crée sa société) ; prod lecture seule : aucune |
| Critères retenus | C1, C2, C3, C5, C6, C7, C8, C9, C10, C14, C15, C16, C17, C19, C20 |
| Étapes | PA3-01 composer · PA3-02 envoyer · PA3-03 rendu moteur · PA3-04 page publique · PA3-05 signature publique · PA3-06 acceptation interne · PA3-07 portail · PA3-08 `devis_accepted` · PA3-09 dossier 82-21 · PA3-10 refus · PA3-11 expiration · PA3-12 révision V2 · PA3-13 désacceptation |
| NE PAS REFAIRE | ADEV7, ADEV11-13, ADEV16, ADEV46, ADEV51-53, ADEV57, ADEV95-104 ; AGNR49-62 ; AMOT48, AMOT117 ; QJR500-670 (QJR5) ; CIQ319 ; AGR223, CIQ219 ; ACAL374 ; CADV81, CADV83 ; AARG1-58 (dont AARG26, AARG46, AARG47) ; ASEC11 (matrice), ADEV41 |
| Non-objectifs | facturation en aval (PA4, audité) ; calcul interne du moteur C&I/agricole déjà gardé (CIQ*, AGR*) ; écrans en navigateur (le rejeu joue l'API) ; site public `apps/web` hors consommation de `proposal_data` |

## 2. Couverture
| Lane | Modèle/effort | Chemins lus | Chemins NON lus (raison) |
|---|---|---|---|
| générateur → devis serveur | opus/high | 7 portes de création, `serializers.py`, `domain/noyau_totaux.py`, `domain/creation*.py`, `solar.js`, `lignesEcran.js`, `useCompositionEcran.js` | import de migration (hors MVP) |
| rendu moteur, envoi | opus/high | `quote_engine/builder.py`, `generate_devis_premium.py`, `etude_chiffrage.py`, `views/devis_pdf.py`, `views/devis_envoi.py`, `domain/envoi.py`, `tasks.py` | repli WeasyPrint (interrupteur seul) |
| page publique | opus/high | `public_views.py`, `public/noyau.py`, `public/lecture_views.py`, `public/paiement_views.py`, `public/payload_variantes.py`, `ShareLink` | rendu SSR `apps/web` (consommateur seulement) |
| signature, 3 portes | opus/high | `domain/cycle_vie.py::accept_devis`, `public/signature_views.py`, `views/devis_cycle.py::accepter`, `portail/views_client.py`, `domain/negociation.py`, `modifiabilite.py`, `utils/expiry.py` | — |
| aval de l'acceptation | opus/high | abonnés `devis_accepted`/`devis_refused`/`devis_acceptation_annulee`, `installations/receivers.py`, `crm/receivers.py`, `dossier_8221.py`, `recouvrement.py::expire_stale_devis`, `annuler_acceptation` | `sav/services.py::desactiver_contrat_desaccepte` (contrat SAV) |
| révision, options, batteries | opus/high | `domain/revision.py`, `utils/options.py`, `builder.py::_repartir_options`, `classification.js`, `selectors_portail.py` | — |
| C&I et agricole | sonnet/high | `etude_params` (écrivains/lecteurs), `quote_engine/agricole/**`, `creation_auto.py`, `views/devis_etudes.py` | moteur C&I horaire (gardé par CIQ) |
| sécurité, table, forme | opus/high | permissions des portes PA3, `permissions_registre.py`, `roles/permissions.py`, `crm/fiche_selectors.py`, `PA3.json`, `test_parcours_pa3.py` | — |
Détecteurs : `apps/ventes/tests/test_parcours_pa3.py` (garde de table, logique relue par la lane sécurité) → fige 3 acceptations / 7 créations, faux au code (C-ADVS-050) · non exécutés : `scripts/rejouer_parcours.py PA3` (outil peu fiable sous charge, AARG45) → rejeu par sonde de parcours.
Live : parcours heureux PA3 par l'API réelle sur un enregistrement (sonde `docs/audits/sondes/ADVS/parcours-PA3.py`, de `atomic` à la seconde signature) : 10 étapes 2xx, TTC page publique = TTC devis (33 600,00), société B 404 ×3, 1 signature, 1 chantier, lead SIGNED, aucun `prix_achat` · prévus non joués : écrans (navigateur) · prod : aucune.

## 3. Constats
| C-id | Étape | Critère | Grav. | fichier::symbole | Observé → attendu | Sonde | Tâche(s) |
|---|---|---|---|---|---|---|---|
| C-ADVS-001 | PA3-01 | C7 | S1 | `backend/django_core/apps/ventes/domain/noyau_totaux.py::_absorber_arrondi` | 3 × 1 000 TTC tapés → total 2 900 ; 3 × 700 à 10 % → 2 000 ; palier constant 100 sur centimes perdus → tolérance 1 MAD (D-ADVS-4) | `docs/audits/sondes/ADVS/C-ADVS-001.py` | ADVS3 |
| C-ADVS-002 | PA3-01 | C5 | S2 | `backend/django_core/apps/ventes/serializers.py::DevisSerializer.get_marge_snapshot` | Commercial, Admin RH, Technicien, Commercial terrain sans `marge_voir` lisent la marge 4 000 (→ `prix_achat`) → `marge_voir` seul | `docs/audits/sondes/ADVS/C-ADVS-002.py` | ADVS9 |
| C-ADVS-003 | PA3-01 | C7 | S1 | `backend/django_core/apps/ventes/views/devis_calepinage.py::DevisCalepinageActionsMixin.from_layout` | kWh contredit par les factures : `/atomic` 409, from-layout et « Générer le devis » 201, autoconso 4,48 % imprimée → même 409 | `docs/audits/sondes/ADVS/C-ADVS-003.py` | ADVS26 |
| C-ADVS-004 | PA3-01 | C6 | S2 | `backend/django_core/apps/ventes/domain/creation_auto.py::build_devis_auto` | devis auto C&I avec remise 10 % → remise 0,00, TTC 254 800 → remise posée | `docs/audits/sondes/ADVS/C-ADVS-004.py` | ADVS10 |
| C-ADVS-005 | PA3-01 | C7 | S2 | `backend/django_core/apps/ventes/serializers.py::DevisWriteSerializer` | PATCH conception électrique forgée → persistée, servie par la page publique → champs en lecture seule | `docs/audits/sondes/ADVS/C-ADVS-005.py` | ADVS11 |
| C-ADVS-006 | PA3-01 | C7 | S3 | `frontend/src/pages/ventes/generator/hooks/useCompositionEcran.js::appliquerCompositionServeur` | produit sans TVA : écran 20 %, `creer_ligne` taux du devis, `/devis-lignes/` 10 % panneau → une règle | STATIQUE | ADVS27 |
| C-ADVS-007 | PA3-01 | C7 | S3 | `backend/django_core/apps/ventes/domain/creation.py::create_draft_devis_from_ocr` | OCR et 4 portes naissent MAD / 20 % malgré les défauts société → défaut unique | STATIQUE | ADVS28 |
| C-ADVS-008 | PA3-02 | C17 | S3 | `backend/django_core/apps/ventes/views/devis_envoi.py::DevisEnvoiActionsMixin.envoyer_email` | envoi en échec (409/502) gèle CGV et textes, jamais remplacés au vrai envoi → gel après envoi réussi | STATIQUE | ADVS29 |
| C-ADVS-009 | PA3-02 | C1 | S2 | `backend/django_core/apps/ventes/views/devis_envoi.py::DevisEnvoiActionsMixin.envoyer_email` | rendu en échec → 200, mail « ci-joint » sans pièce jointe, devis « envoyé » → refus nommé, brouillon | `docs/audits/sondes/ADVS/C-ADVS-009.py` | ADVS12 |
| C-ADVS-010 | PA3-02 | C1 | S2 | `backend/django_core/apps/ventes/domain/envoi.py::poser_validite_devis` | PDF joint « valable jusqu'au 02/12 », validité posée 17/11 ; `pdf-partage` sans lien de signature → date posée, lien | `docs/audits/sondes/ADVS/C-ADVS-010.py` | ADVS13, ADVS14 |
| C-ADVS-011 | PA3-03 | C9 | S1 | `backend/django_core/apps/ventes/quote_engine/etude_chiffrage.py::chiffrer_etude` | devis envoyé re-rendu : productible 8 723 → 6 340 kWh, économie 9 159 → 6 657, barème ×1,5 : 10 298 → 14 977 ; signable → figé à l'envoi (D-ADVS-1) | `docs/audits/sondes/ADVS/C-ADVS-011.py` | ADVS1, ADVS2 |
| C-ADVS-012 | PA3-05 | C10 | S2 | `backend/django_core/apps/ventes/domain/cycle_vie.py::_store_signed_pdf` | format mémorisé ignoré : sans onduleur → PDF et page publics 404, aucun exemplaire ; une page → complet à l'acceptation → format suivi | `docs/audits/sondes/ADVS/C-ADVS-012.py` | ADVS15 |
| C-ADVS-020 | PA3-05 | C9 | S1 | `backend/django_core/apps/ventes/domain/cycle_vie.py::accept_devis` | C&I : client renommé dans la transaction qui scelle → sceau rompu, exemplaire signé refusé ; renommage ultérieur aussi → sceau sur l'identité signée | `docs/audits/sondes/ADVS/C-ADVS-020.py` | ADVS8 |
| C-ADVS-021 | PA3-13 | C17 | S1 | `backend/django_core/apps/ventes/domain/cycle_vie.py::_create_esign_record` | re-signature après désacceptation (27 000) : preuve et PDF de la 1re (28 800) servis, sceau « falsifié » → nouvelle preuve (D-ADVS-2) | `docs/audits/sondes/ADVS/C-ADVS-021.py` | ADVS4 |
| C-ADVS-022 | PA3-04 | C8 | S2 | `backend/django_core/apps/ventes/public/payload_variantes.py::_gammes_public` | gamme sœur brouillon servie (42 000), ShareLink créé au GET public, lien 404 → bloc absent, aucune écriture | `docs/audits/sondes/ADVS/C-ADVS-022.py` | ADVS16 |
| C-ADVS-023 | PA3-04 | C8 | S2 | `backend/django_core/apps/ventes/public_views.py::_opts_pdf_public` | case économies décochée : JSON vide, PDF public imprime 21 600 / 10 197 / −53 % → sections suivies au PDF | `docs/audits/sondes/ADVS/C-ADVS-023.py` | ADVS17, ADVS18 |
| C-ADVS-024 | PA3-06 | C1 | S2 | `backend/django_core/apps/ventes/domain/cycle_vie.py::_create_esign_record` | « Marquer accepté » : preuve e-signature, mail client « signature électronique loi 43-20 · Signataire : Commercial » → canal interne | `docs/audits/sondes/ADVS/C-ADVS-024.py` | ADVS19 |
| C-ADVS-025 | PA3-07 | C3 | S2 | `backend/django_core/apps/portail/views_client.py::MesDevisPortailViewSet.accepter` | portail lu à 33 600, ligne corrigée, accepté à 50 400 ; le lien répond 409 → empreinte exigée | `docs/audits/sondes/ADVS/C-ADVS-025.py` | ADVS20 |
| C-ADVS-026 | PA3-10 | C7 | S2 | `backend/django_core/apps/ventes/views/devis_cycle.py::DevisCycleActionsMixin.refuser` | refus lu avant le verrou écrase une acceptation commitée (signature, chantier, lead SIGNED vivants) → 409 `statut` | `docs/audits/sondes/ADVS/C-ADVS-026.py` | ADVS22 |
| C-ADVS-027 | PA3-13 | C17 | S3 | `backend/django_core/apps/installations/selectors.py::blocage_annulation_acceptation` | BCF fournisseur envoyé ignoré : chantier annulé, BCF orphelin → règle D-ADVS-5 (ouverte) | `docs/audits/sondes/ADVS/C-ADVS-027.py` | ADVS40 |
| C-ADVS-028 | PA3-04 | C20 | S3 | `backend/django_core/apps/ventes/public_views.py::public_document` | brouillon au jeton client : `data`/`pdf` 404, `document` 200 et vue comptée → 404 | `docs/audits/sondes/ADVS/C-ADVS-028.py` | ADVS30 |
| C-ADVS-029 | PA3-05 | C3 | S3 | `backend/django_core/apps/ventes/public/signature_views.py::proposal_accept` | accepté en interne puis signé au lien : 200 « acceptée », signature jetée (vu par la sonde 024) → 409 `statut` | STATIQUE | ADVS31 |
| C-ADVS-030 | PA3-13 | C17 | S3 | `backend/django_core/apps/ventes/domain/cycle_vie.py::annuler_acceptation` | `suivi_prolonge_le` gardé : lien dés-accepté valide sans fin → remis à vide | STATIQUE | ADVS32 |
| C-ADVS-031 | PA3-07 | C3 | S3 | `backend/django_core/apps/portail/views_client.py::MesDevisPortailViewSet.accepter` | portail accepte un ICE ≠ client ; le lien répond 409 `ice_divergent` → même garde | STATIQUE | ADVS21 |
| C-ADVS-033 | PA3-13 | C17 | S3 | `backend/django_core/apps/ventes/domain/cycle_vie.py::annuler_acceptation` | validité dépassée : dés-accepté → 409 `expiree`, puis expiré au beat, ré-acceptation 409 → reprise possible | STATIQUE | ADVS33 |
| C-ADVS-034 | PA3-13 | C17 | S3 | `backend/django_core/apps/ventes/domain/capi_signee.py::_fire_capi_signed_quote` | ré-acceptation : conversion SignedQuote ré-émise pleine valeur, même `event_id` → une par devis | STATIQUE | ADVS34 |
| C-ADVS-040 | PA3-04 | C1 | S1 | `backend/django_core/apps/ventes/quote_engine/builder.py::_repartir_options` | « Sans batterie » : câble batterie PDF 20 200 / serveur 19 200 ; batterie « Dyness BX51100 » PDF 26 600 / serveur 41 000, acompte 12 300 → une règle (D-ADVS-3) | `docs/audits/sondes/ADVS/C-ADVS-040.py` | ADVS5, ADVS6 |
| C-ADVS-041 | PA3-04 | C5 | S2 | `backend/django_core/apps/ventes/views/devis.py::DevisViewSet.get_permissions` | Admin RH, Commercial terrain (aucun code ventes) : liste, fiche, historique, `/proposal` 200 → refus (matrice ASEC11) | `docs/audits/sondes/ADVS/C-ADVS-041.py` | ADVS23 |
| C-ADVS-042 | PA3-01 | C5 | S2 | `backend/django_core/apps/crm/fiche_selectors.py::get_company_lead` | Commercial « soi » : lead du collègue 404, mais atomic/auto 201 et from-layout rend son brouillon → 404 | `docs/audits/sondes/ADVS/C-ADVS-042.py` | ADVS24, ADVS44 |
| C-ADVS-044 | PA3-12 | C1 | S1 | `backend/django_core/apps/ventes/domain/modifiabilite.py::empreinte_contenu_signable` | agricole envoyé, HMT corrigée : m³/jour 162 → 17,6, empreinte identique, aucune trace, signature 200 → 409 + trace | `docs/audits/sondes/ADVS/C-ADVS-044.py` | ADVS25 |
| C-ADVS-045 | PA3-11 | C7 | S3 | `backend/django_core/apps/ventes/domain/revision.py::renouveler_devis` | renouveler : prestation C&I 5 000 → 0, forfait 4 500 → 0 (API seule) → prix de la source | `docs/audits/sondes/ADVS/C-ADVS-045.py` | ADVS35 |
| C-ADVS-046 | PA3-01 | C1 | S3 | `frontend/src/pages/ventes/DevisGenerator.jsx` | C&I « les deux » : écran valide l'échéancier sur l'AVEC, serveur sur le SANS (409) → option effective | STATIQUE | ADVS36 |
| C-ADVS-047 | PA3-12 | C1 | S3 | `backend/django_core/apps/ventes/selectors_portail.py::devis_du_client_portail` | V1 acceptée + V2 brouillon : aucune vente au portail → V1 listée (D-ADEV-1) | STATIQUE | ADVS37 |
| C-ADVS-048 | PA3-05 | C1 | S3 | `backend/django_core/apps/ventes/public/paiement_views.py::_deposit_success_payload` | pompage signé : « acompte à régler » + RIB sans condition FDA → règle D-AGQ-12 | STATIQUE | ADVS38 |
| C-ADVS-049 | PA3-04 | C1 | S3 | `backend/django_core/apps/ventes/quote_engine/agricole/synthese.py::synthese_agricole` | carte « Eau / jour » de la page sans « débit déclaré par vous » (PDF oui) → même étiquette | STATIQUE | ADVS39 |
| C-ADVS-050 | PA3-01 | C15 | S3 | `backend/django_core/apps/ventes/parcours/PA3.json` | table ≠ code (entrée PA3-01, 4 appelants d'`accept_devis` contre 3, PA3-08/10/11) → table = code | STATIQUE | ADVS41 |
| C-ADVS-060 | PA3-03 | C9 | S2 | `backend/django_core/apps/ventes/quote_engine/lignes_classement.py::_line_to_item` | fiche produit relue au re-rendu d'un envoyé : garantie 25 → 10 ans, empreinte identique, signature 200 → figée (D-ADVS-1) | `docs/audits/sondes/ADVS/C-ADVS-060.py` | ADVS7 |
| C-ADVS-061 | PA3-02 | C1 | S2 | `backend/django_core/apps/ventes/utils/whatsapp.py::build_single_devis_whatsapp` | lien WhatsApp = PDF brut : code d'accès → 403 `otp_required`, PDF décoché → 404 ; la page répond 200 → lien de la page | `docs/audits/sondes/ADVS/C-ADVS-061.py` | ADVS42 |

## 4. Réfutés, requalifiés, fusionnés
| Constat | Verdict | Argument (sonde ou fichier::symbole) |
|---|---|---|
| C-ADVS-001 | S2 → S1 | sonde : l'argent du document est faux de 100 MAD ; `PAS_ARRONDI_DEVIS` constant, sans réglage |
| C-ADVS-044 | S2 → S1 | sonde : chiffre client changé et signable sans relecture |
| C-ADVS-027 | partiel, S2 → S3 | suites réelles de la désacceptation nommées par le fondateur sans le BCF ; contournement : annuler le BCF ; chaîne DA non rejouée |
| C-ADVS-041 | partiel | Technicien borné par sa portée équipe (404) ; Admin RH et Commercial terrain lisent |
| C-ADVS-045 | S2 → S3 | route API seule (QJR667), résultat brouillon |
| C-ADVS-002 | fusionné | marge : même cause pour Commercial (sonde 002) et pour Admin RH, Technicien, terrain (sonde `docs/audits/sondes/ADVS/C-ADVS-002-L2.py`) |
| C-ADVS-021 | fusionné | page publique (ancien exemplaire servi) et signature (preuve gardée) : une cause, `_create_esign_record` |
| C-ADVS-028 | fusionné | relevé par la page publique et par la lane sécurité (`public_document` sans ADEV11) |
| C-ADVS-050 | fusionné | table décalée relevée par l'aval (PA3-08/10/11) et la sécurité (inventaire des portes) |
Porte : 0 réfuté / 42 bruts (38 après fusion) · seconde lentille : 7 S1 → maintenus 7, élargis 5 (001 voie d'édition et multi-taux, 003 « Générer le devis », 011 barème et redevance, 020 porte interne et renommage, 040 batterie au nom sans « batterie ») · critique de complétude : 2 trous sondés (060, 061), avis S2 sur 003 non retenu (règle fondateur du 30/09 : le chiffre imprimé est faux).

## 5. Non-risques
| Zone | Preuve | Valide tant que |
|---|---|---|
| parcours heureux devis → signature | `docs/audits/sondes/ADVS/parcours-PA3.py` : 10 étapes 2xx, TTC au centime, 1 signature, chantier, lead SIGNED | `accept_devis` reste l'unique fonction d'entrée |
| étanchéité multi-société | parcours-PA3 : société B 404 sur fiche, `/proposal`, accepter ; références d'un autre tenant dans le corps → 404 (lane sécurité) | `SameCompanyFKSerializerMixin` garde la société |
| règle #4 | moteur seul chemin des PDF de devis client ; il n'écrit que `fichier_pdf` et `pdf_render_meta` (lane moteur) | `USE_PREMIUM_QUOTE_ENGINE` reste l'unique interrupteur |
| `prix_achat` côté client | parcours-PA3 (aucune réponse ne le porte) ; aucune lecture dans `quote_engine` ; retrait récursif de `proposal_data` | la marge reste hors des payloads publics |
| trois portes d'acceptation | même `accept_devis`, même verrou de groupe ; signatures concurrentes : un seul effet ; un accepté interne n'écrase jamais une preuve publique | — |
| révision V2 | saisies V1 reprises ; V1 hors jeu partout ; abandon de V2 réactive V1 | `reviser_devis` reste le seul chemin |
| aval | lead jamais avancé sur un devis remplacé, ni deux fois ; expiration jamais sur un accepté | — |
| parité TTC page ↔ PDF hors option | `test_figures_parite.py` (aucun écart connu) | ses compositions ; câble batterie à y ajouter (ADVS6) |

## 6. Décisions
| D-id (`docs/audits/decisions.yml`) | Question (une ligne) | Statut | Tâches |
|---|---|---|---|
| D-ADVS-1 | réglages et fiches relus au re-rendu d'un envoyé | figer_a_l_envoi | ADVS1, ADVS2, ADVS7 |
| D-ADVS-2 | re-signature après désacceptation | nouvelle_preuve | ADVS4 |
| D-ADVS-3 | accessoire de batterie et option | suit_la_batterie | ADVS5, ADVS6 |
| D-ADVS-4 | arrondi à la centaine d'un prix tapé | tolerance_un_dirham | ADVS3 |
| D-ADVS-5 | BCF engagé à la désacceptation | ouverte | ADVS40 |

## 7. Optionnel (jamais une tâche)
- `expiry.date_expiration` prend le jour UTC de `date_creation` : un devis créé entre 00 h et 01 h (Maroc) expire un jour plus tôt (S4).
- Activation d'option sur une offre expirée tant que le beat de 01 h n'est pas passé.
- Dossier 82-21 laissé ouvert après refus ou expiration ; case « marquer le lead perdu » au refus d'un avenant.
- Aucun budget de requêtes sur `proposal_data` (aucune requête en boucle à la lecture).
- PDF public toujours en français ; portail : PDF d'une version remplacée.

## 8. Limites, non couvert, écarts
- Non couvert : écrans en navigateur (rejeu API) ; contrat SAV à la désacceptation (`sav/services.py`) ; chaîne DA de C-ADVS-027 ; onduleurs au nom sans mot-clé (déduits, non sondés, C-ADVS-040) ; clés d'étude résidentielles de C-ADVS-044 (déduites).
- Écart à la méthode : deuxième audit de PARCOURS — entrée `PA3` ajoutée au registre comme `PA4` (groupe ADVS, mot `devis-signature`) ; `scripts/rejouer_parcours.py` toujours remplacé par une sonde de parcours (AARG45 ouverte) ; ponctuel, METHODE inchangée.
- Écart machine : base locale en retard de deux migrations (`facturation.0026`, `parametres.0132`) → `migrate` appliqué avant le rejeu ; charge critique signalée en cours d'audit → un seul sous-agent pendant un temps, deux lanes arrêtées puis relancées ; sondes sérialisées par le verrou à deux créneaux, aucune comptée sur un échec d'infrastructure.
- Incident prod : aucun.

## 9. Coût et routage
Coût : H0 S1 O15 F1 · jetons sous-agents ≈ 6,5 M · tâches 44 (M0 3, M1 0, M2 24, M3 15, GATED 1) dont l'acceptation ADVS43.
Routage : `PLAN_AUDIT_DEVIS.md` 29 · `PLAN_AUDIT_MOTEUR.md` 5 · `PLAN_AUDIT_DOCUMENTS.md` 3 · `PLAN_AUDIT_TRANSVERSE.md` 2 (ADVS23 devis+sécurité, ADVS38 facturation+devis) · `PLAN_AUDIT_CALEPINAGE.md` 2 · `PLAN_AUDIT_GENERATEUR.md` 2 · `PLAN_AUDIT_CHANTIERS.md` 1 · PR #1227.
