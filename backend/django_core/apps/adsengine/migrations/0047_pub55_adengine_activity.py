# PUB55 — Chatter de campagne/ad : AdEngineActivity (notes MANUELLES, acteur +
# société côté serveur). Le fil affiché FUSIONNE ces notes aux événements auto
# (EngineAction appliquées, EngineAlert) à la lecture — jamais dupliqués en base.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adsengine', '0046_pub50_proposal_template'),
        ('authentication', '0025_company_est_demo_mode_presentation'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AdEngineActivity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('entity_type', models.CharField(choices=[('campaign', 'Campagne'), ('adset', 'Ad set'), ('ad', 'Ad')], max_length=10, verbose_name='Type entité')),
                ('entity_meta_id', models.CharField(max_length=64, verbose_name="ID Meta de l'entité")),
                ('body', models.TextField(verbose_name='Note')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='adsengine_chatter_notes', to=settings.AUTH_USER_MODEL, verbose_name='Auteur')),
            ],
            options={
                'verbose_name': 'Note de chatter (Publicité)',
                'verbose_name_plural': 'Notes de chatter (Publicité)',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='adengineactivity',
            index=models.Index(fields=['company', 'entity_type', 'entity_meta_id'], name='adseng_chatter_co_entity_idx'),
        ),
    ]
