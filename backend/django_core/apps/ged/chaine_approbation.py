"""XGED20 — chaîne séquentielle d'approbation d'un document GED (corps sortis
de ``services.py``, mur de ~7 000 lignes, pour qu'il ne grossisse pas).

* :func:`avancer_chaine_verrouillee` — ADOC14 : avance l'étape courante, sous
  verrou de ligne (demande + chaîne) posé par
  ``services.avancer_chaine_approbation_ged`` ;
* :func:`reprendre_chaine_a_l_etape_1` — ASEC84 : une nouvelle version arrivée
  pendant la revue remet la chaîne à l'étape 1 (une approbation donnée sur
  l'ancienne version ne compte plus).
"""
from django.db import transaction


def avancer_chaine_verrouillee(demande, chaine, *, user, commentaire,
                               get_user_model, _tz):
    """ADOC14 — corps de `avancer_chaine_approbation_ged`, appelé sous
    verrou de ligne (demande + chaîne)."""
    from .services import approve_demande

    etapes = list(chaine.etapes or [])
    idx = chaine.etape_courante
    if idx < len(etapes):
        etapes[idx]['statut'] = 'approuve'
        etapes[idx]['decision_le'] = _tz.now().isoformat()
    if idx + 1 < len(etapes):
        # Étape suivante : réassigne l'approbateur actif, la demande reste
        # « en_attente » (décision globale pas encore prise).
        etapes[idx + 1]['statut'] = 'en_cours'
        User = get_user_model()
        suivant = User.objects.filter(
            company=demande.company, pk=etapes[idx + 1]['approbateur_id']).first()
        demande.approbateur = suivant
        demande.save(update_fields=['approbateur', 'updated_at'])
        chaine.etapes = etapes
        chaine.etape_courante = idx + 1
        chaine.save(update_fields=['etapes', 'etape_courante', 'updated_at'])
        return demande
    # Dernière étape : décision définitive (réutilise GED18, jamais dupliqué).
    chaine.etapes = etapes
    chaine.save(update_fields=['etapes', 'updated_at'])
    return approve_demande(demande, user=user, commentaire=commentaire)


def reprendre_chaine_a_l_etape_1(document, *, utilisateur=None):
    """ASEC84 — la demande EN ATTENTE du document dont la chaîne a dépassé
    l'étape 1 repart à l'étape 1 : étapes remises (la première « en_cours »,
    les autres « en_attente », décisions effacées), approbateur réassigné à
    celui de l'étape 1, journal. Sans chaîne en cours : rien (None)."""
    from django.contrib.auth import get_user_model

    from .models import APPROBATION_EN_ATTENTE, ChaineApprobationGed
    from .services import journaliser_evenement

    with transaction.atomic():
        chaine = (ChaineApprobationGed.objects.select_for_update()
                  .filter(demande__document=document, etape_courante__gt=0,
                          demande__statut=APPROBATION_EN_ATTENTE).first())
        if chaine is None:
            return None
        etapes = [{**e, 'statut': 'en_attente', 'decision_le': None}
                  for e in (chaine.etapes or [])]
        if etapes:
            etapes[0]['statut'] = 'en_cours'
        chaine.etapes, chaine.etape_courante = etapes, 0
        chaine.save(update_fields=['etapes', 'etape_courante', 'updated_at'])
        demande = chaine.demande
        demande.approbateur = get_user_model().objects.filter(
            company=document.company,
            pk=etapes[0]['approbateur_id']).first() if etapes else None
        demande.save(update_fields=['approbateur', 'updated_at'])
    journaliser_evenement(
        document, type_evenement='changement_statut',
        message="Nouvelle version — chaîne d'approbation reprise à l'étape 1.",
        utilisateur=utilisateur)
    return chaine
