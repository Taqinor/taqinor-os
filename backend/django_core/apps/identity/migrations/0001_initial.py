import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0020_company_benchmarking_opt_in'),
        ('roles', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='IdentityProvider',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('protocol', models.CharField(
                    choices=[('saml', 'SAML 2.0'), ('oidc', 'OpenID Connect')],
                    help_text='Protocole de fédération (SAML 2.0 ou OIDC).',
                    max_length=8)),
                ('nom', models.CharField(
                    help_text="Libellé lisible de l'IdP (ex. « Azure AD », "
                              "« Okta »).",
                    max_length=120)),
                ('actif', models.BooleanField(
                    default=False,
                    help_text="Active l'IdP pour la connexion SSO. OFF par "
                              'défaut = login local inchangé.')),
                ('metadata_url', models.URLField(
                    blank=True, default='',
                    help_text='URL de métadonnées SAML ou de découverte OIDC '
                              '(.well-known/openid-configuration).',
                    max_length=500)),
                ('metadata_xml', models.TextField(
                    blank=True, default='',
                    help_text='Métadonnées SAML collées (alternative à '
                              'metadata_url).')),
                ('entity_id', models.CharField(
                    blank=True, default='',
                    help_text="EntityID / Issuer de l'IdP (SAML) ou issuer "
                              'OIDC.',
                    max_length=255)),
                ('sso_url', models.URLField(
                    blank=True, default='',
                    help_text="URL de connexion de l'IdP (SAML SSO / OIDC "
                              'authorization_endpoint).',
                    max_length=500)),
                ('x509_cert', models.TextField(
                    blank=True, default='',
                    help_text="Certificat X.509 (PEM) de l'IdP servant à "
                              'valider la signature des assertions SAML / '
                              'id_token.')),
                ('client_id', models.CharField(
                    blank=True, default='',
                    help_text="client_id OIDC enregistré auprès de l'IdP.",
                    max_length=255)),
                ('client_secret', models.CharField(
                    blank=True, default='',
                    help_text='client_secret OIDC (par tenant). Vide pour un '
                              'flow public PKCE seul.',
                    max_length=255)),
                ('attribute_map', models.JSONField(
                    blank=True, default=dict,
                    help_text='Correspondance attribut IdP → champ utilisateur '
                              '(email/nom/prenom/groupes).')),
                ('auto_provision', models.BooleanField(
                    default=False,
                    help_text="Crée automatiquement l'utilisateur absent à la "
                              'première connexion SSO (auto-provisioning).')),
                ('enforce_sso', models.BooleanField(
                    default=False,
                    help_text='Interdit le login local (mot de passe) une fois '
                              'activé — les comptes doivent passer par le SSO '
                              '(NTSEC4).')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='identity_providers',
                    to='authentication.company')),
                ('default_role', models.ForeignKey(
                    blank=True, null=True,
                    help_text='Rôle attribué par défaut à un compte SSO '
                              'auto-provisionné.',
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to='roles.role')),
            ],
            options={
                'verbose_name': "Fournisseur d'identité (SSO)",
                'verbose_name_plural': "Fournisseurs d'identité (SSO)",
                'ordering': ['company', 'protocol', 'nom'],
            },
        ),
        migrations.AddConstraint(
            model_name='identityprovider',
            constraint=models.UniqueConstraint(
                condition=models.Q(('actif', True)),
                fields=('company', 'protocol'),
                name='identity_one_active_idp_per_company_protocol'),
        ),
    ]
