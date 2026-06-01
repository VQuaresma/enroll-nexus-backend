import csv
import io
from django.contrib.auth.models import User
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from .models import Enrollment, PeriodoMatricula, CandidatoAprovado
from .serializers import EnrollmentSerializer, LoginCandidatoSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView


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