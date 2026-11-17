"""Ce que le calcul C&I a dû SUPPOSER est DIT à la commerciale.

Règle fondateur du 17/11/2026 (lead « CPE Go Plus ») : toute information
dont le calculateur de devis se sert et qu'il n'a pas trouvée sur la fiche
est annoncée à l'utilisateur — avec le CHAMP DE LA FICHE qui la lève. Ce
jour-là, six batteries de 16 kWh sortaient d'une consommation de nuit
supposée, sans qu'aucun écran ne nomme la question restée vide.

Ce module ne calcule rien et ne touche pas à l'étude : il relit ses
``alertes`` et ses ``hypotheses`` pour l'AFFICHAGE (aperçu du générateur,
journal du devis automatique) :

* une alerte qui tient à une réponse manquante de la fiche reçoit
  ``champ_lead`` (la colonne du lead) et, quand son texte parlait le jargon
  du moteur (« talon », « borne »), une consigne lisible ;
* une hypothèse au statut ``estimation`` que nulle alerte ne signalait
  (consommation tirée d'une facture en dirhams, inclinaison, orientation)
  devient une ligne « Vendeur seulement » — jamais montrée au client.
"""

#: Code d'alerte → colonne du lead qui lève la supposition.
CHAMP_LEAD_PAR_CODE = {
    'talon_non_declare': 'equipements_hors_horaires',
    'talon_estime': 'equipements_hors_horaires',
    'OPTION_BATTERIE_TALON_INCONNU': 'equipements_hors_horaires',
    'puissance_souscrite_inconnue': 'compteur_puissance_kva',
    'profil_estime': 'jours_ouverture',
    'jours_ouverts_non_declares': 'jours_ouverture',
    'horaires_a_demander': 'heure_debut',
    'heures_jour_a_preciser': 'heure_debut',
    'contenance_toit_inconnue': 'surface_toiture_m2',
    'tarif_omis': 'contrat_electricite',
    'conversion_mad_impossible': 'contrat_electricite',
    'consommation_absente': 'conso_mensuelle_kwh',
}

#: Consigne lisible quand le texte du moteur parlait son jargon.
MESSAGES_PAR_CODE = {
    'talon_non_declare': (
        'Consommation de nuit inconnue : le calcul prend l’hypothèse la plus prudente '
        'pour les panneaux (souvent une consommation étalée sur 24 h). Demandez au '
        'client si des équipements tournent la nuit ou quand le site est fermé.'),
    'puissance_souscrite_inconnue': (
        'Puissance souscrite inconnue : rien ne vérifie que les onduleurs tiennent sous '
        'le contrat du client. Elle est écrite sur sa facture (en kVA).'),
}

#: Hypothèse ``estimation`` → ``(colonne du lead, gabarit du message)``.
HYPOTHESES_ESTIMEES = {
    'consommation': ('conso_mensuelle_kwh', (
        'Consommation estimée{origine} : demandez au client les kWh écrits sur ses '
        'factures pour un chiffre exact.')),
    'inclinaison_deg': ('inclinaison_deg', (
        'Inclinaison des panneaux supposée à {valeur}° : à confirmer avec le client ou '
        'à la visite.')),
    'azimut_deg': ('orientation', (
        'Orientation des panneaux supposée (plein sud par défaut) : à confirmer avec '
        'le client ou à la visite.')),
}


#: Début de la ``source`` d'une consommation estimée → ce que la commerciale lit.
ORIGINES_CONSOMMATION = (
    ('factures MAD', ' à partir de la facture en dirhams'),
    ('relevé partiel', " à partir d'un relevé incomplet"),
)


def _origine(source):
    return next((texte for debut, texte in ORIGINES_CONSOMMATION
                 if str(source or '').startswith(debut)), '')


def _nombre(valeur):
    try:
        return '%g' % float(valeur)
    except (TypeError, ValueError):
        return '?'


def alertes_pour_la_commerciale(etude):
    """Les alertes de ``etude`` (copies, ordre gardé) où chaque supposition
    porte ``champ_lead``, suivies des hypothèses estimées qu'aucune alerte ne
    signalait. L'étude reçue n'est jamais modifiée."""
    etude = etude or {}
    alertes, champs_dits = [], set()
    for alerte in etude.get('alertes') or []:
        alerte = dict(alerte)
        champ = CHAMP_LEAD_PAR_CODE.get(alerte.get('code'))
        if champ:
            alerte['champ_lead'] = champ
            alerte['message'] = MESSAGES_PAR_CODE.get(alerte.get('code'), alerte.get('message'))
            champs_dits.add(champ)
        alertes.append(alerte)
    for hypothese in etude.get('hypotheses') or []:
        regle = HYPOTHESES_ESTIMEES.get(hypothese.get('cle'))
        if regle is None or hypothese.get('statut') != 'estimation' or regle[0] in champs_dits:
            continue
        champ, gabarit = regle
        champs_dits.add(champ)
        alertes.append({
            'code': 'supposition_%s' % hypothese['cle'], 'champ': hypothese['cle'],
            'champ_lead': champ, 'niveau': 'alerte', 'interne': True,
            'message': gabarit.format(valeur=_nombre(hypothese.get('valeur')),
                                      origine=_origine(hypothese.get('source')))})
    return alertes
