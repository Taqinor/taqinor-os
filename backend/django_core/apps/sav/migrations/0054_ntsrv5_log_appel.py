"""NTSRV5 - Trace structuree d'un appel SAV (additif).

* `Ticket.canal_ouverture` gagne la valeur `telephone` (choix seulement).
* `TicketActivity.kind` gagne la valeur `appel` (choix seulement).
* `TicketActivity.outcome` (vide par defaut) + `duree_minutes` (NULL) :
  aucune ligne existante ne change de comportement.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0053_ntsrv3_canal_whatsapp'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ticket',
            name='canal_ouverture',
            field=models.CharField(
                choices=[
                    ('manuel', 'Manuel (back-office)'),
                    ('email', 'E-mail'),
                    ('portail', 'Portail client'),
                    ('whatsapp', 'WhatsApp'),
                    ('telephone', 'Téléphone'),
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
                    ('whatsapp', 'WhatsApp'),
                    ('appel', 'Appel'),
                ],
                max_length=15,
            ),
        ),
        migrations.AddField(
            model_name='ticketactivity',
            name='outcome',
            field=models.CharField(
                blank=True,
                choices=[
                    ('', '—'),
                    ('joint', 'Joint'),
                    ('non_joint', 'Non joint'),
                    ('rappel', 'À rappeler'),
                    ('refuse', 'Refus'),
                    ('interesse', 'Intéressé'),
                ],
                default='',
                max_length=20,
                verbose_name="Résultat de l'interaction",
            ),
        ),
        migrations.AddField(
            model_name='ticketactivity',
            name='duree_minutes',
            field=models.PositiveIntegerField(
                blank=True, null=True, verbose_name='Durée (minutes)'),
        ),
    ]
