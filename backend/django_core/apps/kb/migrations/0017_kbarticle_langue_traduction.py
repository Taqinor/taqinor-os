# XKB18 — Articles multilingues FR/AR/EN. Entièrement additif : ``langue``
# défaut 'fr' (comportement historique inchangé) ; ``traduction_de`` self-FK
# NULL par défaut ; ``traduction_perimee`` défaut False. Réversible par
# ``git revert`` / ``migrate kb 0016``.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('kb', '0016_alter_kbarticleacl_unique_together_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='kbarticle',
            name='langue',
            field=models.CharField(
                choices=[('fr', 'Français'), ('ar', 'العربية'),
                         ('en', 'English')],
                default='fr', max_length=5, verbose_name='Langue'),
        ),
        migrations.AddField(
            model_name='kbarticle',
            name='traduction_perimee',
            field=models.BooleanField(
                default=False, verbose_name='Traduction à mettre à jour'),
        ),
        migrations.AddField(
            model_name='kbarticle',
            name='traduction_de',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='traductions', to='kb.kbarticle',
                verbose_name='Traduction de'),
        ),
        migrations.AddIndex(
            model_name='kbarticle',
            index=models.Index(
                fields=['company', 'traduction_de'],
                name='kb_article_traduction_idx'),
        ),
    ]
