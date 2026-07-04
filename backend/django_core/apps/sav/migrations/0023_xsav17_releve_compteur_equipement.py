import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0001_initial'),
        ('sav', '0022_xsav16_equipementdowntime'),
    ]

    operations = [
        migrations.AddField(
            model_name='equipement',
            name='entretien_toutes_les_heures',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=12, null=True,
                help_text=(
                    'Seuil de compteur (heures ou kWh) entre deux entretiens '
                    "préventifs. Vide = entretien déclenché par le temps "
                    "uniquement (comportement actuel).")),
        ),
        migrations.AddField(
            model_name='equipement',
            name='dernier_entretien_compteur_valeur',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.CreateModel(
            name='ReleveCompteurEquipement',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('type', models.CharField(
                    choices=[('heures', 'Heures'), ('kwh', 'kWh')],
                    max_length=10)),
                ('valeur', models.DecimalField(decimal_places=2, max_digits=12)),
                ('date', models.DateField()),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='releves_compteur_equipement',
                    to='authentication.company')),
                ('equipement', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='releves_compteur', to='sav.equipement')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Relevé compteur équipement',
                'verbose_name_plural': 'Relevés compteur équipement',
                'ordering': ['-date', '-date_creation'],
            },
        ),
        migrations.AddIndex(
            model_name='relevecompteurequipement',
            index=models.Index(
                fields=['company', 'equipement'],
                name='sav_releve_co_equip_idx'),
        ),
    ]
