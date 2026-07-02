# CH4 — Pack de remise client (HandoverPack) assemblé au gate « Remise ».
#
# Additif : référence des pièces (as-built, datasheets, garanties, certificat
# de recette CH3, dossier 82-21, accès monitoring) sans stockage binaire ;
# dégrade proprement quand une pièce manque. Migration écrite À LA MAIN,
# strictement cohérente avec le modèle.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0014_customuser_account_lockout'),
        ('installations', '0050_ch3_commissioning_record'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='HandoverPack',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('titre', models.CharField(
                    blank=True, max_length=160, null=True)),
                ('pieces', models.JSONField(blank=True, default=list)),
                ('monitoring_acces', models.CharField(
                    blank=True, max_length=255, null=True)),
                ('complet', models.BooleanField(default=False)),
                ('date_generation',
                 models.DateTimeField(blank=True, null=True)),
                ('notes', models.TextField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='handover_packs',
                    to='authentication.company')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='handover_packs_crees',
                    to=settings.AUTH_USER_MODEL)),
                ('installation', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='handover_pack',
                    to='installations.installation')),
            ],
            options={
                'verbose_name': 'Pack de remise client',
                'verbose_name_plural': 'Packs de remise client',
                'ordering': ['-date_creation'],
            },
        ),
    ]
