# Audit PF9 « doubles clics, gestes rejoués, courses » — BROUILLON (point de contrôle du 11/11, avant fusion)

Point de contrôle de travail : tableau vérifié provisoire, remplacé par le dossier v3 avant la PR.


En cours au moment de l'écriture : vérificateur D (verif_D.md), critique de complétude (critique.md).
→ rédaction ≤ 3 lots (adapter pf8_brief_redaction.md : AMSG→ACNC) → éditeur (pf4_brief_editeur.md adapté) → gardes → PR.

notes de débit 0 ; avoirs 2 (type `correction`) ; encaissements groupés 0 ; Paiement 7 (4 factures, 2 factures avec ≥ 2
paiements ; doublon même jour non mesuré) ; pièces SAV 0, prêts SAV 0 ; BCF 5 (1 brouillon, 4 envoyés, 8 lignes) ; réceptions 0 ;
factures fournisseur 0 ; MouvementStock 260 ; ventes.BonCommande 3 (1 confirmé, 2 annulés).
Règle de gravité appliquée : un geste jamais utilisé en prod = S3 latent (brief) ; utilisé = S2 si rejeu après délai / deux onglets.

## Tableau provisoire (ordre de gravité ; numéros définitifs à la fusion)
S2 réels :
1. enregistrer-paiement partiel rejoué (apps/ventes/domain/encaissements.py::enregistrer_paiement ; écran PaiementDialog.jsx n'envoie pas `idempotency_key` que le service accepte ; contrainte uniq_paiement_idempotency_par_societe) — rejoué (a_rejeu_paiement_partiel.py, vA_rejeu_argent.py) ; 7 paiements en prod.
2. suppression d'une facture pendant son émission (apps/ventes/... facture.py::perform_destroy, pas de verrou ni relecture ; VNT14 cochée) — lecture.
3. BCF update / perform_destroy concurrent d'« envoyer » (apps/stock/serializers.py::update, _upsert_lignes ; ASTK84 cochée ; aucun écran n'envoie lock_version) — lecture ; 5 BCF en prod.
4. mouvements manuels / transferts de stock sans clé, dialogue gardé après délai (B3 partie stock + D2) — lecture ; 260 mouvements.
5. hausse de prix en masse cumulée au nouvel essai (apps/stock/services.py::apply_product_bulk set_price %, BulkProductBar.jsx) — rejoué (d_replay_bulk_prix.py) ; usage non mesuré.
6. avoir partiel / retour client partiel rejoué (facturation_ops.py::creer_avoir_facture) — lecture ; 2 avoirs `correction` (à relier).
S3 latents (jamais utilisés en prod) : encaissement groupé (rejoué : 20 000 pour 10 000), note de débit, prêt SAV (rejoué), retrait pièce SAV (rejoué 10→16), réception BCF rejouée, facture fournisseur manuelle (doublon_warning ignoré), devis depuis ticket, OCR, agent IA confirm_proposal (rejoué, 0 action), CMI marquer_paye, webhook automation, relancer_job, imports, offlinesync _apply_one, client_ref.
S3 autres : statut lu hors verrou (rejeter_paiement, bon_commande confirmer/annuler/creer_facture), annulations croisées stock (annulation_facture._retourner_stock_de_la_vente), relance doublée, modifier_montant_tranche cas résiduel (VNT67), remise perform_update, transitions chantier/intervention/ticket, lire-puis-créer (ASAV23, generer_devis_reserve…), generer_visites_dues, workflow approuver/rejeter, FactureForm « aucun doublon », LeadsPage optimiste, angles morts des gardes check_read_modify_write (services seulement, variable locale, `return` au lieu de `raise`) et check_get_or_create (core, authentication).
Piste vérif C : crm/views.py::WebsiteLeadPayloadViewSet.replay sans verrou ni dedupe.
Non-risques : numérotation (core/numbering), acceptation publique et interne, commission, .delay hors atomic, post_save, file hors ligne sans argent, axios ne rejoue qu'après 401.
