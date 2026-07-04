import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('gestion_projet', '0036_zprj1_reglagetemps'),
    ]

    operations = [
        migrations.AddField(
            model_name='affectationressource',
            name='statut_publication',
            field=models.CharField(
                choices=[('brouillon', 'Brouillon'), ('publie', 'Publié')],
                default='brouillon', max_length=10,
                verbose_name='Statut de publication'),
        ),
        migrations.AddField(
            model_name='affectationressource',
            name='publie_le',
            field=models.DateTimeField(
                blank=True, null=True, verbose_name='Publié le'),
        ),
        migrations.AddField(
            model_name='affectationressource',
            name='publie_par',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+', to=settings.AUTH_USER_MODEL,
                verbose_name='Publié par'),
        ),
    ]
