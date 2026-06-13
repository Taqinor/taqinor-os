"""
Gating « devis automatique » — source de vérité UNIQUE côté serveur.

Selon le mode du lead (type_installation), certaines entrées sont requises
avant de pouvoir lancer le générateur de devis automatique :

  - Résidentiel (ou non renseigné) : facture hiver ; facture été UNIQUEMENT
    si le toggle « été différent » est actif (sinon la facture hiver vaut
    pour toute l'année) ;
  - Industriel / Commercial : consommation mensuelle (kWh) ;
  - Agricole (pompage) : puissance pompe (CV), HMT (m), débit souhaité (m³/h).

La même liste alimente le champ sérialisé `devis_auto` (UI) et l'endpoint
POST /crm/leads/<id>/devis-auto/ (règle serveur) — jamais deux logiques.
"""

# Modes regroupés (clés de Lead.TypeInstallation — scalaires, jamais une
# liste d'étapes du pipeline, qui vit dans STAGES.py).
_MODES_ETUDE = ('commercial', 'industriel')
_MODE_AGRICOLE = 'agricole'


def champs_manquants(lead) -> list[str]:
    """Champs requis manquants pour un devis automatique, selon le mode du lead."""
    mode = lead.type_installation or 'residentiel'
    manquants = []

    if mode == _MODE_AGRICOLE:
        if not lead.pompe_cv:
            manquants.append('pompe (CV)')
        if not lead.pompe_hmt_m:
            manquants.append('HMT')
        if not lead.pompe_debit_m3h:
            manquants.append('débit souhaité')
    elif mode in _MODES_ETUDE:
        if not lead.conso_mensuelle_kwh:
            manquants.append('consommation mensuelle (kWh)')
    else:
        # Résidentiel — comportement simulateur : la facture été n'est
        # requise QUE si elle diffère de l'hiver (toggle existant).
        if not lead.facture_hiver:
            manquants.append('facture hiver')
        if lead.ete_differente and not lead.facture_ete:
            manquants.append('facture été')

    return manquants


def message_manquants(manquants):
    return 'Manque : ' + ', '.join(manquants)
