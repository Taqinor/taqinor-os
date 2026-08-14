"""NTWMS34 — Services du contrôle qualité à réception (échantillonnage).

Trois responsabilités, aucune ailleurs :
  * ``plan_echantillonnage_pour_produit`` — quel plan s'applique à un produit
    (plan de sa catégorie, sinon plan par défaut de la société, sinon aucun) ;
  * ``echantillon_requis_pour_reception`` — le drapeau DÉRIVÉ que la tâche
    situait sur ``ReceptionFournisseur`` (modèle d'``achats``, hors périmètre
    de cette lane) : vrai dès qu'une ligne de la réception relève d'un plan à
    taux > 0 ;
  * ``enregistrer_controle_reception`` — saisie du verdict, puis routage :
    conforme → put-away normal ; non conforme → quarantaine (``BlocageQualite``
    NTWMS31), jamais du stock vendable.

La GARDE elle-même (« pas de confirmation sans contrôle ») est posée dans
``confirm_reception_fournisseur`` (``services.py``), qui appelle
``verifier_controle_reception`` juste avant de toucher au stock.
"""
import logging

logger = logging.getLogger(__name__)


def plan_echantillonnage_pour_produit(company, produit):
    """Plan applicable à ce produit, ou ``None``.

    Priorité : plan de la catégorie du produit, puis plan par défaut de la
    société (catégorie nulle). Un plan inactif ne s'applique jamais.
    """
    from .models import PlanEchantillonnage

    plans = list(PlanEchantillonnage.objects.filter(
        company=company, actif=True))
    if not plans:
        return None
    categorie_id = getattr(produit, 'categorie_id', None)
    if categorie_id:
        for plan in plans:
            if plan.categorie_id == categorie_id:
                return plan
    for plan in plans:
        if plan.categorie_id is None:
            return plan
    return None


def echantillon_requis_pour_reception(reception):
    """Vrai si AU MOINS une ligne de la réception relève d'un plan à taux > 0.

    C'est le drapeau ``echantillon_requis`` de la tâche, calculé au moment où
    on en a besoin plutôt que stocké dans l'app d'un autre domaine.
    """
    company = reception.company
    if company is None:
        return False
    for ligne in reception.lignes.select_related('produit'):
        if ligne.produit_id is None:
            continue
        plan = plan_echantillonnage_pour_produit(company, ligne.produit)
        if plan is not None and plan.taux_echantillon_pct:
            return True
    return False


def echantillon_attendu_reception(reception):
    """Nombre total d'unités à contrôler sur cette réception (somme des
    plans ligne à ligne). 0 = aucun contrôle exigé."""
    company = reception.company
    if company is None:
        return 0
    total = 0
    for ligne in reception.lignes.select_related('produit'):
        if ligne.produit_id is None:
            continue
        plan = plan_echantillonnage_pour_produit(company, ligne.produit)
        if plan is not None:
            total += plan.unites_a_controler(ligne.quantite)
    return total


def controle_de_reception(reception):
    """Le ``ControleReception`` saisi pour cette réception, ou ``None``."""
    from .models import ControleReception
    return ControleReception.objects.filter(reception=reception).first()


def verifier_controle_reception(reception):
    """Lève ``ValueError`` si un plan s'applique ET qu'aucun verdict qualité
    n'a été saisi. No-op total pour toute société sans plan (comportement
    historique strictement inchangé)."""
    if not echantillon_requis_pour_reception(reception):
        return None
    controle = controle_de_reception(reception)
    if controle is None:
        raise ValueError(
            'Un plan d\'échantillonnage s\'applique à cette réception : '
            'saisissez le résultat du contrôle qualité avant de confirmer.')
    return controle


def enregistrer_controle_reception(*, reception, user, resultat,
                                   unites_controlees=0, observation=''):
    """Saisit (ou corrige tant que la réception est en brouillon) le verdict
    qualité d'une réception.

    Une réception DÉJÀ CONFIRMÉE ne se re-contrôle pas : le verdict a piloté
    le routage du stock, le rejouer produirait une seconde quarantaine.
    """
    from django.db import transaction

    from .models import ControleReception, ReceptionFournisseur

    valides = {c for c, _ in ControleReception.Resultat.choices}
    if resultat not in valides:
        raise ValueError(
            'Résultat invalide : attendu « conforme » ou « non_conforme ».')
    if reception.statut == ReceptionFournisseur.Statut.CONFIRME:
        raise ValueError(
            'Cette réception est déjà confirmée : son contrôle qualité ne '
            'peut plus être modifié.')
    try:
        controlees = max(int(unites_controlees or 0), 0)
    except (TypeError, ValueError):
        raise ValueError('Nombre d\'unités contrôlées invalide.')

    attendues = echantillon_attendu_reception(reception)
    with transaction.atomic():
        controle = controle_de_reception(reception)
        if controle is None:
            controle = ControleReception(
                company=reception.company, reception=reception)
        controle.resultat = resultat
        controle.unites_controlees = controlees
        controle.unites_attendues = attendues
        controle.observation = (observation or '').strip()
        controle.controle_par = user
        controle.save()
    return controle


def router_apres_controle(reception, user):
    """Après confirmation : conforme → rien (put-away normal, NTWMS2) ;
    non conforme → la marchandise reçue part en QUARANTAINE (NTWMS31).

    Best-effort ET idempotent : un blocage déjà posé pour cette réception
    n'est jamais dupliqué. Appelé APRÈS le commit de la confirmation.
    """
    from .models import BlocageQualite, ControleReception

    controle = controle_de_reception(reception)
    if controle is None or controle.resultat != (
            ControleReception.Resultat.NON_CONFORME):
        return []
    if BlocageQualite.objects.filter(
            company=reception.company, reception=reception).exists():
        return []

    blocages = []
    for ligne in reception.lignes.select_related('produit'):
        qte = int(ligne.quantite or 0)
        if ligne.produit_id is None or qte <= 0:
            continue
        blocages.append(BlocageQualite.objects.create(
            company=reception.company, produit=ligne.produit, quantite=qte,
            reception=reception, bloque_par=user,
            statut=BlocageQualite.Statut.EN_QUARANTAINE,
            motif=(f'NTWMS34 — contrôle à réception non conforme '
                   f'({reception.reference}).')))
    logger.info('NTWMS34 quarantaine reception=%s lignes=%d',
                reception.reference, len(blocages))
    return blocages
