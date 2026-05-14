from rest_framework import generics, status
from rest_framework.response import Response
from .models import Enrollment
from .serializers import EnrollmentSerializer
from rest_framework.permissions import IsAuthenticated

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