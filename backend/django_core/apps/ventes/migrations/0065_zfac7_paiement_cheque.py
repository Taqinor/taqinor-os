from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0064_ysubs9_periode_service'),
    ]

    operations = [
        migrations.AddField(
            model_name='paiement',
            name='numero_cheque',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
        migrations.AddField(
            model_name='paiement',
            name='banque_tiree',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
    ]
