# NTHCM15 — plans d'action issus d'une enquête d'engagement.
#
# Purement ADDITIF : une table. Les résultats par catégorie (NTHCM15) sont un
# calcul de lecture (`selectors.resultats_enquete`), sans stockage.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0008_customuser_avatar_key_customuser_poste'),
        ('rh', '0093_nthcm14_enquete_engagement'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlanActionEngagement',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('categorie_ciblee', models.CharField(
                    blank=True, default='', max_length=60,
                    verbose_name='Catégorie ciblée')),
                ('action', models.TextField(verbose_name='Action')),
                ('echeance', models.DateField(
                    blank=True, null=True, verbose_name='Échéance')),
                ('statut', models.CharField(
                    choices=[('propose', 'Proposé'), ('en_cours', 'En cours'),
                             ('termine', 'Terminé')],
                    default='propose', max_length=10,
                    verbose_name='Statut')),
                # SCA4 — socle core.models.TenantModel.
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('enquete', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='plans_action',
                    to='rh.enqueteengagement', verbose_name='Enquête')),
                ('responsable', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='plans_action_engagement',
                    to='rh.dossieremploye', verbose_name='Responsable')),
            ],
            options={
                'verbose_name': "Plan d'action engagement",
                'verbose_name_plural': "Plans d'action engagement",
                'ordering': ['echeance', 'created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='planactionengagement',
            index=models.Index(
                fields=['company', 'enquete'],
                name='rh_planacteng_comp_enq_idx'),
        ),
    ]
