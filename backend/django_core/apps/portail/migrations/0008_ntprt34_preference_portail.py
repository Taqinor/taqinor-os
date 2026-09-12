"""NTPRT34 — Préférence d'affichage (langue) d'un compte portail.

Migration STRICTEMENT ADDITIVE : une nouvelle table, aucun champ touché sur
les modèles existants, aucune donnée déplacée. Les comptes déjà provisionnés
n'ont pas de ligne : l'absence de préférence VAUT « français » (le défaut du
modèle), donc aucun portail ne change d'apparence du fait de cette migration.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # `authentication.Company` naît dans cette migration-là (la FK
        # `company` de TenantModel en dépend).
        ('authentication', '0003_company_alter_customuser_groups_and_more'),
        ('portail', '0007_documentclientportail_fichier_filename_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PreferencePortail',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'langue',
                    models.CharField(
                        choices=[('fr', 'Français'), ('ar', 'العربية')],
                        default='fr', max_length=2,
                        verbose_name='Langue du portail'),
                ),
                (
                    'company',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='%(app_label)s_%(class)s_set',
                        to='authentication.company',
                        verbose_name='Société'),
                ),
                (
                    'utilisateur',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='preference_portail',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='Compte portail'),
                ),
            ],
            options={
                'verbose_name': 'Préférence de portail',
                'verbose_name_plural': 'Préférences de portail',
                'ordering': ['-id'],
            },
        ),
    ]
