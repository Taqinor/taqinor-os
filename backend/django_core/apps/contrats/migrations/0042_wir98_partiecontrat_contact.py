# WIR98 — FK optionnelle PartieContrat -> contacts.ContactClient (additive).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0001_initial'),
        ('contrats', '0041_ntsub8_dunning'),
    ]

    operations = [
        migrations.AddField(
            model_name='partiecontrat',
            name='contact',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='parties_contrat',
                to='contacts.contactclient',
                verbose_name='Contact lié'),
        ),
    ]
