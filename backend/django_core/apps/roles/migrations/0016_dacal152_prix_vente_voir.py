# D-ACAL-152 (fondateur, 26/11/2026) — « voir les prix de vente » devient un
# code (``prix_vente_voir``) : sans lui, le stock ne sert plus les prix de
# vente. Aucun rôle déjà en base ne doit perdre l'accès en silence, sauf les
# deux rôles SYSTÈME techniciens visés par la décision.
#
# Aller : le code est AJOUTÉ en fin de liste à TOUT rôle en base — rôles
# personnalisés compris — SAUF :
#   * les rôles système « Technicien » et « Technicien responsable » (ils
#     perdent les prix de vente : c'est la décision) ;
#   * les rôles qui portent un code portail (``portail_*``) : axe EXTERNE, ils
#     ne portent jamais de code interne (NTPRT1) ;
#   * les rôles à liste VIDE : ils n'ouvrent déjà aucune lecture du stock
#     côté serveur, et un premier code ferait basculer l'interface du repli
#     historique (« aucun code ») au régime des codes fins.
# Un rôle personnalisé nommé « Technicien » (``est_systeme=False``) le reçoit
# comme les autres : seuls les rôles système sont visés. Idempotente, ligne à
# ligne, ordre des autres codes préservé. ``init_roles`` (relancé à chaque
# déploiement) réaligne de toute façon les rôles système sur le registre.
#
# Retour : retrait du code de tous les rôles. Le code n'existait pas avant
# cette migration : le retrait est exact.

from django.db import migrations

CODE = 'prix_vente_voir'
ROLES_SYSTEME_EXCLUS = frozenset({'Technicien', 'Technicien responsable'})


def _exclu(role, avant):
    if not avant or (role.est_systeme and role.nom in ROLES_SYSTEME_EXCLUS):
        return True
    return any(isinstance(c, str) and c.startswith('portail_') for c in avant)


def ajouter(apps, schema_editor):
    Role = apps.get_model('roles', 'Role')
    for role in Role.objects.all().iterator():
        avant = role.permissions if isinstance(role.permissions, list) else []
        if CODE in avant or _exclu(role, avant):
            continue
        role.permissions = list(avant) + [CODE]
        role.save(update_fields=['permissions'])


def retirer(apps, schema_editor):
    Role = apps.get_model('roles', 'Role')
    for role in Role.objects.all().iterator():
        avant = role.permissions if isinstance(role.permissions, list) else []
        if CODE not in avant:
            continue
        role.permissions = [c for c in avant if c != CODE]
        role.save(update_fields=['permissions'])


class Migration(migrations.Migration):

    dependencies = [
        ('roles', '0015_dacal117_commercial_resp_approuver'),
    ]

    operations = [
        migrations.RunPython(ajouter, retirer),
    ]
