# NTHCM14 — enquêtes d'engagement multi-questions (au-delà de l'eNPS XRH32).
#
# Purement ADDITIF. L'anonymat est STRUCTUREL, pas déclaratif :
#   * `ReponseEnquete` ne porte AUCUNE FK `user` ;
#   * une CheckConstraint interdit qu'une réponse `anonyme=True` porte un
#     `employe` — la garantie tient même pour une écriture directe en base ;
#   * le double-envoi est bloqué à part par `ParticipationEnquete`, jamais
#     jointe aux réponses.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0008_customuser_avatar_key_customuser_poste'),
        ('rh', '0092_nthcm13_seuil_risque_succession'),
    ]

    operations = [
        migrations.CreateModel(
            name='EnqueteEngagement',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('titre', models.CharField(
                    max_length=200, verbose_name='Titre')),
                ('questions', models.JSONField(
                    blank=True, default=list, verbose_name='Questions')),
                ('date_debut', models.DateField(
                    blank=True, null=True, verbose_name='Date de début')),
                ('date_fin', models.DateField(
                    blank=True, null=True, verbose_name='Date de fin')),
                ('anonyme', models.BooleanField(
                    default=True, verbose_name='Anonyme')),
                # SCA4 — socle core.models.TenantModel.
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': "Enquête d'engagement",
                'verbose_name_plural': "Enquêtes d'engagement",
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ReponseEnquete',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('anonyme', models.BooleanField(
                    default=True, verbose_name='Anonyme')),
                ('reponses', models.JSONField(
                    blank=True, default=dict, verbose_name='Réponses')),
                # SCA4 — socle core.models.TenantModel.
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('employe', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reponses_enquete',
                    to='rh.dossieremploye',
                    verbose_name='Employé (enquête nominative)')),
                ('enquete', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reponses', to='rh.enqueteengagement',
                    verbose_name='Enquête')),
            ],
            options={
                'verbose_name': "Réponse d'enquête",
                'verbose_name_plural': "Réponses d'enquête",
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ParticipationEnquete',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('token_hash', models.CharField(
                    max_length=64, verbose_name='Jeton (empreinte)')),
                # SCA4 — socle core.models.TenantModel.
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('enquete', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='participations',
                    to='rh.enqueteengagement', verbose_name='Enquête')),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='participations_enquete',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Utilisateur')),
            ],
            options={
                'verbose_name': 'Participation enquête',
                'verbose_name_plural': 'Participations enquête',
            },
        ),
        migrations.AddIndex(
            model_name='reponseenquete',
            index=models.Index(
                fields=['company', 'enquete'],
                name='rh_repenq_comp_enq_idx'),
        ),
        migrations.AddConstraint(
            model_name='reponseenquete',
            constraint=models.CheckConstraint(
                condition=models.Q(('anonyme', False)) | models.Q(
                    ('employe__isnull', True)),
                name='rh_repenq_anonyme_sans_employe'),
        ),
        migrations.AddConstraint(
            model_name='participationenquete',
            constraint=models.UniqueConstraint(
                fields=('enquete', 'user'),
                name='rh_partenq_enquete_user_uniq'),
        ),
    ]
