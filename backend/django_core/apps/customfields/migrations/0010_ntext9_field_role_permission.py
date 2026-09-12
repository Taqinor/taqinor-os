"""NTEXT9 — permissions de champ par rôle (visible/éditable).

Purement ADDITIF et RÉVERSIBLE : une nouvelle table. Sans ligne pour un
(champ, palier), le comportement reste inchangé (visible et éditable) — voir
``services.niveau_pour_role``.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customfields', '0009_ntext1_formule'),
        ('authentication', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='FieldRolePermission',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('role_tier', models.CharField(
                    help_text='« normal », « responsable » ou « admin » '
                              '(authentication.role_tiers).',
                    max_length=40, verbose_name='Palier de rôle')),
                ('niveau', models.CharField(
                    choices=[('masque', 'Masqué'),
                             ('lecture', 'Lecture seule'),
                             ('edition', 'Édition')],
                    default='edition', max_length=10)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='field_role_permissions',
                    to='authentication.company')),
                ('field_def', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='role_permissions',
                    to='customfields.customfielddef')),
            ],
            options={
                'verbose_name': 'Permission de champ par rôle',
                'verbose_name_plural': 'Permissions de champ par rôle',
                'unique_together': {('field_def', 'role_tier')},
            },
        ),
        migrations.AddIndex(
            model_name='fieldrolepermission',
            index=models.Index(
                fields=['company', 'field_def', 'role_tier'],
                name='customfields_fieldrole_idx'),
        ),
    ]
