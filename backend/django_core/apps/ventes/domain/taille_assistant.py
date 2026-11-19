"""Copilote vague 2 (VAD7, décision D-W2-Q1 = OUI_APRES_CONFIRMATION) — « mets-lui
12 panneaux » : la taille d'un devis BROUILLON ou ENVOYÉ changée en place.

UNE SEULE MACHINERIE, CELLE DE L'ÉCRAN. Le geste est exactement celui de
« Taille Recommandé → Appliquer au devis » (``views/devis_etudes.py``,
``offres_tailles_appliquer``) : configuration de la taille « Recommandé »
(``offres_tailles.enregistrer_config``), marqueur de composition imposée retiré
(geste explicite), ``offres_tailles.appliquer_au_devis`` (mode « réconcilier » :
onduleur, structures et câbles suivent, prix négociés et remise globale gardés,
toit borné, devis envoyé corrigé en place et tracé « corrigé après envoi »,
statut jamais écrit — règle #4) puis rebase de l'échéancier.

L'APERÇU joue le MÊME chemin dans une transaction ANNULÉE : rien n'est écrit,
et les totaux qu'il rend sont ceux que l'écriture produira. L'écriture exige
que l'appelant recopie l'ancien et le nouveau total de l'aperçu (ce sont eux
que la confirmation a montrés) : s'ils ne sont plus ceux que le serveur
recalcule, rien n'est écrit (409 ``apercu_perime``).

Aucun PDF n'est produit ici (le PDF client reste ``/proposal``) ; aucun prix
d'achat ni marge dans ce qui est rendu.
"""
from decimal import Decimal, InvalidOperation

from django.db import transaction

from core.money import quantize_mad

#: Bornes du nombre de panneaux demandé à l'assistant.
PANNEAUX_MIN, PANNEAUX_MAX = 1, 200
_LIBELLES_CLOS = {'accepte': 'accepté', 'refuse': 'refusé', 'expire': 'expiré'}


class TailleRefusee(Exception):
    """Un refus d'état : 409 ``{detail, field, code}``."""

    def __init__(self, detail, *, field, code):
        super().__init__(detail)
        self.corps = {'detail': detail, 'field': field, 'code': code}


def _texte(valeur):
    from apps.ventes.selectors_assistant import texte_montant
    return texte_montant(valeur)


def refus_de_statut(devis):
    """Le refus d'un devis qui ne se corrige plus (geste TAILLE du prédicat
    unique ``domain/modifiabilite``), avec la phrase qui dit quoi faire."""
    from .modifiabilite import TAILLE, verdict

    if verdict(devis, TAILLE)['modifiable']:
        return None
    ref = devis.reference
    if not devis.is_active:
        return TailleRefusee(
            f'Devis {ref} remplacé par une nouvelle version : il ne se corrige '
            'plus. Travaillez sur la version en cours (fiche du devis).',
            field='statut', code='version_remplacee')
    libelle = _LIBELLES_CLOS.get(devis.statut, devis.get_statut_display())
    return TailleRefusee(
        f'Devis {ref} {libelle} : il ne se corrige plus. Proposez de le réviser '
        '(V2 brouillon), puis changez la taille sur la V2.',
        field='statut', code='revision_possible')


def refus_du_toit(devis, nb_panneaux):
    """Au-dessus de la contenance mesurée du toit (même borne que les cartes
    de taille) : refus qui la nomme. Aucune géométrie ⇒ aucune borne."""
    from .dimensionnement_devis import contenance_toit_du_devis

    contenance = contenance_toit_du_devis(devis)
    if contenance and nb_panneaux > int(contenance):
        return TailleRefusee(
            f'Le toit tient {int(contenance)} panneaux au plus (calepinage du '
            f'devis) : {nb_panneaux} panneaux ne tiennent pas.',
            field='nb_panneaux', code='toit_trop_petit')
    return None


def _appliquer(devis, nb_panneaux, modules, utilisateur, ttc_avant):
    """Le corps de ``offres_tailles_appliquer`` (configuration comprise)."""
    from apps.ventes.offres_tailles import (
        ApplicationImpossible, appliquer_au_devis, enregistrer_config)
    from .composition_imposee import effacer_marqueur, marqueur
    from .modifiabilite import rebaser_echeancier_ou_409

    compose_sur_demande = marqueur(devis) is not None  # lu AVANT de l'effacer
    config = {'nb_panneaux': int(nb_panneaux)}
    if modules:
        config['batterie_nb_modules'] = int(modules)
    enregistrer_config(devis, 'recommande', config, utilisateur=utilisateur)
    effacer_marqueur(devis)
    try:
        resume = appliquer_au_devis(devis, 'recommande', utilisateur=utilisateur)
    except ApplicationImpossible as erreur:
        if erreur.revision_possible:
            raise TailleRefusee(erreur.detail, field='statut',
                                code='revision_possible') from erreur
        if compose_sur_demande:
            # Essai du 19/11 : un devis composé sur demande n'a pas d'étude de
            # consommation — le refus dit le geste qui marche, pas seulement non.
            raise TailleRefusee(
                'Ce devis a été composé sur demande (composition imposée, sans '
                'étude de consommation) : sa taille ne se recalcule pas en place. '
                f'Pour {int(nb_panneaux)} panneaux, composez un nouveau devis avec '
                'la même demande et ce nombre de panneaux ; l\'ancien brouillon se '
                'supprime à l\'écran.',
                field='nb_panneaux', code='composition_imposee') from erreur
        raise TailleRefusee(erreur.detail, field='nb_panneaux',
                            code='taille_impossible') from erreur
    rebaser_echeancier_ou_409(devis, ttc_avant=ttc_avant)
    return resume


def _alertes(resume):
    return [a if isinstance(a, dict) else {'code': 'taille', 'message': str(a)}
            for a in (resume.get('avertissements') or [])]


def _kwc(devis):
    from .scenario import puissance_kwc_du_devis
    valeur = puissance_kwc_du_devis(devis)
    return round(float(valeur), 3) if valeur is not None else None


def mesurer(devis, nb_panneaux, modules=None, *, utilisateur=None,
            ecrire=False, attendus=None):
    """La taille ``nb_panneaux`` (et ``modules`` de batterie) jouée sur
    ``devis`` : écrite si ``ecrire`` (et seulement si ``attendus`` — les deux
    totaux de l'aperçu — sont toujours ceux du serveur), annulée sinon. Rend
    ``{statut, corrige_apres_envoi, nb_panneaux_avant, nb_panneaux,
    kwc_avant, kwc, ancien_total_ttc, nouveau_total_ttc, alertes}``. Lève
    :class:`TailleRefusee` (aucune écriture)."""
    from .modifiabilite import ttc_du_devis

    refus = refus_de_statut(devis) or refus_du_toit(devis, nb_panneaux)
    if refus is not None:
        raise refus
    statut, kwc_avant, ttc_avant = devis.statut, _kwc(devis), ttc_du_devis(devis)
    with transaction.atomic():
        resume = _appliquer(devis, nb_panneaux, modules, utilisateur, ttc_avant)
        devis.refresh_from_db()
        mesure = {
            'statut': statut,
            'corrige_apres_envoi': statut == 'envoye',
            'nb_panneaux_avant': resume.get('panneaux_avant'),
            'nb_panneaux': resume.get('panneaux') or int(nb_panneaux),
            'kwc_avant': kwc_avant,
            'kwc': _kwc(devis),
            'ancien_total_ttc': _texte(ttc_avant),
            'nouveau_total_ttc': _texte(ttc_du_devis(devis)),
            'alertes': _alertes(resume),
        }
        if not ecrire:
            transaction.set_rollback(True)
        else:
            exiger_apercu_a_jour(mesure, attendus or {})
    return mesure


def _montant_lu(valeur):
    try:
        return quantize_mad(Decimal(str(valeur)))
    except (InvalidOperation, TypeError, ValueError):
        return None


def exiger_apercu_a_jour(mesure, attendus):
    """409 ``apercu_perime`` (sous la transaction : tout est annulé) quand
    l'ancien ou le nouveau total confirmé n'est plus celui du serveur."""
    for champ in ('ancien_total_ttc', 'nouveau_total_ttc'):
        if _montant_lu(attendus.get(champ)) != Decimal(mesure[champ]):
            raise TailleRefusee(
                'Les totaux ont changé depuis l\'aperçu (ancien total '
                f'{mesure["ancien_total_ttc"]} MAD TTC, nouveau total '
                f'{mesure["nouveau_total_ttc"]} MAD TTC) : relisez l\'aperçu et '
                'faites confirmer les nouveaux chiffres.',
                field=champ, code='apercu_perime')
