"""NTSRV1 - Threading e-mail entrant/sortant sur les tickets SAV (additif).

* ``Ticket.canal_ouverture`` : defaut ``manuel`` -> tous les tickets existants
  gardent exactement leur semantique actuelle.
* ``TicketActivity.kind`` gagne la valeur ``email`` (choix seulement, aucune
  donnee touchee).
* ``TicketEmailThread`` : nouvelle table, memoire de threading RFC 5322.
"""
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('sav', '0051_aud529_ticket_reclamation'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='canal_ouverture',
            field=models.CharField(
                choices=[
                    ('manuel', 'Manuel (back-office)'),
                    ('email', 'E-mail'),
                    ('portail', 'Portail client'),
                ],
                default='manuel',
                help_text='Par quel canal la demande est arrivée (manuel, '
                          'e-mail, portail client…).',
                max_length=12,
                verbose_name="Canal d'ouverture",
            ),
        ),
        migrations.AlterField(
            model_name='ticketactivity',
            name='kind',
            field=models.CharField(
                choices=[
                    ('creation', 'Création'),
                    ('modification', 'Modification'),
                    ('note', 'Note'),
                    ('email', 'E-mail'),
                ],
                max_length=15,
            ),
        ),
        migrations.CreateModel(
            name='TicketEmailThread',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('message_id', models.CharField(
                    max_length=255, verbose_name='Message-ID')),
                ('in_reply_to', models.CharField(
                    blank=True, default='', max_length=255,
                    verbose_name='In-Reply-To')),
                ('thread_root', models.CharField(
                    blank=True, db_index=True, default='', max_length=255,
                    verbose_name='Racine du fil')),
                ('expediteur', models.CharField(
                    blank=True, default='', max_length=254,
                    verbose_name='Expéditeur')),
                ('destinataire', models.CharField(
                    blank=True, default='', max_length=254,
                    verbose_name='Destinataire')),
                ('sujet', models.CharField(
                    blank=True, default='', max_length=255)),
                ('corps_brut', models.TextField(blank=True, default='')),
                ('pieces_jointes', models.JSONField(blank=True, null=True)),
                ('direction', models.CharField(
                    choices=[('entrant', 'Entrant'), ('sortant', 'Sortant')],
                    default='entrant', max_length=8)),
                ('date_reception', models.DateTimeField(
                    default=django.utils.timezone.now)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ticket_email_threads',
                    to='authentication.company')),
                ('ticket', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='emails', to='sav.ticket')),
            ],
            options={
                'verbose_name': 'Message e-mail de ticket',
                'verbose_name_plural': 'Messages e-mail de ticket',
                'ordering': ['date_reception', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='ticketemailthread',
            index=models.Index(
                fields=['company', 'thread_root'],
                name='sav_email_thread_root_idx'),
        ),
        migrations.AddConstraint(
            model_name='ticketemailthread',
            constraint=models.UniqueConstraint(
                fields=('company', 'message_id'),
                name='sav_ticketemailthread_msgid_uniq'),
        ),
    ]
