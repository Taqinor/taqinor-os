"""NTMIG31 — parcours de certification partenaire (formation + badge).

Migration PUREMENT ADDITIVE : un ``CreateModel`` sur une table neuve, aucun
``RunPython``, aucune colonne existante touchée. Le reverse est le DROP TABLE
standard de Django.

Les FK vers ``crm.Partenaire`` et ``kb.KbParcours`` sont des références par
CHAÎNE (jamais un import direct de leurs modèles depuis ``apps.migration``) ;
les index portent un nom EXPLICITE identique à celui déclaré dans
``Meta.indexes``.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0028_company_tours_actifs'),
        ('crm', '0084_relanceetape'),
        ('kb', '0024_ntmig21_playbook'),
        ('migration', '0005_ntmig28_deploiementpartenaire'),
    ]

    operations = [
        migrations.CreateModel(
            name='ParcoursCertificationPartenaire',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('parcours_nom', models.CharField(blank=True, default='', help_text="Nom figé à l'instanciation (reste lisible si le parcours modèle est supprimé ou renommé).", max_length=200, verbose_name='Nom du parcours')),
                ('specialite', models.CharField(blank=True, default='', max_length=32, verbose_name='Spécialité proposée')),
                ('articles', models.JSONField(blank=True, default=list, verbose_name='Articles (instantané)')),
                ('avancement', models.JSONField(blank=True, default=dict, verbose_name='Avancement')),
                ('statut', models.CharField(choices=[('en_cours', 'En cours'), ('termine', 'Terminé')], default='en_cours', max_length=10, verbose_name='Statut')),
                ('proposition_validee', models.BooleanField(default=False, verbose_name='Proposition de spécialité validée')),
                ('date_validation', models.DateTimeField(blank=True, null=True, verbose_name='Validé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('partenaire', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='parcours_certification', to='crm.partenaire', verbose_name='Partenaire')),
                ('parcours', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='kb.kbparcours', verbose_name='Parcours (kb)')),
                ('valide_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='parcours_certification_valides', to='authentication.customuser', verbose_name='Validé par')),
            ],
            options={
                'verbose_name': 'Parcours de certification partenaire',
                'verbose_name_plural': 'Parcours de certification partenaire',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='parcourscertificationpartenaire',
            index=models.Index(fields=['company', 'partenaire'], name='mig_parc_cert_soc_part_idx'),
        ),
        migrations.AddIndex(
            model_name='parcourscertificationpartenaire',
            index=models.Index(fields=['company', 'statut'], name='mig_parc_cert_soc_statut_idx'),
        ),
    ]
