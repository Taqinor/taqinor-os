import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qhse', '0051_xqhs22_cout_non_qualite'),
        ('sav', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='nonconformite',
            name='ticket_sav',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='qhse_ncr', to='sav.ticket', verbose_name="Ticket SAV d'origine"),
        ),
    ]
