import csv
import io
import tempfile, os
from django.http import FileResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from django.contrib.auth.models import User
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from .models import Enrollment, PeriodoMatricula, CandidatoAprovado, PeriodoMatricula, DocumentoEnrollment
from .serializers import EnrollmentSerializer, LoginCandidatoSerializer, PeriodoMatriculaSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny


# 1. View para Criar Inscrições (Usada pelo formulário React)
class EnrollmentCreateView(generics.CreateAPIView):
    queryset = Enrollment.objects.all()
    serializer_class = EnrollmentSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            print("\n❌ ERRO DE VALIDAÇÃO NO DJANGO:")
            print(serializer.errors)
            print("----------------------------\n")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return super().create(request, *args, **kwargs)


# 2. View para Listar Inscrições (Usada pelo Dashboard)
class EnrollmentListView(generics.ListAPIView):
    serializer_class = EnrollmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Enrollment.objects.all().order_by('-id')
        programa_url = self.request.query_params.get('program', None)
        if programa_url is not None:
            queryset = queryset.filter(program__iexact=programa_url)
        return queryset


# 3. View de Login do Candidato
class LoginCandidatoView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginCandidatoSerializer(data=request.data)
        if serializer.is_valid():
            return Response(serializer.validated_data)
        # ADICIONE ESTA LINHA PARA VER O ERRO NO TERMINAL:
        print(f"Erro de validação: {serializer.errors}")
        return Response(serializer.errors, status=400)

# 4. View de Troca de Senha
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

        # Marca que não é mais primeiro acesso
        try:
            candidato = user.candidato_aprovado  # related_name que definimos
            candidato.is_first_access = False
            candidato.save()
        except Exception:
            pass

        return Response({"message": "Senha atualizada com sucesso!"})



class ImportarCandidatosView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]  # Essencial para receber arquivo + campos juntos

    def post(self, request):
        titulo      = request.data.get('titulo', '').strip()
        descricao   = request.data.get('descricao', '').strip()
        programa    = request.data.get('program', '').strip()
        data_inicio = request.data.get('data_inicio')
        data_fim    = request.data.get('data_fim')
        arquivo     = request.FILES.get('file')

        if not all([titulo, programa, data_inicio, data_fim, arquivo]):
            campos_faltando = {
                'titulo': bool(titulo),
                'program': bool(programa),
                'data_inicio': bool(data_inicio),
                'data_fim': bool(data_fim),
                'file': bool(arquivo),
            }
            return Response(
                {'erro': 'Campos obrigatórios ausentes', 'detalhes': campos_faltando},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 1. Cria o período de matrícula
        periodo = PeriodoMatricula.objects.create(
            nome=titulo,
            programa=programa,
            data_abertura=data_inicio,
            data_fechamento=data_fim,
            ativo=True
        )

        # 2. Processa a leitura e importação do CSV
        try:
            conteudo = arquivo.read().decode('utf-8-sig')  # utf-8-sig ignora BOM do Excel
            reader = csv.DictReader(io.StringIO(conteudo))

            # Normaliza headers: remove espaços e coloca em minúsculo
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

                # A. Cria o candidato no banco de dados
                candidato = CandidatoAprovado.objects.create(
                    periodo=periodo,
                    nome=nome,
                    cpf=cpf,
                    inscricao=inscricao,
                    email=email,
                    status='PENDING'
                )

                # B. Lógica de Segurança para o User do Django
                # Verifica se já existe um User com esse CPF (caso você reimporte uma planilha antiga)
                user = User.objects.filter(username=cpf).first()
                
                if not user:
                    # Se não existe, cria um novo usuário usando o CPF como senha provisória
                    user = User.objects.create_user(username=cpf, password=cpf)
                else:
                    # Se já existe, força a senha voltar a ser o CPF no re-import
                    user.set_password(cpf)
                    user.save()

                # C. Vincula o usuário ao candidato
                candidato.user = user
                candidato.save()
                
                criados += 1

        except Exception as e:
            periodo.delete()  # Não deixa o período órfão caso o CSV esteja quebrado
            return Response(
                {'erro': f'Erro ao processar CSV: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 3. Retorno de Sucesso para o React
        return Response({
            'sucesso': True,
            'periodo_id': periodo.id,
            'periodo_nome': periodo.nome,
            'candidatos_importados': criados,
            'erros': erros,
        }, status=status.HTTP_201_CREATED)
    
class PeriodoMatriculaListCreateView(generics.ListCreateAPIView):
    serializer_class = PeriodoMatriculaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        programa = self.request.query_params.get('program')
        qs = PeriodoMatricula.objects.all().order_by('-id')
        if programa:
            qs = qs.filter(programa__iexact=programa)
        return qs

class PeriodoMatriculaDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PeriodoMatricula.objects.all()
    serializer_class = PeriodoMatriculaSerializer
    permission_classes = [IsAuthenticated]



class EnrollmentStatusUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            enrollment = Enrollment.objects.get(pk=pk)
        except Enrollment.DoesNotExist:
            # Tenta também em CandidatoAprovado
            try:
                candidato = CandidatoAprovado.objects.get(pk=pk)
                novo_status = request.data.get('status', '').upper()
                candidato.status = novo_status
                candidato.save()
                return Response({'id': pk, 'status': candidato.status})
            except CandidatoAprovado.DoesNotExist:
                return Response({'erro': 'Não encontrado'}, status=404)

        novo_status = request.data.get('status', '')
        enrollment.status = novo_status
        enrollment.save()
        return Response({'id': pk, 'status': enrollment.status})


class EnrollmentComprovanteView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        # Tenta Enrollment primeiro
        enrollment = Enrollment.objects.filter(pk=pk).first()
        
        if enrollment:
            nome     = enrollment.full_name
            cpf      = getattr(enrollment, 'cpf', '—')
            email    = getattr(enrollment, 'email', '—')
            nivel    = enrollment.program_level
            programa = enrollment.program
            criado   = str(enrollment.created_at)[:19] if enrollment.created_at else '—'
            status   = enrollment.status or 'Aguardando'
        else:
            # Tenta CandidatoAprovado
            candidato = CandidatoAprovado.objects.filter(pk=pk).first()
            if not candidato:
                return Response({'erro': 'Não encontrado'}, status=404)
            nome     = candidato.nome
            cpf      = candidato.cpf
            email    = getattr(candidato, 'email', '—')
            nivel    = getattr(candidato, 'inscricao', '—')
            programa = candidato.periodo.programa if candidato.periodo else '—'
            criado   = str(candidato.periodo.data_abertura) if candidato.periodo else '—'
            status   = candidato.status or 'Pendente'

        # Gera PDF
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        c = canvas.Canvas(tmp.name, pagesize=A4)
        width, height = A4

        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, height - 60, "Comprovante de Pré-matrícula")

        c.setFont("Helvetica", 11)
        y = height - 100
        campos = [
            ("Nome", nome),
            ("CPF", cpf),
            ("E-mail", email),
            ("Nível / Inscrição", nivel),
            ("Programa", programa),
            ("Data de inscrição", criado),
            ("Status", status),
        ]
        for label, valor in campos:
            c.setFont("Helvetica-Bold", 10)
            c.drawString(50, y, f"{label}:")
            c.setFont("Helvetica", 10)
            c.drawString(180, y, str(valor or '—'))
            y -= 22

        c.save()
        tmp.close()

        response = FileResponse(open(tmp.name, 'rb'), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="comprovante_{pk}.pdf"'

        import threading
        def deletar():
            import time; time.sleep(5)
            try: os.unlink(tmp.name)
            except: pass
        threading.Thread(target=deletar, daemon=True).start()

        return response
    

class EnrollmentDocumentosView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        try:
            enrollment = Enrollment.objects.get(pk=pk)
        except Enrollment.DoesNotExist:
            return Response({'erro': 'Não encontrado'}, status=404)

        tipos_validos = ['diploma','historico','rg','cpf','titulo','comp_votacao','comp_residencia','reservista']
        salvos = []

        for tipo in tipos_validos:
            arquivo = request.FILES.get(tipo)
            if arquivo:
                DocumentoEnrollment.objects.create(
                    enrollment=enrollment,
                    tipo=tipo,
                    arquivo=arquivo
                )
                salvos.append(tipo)

        return Response({'salvos': salvos}, status=201)