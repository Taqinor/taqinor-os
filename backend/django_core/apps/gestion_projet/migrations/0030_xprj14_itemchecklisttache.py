import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0012_customuser_must_change_password_and_more'),
        ('gestion_projet', '0029_xprj13_recurrencetache'),
    ]

    operations = [
        migrations.CreateModel(
            name='ItemChecklistTache',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('libelle', models.CharField(
                    max_length=200, verbose_name='Libellé')),
                ('fait', models.BooleanField(
                    default=False, verbose_name='Fait')),
                ('fait_le', models.DateTimeField(
                    blank=True, null=True, verbose_name='Fait le')),
                ('ordre', models.PositiveIntegerField(
                    default=0, verbose_name='Ordre')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='gp_items_checklist',
                    to='authentication.company', verbose_name='Société')),
                ('fait_par', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL,
                    verbose_name='Fait par')),
                ('tache', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='items_checklist',
                    to='gestion_projet.tache', verbose_name='Tâche')),
            ],
            options={
                'verbose_name': 'Item de checklist',
                'verbose_name_plural': 'Items de checklist',
                'ordering': ['tache', 'ordre', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='itemchecklisttache',
            index=models.Index(
                fields=['tache'], name='gp_item_checklist_tache_idx'),
        ),
    ]
