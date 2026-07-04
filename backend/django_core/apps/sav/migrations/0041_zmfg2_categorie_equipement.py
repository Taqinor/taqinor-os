# ZMFG2 — Catégories d'équipement (Configuration > Equipment Categories) +
# regroupement/filtre du parc. `CategorieEquipement` (responsable, commentaire)
# + `Equipement.categorie` optionnel (SET_NULL).
import django.conf
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        migrations.swappable_dependency(django.conf.settings.AUTH_USER_MODEL),
        ('sav', '0040_zmfg1_equipe_maintenance'),
    ]

    operations = [
        migrations.CreateModel(
            name='CategorieEquipement',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('nom', models.CharField(max_length=120)),
                ('commentaire', models.TextField(blank=True, default='')),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='categories_equipement',
                    to='authentication.company')),
                ('responsable', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='categories_equipement_dirigees',
                    to=django.conf.settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': "Catégorie d'équipement",
                'verbose_name_plural': "Catégories d'équipement",
                'ordering': ['nom'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='categorieequipement',
            unique_together={('company', 'nom')},
        ),
        migrations.AddField(
            model_name='equipement',
            name='categorie',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='equipements', to='sav.categorieequipement'),
        ),
    ]
