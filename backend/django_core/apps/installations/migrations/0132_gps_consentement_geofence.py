# Revue chantier 26/10/2026 — suivi GPS des techniciens (loi 09-08 / CNDP 17-2014).
#   * GpsConsentRecord : notice_version, recepisse_cndp, accusé de réception du
#     technicien (accepte_le + accepte_depuis_ip) — additif, nullable/défauts.
#   * GeofenceAlert.position : CASCADE → SET_NULL (null=True) pour que la purge
#     des positions (rétention 30 j) garde l'historique de présence.
#   * Installation.geofence_rayon_m : rayon de géofence propre au chantier.
# Additif et revertable (le retour arrière de l'AlterField exige qu'aucune
# alerte n'ait perdu sa position — la purge n'en a pas encore tourné).

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0131_acht100_demontage_ligne_origine'),
    ]

    operations = [
        migrations.AddField(
            model_name='gpsconsentrecord',
            name='notice_version',
            field=models.CharField(
                default='v1', max_length=20,
                help_text="Version de la notice d'information géolocalisation montrée."),
        ),
        migrations.AddField(
            model_name='gpsconsentrecord',
            name='recepisse_cndp',
            field=models.CharField(
                blank=True, default='', max_length=60,
                help_text='N° de récépissé de la déclaration CNDP (vide = non encore déclaré).'),
        ),
        migrations.AddField(
            model_name='gpsconsentrecord',
            name='accepte_le',
            field=models.DateTimeField(
                blank=True, null=True,
                help_text="Accusé de réception de la notice par le technicien (dans l'application)."),
        ),
        migrations.AddField(
            model_name='gpsconsentrecord',
            name='accepte_depuis_ip',
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='geofencealert',
            name='position',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='geofence_alerts',
                to='installations.positiontechnicien'),
        ),
        migrations.AddField(
            model_name='installation',
            name='geofence_rayon_m',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                help_text='Rayon de géofence du chantier en mètres (vide = 500 m par défaut).',
                validators=[
                    django.core.validators.MinValueValidator(10),
                    django.core.validators.MaxValueValidator(50000)]),
        ),
    ]
