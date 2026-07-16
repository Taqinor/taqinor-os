# NTEXT13 — registre de packages d'extension (marketplace interne).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExtensionPackage',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('code', models.SlugField(max_length=60)),
                ('nom', models.CharField(max_length=150)),
                ('version', models.CharField(default='1.0.0', max_length=20)),
                ('description', models.TextField(blank=True, default='')),
                ('categorie', models.CharField(
                    blank=True, default='', max_length=60)),
                ('manifest', models.JSONField(blank=True, default=dict)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='extension_packages',
                    to='authentication.company')),
            ],
            options={
                'verbose_name': "Package d'extension",
                'verbose_name_plural': "Packages d'extension",
                'ordering': ['nom'],
                'unique_together': {('company', 'code')},
            },
        ),
    ]
