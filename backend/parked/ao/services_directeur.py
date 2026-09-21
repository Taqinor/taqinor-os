"""AOF157 — services de l'ÉCONOMIE d'un appel d'offres (DIRECTEUR SEUL).

Module SÉPARÉ de ``apps.ao.services`` pour la même raison que les serializers
et les vues : un coût, une marge ou un bénéfice ne doivent JAMAIS se retrouver
par distraction dans un chemin consommé par une surface non-directeur.
"""
from __future__ import annotations

from decimal import Decimal

__all__ = ['creer_economie', 'donnees_du_classeur', 'economie_du_projet',
           'nouvelle_cible']


def creer_economie(appel_offre, *, benefice_net_cible_ht=None, user=None,
                   motif='', arrondi_psychologique=None,
                   seuil_psychologique=None, ligne_ajustement=None, **champs):
    """Crée l'économie d'un AO (et sa première cible s'il y a une cible visée).

    L'arrondi, le SEUIL psychologique (la barre des 5 M en TTC) et la ligne
    d'ajustement appartiennent à la CIBLE, pas à l'économie : ils sont
    VERSIONNÉS avec elle, donc explicitement redirigés vers ``nouvelle_cible``
    au lieu de tomber dans ``**champs`` (où ils atterrissaient sur
    ``EconomieAO.objects.create()``, qui ne porte aucun de ces champs).
    ``**champs`` reste réservé aux vrais champs de l'économie (taux de TVA,
    note comptable, verrou).
    """
    from .models import EconomieAO

    economie = EconomieAO.objects.create(
        company=appel_offre.company, appel_offre=appel_offre, **champs)
    valeurs_de_cible = (benefice_net_cible_ht, arrondi_psychologique,
                        seuil_psychologique, ligne_ajustement)
    if any(valeur is not None for valeur in valeurs_de_cible):
        nouvelle_cible(
            economie,
            benefice_net_cible_ht=(benefice_net_cible_ht
                                   if benefice_net_cible_ht is not None
                                   else Decimal('0.00')),
            motif=motif, arrondi_psychologique=arrondi_psychologique,
            seuil_psychologique=seuil_psychologique,
            ligne_ajustement=ligne_ajustement, user=user)
    return economie


def nouvelle_cible(economie, *, benefice_net_cible_ht, motif='',
                   arrondi_psychologique=None, seuil_psychologique=None,
                   ligne_ajustement=None, user=None):
    """Ajoute une VERSION de cible financière et désactive la précédente.

    Chaque version porte son auteur, sa date et son motif : c'est ce qui
    permet de justifier un mouvement de prix sans reconstituer de mémoire.
    L'auteur est posé CÔTÉ SERVEUR, jamais lu d'un corps de requête.
    """
    from django.db import transaction

    from .models import CibleFinanciere

    with transaction.atomic():
        precedente = economie.cibles.filter(active=True).first()
        version = (precedente.version + 1) if precedente else 1
        if precedente is not None:
            precedente.active = False
            precedente.save(update_fields=['active', 'updated_at'])
        cible = CibleFinanciere.objects.create(
            company=economie.company, economie=economie, version=version,
            benefice_net_cible_ht=Decimal(str(benefice_net_cible_ht)),
            arrondi_psychologique=(
                arrondi_psychologique
                if arrondi_psychologique is not None
                else (precedente.arrondi_psychologique if precedente
                      else Decimal('0.00'))),
            seuil_psychologique=(
                seuil_psychologique
                if seuil_psychologique is not None
                else (precedente.seuil_psychologique if precedente else None)),
            ligne_ajustement=(
                ligne_ajustement
                if ligne_ajustement is not None
                else (precedente.ligne_ajustement if precedente else None)),
            active=True, auteur=user, motif=motif or '')
    _journaliser_cible(cible, precedente, user)
    return cible


def _journaliser_cible(cible, precedente, user):
    """Trace le mouvement au chatter générique ``records`` (best-effort).

    Le chatter est posé sur l'APPEL D'OFFRES : il est déjà scopé société et
    déjà gardé. Le MONTANT n'y figure pas — un chatter se lit avec ``ao_voir``,
    pas avec ``ao_rentabilite_voir``.
    """
    from apps.records.models import Activity
    from apps.records.services import log_activity

    log_activity(
        cible.economie.appel_offre, Activity.Kind.MODIFICATION, user=user,
        field='cible_financiere', field_label='Cible financière (directeur)',
        old_value=f'v{precedente.version}' if precedente else '',
        new_value=f'v{cible.version}', body=cible.motif or '',
        company=cible.company)


def economie_du_projet(appel_offre_id):
    """L'économie DIRECTEUR d'un AO + la référence à porter sur le classeur.

    Point d'entrée unique de la tâche ``ao.produire_rentabilite_xlsx`` : elle
    importait ce nom sans qu'il existe, et dégradait donc silencieusement en
    « rien à produire » — le classeur de rentabilité n'était jamais généré.
    Renvoie ``(None, '')`` quand l'AO n'a pas encore d'économie, ce que la
    tâche sait traiter.
    """
    from .models import AppelOffre

    ao = (AppelOffre.objects
          .filter(pk=appel_offre_id)
          .select_related('economie')
          .first())
    if ao is None:
        return None, ''
    economie = getattr(ao, 'economie', None)
    return economie, (ao.reference or '')


def donnees_du_classeur(economie):
    """Traduit l'``EconomieAO`` en la structure attendue par le rendu XLSX.

    ``fabrique.rendus.rentabilite_xlsx.ecrire_classeur`` consomme le
    DICTIONNAIRE calculé par ``construire_economie`` (``economie['postes']``,
    ``economie['controle_tresorerie']``…), pas une instance de modèle. La tâche
    ``ao.produire_rentabilite_xlsx`` lui passait l'instance : le classeur ne
    pouvait pas être produit — il n'a jamais existé qu'en théorie. Ce
    traducteur est la pièce qui manquait entre les deux moitiés déjà écrites.

    Le TAUX de TVA sur achats est celui du RÉGIME de la ligne (réduit pour les
    panneaux, standard pour le reste) : c'est la différenciation qui rend la
    TVA nette à reverser juste, et donc le contrôle de trésorerie vérifiable.
    Les taux sont stockés en POURCENTAGE sur l'économie et attendus en FRACTION
    par le rendu — la division par 100 est faite ici, une seule fois.

    Raises:
        ControleTresorerieRouge: aucun poste de coût, ou ventilation de TVA
            incohérente (le rendu refuse de produire un classeur faux).
    """
    from .fabrique.rendus.rentabilite_xlsx import construire_economie
    from .models import LigneCoutRevient

    cent = Decimal('100')
    postes = []
    for ligne in economie.lignes.all():
        reduit = ligne.regime_tva == LigneCoutRevient.RegimeTVA.REDUIT
        taux = (economie.taux_tva_achat_reduit if reduit
                else economie.taux_tva_achat_standard)
        postes.append({
            'libelle': ligne.designation or ligne.get_poste_display(),
            'montant_ht': ligne.montant_ht,
            'taux_tva_achat': Decimal(str(taux)) / cent,
        })
    return construire_economie(
        postes,
        total_vente_ht=economie.total_ht,
        taux_tva_vente=Decimal(str(economie.taux_tva_vente)) / cent)
