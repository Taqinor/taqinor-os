"""Provenances des valeurs de pompage saisies sur la fiche lead (AGR400).

Une valeur de pompage SAISIE dans l'ERP porte sa provenance, posée ici par le
sérialiseur du lead (``LeadSerializer._poser_provenances_pompage``). Une valeur
effacée efface sa provenance ; une valeur inchangée ne touche à rien.

T4-U3-002 — la fiche propose l'origine en liste (la question de l'appel :
« essai, foreur ou votre estimation ? ») : une origine CHOISIE est gardée ;
« Mesuré en visite » et « Saisi sur le site » sont posées par leur propre
chemin (validation du relevé de visite, questionnaire du site) et sont
REFUSÉES en 409 qui le dit — jamais remplacées en silence par l'origine
déclarée. Sorti de ``serializers.py`` (fichier-mur, règle C20).
"""
from core.conflit_etat import ConflitEtat

#: (valeur, colonne de provenance, origine posée quand la valeur change).
PROVENANCES_POMPAGE_SAISIE = (
    ('niveau_statique_m', 'niveau_statique_source', 'declare'),
    ('debit_forage_m3h', 'debit_forage_source', 'client'),
    ('besoin_eau_m3j', 'besoin_eau_source', 'client'),
    ('pompe_hmt_m', 'pompe_hmt_source', 'declaree'),
)

#: Les origines que la question de l'appel fait choisir sur la fiche.
PROVENANCES_POMPAGE_CHOISISSABLES = {
    'niveau_statique_source': ('declare',),
    'debit_forage_source': ('essai', 'foreur', 'client'),
    'besoin_eau_source': ('client', 'pompe_actuelle'),
    'pompe_hmt_source': ('declaree',),
}

#: Les origines posées par un autre chemin, et ce qu'il faut faire.
PROVENANCES_POMPAGE_RESERVEES = {
    'mesure_visite': (
        "« Mesuré en visite » ne se choisit pas sur la fiche : il se pose "
        "seul quand le technicien valide le relevé du point d'eau de la "
        "visite technique. Planifiez la visite depuis la fiche, ou "
        "choisissez ici l'origine que le client a donnée."),
    'site_web': (
        "« Saisi sur le site » ne se choisit pas sur la fiche : il se pose "
        "seul quand le client remplit le questionnaire du site. "
        "Choisissez ici l'origine que le client a donnée."),
}


def _refuser_provenance(instance, attrs, valeur, source, choisie):
    """409 quand l'origine choisie ne peut pas être posée depuis la fiche."""
    motif = PROVENANCES_POMPAGE_RESERVEES.get(choisie)
    if motif is None and choisie not in PROVENANCES_POMPAGE_CHOISISSABLES[source]:
        motif = "Cette origine n'est pas proposée pour ce champ."
    if motif:
        raise ConflitEtat({source: [motif]})
    finale = attrs[valeur] if valeur in attrs else getattr(instance, valeur, None)
    if finale is None:
        from .models import Lead
        libelle = Lead._meta.get_field(valeur).verbose_name
        raise ConflitEtat({source: [
            f"Saisissez d'abord « {libelle} », puis son origine."]})


def poser_provenances_pompage(instance, attrs):
    """Pose (ou refuse) les provenances pompage et la date du prix carburant
    dans ``attrs`` (données validées du sérialiseur ; ``instance`` = le lead
    enregistré, ``None`` à la création)."""

    def _avant(champ):
        return getattr(instance, champ, None) if instance else None

    def _change(champ):
        return champ in attrs and (
            instance is None or getattr(instance, champ) != attrs[champ])

    for valeur, source, origine in PROVENANCES_POMPAGE_SAISIE:
        choisie = attrs.get(source) or None
        if source in attrs and choisie != _avant(source):
            # Origine CHOISIE sur la fiche (elle diffère de l'enregistrée).
            if choisie is not None:
                _refuser_provenance(instance, attrs, valeur, source, choisie)
            attrs[source] = choisie
        elif _change(valeur):
            attrs[source] = origine if attrs[valeur] is not None else None
        else:
            # Renvoyée telle quelle : rien ne change.
            attrs.pop(source, None)
    # Q17 — le prix du carburant est DÉCLARÉ et DATÉ : la date est celle du
    # jour où le prix change, posée par le serveur.
    if _change('carburant_prix_unitaire_mad'):
        from core.dates import aujourd_hui_local
        attrs['carburant_prix_declare_le'] = (
            aujourd_hui_local()
            if attrs['carburant_prix_unitaire_mad'] is not None else None)
