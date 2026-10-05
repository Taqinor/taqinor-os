"""CIQ406 — reprise de l'existant : les réponses PRO du site restées dans
``web_questionnaire`` passent dans leurs colonnes CIQ401.

DONNÉES seulement (aucun changement de schéma), patron 0117 (QJR595) / 0120
(AGR402). Une clé n'est déplacée que si sa colonne est VIDE et que la valeur
tient dans la colonne ; la clé déplacée est RETIRÉE du sac, celle qui ne
l'est pas y reste. ``activity_profile``, ``weekend`` et ``fermeture_estivale``
restent au sac (informations). Idempotente (une clé déplacée n'est plus dans
le sac ; une colonne remplie n'est plus vide). Retour arrière : no-op.

Tension : sans ``tension_source`` « touchee » dans le sac (cas de TOUS les
anciens leads), la source est ``site_defaut_visible`` — la valeur pré-cochée
du site n'est jamais lue comme une déclaration (D-CIQ-5). Aucun devis n'est
touché (D-CIQ-21).

Les tables sont COPIÉES ici (jamais importées du code de l'app : une
migration ne doit pas changer de sens quand le code évolue).
"""
from django.db import migrations

LOT = 500

CATEGORIES = {
    'hotel': ('chambres', 'occupation_pct', 'piscine', 'heures_piscine',
              'blanchisserie', 'reception_24h'),
    'restaurant': ('chambres_froides', 'horaires', 'cuisson',
                   'ouvert_journee_ramadan'),
    'commerce': ('surface_vente_m2', 'chambres_froides'),
    'bureau': ('effectif', 'clim'),
    'sante': ('lits', 'garde_nuit'),
    'ecole': ('effectif', 'internat', 'fermeture_estivale'),
    'hammam': ('surface_m2', 'chauffe'),
    'boulangerie': ('four', 'cuisson_nocturne'),
    'froid': ('temperature_consigne', 'volume_m3', 'saisonnalite_recolte'),
    'autre': (),
}

CLES_REPONSES = (
    'chambres', 'occupation_pct', 'piscine', 'blanchisserie',
    'chambres_froides', 'horaires', 'cuisson', 'surface_vente_m2',
    'effectif', 'clim', 'lits', 'garde_nuit', 'internat', 'four',
    'cuisson_nocturne', 'temperature_consigne', 'volume_m3',
    'saisonnalite_recolte', 'chauffe',
)

TYPE_SURFACE = {
    'bac_acier': ('toiture', 'bac_acier'),
    'terrasse': ('toiture', 'terrasse_beton'),
    'ombriere': ('ombriere', None),
    'terrain': ('terrain', None),
}


def _nombre(valeur):
    if isinstance(valeur, bool):
        return None
    if isinstance(valeur, (int, float)):
        return valeur
    return None


def _json(valeur):
    if isinstance(valeur, float) and valeur.is_integer():
        return int(valeur)
    return valeur


def _vide(valeur):
    return valeur is None or valeur == ''


def promouvoir(lead, sac):
    """Mute ``lead`` et ``sac`` ; rend la liste des champs écrits."""
    champs = []

    def _poser(colonne, valeur):
        setattr(lead, colonne, valeur)
        champs.append(colonne)

    tension = sac.get('tension_raccordement')
    if tension in ('bt', 'mt') and _vide(lead.tension_raccordement):
        origine = sac.pop('tension_source', None)
        sac.pop('tension_raccordement')
        _poser('tension_raccordement', tension)
        _poser('tension_source', 'site_web' if origine == 'touchee'
               else 'site_defaut_visible')
    categorie = sac.get('categorie_commerciale')
    if categorie in CATEGORIES and _vide(lead.categorie_commerciale):
        _poser('categorie_commerciale', sac.pop('categorie_commerciale'))
    categorie = lead.categorie_commerciale or categorie
    permises = (set(CATEGORIES[categorie]) if categorie in CATEGORIES
                else set(CLES_REPONSES))
    if not lead.reponses_categorie:
        reponses = {}
        for cle in CLES_REPONSES:
            if cle in permises and sac.get(cle) is not None:
                reponses[cle] = _json(sac.pop(cle))
        if reponses:
            _poser('reponses_categorie', reponses)
    equipes = sac.get('equipes')
    if equipes in ('1x8', '2x8', '3x8', 'continu') \
            and _vide(lead.regime_equipes):
        _poser('regime_equipes', sac.pop('equipes'))
    surface = TYPE_SURFACE.get(sac.get('surface_type'))
    if surface is not None and _vide(lead.type_surface):
        sac.pop('surface_type')
        _poser('type_surface', surface[0])
        if surface[1] and _vide(lead.type_toiture):
            _poser('type_toiture', surface[1])
    groupe = sac.get('has_generator')
    if isinstance(groupe, bool) and _vide(lead.groupe_electrogene):
        sac.pop('has_generator')
        _poser('groupe_electrogene', 'oui' if groupe else 'non')
    for cle, colonne, borne in (
            ('groupe_kva', 'groupe_kva', 1000000),
            ('diesel_dh_mois', 'groupe_depense_mad_mois', 100000000)):
        valeur = _nombre(sac.get(cle))
        if valeur is not None and 0 <= valeur < borne \
                and getattr(lead, colonne) is None:
            sac.pop(cle)
            _poser(colonne, valeur)
    cos_phi = _nombre(sac.get('cos_phi_connu'))
    if cos_phi is not None and 0 < cos_phi <= 1 and lead.cos_phi is None:
        sac.pop('cos_phi_connu')
        _poser('cos_phi', round(cos_phi, 3))
        _poser('cos_phi_source', 'site_web')
    return champs


def deplacer(apps, schema_editor):
    Lead = apps.get_model('crm', 'Lead')
    pks = list(Lead.objects.exclude(web_questionnaire=None).exclude(
        web_questionnaire={}).order_by('pk').values_list('pk', flat=True))
    for i in range(0, len(pks), LOT):
        for lead in Lead.objects.filter(pk__in=pks[i:i + LOT]):
            sac = lead.web_questionnaire
            if not isinstance(sac, dict):
                continue
            sac = dict(sac)
            champs = promouvoir(lead, sac)
            if champs:
                lead.web_questionnaire = sac
                lead.save(update_fields=champs + ['web_questionnaire'])


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0124_ciq402_client_entreprise'),
    ]

    operations = [
        migrations.RunPython(deplacer, migrations.RunPython.noop),
    ]
