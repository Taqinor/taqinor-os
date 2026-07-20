"""LB48 — SavedView model (vues enregistrées de compte, page crm.leads).

Additif : nouvelle table, aucune colonne existante modifiée. Vue PERSONNELLE
(company + user FK, toutes deux CASCADE) : filtres + disposition (payload)
mémorisés par utilisateur pour une page applicative donnée (ex. 'crm.leads').
Un utilisateur ne peut pas nommer deux vues identiques sur la même page
(UniqueConstraint (user, page, name)) ; ``rank`` ordonne ses vues pour une
page (0 = défaut).
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0066_appointment_statut_no_show'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SavedView',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('page', models.CharField(
                    max_length=64,
                    help_text="Clé applicative de la page (ex. 'crm.leads').",
                )),
                ('name', models.CharField(
                    max_length=80, verbose_name='Nom')),
                ('rank', models.PositiveIntegerField(
                    default=0, verbose_name='Rang',
                    help_text='0 = première/vue par défaut.',
                )),
                ('payload', models.JSONField(
                    default=dict, blank=True,
                    help_text='Contenu de la vue : {filters, view}.',
                )),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='crm_vues_enregistrees',
                    to='authentication.company',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='crm_vues_enregistrees',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Vue enregistrée',
                'verbose_name_plural': 'Vues enregistrées',
                'ordering': ['rank', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='savedview',
            constraint=models.UniqueConstraint(
                fields=['user', 'page', 'name'],
                name='crm_sv_uniq_user_page_name',
            ),
        ),
    ]
