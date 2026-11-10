from django.db import migrations, models


class Migration(migrations.Migration):
    """ASOC65 (D-ASOC-6) — statut « partielle » d'une demande de droit : un
    effacement dont une source a échoué reste ouvert et relançable. Choix
    seulement (aucune colonne modifiée), réversible."""

    dependencies = [
        ('core', '0078_idempotencyrecord_etat'),
    ]

    operations = [
        migrations.AlterField(
            model_name='datasubjectrequest',
            name='statut',
            field=models.CharField(
                choices=[('recue', 'Reçue'),
                         ('en_verification', "En vérification d'identité"),
                         ('partielle', 'Partiellement traitée'),
                         ('traitee', 'Traitée'),
                         ('refusee', 'Refusée')],
                default='recue', max_length=20, verbose_name='Statut'),
        ),
    ]
