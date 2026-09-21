"""NTSCM37 — Permissions fines par rôle sur le module SCM.

Six codes ERP dédiés, enregistrés dans le catalogue central
``apps.roles.models.ALL_PERMISSIONS`` (foundation app, exemptée de la
frontière cross-app — CLAUDE.md) :

  * ``scm_previsions_voir`` / ``scm_previsions_editer`` — prévisions de
    demande (NTSCM1/2/3) et événements de demande.
  * ``scm_politiques_stock_editer`` — écriture des politiques de stock
    (NTSCM6, recalcul en masse, assistant NTSCM30).
  * ``scm_sop_voir`` — lecture des cycles S&OP (NTSCM12/13/14/15/27).
  * ``scm_sop_animer`` — droit d'AVANCER le statut d'un cycle S&OP
    (``avancer-statut``, NTSCM12) et des actions d'écriture associées
    (ajustement de la demande, calcul de l'offre, réouverture admin).
  * ``scm_fournisseurs_classement_voir`` — réservé pour un futur écran de
    classement/scorecard fournisseur (NTSCM23, pas encore au plan) : le code
    est enregistré dès maintenant mais n'a pas encore de viewset à garder
    dans cette lane.

Chaque permission passe par ``authentication.permissions.HasPermissionOrLegacy``
(repli sur le palier Responsable/Admin historique pour un compte SANS rôle
fin — jamais de régression pour les comptes hérités, même contrat que le
reste du repo, ex. ``apps/adsengine/views.py``)."""
from authentication.permissions import HasPermissionOrLegacy

IsScmPrevisionsVoir = HasPermissionOrLegacy('scm_previsions_voir')
IsScmPrevisionsEditer = HasPermissionOrLegacy('scm_previsions_editer')
IsScmPolitiquesStockEditer = HasPermissionOrLegacy('scm_politiques_stock_editer')
IsScmSopVoir = HasPermissionOrLegacy('scm_sop_voir')
IsScmSopAnimer = HasPermissionOrLegacy('scm_sop_animer')
IsScmFournisseursClassementVoir = HasPermissionOrLegacy('scm_fournisseurs_classement_voir')
