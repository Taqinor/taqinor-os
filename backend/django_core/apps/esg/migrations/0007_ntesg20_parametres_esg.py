"""NTESG20 — réglages ESG par société (singleton par tenant).

Migration ADDITIVE : une table. Tant qu'une société n'a pas de ligne,
``services.config_esg`` applique les défauts du module — aucun comportement ne
change au déploiement (seuil de dérive 10 %, pondération du badge 1/3 chacun,
destinataire = administrateurs actifs).
"""
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0024_ntprt1_customuser_portee'),
        ('esg', '0006_facteuremissionversioncounter'),
    ]

    operations = [
        migrations.CreateModel(
            name='ParametresESG',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('seuil_alerte_derive_pct', models.PositiveIntegerField(
                    default=10,
                    validators=[
                        django.core.validators.MinValueValidator(1),
                        django.core.validators.MaxValueValidator(100),
                    ],
                    verbose_name="Seuil d'alerte de dérive de trajectoire (%)")),
                ('frequence_reporting', models.CharField(
                    choices=[('mensuelle', 'Mensuelle'),
                             ('trimestrielle', 'Trimestrielle'),
                             ('annuelle', 'Annuelle')],
                    default='annuelle', max_length=15,
                    verbose_name='Fréquence de reporting')),
                ('ponderation_badge_maturite', models.JSONField(
                    blank=True, default=dict,
                    verbose_name='Pondération du badge de maturité (somme = 100)')),
                ('company', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='esg_parametres',
                    to='authentication.company', verbose_name='Société')),
                ('pilote_esg', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='esg_pilotages',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Pilote ESG (destinataire par défaut)')),
            ],
            options={
                'verbose_name': 'Réglages ESG',
                'verbose_name_plural': 'Réglages ESG',
            },
        ),
    ]
