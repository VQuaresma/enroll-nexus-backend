from rest_framework import serializers
from django.contrib.auth.models import User
from .models import AdminProfile, ParametrosSistema
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import AuthenticationFailed
from core.permissions import is_admin


class AdminTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        if not is_admin(self.user):
            raise AuthenticationFailed('Dados inválidos.')
        return data


class RejectProtectedFieldsMixin:
    protected_fields = {'user', 'user_id', 'role', 'is_staff', 'is_superuser', 'is_active', 'password'}

    def to_internal_value(self, data):
        forbidden = self.protected_fields.intersection(data)
        if forbidden:
            raise serializers.ValidationError({
                field: 'Este campo não pode ser alterado nesta operação.'
                for field in sorted(forbidden)
            })
        return super().to_internal_value(data)


class AdminProfileSerializer(RejectProtectedFieldsMixin, serializers.ModelSerializer):
    username   = serializers.CharField(source='user.username', read_only=True)
    email      = serializers.EmailField(source='user.email')
    first_name = serializers.CharField(source='user.first_name')
    last_name  = serializers.CharField(source='user.last_name')

    class Meta:
        model  = AdminProfile
        fields = ['username', 'email', 'first_name', 'last_name', 'role', 'foto']
        read_only_fields = ['role']

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        for attr, value in user_data.items():
            setattr(instance.user, attr, value)
        instance.user.save()
        return super().update(instance, validated_data)


class AlterarSenhaSerializer(serializers.Serializer):
    senha_atual      = serializers.CharField()
    nova_senha       = serializers.CharField(min_length=8)
    confirmar_senha  = serializers.CharField()

    def validate(self, data):
        if data['nova_senha'] != data['confirmar_senha']:
            raise serializers.ValidationError("As senhas não coincidem.")
        return data


class AdminUsuarioSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source='admin_profile.role', default='avaliador')

    class Meta:
        model  = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'is_active']


class ConvidarAdminSerializer(RejectProtectedFieldsMixin, serializers.Serializer):
    protected_fields = RejectProtectedFieldsMixin.protected_fields - {'role'}
    email      = serializers.EmailField()
    first_name = serializers.CharField()
    last_name  = serializers.CharField()
    role       = serializers.ChoiceField(choices=AdminProfile.Role.choices)


class ParametrosSistemaSerializer(RejectProtectedFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model  = ParametrosSistema
        fields = '__all__'
