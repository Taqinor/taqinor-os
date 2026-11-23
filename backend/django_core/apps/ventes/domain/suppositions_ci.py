"""Ce que le calcul C&I a dû SUPPOSER est DIT à la commerciale.

Règle fondateur du 17/11/2026 (lead « CPE Go Plus ») : toute information
dont le calculateur de devis se sert et qu'il n'a pas trouvée sur la fiche
est annoncée à l'utilisateur — avec le CHAMP DE LA FICHE qui la lève. Ce
jour-là, six batteries de 16 kWh sortaient d'une consommation de nuit
supposée, sans qu'aucun écran ne nomme la question restée vide.

Il porte aussi LA règle des entrées que le calcul C&I suppose quand la fiche
les laisse vides (décisions du fondateur du 23/11/2026, :func:`supposer_entrees`)
— lue par le moteur ET par la fiche lead (``ventes.selectors.champs_supposes_ci``),
jamais recopiée. Pour le reste, il relit les ``alertes`` et les ``hypotheses`` de
l'étude pour l'AFFICHAGE (aperçu du générateur, journal du devis automatique) :

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
    'contrat_electricite': ('contrat_electricite', (
        "Contrat d'électricité non déclaré : tarif basse tension ({libelle}) supposé, devis "
        'en estimation. Demandez au client son contrat : il est écrit sur sa facture.')),
    'phases': ('raccordement', (
        'Phase du site non déclarée : triphasé supposé, les onduleurs en dépendent. '
        'Demandez au client s’il est en monophasé ou en triphasé : c’est écrit sur sa '
        'facture ou sur son compteur.')),
}

#: ADEV125 (D-ACAL-92, fondateur 23/11/2026) — contrat d'électricité non déclaré
#: (« ne sait pas » compris) hors moyenne tension DÉCLARÉE : le tarif basse tension
#: de la famille est supposé (patenté pour un commerce, force motrice pour une
#: usine), dit avec le champ de la fiche, devis marqué estimation.
CONTRAT_BT_SUPPOSE = {'commercial': 'bt_patente', 'industriel': 'bt_force_motrice'}
LIBELLES_SUPPOSES = {'bt_patente': 'BT patenté', 'bt_force_motrice': 'BT force motrice'}
#: ADEV126 (D-ACAL-93, fondateur 23/11/2026) — phase non déclarée (vide ou « je
#: ne sais pas ») : triphasé supposé pour tout commercial et industriel, dit.
PHASE_SUPPOSEE = 'tri'
PHASES_DECLAREES = ('mono', 'tri')
#: Origine d'une entrée supposée (vocabulaire du contrat ``etude_ci_preview.json``).
ORIGINE_SUPPOSEE = 'estimation'


def _provenance_supposee(champ):
    return {'origine': ORIGINE_SUPPOSEE, 'detail': champ, 'date': None}


def champs_supposes(mode, tension):
    """Les champs du LEAD que le calcul C&I suppose quand ils sont vides —
    ``tension`` : celle déclarée (``'mt'`` = aucun contrat à supposer)."""
    if mode not in CONTRAT_BT_SUPPOSE:
        return ()
    return (() if tension == 'mt' else ('contrat_electricite',)) + ('raccordement',)


def supposer_entrees(res, mode, regles=None):
    """Pose dans la résolution ``res`` (``etude_ci._Resolution``) les valeurs
    supposées des entrées vides, provenance ``estimation`` (jamais figées au
    devis : le rafraîchisseur les re-suppose tant que la fiche est muette) ;
    rend les hypothèses ``estimation`` qui les disent."""
    from apps.ventes import tarif_ci

    hypotheses = []
    tension = res.valeur('tension')
    if 'contrat_electricite' in champs_supposes(mode, tension):
        declare = res.valeur('tarif_declare')
        tarif = tarif_ci.tarif_applicable(declare, tension=tension, **(regles or {}))
        if tarif.get('origine') == tarif_ci.ORIGINE_OMIS and not tarif.get('contrat'):
            contrat = CONTRAT_BT_SUPPOSE[mode]
            res.poser('tarif_declare', dict(declare if isinstance(declare, dict) else {},
                                            contrat=contrat),
                      _provenance_supposee('contrat_electricite'))
            hypotheses.append({'cle': 'contrat_electricite', 'valeur': contrat,
                               'statut': 'estimation',
                               'source': 'contrat non déclaré : tarif basse tension supposé '
                                         '(décision fondateur du 23/11/2026)'})
    if 'raccordement' in champs_supposes(mode, tension) and res.valeur('phases') not in PHASES_DECLAREES:
        res.poser('phases', PHASE_SUPPOSEE, _provenance_supposee('raccordement'))
        hypotheses.append({'cle': 'phases', 'valeur': PHASE_SUPPOSEE, 'statut': 'estimation',
                           'source': 'phase non déclarée : triphasé supposé (décision fondateur '
                                     'du 23/11/2026)'})
    return hypotheses


def est_supposee(entree):
    """Vrai si l'entrée résolue ``{valeur, provenance}`` a été supposée."""
    return ((entree or {}).get('provenance') or {}).get('origine') == ORIGINE_SUPPOSEE


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
        # Clé TOUJOURS servie (contrat ``etude_ci_preview.json`` : mêmes clés sur
        # chaque alerte) ; ``None`` = aucun champ de la fiche ne la lève.
        alerte['champ_lead'] = champ
        if champ:
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
                                      origine=_origine(hypothese.get('source')),
                                      libelle=LIBELLES_SUPPOSES.get(hypothese.get('valeur'), ''))})
    return alertes
