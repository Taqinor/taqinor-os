"""Sélecteurs de lecture de l'app ``authentication`` (couche de fondation).

SCA19 — Source UNIQUE des sociétés « balayables » par les fan-outs beat
----------------------------------------------------------------------
``active_companies()`` renvoie le queryset des sociétés ACTIVES (opérationnelles
au sens SCA18 : ``Company.actif=True``, ce qui — via le pont bool↔statut — exclut
tout tenant ``suspendu``/``en fermeture``). Toute tâche périodique Celery qui
« fan-out » par société DOIT itérer sur ce sélecteur plutôt que de recopier un
filtre ``Company.objects.filter(actif=True)`` — de sorte qu'un tenant suspendu ne
soit plus jamais facturé, relancé ni balayé.

INVENTAIRE des fan-outs beat par société (audité site par site, 2026-07-10 puis
RÉ-AUDITÉ par AUD415 le 2026-09-04) et leur état vis-à-vis du sélecteur :

  MIGRÉS vers ``active_companies()`` — lot SCA19 (2026-07-10) :
    * apps/contrats/scheduled.py  (générer échéances récurrentes + relances)
    * apps/sav/tasks.py           (génération visites préventives dues)
    * apps/monitoring/tasks.py    (balayage monitoring quotidien)
    * apps/ged/tasks.py           (documents échus / corbeille / archives)
    * apps/rh/tasks.py            (échéances RH / alertes)
    * apps/automation/beat_tasks.py (moteur de règles automation)

  MIGRÉS vers ``active_companies()`` — lot AUD415 (2026-09-04). L'inventaire
  SCA19 n'avait jamais été rejoué depuis juillet ; ces 10 sites (21 appels)
  balayaient encore TOUTES les sociétés, dont un DESTRUCTIF :
    * apps/ged/services.py        (``purger_corbeille_toutes_societes`` — le
      SEUL fan-out ged resté non scopé, alors que ce module était listé
      « MIGRÉ » ci-dessus ; avec ``GED_PURGE_AUTO_APPLY=1`` la corbeille d'un
      tenant suspendu était purgée DÉFINITIVEMENT chaque nuit à 02:30)
    * apps/credit/tasks.py        (encours quotidien, alerte d'exposition)
    * apps/marketing/tasks.py     (journeys, purge jetons, rappels, scores)
    * apps/stock/tasks.py         (réappro, relance BCF, surcapacité,
      péremption — sa docstring affirmait déjà « par société active »)
    * apps/scm/tasks.py           (les 3 boucles + ``_companies_by_ids``)
    * apps/education/tasks.py     (séances de la semaine, réinscriptions)
    * apps/ai_governance/tasks.py (snapshot de dérive mensuel)
    * apps/ao/scheduled.py        (échéances AO dues)
    * apps/veille_ao/tasks.py     (collecte des sources — relève réseau réelle)
    * apps/ventes/scheduled.py    (rappels devis à facturer, relève IMAP)

  DÉJÀ SÛRS (aucun changement requis) :
    * apps/compta/tasks.py itère ``Company.objects.all()`` MAIS chaque écriture
      passe par un service scopé société ne produisant rien pour un tenant sans
      données — laissé tel quel pour ne pas modifier la sémantique compta ; il
      pourra migrer séparément si un skip explicite des suspendus est voulu.
    * apps/chat/tasks.py itère ``Company.objects.all()`` pour de la maintenance
      de sessions internes (pas de facturation/relance) — hors périmètre SCA19.
    * apps/adminops/tasks.py et apps/compta/scheduled.py recopient
      ``Company.objects.filter(actif=True)`` : sémantique DÉJÀ correcte (aucun
      tenant suspendu balayé), il leur reste seulement à passer par la source
      unique — à migrer par une tâche dédiée, sans urgence de sécurité.

CETTE LISTE NE SE MAINTIENT PLUS À LA MAIN. ``scripts/check_beat_active_
companies.py`` (AUD415, job CI ``backend-lint-fast``) échoue sur tout NOUVEAU
``Company.objects.all()`` / ``filter(actif=True)`` dans un ``tasks.py`` /
``scheduled.py`` / ``beat_tasks.py`` d'``apps/`` hors
``scripts/beat_active_companies_allow.txt`` — c'est la garde qui empêche
l'inventaire de re-dériver deux mois durant.

``authentication`` est une couche de fondation : ce module ne dépend d'AUCUNE
app métier. Les apps métier l'importent (import descendant autorisé).
"""
from __future__ import annotations


def active_companies():
    """Queryset des sociétés opérationnelles (SCA18) à balayer par les beats.

    Un tenant suspendu ou en fermeture a ``actif=False`` (pont bool↔statut), il
    est donc exclu ici — jamais facturé ni balayé. Ordonné par id pour un
    parcours déterministe."""
    from authentication.models import Company
    return Company.objects.filter(actif=True).order_by('id')


def active_company_ids():
    """Ids des sociétés opérationnelles (variante légère sans charger les objets)."""
    return list(active_companies().values_list('id', flat=True))


def revoke_user_sessions(user):
    """Révoque TOUTES les sessions actives d'un utilisateur (NTSEC5/10/25).

    Marque chaque ``UserSession`` non révoquée ``revoked=True`` ET blackliste
    son jeton de rafraîchissement (best-effort) pour qu'il ne puisse plus
    rafraîchir d'accès. Fondation partagée : révocation de sessions lors d'un
    déprovisioning SCIM, d'une éviction de session concurrente ou d'une
    désactivation de compte dormant. Renvoie le nombre de sessions révoquées.
    """
    if user is None or not getattr(user, 'pk', None):
        return 0
    from authentication.models import UserSession
    sessions = list(UserSession.objects.filter(user=user, revoked=False))
    n = 0
    for s in sessions:
        try:
            from rest_framework_simplejwt.token_blacklist.models import (
                BlacklistedToken, OutstandingToken,
            )
            outstanding = OutstandingToken.objects.filter(jti=s.jti).first()
            if outstanding is not None:
                BlacklistedToken.objects.get_or_create(token=outstanding)
        except Exception:
            pass
        s.revoked = True
        s.save(update_fields=['revoked'])
        n += 1
    return n


def comptes_dormants(company, seuil_jours):
    """Comptes actifs d'une société inactifs depuis plus de ``seuil_jours``.

    Inactivité = dernière ``UserSession.last_seen_at`` antérieure au seuil (ou
    aucune session du tout). ``seuil_jours <= 0`` → aucun compte (fonction
    inerte). Company-scopé ; exclut les super-admins (jamais désactivés
    automatiquement). Renvoie un queryset de ``CustomUser``."""
    if company is None or not seuil_jours or seuil_jours <= 0:
        from authentication.models import CustomUser
        return CustomUser.objects.none()
    from datetime import timedelta

    from django.db.models import Max, Q
    from django.utils import timezone

    from authentication.models import CustomUser

    cutoff = timezone.now() - timedelta(days=seuil_jours)
    return (
        CustomUser.objects.filter(
            company=company, is_active=True, is_superuser=False)
        .annotate(derniere_activite=Max('sessions__last_seen_at'))
        .filter(
            Q(derniere_activite__lt=cutoff)
            | Q(derniere_activite__isnull=True))
    )


# NTMOB6 — accueil mobile PAR DÉFAUT selon le rôle métier (nom du Role fin).
# Rôles composés (« Commercial responsable », « Technicien responsable »)
# retombent sur l'accueil de base de leur famille via un préfixe — aucun
# accueil mobile dédié n'existe encore pour ces variantes « responsable ».
_MOBILE_HOME_EXACT = {
    'Directeur': '/mobile/cockpit',
    'Administrateur': '/mobile/cockpit',
    # VTA6 — le « Commercial terrain » n'a QUE l'app Visites (liste blanche
    # `app_visites_voir`) : son accueil mobile est « Ma journée ». Entrée
    # EXACTE, lue avant les préfixes — sans elle il retomberait sur le préfixe
    # « Commercial » → `/mobile/commercial`, un écran qu'il ne voit pas.
    'Commercial terrain': '/visites',
}
_MOBILE_HOME_PREFIX = (
    ('Technicien', '/ma-journee'),
    ('Commercial', '/mobile/commercial'),
)


def default_mobile_home_route(user):
    """Route d'accueil mobile suggérée pour ``user`` (fonction PURE, ne
    persiste rien) : Technicien → ``/ma-journee`` (déjà existant), Commercial
    → NTMOB4, Directeur/Administrateur → NTMOB5, tout autre rôle → ``''``
    (dashboard générique, comportement inchangé). Un compte HÉRITÉ sans Role
    fin retombe sur ``role_legacy``/``is_admin_role`` (même repli que
    ``menu_tier``)."""
    role_nom = user.role.nom if getattr(user, 'role', None) else ''
    if role_nom in _MOBILE_HOME_EXACT:
        return _MOBILE_HOME_EXACT[role_nom]
    for prefix, route in _MOBILE_HOME_PREFIX:
        if role_nom.startswith(prefix):
            return route
    if not role_nom and getattr(user, 'is_admin_role', False):
        return '/mobile/cockpit'
    return ''


# Whitelist stricte des routes mobile persistables (défense en profondeur :
# jamais une route arbitraire écrite depuis le corps de requête).
MOBILE_HOME_ALLOWED_ROUTES = frozenset(
    # VTA6 — `/visites` : l'accueil « Ma journée » de l'app Visites terrain.
    # À NE PAS confondre avec `/ma-journee`, la journée des TECHNICIENS
    # (post-vente), qui appartient à `apps.installations` — deux métiers, deux
    # routes, jamais fusionnées.
    {'', '/ma-journee', '/mobile/commercial', '/mobile/cockpit', '/visites'})
