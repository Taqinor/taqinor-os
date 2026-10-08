# Décisions fondateur — revue de la vague 3 sécurité (ASEC), 07/10/2026

Posées de façon interactive pendant la revue adversariale de la vague 3 (lot auth/sécurité ASEC + ALEA).
Correctifs sur la branche `w3-fixes` (commits `ASECxx-revue` / `ALEAxx-revue`) ; note de déploiement
pour le fondateur : `docs/deploy-notes-vague3.md`.

- **ASEC4 — verrou de connexion.** Réponse : « Verrou par compte+IP ». Le plancher plateforme
  (`LOGIN_PLANCHER_ECHECS` = 10 échecs consécutifs, `LOGIN_PLANCHER_VERROU_MINUTES` = 15) verrouille le
  couple (compte, IP) seulement : le titulaire depuis une autre IP n'est pas gêné ; superuser compris, aucune
  exemption. Compteurs dans le cache Django (Redis en prod), IP par `core.throttling.ip_de_requete`. Le
  verrou SOCIÉTÉ opt-in (`lockout_max_attempts`) garde sa sémantique : le compte entier.
- **ASEC14 — réponse quand le compte est verrouillé.** Réponse : « Même réponse que faux ». Compte
  verrouillé (société ou compte+IP) : le mot de passe n'est PAS vérifié, réponse = exactement le 401
  générique d'un mauvais mot de passe, et la tentative est comptée (API et admin Django).
- **ASEC11 — droits par module, agenda.** Réponse : « Rendre le calendrier seulement ». Commercial et
  Technicien gardent la replanification de l'agenda (`calendar/reschedule`, garde au niveau lecture du
  module reporting) ; rapports sauvegardés, config du tableau de bord et alertes KPI restent
  administrateur/responsable. Le passage devis → chantier (`creer-depuis-devis`, `a-facturer`) reste
  ouvert aux rôles ventes via `ventes_creer` (régression ASEC11 corrigée, pas une décision).
- **ASEC10 — gestion des comptes.** Réponse : « Retirer à Admin Ventes ». Admin Ventes ne porte pas
  `users_gerer` : il lit la liste des comptes mais toute écriture `/users/` est refusée (403
  `droit_manquant`). Commercial responsable, Technicien responsable et Responsable gardent le code.

Ne jamais re-demander ces questions.
