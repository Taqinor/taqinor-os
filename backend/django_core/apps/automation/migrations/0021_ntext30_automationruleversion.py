# NTEXT30 — versionnement d'une règle d'automatisation (additif, réversible).
# Une nouvelle table : aucune règle existante n'a d'historique tant qu'elle
# n'est pas modifiée une première fois après ce déploiement.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('automation', '0020_ntext27_custom_record_saved'),
    ]

    operations = [
        migrations.CreateModel(
            name='AutomationRuleVersion',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('version', models.PositiveIntegerField(
                    help_text='Rang incrémental (1, 2, 3…), par règle.')),
                ('snapshot', models.JSONField(
                    blank=True, default=dict,
                    help_text='nom/trigger_type/trigger_config/action_type/'
                              'action_config/steps figés à cet instant.')),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('auteur', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='automation_rule_versions_creees',
                    to=settings.AUTH_USER_MODEL)),
                ('rule', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='versions', to='automation.automationrule',
                    verbose_name='Règle')),
            ],
            options={
                'verbose_name': "Version de règle d'automatisation",
                'verbose_name_plural': "Versions de règle d'automatisation",
                'ordering': ['-version', '-id'],
                'unique_together': {('rule', 'version')},
            },
        ),
        migrations.AddIndex(
            model_name='automationruleversion',
            index=models.Index(
                fields=['rule', '-version'],
                name='automation_ruleversion_idx'),
        ),
    ]
