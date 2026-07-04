from django.db import migrations, models


class Migration(migrations.Migration):
    """XPLT23 fix — widen DataSubjectRequest.kind to fit the 'rectification'
    choice value (13 chars); the field was max_length=12 (E009)."""

    dependencies = [
        ('core', '0018_registretraitement_xplt23'),
    ]

    operations = [
        migrations.AlterField(
            model_name='datasubjectrequest',
            name='kind',
            field=models.CharField(
                choices=[
                    ('acces', 'Accès (export)'),
                    ('effacement', 'Effacement'),
                    ('rectification', 'Rectification'),
                ],
                max_length=20,
                verbose_name='Type',
            ),
        ),
    ]
