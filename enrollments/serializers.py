from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from .models import Enrollment, CandidatoAprovado


class EnrollmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Enrollment
        fields = '__all__'


class LoginCandidatoSerializer(serializers.Serializer):
    inscricao = serializers.CharField()
    senha = serializers.CharField()

    def validate(self, attrs):
        inscricao = str(attrs.get('inscricao', '')).strip()
        senha = str(attrs.get('senha', '')).strip()

        candidato = CandidatoAprovado.objects.filter(inscricao=inscricao).first()

        if not candidato:
            raise serializers.ValidationError("Dados inválidos.")

        # Garante que o User existe
        user, criado = User.objects.get_or_create(
            username=inscricao,
            defaults={'password': make_password(candidato.cpf)}
        )

        # Se o User foi criado agora, vincula ao candidato
        if criado or candidato.user is None:
            candidato.user = user
            candidato.save()

        # Verifica a senha (CPF no primeiro acesso, senha nova depois)
        if not user.check_password(senha):
            raise serializers.ValidationError("Dados inválidos.")

        refresh = RefreshToken.for_user(user)

        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'nome': candidato.nome,
            'inscricao': candidato.inscricao,
            'is_first_access': candidato.is_first_access,
        }