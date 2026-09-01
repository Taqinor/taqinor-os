"""QJR52 (audit L3 du 29/08/2026, décision fondateur D2) — les ``prix_par_kwc``
historiques GELÉS SUR LE BRUT sont corrigés sur le NET.

CE QUI ÉTAIT FAUX. ``Devis.save`` gèle ``prix_par_kwc`` (Total TTC ÷ kWc) UNE
SEULE FOIS, write-once, et le lisait sur un total TTC qui IGNORAIT
``remise_globale`` : tout devis remisé est donc enregistré à jamais à un prix
par kWc gonflé, sans aucun chemin de correction (le champ n'est jamais
recalculé). QJR51 a fait passer ``Devis.total_ttc`` au NET, ce qui corrige les
devis À VENIR ; cette migration corrige ceux qui existent DÉJÀ.

PÉRIMÈTRE STRICT — les devis dont ``remise_globale > 0`` ET dont
``prix_par_kwc`` est déjà gelé. Un devis sans remise globale a un prix par kWc
identique dans les deux vues : il n'est pas touché. Un devis dont le champ est
NULL se gèlera correctement à sa prochaine sauvegarde utile.

CE N'EST PAS L'INVENTION D'UN NOMBRE — c'est la correction d'un nombre stocké
faux : la valeur est RE-DÉRIVÉE des lignes du devis et de sa remise, par la
MÊME chaîne canonique que ``selectors._canonical_totaux`` (HT brut → remise
globale → TVA par taux → TTC, au centime), recopiée ici pour que la migration
reste SELF-CONTAINED et rejouable telle quelle dans dix ans.

CE QUE CETTE MIGRATION NE FAIT PAS. Elle n'applique AUCUN filtre d'option : le
défaut nommé par D2 est la REMISE, et les prédicats de classification
« deux options » vivent dans le moteur PDF, code de PRODUCTION qu'une migration
ne doit pas importer (une règle de classification qui évolue changerait
rétroactivement le résultat d'une migration déjà appliquée).

RÉVERSIBLE POUR DE VRAI : les deux sens sont des dérivations pures des MÊMES
données immuables (lignes + remise). ``reverse_code`` re-dérive la valeur
BRUTE — l'état exact d'avant.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db import migrations

_CENT = Decimal('0.01')


def _q(valeur):
    return valeur.quantize(_CENT, rounding=ROUND_HALF_UP)


def _compte_dans_totaux(ligne):
    """XSAL5/XSAL14 — seule une ligne PRODUIT non optionnelle compte."""
    return (getattr(ligne, 'type_ligne', 'produit') == 'produit'
            and not getattr(ligne, 'optionnelle', False))


def _ligne_ht(ligne):
    """``quantite × P.U. × (1 − remise de ligne)`` — miroir de
    ``LigneDevis.total_ht``, None-safe."""
    if ligne.quantite is None or ligne.prix_unitaire is None:
        return Decimal('0')
    remise = Decimal(str(ligne.remise or 0))
    return (Decimal(str(ligne.quantite)) * Decimal(str(ligne.prix_unitaire))
            * (Decimal('1') - remise / Decimal('100')))


def _ttc(devis, lignes, *, remise_pct):
    """La chaîne canonique, recopiée de ``selectors._canonical_totaux``.

    ``remise_pct`` à zéro rend le TTC BRUT (l'état d'avant QJR51) ; à la remise
    du devis, le TTC NET.
    """
    comptees = [li for li in lignes if _compte_dans_totaux(li)]
    disc = Decimal(str(remise_pct or 0))
    ht_brut = sum((_ligne_ht(li) for li in comptees), Decimal('0'))
    remise = _q(ht_brut * disc / Decimal('100')) if disc > 0 else Decimal('0')
    ht_net = _q(ht_brut - remise)

    paniers = {}
    for ligne in comptees:
        taux = ligne.taux_tva if ligne.taux_tva is not None else devis.taux_tva
        taux = Decimal(str(taux or 0))
        paniers[taux] = paniers.get(taux, Decimal('0')) + _ligne_ht(ligne)

    if len(paniers) <= 1:
        taux = next(iter(paniers), Decimal(str(devis.taux_tva or 0)))
        tva = _q(ht_net * taux / Decimal('100'))
    else:
        taux_tries = sorted(paniers)
        nets = {t: _q(paniers[t] * (Decimal('1') - disc / Decimal('100')))
                for t in taux_tries}
        residu = _q(ht_net - sum(nets.values(), Decimal('0')))
        nets[taux_tries[-1]] = _q(nets[taux_tries[-1]] + residu)
        tva = _q(sum((_q(nets[t] * t / Decimal('100')) for t in taux_tries),
                     Decimal('0')))
    return _q(ht_net + tva)


def _kwc(devis):
    """Le kWc figé dans ``etude_params``, ou ``None`` — jamais deviné."""
    brut = (devis.etude_params or {}).get('puissance_kwc')
    if not brut:
        return None
    try:
        valeur = Decimal(str(brut))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return valeur if valeur > 0 else None


#: Taille de lot du parcours. Le périmètre est déjà étroit (devis REMISÉS et
#: DÉJÀ gelés), mais on parcourt par ``iterator(chunk_size=…)`` et on écrit
#: DEVIS PAR DEVIS : jamais un ``UPDATE`` global qui verrouillerait la table.
_LOT = 200


def _recalculer(apps, *, honorer_la_remise):
    Devis = apps.get_model('ventes', 'Devis')
    concernes = (Devis.objects
                 .filter(remise_globale__gt=0)
                 .exclude(prix_par_kwc=None)
                 .prefetch_related('lignes')
                 .iterator(chunk_size=_LOT))
    for devis in concernes:
        kwc = _kwc(devis)
        if kwc is None:
            continue
        lignes = list(devis.lignes.all())
        remise = devis.remise_globale if honorer_la_remise else 0
        ttc = _ttc(devis, lignes, remise_pct=remise)
        if ttc <= 0:
            continue
        Devis.objects.filter(pk=devis.pk).update(prix_par_kwc=_q(ttc / kwc))


def corriger_sur_le_net(apps, schema_editor):
    _recalculer(apps, honorer_la_remise=True)


def revenir_au_brut(apps, schema_editor):
    _recalculer(apps, honorer_la_remise=False)


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0105_analyt1_friction_alert'),
    ]

    operations = [
        migrations.RunPython(corriger_sur_le_net, revenir_au_brut),
    ]
