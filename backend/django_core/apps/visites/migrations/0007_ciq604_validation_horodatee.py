import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('visites', '0006_ciq600_gabarit_ci'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='visiteterrain',
            name='validee_le',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Validée le'),
        ),
        migrations.AddField(
            model_name='visiteterrain',
            name='validee_par',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='visites_validees', to=settings.AUTH_USER_MODEL, verbose_name='Validée par'),
        ),
    ]
