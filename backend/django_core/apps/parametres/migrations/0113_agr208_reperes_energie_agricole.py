# AGR208 (Groupe AGR, 02/10/2026) — les réglages « bonbonne » morts deviennent
# des REPÈRES énergie datés et sourcés.
#
# `agricole_prix_bonbonne` (50) et `agricole_cout_reel_bonbonne` (128) — Q4 du
# 20/08/2026 — n'étaient plus lus par aucun calcul depuis QJR236. On
# requalifie l'intention (décision Q4 : on ne la supprime pas) dans le JSON
# `reperes_energie_agricole` : chaque valeur est recopiée avec
# `releve_le = 2026-08-20` et une source VIDE (la valeur Q4 n'a pas de source
# publique relevée — un repère sans source n'est jamais affiché), puis les deux
# colonnes sont retirées.
#
# RÉVERSIBLE : le retour restaure les deux colonnes et y recopie les valeurs
# du JSON (repli sur les anciens défauts 50 / 128 si le repère est absent).
# Parcours ligne à ligne en `.iterator()` (une ligne de profil par société),
# jamais une mise à jour de masse (garde YOPSB4).
from decimal import Decimal, InvalidOperation

from django.db import migrations, models

RELEVE_Q4 = '2026-08-20'
ANCIENS_DEFAUTS = {
    'butane_12kg_detail': Decimal('50'),
    'butane_12kg_non_subventionne': Decimal('128'),
}
COLONNES = {
    'butane_12kg_detail': 'agricole_prix_bonbonne',
    'butane_12kg_non_subventionne': 'agricole_cout_reel_bonbonne',
}


def _nombre_json(valeur):
    """Decimal → nombre JSON (entier quand il est rond, sinon flottant)."""
    if valeur is None:
        return None
    d = Decimal(valeur)
    return int(d) if d == d.to_integral_value() else float(d)


def vers_reperes(apps, schema_editor):
    Profil = apps.get_model('parametres', 'CompanyProfile')
    for profil in Profil.objects.all().iterator():
        reperes = dict(profil.reperes_energie_agricole or {})
        for cle, colonne in COLONNES.items():
            reperes.setdefault(cle, {
                'valeur': _nombre_json(getattr(profil, colonne)),
                'source': '',
                'releve_le': RELEVE_Q4,
            })
        reperes.setdefault('gasoil_litre',
                           {'valeur': None, 'source': '', 'releve_le': None})
        profil.reperes_energie_agricole = reperes
        profil.save(update_fields=['reperes_energie_agricole'])


def vers_colonnes(apps, schema_editor):
    Profil = apps.get_model('parametres', 'CompanyProfile')
    for profil in Profil.objects.all().iterator():
        reperes = profil.reperes_energie_agricole or {}
        for cle, colonne in COLONNES.items():
            valeur = (reperes.get(cle) or {}).get('valeur')
            try:
                decimal = Decimal(str(valeur))
            except (InvalidOperation, TypeError, ValueError):
                decimal = None
            if decimal is None or not decimal.is_finite():
                decimal = ANCIENS_DEFAUTS[cle]
            setattr(profil, colonne, decimal)
        profil.save(update_fields=list(COLONNES.values()))


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0112_agr207_reglages_pompage'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='reperes_energie_agricole',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(vers_reperes, vers_colonnes),
        migrations.RemoveField(
            model_name='companyprofile',
            name='agricole_prix_bonbonne',
        ),
        migrations.RemoveField(
            model_name='companyprofile',
            name='agricole_cout_reel_bonbonne',
        ),
    ]
