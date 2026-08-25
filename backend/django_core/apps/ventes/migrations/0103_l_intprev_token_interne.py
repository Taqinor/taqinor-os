import secrets

import apps.ventes.models
from django.db import migrations, models


def _generer_jetons_internes_liens_existants(apps, schema_editor):
    """L-INTPREV (fondateur 25/08/2026) — backfill du jeton d'aperçu interne
    pour tout ShareLink NON EXPIRÉ qui existe déjà au moment de la migration
    (un lien déjà envoyé à un client doit pouvoir recevoir son jeton interne
    sans que le commercial ait à régénérer le lien public). Les liens EXPIRÉS
    ne sont pas touchés : personne ne les rouvrira plus jamais.

    Parcours par tranches de pks via ``.iterator()`` (patron
    check_safe_migrations, déjà suivi par la migration 0100) : la table est
    petite aujourd'hui, mais charger tout le queryset en mémoire d'un coup ne
    scale pas. L'UPDATE lui-même reste PAR LIGNE, volontairement : un jeton
    UNIQUE par lien (secrets.token_urlsafe(32), même générateur que
    ``token``) — jamais une valeur partagée sur tout un lot, qui romprait la
    contrainte unique dès la deuxième ligne touchée.
    """
    ShareLink = apps.get_model('ventes', 'ShareLink')
    from django.utils import timezone
    now = timezone.now()
    pks = (ShareLink.objects
           .filter(expires_at__gt=now, token_interne__isnull=True)
           .values_list('pk', flat=True))
    for pk in pks.iterator(chunk_size=500):
        ShareLink.objects.filter(pk=pk).update(
            token_interne=secrets.token_urlsafe(32))


def _noop_reverse(apps, schema_editor):
    """Reverse volontairement no-op — retirer les jetons internes casserait
    tout aperçu déjà partagé en interne sans aucun bénéfice (un vrai revert
    de la migration retire de toute façon la colonne via le RemoveField
    implicite du reverse d'AddField)."""


class Migration(migrations.Migration):
    """L-INTPREV — second jeton « aperçu interne » sur ShareLink (PROPOSITION
    ventes, apps/ventes/public_views.py) : le commercial peut ouvrir la MÊME
    page publique que le client sans déclencher aucune des traces d'ouverture
    (compteur de vues, note chatter, avance de stage funnel, notification,
    beacon d'engagement).

    Additive only, 3 étapes pour éviter le piège classique « AddField(unique)
    avec un default callable » : (1) colonne NULLABLE sans default posé au
    niveau SQL — un default callable sur un AddField est calculé UNE SEULE
    FOIS par Django et appliqué à TOUTES les lignes existantes via la clause
    DEFAULT de l'ALTER TABLE, ce qui ferait exploser la contrainte unique dès
    qu'il y a plus d'un ShareLink en base ; (2) RunPython qui pose un jeton
    DIFFÉRENT par ligne, mais SEULEMENT pour les liens NON EXPIRÉS (backfill
    batché) ; (3) AlterField qui ajoute le default Python
    (``apps.ventes.models._default_share_token`` — même fonction que
    ``token``, réimportée pour que l'état de migration reste identique à
    celui de ``models.py`` et que ``makemigrations --check`` ne voie aucune
    dérive) SANS effet SQL puisque la colonne reste nullable — seules les
    FUTURES créations via l'ORM en bénéficient. Entièrement révertable
    (reverse du RunPython en no-op explicite, comme la migration 0100)."""

    dependencies = [
        ('ventes', '0102_l2opt_ligne_variante'),
    ]

    operations = [
        migrations.AddField(
            model_name='sharelink',
            name='token_interne',
            field=models.CharField(
                max_length=64, unique=True, null=True, blank=True,
                editable=False,
                verbose_name='Jeton aperçu interne (sans notification)'),
        ),
        migrations.RunPython(
            _generer_jetons_internes_liens_existants, _noop_reverse),
        migrations.AlterField(
            model_name='sharelink',
            name='token_interne',
            field=models.CharField(
                max_length=64, unique=True, null=True, blank=True,
                default=apps.ventes.models._default_share_token,
                editable=False,
                verbose_name='Jeton aperçu interne (sans notification)'),
        ),
    ]
