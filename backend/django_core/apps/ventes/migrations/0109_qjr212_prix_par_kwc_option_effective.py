"""QJR212 — la réparation d'historique ``prix_par_kwc`` couvre AUSSI les devis
à deux options SANS remise globale.

CE QUI RESTAIT FAUX. ``0106_qjr52_prix_par_kwc_net`` ne réparait que les devis
``remise_globale > 0``, parce que le défaut nommé par D2 était la remise. Or
``Devis.save`` gèle désormais ce champ depuis la vue NET, qui applique AUSSI le
FILTRE D'OPTION EFFECTIVE (décision D9) : un devis à deux options SANS remise
garde donc une valeur figée sur la SOMME DES DEUX PANIERS — un montant qui
n'existe dans aucun document. Ancien et nouveau devis ne sont plus comparables
sur la même métrique interne.

PÉRIMÈTRE STRICT — devis SANS remise globale (les remisés sont déjà passés par
0106), ``prix_par_kwc`` DÉJÀ gelé, et RÉELLEMENT à deux options. Un devis
mono-option, un pompage, une liste libre : jamais touchés.

AUCUNE VALEUR INVENTÉE. Chaque valeur est RE-DÉRIVÉE des lignes du devis par la
même chaîne canonique que 0106 (HT brut → TVA par taux → TTC, au centime),
restreinte au panier de l'option EFFECTIVE. Un devis dont le NET n'est pas
calculable (kWc absent ou nul, TTC nul, option indécidable) est LAISSÉ TEL QUEL
et COMPTÉ dans le journal de migration.

SELF-CONTAINED, COMME 0106. Les prédicats de classification sont RECOPIÉS ici
plutôt qu'importés du moteur : une règle de production qui évolue changerait
rétroactivement le résultat d'une migration déjà appliquée. Les mots-clés
recopiés sont ceux d'``apps.ventes.solar_design`` au 31/08/2026 — batterie,
onduleur hybride, onduleur réseau/injection — plus la règle QF9/QJR200 (un
panier dont l'onduleur n'est pas Huawei perd son Smart Meter et sa clé Wi-Fi),
pour que la valeur réparée soit EXACTEMENT celle que ``Devis.save`` figerait
aujourd'hui.

RÉVERSIBLE POUR DE VRAI : les deux sens sont des dérivations pures des MÊMES
données immuables. ``reverse_code`` re-dérive la valeur sur la SOMME des deux
paniers — l'état exact d'avant.
"""
import logging

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db import migrations

logger = logging.getLogger(__name__)

_CENT = Decimal('0.01')

#: Les trois scénarios qui DÉCLARENT une alternative (``etude_params``).
_SCENARIOS_DEUX_OPTIONS = (
    'Sans batterie', 'Avec batterie', 'Les deux (Sans + Avec)',
)

SANS_BATTERIE = 'sans_batterie'
AVEC_BATTERIE = 'avec_batterie'


def _q(valeur):
    return valeur.quantize(_CENT, rounding=ROUND_HALF_UP)


# ── Prédicats de classification, RECOPIÉS (voir la docstring du module) ──────

def _est_batterie(texte):
    return 'batterie' in (texte or '').lower()


def _est_onduleur(texte):
    return 'onduleur' in (texte or '').lower()


def _est_onduleur_hybride(texte):
    t = (texte or '').lower()
    return 'onduleur' in t and 'hybride' in t


def _est_onduleur_reseau(texte):
    t = (texte or '').lower()
    return 'onduleur' in t and (
        'réseau' in t or 'reseau' in t or 'injection' in t)


def _est_accessoire_huawei(texte):
    t = (texte or '').lower()
    return 'smart meter' in t or 'wifi' in t or 'dongle' in t


def _blob(ligne):
    """Désignation + nom du produit lié — le texte de CLASSEMENT d'une ligne."""
    produit = getattr(ligne, 'produit', None)
    return (f"{getattr(ligne, 'designation', '') or ''} "
            f"{getattr(produit, 'nom', '') or ''}")


def _blob_marque(ligne):
    """Désignation + marque + nom du produit — le texte de MARQUE."""
    produit = getattr(ligne, 'produit', None)
    return (f"{getattr(ligne, 'designation', '') or ''} "
            f"{getattr(produit, 'marque', '') or ''} "
            f"{getattr(produit, 'nom', '') or ''}")


def _variante(ligne):
    valeur = str(getattr(ligne, 'variante', '') or '').strip().lower()
    return valeur if valeur in ('sans', 'avec') else ''


def _compte_dans_totaux(ligne):
    """XSAL5/XSAL14 — seule une ligne PRODUIT non optionnelle compte."""
    return (getattr(ligne, 'type_ligne', 'produit') == 'produit'
            and not getattr(ligne, 'optionnelle', False))


def _deux_options(devis, lignes):
    """Miroir PRUDENT d'``utils.options.deux_options_declarees``.

    Une ligne VARIANTÉE court-circuite tout (la composition a déjà distingué
    les deux options) ; sinon l'alternative doit être DÉCLARÉE et les lignes
    doivent porter les deux familles ET une batterie réelle.
    """
    if any(_variante(li) for li in lignes):
        return True
    scenario = (devis.etude_params or {}).get('scenario')
    if scenario not in _SCENARIOS_DEUX_OPTIONS:
        return False
    blobs = [_blob(li) for li in lignes if _compte_dans_totaux(li)]
    return (any(_est_onduleur_reseau(b) for b in blobs)
            and any(_est_onduleur_hybride(b) for b in blobs)
            and any(_est_batterie(b) for b in blobs))


def _option_effective(devis):
    """D9 — l'option acceptée, sinon celle du total affiché (AVEC)."""
    return (getattr(devis, 'option_acceptee', '') or '') or AVEC_BATTERIE


def _garder(ligne, option):
    v = _variante(ligne)
    if option == SANS_BATTERIE:
        if v == 'avec':
            return False
        if v == 'sans':
            return True
        blob = _blob(ligne)
        return not _est_batterie(blob) and not _est_onduleur_hybride(blob)
    if v == 'sans':
        return False
    if v == 'avec':
        return True
    return not _est_onduleur_reseau(_blob(ligne))


def _retirer_accessoires_huawei(lignes):
    """QF9/QJR200 — un panier dont l'onduleur n'est pas Huawei perd ses
    accessoires Huawei orphelins."""
    onduleurs = [li for li in lignes if _est_onduleur(_blob(li))]
    if onduleurs and all('huawei' in _blob_marque(li).lower()
                         for li in onduleurs):
        return lignes
    return [li for li in lignes if not _est_accessoire_huawei(_blob(li))]


def _panier(lignes, option):
    return _retirer_accessoires_huawei(
        [li for li in lignes if _garder(li, option)])


# ── Chaîne canonique, RECOPIÉE de 0106 (aucune remise ici par périmètre) ─────

def _ligne_ht(ligne):
    if ligne.quantite is None or ligne.prix_unitaire is None:
        return Decimal('0')
    remise = Decimal(str(ligne.remise or 0))
    return (Decimal(str(ligne.quantite)) * Decimal(str(ligne.prix_unitaire))
            * (Decimal('1') - remise / Decimal('100')))


def _ttc(devis, lignes):
    comptees = [li for li in lignes if _compte_dans_totaux(li)]
    ht_net = _q(sum((_ligne_ht(li) for li in comptees), Decimal('0')))
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
        nets = {t: _q(paniers[t]) for t in taux_tries}
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


#: Taille de lot du parcours — écriture DEVIS PAR DEVIS, jamais un UPDATE global.
_LOT = 200


def _recalculer(apps, *, filtrer_loption):
    Devis = apps.get_model('ventes', 'Devis')
    concernes = (Devis.objects
                 .filter(remise_globale=0)
                 .exclude(prix_par_kwc=None)
                 .prefetch_related('lignes__produit')
                 .iterator(chunk_size=_LOT))
    repares = 0
    laisses = 0
    for devis in concernes:
        lignes = list(devis.lignes.all())
        if not _deux_options(devis, lignes):
            continue  # hors périmètre : ni compté, ni touché
        kwc = _kwc(devis)
        if kwc is None:
            laisses += 1
            continue
        panier = (_panier(lignes, _option_effective(devis))
                  if filtrer_loption else lignes)
        ttc = _ttc(devis, panier)
        if ttc <= 0:
            laisses += 1
            continue
        Devis.objects.filter(pk=devis.pk).update(prix_par_kwc=_q(ttc / kwc))
        repares += 1
    logger.info(
        'QJR212 — prix_par_kwc : %s devis à deux options sans remise '
        'recalculés, %s laissés tels quels (NET non calculable).',
        repares, laisses)
    return repares, laisses


def corriger_sur_loption_effective(apps, schema_editor):
    _recalculer(apps, filtrer_loption=True)


def revenir_a_la_somme_des_deux(apps, schema_editor):
    _recalculer(apps, filtrer_loption=False)


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0108_qjr59_ligne_manuelle'),
    ]

    operations = [
        migrations.RunPython(corriger_sur_loption_effective,
                             revenir_a_la_somme_des_deux),
    ]
