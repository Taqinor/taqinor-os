"""APAR23 — marqueur d'émission des balayages (additif, revertable :
``python manage.py migrate notifications 0067``)."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0010_customuser_supervisor'),
        ('notifications', '0067_apar22_whatsapp_inbound_message'),
    ]

    operations = [
        migrations.CreateModel(
            name='MarqueurEmissionBalayage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('event_type', models.CharField(max_length=64, verbose_name="Type d'événement")),
                ('cle', models.CharField(max_length=255, verbose_name='Objet')),
                ('periode', models.CharField(blank=True, default='', max_length=10, verbose_name='Période')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': "Marqueur d'émission de balayage",
                'verbose_name_plural': "Marqueurs d'émission de balayage",
                'constraints': [models.UniqueConstraint(fields=('company', 'event_type', 'cle', 'periode'), name='notif_marqueur_emission_uniq')],
            },
        ),
    ]
