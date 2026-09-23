from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from enrollments.models import CandidatoAprovado, PeriodoMatricula
from .models import AdminProfile, ParametrosSistema


class AdminAuthorizationTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='evaluator', password='admin-password', is_staff=True,
            first_name='Avaliador', last_name='Teste', email='evaluator@example.test',
        )
        self.profile = AdminProfile.objects.create(user=self.admin, role='avaliador')
        self.super_admin = User.objects.create_user(username='super-admin', password='super-password', is_staff=True)
        AdminProfile.objects.create(user=self.super_admin, role='super_admin')
        self.root = User.objects.create_superuser(username='django-root', password='root-password')
        self.candidate_user = User.objects.create_user(username='candidate', password='candidate-password')
        period = PeriodoMatricula.objects.create(
            nome='Teste', programa='PPEB', data_abertura='2026-01-01', data_fechamento='2026-12-31',
        )
        CandidatoAprovado.objects.create(
            user=self.candidate_user, periodo=period, nome='Candidato', cpf='00000000000', inscricao='candidate',
        )

    def authenticate(self, user):
        token = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def invitation(self, email='invited@example.test', role='avaliador'):
        return {'email': email, 'first_name': 'Convidado', 'last_name': 'Teste', 'role': role}

    def test_administrative_login_allows_evaluator_super_admin_and_django_superuser(self):
        for user, password in [(self.admin, 'admin-password'), (self.super_admin, 'super-password'), (self.root, 'root-password')]:
            with self.subTest(account=user.username):
                response = self.client.post('/api/token/', {'username': user.username, 'password': password}, format='json')
                self.assertEqual(response.status_code, 200)
                self.assertIn('access', response.data)
                self.assertIn('refresh', response.data)

    def test_administrative_login_rejects_candidate_wrong_password_and_inactive_admin(self):
        self.assertEqual(self.client.post('/api/token/', {'username': 'candidate', 'password': 'candidate-password'}).status_code, 401)
        self.assertEqual(self.client.post('/api/token/', {'username': 'evaluator', 'password': 'wrong'}).status_code, 401)
        self.admin.is_active = False
        self.admin.save()
        self.assertEqual(self.client.post('/api/token/', {'username': 'evaluator', 'password': 'admin-password'}).status_code, 401)

    def test_candidate_and_anonymous_cannot_access_configurations(self):
        endpoints = [
            ('get', '/api/configuracoes/perfil/'),
            ('patch', '/api/configuracoes/perfil/'),
            ('post', '/api/configuracoes/perfil/senha/'),
            ('get', '/api/configuracoes/admins/'),
            ('post', '/api/configuracoes/admins/'),
            ('patch', f'/api/configuracoes/admins/{self.admin.pk}/'),
            ('delete', f'/api/configuracoes/admins/{self.admin.pk}/'),
            ('get', '/api/configuracoes/parametros/'),
            ('patch', '/api/configuracoes/parametros/'),
        ]
        for user, expected in [(None, 401), (self.candidate_user, 403)]:
            self.client.credentials()
            if user:
                self.authenticate(user)
            for method, url in endpoints:
                with self.subTest(user=user is not None, method=method, url=url):
                    self.assertEqual(getattr(self.client, method)(url).status_code, expected)
        self.assertFalse(AdminProfile.objects.filter(user=self.candidate_user).exists())

    def test_evaluator_can_read_admins_and_update_operational_parameters(self):
        self.authenticate(self.admin)
        self.assertEqual(self.client.get('/api/configuracoes/admins/').status_code, 200)
        response = self.client.get('/api/configuracoes/parametros/')
        self.assertEqual(response.status_code, 200)
        data = dict(response.data)
        data.update(max_candidatos_por_periodo=250, aceitar_novas_inscricoes=False, tema='dark')
        response = self.client.patch('/api/configuracoes/parametros/', data, format='json')
        self.assertEqual(response.status_code, 200)
        params = ParametrosSistema.get()
        self.assertEqual(params.max_candidatos_por_periodo, 250)
        self.assertFalse(params.aceitar_novas_inscricoes)
        self.assertEqual(params.tema, 'dark')

    def test_evaluator_cannot_create_disable_or_change_admin_roles(self):
        self.authenticate(self.admin)
        before = User.objects.count()
        self.assertEqual(self.client.post('/api/configuracoes/admins/', self.invitation(), format='json').status_code, 403)
        for user in [self.admin, self.super_admin]:
            url = f'/api/configuracoes/admins/{user.pk}/'
            self.assertEqual(self.client.patch(url, {'role': 'super_admin'}, format='json').status_code, 403)
            self.assertEqual(self.client.delete(url).status_code, 403)
        self.assertEqual(User.objects.count(), before)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.role, 'avaliador')
        self.super_admin.refresh_from_db()
        self.assertTrue(self.super_admin.is_active)

    def test_admin_can_update_only_own_profile_and_password(self):
        self.authenticate(self.admin)
        response = self.client.patch('/api/configuracoes/perfil/', {'first_name': 'Atualizado', 'email': 'updated@example.test'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.admin.refresh_from_db()
        self.super_admin.refresh_from_db()
        self.assertEqual(self.admin.first_name, 'Atualizado')
        self.assertNotEqual(self.super_admin.first_name, 'Atualizado')
        response = self.client.post('/api/configuracoes/perfil/senha/', {
            'senha_atual': 'admin-password', 'nova_senha': 'new-admin-password', 'confirmar_senha': 'new-admin-password',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password('new-admin-password'))
        self.assertTrue(self.super_admin.check_password('super-password'))

    def test_profile_and_parameters_cannot_be_used_to_escalate_privileges(self):
        self.authenticate(self.admin)
        ParametrosSistema.get()
        for path in ['perfil/', 'parametros/']:
            for payload in [
                {'role': 'super_admin'}, {'is_staff': True}, {'is_superuser': True},
                {'user': {'id': self.super_admin.pk, 'is_superuser': True}},
                {'user_id': self.super_admin.pk},
            ]:
                with self.subTest(path=path, fields=list(payload)):
                    self.assertEqual(self.client.patch('/api/configuracoes/' + path, payload, format='json').status_code, 400)
        self.admin.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertFalse(self.admin.is_superuser)
        self.assertEqual(self.profile.role, 'avaliador')

    def test_super_admin_manages_admins_and_can_promote_and_demote(self):
        self.authenticate(self.super_admin)
        response = self.client.post('/api/configuracoes/admins/', self.invitation(), format='json')
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username='invited@example.test')
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)
        url = f'/api/configuracoes/admins/{user.pk}/'
        for role in ['super_admin', 'avaliador']:
            self.assertEqual(self.client.patch(url, {'role': role}, format='json').status_code, 200)
            self.assertEqual(AdminProfile.objects.get(user=user).role, role)
        self.assertEqual(self.client.delete(url).status_code, 204)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_role_endpoint_cannot_modify_candidate_or_django_flags(self):
        self.authenticate(self.super_admin)
        AdminProfile.objects.create(user=self.candidate_user, role='avaliador')
        self.assertEqual(self.client.patch(f'/api/configuracoes/admins/{self.candidate_user.pk}/', {'role': 'super_admin'}, format='json').status_code, 404)
        self.assertEqual(self.client.patch(f'/api/configuracoes/admins/{self.admin.pk}/', {'role': 'super_admin', 'is_superuser': True}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(f'/api/configuracoes/admins/{self.admin.pk}/', {'role': 'invalid'}, format='json').status_code, 400)
        self.assertEqual(self.client.patch('/api/configuracoes/perfil/', {'role': 'avaliador'}, format='json').status_code, 400)

    def test_existing_self_deactivation_protection_is_preserved(self):
        self.authenticate(self.super_admin)
        self.assertEqual(self.client.delete(f'/api/configuracoes/admins/{self.super_admin.pk}/').status_code, 400)

    def test_role_and_staff_changes_apply_to_already_issued_tokens(self):
        self.authenticate(self.admin)
        url = '/api/configuracoes/admins/'
        self.assertEqual(self.client.post(url, self.invitation(), format='json').status_code, 403)
        self.profile.role = 'super_admin'
        self.profile.save()
        self.assertEqual(self.client.post(url, self.invitation(), format='json').status_code, 201)
        self.profile.role = 'avaliador'
        self.profile.save()
        self.assertEqual(self.client.post(url, self.invitation('another@example.test'), format='json').status_code, 403)
        self.admin.is_staff = False
        self.admin.save()
        self.assertEqual(self.client.get('/api/configuracoes/parametros/').status_code, 403)

    def test_staff_without_profile_is_never_automatically_promoted(self):
        user = User.objects.create_user(username='legacy-staff', password='legacy-password', is_staff=True)
        self.authenticate(user)
        self.assertEqual(self.client.get('/api/configuracoes/perfil/').status_code, 200)
        self.assertEqual(AdminProfile.objects.get(user=user).role, 'avaliador')
        self.assertEqual(self.client.patch('/api/configuracoes/parametros/', {'tema': 'dark'}, format='json').status_code, 200)
        self.assertEqual(self.client.post('/api/configuracoes/admins/', self.invitation(), format='json').status_code, 403)

    def test_django_superuser_without_profile_retains_management_access(self):
        self.authenticate(self.root)
        self.assertFalse(AdminProfile.objects.filter(user=self.root).exists())
        self.assertEqual(self.client.post('/api/configuracoes/admins/', self.invitation(), format='json').status_code, 201)

    def test_candidate_with_forged_super_admin_profile_is_still_not_admin(self):
        AdminProfile.objects.create(user=self.candidate_user, role='super_admin')
        self.authenticate(self.candidate_user)
        self.assertEqual(self.client.get('/api/configuracoes/admins/').status_code, 403)
        self.assertEqual(self.client.post('/api/configuracoes/admins/', self.invitation(), format='json').status_code, 403)
