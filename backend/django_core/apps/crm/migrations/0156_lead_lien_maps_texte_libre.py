"""``Lead.lien_maps`` : texte libre de 2000 signes (était ``URLField`` de 500).

Le champ « Lien Google Maps (envoyé par le client) » refusait tout ce qui ne
commençait pas par http(s):// — coordonnées, plus code, adresse — et les liens
de plus de 500 signes. Le résolveur ``resoudre-gps`` comprend désormais ces
formes. Élargissement pur (aucune donnée modifiée) ; retour arrière sans danger
tant qu'aucune valeur de plus de 500 signes n'a été saisie.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0155_waud83_lead_langue_en'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lead',
            name='lien_maps',
            field=models.CharField(
                blank=True, default='', max_length=2000,
                verbose_name='Lien Google Maps'),
        ),
    ]
