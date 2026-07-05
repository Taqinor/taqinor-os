from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qhse', '0050_xqhs21_releve_consommation'),
    ]

    operations = [
        migrations.AddField(
            model_name='nonconformite',
            name='cout_estime',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Coût estimé (interne)'),
        ),
        migrations.AddField(
            model_name='nonconformite',
            name='cout_reel',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Coût réel (interne)'),
        ),
        migrations.AddField(
            model_name='actioncorrectivepreventive',
            name='cout',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Coût (interne)'),
        ),
        migrations.AddField(
            model_name='incident',
            name='cout',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Coût (interne)'),
        ),
    ]
