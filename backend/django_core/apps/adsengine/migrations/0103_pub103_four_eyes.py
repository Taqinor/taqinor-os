# PUB103 — quatre yeux optionnel : flag GuardrailConfig.require_four_eyes (OFF
# par défaut) + EngineAction.proposed_by (proposeur posé côté serveur). Additif.
#
# NOTE ORCHESTRATEUR : la base de cette worktree s'arrêtait à la migration 0033
# (le lot batch-1 « 0038_pub49_annotation » attendu n'y était pas). La dépendance
# est donc ancrée sur 0033 ; re-chaîner sur la vraie dernière migration au fold.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('adsengine', '0033_guardrailconfig_health_creative_weight_ctr_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='guardrailconfig',
            name='require_four_eyes',
            field=models.BooleanField(
                default=False,
                verbose_name='Double validation (quatre yeux) sur les approbations'),
        ),
        migrations.AddField(
            model_name='engineaction',
            name='proposed_by',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='adsengine_actions_proposees',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Proposée par'),
        ),
    ]
