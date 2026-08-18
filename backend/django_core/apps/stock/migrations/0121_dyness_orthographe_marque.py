"""Correction de marque « Deyness » → « Dyness » sur les produits en base.

Migration de DONNÉES (aucun changement de schéma), décision fondateur du
2026-08-18. La vraie marque de batteries est **Dyness** (dyness.com) ; le
catalogue vendu du simulateur écrivait « Deyness » — le seeder lui-même le
disait déjà dans ses propres commentaires (« PVG4 — Batteries Dyness ») et
dans le modèle constructeur seedé (« Dyness DL5.0C »).

POURQUOI UNE MIGRATION ET PAS LE SEEDER : ``seed_catalogue`` est **strictement
additif** — il crée les produits manquants et ne renomme JAMAIS une ligne
existante. Corriger l'orthographe dans sa table ``CATALOGUE`` ne suffit donc
pas pour une base déjà seedée (production) : le produit y garde son ancien nom
pour toujours. C'est cette migration qui fait le renommage en base.

PÉRIMÈTRE — DEUX CHAMPS, RIEN D'AUTRE :
  * ``Produit.nom``    (« Batterie Deyness 5 kWh » → « Batterie Dyness 5 kWh »)
  * ``Produit.marque`` (« Deyness » → « Dyness »)
Aucun prix, aucune quantité, aucun SKU (les SKU ``BAT-DEY-*`` sont des codes,
pas la marque : les toucher casserait l'appariement du seeder, des fiches
techniques et du simulateur de batterie du site).

CE QUI N'EST **PAS** TOUCHÉ — LES DOCUMENTS HISTORIQUES : les désignations
figées des lignes de devis (``ventes.DevisLigne.designation``) et les PDF déjà
générés gardent leur texte d'origine. Un devis signé en 2026-06 doit rester le
document qui a été envoyé au client ; c'est la resynchronisation habituelle du
devis qui fera suivre les rendus futurs. Tout le code qui CLASSIFIE ou APPARIE
par chaîne (mots-clés batterie, jeton de marque, appariement de fiche) accepte
les DEUX orthographes, pour que ces vieilles désignations restent bien classées
après ce renommage.

RÉVERSIBILITÉ : ``reverse`` réapplique l'ancienne orthographe sur les mêmes
deux champs. Nuance assumée : après un ``migrate`` arrière, un produit seedé
« Dyness » dès l'origine repartira lui aussi en « Deyness » — la marche arrière
restaure l'état du catalogue de l'époque, pas l'historique par ligne.
"""
from django.db import migrations
from django.db.models import Q

# Les trois casses rencontrées dans le catalogue et les saisies libres.
# Ordre indifférent : les motifs ne se chevauchent pas.
_VERS_DYNESS = (
    ('Deyness', 'Dyness'),
    ('deyness', 'dyness'),
    ('DEYNESS', 'DYNESS'),
)


def _renommer(apps, ancien_vers_nouveau):
    """Applique les remplacements sur ``nom``/``marque`` de chaque Produit visé.

    Écrit UNIQUEMENT les lignes réellement modifiées (idempotent : rejouer la
    migration ne produit aucune écriture) et seulement les champs concernés.
    """
    Produit = apps.get_model('stock', 'Produit')
    recherche = ancien_vers_nouveau[0][0]  # 'Deyness' ou 'Dyness'
    # Volume attendu : quelques lignes par société (les modules batterie du
    # catalogue) — pas de curseur serveur, on écrit dans la même boucle.
    lignes = Produit.objects.filter(
        Q(nom__icontains=recherche) | Q(marque__icontains=recherche))
    for produit in lignes:
        champs = []
        for champ in ('nom', 'marque'):
            valeur = getattr(produit, champ) or ''
            nouvelle = valeur
            for ancien, nouveau in ancien_vers_nouveau:
                nouvelle = nouvelle.replace(ancien, nouveau)
            if nouvelle != valeur:
                setattr(produit, champ, nouvelle)
                champs.append(champ)
        if champs:
            produit.save(update_fields=champs)


def corriger_orthographe(apps, schema_editor):
    _renommer(apps, _VERS_DYNESS)


def retablir_orthographe(apps, schema_editor):
    _renommer(apps, tuple((n, a) for a, n in _VERS_DYNESS))


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0120_ntp2p22_favoris_catalogue_achat'),
    ]

    operations = [
        migrations.RunPython(corriger_orthographe, retablir_orthographe),
    ]
