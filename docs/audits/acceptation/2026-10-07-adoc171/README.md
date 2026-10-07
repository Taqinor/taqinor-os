# ADOC171 — acceptation live du suivi public (07/10/2026)

Pile locale mise à `origin/main` = `1fc8c8b5a` (merge PR #851), 15 migrations appliquées, conteneurs django/celery redémarrés.
Scénario joué par les vrais endpoints HTTP (compte `demo_admin`, société « TAQINOR Démo »), lecture anonyme du suivi deux fois par étape,
recoupée par curl via nginx. Horloge : `django.utils.timezone.now` patché (freezegun absent du conteneur). Deux devis :
A = DEV-202610-0001 (devis 176, chantier 55), B = DEV-202610-0002 (devis 177, chantier 56, annulé). Jetons de partage masqués.

| # | Attendu | Verdict | Preuve |
|---|---|---|---|
| 1 | Signé : « accepté » fait, Matériel/Installation non faits | PASS | `*_A_01_signe.json` |
| 2a | Chantier `materiel_commande` coche « Matériel » | **FAIL** — rien ne publie le jalon | `*_A_02a_appro_statut_chantier_J+3.json` |
| 2b | Jalon appro synchronisé coche « Matériel » daté | PASS (jalon posé en base, puis `synchroniser_jalon_portail`) | `*_A_02b_*` |
| 3a | « Installation » non faite pendant la pose | PASS | `*_A_03a_pose_en_cours_J+8.json` |
| 3b | « Installation » faite à la pose réelle (`installe`) | **FAIL** — reste non faite | `*_A_03b_pose_statut_installe_J+10.json` |
| 3c | Jalon pose synchronisé coche « Installation » (17/10) | PASS (même réserve que 2b) | `*_A_03c_*` |
| 4 | Facture émise coche « Facturé », annulée la décoche | PASS | `*_A_04*` |
| 5 | Paiement encaissé coche « Acompte », rejeté le décoche ; `mis_a_jour_le` revient | PASS | `*_A_05*` |
| 6 | Chantier annulé décoche Matériel et Installation | PASS | `*_B_03_chantier_annule.json` |
| 7 | Aucune étape cochée sur une ligne annulée/rejetée | PASS | lignes 4-6 |
| 8 | Jalons = ceux du portail client | PASS à chaque 200 | tous |
| 9 | `mis_a_jour_le` = date du dernier jalon fait | PASS | tous |
| 10 | Deux requêtes ⇒ JSON identique (hors `generated_at`, horodatage technique du contrat) | PASS | tous |
| 11 | 200 à J+31 | PASS | `*_A_06_J+31_*` |
| 12 | 200 à réception+90, 404 à réception+91 | PASS | `*_A_08*` |
| 13 | Révocation ⇒ 404 immédiat (nginx aussi) | PASS | `*_A_09b_*`, `nginx_A_revoque.txt` |
| 14 | Réponse conforme à `ventes/contract_samples/suivi_public.json` | PASS (le 404 dit « Ce lien de partage a expiré… » au lieu de « Introuvable. » — cosmétique) | tous |

**Constat principal → ADOC172 (docs/plans/PLAN_AUDIT_CHANTIERS.md)** : passer le chantier à `materiel_commande` / `installe`
ne publie aucun jalon ; depuis SOLMVP13 (commit 6324012f3) aucun écran ni service ne pose un jalon appro/pose. Seule la réception
synchronise le sien. 403 `otp_required` non testé (liens sans code).
