"""Reste d'ACAL2020 — la consommation IMPOSÉE au moteur unique (D-ACAL-97), UNE forme.

``imposes.consommation`` = ``{kwh_annuel, kwh_mensuels?, source}`` :

* ``kwh_annuel`` — kWh par an (> 0, ≤ :data:`KWH_ANNUEL_MAX`) ; déduit des douze mois
  quand seuls eux sont donnés ;
* ``kwh_mensuels`` — facultatif : douze kWh mensuels (chacun 0..:data:`KWH_MENSUEL_MAX`,
  somme > 0) ; donnés avec ``kwh_annuel``, leur somme doit valoir l'annuel à
  :data:`TOLERANCE_KWH` près ;
* ``source`` — ``releve`` (relevé collé au calepinage), ``factures`` (douze factures
  saisies), ``facture_reelle`` (facture réelle en MAD par mois, convertie par l'écran) ou
  ``saisie``.

Deux appelants : le relevé collé au calepinage (``porte_calepinage.consommation_du_calepinage``,
NIVEAU DE RÈGLES 15 seulement : il change une conception rangée) et l'aperçu de l'écran devis
(``service.apercu_conception``, qui n'écrit rien : accepté au niveau courant). Le moteur la
reçoit sur une COPIE non enregistrée du lead (``conso_mensuelle_kwh`` = annuel ÷ 12, la
priorité « kWh déclaré » des deux marchés solaires) : elle entre donc dans l'empreinte des
entrées, le lead n'est jamais écrit, et la conception le DIT (entrée + supposition).
"""
import math

CLE = 'consommation'
SOURCES = ('releve', 'factures', 'facture_reelle', 'saisie')
KWH_ANNUEL_MAX = 5_000_000.0
KWH_MENSUEL_MAX = 1_000_000.0
TOLERANCE_KWH = 1.0
CODE = 'consommation_du_releve'
CODE_IMPOSEE = 'consommation_imposee'
MESSAGE_RELEVE = ('Consommation prise du relevé collé au calepinage (%s kWh par mois) : celle de la fiche du '
                  'lead n\'est pas utilisée. Retirez le relevé à l\'étape Consommation du calepinage pour revenir '
                  'à celle du lead.')
MESSAGE_IMPOSEE = ('Consommation imposée par le devis (%s kWh par mois, %s) : celle de la fiche du lead n\'est pas '
                   'utilisée.')
MESSAGE_DOUZE_MOIS = ' Les douze mois reçus sont ramenés à leur moyenne mensuelle par le moteur.'
_LIBELLES = {'factures': 'factures saisies', 'facture_reelle': 'factures réelles', 'saisie': 'saisie'}


class ConsommationRefusee(ValueError):
    """Une consommation imposée hors forme ou hors bornes ; ``champ`` la nomme."""

    def __init__(self, message, champ):
        super().__init__(message)
        self.champ = champ


def _kwh(valeur, champ, maximum):
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)) or not math.isfinite(valeur) \
            or valeur < 0 or valeur > maximum:
        raise ConsommationRefusee('« %s » : un nombre de kWh entre 0 et %s est attendu.' % (champ, int(maximum)),
                                  champ)
    return float(valeur)


def valider(brut):
    """La consommation imposée NORMALISÉE ``{kwh_annuel, kwh_mensuels | None, source}`` ;
    ``ConsommationRefusee`` (champ nommé ``consommation.<clé>``) sinon. Seule validation."""
    if not isinstance(brut, dict):
        raise ConsommationRefusee('« consommation » est un objet.', CLE)
    inconnues = sorted(set(brut) - {'kwh_annuel', 'kwh_mensuels', 'source'})
    if inconnues:
        raise ConsommationRefusee('Clé inconnue : %s.' % inconnues[0], '%s.%s' % (CLE, inconnues[0]))
    if brut.get('source') not in SOURCES:
        raise ConsommationRefusee('« source » : une de %s.' % ', '.join(SOURCES), CLE + '.source')
    mensuels = brut.get('kwh_mensuels')
    if mensuels is not None:
        if not isinstance(mensuels, list) or len(mensuels) != 12:
            raise ConsommationRefusee('« kwh_mensuels » : douze valeurs.', CLE + '.kwh_mensuels')
        mensuels = [_kwh(v, CLE + '.kwh_mensuels', KWH_MENSUEL_MAX) for v in mensuels]
    annuel = brut.get('kwh_annuel')
    if annuel is None and mensuels is not None:
        annuel = sum(mensuels)
    annuel = _kwh(annuel, CLE + '.kwh_annuel', KWH_ANNUEL_MAX) if annuel is not None else 0.0
    if annuel <= 0:
        raise ConsommationRefusee('« kwh_annuel » : une consommation positive est attendue.', CLE + '.kwh_annuel')
    if mensuels is not None and abs(sum(mensuels) - annuel) > TOLERANCE_KWH:
        raise ConsommationRefusee('« kwh_annuel » ne vaut pas la somme des douze mois.', CLE + '.kwh_annuel')
    return {'kwh_annuel': annuel, 'kwh_mensuels': mensuels, 'source': brut['source']}


def separer(imposes):
    """``(imposes sans la consommation | None, consommation brute | None)``."""
    if not imposes or CLE not in imposes:
        return imposes, None
    reste = {cle: valeur for cle, valeur in imposes.items() if cle != CLE}
    return reste or None, imposes[CLE]


def imposer(lead, company, calepinage_id=None, *, imposee=None):
    """``(porteur, consommation | None)`` : ``imposee`` (déjà validée, aperçu) sinon, au
    niveau de règles 15 seulement, le relevé collé au calepinage ``calepinage_id``. Une COPIE
    non enregistrée du lead porte ``conso_mensuelle_kwh`` ; idempotent ; agricole, ou sans
    consommation : le lead lui-même."""
    import copy
    from decimal import Decimal

    deja = getattr(lead, '_consommation_imposee', None)
    if deja is not None or lead is None:
        return lead, deja
    from apps.ventes.conception.entrees import marche_du_lead
    try:
        if marche_du_lead(lead) == 'agricole':
            return lead, None
    except ValueError:
        return lead, None
    if imposee is None and calepinage_id:
        from apps.ventes.domain.regles_calcul import REGLES_POSE_REELLE_2111, regles_au_moins
        if regles_au_moins(None, REGLES_POSE_REELLE_2111):
            from apps.ventes.conception.porte_calepinage import consommation_du_calepinage
            imposee = consommation_du_calepinage(company, calepinage_id)
    if imposee is None:
        return lead, None
    copie = copy.copy(lead)
    copie.conso_mensuelle_kwh = Decimal(str(round(imposee['kwh_annuel'] / 12, 1)))
    copie._consommation_imposee = imposee
    return copie, imposee


def dire(resultat, imposee):
    """La conception DIT d'où vient sa consommation : l'entrée ``conso_mensuelle_kwh``
    (source ``calepinage`` pour le relevé, ``saisie`` sinon) et une supposition."""
    if imposee is None:
        return
    mensuel = round(imposee['kwh_annuel'] / 12, 1)
    texte = '{:,.0f}'.format(mensuel).replace(',', ' ')
    releve = imposee['source'] == 'releve'
    source = 'calepinage' if releve else 'saisie'
    resultat.entrees_utilisees['conso_mensuelle_kwh'] = {'valeur': mensuel, 'source': source}
    message = (MESSAGE_RELEVE % texte if releve
               else MESSAGE_IMPOSEE % (texte, _LIBELLES.get(imposee['source'], imposee['source'])))
    if imposee.get('kwh_mensuels'):
        message += MESSAGE_DOUZE_MOIS
    resultat.suppositions.append({'code': CODE if releve else CODE_IMPOSEE, 'champ': 'conso_mensuelle_kwh',
                                  'valeur': mensuel, 'source': source,
                                  'message': message})
