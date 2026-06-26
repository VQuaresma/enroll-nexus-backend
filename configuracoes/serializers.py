from rest_framework import serializers
from django.contrib.auth.models import User
from .models import AdminProfile, ParametrosSistema


class AdminProfileSerializer(serializers.ModelSerializer):
    username   = serializers.CharField(source='user.username', read_only=True)
    email      = serializers.EmailField(source='user.email')
    first_name = serializers.CharField(source='user.first_name')
    last_name  = serializers.CharField(source='user.last_name')

    class Meta:
        model  = AdminProfile
        fields = ['username', 'email', 'first_name', 'last_name', 'role', 'foto']

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


class ConvidarAdminSerializer(serializers.Serializer):
    email      = serializers.EmailField()
    first_name = serializers.CharField()
    last_name  = serializers.CharField()
    role       = serializers.ChoiceField(choices=AdminProfile.Role.choices)


class ParametrosSistemaSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ParametrosSistema
        fields = '__all__'