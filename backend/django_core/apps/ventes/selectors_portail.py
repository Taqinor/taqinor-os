"""Sélecteurs LECTURE SEULE du portail client (devis et factures du client,
payabilité, résumé du portail) — sortis de ``apps/ventes/selectors.py`` par
SPL147 (déplacement pur, corps inchangés ; propriétaire : documents).

Les autres apps continuent de lire ces fonctions par la FAÇADE
``apps.ventes.selectors`` (ré-export en fin de fichier) ; ce module est PLAT :
aucun import de ``.selectors`` en tête (cycle).
"""


# ── NTPRT10/NTPRT11 — Lectures self-service du PORTAIL CLIENT ───────────────
#
# Point d'entrée cross-app UNIQUE de ``apps.portail`` sur les documents
# ``ventes`` (jamais un import de ``apps.ventes.models`` depuis portail).
# Lecture SEULE et volontairement PAUVRE : uniquement ce qu'un client peut voir
# de SON dossier. Aucun champ de coût/marge n'y figure (``prix_achat``,
# ``marge``… ne sortent JAMAIS vers un écran client — registre
# ``core.permissions.SENSITIVE_FIELDS``), ni aucune donnée interne
# (propriétaire, notes, portée de visibilité).
#
# Les fonctions exigent ``company`` ET ``client_id`` : un ``client_id`` absent
# renvoie VIDE, jamais tous les documents de la société.

def devis_envoyes_du_client(company_id, client_id):
    """QJR590 — devis ACTIFS au statut « envoyé » d'un client (borné
    société) : ceux dont le client a déjà reçu un exemplaire et qui reçoivent
    une trace « corrigé après envoi » quand l'identité client est corrigée.
    Un accepté garde son exemplaire signé figé (exclu)."""
    from .models import Devis

    if not company_id or not client_id:
        return []
    return list(Devis.objects.filter(
        company_id=company_id, client_id=client_id, is_active=True,
        statut=Devis.Statut.ENVOYE))


def devis_du_client_portail(company, client_id, *, limit=200):
    """NTPRT10 — Devis visibles par le client ``client_id`` sur son portail.

    Les BROUILLONS internes sont EXCLUS : un devis non envoyé n'a jamais été
    montré au client, l'exposer serait une fuite de travail en cours.
    """
    from .models import Devis

    if company is None or not client_id:
        return []
    # QJR520 — une version remplacée n'est plus listée à côté de sa
    # remplaçante (is_active=True).
    qs = (Devis.objects
          .filter(company=company, client_id=client_id, is_active=True)
          .exclude(statut=Devis.Statut.BROUILLON)
          .order_by('-date_creation')[:limit])
    return [{
        'id': d.id,
        'reference': d.reference,
        'statut': d.statut,
        'statut_display': d.get_statut_display(),
        'date_creation': d.date_creation,
        'date_validite': d.date_validite,
        'total_ttc': str(d.total_ttc),
        'accepte': d.statut == Devis.Statut.ACCEPTE,
        # QJR565 (contrat portail ``mes_devis_liste.json``) — date de la
        # dernière correction après envoi (``etude_params.resync_apres_envoi``),
        # null sinon — JAMAIS updated_at.
        'mis_a_jour_le': _date_correction_apres_envoi(d),
        # ADOC113 (contrat ``mes_devis_liste.json``) — LE prédicat QJR55 que
        # ``accept_devis`` relit : un devis à deux options s'accepte au
        # portail avec l'option choisie (``options[].cle``), jamais sans.
        **_options_portail(d),
    } for d in qs]


def _options_portail(devis):
    """ADOC113 — ``deux_options`` (``deux_options_declarees``) et ``options``
    (null si mono-option, sinon les deux choix de ``Devis.OptionAcceptee``).
    Aucun montant : le chiffrage par option reste le PDF /proposal."""
    from .models import Devis
    from .utils.options import deux_options_declarees

    deux = bool(deux_options_declarees(devis))
    return {
        'deux_options': deux,
        'options': ([{'cle': cle, 'libelle': libelle}
                     for cle, libelle in Devis.OptionAcceptee.choices]
                    if deux else None),
    }


def _date_correction_apres_envoi(devis):
    """QJR565 — ISO de ``etude_params.resync_apres_envoi.date`` ou ``None``."""
    params = devis.etude_params if isinstance(devis.etude_params, dict) else {}
    marqueur = params.get('resync_apres_envoi')
    if isinstance(marqueur, dict):
        return marqueur.get('date') or None
    return None


def devis_du_client_portail_obj(company, client_id, devis_id):
    """NTPRT10 — UN devis du client (objet ORM), ou ``None``.

    Le triplet (société, client, id) est exigé : un devis d'un autre client —
    ou d'une autre société — est INTROUVABLE, jamais « trouvé puis refusé ».
    """
    from .models import Devis

    if company is None or not client_id or not devis_id:
        return None
    # ADOC125 — même périmètre que la liste : une version REMPLACÉE
    # (is_active=False) est introuvable, donc jamais acceptable au portail.
    return (Devis.objects
            .filter(company=company, client_id=client_id, pk=devis_id,
                    is_active=True)
            .exclude(statut=Devis.Statut.BROUILLON)
            .first())


def factures_du_client_portail(company, client_id, *, limit=200):
    """NTPRT11 — Factures visibles par le client ``client_id`` sur son portail.

    Mêmes règles : brouillons internes exclus, aucun champ de coût.
    ``montant_du`` est le reste à payer déjà calculé par le modèle (source
    unique — jamais un recalcul local qui divergerait de l'écran interne),
    SAUF pour une facture ANNULÉE (AUD137) : ``Facture.montant_du`` ignore le
    statut par construction et rend donc le TTC entier pour une annulation
    sans paiement — l'agrégat portail compense ici en la figeant à '0.00'.
    ``payable`` (AUD137) est le SEUL champ que l'écran doit lire pour décider
    d'afficher « reste dû » et le bouton « Payer » : faux pour ANNULEE et
    PAYEE, jamais dérivé côté client depuis ``statut``.
    """
    from .models import Facture

    if company is None or not client_id:
        return []
    qs = (Facture.objects
          .filter(company=company, client_id=client_id)
          .exclude(statut=Facture.Statut.BROUILLON)
          # AUD159 — EXACTEMENT les relations lues par les deux propriétés
          # sérialisées ci-dessous : `total_ttc` itère `lignes` (via
          # `tva_par_taux`) et `montant_du` touche `paiements`,
          # `affectations_paiement`, `avoirs`, `notes_debit` et
          # `retenues_subies`. Le queryset n'avait AUCUN prefetch : jusqu'à
          # ~7 requêtes par facture, sur 200 factures par page — d'une surface
          # PUBLIQUE, donc exposée à la charge externe. La SOURCE des chiffres
          # ne change pas : les propriétés modèles restent propriétaires.
          .prefetch_related('lignes', 'paiements', 'avoirs', 'notes_debit',
                            'retenues_subies',
                            'affectations_paiement__paiement')
          .order_by('-date_emission', '-id')[:limit])
    return [{
        'id': f.id,
        'reference': f.reference,
        'statut': f.statut,
        'statut_display': f.get_statut_display(),
        'date_emission': f.date_emission,
        'date_echeance': f.date_echeance,
        'montant_ttc': str(f.total_ttc),
        'montant_du': ('0.00' if f.statut == Facture.Statut.ANNULEE
                       else str(f.montant_du)),
        'payee': f.statut == Facture.Statut.PAYEE,
        'payable': f.statut not in (
            Facture.Statut.ANNULEE, Facture.Statut.PAYEE),
    } for f in qs]


def facture_du_client_portail(company, client_id, facture_id):
    """NTPRT11 — UNE facture du client (objet ORM), ou ``None``. Voir ci-dessus."""
    from .models import Facture

    if company is None or not client_id or not facture_id:
        return None
    return (Facture.objects
            .filter(company=company, client_id=client_id, pk=facture_id)
            .exclude(statut=Facture.Statut.BROUILLON)
            .first())


def facture_est_payable_portail(facture):
    """AUD137 — une facture ANNULÉE ou déjà PAYÉE n'est plus payable au
    portail. Utilisé par ``portail.views_client.payer`` AVANT de créer/
    réutiliser une intention de paiement — jamais un import de
    ``apps.facturation.models`` côté portail (frontière cross-app)."""
    from .models import Facture

    return facture is not None and facture.statut not in (
        Facture.Statut.ANNULEE, Facture.Statut.PAYEE)


# ── NTPRT9 — Tableau de bord CLIENT (devis en attente / factures impayées) ──

def resume_portail_client(company, client_id):
    """NTPRT9 — Cartes « Devis en attente » / « Factures impayées » du
    tableau de bord portail CLIENT (``apps.portail.views_client``).

    Même périmètre EXACTEMENT que ``devis_du_client_portail``/
    ``factures_du_client_portail`` ci-dessus (brouillons exclus, aucun champ
    de coût) : les compteurs matchent donc, par construction, ce que l'écran
    interne montrerait pour ce même client — jamais un recalcul divergent.
    ``devis_en_attente`` = devis ``ENVOYE`` (ni accepté/refusé/expiré, en
    attente d'une décision du client). ``factures_impayees`` = factures
    ``EMISE``/``EN_RETARD`` (ni payées, ni annulées, ni brouillon) ;
    ``prochaine_echeance`` = la date d'échéance la plus proche parmi elles
    (``None`` si aucune échéance renseignée). Lecture seule."""
    from .models import Devis, Facture

    vide = {
        'devis_en_attente': 0,
        'factures_impayees': 0,
        'prochaine_echeance': None,
    }
    if company is None or not client_id:
        return vide

    # ADOC125 — is_active=True : périmètre EXACT de « Mes devis » (QJR520) ;
    # une version remplacée par une révision ne compte plus.
    devis_en_attente = Devis.objects.filter(
        company=company, client_id=client_id, is_active=True,
        statut=Devis.Statut.ENVOYE).count()

    factures_impayees_qs = Facture.objects.filter(
        company=company, client_id=client_id,
        statut__in=(Facture.Statut.EMISE, Facture.Statut.EN_RETARD))
    prochaine_echeance = (
        factures_impayees_qs
        .exclude(date_echeance__isnull=True)
        .order_by('date_echeance')
        .values_list('date_echeance', flat=True)
        .first())

    return {
        'devis_en_attente': devis_en_attente,
        'factures_impayees': factures_impayees_qs.count(),
        # Chaîne ISO, jamais un objet date : la valeur part telle quelle dans
        # la réponse JSON du tableau de bord portail (contrat
        # apps/portail/contract_samples/client_tableau_de_bord.json).
        'prochaine_echeance': (
            prochaine_echeance.isoformat() if prochaine_echeance else None),
    }
