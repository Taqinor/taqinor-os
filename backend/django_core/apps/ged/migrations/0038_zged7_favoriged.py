import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ged', '0037_zged6_routagedocumentaire'),
    ]

    operations = [
        migrations.CreateModel(
            name='FavoriGed',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='ged_favoris', to='authentication.company')),
                ('document', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='favoris', to='ged.document')),
                ('folder', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='favoris', to='ged.folder')),
                ('utilisateur', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ged_favoris', to=settings.AUTH_USER_MODEL, verbose_name='utilisateur')),
            ],
            options={
                'verbose_name': 'Favori GED',
                'verbose_name_plural': 'Favoris GED',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='favoriged',
            index=models.Index(fields=['company', 'utilisateur'], name='ged_favori_co_user_idx'),
        ),
        migrations.AddConstraint(
            model_name='favoriged',
            constraint=models.CheckConstraint(condition=(models.Q(('document__isnull', True), ('folder__isnull', False)) | models.Q(('document__isnull', False), ('folder__isnull', True))), name='ged_favori_exactly_one_target'),
        ),
        migrations.AddConstraint(
            model_name='favoriged',
            constraint=models.UniqueConstraint(condition=models.Q(('folder__isnull', False)), fields=('utilisateur', 'folder'), name='ged_favori_unique_user_folder'),
        ),
        migrations.AddConstraint(
            model_name='favoriged',
            constraint=models.UniqueConstraint(condition=models.Q(('document__isnull', False)), fields=('utilisateur', 'document'), name='ged_favori_unique_user_document'),
        ),
    ]
