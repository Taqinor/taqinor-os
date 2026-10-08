# Audit X3 « parametres » — dossier d'évaluation (L2, 08/10/2026)

*Dossier partiel (phase 1 — charte). Claim : branche `audit-X3`.*


SHA lu : origin/main (branche audit-X3). Pile locale : checkout `C:\dev\taqinor-os` sur un origin/main récent (dire son SHA :
`git -C C:\dev\taqinor-os log -1 --oneline`, et `git diff --stat <ce SHA> HEAD -- <fichiers sondés>` avant toute sonde).

## Système et frontière
X3 possède : `backend/django_core/apps/parametres/**` (≈ 30 000 l. hors tests/migrations), `apps/notifications/**` (≈ 16 000),
`apps/automation/**` (≈ 9 600), `apps/onboarding/**`, `backend/django_core/core/events/**` (paquet, 1 622 l.) et
`core/event_coverage.py` (surfaces append-only), `frontend/src/pages/parametres/**` (≈ 20 000), `features/parametres/**`,
`features/notifications/**`, `pages/onboarding/**`, `features/onboarding/**`, `pages/approbations/**`,
`frontend/src/api/{parametresApi,notificationsApi,automationApi}.js`. `docs/ownership.yml` PRIME
(`python scripts/check_ownership.py --owner-of`). Lu : chaque LECTEUR d'un réglage dans les autres apps (grep). Apps parquées hors périmètre.

## Objet
Contrat X3 : un réglage est lu UNE seule fois (un seul lecteur canonique, pas de repli codé en dur divergent ailleurs) ; changer
un réglage est tracé (avant/après, qui) et réservé au bon rôle ; un document envoyé/signé garde sa version figée (CGV, mentions,
taux) ; aucun texte client codé en dur hors des gabarits ; un message WhatsApp/e-mail = ce que l'étape promet, jamais envoyé
à un contact en opposition (`ne_plus_contacter`, loi 09-08) ni hors des heures ; chaque événement du bus a un émetteur ET un abonné
vivants (sinon listé et justifié dans `ALLOWED_UNCONSUMED`) ; les automatisations n'écrivent que des champs autorisés, dans la
société, et les webhooks publics sont authentifiés et limités. Personas : Administrateur (réglages), Commercial, Technicien
responsable ; société 43 en second locataire.

## NE PAS REFAIRE
Tâches ouvertes déjà déposées dans `docs/plans/PLAN_AUDIT_PARAMETRES.md` (ASEC, ADOC, AGNR…), SPL (registres partagés), NT*
(new_tasks_plan), ERR-* : CITER, jamais redéposer.

## Critères retenus
C2, C3, C4, C5, C6, C7, C9, C10, C11, C13. (C1 seulement via textes/taux imprimés ; C14 : X6.)

## Étapes (identifiants stables)
- P1 réglages société : P1.1 profil société (ICE, RIB, logos, mentions), P1.2 taxes/TVA/unités/conditions de paiement,
  P1.3 tarifs ONEE/82-21/tarifs officiels, P1.4 statuts et étapes configurables (STAGES.py, règle #2), P1.5 feature flags/licence.
- P2 textes : P2.1 gabarits documents/e-mails/messages, P2.2 i18n/traductions, P2.3 CGV et version figée à l'envoi.
- P3 notifications : P3.1 création/routage/préférences, P3.2 heures calmes/fériés, P3.3 WhatsApp BSP/e-mail sortants, P3.4
  jetons d'approbation, P3.5 digests et balayages.
- P4 automatisation : P4.1 moteur/règles/actions (set_field), P4.2 déclencheurs (bus, webhooks entrants publics), P4.3 simulation.
- P5 bus d'événements : P5.1 signaux déclarés, émetteurs, abonnés, `ALLOWED_UNCONSUMED`, P5.2 abonnés qui supposent un ordre ou
  avalent une erreur dans la transaction de l'émetteur.
- P6 onboarding et approbations (écrans + API).
- P7 écrans paramètres : erreurs sous le champ, pagination, rôle.

## Scénarios H×H
- Un Commercial tente de modifier un réglage société / une règle d'automatisation ⇒ refusé (403/404) et rien n'est écrit.
- Un réglage (TVA, mention, CGV) modifié après l'envoi d'un devis ⇒ le PDF/la page du devis envoyé ne change pas.
- Une règle d'automatisation `set_field` ⇒ n'écrit jamais un champ hors liste blanche ni un objet d'une autre société.
- Un contact en opposition ⇒ aucun message sortant (tous canaux) ; heures calmes respectées (Africa/Casablanca).
- Chaque signal de `core/events` : émetteur ET abonné vivants (grep), sinon justifié.

## Détecteurs (scout)
`python scripts/check_parked_apps.py` ; `python scripts/check_api_shapes.py` ; `python scripts/check_api_contract.py` ;
`python scripts/check_ecrans_atteignables.py` ; `python scripts/rapport_backend_sombre.py` ; `python scripts/check_services_appeles.py` ;
`python scripts/check_stages.py` ; `python scripts/check_tests_source_regex.py` ; `cd backend/django_core && lint-imports` ;
couverture d'événements : exécuter la vérification de `core/event_coverage.py` (lire comment elle est appelée par les tests ;
sinon script python AST/grep : `.send(`/`send_robust(` vs `.connect(`/`@receiver` par signal) ;
grep des envois sortants (`send_mail`, `EmailMessage`, `whatsapp`, `send_template`) et de leurs gardes `ne_plus_contacter`.
