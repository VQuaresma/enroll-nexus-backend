from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Enrollment
from .serializers import EnrollmentSerializer, LoginCandidatoSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView

# 1. View para Criar Inscrições (Usada pelo formulário React)
class EnrollmentCreateView(generics.CreateAPIView):
    queryset = Enrollment.objects.all()
    serializer_class = EnrollmentSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            # Log de erro para facilitar sua vida no terminal do VS Code
            print("\n❌ ERRO DE VALIDAÇÃO NO DJANGO:")
            print(serializer.errors)
            print("----------------------------\n")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        return super().create(request, *args, **kwargs)

# 2. View para Listar Inscrições (Usada pelo Dashboard do NEB)
class EnrollmentListView(generics.ListAPIView):
    # .order_by('-created_at') faz com que os últimos inscritos apareçam primeiro
    queryset = Enrollment.objects.all().order_by('-id') 
    serializer_class = EnrollmentSerializer
    permission_classes = [IsAuthenticated]

# 1. A View de Login que usa o nosso Serializer customizado
class LoginCandidatoView(TokenObtainPairView):
    serializer_class = LoginCandidatoSerializer

# 2. A View de Troca de Senha Segura
class TrocarSenhaView(APIView):
    permission_classes = [IsAuthenticated] # Só quem tem o Token entra aqui

    def post(self, request):
        user = request.user
        senha_atual = request.data.get('senha_atual')
        nova_senha = request.data.get('nova_senha')

        # Checa se a senha "provisória" que ele digitou está certa
        if not user.check_password(senha_atual):
            return Response({"error": "A senha atual está incorreta."}, status=400)
        
        # Salva a nova senha com hash de segurança
        user.set_password(nova_senha)
        user.save()
        
        # Atualiza o status do candidato para dizer que não é mais o primeiro acesso
        try:
            candidato = user.perfil_candidato
            candidato.is_first_access = False
            candidato.save()
        except Exception as e:
            pass # Ignora se for admin
            
        return Response({"message": "Senha atualizada com sucesso!"})