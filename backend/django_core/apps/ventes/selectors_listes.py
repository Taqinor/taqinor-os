"""AOOM1 — sélecteurs LECTURE SEULE de PRÉCHARGEMENT, pour les LISTES d'autres
apps qui sérialisent des devis.

Même famille que ``selectors_cadence`` / ``selectors_facturation`` : une surface
de lecture cross-app exposée par ``ventes``, que ``crm`` appelle sans jamais
importer ``apps.ventes.models`` (frontière M3).

Pourquoi un module à part et non ``selectors.py`` : ce dernier est un FICHIER
MUR de 2 079 lignes, dont la garde C20 (``scripts/check_forme_code.py``)
interdit la croissance — budget 0 ligne nette.
"""
from __future__ import annotations

import functools
import logging

logger = logging.getLogger(__name__)


def prefetch_devis_liste_leads(prefixe='devis'):
    """AOOM1 — LE préchargement des devis d'une LISTE de leads, SANS leur
    ``etude_params``.

    Rend le tuple à passer tel quel à ``prefetch_related(*…)`` depuis
    ``apps.crm`` : les devis, leurs lignes AVEC produit (ERR-PERF-CRM-N1 : la
    garde de cache de ``lignes_avec_produit`` n'économise la requête que si
    chaque ligne porte DÉJÀ son produit) et le successeur d'une V1 remplacée
    (``devis_modifiabilite`` lit ``superseded_by.reference``).

    CE QUI CHANGE (incident du 02/11/2026, mesuré sur la copie anonymisée de
    la production) : les devis arrivent ``defer('etude_params')`` + les seuls
    chemins que la liste lit (``scenario``, ``nombre_proprietes``,
    ``resync_apres_envoi.date``) ANNOTÉS en SQL —
    :data:`~apps.ventes.utils.annotations_devis.ANNOTATION_PAR_CLE` en est
    l'unique table. Les 225 devis d'une page de 200 leads portaient 39,3 Mio
    de JSON ``etude_params`` (jusqu'à 1,45 Mio pour un seul devis : l'étude
    horaire C&I), décodés en ~123 Mio d'objets Python à CHAQUE requête pour
    lire ces trois chemins — +254 Mio de RSS définitifs par worker, 3 Gio de
    conteneur saturés, 17 workers tués par le noyau dans la journée.

    Aucun montant ne change : les lecteurs passent tous par
    ``utils.annotations_devis.cle_etude``, qui rend la même valeur ET le même
    type. Un lecteur d'un chemin NON annoté coûterait une requête PAR DEVIS
    (champ déferré) — le budget de requêtes de
    ``apps/crm/tests_perf_n1_leads.py`` rougit alors, il ne se tait pas.
    """
    from django.db.models import Prefetch

    return (
        Prefetch(prefixe, queryset=_devis_sans_etude()),
        f'{prefixe}__lignes__produit',
        f'{prefixe}__superseded_by',
    )


def prefetch_devis_resume(prefixe='devis'):
    """ACVI94 — le préchargement RÉSUMÉ des devis d'une liste de leads (cockpit,
    objectifs, attribution) : statut, dates et montants sans le JSON d'étude.

    Les chemins de ``ANNOTATION_PAR_CLE`` restent annotés : ``total_ttc`` lit
    ``scenario`` et ``nombre_proprietes`` par ``cle_etude`` ; sans eux, chaque
    lecture de montant rechargerait la colonne déferrée, devis par devis."""
    from django.db.models import Prefetch

    return (Prefetch(prefixe, queryset=_devis_sans_etude()),)


def _devis_sans_etude():
    """Les devis ``defer('etude_params')`` avec ses seuls chemins lus ANNOTÉS."""
    from django.db.models.fields.json import KeyTransform

    from .models import Devis
    from .utils.annotations_devis import ANNOTATION_PAR_CLE

    def _extrait(chemin):
        """``etude_params -> … -> derniere_cle`` pour un chemin imbriqué.

        ``->`` (``KeyTransform``) à TOUS les niveaux, jamais ``->>`` : le
        résultat reste du jsonb, que Django redécode — un entier revient
        ``int``, une chaîne ``str``, comme la lecture du JSON. ``->>``
        ramènerait tout en texte et ``nombre_proprietes`` stocké ``3.0``
        deviendrait ``int('3.0')`` → ValueError → 1 villa : un TOTAL FAUX.
        """
        cles = (chemin,) if isinstance(chemin, str) else tuple(chemin)
        expression = 'etude_params'
        for cle in cles:
            expression = KeyTransform(cle, expression)
        return expression

    return (Devis.objects
            .defer('etude_params')
            .annotate(**{annote: _extrait(chemin)
                         for chemin, annote in ANNOTATION_PAR_CLE.items()}))


# ---------------------------------------------------------------------------
# T4-X4-005 — la liste des devis (``/ventes/devis``) paginée PAR LE SERVEUR :
# l'écran chargeait TOUS les devis (590 pour un responsable ≈ 48 Mo) pour
# filtrer, chercher et compter dans le navigateur. Les filtres et la synthèse
# de l'en-tête sont calculés ici, sur la portée déjà bornée par la vue.
# ---------------------------------------------------------------------------
#: Statuts effectifs de la liste : le statut stocké, sauf qu'un devis en
#: attente dont la validité est passée se lit « expire » (T7, ``utils.expiry``).
STATUTS_EFFECTIFS = ('brouillon', 'envoye', 'accepte', 'refuse', 'expire')


def filtrer_liste_devis(qs, company, *, q=None, statut_effectif=None,
                        actifs=False, auteurs=None):
    """Recherche (référence ou nom du client), statut effectif, versions
    remplacées masquées, auteurs — les mêmes règles que l'écran appliquait
    aux devis chargés, appliquées en SQL."""
    from django.db.models import Q
    from django.utils import timezone

    from .utils.expiry import q_expire_a_la_volee

    if q:
        qs = qs.filter(Q(reference__icontains=q) | Q(client__nom__icontains=q))
    if statut_effectif:
        expire = q_expire_a_la_volee(company, timezone.localdate())
        if statut_effectif == 'expire':
            qs = qs.filter(Q(statut='expire') | expire)
        elif statut_effectif in ('brouillon', 'envoye'):
            qs = qs.filter(statut=statut_effectif).exclude(expire)
        else:
            qs = qs.filter(statut=statut_effectif)
    if actifs:
        qs = qs.filter(is_active=True)
    if auteurs:
        qs = qs.filter(created_by_id__in=auteurs)
    return qs


# ADEV162 — le total d'un devis est calculé par le MOTEUR du PDF
# (``display_totals``, 20 à 30 ms par devis, inexprimable en SQL) : sur 583
# devis la synthèse prenait 11 à 21 s à froid. Il est donc RANGÉ sur le devis
# (``total_affiche_range``) avec l'EMPREINTE de tout ce dont il a été calculé
# (``total_affiche_empreinte``), écrit hors de toute lecture par
# ``domain.etudes.ranger_totaux_affiches`` (après chaque écriture du devis et
# de ses lignes, balayage planifié, commande). La synthèse relit l'empreinte et
# ne sert le total rangé que si elle CONCORDE ; sinon elle recalcule (et ne
# range rien : un GET n'écrit jamais). L'empreinte couvre les DONNÉES que le
# calcul lit sans requête (la ligne du devis hors horodatage et colonnes
# rangées, ses lignes, leurs produits hors colonnes de stock, les fiches
# techniques, le client, la société et son profil) et le CODE : l'empreinte
# des sources de ``_SOURCES_DU_TOTAL`` — tout déploiement qui y touche
# périme tous les totaux rangés (le balayage les recalcule).
_HORS_EMPREINTE = frozenset({'updated_at', 'search_vector', 'lock_version',
                             'total_affiche_range', 'total_affiche_empreinte'})
# Colonnes de ``stock.Produit`` réécrites par la vie du stock et que le calcul
# du total ne lit pas (prouvé par ``test_aprf6_liste_sans_conception``) :
# hors empreinte, sinon un mouvement de stock périmerait tous les devis du
# panneau courant. Toute AUTRE colonne, présente ou future, est hachée.
# D-ACAL-169 — ``panneau_par_defaut`` (le panneau désigné de la société) ne
# décide qu'une composition NOUVELLE (``domain.panneau_defaut.devis_a_naitre``) ;
# un devis existant lit le panneau de SES lignes : le total affiché ne le lit
# jamais, et désigner un autre panneau ne périme aucun total rangé.
PRODUIT_HORS_EMPREINTE = frozenset({
    'quantite_stock', 'seuil_alerte', 'date_mise_a_jour',
    'prix_achat', 'quantite_reappro_cible', 'delai_appro_jours', 'fournisseur_id',
    'panneau_par_defaut'})
# Les sources dont le total affiché dépend : tout ``apps/ventes`` (moteur,
# options, arrondis, classement, multivilla…), ``core`` (``core.money``),
# ``apps/parametres`` (profil, tarifs) et la ville de calcul du lead, hors
# tests et migrations ; ``test_aprf6_liste_sans_conception`` vérifie que chaque
# fichier du dépôt exécuté par ``display_totals`` y est.
_SOURCES_DU_TOTAL = ('apps/ventes', 'core', 'apps/parametres', 'apps/crm/devis_selectors.py')
# Les SEULES colonnes du lead que le calcul lit (``crm.ville_effective``, quand
# l'étude n'a pas figé sa ville) — relevé par le même test : le reste du lead
# (score, date de modification…) bouge chaque jour sans rien changer au total.
LEAD_LU_PAR_LE_TOTAL = ('ville', 'ville_reference')
PREFETCH_TOTAUX = ('lignes', 'lignes__produit', 'lignes__produit__fiche_technique')


def fichiers_du_total():
    """Les fichiers ``.py`` de ``_SOURCES_DU_TOTAL`` (chemins absolus, triés)."""
    import os

    from django.conf import settings
    trouves = []
    for source in _SOURCES_DU_TOTAL:
        chemin = os.path.join(str(settings.BASE_DIR), source)
        if source.endswith('.py'):
            trouves.append(chemin)
            continue
        for racine, dossiers, fichiers in os.walk(chemin):
            dossiers[:] = sorted(x for x in dossiers if x not in ('tests', 'migrations', '__pycache__'))
            trouves += [os.path.join(racine, f) for f in fichiers
                        if f.endswith('.py') and not f.startswith('test')]
    return sorted(trouves)


@functools.lru_cache(maxsize=1)
def empreinte_du_code():
    """Le hachage des octets des sources du total, calculé UNE fois par
    processus (≈ 1 000 fichiers lus au premier appel)."""
    import hashlib
    h = hashlib.sha256()
    for chemin in fichiers_du_total():
        with open(chemin, 'rb') as f:
            h.update(f.read())
    return h.hexdigest()


def _sql_empreinte_devis():
    """La grosse ligne du devis (étude de 60 Ko) et la ville du lead hachées par la
    base — en Python, 600 études coûtaient 1,4 s de ``repr``."""
    from django.db import connection

    from .models import Devis
    q = connection.ops.quote_name
    table = q(Devis._meta.db_table)
    colonnes = ', '.join('%s.%s' % (table, q(f.column)) for f in Devis._meta.concrete_fields
                         if f.attname not in _HORS_EMPREINTE)
    lead = q(Devis._meta.get_field('lead').related_model._meta.db_table)
    lus = ', '.join('l.%s' % q(c) for c in LEAD_LU_PAR_LE_TOTAL)
    # Sûr (bandit B608) : les cinq morceaux interpolés sont des IDENTIFIANTS, tous
    # passés par ``quote_name`` — table et colonnes tirées de ``Devis._meta``, table
    # du lead de ``_meta`` du modèle lié, colonnes du lead de la constante de module
    # ``LEAD_LU_PAR_LE_TOTAL``, ``lead_id`` littéral ; aucune valeur de requête,
    # de réglage ni de contenu de base.
    return ("md5(ROW(%s)::text) || COALESCE((SELECT md5(ROW(%s)::text) FROM %s l"  # nosec B608
            " WHERE l.id = %s.%s), '-')" % (colonnes, lus, lead, table, q('lead_id')))


def devis_pour_les_totaux(qs, *, leger=False):
    """Le jeu de lecture UNIQUE de la synthèse et de l'écrivain : mêmes
    lignes chargées, donc même empreinte des deux côtés. ``leger`` laisse en
    base les gros blocs JSON du devis (l'empreinte les hache en SQL) : la
    synthèse ne les charge que pour les devis à recalculer."""
    from django.db.models.expressions import RawSQL

    from .serializers import CHAMPS_RETIRES_LISTE_DEVIS
    # Sûr (bandit B611) : SQL fait des seuls identifiants cités de _sql_empreinte_devis, sans paramètre.
    empreinte = RawSQL(_sql_empreinte_devis(), ())  # nosec B611
    qs = (qs.select_related('client', 'lead', 'company').order_by('pk')
          .prefetch_related(None).prefetch_related(*PREFETCH_TOTAUX)
          .annotate(empreinte_sql_adev162=empreinte))
    return qs.defer(*CHAMPS_RETIRES_LISTE_DEVIS) if leger else qs


def profil_pour_les_totaux(company):
    """Le profil société relu EN BASE (un profil tout juste créé garde en
    mémoire ses valeurs par défaut non normalisées : l'empreinte différerait)."""
    from apps.parametres.models import CompanyProfile
    profil = CompanyProfile.lire(company)
    if getattr(profil, 'pk', None):
        profil.refresh_from_db()
    return profil


def _valeurs(obj, hors=_HORS_EMPREINTE):
    if obj is None:
        return None
    return [f.value_from_object(obj) for f in obj._meta.concrete_fields
            if f.attname not in hors]


def empreinte_total_affiche(devis, profil):
    """L'empreinte de ce que ``display_totals`` lit pour ce devis."""
    import hashlib
    lignes = sorted(((lg.pk, _valeurs(lg),
                      _valeurs(lg.produit if lg.produit_id else None,
                               _HORS_EMPREINTE | PRODUIT_HORS_EMPREINTE),
                      _valeurs(getattr(lg.produit, 'fiche_technique', None)
                               if lg.produit_id else None))
                     for lg in devis.lignes.all()), key=lambda t: t[0])
    contenu = repr((empreinte_du_code(), devis.empreinte_sql_adev162, lignes,
                    _valeurs(devis.client), _valeurs(devis.company), _valeurs(profil)))
    return hashlib.sha256(contenu.encode('utf-8')).hexdigest()


def total_du_moteur(devis, display_totals, donnees=None):
    """``donnees`` reste vide quand le moteur a échoué (total de repli)."""
    from decimal import Decimal
    return Decimal(str(display_totals(devis, lignes_prechargees=True,
                                      donnees=donnees)['total'] or 0))


def total_range_valide(devis, profil):
    """Le total rangé si son empreinte concorde avec la relecture, sinon None."""
    if (devis.total_affiche_range is not None
            and devis.total_affiche_empreinte == empreinte_total_affiche(devis, profil)):
        return devis.total_affiche_range
    return None


def _totaux_par_statut(qs, company, jour):
    """Nombre et total affiché par statut effectif des devis en jeu : le total
    rangé quand il concorde, sinon ``display_totals`` sur le devis relu en
    entier (un second passage, en nombre de requêtes constant)."""
    from decimal import Decimal

    from .quote_engine.builder import display_totals
    from .utils.expiry import is_expired
    profil = profil_pour_les_totaux(company)
    par_statut = {s: {'count': 0, 'total': Decimal('0')} for s in STATUTS_EFFECTIFS}
    a_calculer = {}
    for devis in devis_pour_les_totaux(qs.filter(is_active=True), leger=True).iterator(chunk_size=100):
        cle = 'expire' if is_expired(devis, today=jour) else devis.statut
        cellule = par_statut.setdefault(cle, {'count': 0, 'total': Decimal('0')})
        cellule['count'] += 1
        total = total_range_valide(devis, profil)
        if total is None:
            a_calculer[devis.pk] = cle
        else:
            cellule['total'] += total
    if a_calculer:
        for devis in devis_pour_les_totaux(qs.filter(pk__in=list(a_calculer))).iterator(chunk_size=50):
            par_statut[a_calculer[devis.pk]]['total'] += total_du_moteur(devis, display_totals)
    return par_statut


def synthese_liste_devis(qs, company):
    """L'en-tête de la liste sur TOUTE la portée (pas sur la page) : nombre et
    total affiché par statut effectif des devis en jeu, devis à relancer
    (envoyés, validité ≤ 7 jours), option batterie des acceptés, versions
    remplacées. Le total d'argent est ``display_totals`` — le MÊME que la
    colonne « Total TTC » de chaque ligne (``total_affiche``), jamais un
    second calcul ; les devis sont lus par paquets (mémoire bornée)."""
    from datetime import timedelta

    from django.utils import timezone

    from core.money import quantize_mad

    from .utils.expiry import q_expiration
    jour = timezone.localdate()
    par_statut = _totaux_par_statut(qs, company, jour)
    for cellule in par_statut.values():  # une seule règle d'arrondi de l'argent (core.money)
        cellule['total'] = float(quantize_mad(cellule['total']))
    a_relancer = (qs.filter(is_active=True, statut='envoye')
                  .filter(q_expiration(company, apres=jour,
                                       avant=jour + timedelta(days=7)))
                  .values('id', 'reference'))
    acceptes = qs.filter(statut='accepte')
    return {
        'total': qs.count(),
        'remplaces': qs.filter(is_active=False).count(),
        'par_statut': par_statut,
        'a_relancer': [{'id': d['id'], 'reference': d['reference']}
                       for d in a_relancer],
        'batterie': {
            'avec': acceptes.filter(option_acceptee='avec_batterie').count(),
            'sans': acceptes.filter(option_acceptee='sans_batterie').count(),
        },
    }
