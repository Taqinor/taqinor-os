"""CAL159 (moitié serveur) — la porte HTTP du dimensionnement de pompage.

POURQUOI CETTE VUE EXISTE
-------------------------
``services/pompage.py`` (CAL155-CAL158) porte tout le dimensionnement — besoin
en eau, HMT itérée sur la courbe du puits, 12 volumes pondérés PVGIS, pompe et
variateur assortis — et AUCUNE porte HTTP ne l'exposait. L'écran de pompage du
module (CAL159) aurait donc dû, pour afficher quoi que ce soit, interpoler la
courbe de pompe lui-même : exactement ce que sa tâche interdit (« toutes les
valeurs viennent du backend, aucune interpolation de courbe côté écran ») et
exactement le mode de panne « deux implémentations d'une seule formule » que la
docstring de ``_debit_a_hmt`` combat déjà entre Python et JavaScript.

ELLE EST MINCE, ET DÉLIBÉRÉMENT. Elle ne calcule RIEN : elle lit la saisie,
va chercher le vivier de pompes/variateurs chez ``apps.stock`` par son SEUL
``selectors.py`` (frontière inter-apps), appelle les fonctions PURES du service
et assemble le dictionnaire figé par l'échantillon de contrat
``contract_samples/calepinage_pompage.json`` (PACT10, posé avant les deux
moitiés).

ELLE N'ÉCRIT QUE LE DERNIER RENDU (ACAL831) : un calcul complet, demandé par
``calepinage_gerer`` hors verrou, est rangé dans ``resultat['pompage_dernier']``
pour le rapport d'étude — aucun statut, aucune version, aucune variante, aucune
ligne de devis. POST plutôt que GET parce que l'entrée est une SAISIE (puits, besoin,
réservoir, débit souhaité), pas un identifiant.

FICHIER À PART DE ``views/calepinages.py`` pour la MÊME raison que
``views/equipements.py`` (CAL243) : d'autres lanes travaillent sur ce fichier,
l'action est donc posée ici et rattachée au viewset par une affectation
d'attribut de classe, importée depuis ``urls.py`` AVANT ``router.register``.

ZÉRO CHIFFRE INVENTÉ : une donnée manquante NOMME son champ dans ``erreurs``
(l'écran la pose sous le champ fautif) et fait tomber le bloc concerné à
``None`` — jamais un zéro, jamais une valeur par défaut. En particulier, aucune
pompe sans ``courbe_pompe`` n'est candidate, donc aucun m³/jour n'est jamais
publié pour une pompe sans courbe.
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from core.champs_stricts import ChaineStricte
from core.pompage.hydraulique import hmt_mensuelle
from core.pompage.selection import alertes_pose_pompe, selection_pompe, selection_variateur, tension_produit
from core.pompage.volumes import couverture_besoin_eau

from ..permissions import PeutVoirCalepinage
from ..serializers import forme_du_contrat
from ..services import pompage as dim
from .calepinages import CalepinageViewSet, contexte_conception
from ..services.valeurs import nombre as _nombre

import logging
import math

logger = logging.getLogger(__name__)

__all__ = ['pompage']

#: Valeurs par défaut de FORME (pas de grandeur physique) : le type de pompe et
#: l'alimentation sont des CHOIX d'écran à deux options, jamais des mesures.
#: ``heures_pompage`` reste le 7 h éditable déjà en vigueur côté devis
#: (CLAUDE.md « Pompage sizing ») — publié dans ``entrees`` pour que l'écran
#: montre TOUJOURS la valeur employée.
_TYPE_POMPE_DEFAUT = 'immerge'
_ALIM_DEFAUT = 'tri'
_HEURES_DEFAUT = 7.0


def _produit_pompage(produit):
    """Un ``Produit`` du catalogue → le dict attendu par le service.

    AUCUN prix d'achat, AUCUNE marge : seul ``prix_vente`` transite, et
    uniquement parce que le service refuse de coter un produit sans prix.
    """
    return {
        'id': produit.id,
        'nom': produit.nom,
        'pompe_kw': produit.pompe_kw,
        'courbe_pompe': produit.courbe_pompe,
        'tension_v': produit.tension_v,
        'prix_vente': produit.prix_vente,
    }


def _site(calepinage, request):
    """Le point GPS et la ville du calepinage, pour l'irradiation RÉELLE.

    Lus dans le contexte de conception déjà servi (CAL231) : jamais une ville
    devinée ni des coordonnées de repli — sans pin ni ville, PVGIS n'est pas
    interrogé et seuls les volumes plats sont publiés, annoncés comme tels.
    """
    try:
        contexte = contexte_conception(calepinage, request)
    except Exception:  # le pompage survit à une carte muette
        logger.warning("site : échec ignoré, comportement dégradé", exc_info=True)
        return None, None, None
    pin = ((contexte or {}).get('geometrie') or {}).get('pin') or {}
    ville = ((contexte or {}).get('calepinage') or {}).get('client_ville') or None
    return pin.get('lat'), pin.get('lng'), ville


def _kwc_retenu(calepinage):
    """AGR125 — le kWc du champ de la variante RETENUE de ce calepinage.

    Même lecture que ``selectors.calepinage_retenu_pour_devis`` : résultat du
    moteur (``resultat['pose']``), sinon résumé de l'atelier 3D
    (``roof_layout['result']``). Aucune variante retenue ⇒ ``None``.
    """
    return _resume_retenu(calepinage, 'kwc', 'kwc')


def _modules_retenus(calepinage):
    """ACAL810 — modules POSÉS de la variante retenue : ``pose.total_modules``,
    sinon ``roof_layout['result']['panels']`` ; aucune variante ⇒ ``None``."""
    valeur = _resume_retenu(calepinage, 'total_modules', 'panels')
    return int(valeur) if valeur is not None else None


def _resume_retenu(calepinage, cle_pose, cle_atelier):
    from ..models import CalepinageVariante

    variante = (CalepinageVariante.objects
                .filter(calepinage=calepinage, retenue=True).first())
    if variante is None:
        return None
    resultat = variante.resultat if isinstance(variante.resultat, dict) else {}
    pose = resultat.get('pose') if isinstance(resultat.get('pose'), dict) else {}
    if pose.get(cle_pose) is not None:
        return _nombre(pose.get(cle_pose))
    layout = (variante.roof_layout
              if isinstance(variante.roof_layout, dict) else {})
    result = layout.get('result') if isinstance(layout.get('result'), dict) else {}
    return _nombre(result.get(cle_atelier))


def _salissure_societe(company):
    """Le supplément de salissure RÉGLÉ par la société (AGR107), ou ``None``.

    Le MÊME réglage que lit le devis (``ventes.domain.pompage``) : jamais un
    défaut appliqué d'office.
    """
    from apps.parametres.models import CompanyProfile

    profil = CompanyProfile.objects.filter(company=company).first()
    return _nombre(getattr(profil, 'agricole_salissure_supp_pct', None))


def _rendement_mppt(company, variateur_id):
    """Rendement MPPT PUBLIÉ par la fiche du variateur (fraction), ou ``None``."""
    produit = _element_pompage(company, variateur_id)
    if produit is None:
        return None
    pct = _nombre((produit.get('fiche') or {}).get('var_rendement_mppt_pct'))
    return pct / 100.0 if pct else None


def _element_pompage(company, produit_id):
    """L'élément ``produits_pompage`` (avec sa fiche) de ce produit, ou ``None``."""
    if produit_id is None:
        return None
    from apps.stock.selectors import produits_pompage

    return next((p for p in produits_pompage(company)
                 if p.get('id') == produit_id), None)


def _chaines_variateur(calepinage, variateur_id, serie, paralleles):
    """ACAL810 — ``controle_chaine_variateur`` (noyau) sur le module RETENU
    (``resoudre_materiel``) et les températures du site, plus les modules
    posés ; aucune adaptation du champ."""
    from core.pompage.champ import controle_chaine_variateur

    from ..services.electrique import (
        entree_stockee, resoudre_materiel, temperatures_pour_calepinage)

    materiel, module, temperatures, variateur = {}, None, None, None
    if serie is not None:  # sans longueur saisie, rien à résoudre
        entree = entree_stockee(calepinage)
        materiel = resoudre_materiel(calepinage.company, entree,
                                     calepinage=calepinage)
        module = materiel.get('module') or None
        site = temperatures_pour_calepinage(calepinage, saisie=entree,
                                            module_specs=module)
        if site.source is not None:
            temperatures = {'froid_c': float(site.froid_c),
                            'chaud_c': float(site.chaud_c), 'source': site.source}
        variateur = _element_pompage(calepinage.company, variateur_id)
    bloc = controle_chaine_variateur(variateur, module, serie or 0,
                                     paralleles or 1, temperatures)
    if serie is None:
        bloc['motif'] = 'nombre de modules par chaîne non saisi'
    elif variateur is None:
        bloc['motif'] = 'aucun variateur retenu'
    elif not module:
        bloc['motif'] = next((t for t in materiel.get('absents') or ()
                              if t.startswith('module PV')), bloc['motif'])
    bloc.update(serie=serie, paralleles=paralleles or 1,
                modules_poses=_modules_retenus(calepinage),
                champ='modules_en_serie' if serie is None else None)
    return bloc


_NOMBRES_POMPAGE = (
    'hmt_saisie', 'debit_souhaite_m3h', 'heures_pompage',
    'volume_reservoir_m3', 'besoin_m3_jour', 'niveau_statique_m',
    'niveau_dynamique_m', 'coefficient_rabattement_m_par_m3h',
    'longueur_tuyauterie_m', 'coefficient_frottement',
    'hauteur_refoulement_m', 'denivele_m', 'diametre_interieur_mm',
    'c_hazen_williams', 'pertes_singulieres_m', 'pression_service_bar',
    'kwc', 'niveau_statique_ete_m', 'niveau_statique_hiver_m',
    'profondeur_calage_m', 'diametre_tubage_mm')  # ACAL1113 — contrôles de pose


class FlottantFini(serializers.FloatField):
    """Nombre FINI : ``1e999`` (lu ``inf`` par le JSON) etait « conforme » au
    schema (un nombre) puis, une fois calcule, faisait lever le rendu JSON de
    la reponse (``Out of range float values``) - un 500 HTML hors enveloppe."""

    def to_internal_value(self, data):
        valeur = super().to_internal_value(data)
        if not math.isfinite(valeur):
            self.fail('invalid')
        return valeur


def _sans_non_fini(valeur):
    """La reponse SANS ``inf`` / ``nan`` (``None`` a la place) : un calcul qui
    deborde sur une saisie enorme ne doit jamais faire echouer le rendu."""
    if isinstance(valeur, float):
        return valeur if math.isfinite(valeur) else None
    if isinstance(valeur, dict):
        return {cle: _sans_non_fini(sous) for cle, sous in valeur.items()}
    if isinstance(valeur, (list, tuple)):
        return [_sans_non_fini(sous) for sous in valeur]
    return valeur


def _champs_corps():
    """Les champs du corps — UNE déclaration pour le schéma ET la validation.

    Les nombres restent ``null``-ables (un ``null`` vaut « non renseigné »,
    comme l'absence) ; les trois choix texte sont des chaînes STRICTES : un
    ``"type_pompe": 0`` est un 400 nommé, jamais un choix par défaut
    silencieux (api-fuzz). Fabrique : un champ DRF ne se lie qu'une fois."""
    return {
        **{nom: FlottantFini(required=False, allow_null=True)
           for nom in _NOMBRES_POMPAGE},
        'type_pompe': ChaineStricte(required=False),
        'alim': ChaineStricte(required=False),
        'materiau_conduite': ChaineStricte(required=False),
        'besoin_m3_mois': serializers.ListField(
            child=FlottantFini(allow_null=True), required=False),
        'mois_niveau_bas': serializers.ListField(
            child=serializers.IntegerField(min_value=1, max_value=12),
            required=False, allow_null=True),
        'modules_en_serie': serializers.IntegerField(
            min_value=1, required=False, allow_null=True),
        'chaines_paralleles': serializers.IntegerField(
            min_value=1, required=False, allow_null=True)}


@extend_schema(
    request=inline_serializer('CalepinagePompageCorps', _champs_corps()),
    responses=forme_du_contrat('CalepinagePompageReponse',
                               'calepinage_pompage.json'))
@action(detail=True, methods=['post'], url_path='pompage',
        permission_classes=[PeutVoirCalepinage],
        parser_classes=[JSONParser])  # corps JSON seul : un multipart n'a pas de null
def pompage(self, request, pk=None):
    """CAL159 — puits, besoin, réservoir, pompe/variateur et volumes mensuels.

    Forme de la réponse : ``contract_samples/calepinage_pompage.json``.
    Calcul borné société par ``get_queryset`` ; seul le dernier rendu complet
    est enregistré (``_enregistrer_dernier``, ACAL831).
    """
    from apps.stock.selectors import produits_par_type_equipement

    calepinage = self.get_object()
    type('CalepinagePompageCorps', (serializers.Serializer,), _champs_corps())(
        data=request.data).is_valid(raise_exception=True)
    corps = request.data if isinstance(request.data, dict) else {}

    type_pompe = str(corps.get('type_pompe') or _TYPE_POMPE_DEFAUT)
    alim = str(corps.get('alim') or _ALIM_DEFAUT)
    heures = _nombre(corps.get('heures_pompage'))
    if heures is None or heures <= 0:
        heures = _HEURES_DEFAUT
    debit_souhaite = _nombre(corps.get('debit_souhaite_m3h'))
    reservoir = _nombre(corps.get('volume_reservoir_m3'))
    besoin_jour = _nombre(corps.get('besoin_m3_jour'))
    besoin_mois = corps.get('besoin_m3_mois')
    if not isinstance(besoin_mois, list) or len(besoin_mois) != 12:
        besoin_mois = None

    erreurs = {}
    avertissements = []

    # ── 1. La HMT : MÊME calcul que le devis (AGR111/AGR125), sinon SAISIE ─
    saisie_puits = dict(
        hmt_saisie=_nombre(corps.get('hmt_saisie')),
        debit_m3h=debit_souhaite,
        niveau_statique_m=_nombre(corps.get('niveau_statique_m')),
        niveau_dynamique_m=_nombre(corps.get('niveau_dynamique_m')),
        coefficient_rabattement_m_par_m3h=_nombre(
            corps.get('coefficient_rabattement_m_par_m3h')),
        longueur_tuyauterie_m=_nombre(corps.get('longueur_tuyauterie_m')),
        coefficient_frottement=_nombre(corps.get('coefficient_frottement')),
        hauteur_refoulement_m=_nombre(corps.get('hauteur_refoulement_m')),
        denivele_m=_nombre(corps.get('denivele_m')),
        diametre_interieur_mm=_nombre(corps.get('diametre_interieur_mm')),
        materiau_conduite=corps.get('materiau_conduite') or None,
        c_hazen_williams=_nombre(corps.get('c_hazen_williams')),
        pertes_singulieres_m=_nombre(corps.get('pertes_singulieres_m')),
        pression_service_bar=_nombre(corps.get('pression_service_bar')),
    )
    # ACAL806 — niveau statique de chaque mois : été sur `mois_niveau_bas`,
    # hiver ailleurs ; la plus haute des 12 HMT choisit la pompe.
    niveau_ete = _nombre(corps.get('niveau_statique_ete_m'))
    niveau_hiver = _nombre(corps.get('niveau_statique_hiver_m'))
    mois_bas = sorted({int(m) for m in corps.get('mois_niveau_bas') or []})
    hmt_par_mois = None
    if (niveau_ete is not None or niveau_hiver is not None) and not mois_bas:
        erreurs['mois_niveau_bas'] = (
            'Indiquez les mois où le niveau d’eau est bas (été) : sans eux, '
            'le niveau d’été et le niveau d’hiver ne peuvent pas être répartis.')
    elif niveau_ete is not None or niveau_hiver is not None:
        niveaux = [niveau_ete if m in mois_bas else niveau_hiver
                   for m in range(1, 13)]
        hmt_par_mois = hmt_mensuelle(
            niveaux_statiques_m_mois=niveaux,
            **dim.parametres_hmt_du_puits(**saisie_puits))
        effectifs = [saisie_puits['niveau_statique_m'] if n is None else n
                     for n in niveaux]
        saisie_puits['niveau_statique_m'] = max(
            (n for n in effectifs if n is not None), default=None)
    hmt = dim.hmt_du_puits(**saisie_puits)
    if hmt_par_mois and hmt_par_mois['valeurs_m']:
        hmt['hmt_m'] = max(hmt_par_mois['valeurs_m'])
    manquantes = hmt.pop('manquantes', None) or []
    for alerte in hmt.pop('alertes', None) or []:
        avertissements.append(alerte.get('message') or str(alerte))
    if hmt['hmt_m'] is None:
        noms = [dim.LIBELLES_COMPOSANTES_HMT.get(m, m) for m in manquantes]
        erreurs['hmt_saisie'] = (
            'Renseignez la HMT, ou toutes ses composantes pour qu’elle soit '
            'calculée comme au devis'
            + (' — manquant : ' + ', '.join(noms) if noms else '') + '.')
    if debit_souhaite is None or debit_souhaite <= 0:
        erreurs['debit_souhaite_m3h'] = (
            'Le débit souhaité (m³/h) est obligatoire : sans lui, '
            'aucune pompe ne peut être choisie sur sa courbe.')

    # ── 2. La pompe, puis le variateur assorti ─────────────────────────────
    choix = selection_pompe(
        [_produit_pompage(p) for p in produits_par_type_equipement(
            calepinage.company, 'pompe', avec_prix=False)],
        hmt=hmt['hmt_m'], debit_souhaite_m3h=debit_souhaite,
        type_pompe=type_pompe, alim=alim)

    pompe_servie = None
    variateur_servi = None
    if choix['pompe'] is not None:
        produit = choix['pompe']
        courbe = produit.get('courbe_pompe') or {}
        pompe_servie = {
            'produit': produit.get('id'),
            'nom': produit.get('nom'),
            'pompe_kw': produit.get('pompe_kw'),
            'tension_v': tension_produit(produit),
            'debit_hmt_m3h': choix['debit_hmt_m3h'],
            'courbe': {
                'debits_m3h': courbe.get('debits_m3h'),
                'hmt_m': courbe.get('hmt_m'),
            },
            # Le point de fonctionnement est CALCULÉ ICI, une seule fois :
            # l'écran le trace, il ne le cherche pas sur la courbe.
            'point_fonctionnement': {
                'debit_m3h': choix['debit_hmt_m3h'],
                'hmt_m': hmt['hmt_m'],
            },
            'sans_prix': choix['sans_prix'],
            'ecart_phase': choix['ecart_phase'],
        }
        assorti = selection_variateur(
            [_produit_pompage(p) for p in produits_par_type_equipement(
                calepinage.company, 'variateur', avec_prix=False)],
            choix['kw'], alim)
        if assorti['variateur'] is not None:
            variateur_servi = {
                'produit': assorti['variateur'].get('id'),
                'nom': assorti['variateur'].get('nom'),
                'pompe_kw': assorti['variateur'].get('pompe_kw'),
                'tension_v': tension_produit(assorti['variateur']),
                'insuffisant': False,
            }
        elif assorti['insuffisant']:
            avertissements.append(
                'aucun variateur du catalogue n’atteint la puissance de la '
                'pompe retenue — aucun variateur sous-dimensionné n’est '
                'proposé à sa place')
        if choix['ecart_phase']:
            avertissements.append(
                'des pompes compatibles existent dans l’autre tension '
                'd’alimentation : vérifiez le choix mono/triphasé')
    elif not erreurs:
        avertissements.append(
            'aucune pompe à courbe ne délivre le débit demandé à cette HMT — '
            'aucun m³/jour n’est publié (une pompe sans courbe ne produit '
            'jamais de volume chiffré)')
        if choix['sans_prix']:
            avertissements.append(
                'des pompes conviennent mais n’ont pas de prix renseigné : '
                + ', '.join(str(n) for n in choix['sans_prix'] if n))

    # ACAL1113 — les contrôles de pose DU DEVIS, sur la seule pompe retenue (aucun défaut).
    calage, tubage = _nombre(corps.get('profondeur_calage_m')), _nombre(corps.get('diametre_tubage_mm'))
    alertes = []
    if pompe_servie is not None and (calage is not None or tubage is not None):
        alertes = alertes_pose_pompe(
            (_element_pompage(calepinage.company, pompe_servie['produit']) or {}).get('fiche'),
            diametre_tubage_mm=tubage, profondeur_calage_m=calage,
            niveau_dynamique_m=_nombre(corps.get('niveau_dynamique_m')))

    # ── 3. Les volumes — JAMAIS sans pompe à courbe retenue ────────────────
    # AGR125 — MÊME calcul que le devis : production heure par heure sur le
    # MÊME profil PVGIS du site (``ventes.domain.pompage.profils_horaires_site``),
    # pour le kWc du champ (saisi, sinon variante retenue) et la plaque de la
    # pompe retenue. Le calcul plat reste publié à côté.
    volumes = None
    if pompe_servie is not None and choix['debit_hmt_m3h']:
        from apps.parametres.pvgis_profils import productible_mensuel
        from apps.ventes.domain.pompage import profils_horaires_site
        from core.pompage.selection import kw_pompe

        lat, lon, ville = _site(calepinage, request)
        profils = profils_horaires_site(ville=ville, lat=lat, lon=lon)
        source_irradiation = None
        if profils is not None:
            resolu = productible_mensuel(ville=ville, lat=lat, lon=lon)
            source_irradiation = resolu[1] if resolu else None
        kwc = _nombre(corps.get('kwc'))
        if kwc is None or kwc <= 0:
            kwc = _kwc_retenu(calepinage)
        plaque_kw, _source_kw = kw_pompe(choix['pompe'])
        volumes = dim.volumes_mensuels(
            debit_hmt_m3h=choix['debit_hmt_m3h'], pumping_hours=heures,
            courbe_pompe=choix['pompe'].get('courbe_pompe'),
            hmt_m=hmt['hmt_m'], kwc=kwc, p_plaque_kw=plaque_kw,
            rendement_mppt=_rendement_mppt(
                calepinage.company, (variateur_servi or {}).get('produit')),
            salissure_pct=_salissure_societe(calepinage.company),
            profils_horaires=profils, source_irradiation=source_irradiation,
            hmt_m_mois=(hmt_par_mois or {}).get('valeurs_m'))

    # ── 3 bis. ACAL810 — les chaînes du champ posé contre le variateur ──────
    serie = corps.get('modules_en_serie')
    paralleles = corps.get('chaines_paralleles')
    chaines = _chaines_variateur(
        calepinage, (variateur_servi or {}).get('produit'),
        int(serie) if serie is not None else None,
        int(paralleles) if paralleles is not None else None)
    if chaines['modules_poses'] is not None and chaines['serie'] is not None \
            and chaines['serie'] * chaines['paralleles'] != chaines['modules_poses']:
        avertissements.append(
            '%d chaîne(s) de %d modules ne font pas les %d modules posés de la '
            'variante retenue' % (chaines['paralleles'], chaines['serie'],
                                  chaines['modules_poses']))

    besoin = couverture_besoin_eau(
        besoin_m3_jour=besoin_jour, besoin_m3_mois=besoin_mois,
        volume_reservoir_m3=reservoir,
        production_m3_mois=(volumes or {}).get('m3_mois_pvgis')
        or (volumes or {}).get('m3_mois_plat'))

    reponse = _sans_non_fini({
        'calepinage': calepinage.id,
        'entrees': {
            'hmt_saisie': _nombre(corps.get('hmt_saisie')),
            'debit_souhaite_m3h': debit_souhaite,
            'type_pompe': type_pompe,
            'alim': alim,
            'heures_pompage': heures,
            'volume_reservoir_m3': reservoir,
            'besoin_m3_jour': besoin_jour,
            'niveau_statique_ete_m': niveau_ete,
            'niveau_statique_hiver_m': niveau_hiver,
            'mois_niveau_bas': mois_bas,
            'profondeur_calage_m': calage,
            'diametre_tubage_mm': tubage,
        },
        'hmt': hmt,
        'hmt_mensuelle': hmt_par_mois,
        'pompe': pompe_servie,
        'variateur': variateur_servi,
        'volumes': volumes,
        'chaines_variateur': chaines,
        'besoin': besoin,
        'erreurs': erreurs,
        'avertissements': avertissements,
        'alertes': alertes,
    })
    reponse['enregistre'], reponse['motif_non_enregistre'] = _enregistrer_dernier(
        calepinage, request, reponse)
    return Response(reponse)


#: ACAL831 — la clé de ``Calepinage.resultat`` qui garde le DERNIER rendu.
CLE_POMPAGE_DERNIER = 'pompage_dernier'


def _enregistrer_dernier(calepinage, request, reponse):
    """ACAL831 — range le dernier dimensionnement COMPLET (sans ``calepinage``
    ni ``erreurs``) dans ``resultat['pompage_dernier']`` par l'écrivain unique,
    seulement pour ``calepinage_gerer`` et hors verrou ; rend
    ``(enregistre, motif_non_enregistre)`` — le calcul reste servi."""
    from django.utils import timezone

    from ..permissions import PeutGererCalepinage
    from ..services.resultat import modifier_resultat
    from ..services.verrou import VerrouilleRefuse, verifier_ecriture_autorisee

    if reponse['erreurs']:
        return False, 'calcul incomplet : ' + ', '.join(sorted(reponse['erreurs']))
    if not PeutGererCalepinage().has_permission(request, None):
        return False, 'droit calepinage_gerer manquant'
    try:
        verifier_ecriture_autorisee(calepinage, champ='pompage')
    except VerrouilleRefuse as refus:
        messages = [str(m) for liste in refus.detail.values() for m in liste]
        return False, ' '.join(messages)
    bloc = {cle: valeur for cle, valeur in reponse.items()
            if cle not in ('calepinage', 'erreurs')}
    bloc['enregistre_le'] = timezone.now().isoformat()

    def _poser(resultat):
        resultat[CLE_POMPAGE_DERNIER] = bloc

    modifier_resultat(calepinage, _poser)
    return True, None


# Rattachement au viewset PIVOT — voir la docstring du module.
CalepinageViewSet.pompage = pompage
