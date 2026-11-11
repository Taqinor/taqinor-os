"""APRF37 — blocs de DÉTAIL de ``InstallationSerializer``, servis ``null`` en liste.

``regime_suggere``, ``calepinage`` et ``dossier_8221_resume`` coûtent des
requêtes PAR chantier (nomenclature → produit → fiche technique, calepinage,
devis, dossier réglementaire : sonde V_VB, ~26 requêtes par chantier). Quand le
sérialiseur est l'enfant d'un ``ListSerializer`` (``many=True`` : liste de
chantiers), ``serializer.parent`` n'est pas ``None`` et les trois blocs valent
``None`` ; le DÉTAIL (``retrieve``, réponses d'écriture d'un chantier) les sert
inchangés. Le panneau ``InstallationDetail`` relit le détail à son ouverture.

APFS29 — en fin de fichier : mixins de masquage des montants d'achat (``champs_montants_achat``
retirés sans ``prix_achat_voir``, cf. ``apps.stock.permissions``).

Fichier frère de ``serializers.py`` (mur ≥ 2 000 lignes : il ne grossit pas).
"""


from apps.stock.permissions import MasqueMontantsAchatMixin


def bloc_regime_suggere(serializer, obj):
    """CIQ613 — noyau sourcé : kWc DC, kW AC des onduleurs (nomenclature gelée),
    niveau de tension, hors réseau ; C&I inconnu → à qualifier."""
    if serializer.parent is not None:
        return None
    from .models import Installation
    from .regime import suggest_for_installation
    code = suggest_for_installation(obj)
    return {'code': code,
            'label': dict(Installation.Regime8221.choices).get(code, code)}


def bloc_calepinage(serializer, obj):
    """CAL245 — sélecteur (frontière inter-apps), jamais ``calepinage.models``."""
    if serializer.parent is not None:
        return None
    from .selectors import calepinage_retenu_du_chantier
    return calepinage_retenu_du_chantier(obj)


def bloc_dossier_8221_resume(serializer, obj):
    if serializer.parent is not None:
        return None
    from .services import resume_dossier_8221
    return resume_dossier_8221(obj)


def bloc_avertissements_cloture(serializer, obj):
    """G14 (revue chantier 26/10/2026) — phrases consultatives à lire avant de
    clôturer. DÉTAIL d'un chantier RÉCEPTIONNÉ seulement : ``None`` en liste
    (``serializer.parent``) et pour tout autre statut, pour que la liste ne
    paie jamais ce calcul (factures, parc, pack)."""
    if serializer.parent is not None:
        return None
    from .models import Installation
    if (Installation.canonical_statut(obj.statut)
            != Installation.Statut.RECEPTIONNE):
        return None
    from .services import avertissements_cloture
    return avertissements_cloture(obj)


class MasqueBudgetProjet(MasqueMontantsAchatMixin):
    champs_montants_achat = ('budget_materiel', 'budget_main_oeuvre', 'budget_sous_traitance',
                             'budget_divers', 'budget_total', 'tarif_jour_mo')


class MasquePrixNegocie(MasqueMontantsAchatMixin):
    champs_montants_achat = ('prix_negocie',)


class MasqueMontant(MasqueMontantsAchatMixin):
    champs_montants_achat = ('montant',)


class MasqueLandedCost(MasqueMontantsAchatMixin):
    champs_montants_achat = ('valeur_fob', 'cout_fob_unitaire')


class MasquePrixConvenu(MasqueMontantsAchatMixin):
    champs_montants_achat = ('prix_convenu', 'remise_pct')


class MasqueCoutPrevu(MasqueMontantsAchatMixin):
    champs_montants_achat = ('cout_prevu',)


class MasqueCoutTransport(MasqueMontantsAchatMixin):
    champs_montants_achat = ('cout_transport',)


class MasqueMontantApprouve(MasqueMontantsAchatMixin):
    """ALEC8 — montant d'achat HT du BCF figé à l'approbation (masqué comme le BCF, ASTK10)."""
    champs_montants_achat = ('montant_approuve',)
