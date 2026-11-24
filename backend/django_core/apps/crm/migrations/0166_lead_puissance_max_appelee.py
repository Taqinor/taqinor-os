"""Décision fondateur du 24/11/2026 (lead « Karim Hasnaoui ») — puissance
maximale appelée (kVA) et charge moyenne pendant les heures d'ouverture (%)
sur le lead pro (``models_lead_puissance.LeadPuissanceMaxMixin``) : colonnes
nullables SANS défaut (vide = question pas encore posée), lues par
l'estimation de consommation du moteur C&I. Additive, revertable.

Générée par ``makemigrations`` sur le poste (sans base) : miroir exact des
champs ; ``test_aucune_migration_en_attente`` le confirme en CI.
"""
import django.core.validators
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0165_parc_raison_liste_froide'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='charge_moyenne_pct',
            field=models.PositiveSmallIntegerField(blank=True, help_text="Question à l'appel : « Pendant vos heures d'ouverture, le site tourne en moyenne à quel pourcentage de cette puissance maximale ? » (1 à 100 ; vide = 50 % supposés par le calcul, décision fondateur du 24/11/2026).", null=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(100)], verbose_name="Charge moyenne pendant les heures d'ouverture (%)"),
        ),
        migrations.AddField(
            model_name='lead',
            name='puissance_max_appelee_kva',
            field=models.DecimalField(blank=True, decimal_places=2, help_text="Question à l'appel : « Quelle est la puissance maximale que votre site appelle, en kVA ? » (vide = pas encore posée). DISTINCTE de la puissance souscrite du compteur : elle ne sert qu'à ESTIMER la consommation quand aucune n'est connue (estimation dite, sous réserve de visite).", max_digits=7, null=True, validators=[django.core.validators.MinValueValidator(Decimal('0.01'))], verbose_name='Puissance maximale appelée (kVA)'),
        ),
    ]
