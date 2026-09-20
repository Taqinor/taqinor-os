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

ELLE N'ÉCRIT RIEN : aucun statut, aucune version, aucune variante, aucune ligne
de devis. POST plutôt que GET parce que l'entrée est une SAISIE (puits, besoin,
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

from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutVoirCalepinage
from ..services import pompage as dim
from .calepinages import CalepinageViewSet, contexte_conception

__all__ = ['pompage']

#: Valeurs par défaut de FORME (pas de grandeur physique) : le type de pompe et
#: l'alimentation sont des CHOIX d'écran à deux options, jamais des mesures.
#: ``heures_pompage`` reste le 7 h éditable déjà en vigueur côté devis
#: (CLAUDE.md « Pompage sizing ») — publié dans ``entrees`` pour que l'écran
#: montre TOUJOURS la valeur employée.
_TYPE_POMPE_DEFAUT = 'immerge'
_ALIM_DEFAUT = 'tri'
_HEURES_DEFAUT = 7.0


def _nombre(valeur):
    """La saisie en flottant, ou ``None`` — jamais 0 en guise d'absence."""
    if valeur is None or valeur == '':
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


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


def _pin(calepinage, request):
    """Le point GPS du calepinage, pour l'irradiation RÉELLE du site.

    Lu dans le contexte de conception déjà servi (CAL231) : jamais une ville
    devinée ni des coordonnées de repli — sans pin, PVGIS n'est pas interrogé
    et les volumes restent le calcul plat, annoncé comme tel.
    """
    try:
        contexte = contexte_conception(calepinage, request)
    except Exception:   # noqa: BLE001 — le pompage survit à une carte muette
        return None, None
    pin = ((contexte or {}).get('geometrie') or {}).get('pin') or {}
    return pin.get('lat'), pin.get('lng')


@action(detail=True, methods=['post'], url_path='pompage',
        permission_classes=[PeutVoirCalepinage])
def pompage(self, request, pk=None):
    """CAL159 — puits, besoin, réservoir, pompe/variateur et volumes mensuels.

    Forme de la réponse : ``contract_samples/calepinage_pompage.json``.
    Lecture PURE, bornée société par ``get_queryset``.
    """
    from apps.stock.selectors import produits_par_type_equipement

    calepinage = self.get_object()
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

    # ── 1. La HMT : calculée sur les données de puits, sinon SAISIE ─────────
    hmt = dim.hmt_puits_iteree(
        hmt_saisie=_nombre(corps.get('hmt_saisie')),
        niveau_statique_m=_nombre(corps.get('niveau_statique_m')),
        coefficient_rabattement_m_par_m3h=_nombre(
            corps.get('coefficient_rabattement_m_par_m3h')),
        longueur_tuyauterie_m=_nombre(corps.get('longueur_tuyauterie_m')),
        coefficient_frottement=_nombre(corps.get('coefficient_frottement')),
        hauteur_refoulement_m=_nombre(corps.get('hauteur_refoulement_m')),
        debit_initial_m3h=debit_souhaite,
    )
    if hmt['hmt_m'] is None:
        erreurs['hmt_saisie'] = (
            'Renseignez la HMT, ou les cinq données de puits (niveau '
            'statique, rabattement spécifique, longueur de tuyauterie, '
            'coefficient de frottement, hauteur de refoulement) pour '
            'qu’elle soit calculée.')
    if debit_souhaite is None or debit_souhaite <= 0:
        erreurs['debit_souhaite_m3h'] = (
            'Le débit souhaité (m³/h) est obligatoire : sans lui, '
            'aucune pompe ne peut être choisie sur sa courbe.')

    # ── 2. La pompe, puis le variateur assorti ─────────────────────────────
    choix = dim.selection_pompe(
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
            'tension_v': dim.tension_produit(produit),
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
        assorti = dim.selection_variateur(
            [_produit_pompage(p) for p in produits_par_type_equipement(
                calepinage.company, 'variateur', avec_prix=False)],
            choix['kw'], alim)
        if assorti['variateur'] is not None:
            variateur_servi = {
                'produit': assorti['variateur'].get('id'),
                'nom': assorti['variateur'].get('nom'),
                'pompe_kw': assorti['variateur'].get('pompe_kw'),
                'tension_v': dim.tension_produit(assorti['variateur']),
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

    # ── 3. Les volumes — JAMAIS sans pompe à courbe retenue ────────────────
    volumes = None
    if pompe_servie is not None and choix['debit_hmt_m3h']:
        lat, lon = _pin(calepinage, request)
        volumes = dim.pompage_mensuel_pvgis(
            debit_hmt_m3h=choix['debit_hmt_m3h'], pumping_hours=heures,
            lat=lat, lon=lon)

    besoin = dim.couverture_besoin_eau(
        besoin_m3_jour=besoin_jour, besoin_m3_mois=besoin_mois,
        volume_reservoir_m3=reservoir,
        production_m3_mois=(volumes or {}).get('m3_mois_pvgis')
        or (volumes or {}).get('m3_mois_plat'))

    return Response({
        'calepinage': calepinage.id,
        'entrees': {
            'hmt_saisie': _nombre(corps.get('hmt_saisie')),
            'debit_souhaite_m3h': debit_souhaite,
            'type_pompe': type_pompe,
            'alim': alim,
            'heures_pompage': heures,
            'volume_reservoir_m3': reservoir,
            'besoin_m3_jour': besoin_jour,
        },
        'hmt': hmt,
        'pompe': pompe_servie,
        'variateur': variateur_servi,
        'volumes': volumes,
        'besoin': besoin,
        'erreurs': erreurs,
        'avertissements': avertissements,
    })


# Rattachement au viewset PIVOT — voir la docstring du module.
CalepinageViewSet.pompage = pompage
