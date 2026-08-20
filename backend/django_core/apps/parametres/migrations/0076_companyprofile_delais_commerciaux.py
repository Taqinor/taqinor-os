# Q5 (fondateur, 20/08/2026) — délais commerciaux « visite technique » et
# « installation » : deux réglages société (texte libre court), même modèle que
# les réglages agricoles voisins. Additif, défauts = les littéraux qui étaient
# codés en dur dans les renderers, donc comportement inchangé tant que la
# société ne les édite pas. Un réglage VIDÉ fait disparaître le délai du
# document (jamais un forfait déguisé en donnée société).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0075_companyprofile_agricole_prix_bonbonne_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='delai_visite_technique',
            field=models.CharField(blank=True, default='48-72 h',
                                   max_length=40),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='delai_installation',
            field=models.CharField(blank=True, default='7-14 jours ouvrés',
                                   max_length=40),
        ),
    ]
