"""Sélecteurs de lecture de l'app ``authentication`` (couche de fondation).

SCA19 — Source UNIQUE des sociétés « balayables » par les fan-outs beat
----------------------------------------------------------------------
``active_companies()`` renvoie le queryset des sociétés ACTIVES (opérationnelles
au sens SCA18 : ``Company.actif=True``, ce qui — via le pont bool↔statut — exclut
tout tenant ``suspendu``/``en fermeture``). Toute tâche périodique Celery qui
« fan-out » par société DOIT itérer sur ce sélecteur plutôt que de recopier un
filtre ``Company.objects.filter(actif=True)`` — de sorte qu'un tenant suspendu ne
soit plus jamais facturé, relancé ni balayé.

INVENTAIRE des fan-outs beat par société (audité site par site, 2026-07-10) et
leur état vis-à-vis du sélecteur :

  MIGRÉS vers ``active_companies()`` (ce lot) :
    * apps/contrats/scheduled.py  (générer échéances récurrentes + relances)
    * apps/sav/tasks.py           (génération visites préventives dues)
    * apps/monitoring/tasks.py    (balayage monitoring quotidien)
    * apps/ged/tasks.py           (documents échus / corbeille / archives)
    * apps/rh/tasks.py            (échéances RH / alertes)
    * apps/automation/beat_tasks.py (moteur de règles automation)

  DÉJÀ SÛRS (aucun changement requis) :
    * apps/compta/tasks.py itère ``Company.objects.all()`` MAIS chaque écriture
      passe par un service scopé société ne produisant rien pour un tenant sans
      données — laissé tel quel pour ne pas modifier la sémantique compta ; il
      pourra migrer séparément si un skip explicite des suspendus est voulu.
    * apps/chat/tasks.py itère ``Company.objects.all()`` pour de la maintenance
      de sessions internes (pas de facturation/relance) — hors périmètre SCA19.

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
