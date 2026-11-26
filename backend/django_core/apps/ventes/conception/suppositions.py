"""ADEV134 — les suppositions du moteur unique, chacune avec le champ de la fiche.

Déplacées de ``conception/moteur.py`` à la relecture (budget du module), sans
changement de comportement hors des points de relecture (valeur mensuelle, plan
de production, froid supposé).
"""

from core.pompage.kit import CODE_CABLE_DC_NON_CHIFFRE

CODE_FROID_SUPPOSE = 'froid_suppose'
#: D-ACAL-156 — alertes qui nomment un champ du lead SANS rien supposer (un
#: poste non chiffré, faute de la donnée) : jamais rangées parmi les suppositions.
CODES_MANQUE_SANS_SUPPOSITION = (CODE_CABLE_DC_NON_CHIFFRE,)


def suppositions_de(resultat, *, froid=None):
    """ADEV134 (règle du 17/11/2026) — ce que le calcul a SUPPOSÉ :
    ``[{code, champ, valeur, source, message}]``. Ce sont les suppositions que
    le devis automatique dit déjà au vendeur, avec leur champ de la fiche
    (résidentiel : ``creation_auto_residentiel.SUPPOSITIONS_RESIDENTIEL`` ;
    C&I : ``suppositions_ci.alertes_du_journal``) — mêmes codes, mêmes phrases,
    aucune seconde formulation ; ``valeur`` = ce que le calcul a retenu à la
    place, lu sur ses blocs ou ses constantes. Une alerte qui ne nomme aucun
    champ n'en est pas une (le journal la garde). Le froid du site supposé
    (−5 °C, ``froid`` sans source) sort avec la phrase de la règle D-ACAL-80.
    Les quatre pertes D-ACAL-82 n'en sont pas : au niveau de règles courant,
    sans toit tracé, le calcul ne les applique pas (elles viennent avec la
    simulation de la pose, ADEV149) — rien n'est donc supposé ni dit ici."""
    dites = [{'code': alerte['code'], 'champ': alerte['champ_lead'], 'valeur': _valeur_supposee(resultat, alerte),
              'source': 'defaut', 'message': _message(resultat, alerte)}
             for alerte in resultat.journal.get('alertes') or [] if alerte.get('champ_lead')
             and alerte.get('code') not in CODES_MANQUE_SANS_SUPPOSITION]
    if froid is not None and froid.source is None and not any('froid' in sup['code'] for sup in dites):
        dites.append({'code': CODE_FROID_SUPPOSE, 'champ': 'gps_lat', 'valeur': froid.valeur_c,
                      'source': 'defaut', 'message': froid.detail})
    return dites


def _message(resultat, alerte):
    """La phrase du journal ; relecture E5 (b) — une facture d'été SAISIE sans « Été
    différent » : la phrase dit de cocher la case (la renseigner ne servirait à rien)."""
    ete = (resultat.entrees_utilisees.get('facture_ete') or {}).get('valeur')
    if alerte['champ_lead'] != 'facture_ete' or not isinstance(ete, (int, float)) or ete <= 0:
        return alerte['message']
    montant = ('%d' % ete) if float(ete).is_integer() else ('%s' % ete).replace('.', ',')
    return ("Facture d'été saisie (%s MAD) mais non prise en compte : cochez « Été différent » sur la fiche "
            "pour qu'elle compte (sinon l'été est supposé égal à l'hiver)." % montant)


def _valeur_supposee(resultat, alerte):
    params = resultat.etude_params
    if resultat.marche == 'residentiel':
        from apps.parametres.pvgis_profils import PVGIS_ANGLE_DEG, PVGIS_ASPECT_DEG
        bloc = params.get('etude_horaire') or {}
        mensuelles = [m.get('consommation_kwh') for m in bloc.get('mois') or []]
        return {'occupation_jour': bloc.get('occupation'),
                'facture_ete': (resultat.entrees_utilisees.get('facture_hiver') or {}).get('valeur'),
                # La consommation MENSUELLE retenue (une valeur si les 12 mois sont égaux).
                'conso_mensuelle_kwh': mensuelles[0] if len(set(mensuelles)) == 1 else (mensuelles or None),
                # Le plan de la production par ville (``pvgis_profils``, 0 = plein sud).
                'inclinaison_deg': {'inclinaison_deg': PVGIS_ANGLE_DEG, 'azimut_deg': PVGIS_ASPECT_DEG},
                }.get(alerte['champ_lead'])
    etude = params.get('etude_ci') or {}
    hypothese = next((h for h in etude.get('hypotheses') or [] if isinstance(h, dict)
                      and 'supposition_%s' % h.get('cle') == alerte['code']), None)
    if hypothese is not None:
        return hypothese.get('valeur')
    if alerte['champ_lead'] == 'jours_ouverture':  # profil estimé : l'archétype retenu
        return (etude.get('profil_charge') or {}).get('archetype')
    return ((etude.get('entrees_resolues') or {}).get(alerte.get('champ')) or {}).get('valeur')
