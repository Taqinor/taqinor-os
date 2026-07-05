# ZSAV3 — Activités planifiées à échéance sur le ticket (rappeler / rappel
# visite). `TicketActiviteAFaire` — distincte du chatter `TicketActivity`.
import django.conf
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(django.conf.settings.AUTH_USER_MODEL),
        ('sav', '0043_zmfg12_equipement_rebut'),
    ]

    operations = [
        migrations.CreateModel(
            name='TicketActiviteAFaire',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('type', models.CharField(
                    choices=[
                        ('appel', 'Appel'), ('email', 'Email'),
                        ('visite', 'Visite'), ('rappel', 'Rappel'),
                    ], max_length=10)),
                ('titre', models.CharField(max_length=200)),
                ('echeance', models.DateField()),
                ('fait', models.BooleanField(default=False)),
                ('fait_le', models.DateTimeField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ticket_activites_a_faire',
                    to='authentication.company')),
                ('ticket', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='activites_a_faire', to='sav.ticket')),
                ('assigne', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='ticket_activites_a_faire',
                    to=django.conf.settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='ticket_activites_a_faire_creees',
                    to=django.conf.settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Activité à faire (ticket)',
                'verbose_name_plural': 'Activités à faire (ticket)',
                'ordering': ['echeance', '-date_creation'],
            },
        ),
        migrations.AddIndex(
            model_name='ticketactiviteafaire',
            index=models.Index(
                fields=['company', 'echeance'],
                name='sav_taf_company_echeance_idx'),
        ),
        migrations.AddIndex(
            model_name='ticketactiviteafaire',
            index=models.Index(
                fields=['ticket', 'fait'],
                name='sav_taf_ticket_fait_idx'),
        ),
    ]
