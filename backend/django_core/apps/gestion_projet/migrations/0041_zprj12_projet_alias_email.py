from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_projet', '0040_zprj11_tache_ticket_sav_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='projet',
            name='alias_email',
            field=models.CharField(
                blank=True, default='', max_length=254, null=True,
                verbose_name='Alias e-mail (création de tâches)'),
        ),
        migrations.AddConstraint(
            model_name='projet',
            constraint=models.UniqueConstraint(
                condition=~models.Q(('alias_email__in', ['', None])),
                fields=('company', 'alias_email'),
                name='gp_projet_alias_email_uniq'),
        ),
    ]
