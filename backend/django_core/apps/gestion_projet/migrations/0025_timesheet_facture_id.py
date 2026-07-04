# Generated for XPRJ3 -- T&M billing from approved timesheets (loose Facture ref).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_projet', '0024_timesheet_facturable_type_activite'),
    ]

    operations = [
        migrations.AddField(
            model_name='timesheet',
            name='facture_id',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name='ID de la facture de régie'),
        ),
    ]
