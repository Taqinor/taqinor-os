from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0068_xfsm7_lien_client_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='installation',
            name='contact_site_nom',
            field=models.CharField(blank=True, max_length=120, null=True),
        ),
        migrations.AddField(
            model_name='installation',
            name='contact_site_telephone',
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
        migrations.AddField(
            model_name='installation',
            name='acces_instructions',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='installation',
            name='horaires_acces',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
    ]
