"""Ce que le calcul C&I a dû SUPPOSER est DIT à la commerciale.

Règle fondateur du 17/11/2026 (lead « CPE Go Plus ») : toute information
dont le calculateur de devis se sert et qu'il n'a pas trouvée sur la fiche
est annoncée à l'utilisateur — avec le CHAMP DE LA FICHE qui la lève. Ce
jour-là, six batteries de 16 kWh sortaient d'une consommation de nuit
supposée, sans qu'aucun écran ne nomme la question restée vide.

Il porte aussi LA règle des entrées que le calcul C&I suppose quand la fiche
les laisse vides (décisions du fondateur du 23/11/2026, :func:`supposer_entrees`)
— lue par le moteur ET par la fiche lead (``ventes.services.champs_supposes_ci``),
jamais recopiée. Pour le reste, il relit les ``alertes`` et les ``hypotheses`` de
l'étude pour l'AFFICHAGE (aperçu du générateur, journal du devis automatique) :

* une alerte qui tient à une réponse manquante de la fiche reçoit
  ``champ_lead`` (la colonne du lead) et, quand son texte parlait le jargon
  du moteur (« talon », « borne »), une consigne lisible ;
* une hypothèse au statut ``estimation`` que nulle alerte ne signalait
  (consommation tirée d'une facture en dirhams, inclinaison, orientation)
  devient une ligne « Vendeur seulement » — jamais montrée au client.
"""

from apps.ventes.moteur_ci.production import METHODE_JOURNEES_MOYENNES

#: Code d'alerte → colonne du lead qui lève la supposition.
CHAMP_LEAD_PAR_CODE = {
    'talon_non_declare': 'equipements_hors_horaires',
    'talon_estime': 'equipements_hors_horaires',
    'OPTION_BATTERIE_TALON_INCONNU': 'equipements_hors_horaires',
    'puissance_souscrite_inconnue': 'compteur_puissance_kva',
    'profil_estime': 'jours_ouverture',
    'jours_ouverts_non_declares': 'jours_ouverture',
    'jours_ouverts_supposes': 'jours_ouverture',  # ADEV127 (D-ACAL-94)
    'heure_debut_supposee': 'heure_debut',  # D-ACAL-94 « regime_suffit »
    'horaires_a_demander': 'heure_debut',
    'heures_jour_a_preciser': 'heure_debut',
    'contenance_toit_inconnue': 'surface_toiture_m2',
    'tarif_omis': 'contrat_electricite',
    'conversion_mad_impossible': 'contrat_electricite',
    'consommation_absente': 'conso_mensuelle_kwh',
    # Fondateur 24/11/2026 — consommation estimée par la puissance maximale :
    # ce sont les kWh (ou les factures) de la fiche qui la remplacent.
    'consommation_estimee_puissance': 'conso_mensuelle_kwh',
    'estimation_puissance_sans_jours': 'jours_ouverture',
    'estimation_puissance_sans_heures': 'heure_debut',
    'facture_ete_non_lue': 'facture_ete',  # ACAL1227
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
    'tension': ('tension_raccordement', (
        'Tension de raccordement non déclarée : basse tension supposée, devis en estimation. '
        'Demandez au client s’il est en basse ou en moyenne tension : c’est écrit sur sa facture.')),
    'phases': ('raccordement', (
        'Phase du site non déclarée : triphasé supposé, les onduleurs en dépendent. '
        'Demandez au client s’il est en monophasé ou en triphasé : c’est écrit sur sa '
        'facture ou sur son compteur.')),
}

#: ADEV124 — sur le repli sans série horaire, inclinaison et orientation sont
#: levées par le point GPS du chantier (une seule ligne, dédoublonnée par champ).
_MESSAGE_REPLI = ('Inclinaison et orientation supposées à 30° plein sud : sans point GPS du '
                  'chantier, la production suit 12 journées moyennes. Posez le point GPS pour '
                  'la calculer heure par heure.')
HYPOTHESES_REPLI = {'inclinaison_deg': ('gps_lat', _MESSAGE_REPLI),
                    'azimut_deg': ('gps_lat', _MESSAGE_REPLI)}
#: ADEV124 — alertes de niveau ``info`` gardées au journal : le profil horaire
#: estimé (archétype de l'activité) change la taille et l'autoconsommation.
CODES_INFO_DITS = frozenset({'profil_estime'})

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
#: D-ACAL-92 — tensions DÉCLARÉES (``entrees_ci_du_lead`` sert « inconnue »
#: pour « ne sait pas » et le défaut du site jamais touché).
TENSIONS_DECLAREES = ('bt', 'mt')
#: D-ACAL-94 (réponse du fondateur du 23/11/2026 : « regime_suffit ») — régime
#: 1×8 / 2×8 déclaré SANS heure de début : l'heure de la première équipe est
#: supposée (une équipe de jour 8 h-16 h ; deux équipes 6 h-22 h), dite avec le
#: champ ``heure_debut`` de la fiche, en estimation. Une heure DÉCLARÉE prime.
HEURE_DEBUT_SUPPOSEE = {'1x8': 8, '2x8': 6}
SOURCE_HEURE_DEBUT_SUPPOSEE = 'décision fondateur du 23/11/2026 (D-ACAL-94)'
MESSAGE_HEURE_DEBUT_SUPPOSEE = (
    "Heure de début d'équipe non déclarée : {heure} h supposée (régime {regime}, estimation, "
    + SOURCE_HEURE_DEBUT_SUPPOSEE + "). Demandez au client l'heure de début de sa première équipe.")
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


def _tension_supposee(res, mode, tension):
    """D-ACAL-92 (« supposer_bt », 23/11/2026, lead commercial ou industriel) —
    tension non déclarée (vide, « ne sait pas », défaut du site) sous un tarif
    basse tension (déclaré ou supposé) : la basse tension est SUPPOSÉE, dite
    avec le champ ``tension_raccordement`` (jamais posée dans ``res`` : aucun
    chiffre de composition ne bouge)."""
    tarif = res.valeur('tarif_declare')
    contrat = tarif.get('contrat') if isinstance(tarif, dict) else None
    if mode not in CONTRAT_BT_SUPPOSE or tension in TENSIONS_DECLAREES or not str(contrat or '').startswith('bt_'):
        return []
    return [{'cle': 'tension', 'valeur': 'bt', 'statut': 'estimation',
             'source': 'tension non déclarée : basse tension supposée (décision fondateur du '
                       '23/11/2026, D-ACAL-92)'}]


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
    hypotheses.extend(_tension_supposee(res, mode, tension))
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
    ('puissance maximale', ' à partir de la puissance maximale'),
)


def _origine(source):
    return next((texte for debut, texte in ORIGINES_CONSOMMATION
                 if str(source or '').startswith(debut)), '')


def _nombre(valeur):
    try:
        return '%g' % float(valeur)
    except (TypeError, ValueError):
        return '?'


MESSAGE_FACTURE_ETE_NON_LUE = ("Facture d'été non prise en compte : la consommation répète "
                               "la facture d'hiver sur 12 mois")


def alerte_facture_ete_non_lue(lead, feuille_retenue):
    """ACAL1227 (règle du 17/11) — été déclaré différent, mais la consommation
    C&I répète la facture d'hiver (``facture_hiver_mad``) : DIT, aucun chiffre ne bouge."""
    ete = getattr(lead, 'facture_ete', None)
    if feuille_retenue != 'facture_hiver_mad' or not getattr(lead, 'ete_differente', False) \
            or ete in (None, '') or float(ete) <= 0:
        return []
    return [{'code': 'facture_ete_non_lue', 'champ': 'consommation.facture_mad',
             'message': MESSAGE_FACTURE_ETE_NON_LUE, 'niveau': 'alerte', 'interne': True}]


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
    hypotheses = etude.get('hypotheses') or []
    # ADEV124 — sur le repli (12 journées moyennes à 30° plein sud), c'est le
    # point GPS qui lève la supposition d'inclinaison et d'orientation.
    repli = any(h.get('cle') == 'methode_autoconsommation' and h.get('valeur') == METHODE_JOURNEES_MOYENNES
                for h in hypotheses if isinstance(h, dict))
    for hypothese in hypotheses:
        regle = ((HYPOTHESES_REPLI if repli else {}).get(hypothese.get('cle'))
                 or HYPOTHESES_ESTIMEES.get(hypothese.get('cle')))
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


def alertes_du_journal(etude):
    """ADEV124 — les alertes du JOURNAL du devis automatique : celles de
    :func:`alertes_pour_la_commerciale` de niveau alerte / bloquant, plus les
    suppositions de niveau ``info`` qui changent un chiffre (``CODES_INFO_DITS``)."""
    return [a for a in alertes_pour_la_commerciale(etude)
            if a.get('niveau') in ('alerte', 'bloquant') or a.get('code') in CODES_INFO_DITS]
