# NTHCM3 — rattachement FONCTIONNEL (dotted-line), distinct du manager
# hiérarchique unique de NTHCM1.
#
# Purement ADDITIF : une table neuve, aucun champ existant touché.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0008_customuser_avatar_key_customuser_poste'),
        ('rh', '0102_nthcm27_genre_dossier'),
    ]

    operations = [
        migrations.CreateModel(
            name='RattachementFonctionnel',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('role_fonctionnel', models.CharField(
                    blank=True, default='', max_length=60,
                    verbose_name='Rôle fonctionnel')),
                ('date_debut', models.DateField(
                    blank=True, null=True, verbose_name='Début')),
                ('date_fin', models.DateField(
                    blank=True, null=True, verbose_name='Fin')),
                # SCA4 — socle core.models.TenantModel.
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('employe', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rattachements_fonctionnels',
                    to='rh.dossieremploye', verbose_name='Employé')),
                ('manager_fonctionnel', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rattaches_fonctionnels',
                    to='rh.dossieremploye',
                    verbose_name='Manager fonctionnel')),
            ],
            options={
                'verbose_name': 'Rattachement fonctionnel',
                'verbose_name_plural': 'Rattachements fonctionnels',
                'ordering': ['employe', 'role_fonctionnel'],
            },
        ),
        migrations.AddIndex(
            model_name='rattachementfonctionnel',
            index=models.Index(
                fields=['company', 'employe'],
                name='rh_rattfonc_comp_emp_idx'),
        ),
    ]
