"""AOF60/AOF62 — service d'orchestration du calepinage : la COUTURE, STATELESS
côté moteur.

Ce module est le seul point par lequel ``apps.ao`` appelle
``core.calepinage``. Il ne contient **aucune géométrie** : il désérialise,
délègue, VALIDE, et — pour le chemin persistant — écrit le résultat, la preuve
et les marges en appliquant les gardes de publication d'AOF28.

Deux fonctions, deux responsabilités qui ne doivent jamais fusionner
--------------------------------------------------------------------
* ``calepiner(entree_json, *, company, user)`` — **STATELESS**. Elle
  désérialise un document du contrat AOF57, calcule, valide, et renvoie du
  JSON. Elle n'écrit RIEN en base, ne change AUCUN statut, ne produit AUCUN
  document. C'est ce qui rend l'aperçu d'un tiroir de l'atelier gratuit : on
  peut la rejouer mille fois sans laisser de trace.
* ``calculer_variante(toiture, params, *, user)`` — compose l'entrée depuis
  les modèles (enveloppe, obstacles actifs, kits, preset), appelle la première,
  puis PERSISTE résultat + preuve + marges sur une ``VarianteCalepinage``.

**Le moteur est injectable.** ``moteur=`` accepte tout objet exposant
``calculer(surface, parametres, obstacles, zones)`` : les tests peuvent
compter les appels (preuve du cache d'AOF61) ou simuler un moteur lent sans
toucher au paquet pur.

Frontières respectées
---------------------
* aucun import de ``apps.crm`` / ``apps.ventes`` / ``apps.stock`` — le prix
  d'un kit vient de la string-FK ``stock.Produit`` portée par le modèle, jamais
  d'un import cross-app ici ;
* ``valider()`` (AOF51) est appelée sur CHAQUE surface AVANT tout retour : un
  résultat incohérent lève ``CalepinageIncoherent``, il ne sort jamais de ce
  module ;
* aucun coût, aucun ``prix_achat``, aucune marge ne transite ici : le service
  ne produit que de la géométrie et des comptes.
"""
from __future__ import annotations

import logging

from core.calepinage.exceptions import CalepinageIncoherent
from core.calepinage.garde_fous import valider
from core.calepinage.obstacles import appliquer_regles, engageable
from core.calepinage.optimum import calculer as calculer_optimum
from core.calepinage.perf import BudgetCalcul, estimer_cout, optimiser_economique
from core.calepinage.poseur import poser_plan
from core.calepinage.robustesse import marges_du_plan
from core.calepinage.serialisation import (
    EntreeCalepinage, SchemaIncompatible, hash_entree,
)
from core.calepinage.types import ModePose
from core.calepinage.version import VERSION_MOTEUR

from . import calepinage_io
from .calepinage_io import EntreeInvalide

logger = logging.getLogger(__name__)

__all__ = [
    'MoteurCalepinage', 'EntreeInvalide', 'CalepinageIncoherent',
    'calepiner', 'calculer_variante', 'cout_estime', 'empreinte_document',
    'retenir_variante', 'comparer_variantes', 'calculer_sensibilites',
    'calculer_marches', 'VariantePerimee',
]


class VariantePerimee(Exception):
    """AOF62 — on ne retient jamais une variante dont l'entrée a bougé."""


class MoteurCalepinage:
    """Adaptateur MINCE devant le paquet pur — le seul « moteur » injectable.

    Il ne fait qu'un choix, et ce choix est celui des ``Parametres`` :
    ``RANGEES_EXPLICITES_DP`` passe par ``perf.optimiser_economique`` (le même
    optimum que le balayage au centimètre, sur un jeu de positions
    strictement équivalent et bien plus petit) ; tout autre mode de pose passe
    par ``optimum.calculer``, qui sait déléguer au balayage de phase.

    ``appels`` compte les délégations RÉELLES au moteur : c'est ce compteur que
    le test du cache d'AOF61 observe pour prouver qu'un second appel identique
    ne recalcule rien.
    """

    version = VERSION_MOTEUR

    def __init__(self):
        self.appels = 0

    def calculer(self, surface, parametres, obstacles=(), zones=(),
                 politique=None):
        self.appels += 1
        if parametres.mode_pose is ModePose.RANGEES_EXPLICITES_DP:
            return optimiser_economique(surface, parametres, obstacles, zones,
                                        politique)
        return calculer_optimum(surface, parametres, obstacles, zones,
                                politique)


def _moteur(moteur):
    return moteur if moteur is not None else MoteurCalepinage()


def _entree(document):
    """Désérialise un document du contrat — refus NOMMÉ, jamais un ``KeyError``."""
    try:
        return EntreeCalepinage.depuis_dict(document)
    except SchemaIncompatible as erreur:
        raise EntreeInvalide(str(erreur)) from erreur
    except (KeyError, TypeError, ValueError) as erreur:
        raise EntreeInvalide(
            "Document de calepinage invalide : %s" % erreur) from erreur


def empreinte_document(document):
    """Empreinte canonique d'un document d'entrée (AOF57), au millimètre."""
    return hash_entree(_entree(document))


def cout_estime(document, *, budget=None):
    """Chiffre le travail AVANT de le lancer, sur la surface la plus lourde.

    C'est ce chiffre qui pilote la bascule synchrone/asynchrone d'AOF61 : au
    delà du budget, l'API refuse de faire attendre l'utilisateur et renvoie la
    consigne d'appel asynchrone.
    """
    entree = _entree(document)
    obstacles = appliquer_regles(entree.obstacles)
    par_surface = calepinage_io.affectations_du_document(
        document, entree.surfaces, obstacles)
    budget = budget or BudgetCalcul()
    cumul = None
    for surface in entree.surfaces:
        cout = estimer_cout(surface, entree.parametres,
                            par_surface.get(surface.repere, ()),
                            entree.zones, budget=budget)
        if cumul is None:
            cumul = cout
            continue
        # cumul HONNÊTE : on additionne les appels, pas les motifs.
        cumul = type(cout)(
            positions=cumul.positions + cout.positions,
            kits=cout.kits, variantes=cout.variantes,
            appels=cumul.appels + cout.appels,
            millisecondes=cumul.millisecondes + cout.millisecondes,
            synchrone=(cumul.millisecondes + cout.millisecondes
                       <= budget.seuil_synchrone_ms),
            motif=cout.motif)
    if cumul is None:
        raise EntreeInvalide("Le document ne déclare aucune surface.")
    return cumul


# ───────────────────────────────────────────────── AOF60 — calcul STATELESS
def calepiner(document, *, company, user=None, moteur=None):
    """Calcule un calepinage COMPLET et renvoie du JSON. N'écrit RIEN.

    ``company`` est OBLIGATOIRE : le service refuse de tourner hors société,
    de sorte qu'aucun chemin d'appel ne puisse contourner le cloisonnement
    multi-tenant en oubliant un argument.

    Raises:
        EntreeInvalide: document non conforme au contrat (motif français).
        CalepinageIncoherent: un contrôle d'AOF51 a échoué — le résultat ne
            sort JAMAIS de cette fonction.
    """
    if company is None:
        raise EntreeInvalide(
            'Un calepinage se calcule toujours dans une société : '
            '`company` est obligatoire.')
    entree = _entree(document)
    obstacles = appliquer_regles(entree.obstacles)
    par_surface = calepinage_io.affectations_du_document(
        document, entree.surfaces, obstacles)
    machine = _moteur(moteur)

    plans = []
    total_modules = 0
    total_kwc = 0.0
    preuves = []
    marges_globales = None
    controles = None

    for surface in entree.surfaces:
        lot = par_surface.get(surface.repere, ())
        resultat = machine.calculer(surface, entree.parametres, lot,
                                    entree.zones)
        rangees = tuple((y0, entree.parametres.kit(code))
                        for y0, code in resultat.rangees)
        tables = poser_plan(surface, rangees, lot, entree.zones)

        # AOF51 — la porte, PAS un rapport : ``strict=True`` lève avant retour.
        rapport = valider(surface, entree.parametres, rangees, lot,
                          entree.zones, tables=tables, preuve=resultat.preuve,
                          strict=True)
        controles = (tuple(rapport.controles_passes) if controles is None
                     else tuple(c for c in controles
                                if c in set(rapport.controles_passes)))

        marges_globales = _cumuler_marges(
            marges_globales,
            marges_du_plan(surface, rangees, lot, entree.zones))

        plans.append(calepinage_io.plan_vers_json(surface.repere, resultat,
                                                  tables))
        total_modules += resultat.plan.modules
        for rangee in resultat.plan.rangees:
            kit = entree.parametres.kit(rangee.kit_code)
            total_kwc += rangee.modules * kit.puissance_module_wc / 1000.0
        preuves.append(resultat.preuve)

    ok_engagement, motifs = engageable(obstacles)
    empreinte = hash_entree(entree)
    sortie = calepinage_io.resultat_vers_json(
        repere=entree.repere, hash_entree=empreinte, modules=total_modules,
        kwc=total_kwc, plans=plans, engageable=ok_engagement,
        motifs_non_engageable=motifs)
    sortie['company_id'] = getattr(company, 'id', company)
    sortie['preuve'] = calepinage_io.preuve_vers_json(
        _preuve_cumulee(preuves), marges_globales,
        controles=controles or (),
        pas_recherche_m=entree.parametres.pas_recherche_m)
    sortie['engagement_modules'] = entree.parametres.engagement_modules
    return sortie


def _cumuler_marges(cumul, marges):
    """Retient la marge la PLUS SERRÉE de chaque axe, indépendamment.

    Un site de trois segments a trois jeux de marges : publier celles d'un seul
    segment cacherait le segment au ras. Les deux axes sont cumulés
    SÉPARÉMENT — un segment sans obstacle (aucune marge de bande MESURÉE) ne
    doit jamais écraser la marge de bande réelle d'un autre segment par un
    zéro qui ne veut rien dire.
    """
    from core.calepinage.types import Marges

    if cumul is None:
        return marges
    troncon, rangee = cumul.troncon_min_m, cumul.rangee_critique
    if marges.rangee_critique and (
            not rangee or marges.troncon_min_m < troncon):
        troncon, rangee = marges.troncon_min_m, marges.rangee_critique
    bande, obstacle = cumul.bande_min_m, cumul.obstacle_critique
    if marges.obstacle_critique and (
            not obstacle or marges.bande_min_m < bande):
        bande, obstacle = marges.bande_min_m, marges.obstacle_critique
    return Marges(troncon_min_m=troncon, bande_min_m=bande,
                  rangee_critique=rangee, obstacle_critique=obstacle)


def _preuve_cumulee(preuves):
    """Agrège les preuves de N surfaces en UNE preuve du site.

    La méthode retenue est la MOINS forte des méthodes rencontrées : un site
    dont un seul segment a été calculé par heuristique n'est pas « prouvé
    optimal ». C'est le verrou de vocabulaire d'AOF44, appliqué au cumul.
    """
    from core.calepinage.types import Preuve

    if not preuves:
        raise EntreeInvalide('Aucune surface calculée : preuve impossible.')
    if len(preuves) == 1:
        return preuves[0]
    inexactes = [p for p in preuves if not p.methode.exacte]
    methode = inexactes[0].methode if inexactes else preuves[0].methode
    optimaux = [p.compte_optimal for p in preuves]
    bornes = [p.borne_superieure for p in preuves]
    return Preuve(
        methode=methode,
        pas_recherche_m=max(p.pas_recherche_m for p in preuves),
        compte_retenu=sum(p.compte_retenu for p in preuves),
        compte_optimal=(None if any(v is None for v in optimaux)
                        else sum(optimaux)),
        borne_superieure=(None if any(v is None for v in bornes)
                          else sum(bornes)),
        nb_plans_optimaux=None)


# ─────────────────────────────────────── AOF60 — calcul PERSISTÉ (variante)
def calculer_variante(toiture, params=None, *, user=None, moteur=None,
                      nom='', role=None, parent=None, appel_offre=None,
                      variante=None):
    """Compose l'entrée depuis les modèles, calcule, et PERSISTE la variante.

    Les gardes de publication d'AOF28 sont appliquées ICI : la variante ne
    devient ``publiable`` que si sa PREUVE le démontre (total retenu = total
    optimal, marges au-dessus des seuils, aucun obstacle non mesuré actif).
    Sinon elle reste ``calculee`` et porte ses motifs dans ``justification`` —
    jamais un statut optimiste qu'un écran présenterait comme engageant.
    """
    from .models import VarianteCalepinage

    document = calepinage_io.document_entree(toiture, params=params)
    sortie = calepiner(document, company=toiture.company, user=user,
                       moteur=moteur)

    if variante is None:
        variante = VarianteCalepinage(
            company=toiture.company, toiture=toiture,
            appel_offre=appel_offre or toiture.batiment.appel_offre,
            role=role or VarianteCalepinage.Role.RETENUE, parent=parent)
    variante.nom = nom or variante.nom or (
        'Calepinage %s' % (toiture.code_document or toiture.pk))
    variante.params = dict(params if params is not None
                           else (toiture.parametres_calepinage or {}))
    variante.entree_hash = sortie['hash_entree']
    variante.resultat = {k: v for k, v in sortie.items() if k != 'preuve'}
    variante.preuve = sortie['preuve']
    variante.version_moteur = VERSION_MOTEUR
    variante.statut = VarianteCalepinage.Statut.CALCULEE
    variante.save()

    _appliquer_gardes_publication(variante)
    return variante


def _appliquer_gardes_publication(variante):
    """AOF28 — passe ``publiable`` SI et SEULEMENT SI la preuve le démontre."""
    raisons = variante.raisons_de_non_publiabilite()
    if raisons:
        variante.statut = variante.Statut.CALCULEE
        variante.justification = '\n'.join(raisons)
    else:
        variante.statut = variante.Statut.PUBLIABLE
        variante.justification = variante.preuve.get('libelle', '')
    variante.save(update_fields=['statut', 'justification', 'updated_at'])
    return variante


# ─────────────────────────────────────── AOF62 — actions de variante
def retenir_variante(variante, *, user=None):
    """Désigne LA variante retenue — IDEMPOTENTE, et jamais sur une périmée.

    Rejouer l'appel sur une variante déjà retenue ne fait rien (aucune seconde
    bascule, aucun second calcul). Une variante ``PERIME`` est REFUSÉE : son
    entrée a bougé depuis le calcul, la retenir publierait un plan que la
    donnée ne soutient plus.
    """
    from . import services

    if variante.statut == variante.Statut.PERIME:
        raise VariantePerimee(
            "La variante « %s » est PÉRIMÉE : son entrée a changé depuis le "
            "calcul. Recalculez-la avant de la retenir." % variante.nom)
    if variante.est_retenue:
        return variante
    return services.retenir_variante(variante)


def comparer_variantes(company, identifiants):
    """Compare N variantes EN UN APPEL — une requête, aucun calcul moteur.

    Les nombres comparés sont ceux qui ont été PROUVÉS au calcul : la
    comparaison ne rejoue pas le moteur, sans quoi deux colonnes du même écran
    pourraient sortir de deux versions différentes.
    """
    from .models import VarianteCalepinage

    identifiants = [int(i) for i in identifiants]
    variantes = list(VarianteCalepinage.objects.filter(
        company=company, pk__in=identifiants).select_related('toiture'))
    trouvees = {v.pk for v in variantes}
    manquantes = [i for i in identifiants if i not in trouvees]
    lignes = []
    for variante in variantes:
        preuve = variante.preuve or {}
        lignes.append({
            'id': variante.pk,
            'nom': variante.nom,
            'role': variante.role,
            'statut': variante.statut,
            'est_retenue': variante.est_retenue,
            'toiture': variante.toiture_id,
            'total_modules': variante.total_modules,
            'kwc': variante.puissance_kwc,
            'total_optimal': preuve.get('total_optimal'),
            'optimal': preuve.get('optimal'),
            'methode': preuve.get('methode'),
            'marge_troncon_min': preuve.get('marge_troncon_min'),
            'marge_bande_min': preuve.get('marge_bande_min'),
            'version_moteur': variante.version_moteur,
            'entree_hash': variante.entree_hash,
        })
    lignes.sort(key=lambda ligne: (-(ligne['total_modules'] or 0),
                                   ligne['id']))
    reference = lignes[0]['total_modules'] if lignes else 0
    for ligne in lignes:
        ligne['delta_modules'] = (ligne['total_modules'] or 0) - reference
    return {'lignes': lignes, 'introuvables': manquantes,
            'reference_modules': reference}


def calculer_sensibilites(variante, *, user=None, moteur=None):
    """Rejoue la batterie défavorable et PERSISTE les marches ``SENSIBILITE``.

    IDEMPOTENTE par construction : chaque sensibilité est identifiée par son
    CODE moteur et écrite en ``update_or_create`` sous la variante parente —
    rejouer l'appel met à jour les mêmes lignes, il n'en crée jamais de
    secondes.
    """
    from core.calepinage.sensibilites import batterie

    from .models import VarianteCalepinage

    toiture = variante.toiture
    document = calepinage_io.document_entree(toiture,
                                             params=variante.params or None)
    entree = _entree(document)
    obstacles = appliquer_regles(entree.obstacles)
    par_surface = calepinage_io.affectations_du_document(
        document, entree.surfaces, obstacles)
    if len(entree.surfaces) != 1:
        raise EntreeInvalide(
            "La batterie de sensibilités se calcule surface par surface : "
            "cette toiture en déclare %d." % len(entree.surfaces))
    surface = entree.surfaces[0]
    resultat = batterie(surface, entree.parametres,
                        par_surface.get(surface.repere, ()), entree.zones,
                        engagement=entree.parametres.engagement_modules)

    enfants = []
    for sensibilite in resultat.sensibilites:
        enfant, _cree = VarianteCalepinage.objects.update_or_create(
            company=variante.company, toiture=toiture, parent=variante,
            role=VarianteCalepinage.Role.SENSIBILITE, nom=sensibilite.code,
            defaults={
                'appel_offre_id': variante.appel_offre_id,
                'params': dict(variante.params or {}),
                'entree_hash': variante.entree_hash,
                'resultat': {'total_modules': sensibilite.modules,
                             'delta': sensibilite.delta,
                             'libelle': sensibilite.libelle},
                'preuve': {'total_retenu': sensibilite.modules,
                           'total_optimal': sensibilite.modules,
                           'methode': 'sensibilite',
                           'version_moteur': VERSION_MOTEUR},
                'statut': VarianteCalepinage.Statut.CALCULEE,
                'justification': sensibilite.libelle,
                'version_moteur': VERSION_MOTEUR,
            })
        enfants.append(enfant)
    return {
        'reference_modules': resultat.reference,
        'plancher_modules': resultat.plancher,
        'engagement_modules': resultat.engagement,
        'verdict': resultat.verdict(),
        'non_applicables': list(resultat.non_applicables),
        'sensibilites': [
            {'id': enfant.pk, 'code': sensibilite.code,
             'libelle': sensibilite.libelle, 'modules': sensibilite.modules,
             'delta': sensibilite.delta, 'tenu': sensibilite.tenu}
            for enfant, sensibilite in zip(enfants, resultat.sensibilites)],
    }


def calculer_marches(variante):
    """Rejoue l'échelle de décomposition d'une variante — deltas SIGNÉS.

    Les marches sont les variantes filles de rôle ``MARCHE`` : chacune porte
    son état nommé et son compte. ``echelle.comparer`` republie les deltas à
    partir des comptes PERSISTÉS, et ``verifier_honnetete`` fait échouer une
    marche qui n'a pas redonné le nombre qu'elle annonçait.
    """
    from core.calepinage.echelle import EtatNomme, comparer, verifier_honnetete

    from .models import VarianteCalepinage

    filles = list(VarianteCalepinage.objects.filter(
        company=variante.company, parent=variante,
        role=VarianteCalepinage.Role.MARCHE).order_by('id'))
    etats = [
        EtatNomme(code=fille.nom, libelle=fille.justification or fille.nom,
                  calculer=(lambda f=fille: int(f.total_modules or 0)),
                  attendu=(fille.resultat or {}).get('attendu'))
        for fille in filles
    ]
    echelle = comparer(etats)
    motifs = verifier_honnetete(echelle, strict=False)
    return {
        'recit': echelle.recit(),
        'depart': echelle.depart,
        'arrivee': echelle.arrivee,
        'gain_total': echelle.gain_total,
        'honnete': not motifs,
        'motifs': list(motifs),
        'marches': [{'code': m.code, 'libelle': m.libelle,
                     'modules': m.modules, 'delta': m.delta,
                     'attendu': m.attendu} for m in echelle.marches],
    }
