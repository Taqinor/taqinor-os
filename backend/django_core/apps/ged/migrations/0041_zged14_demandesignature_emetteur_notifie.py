from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ged', '0040_zged9_document_verrou_avertissement'),
    ]

    operations = [
        migrations.AddField(
            model_name='demandesignaturedocument',
            name='emetteur_notifie_expiration_le',
            field=models.DateTimeField(blank=True, null=True, verbose_name="émetteur notifié de l'expiration proche le"),
        ),
    ]
