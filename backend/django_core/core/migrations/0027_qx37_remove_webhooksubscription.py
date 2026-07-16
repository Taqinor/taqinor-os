# QX37 (2026-07-10) — Retire le doublon mort ``core.WebhookSubscription``.
#
# Cette table dupliquait la couche webhook vivante ``apps.publicapi`` sans
# jamais être déclenchée (aucun câblage n'appelait ``core.webhooks``). On garde
# UNE seule surface d'abonnement (publicapi). Destructive mais RÉVERSIBLE : le
# ``RunPython`` inverse est un no-op ; l'``AddField`` inverse recrée le modèle
# tel qu'il était (via ``migrations.CreateModel`` sous ``reverse``). Comme
# Django recrée automatiquement la table à partir de l'état de migration
# précédent en cas de ``migrate core 0026``, aucune donnée métier n'est perdue
# côté application (la table n'était lue par aucun code vivant).
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0026_alter_contenttranslation_field_and_more'),
    ]

    operations = [
        migrations.DeleteModel(
            name='WebhookSubscription',
        ),
    ]
