"""ACAL667 — les valeurs ATTENDUES par chaîne d'une fiche de recette.

Module frère de ``selectors.py`` (fichier-mur) : le chantier ne porte aucun
champ calepinage, il se BRANCHE sur le sélecteur du calepinage retenu de son
devis (import fonction-local, frontière inter-apps). Lecture pure. Forme :
``contract_samples/recette_valeurs_attendues.json`` (ACAL666).
"""

MOTIF_SANS_CALEPINAGE = ('aucun calepinage retenu pour le devis de ce chantier : '
                         'les valeurs attendues ne sont pas calculées')
MOTIF_SANS_VALEURS = ('aucune chaîne publiée ou fiche du module incomplète (Voc, Isc, '
                      'Pmax) sur le calepinage retenu : les valeurs attendues ne sont '
                      'pas calculées')


def valeurs_attendues_du_chantier(installation, *, temperature_c=None,
                                  eclairement_w_m2=None):
    """``{installation, chaines, temperature_c, eclairement_w_m2[, motif]}``."""
    from apps.calepinage.selectors import calepinage_retenu_pour_devis
    from apps.calepinage.selectors_chantier import valeurs_attendues_par_chaine

    reponse = {'installation': installation.pk, 'chaines': [],
               'temperature_c': None, 'eclairement_w_m2': None}
    bloc = (calepinage_retenu_pour_devis(installation.devis_id, installation.company)
            if installation.devis_id else None)
    if bloc is None:
        return {**reponse, 'motif': MOTIF_SANS_CALEPINAGE}
    lignes = valeurs_attendues_par_chaine(
        installation.devis_id, installation.company,
        temperature_c=temperature_c, eclairement_w_m2=eclairement_w_m2)
    if not lignes:
        return {**reponse, 'motif': MOTIF_SANS_VALEURS}
    from apps.calepinage.services.valeurs_attendues import (
        ECLAIREMENT_STC_W_M2, TEMPERATURE_STC_C,
    )

    corrigee = lignes[0]['corrigee']
    reponse['temperature_c'] = float(temperature_c) if corrigee else TEMPERATURE_STC_C
    reponse['eclairement_w_m2'] = float(eclairement_w_m2) if corrigee else ECLAIREMENT_STC_W_M2
    for ligne in lignes:
        repere = 'CH%s' % ligne['chaine']
        reponse['chaines'].append({
            'chaine': repere, 'modules': ligne['modules'],
            'voc_attendu_v': ligne['voc_v' if corrigee else 'voc_stc_v'],
            'isc_attendu_a': ligne['isc_a' if corrigee else 'isc_stc_a'],
            'pmax_attendu_w': ligne['pmax_w' if corrigee else 'pmax_stc_w'],
            'sources': ligne['sources'] + ['calepinage retenu #%s : chaîne %s de %d modules'
                                           % (bloc['id'], repere, ligne['modules'])],
            'corrigee': corrigee,
            'isc_corrige_motif': ligne.get('isc_corrige_motif'),
        })
    return reponse
