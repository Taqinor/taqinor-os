"""L-FORFAIT (ordre fondateur 24/08/2026) — le tarif forfaitaire au panneau.

Deux champs ADDITIFS sur ``Produit`` (``prix_fixe_ht`` /
``prix_par_panneau_ht``, tous deux NULL par défaut : aucun produit existant ne
change de prix) + un remplissage de données pour les TROIS items du kit
résidentiel que le fondateur veut piloter depuis le stock.

Le remplissage est IDEMPOTENT et ADDITIF : il n'écrit que là où les DEUX
champs sont vides, donc il ne peut jamais écraser une valeur saisie par le
fondateur (même motif que ``seed_catalogue``). Revert : les colonnes sont
supprimées, la composition retombe sur ``prix_vente``.
"""
from decimal import Decimal
import unicodedata

from django.db import migrations, models


#: Barème fondateur, en DH HT : (part fixe, part par panneau).
#: · Installation — chiffres bruts du fondateur ; ancrages 8 panneaux →
#:   4 000 HT, 16 → 6 000 HT, l'entre-deux se lisse (10 → 4 500).
#: · Accessoires — ancienne règle : 1 000 TTC par bloc de 5 kWc, soit 833,33 HT
#:   à 8 panneaux et 1 666,67 HT à 16 ⇒ aucune part fixe, 1 000/1,20/8 =
#:   104,1666…/panneau, PUIS ÷ 2 (« reduce the price of accesoirs by half »).
#:   52,0833 (et non 52,08) garde la MOITIÉ EXACTE aux deux ancrages.
#: · Tableau De Protection AC/DC — même dérivation : 1 500 TTC/bloc ⇒ 1 250 HT
#:   à 8 panneaux et 2 500 HT à 16 ⇒ 1 500/1,20/8 = 156,25/panneau EXACT,
#:   PUIS + 30 % (« add 30% to tableau DC AC total price ») = 203,125.
BAREME = {
    'installation': (Decimal('2000'), Decimal('250')),
    'accessoires': (Decimal('0'), Decimal('52.0833')),
    'tableau': (Decimal('0'), Decimal('203.1250')),
}


def _sans_accents(texte):
    decompose = unicodedata.normalize('NFD', str(texte or '').lower())
    return ''.join(c for c in decompose
                   if unicodedata.category(c) != 'Mn')


def _role(nom):
    """Le rôle forfaitaire d'un nom de produit — sinon ``None``.

    Mêmes mots-clés et MÊME ORDRE que ``apps.ventes.services.classer_produit``
    (accessoire → tableau → installation), recopiés ici plutôt qu'importés :
    une migration ne doit dépendre d'aucune autre app.
    """
    n = _sans_accents(nom)
    if not n:
        return None
    # Les classes qui passent AVANT dans le classifieur : un produit qui les
    # porte n'est pas un forfait, même s'il contient « installation ».
    for mot in ('onduleur', 'panneau', 'batterie', 'structure', 'socle',
                'cable', 'smart meter', 'wifi', 'dongle'):
        if mot in n:
            return None
    if 'accessoire' in n:
        return 'accessoires'
    if 'tableau' in n:
        return 'tableau'
    if 'suivi' in n:
        return None
    if 'installation' in n:
        return 'installation'
    return None


def remplir_bareme(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')
    for produit in Produit.objects.filter(
            prix_fixe_ht__isnull=True, prix_par_panneau_ht__isnull=True
    ).iterator():
        role = _role(produit.nom)
        if not role:
            continue
        fixe, par_panneau = BAREME[role]
        produit.prix_fixe_ht = fixe
        produit.prix_par_panneau_ht = par_panneau
        produit.save(update_fields=['prix_fixe_ht', 'prix_par_panneau_ht'])


def vider_bareme(apps, schema_editor):
    """Revert : on repose les deux champs à NULL sur les seuls forfaits."""
    Produit = apps.get_model('stock', 'Produit')
    for produit in Produit.objects.exclude(
            prix_fixe_ht__isnull=True, prix_par_panneau_ht__isnull=True
    ).iterator():
        if _role(produit.nom):
            produit.prix_fixe_ht = None
            produit.prix_par_panneau_ht = None
            produit.save(
                update_fields=['prix_fixe_ht', 'prix_par_panneau_ht'])


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0128_l22a_bornes_mppt_5kw'),
    ]

    operations = [
        migrations.AddField(
            model_name='produit',
            name='prix_fixe_ht',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True,
                help_text="Tarif forfaitaire — part FIXE en DH HT, due quel "
                          "que soit le nombre de panneaux (ex. Installation : "
                          "2000). Laisser vide pour un produit vendu au prix "
                          "de vente catalogue."),
        ),
        migrations.AddField(
            model_name='produit',
            name='prix_par_panneau_ht',
            field=models.DecimalField(
                blank=True, decimal_places=4, max_digits=10, null=True,
                help_text="Tarif forfaitaire — part PAR PANNEAU en DH HT, "
                          "multipliée par le nombre de panneaux du devis (ex. "
                          "Installation : 250). Laisser vide pour un produit "
                          "vendu au prix de vente catalogue."),
        ),
        migrations.RunPython(remplir_bareme, vider_bareme),
    ]
