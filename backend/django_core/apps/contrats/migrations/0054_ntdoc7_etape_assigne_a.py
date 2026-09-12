"""NTDOC7 — Destinataire nomme d'une etape d'approbation (parapheur).

Purement ADDITIF et revertable : un champ FK NULLABLE (``SET_NULL``) plus un
index. Aucune donnee existante n'est touchee, aucune etape n'est reassignee :
``assigne_a`` vaut NULL partout apres la migration, donc le workflow
d'approbation garde exactement son comportement historique (pilote par
``niveau_approbation``). Le champ ne sert qu'a alimenter la file « ce qui
m'attend » du parapheur du dirigeant.
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contrats', '0053_ntsub27_metriques_saas_cache'),
    ]

    operations = [
        migrations.AddField(
            model_name='etapeapprobation',
            name='assigne_a',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='contrats_etapes_assignees',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Assignée à',
            ),
        ),
    ]
