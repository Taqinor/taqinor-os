# NTHCM16 — feedback continu (reconnaissance / axe d'amélioration / coaching).
#
# Purement ADDITIF : une table neuve, aucun champ existant touché.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0008_customuser_avatar_key_customuser_poste'),
        ('rh', '0095_ntfsm26_zone_intervention'),
    ]

    operations = [
        migrations.CreateModel(
            name='FeedbackContinu',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('type', models.CharField(
                    choices=[('reconnaissance', 'Reconnaissance'),
                             ('axe_amelioration', "Axe d'amélioration"),
                             ('coaching', 'Coaching')],
                    default='reconnaissance', max_length=20,
                    verbose_name='Type')),
                ('message', models.TextField(verbose_name='Message')),
                ('visible_par_pour', models.BooleanField(
                    default=True,
                    verbose_name='Visible par le destinataire')),
                ('partage_avec_manager', models.BooleanField(
                    default=False,
                    verbose_name='Partagé avec le manager')),
                # SCA4 — socle core.models.TenantModel.
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('de', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='feedbacks_envoyes',
                    to='rh.dossieremploye', verbose_name='Auteur')),
                ('pour', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='feedbacks_recus',
                    to='rh.dossieremploye', verbose_name='Destinataire')),
            ],
            options={
                'verbose_name': 'Feedback continu',
                'verbose_name_plural': 'Feedbacks continus',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='feedbackcontinu',
            index=models.Index(
                fields=['company', 'pour'],
                name='rh_feedcont_comp_pour_idx'),
        ),
        migrations.AddIndex(
            model_name='feedbackcontinu',
            index=models.Index(
                fields=['company', 'de'],
                name='rh_feedcont_comp_de_idx'),
        ),
    ]
