"""N1 — index PARTIEL ``programmee_pour`` sur ``notifications_notification``,
posé EN CONCURRENT (YOPSB6).

``notifications_notification`` est une table VIVANTE : chaque ``notify()`` y
écrit. Un ``AddIndex`` nu la verrouillerait en écriture pendant toute la
construction (garde ``scripts/check_safe_migrations.py``). On passe donc par
l'opération bornée de ``core.migrations_utils`` (``CREATE INDEX
CONCURRENTLY`` + ``lock_timeout`` 3 s remis dans un ``finally``) ; le helper
public ``concurrent_index_migration`` ne sait pas poser la CONDITION d'un
index partiel, d'où l'usage direct de son opération. L'index ne contient que
les notifications en attente de livraison (quelques dizaines par nuit),
jamais l'historique.
"""
from django.db import migrations, models

from core.migrations_utils import _AddIndexConcurrentlyBorne


class Migration(migrations.Migration):

    # CREATE INDEX CONCURRENTLY est interdit dans une transaction.
    atomic = False

    dependencies = [
        ('notifications', '0065_n1_notification_programmee_pour'),
    ]

    operations = [
        _AddIndexConcurrentlyBorne(
            model_name='notification',
            index=models.Index(
                condition=models.Q(('programmee_pour__isnull', False)),
                fields=['programmee_pour'],
                name='notif_programmee_pour_idx'),
        ),
    ]
