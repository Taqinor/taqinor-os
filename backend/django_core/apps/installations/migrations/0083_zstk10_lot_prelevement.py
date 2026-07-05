import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('installations', '0082_zstk9_storage_categories_putaway_rules'),
    ]

    operations = [
        migrations.CreateModel(
            name='LotPrelevement',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('reference', models.CharField(max_length=50)),
                ('statut', models.CharField(
                    choices=[
                        ('planifie', 'Planifié'), ('en_cours', 'En cours'),
                        ('termine', 'Terminé'),
                    ], default='planifie', max_length=20)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='lots_prelevement',
                    to='authentication.company')),
                ('pick_lists', models.ManyToManyField(
                    related_name='lots_prelevement',
                    to='installations.picklist')),
                ('operateur', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='lots_prelevement_assignes',
                    to=settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='lots_prelevement_crees',
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Lot de prélèvement',
                'verbose_name_plural': 'Lots de prélèvement',
                'ordering': ['-date_creation'],
                'unique_together': {('company', 'reference')},
            },
        ),
    ]
