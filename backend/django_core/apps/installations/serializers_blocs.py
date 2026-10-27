"""APRF37 — blocs de DÉTAIL de ``InstallationSerializer``, servis ``null`` en liste.

``regime_suggere``, ``calepinage`` et ``dossier_8221_resume`` coûtent des
requêtes PAR chantier (nomenclature → produit → fiche technique, calepinage,
devis, dossier réglementaire : sonde V_VB, ~26 requêtes par chantier). Quand le
sérialiseur est l'enfant d'un ``ListSerializer`` (``many=True`` : liste de
chantiers), ``serializer.parent`` n'est pas ``None`` et les trois blocs valent
``None`` ; le DÉTAIL (``retrieve``, réponses d'écriture d'un chantier) les sert
inchangés. Le panneau ``InstallationDetail`` relit le détail à son ouverture.

Fichier frère de ``serializers.py`` (mur ≥ 2 000 lignes : il ne grossit pas).
"""


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
