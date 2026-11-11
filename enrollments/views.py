import csv
import io
import json
import os

from django.http import FileResponse, Http404
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework.exceptions import ValidationError
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

from rest_framework import generics, status
from rest_framework.generics import RetrieveAPIView, ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny
from core.permissions import IsAdmin, IsCandidate, IsCandidateOrAdminReadOnly, is_admin
from configuracoes.models import AdminProfile, ParametrosSistema

from .models import PeriodoMatricula, CandidatoAprovado, DocumentoCandidato
from .serializers import CandidatoAprovadoSerializer, LoginCandidatoSerializer, PeriodoMatriculaSerializer


def visible_candidates(user):
    queryset = CandidatoAprovado.objects.select_related('periodo')
    return queryset if is_admin(user) else queryset.filter(user=user)


DOCUMENT_TYPES = {'diploma', 'historico', 'rg', 'cpf', 'titulo', 'comp_votacao', 'comp_residencia', 'reservista'}
REQUIRED_DOCUMENT_TYPES = DOCUMENT_TYPES - {'reservista'}


def validate_documents(files):
    if set(files) - DOCUMENT_TYPES:
        raise ValidationError({'arquivos': 'Tipo de documento desconhecido.'})
    for tipo, arquivo in files.items():
        header = arquivo.read(5)
        arquivo.seek(0)
        if arquivo.size > 10 * 1024 * 1024 or header != b'%PDF-':
            raise ValidationError({tipo: 'Envie um PDF de até 10 MB.'})


def save_documents(candidato, files):
    # Keep previous files: uploads never delete historical documents.
    for tipo, arquivo in files.items():
        DocumentoCandidato.objects.create(candidato=candidato, tipo=tipo, arquivo=arquivo)


# ── 1. Submeter formulário (PATCH no próprio CandidatoAprovado) ───────────────
class EnrollmentCreateView(APIView):
    permission_classes = [IsCandidate]

    @transaction.atomic
    def post(self, request):
        try:
            candidato = CandidatoAprovado.objects.select_for_update().get(user=request.user)
        except CandidatoAprovado.DoesNotExist:
            return Response({'erro': 'Candidato não encontrado.'}, status=404)

        if candidato.formulario_enviado:
            return Response(
                {'erro': 'Você já enviou sua inscrição. Acompanhe pelo seu painel.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        params = ParametrosSistema.objects.filter(pk=1).first()
        if params and not params.aceitar_novas_inscricoes:
            raise ValidationError({'erro': 'Novas inscrições estão temporariamente suspensas.'})

        data = request.data
        if 'payload' in request.data:
            try:
                data = json.loads(request.data['payload'])
            except (ValueError, TypeError):
                raise ValidationError({'payload': 'JSON inválido.'})
        validate_documents(request.FILES)
        serializer = CandidatoAprovadoSerializer(candidato, data=data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        required_fields = (
            'nome', 'cpf', 'date_of_birth', 'dispatch_date', 'program_level',
            'email', 'phone', 'emergency_contact_1', 'emergency_phone_1',
            'emergency_contact_2', 'emergency_phone_2', 'zip_code', 'street',
            'number', 'neighbourhood', 'city', 'state', 'institution', 'course',
            'graduation_year', 'lattes_url', 'research_area', 'bank_name',
            'compe_code', 'agency', 'account_number', 'bank_account_type',
        )
        missing = {field: 'Campo obrigatório.' for field in required_fields if not serializer.validated_data.get(field)}
        if missing:
            raise ValidationError(missing)
        available_documents = set(candidato.documentos.values_list('tipo', flat=True)) | set(request.FILES)
        if REQUIRED_DOCUMENT_TYPES - available_documents:
            raise ValidationError({'documentos': 'Anexe todos os PDFs obrigatórios.'})

        save_documents(candidato, request.FILES)
        serializer.save(formulario_enviado=True, status='AGUARDANDO')
        return Response(serializer.data, status=status.HTTP_200_OK)


# ── 2. Listar candidatos para o admin ─────────────────────────────────────────
class EnrollmentListView(generics.ListAPIView):
    serializer_class = CandidatoAprovadoSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        qs = CandidatoAprovado.objects.prefetch_related('documentos').order_by('-id')
        programa = self.request.query_params.get('program')
        if programa:
            qs = qs.filter(periodo__programa__iexact=programa)
        return qs


# ── 3. Login do candidato ─────────────────────────────────────────────────────
class LoginCandidatoView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginCandidatoSerializer(data=request.data)
        if serializer.is_valid():
            return Response(serializer.validated_data)
        return Response(serializer.errors, status=400)


# ── 4. Trocar senha ───────────────────────────────────────────────────────────
class TrocarSenhaView(APIView):
    permission_classes = [IsCandidate]

    @transaction.atomic
    def post(self, request):
        user = request.user
        senha_atual = request.data.get('senha_atual')
        nova_senha = request.data.get('nova_senha')

        if not isinstance(senha_atual, str) or not isinstance(nova_senha, str) or not nova_senha:
            return Response({'error': 'Informe a senha atual e a nova senha.'}, status=400)

        if not user.check_password(senha_atual):
            return Response({"error": "A senha atual está incorreta."}, status=400)

        try:
            validate_password(nova_senha, user)
        except DjangoValidationError as exc:
            return Response({'nova_senha': exc.messages}, status=400)
        user.set_password(nova_senha)
        user.save()

        candidato = user.candidato_aprovado
        candidato.is_first_access = False
        candidato.save(update_fields=['is_first_access'])

        return Response({"message": "Senha atualizada com sucesso!"})


# ── 5. Importar CSV e criar período ───────────────────────────────────────────
class ImportarCandidatosView(APIView):
    permission_classes = [IsAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        titulo      = request.data.get('titulo', '').strip()
        descricao   = request.data.get('descricao', '').strip()
        programa    = request.data.get('program', '').strip()
        data_inicio = request.data.get('data_inicio')
        data_fim    = request.data.get('data_fim')
        arquivo     = request.FILES.get('file')

        if not all([titulo, programa, data_inicio, data_fim, arquivo]):
            return Response(
                {'erro': 'Campos obrigatórios ausentes', 'detalhes': {
                    'titulo': bool(titulo), 'program': bool(programa),
                    'data_inicio': bool(data_inicio), 'data_fim': bool(data_fim),
                    'file': bool(arquivo),
                }},
                status=status.HTTP_400_BAD_REQUEST
            )

        period_serializer = PeriodoMatriculaSerializer(data={
            'titulo': titulo, 'programa': programa,
            'data_inicio': data_inicio, 'data_fim': data_fim,
        })
        period_serializer.is_valid(raise_exception=True)
        try:
            conteudo = arquivo.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(conteudo))
            if not reader.fieldnames:
                raise ValueError('CSV vazio.')
            reader.fieldnames = [h.strip().lower() for h in reader.fieldnames]
            if not {'nome', 'cpf', 'inscricao'}.issubset(reader.fieldnames):
                raise ValueError('Colunas obrigatorias: nome, cpf, inscricao.')
            rows = list(reader)
        except (UnicodeDecodeError, csv.Error, ValueError) as exc:
            raise ValidationError({'file': str(exc)})

        valid_rows, erros, seen = [], [], set()
        for i, linha in enumerate(rows, start=2):
            values = {key: (linha.get(key) or '').strip() for key in ('nome', 'cpf', 'inscricao', 'email')}
            nome, cpf, inscricao = values['nome'], values['cpf'], values['inscricao']
            if not all((nome, cpf, inscricao)):
                erros.append(f'Linha {i}: nome, cpf e inscricao sao obrigatorios')
                continue
            if len(nome) > 255 or len(cpf) > 14 or len(inscricao) > 20:
                erros.append(f'Linha {i}: campo excede o tamanho permitido')
                continue
            if (inscricao in seen or User.objects.filter(username=inscricao).exists()
                    or CandidatoAprovado.objects.filter(inscricao=inscricao).exists()):
                erros.append(f'Linha {i}: inscricao ja vinculada a uma conta ou candidato')
                continue
            seen.add(inscricao)
            valid_rows.append(values)
        if not valid_rows:
            return Response({'erro': 'Nenhum candidato valido.', 'erros': erros}, status=400)

        params = ParametrosSistema.objects.filter(pk=1).first()
        limite = params.max_candidatos_por_periodo if params else 100
        if len(valid_rows) > limite:
            raise ValidationError({'file': f'O limite por período é de {limite} candidatos.'})

        with transaction.atomic():
            periodo = period_serializer.save()
            for values in valid_rows:
                user = User.objects.create_user(username=values['inscricao'], password=values['cpf'])
                CandidatoAprovado.objects.create(periodo=periodo, user=user, **values)

        return Response({
            'sucesso': True, 'periodo_id': periodo.id, 'periodo_nome': periodo.nome,
            'candidatos_importados': len(valid_rows), 'erros': erros,
        }, status=status.HTTP_201_CREATED)


# ── 6. Listar/criar períodos ──────────────────────────────────────────────────
class PeriodoMatriculaListCreateView(generics.ListCreateAPIView):
    serializer_class = PeriodoMatriculaSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        qs = PeriodoMatricula.objects.all().order_by('-id')
        programa = self.request.query_params.get('program')
        if programa:
            qs = qs.filter(programa__iexact=programa)
        return qs


# ── 7. Detalhe/editar período (sem deletar) ───────────────────────────────────
class PeriodoMatriculaDetailView(generics.RetrieveUpdateAPIView):
    queryset = PeriodoMatricula.objects.all()
    serializer_class = PeriodoMatriculaSerializer
    permission_classes = [IsAdmin]
    # RetrieveUpdateAPIView — sem DestroyAPIView, períodos não podem ser excluídos


# ── 8. Atualizar status do candidato ──────────────────────────────────────────
class EnrollmentStatusUpdateView(APIView):
    permission_classes = [IsAdmin]

    def patch(self, request, pk):
        candidato = CandidatoAprovado.objects.filter(pk=pk).first()
        if not candidato:
            return Response({'erro': 'Candidato não encontrado.'}, status=404)

        novo_status = request.data.get('status')
        if not isinstance(novo_status, str) or novo_status.upper() not in dict(CandidatoAprovado.STATUS_CHOICES):
            return Response({'status': 'Status inválido.'}, status=400)
        novo_status = novo_status.upper()
        candidato.status = novo_status
        candidato.save()
        return Response({'id': pk, 'status': candidato.status})


# ── 9. Gerar comprovante PDF ──────────────────────────────────────────────────
class EnrollmentComprovanteView(APIView):
    permission_classes = [IsCandidateOrAdminReadOnly]

    def get(self, request, pk):
        candidato = visible_candidates(request.user).filter(pk=pk).first()
        if not candidato:
            return Response({'erro': 'Candidato não encontrado.'}, status=404)

        tmp = io.BytesIO()
        c = canvas.Canvas(tmp, pagesize=A4)
        width, height = A4

        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, height - 60, "Comprovante de Pré-matrícula")
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, height - 80, f"Programa: {candidato.periodo.programa if candidato.periodo else '—'}")

        y = height - 120
        campos = [
            ("Nome",            candidato.nome),
            ("CPF",             candidato.cpf),
            ("Inscrição",       candidato.inscricao),
            ("E-mail",          candidato.email or '—'),
            ("Nível",           candidato.program_level or '—'),
            ("Instituição",     candidato.institution or '—'),
            ("Curso",           candidato.course or '—'),
            ("Banco",           candidato.bank_name or '—'),
            ("Agência",         candidato.agency or '—'),
            ("Conta",           candidato.account_number or '—'),
            ("Status",          candidato.status or 'Pendente'),
        ]
        for label, valor in campos:
            c.setFont("Helvetica-Bold", 10)
            c.drawString(50, y, f"{label}:")
            c.setFont("Helvetica", 10)
            c.drawString(180, y, str(valor))
            y -= 22

        c.save()
        tmp.seek(0)
        response = FileResponse(tmp, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="comprovante_{pk}.pdf"'

        return response


# ── 10. Upload de documentos PDF ──────────────────────────────────────────────
class EnrollmentDocumentosView(APIView):
    permission_classes = [IsCandidateOrAdminReadOnly]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, pk):  # ← adicione este método
        candidato = visible_candidates(request.user).filter(pk=pk).first()
        if not candidato:
            return Response({'erro': 'Candidato não encontrado.'}, status=404)

        documentos = candidato.documentos.all()
        return Response([
            {
                'id': d.id,
                'tipo': d.tipo,
                'url': request.build_absolute_uri(d.arquivo.url),
                'enviado_em': d.enviado_em,
            }
            for d in documentos
        ])

    def post(self, request, pk):
        candidato = visible_candidates(request.user).filter(pk=pk).first()
        if not candidato:
            return Response({'erro': 'Candidato não encontrado.'}, status=404)

        if not request.FILES:
            raise ValidationError({'arquivos': 'Selecione pelo menos um PDF.'})
        validate_documents(request.FILES)
        with transaction.atomic():
            save_documents(candidato, request.FILES)
        salvos = list(request.FILES)

        return Response({'salvos': salvos}, status=201)
    
class ComprovanteDataView(APIView):
    permission_classes = [IsCandidateOrAdminReadOnly]

    def get(self, request, pk):
        candidato = visible_candidates(request.user).filter(pk=pk).first()
        if not candidato:
            return Response({'erro': 'Não encontrado'}, status=404)

        return Response({
            'id': candidato.id,
            'nome': candidato.nome,
            'full_name': candidato.nome,
            'social_name': candidato.social_name,
            'cpf': candidato.cpf,
            'email': candidato.email,
            'program_level': candidato.program_level,
            'date_of_birth': str(candidato.date_of_birth) if candidato.date_of_birth else None,
            'rg': candidato.rg,
            'issuing_body': candidato.issuing_body,
            'dispatch_date': str(candidato.dispatch_date) if candidato.dispatch_date else None,
            'voter_id': candidato.voter_id,
            'voter_zone': candidato.voter_zone,
            'voter_section': candidato.voter_section,
            'military_id': candidato.military_id,
            'military_series': candidato.military_series,
            'military_category': candidato.military_category,
            'military_dispatch_date': str(candidato.military_dispatch_date) if candidato.military_dispatch_date else None,
            'mother_name': candidato.mother_name,
            'father_name': candidato.father_name,
            'gender': candidato.gender,
            'marital_status': candidato.marital_status,
            'race_color': candidato.race_color,
            'birth_city': candidato.birth_city,
            'birth_state': candidato.birth_state,
            'birth_country': candidato.birth_country,
            'nationality': candidato.nationality,
            'phone': candidato.phone,
            'zip_code': candidato.zip_code,
            'street': candidato.street,
            'number': candidato.number,
            'complement': candidato.complement,
            'neighbourhood': candidato.neighbourhood,
            'city': candidato.city,
            'state': candidato.state,
            'emergency_contact_1': candidato.emergency_contact_1,
            'emergency_phone_1': candidato.emergency_phone_1,
            'emergency_contact_2': candidato.emergency_contact_2,
            'emergency_phone_2': candidato.emergency_phone_2,
            'institution': candidato.institution,
            'course': candidato.course,
            'graduation_year': candidato.graduation_year,
            'bank_name': candidato.bank_name,
            'agency': candidato.agency,
            'account_number': candidato.account_number,
            'status': candidato.status,
        })
    
class CandidatoSituacaoView(APIView):
    permission_classes = [IsCandidate]

    def get(self, request):
        try:
            candidato = request.user.candidato_aprovado
        except CandidatoAprovado.DoesNotExist:
            return Response({'erro': 'Candidato não encontrado.'}, status=404)

        status_map = {
            'PENDING':    'PENDING',
            'ANDAMENTO':  'ANDAMENTO',
            'AGUARDANDO': 'AGUARDANDO',
            'APROVADO':   'APROVADO',
            'REJEITADO':  'REJEITADO',
        }

        return Response({
            'status':             status_map.get(candidato.status.upper(), 'PENDING'),
            'formulario_enviado': candidato.formulario_enviado,
            'nome':               candidato.nome,
            'programa':           candidato.periodo.programa if candidato.periodo else '',
            'periodo_titulo':     candidato.periodo.nome if candidato.periodo else None,
            'periodo_inicio':     str(candidato.periodo.data_abertura) if candidato.periodo else None,
            'periodo_fim':        str(candidato.periodo.data_fechamento) if candidato.periodo else None,
        })
    
class EnrollmentDetailView(RetrieveAPIView):
    serializer_class = CandidatoAprovadoSerializer
    permission_classes = [IsCandidateOrAdminReadOnly]

    def get_queryset(self):
        return visible_candidates(self.request.user)

    def get_serializer_context(self):
        return {'request': self.request}


class DocumentoArquivoView(APIView):
    permission_classes = [IsCandidateOrAdminReadOnly]

    def get(self, request, path):
        # Look up a registered file; never resolve a client-supplied filesystem path.
        documento = DocumentoCandidato.objects.filter(
            arquivo=path, candidato__in=visible_candidates(request.user)
        ).first()
        arquivo = documento.arquivo if documento else None
        if arquivo is None and is_admin(request.user):
            profile = AdminProfile.objects.filter(foto=path).first()
            arquivo = profile.foto if profile else None
        if not arquivo:
            raise Http404
        try:
            response = FileResponse(arquivo.open('rb'), filename=os.path.basename(arquivo.name))
        except FileNotFoundError:
            raise Http404
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
