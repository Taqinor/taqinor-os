# NTEDU40 — ParametresEducation.date_limite_reinscription (relance
# réinscription, tâche planifiée).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('education', '0014_ntedu31_compteparent'),
    ]

    operations = [
        migrations.AddField(
            model_name='parametreseducation',
            name='date_limite_reinscription',
            field=models.DateField(
                blank=True, null=True,
                verbose_name='Date limite de réinscription'),
        ),
    ]
