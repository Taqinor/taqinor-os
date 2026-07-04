import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0001_initial'),
        ('sav', '0017_xsav9_affectation_auto'),
    ]

    operations = [
        migrations.CreateModel(
            name='TicketSatisfaction',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('note', models.PositiveSmallIntegerField(
                    help_text=(
                        'Note de satisfaction 1 (très insatisfait) à '
                        '5 (très satisfait).'))),
                ('commentaire', models.TextField(blank=True, default='')),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ticket_satisfactions',
                    to='authentication.company')),
                ('ticket', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='satisfaction', to='sav.ticket')),
            ],
            options={
                'verbose_name': 'Satisfaction ticket SAV (CSAT)',
                'verbose_name_plural': 'Satisfactions ticket SAV (CSAT)',
                'ordering': ['-date_creation'],
            },
        ),
        migrations.AddIndex(
            model_name='ticketsatisfaction',
            index=models.Index(
                fields=['company', 'date_creation'],
                name='sav_ticketsat_co_date_idx'),
        ),
        migrations.AddConstraint(
            model_name='ticketsatisfaction',
            constraint=models.CheckConstraint(
                check=models.Q(('note__gte', 1), ('note__lte', 5)),
                name='sav_ticketsatisfaction_note_1_5'),
        ),
    ]
