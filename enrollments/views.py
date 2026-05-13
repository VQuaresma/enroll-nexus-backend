from rest_framework import generics, status # Adicione o status aqui
from rest_framework.response import Response # Adicione o Response aqui
from .models import Enrollment
from .serializers import EnrollmentSerializer

class EnrollmentCreateView(generics.CreateAPIView):
    queryset = Enrollment.objects.all()
    serializer_class = EnrollmentSerializer

    # Adicione este bloco abaixo:
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            # Isso vai imprimir o erro exato no seu terminal preto do VS Code
            print("\n❌ ERRO DE VALIDAÇÃO NO DJANGO:")
            print(serializer.errors)
            print("----------------------------\n")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        return super().create(request, *args, **kwargs)

class EnrollmentListView(generics.ListAPIView):
    queryset = Enrollment.objects.all()
    serializer_class = EnrollmentSerializer