"""Le devis automatique AGRICOLE (déplacé tel quel de ``creation_auto.py``).

Le dispatcher ``build_devis_auto`` reste dans ``creation_auto.py``.
NOM DU LOGGER FIGÉ sur ``apps.ventes.services``.
"""
from decimal import Decimal
import logging


logger = logging.getLogger("apps.ventes.services")


#: AGR124 — refus D-AGR-4 : le relevé du point d'eau d'abord.
MESSAGE_RELEVE_POINT_EAU = (
    "Relevé du point d'eau requis avant devis (D-AGR-4) : niveau d'eau et "
    "débit du forage à mesurer lors d'une visite.")


def _fr_nombre(valeur):
    if valeur is None:
        return '?'
    texte = ('%.1f' % float(valeur)).rstrip('0').rstrip('.')
    return texte.replace('.', ',')


def _build_devis_auto_agricole(*, lead, user, company, taux_tva=None,
                               journal_auto=None, target_kwc=None):
    """AGR124 — devis automatique AGRICOLE (pompage) par le serveur.

    Entrées : ``crm.selectors.entrees_pompage_du_lead`` (AGR404), lues par
    ``pompage.etudier_pompage`` — jamais une colonne du lead lue ici. Refus
    ``AutoDevisError(field=…)`` : données manquantes (``devis_auto.
    champs_requis``, AGR403), relevé du point d'eau requis (D-AGR-4), HMT ou
    débit introuvables, aucune pompe chiffrable. Chaîne : ``etudier_pompage``
    → taille Recommandée + kit minimum (afficheur par défaut) → devis
    BROUILLON (numérotation ``utils/references.py``, lignes par l'écrivain
    unique) → étude v2 écrite UNE fois par le rafraîchisseur (AGR123). Les
    entrées carburant du lead partent dans ``saisies_economie_pompage``
    (provenance ``lead``). Le type du lead n'est JAMAIS changé (D-AGR-9) ;
    aucun statut touché (règle #4). ``journal_auto['alertes']`` reçoit les
    alertes de l'étude et les articles « prix à renseigner » omis."""
    # AGNR39 — une puissance cible n'a aucun sens au pompage (le champ découle
    # de la pompe) : refusée en la NOMMANT (400), jamais ignorée en silence.
    if target_kwc not in (None, ''):
        from rest_framework.exceptions import ValidationError
        raise ValidationError({'target_kwc': (
            "La puissance cible ne s'applique pas au pompage : le champ "
            "solaire découle de la pompe retenue (HMT et débit du lead).")})
    # APAR49 — taux absent ⇒ taux STANDARD de la société (jamais 20 codé).
    if taux_tva is None:
        from apps.ventes.utils.company_settings import tva_standard
        taux_tva = tva_standard(company)
    from apps.crm.selectors import (
        champs_devis_auto_manquants, visite_point_eau_du_lead)
    from apps.crm.services import resolve_client_for_lead
    from apps.ventes.domain.catalogue import catalogue_de_la_societe
    from apps.ventes.domain.pompage import (
        etude_precalculee, etudier_pompage, lignes_kit_auto,
        saisies_economie_pompage_du_lead)
    from apps.ventes.models import Devis

    manquants = champs_devis_auto_manquants(lead)
    if manquants:
        raise AutoDevisError(
            'Manque : ' + ', '.join(m['label'] for m in manquants),
            field=manquants[0]['champ'])
    visite = visite_point_eau_du_lead(lead)
    if visite and visite.get('requise'):
        # AGQ22 (C-AGQ-021) — le 409 nomme le champ du PREMIER motif (débit
        # du forage ≠ niveau d'eau), lu sur la règle servie, jamais figé.
        detail = visite.get('motifs_detail') or [{}]
        raise AutoDevisError(MESSAGE_RELEVE_POINT_EAU,
                             field=detail[0].get('champ')
                             or 'niveau_statique_m')

    # L'alimentation est DÉDUITE du raccordement déclaré (mono/tri) ; inconnu
    # ⇒ absente (jamais « tri » par défaut).
    corps = {'taille': 'recommandee'}
    alim = {'monophase': 'mono', 'triphase': 'tri'}.get(
        phase_et_isolement_du_lead(lead)[0])
    if not alim:
        # AGQ7 (C-AGQ-006) — refus AVANT l'étude, qui nomme la saisie
        # manquante (et non « aucune pompe compatible au catalogue »).
        raise AutoDevisError(
            'Alimentation de la pompe inconnue : renseignez mono ou tri '
            '(raccordement du lead)', field='raccordement')
    corps['alim'] = alim
    # AGQ24 (C-AGQ-023) — latence bornée : aucune TMY sur ce chemin (replis
    # MENTIONNÉS du noyau électrique), étude calculée UNE fois.
    sortie = etudier_pompage(company, corps, lead=lead, sans_tmy=True)
    hmt_m = (sortie.get('hmt') or {}).get('valeur_m')
    debit = (sortie.get('conception') or {}).get('debit_conception_m3h')
    pompe = sortie.get('pompe') or {}
    mode_pompe = ((sortie.get('entrees_resolues') or {}).get(
        'mode_pompe') or {}).get('valeur') or 'neuve'
    if hmt_m is None:
        # AGQ9 (D-AGQ-5) — le niveau d'eau seul ne fait pas une HMT.
        raise AutoDevisError('HMT introuvable : saisissez la HMT (m).',
                             field='pompe_hmt_m')
    if mode_pompe != 'existante' and debit is None:
        # AGQ1 (D-AGQ-1) — le débit souhaité fait le besoin (× heures-pic) :
        # s'il est saisi, ce qui manque ce sont les heures de pompage.
        souhaite = ((sortie.get('entrees_resolues') or {}).get(
            'debit_souhaite_m3h') or {}).get('valeur')
        if souhaite not in (None, ''):
            raise AutoDevisError(
                'Débit de conception introuvable : profil PVGIS du site '
                'indisponible et heures de pompage du réglage société '
                '(agricole_pump_hours) non renseignées.',
                field='agricole_pump_hours')
        raise AutoDevisError(
            'Débit de conception introuvable : saisissez le débit souhaité ou '
            "le besoin en eau (m³/jour).", field='pompe_debit_m3h')

    # AGQ40 (D-AGQ-9) — refus SEULEMENT quand le besoin déclaré devient
    # incouvrable sous le plafond du forage (jamais pour un simple écrêtage).
    codes = {a.get('code') for a in sortie.get('alertes') or ()}
    plafonds = (sortie.get('conception') or {}).get('plafonds') or {}
    controle = sortie.get('controle_conception') or {}
    if (controle.get('statut') == 'couverture_insuffisante'
            and ('debit_limite_forage' in codes or plafonds.get('atteint'))):
        raise AutoDevisError(
            "Besoin déclaré incouvrable : débit limité par votre forage "
            "(%s m³/h exploitables) — mois sous la tolérance : %s. Réduisez "
            "le besoin ou relevez le débit du forage." % (
                _fr_nombre(plafonds.get('plafond_retenu_m3h')),
                ', '.join(str(m) for m in controle.get(
                    'mois_sous_tolerance') or ()) or '?'),
            field='debit_forage_m3h')

    lignes, omises, manquants = lignes_kit_auto(sortie)
    # AGQ4/AGQ5 — prix unitaire : le BARÈME de l'installation (prix fixe +
    # par panneau, ``prix_forfait_ht``) s'il en porte un, sinon le prix de
    # vente du produit.
    from apps.ventes.domain.catalogue import (
        porte_bareme_par_panneau, prix_forfait_ht)
    produits = {p.id: p for p in catalogue_de_la_societe(company)}
    nb_panneaux = sum(int(ligne['quantite']) for ligne in lignes
                      if ligne.get('cle') == 'panneaux')
    chiffrees = []
    for ligne in lignes:
        produit = produits.get(ligne['produit_id'])
        if produit is None:
            continue
        # Barème appliqué à la seule ligne FORFAIT (installation, quantité 1),
        # jamais à une ligne vendue à la quantité (double comptage).
        forfait = (ligne.get('cle') == 'installation'
                   and porte_bareme_par_panneau(produit))
        montant = (prix_forfait_ht(produit, nb_panneaux) if forfait
                   else produit.prix_vente)
        if montant and montant > 0:
            chiffrees.append(dict(ligne,
                                  prix_unitaire=Decimal(str(montant))))
    lignes = chiffrees
    if mode_pompe != 'existante' and (
            pompe.get('placeholder')
            or not any(ligne['role_pompage'] == 'pompe' for ligne in lignes)):
        noms = sortie.get('prix_a_renseigner') or []
        message = ('Aucune pompe chiffrable pour HMT %s m / débit %s m³/h'
                   % (_fr_nombre(hmt_m), _fr_nombre(debit)))
        if noms:
            message += ' — pompes à courbe sans prix : %s' % ', '.join(noms)
        raise AutoDevisError(message + '.', field='pompe')
    # AGQ4 (D-AGQ-3) — kit minimum : un rôle absent ou sans prix refuse le
    # devis en NOMMANT l'article (jamais un devis sans structure ni pose).
    if manquants:
        premier = manquants[0]
        message = '%s : %s' % (premier['libelle'], premier['motif'])
        if premier['cle'] == 'variateur' \
                and premier['motif'] == 'aucun article au catalogue':
            # AGQ6 (C-AGQ-005) — nommer la puissance et l'alimentation
            # cherchées (jamais un devis sans variateur).
            message = ('Variateur : aucun modèle compatible au catalogue '
                       '(%s kW %s)' % (
                           _fr_nombre((sortie.get('puissance_retenue')
                                       or {}).get('kw')), alim))
        raise AutoDevisError(message, field='kit.%s' % premier['cle'])

    client = resolve_client_for_lead(lead)
    etude = dict(corps)
    saisies = saisies_economie_pompage_du_lead(lead)
    if saisies:
        etude['saisies_economie_pompage'] = saisies

    def _create(ref):
        return Devis.objects.create(
            company=company, reference=ref, client=client, lead=lead,
            statut=Devis.Statut.BROUILLON, created_by=user,
            taux_tva=taux_tva, mode_installation='agricole',
            etude_params=etude)

    with etude_precalculee(lead, sortie):
        devis = _ecrire_devis_auto_par_pipeline(
            company=company, user=user, lead=lead, creer=_create,
            lignes=lignes, mode_installation='agricole')
    if journal_auto is not None:
        alertes = [dict(a) for a in (sortie.get('alertes') or [])]
        for designation in omises:
            alertes.append({
                'code': 'article_prix_a_renseigner', 'champ': 'kit',
                'message': ('« %s » non ajouté au devis : prix à renseigner '
                            'au catalogue (jamais un article gratuit).'
                            % designation)})
        journal_auto['alertes'] = alertes
    logger.info('Auto-devis agricole %s: pompe %s (lead %s, company %s)',
                devis.reference, pompe.get('nom'), getattr(lead, 'pk', '?'),
                getattr(company, 'id', '?'))
    return devis


# ── PONTS M3 : noms hébergés ailleurs ────────────────────────────────────────
# Imports EN BAS DE FICHIER, visant le module qui PORTE chaque corps.
from apps.ventes.domain.taille import (  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
    AutoDevisError,
    phase_et_isolement_du_lead,
)
from apps.ventes.domain.creation_auto import _ecrire_devis_auto_par_pipeline  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
