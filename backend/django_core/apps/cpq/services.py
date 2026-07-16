"""Services (écritures / orchestration) de l'app CPQ.

Toute écriture cross-app (créer des ``LigneDevis``, lire un ``Devis``…) passe
par des imports LOCAUX (fonction-locaux) des modèles ventes/crm pour éviter les
cycles — l'app cpq est en aval de ventes dans le graphe d'apps."""
from decimal import Decimal, ROUND_HALF_UP

from .models import (
    LigneOffreGroupee, RegleApprobationRemise, EtapeApprobationDevis,
)

_CENT = Decimal('0.01')


def appliquer_offre_groupee(*, offre, devis, user=None):
    """NTCPQ3 — Insère les ``LigneDevis`` d'une offre groupée dans un devis.

    Si ``offre.prix_total`` est renseigné et qu'au moins une ligne est en mode
    ``FIXE``, le total du bundle PRIME : il est réparti au prorata du prix
    catalogue (``produit.prix_vente`` × quantité) sur les lignes, le reste de
    centime étant absorbé par la dernière ligne pour que le sous-total HT égale
    exactement ``prix_total``. Sinon chaque ligne est valorisée par son propre
    ``mode_prix`` (``REMISE_PCT`` / ``PRIX_COMPOSANT``).

    Renvoie la liste des ``LigneDevis`` créées. Écriture cross-app ventes via
    import local (aucun import de ``ventes.models`` au niveau module)."""
    from apps.ventes.models import LigneDevis

    lignes = list(offre.lignes.select_related('produit').all())
    if not lignes:
        return []

    fixe = LigneOffreGroupee.ModePrix.FIXE
    use_bundle_total = (
        offre.prix_total is not None
        and any(li.mode_prix == fixe for li in lignes))

    created = []
    if use_bundle_total:
        poids = [
            (li, (li.produit.prix_vente or Decimal('0')) * (li.quantite or Decimal('1')))
            for li in lignes]
        base = sum((w for _, w in poids), Decimal('0')) or Decimal('1')
        prix_total = Decimal(str(offre.prix_total))
        running = Decimal('0')
        n = len(poids)
        for i, (li, w) in enumerate(poids):
            if i < n - 1:
                part = (prix_total * (w / base)).quantize(_CENT, ROUND_HALF_UP)
                running += part
            else:
                part = prix_total - running  # dernière ligne absorbe le reste
            qte = li.quantite or Decimal('1')
            pu = (part / qte).quantize(_CENT, ROUND_HALF_UP)
            created.append(LigneDevis.objects.create(
                devis=devis, produit=li.produit,
                designation=li.produit.nom, quantite=qte,
                prix_unitaire=pu, remise=Decimal('0')))
    else:
        for li in lignes:
            qte = li.quantite or Decimal('1')
            if li.mode_prix == LigneOffreGroupee.ModePrix.REMISE_PCT:
                pu = li.produit.prix_vente
                remise = li.valeur if li.valeur is not None else Decimal('0')
            elif li.mode_prix == LigneOffreGroupee.ModePrix.PRIX_COMPOSANT:
                pu = li.valeur if li.valeur is not None else li.produit.prix_vente
                remise = Decimal('0')
            else:  # FIXE sans prix_total → repli prix catalogue
                pu = li.produit.prix_vente
                remise = Decimal('0')
            created.append(LigneDevis.objects.create(
                devis=devis, produit=li.produit,
                designation=li.produit.nom, quantite=qte,
                prix_unitaire=pu, remise=remise))
    return created


def resoudre_regle_remise(*, company, remise):
    """NTCPQ7 — Résout la règle d'approbation de remise la plus SPÉCIFIQUE
    couvrant ``remise`` (%) pour la société. Renvoie une
    ``RegleApprobationRemise`` ou ``None`` (aucune règle → aucune approbation)."""
    candidates = [
        r for r in RegleApprobationRemise.objects.filter(
            company=company, actif=True)
        if r.couvre(remise)]
    if not candidates:
        return None

    def _cle(r):
        largeur = r.largeur_intervalle()
        # None (intervalle ouvert) = moins spécifique → trié après les bornés.
        largeur_key = (1, Decimal('0')) if largeur is None else (0, largeur)
        return (largeur_key, -int(r.priorite), -r.id)

    candidates.sort(key=_cle)
    return candidates[0]


def _profondeur_remise(devis):
    """Profondeur de remise réelle du devis (en %). Utilise ``remise_globale``
    (déjà un pourcentage). Repli 0."""
    return Decimal(str(getattr(devis, 'remise_globale', 0) or 0))


def lancer_approbation_devis(devis, *, user=None):
    """NTCPQ7 — Instancie les étapes d'approbation d'un devis selon la
    profondeur de remise réelle.

    Résout la règle par ``remise_globale``. Aucune règle (ou
    ``nombre_approbateurs`` = 0) ⇒ aucune étape (envoi libre). Sinon crée
    ``nombre_approbateurs`` étapes ``en_attente`` (niveaux 1..N). Idempotent :
    si des étapes non rejetées existent déjà pour ce devis, les renvoie sans en
    recréer. Renvoie la liste des étapes (existantes ou créées)."""
    existantes = list(EtapeApprobationDevis.objects.filter(
        devis_id=devis.id).exclude(
            statut=EtapeApprobationDevis.Statut.REJETE))
    if existantes:
        return existantes

    remise = _profondeur_remise(devis)
    regle = resoudre_regle_remise(company=devis.company, remise=remise)
    if regle is None or regle.nombre_approbateurs < 1:
        return []

    etapes = []
    for niveau in range(1, regle.nombre_approbateurs + 1):
        etapes.append(EtapeApprobationDevis.objects.create(
            company=devis.company, devis=devis, regle=regle,
            niveau=niveau, niveau_approbation=regle.niveau_approbation,
            statut=EtapeApprobationDevis.Statut.EN_ATTENTE))
    return etapes


def approuver_etape_devis(devis, *, user, commentaire=''):
    """NTCPQ8 — Approuve la PREMIÈRE étape en attente du devis.

    Pose ``approbateur``/``decision_le``, passe la statut à ``approuve``, logue
    l'événement dans le chatter du devis (DevisActivity). Renvoie
    ``(etape, toutes_approuvees)`` où ``toutes_approuvees`` est True quand plus
    aucune étape n'est en attente. Lève ``ValidationError`` s'il n'y a aucune
    étape en attente."""
    from django.utils import timezone
    from rest_framework.exceptions import ValidationError
    from apps.ventes import activity

    etape = EtapeApprobationDevis.objects.filter(
        devis_id=devis.id,
        statut=EtapeApprobationDevis.Statut.EN_ATTENTE,
    ).order_by('niveau', 'id').first()
    if etape is None:
        raise ValidationError({'detail': 'Aucune étape en attente.'})
    etape.statut = EtapeApprobationDevis.Statut.APPROUVE
    etape.approbateur = user
    etape.decision_le = timezone.now()
    if commentaire:
        etape.commentaire = commentaire
    etape.save(update_fields=[
        'statut', 'approbateur', 'decision_le', 'commentaire'])
    activity.log_devis_note(
        devis, user,
        f"Approbation de remise — étape {etape.niveau} approuvée"
        + (f" : {commentaire}" if commentaire else ""))
    reste = EtapeApprobationDevis.objects.filter(
        devis_id=devis.id,
        statut=EtapeApprobationDevis.Statut.EN_ATTENTE).exists()
    return etape, not reste


def rejeter_etape_devis(devis, *, user, motif=''):
    """NTCPQ8 — Rejette la première étape en attente : passe la statut à
    ``rejete`` (approbateur/motif), remet le devis en ``brouillon`` et logue
    l'événement (auteur + motif) dans le chatter. Renvoie l'étape rejetée."""
    from django.utils import timezone
    from rest_framework.exceptions import ValidationError
    from apps.ventes import activity
    from apps.ventes.models import Devis

    etape = EtapeApprobationDevis.objects.filter(
        devis_id=devis.id,
        statut=EtapeApprobationDevis.Statut.EN_ATTENTE,
    ).order_by('niveau', 'id').first()
    if etape is None:
        raise ValidationError({'detail': 'Aucune étape en attente.'})
    etape.statut = EtapeApprobationDevis.Statut.REJETE
    etape.approbateur = user
    etape.decision_le = timezone.now()
    etape.commentaire = motif or ''
    etape.save(update_fields=[
        'statut', 'approbateur', 'decision_le', 'commentaire'])
    # Renvoie le devis en brouillon (jamais envoyé tant que la remise n'est pas
    # approuvée / revue à la baisse).
    if devis.statut != Devis.Statut.BROUILLON:
        devis.statut = Devis.Statut.BROUILLON
        devis.save(update_fields=['statut'])
    activity.log_devis_note(
        devis, user,
        f"Approbation de remise — étape {etape.niveau} REJETÉE"
        + (f" : {motif}" if motif else "")
        + " — devis renvoyé en brouillon.")
    return etape
