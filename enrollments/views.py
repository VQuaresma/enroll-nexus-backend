import csv
import io
import tempfile
import os
import threading
import time

from django.http import FileResponse
from django.contrib.auth.models import User
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated, AllowAny

from .models import PeriodoMatricula, CandidatoAprovado, DocumentoCandidato
from .serializers import CandidatoAprovadoSerializer, LoginCandidatoSerializer, PeriodoMatriculaSerializer


# ── 1. Submeter formulário (PATCH no próprio CandidatoAprovado) ───────────────
class EnrollmentCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            candidato = request.user.candidato_aprovado
        except CandidatoAprovado.DoesNotExist:
            return Response({'erro': 'Candidato não encontrado.'}, status=404)

        if candidato.formulario_enviado:
            return Response(
                {'erro': 'Você já enviou sua inscrição. Acompanhe pelo seu painel.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CandidatoAprovadoSerializer(
            candidato, data=request.data, partial=True
        )
        if not serializer.is_valid():
            print("\n❌ ERRO DE VALIDAÇÃO NO DJANGO:")
            print(serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save(formulario_enviado=True, status='AGUARDANDO')
        return Response(serializer.data, status=status.HTTP_200_OK)


# ── 2. Listar candidatos para o admin ─────────────────────────────────────────
class EnrollmentListView(generics.ListAPIView):
    serializer_class = CandidatoAprovadoSerializer
    permission_classes = [IsAuthenticated]

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
        print(f"Erro de validação: {serializer.errors}")
        return Response(serializer.errors, status=400)


# ── 4. Trocar senha ───────────────────────────────────────────────────────────
class TrocarSenhaView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        senha_atual = request.data.get('senha_atual')
        nova_senha = request.data.get('nova_senha')

        if not user.check_password(senha_atual):
            return Response({"error": "A senha atual está incorreta."}, status=400)

        user.set_password(nova_senha)
        user.save()

        try:
            candidato = user.candidato_aprovado
            candidato.is_first_access = False
            candidato.save()
        except Exception:
            pass

        return Response({"message": "Senha atualizada com sucesso!"})


# ── 5. Importar CSV e criar período ───────────────────────────────────────────
class ImportarCandidatosView(APIView):
    permission_classes = [IsAuthenticated]
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

        periodo = PeriodoMatricula.objects.create(
            nome=titulo,
            programa=programa,
            data_abertura=data_inicio,
            data_fechamento=data_fim,
            ativo=True
        )

        try:
            conteudo = arquivo.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(conteudo))
            reader.fieldnames = [h.strip().lower() for h in reader.fieldnames]

            criados = 0
            erros = []

            for i, linha in enumerate(reader, start=2):
                nome      = linha.get('nome', '').strip()
                cpf       = linha.get('cpf', '').strip()
                inscricao = linha.get('inscricao', '').strip()
                email     = linha.get('email', '').strip()

                if not nome or not cpf:
                    erros.append(f"Linha {i}: nome e cpf são obrigatórios")
                    continue

                candidato = CandidatoAprovado.objects.create(
                    periodo=periodo,
                    nome=nome,
                    cpf=cpf,
                    inscricao=inscricao,
                    email=email,
                    status='PENDING'
                )

                # Usa inscricao como username (login) e CPF como senha inicial
                user = User.objects.filter(username=inscricao).first()
                if not user:
                    user = User.objects.create_user(username=inscricao, password=cpf)
                else:
                    user.set_password(cpf)
                    user.save()

                candidato.user = user
                candidato.save()
                criados += 1

        except Exception as e:
            periodo.delete()
            return Response(
                {'erro': f'Erro ao processar CSV: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({
            'sucesso': True,
            'periodo_id': periodo.id,
            'periodo_nome': periodo.nome,
            'candidatos_importados': criados,
            'erros': erros,
        }, status=status.HTTP_201_CREATED)


# ── 6. Listar/criar períodos ──────────────────────────────────────────────────
class PeriodoMatriculaListCreateView(generics.ListCreateAPIView):
    serializer_class = PeriodoMatriculaSerializer
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]
    # RetrieveUpdateAPIView — sem DestroyAPIView, períodos não podem ser excluídos


# ── 8. Atualizar status do candidato ──────────────────────────────────────────
class EnrollmentStatusUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        candidato = CandidatoAprovado.objects.filter(pk=pk).first()
        if not candidato:
            return Response({'erro': 'Candidato não encontrado.'}, status=404)

        novo_status = request.data.get('status', '').upper()
        candidato.status = novo_status
        candidato.save()
        return Response({'id': pk, 'status': candidato.status})


# ── 9. Gerar comprovante PDF ──────────────────────────────────────────────────
class EnrollmentComprovanteView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        candidato = CandidatoAprovado.objects.filter(pk=pk).first()
        if not candidato:
            return Response({'erro': 'Candidato não encontrado.'}, status=404)

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        c = canvas.Canvas(tmp.name, pagesize=A4)
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
        tmp.close()

        response = FileResponse(open(tmp.name, 'rb'), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="comprovante_{pk}.pdf"'

        def deletar():
            time.sleep(5)
            try:
                os.unlink(tmp.name)
            except Exception:
                pass
        threading.Thread(target=deletar, daemon=True).start()

        return response


# ── 10. Upload de documentos PDF ──────────────────────────────────────────────
class EnrollmentDocumentosView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        candidato = CandidatoAprovado.objects.filter(pk=pk).first()
        if not candidato:
            return Response({'erro': 'Candidato não encontrado.'}, status=404)

        tipos_validos = [
            'diploma', 'historico', 'rg', 'cpf',
            'titulo', 'comp_votacao', 'comp_residencia', 'reservista'
        ]
        salvos = []
        for tipo in tipos_validos:
            arquivo = request.FILES.get(tipo)
            if arquivo:
                DocumentoCandidato.objects.create(
                    candidato=candidato,
                    tipo=tipo,
                    arquivo=arquivo
                )
                salvos.append(tipo)

        return Response({'salvos': salvos}, status=201)
    
class ComprovanteDataView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        candidato = CandidatoAprovado.objects.filter(pk=pk).first()
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