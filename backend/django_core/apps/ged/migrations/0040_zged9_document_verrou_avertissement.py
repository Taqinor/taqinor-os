import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ged', '0039_zged8_vuegedenregistree'),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='verrou_avertissement_par',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ged_documents_verrou_avertissement', to=settings.AUTH_USER_MODEL, verbose_name='verrou (avertissement) posé par'),
        ),
        migrations.AddField(
            model_name='document',
            name='verrou_avertissement_le',
            field=models.DateTimeField(blank=True, null=True, verbose_name='verrou (avertissement) posé le'),
        ),
        migrations.AddField(
            model_name='document',
            name='verrou_avertissement_motif',
            field=models.CharField(blank=True, default='', max_length=300, verbose_name='motif du verrou (avertissement)'),
        ),
    ]
