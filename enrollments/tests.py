from datetime import timedelta
import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from configuracoes.models import AdminProfile, ParametrosSistema
from .models import CandidatoAprovado, DocumentoCandidato, PeriodoMatricula


class EnrollmentAuthTests(APITestCase):
    def submission_data(self):
        return {
            'full_name': 'Candidato Atualizado', 'cpf': '52998224725',
            'date_of_birth': '1990-01-01', 'dispatch_date': '2015-01-01',
            'program_level': 'MESTRADO', 'email': 'candidate@example.test',
            'phone': '91999999999', 'emergency_contact_1': 'Contato Um',
            'emergency_phone_1': '91999999998', 'emergency_contact_2': 'Contato Dois',
            'emergency_phone_2': '91999999997', 'zip_code': '66000000',
            'street': 'Rua de Teste', 'number': '1', 'neighbourhood': 'Centro',
            'city': 'Belem', 'state': 'PA', 'institution': 'Instituicao Teste',
            'course': 'Educacao', 'graduation_year': '2020',
            'lattes_url': 'https://example.test/curriculo', 'research_area': 'Educacao',
            'bank_name': 'Banco Teste', 'compe_code': '001', 'agency': '1234',
            'account_number': '12345', 'bank_account_type': 'CC',
            'military_dispatch_date': None,
        }

    def test_incomplete_submission_does_not_finalize(self):
        self.authenticate(self.owner)
        response = self.client.post('/api/enrollments/submit/', {}, format='json')
        self.assertEqual(response.status_code, 400)
        self.candidate.refresh_from_db()
        self.assertFalse(self.candidate.formulario_enviado)

    def test_submission_rejects_invalid_personal_and_bank_fields(self):
        self.authenticate(self.owner)
        for field, value in [('cpf', '00000000000'), ('date_of_birth', '2099-01-01'),
                             ('program_level', 'INVALID'), ('bank_account_type', 'INVALID'),
                             ('compe_code', 'abc'), ('graduation_year', '2099')]:
            data = {**self.submission_data(), field: value}
            response = self.client.post('/api/enrollments/submit/', data, format='json')
            self.assertEqual(response.status_code, 400)
            self.assertIn(field, response.data)
        self.candidate.refresh_from_db()
        self.assertFalse(self.candidate.formulario_enviado)

    def test_closed_registrations_do_not_finalize_candidate(self):
        ParametrosSistema.objects.create(aceitar_novas_inscricoes=False)
        self.authenticate(self.owner)
        self.assertEqual(self.client.post('/api/enrollments/submit/', {}, format='json').status_code, 400)
        self.candidate.refresh_from_db()
        self.assertFalse(self.candidate.formulario_enviado)

    def test_import_respects_configured_capacity(self):
        ParametrosSistema.objects.create(max_candidatos_por_periodo=1)
        self.authenticate(self.admin)
        count = PeriodoMatricula.objects.count()
        response = self.import_csv('nome,cpf,inscricao\nTeste A,12345678901,cap-a\nTeste B,12345678902,cap-b')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(PeriodoMatricula.objects.count(), count)

    def test_invalid_status_never_changes_record(self):
        self.authenticate(self.admin)
        for value in [None, 2, '', 'INVALID']:
            self.assertEqual(self.client.patch(self.candidate_url('status/'), {'status': value}, format='json').status_code, 400)
        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.status, 'PENDING')

    def test_csv_errors_do_not_create_empty_periods_or_users(self):
        self.authenticate(self.admin)
        counts = (PeriodoMatricula.objects.count(), User.objects.count())
        for text in ['', 'wrong,headers\nfoo,bar', 'nome,cpf,inscricao\nNome,,']:
            self.assertEqual(self.import_csv(text).status_code, 400)
            self.assertEqual((PeriodoMatricula.objects.count(), User.objects.count()), counts)

    def test_csv_database_failure_rolls_back_new_accounts_and_period(self):
        self.authenticate(self.admin)
        counts = (PeriodoMatricula.objects.count(), User.objects.count())
        with patch('enrollments.views.CandidatoAprovado.objects.create', side_effect=RuntimeError('simulated storage failure')):
            with self.assertRaises(RuntimeError):
                self.import_csv('nome,cpf,inscricao\nTeste,12345678901,rollback')
        self.assertEqual((PeriodoMatricula.objects.count(), User.objects.count()), counts)

    def test_period_rejects_reversed_dates_including_patch(self):
        self.authenticate(self.admin)
        response = self.client.patch(f'/api/enrollments/periodos/{self.period.pk}/', {'data_fim': '2025-01-01'}, format='json')
        self.assertEqual(response.status_code, 400)
        response = self.client.post('/api/enrollments/periodos/', {
            'titulo': 'Inválido', 'programa': 'PPEB', 'data_inicio': '2026-12-31', 'data_fim': '2026-01-01',
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_multipart_submission_validates_files_before_finalizing(self):
        self.authenticate(self.owner)
        data = {**self.submission_data(), 'military_dispatch_date': ''}
        invalid = SimpleUploadedFile('bad.pdf', b'not a PDF')
        response = self.client.post('/api/enrollments/submit/', {'payload': json.dumps(data), 'cpf': invalid}, format='multipart')
        self.assertEqual(response.status_code, 400)
        self.candidate.refresh_from_db()
        self.assertFalse(self.candidate.formulario_enviado)
        valid = SimpleUploadedFile('good.pdf', b'%PDF-1.4 example')
        response = self.client.post('/api/enrollments/submit/', {'payload': json.dumps(data), 'cpf': valid}, format='multipart')
        self.assertEqual(response.status_code, 200)
        self.candidate.refresh_from_db()
        self.assertTrue(self.candidate.formulario_enviado)
        self.assertIsNone(self.candidate.military_dispatch_date)
        self.assertTrue(self.candidate.documentos.filter(tipo='cpf').exists())

    def test_password_whitespace_is_significant(self):
        self.owner.set_password(' password with spaces ')
        self.owner.save()
        response = self.client.post('/api/enrollments/candidato/login/', {
            'inscricao': self.owner.username, 'senha': ' password with spaces ',
        }, format='json')
        self.assertEqual(response.status_code, 200)

    @override_settings(AUTH_PASSWORD_VALIDATORS=[{'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'}])
    def test_candidate_password_change_uses_django_validators(self):
        self.authenticate(self.owner)
        response = self.client.post('/api/enrollments/candidato/trocar-senha/', {
            'senha_atual': 'candidate-password', 'nova_senha': 'abc',
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.check_password('candidate-password'))

    def setUp(self):
        self.period = PeriodoMatricula.objects.create(
            nome='Periodo de teste', programa='PPEB',
            data_abertura='2026-01-01', data_fechamento='2026-12-31',
        )
        self.owner = User.objects.create_user(username='candidate-a', password='candidate-password')
        self.other = User.objects.create_user(username='candidate-b', password='other-password')
        self.candidate = CandidatoAprovado.objects.create(
            periodo=self.period, user=self.owner, nome='Candidato A',
            cpf='00000000000', inscricao='candidate-a',
        )
        self.other_candidate = CandidatoAprovado.objects.create(
            periodo=self.period, user=self.other, nome='Candidato B',
            cpf='00000000001', inscricao='candidate-b',
        )
        self.admin = User.objects.create_user(username='evaluator', password='admin-password', is_staff=True)
        AdminProfile.objects.create(user=self.admin, role='avaliador')
        self.document = DocumentoCandidato.objects.create(
            candidato=self.candidate, tipo='rg',
            arquivo=SimpleUploadedFile('test.pdf', b'%PDF-1.4 test document', content_type='application/pdf'),
        )
        for tipo in ['diploma', 'historico', 'cpf', 'titulo', 'comp_votacao', 'comp_residencia']:
            DocumentoCandidato.objects.create(
                candidato=self.candidate, tipo=tipo,
                arquivo=SimpleUploadedFile(f'{tipo}.pdf', b'%PDF-1.4 test', content_type='application/pdf'),
            )

    def authenticate(self, user):
        token = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def candidate_url(self, suffix='', candidate=None):
        candidate = candidate or self.candidate
        return f'/api/enrollments/{candidate.pk}/{suffix}'

    def test_submit_enrollment_success(self):
        self.authenticate(self.owner)
        response = self.client.post('/api/enrollments/submit/', self.submission_data(), format='json')
        self.assertEqual(response.status_code, 200)
        self.candidate.refresh_from_db()
        self.other_candidate.refresh_from_db()
        self.assertEqual(self.candidate.nome, 'Candidato Atualizado')
        self.assertEqual(self.candidate.status, 'AGUARDANDO')
        self.assertTrue(self.candidate.formulario_enviado)
        self.assertEqual(self.other_candidate.nome, 'Candidato B')
        self.assertFalse(self.other_candidate.formulario_enviado)
        self.assertEqual(self.client.post('/api/enrollments/submit/', {}, format='json').status_code, 400)

    def test_candidate_can_read_own_data_documents_and_receipt(self):
        self.authenticate(self.owner)
        for suffix in ['', 'documentos/', 'comprovante-dados/', 'comprovante/']:
            with self.subTest(suffix=suffix):
                response = self.client.get(self.candidate_url(suffix))
                self.assertEqual(response.status_code, 200)
                response.close()
        self.assertEqual(self.client.get('/api/enrollments/candidato/situacao/').status_code, 200)

    def test_candidate_cannot_read_another_candidate(self):
        self.authenticate(self.other)
        for suffix in ['', 'documentos/', 'comprovante-dados/', 'comprovante/']:
            with self.subTest(suffix=suffix):
                self.assertEqual(self.client.get(self.candidate_url(suffix)).status_code, 404)

    def test_candidate_upload_is_scoped_to_owner(self):
        self.authenticate(self.owner)
        file = SimpleUploadedFile('own.pdf', b'%PDF-1.4 own', content_type='application/pdf')
        self.assertEqual(self.client.post(self.candidate_url('documentos/'), {'cpf': file}).status_code, 201)
        self.authenticate(self.other)
        before = DocumentoCandidato.objects.count()
        file = SimpleUploadedFile('other.pdf', b'%PDF-1.4 other', content_type='application/pdf')
        self.assertEqual(self.client.post(self.candidate_url('documentos/'), {'cpf': file}).status_code, 404)
        self.assertEqual(DocumentoCandidato.objects.count(), before)

    def test_protected_candidate_fields_are_rejected_without_changes(self):
        self.authenticate(self.owner)
        fields = {
            'user': self.other.pk, 'user_id': self.other.pk,
            'periodo': self.period.pk, 'periodo_id': self.period.pk,
            'inscricao': 'another-login', 'status': 'APROVADO',
            'formulario_enviado': True, 'is_first_access': False,
            'role': 'super_admin', 'is_staff': True, 'is_superuser': True,
        }
        for name, value in fields.items():
            with self.subTest(field=name):
                response = self.client.post('/api/enrollments/submit/', {name: value}, format='json')
                self.assertEqual(response.status_code, 400)
                self.assertIn(name, response.data)
        self.candidate.refresh_from_db()
        self.owner.refresh_from_db()
        self.assertEqual(self.candidate.user_id, self.owner.pk)
        self.assertEqual(self.candidate.inscricao, 'candidate-a')
        self.assertEqual(self.candidate.status, 'PENDING')
        self.assertFalse(self.candidate.formulario_enviado)
        self.assertTrue(self.candidate.is_first_access)
        self.assertFalse(self.owner.is_staff)

    def test_candidate_has_no_administrative_access(self):
        self.authenticate(self.owner)
        for method, url in [
            ('get', '/api/enrollments/list/'),
            ('get', '/api/enrollments/periodos/'),
            ('get', f'/api/enrollments/periodos/{self.period.pk}/'),
            ('post', '/api/enrollments/periodos/'),
            ('patch', f'/api/enrollments/periodos/{self.period.pk}/'),
            ('post', '/api/enrollments/import/'),
            ('patch', self.candidate_url('status/')),
        ]:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 403)

    def test_evaluator_can_read_and_review_all_candidates(self):
        self.authenticate(self.admin)
        self.assertEqual(len(self.client.get('/api/enrollments/list/').data), 2)
        for candidate in [self.candidate, self.other_candidate]:
            for suffix in ['', 'documentos/', 'comprovante-dados/', 'comprovante/']:
                response = self.client.get(self.candidate_url(suffix, candidate))
                self.assertEqual(response.status_code, 200)
                response.close()
            for status in ['aprovado', 'rejeitado']:
                response = self.client.patch(self.candidate_url('status/', candidate), {'status': status}, format='json')
                self.assertEqual(response.status_code, 200)
                candidate.refresh_from_db()
                self.assertEqual(candidate.status, status.upper())

    def test_evaluator_can_create_edit_and_reopen_periods(self):
        self.authenticate(self.admin)
        response = self.client.post('/api/enrollments/periodos/', {
            'titulo': 'Novo periodo', 'programa': 'PPEB',
            'data_inicio': '2026-01-01', 'data_fim': '2026-01-02',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        url = f"/api/enrollments/periodos/{response.data['id']}/"
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.patch(url, {'titulo': 'Editado', 'data_fim': '2026-12-31'}, format='json').status_code, 200)
        self.assertEqual(self.client.delete(url).status_code, 405)

    def import_csv(self, text):
        return self.client.post('/api/enrollments/import/', {
            'titulo': 'Importacao de teste', 'program': 'PPEB',
            'data_inicio': '2026-01-01', 'data_fim': '2026-12-31',
            'file': SimpleUploadedFile('test.csv', text.encode(), content_type='text/csv'),
        })

    def test_evaluator_can_import_candidates(self):
        self.authenticate(self.admin)
        response = self.import_csv('nome,cpf,inscricao,email\nImportado,00000000002,new-candidate,new@example.test\n')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['candidatos_importados'], 1)
        candidate = CandidatoAprovado.objects.get(inscricao='new-candidate')
        self.assertFalse(candidate.user.is_staff)
        self.assertTrue(candidate.user.check_password('00000000002'))

    def test_import_cannot_overwrite_existing_accounts(self):
        self.authenticate(self.admin)
        for user in [self.admin, self.owner]:
            with self.subTest(account=user.username):
                original_password = user.password
                response = self.import_csv(f'nome,cpf,inscricao,email\nDuplicado,00000000003,{user.username},duplicate@example.test\n')
                self.assertEqual(response.status_code, 400)
                self.assertTrue(response.data['erros'])
                user.refresh_from_db()
                self.assertEqual(user.password, original_password)
        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.user_id, self.owner.pk)

    def test_admin_cannot_use_candidate_write_endpoints(self):
        self.authenticate(self.admin)
        for url in ['/api/enrollments/submit/', '/api/enrollments/candidato/trocar-senha/', self.candidate_url('documentos/')]:
            self.assertEqual(self.client.post(url).status_code, 403)

    def test_candidate_login_and_first_access_contract(self):
        response = self.client.post('/api/enrollments/candidato/login/', {
            'inscricao': self.candidate.inscricao, 'senha': 'candidate-password',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_first_access'])
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(str(AccessToken(response.data['access'])['user_id']), str(self.owner.pk))
        self.assertEqual(self.client.post('/api/token/refresh/', {'refresh': response.data['refresh']}, format='json').status_code, 200)

    def test_candidate_login_rejects_wrong_password_inactive_and_admin_accounts(self):
        url = '/api/enrollments/candidato/login/'
        self.assertEqual(self.client.post(url, {'inscricao': 'candidate-a', 'senha': 'wrong'}).status_code, 400)
        for flag in ['is_active', 'is_staff', 'is_superuser']:
            with self.subTest(flag=flag):
                setattr(self.owner, flag, flag != 'is_active')
                self.owner.save()
                self.assertEqual(self.client.post(url, {'inscricao': 'candidate-a', 'senha': 'candidate-password'}).status_code, 400)
                setattr(self.owner, flag, flag == 'is_active')
                self.owner.save()

    def test_login_uses_existing_candidate_link_not_username_lookup(self):
        self.owner.username = 'renamed-account'
        self.owner.save()
        User.objects.create_user(username='candidate-a', password='unrelated-password', is_staff=True)
        url = '/api/enrollments/candidato/login/'
        self.assertEqual(self.client.post(url, {'inscricao': 'candidate-a', 'senha': 'unrelated-password'}).status_code, 400)
        self.assertEqual(self.client.post(url, {'inscricao': 'candidate-a', 'senha': 'candidate-password'}).status_code, 200)

    def test_legacy_first_access_creates_only_its_own_account_after_valid_credentials(self):
        candidate = CandidatoAprovado.objects.create(
            periodo=self.period, nome='Legado', cpf='00000000004', inscricao='legacy-candidate',
        )
        url = '/api/enrollments/candidato/login/'
        self.assertEqual(self.client.post(url, {'inscricao': candidate.inscricao, 'senha': 'wrong'}).status_code, 400)
        self.assertFalse(User.objects.filter(username=candidate.inscricao).exists())
        self.assertEqual(self.client.post(url, {'inscricao': candidate.inscricao, 'senha': candidate.cpf}).status_code, 200)
        candidate.refresh_from_db()
        self.assertIsNotNone(candidate.user_id)
        self.assertFalse(candidate.user.is_staff)

    def test_legacy_login_cannot_adopt_existing_account(self):
        candidate = CandidatoAprovado.objects.create(
            periodo=self.period, nome='Conflito', cpf='00000000005', inscricao=self.admin.username,
        )
        response = self.client.post('/api/enrollments/candidato/login/', {'inscricao': candidate.inscricao, 'senha': candidate.cpf})
        self.assertEqual(response.status_code, 400)
        candidate.refresh_from_db()
        self.assertIsNone(candidate.user_id)

    def test_password_change_affects_only_owner(self):
        self.authenticate(self.owner)
        url = '/api/enrollments/candidato/trocar-senha/'
        self.assertEqual(self.client.post(url, {'senha_atual': 'wrong', 'nova_senha': 'new-password'}).status_code, 400)
        self.assertEqual(self.client.post(url, {'senha_atual': 'candidate-password'}).status_code, 400)
        self.assertEqual(self.client.post(url, {'senha_atual': 'candidate-password', 'nova_senha': 'new-password'}).status_code, 200)
        self.owner.refresh_from_db()
        self.other.refresh_from_db()
        self.candidate.refresh_from_db()
        self.assertTrue(self.owner.check_password('new-password'))
        self.assertTrue(self.other.check_password('other-password'))
        self.assertFalse(self.candidate.is_first_access)

    def test_direct_media_requires_authentication_and_ownership_even_in_debug(self):
        url = self.document.arquivo.url
        for debug in [False, True]:
            with override_settings(DEBUG=debug):
                self.client.credentials()
                self.assertEqual(self.client.get(url).status_code, 401)
                self.authenticate(self.other)
                self.assertEqual(self.client.get(url).status_code, 404)
                for user in [self.owner, self.admin]:
                    self.authenticate(user)
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response['Cache-Control'], 'private, no-store')
                    self.assertTrue(b''.join(response.streaming_content).startswith(b'%PDF'))
                    response.close()
                self.authenticate(self.other)
                alias = '/media/./' + self.document.arquivo.name
                self.assertNotEqual(self.client.get(alias).status_code, 200)

    def test_missing_invalid_expired_and_deactivated_tokens(self):
        url = self.candidate_url()
        self.assertEqual(self.client.get(url).status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid-token')
        self.assertEqual(self.client.get(url).status_code, 401)
        expired = RefreshToken.for_user(self.owner).access_token
        expired.set_exp(from_time=timezone.now() - timedelta(hours=1), lifetime=timedelta(seconds=1))
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {expired}')
        self.assertEqual(self.client.get(url).status_code, 401)
        self.authenticate(self.owner)
        self.owner.is_active = False
        self.owner.save()
        self.assertEqual(self.client.get(url).status_code, 401)
