from rest_framework import serializers
from .models import Enrollment, Candidato
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class EnrollmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Enrollment
        fields = '__all__'

class LoginCandidatoSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        # Chama a validação padrão (que verifica login/senha e gera o token)
        data = super().validate(attrs)
        
        # Vamos descobrir se quem está logando é um candidato
        try:
            candidato = self.user.perfil_candidato
            data['is_first_access'] = candidato.is_first_access
            data['nome'] = self.user.first_name
            data['status'] = candidato.status
        except Candidato.DoesNotExist:
            # Se cair aqui, é porque quem logou foi um Admin (superusuário), e não um candidato
            data['is_first_access'] = False 
            data['nome'] = self.user.username
            data['status'] = 'ADMIN'
            
        return data