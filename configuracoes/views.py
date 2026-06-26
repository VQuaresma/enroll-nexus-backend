import secrets, string
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.models import User
from django.contrib.auth import update_session_auth_hash

from .models import AdminProfile, ParametrosSistema
from .serializers import (
    AdminProfileSerializer, AlterarSenhaSerializer,
    AdminUsuarioSerializer, ConvidarAdminSerializer,
    ParametrosSistemaSerializer,
)


class PerfilView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile, _ = AdminProfile.objects.get_or_create(user=request.user)
        return Response(AdminProfileSerializer(profile).data)

    def patch(self, request):
        profile, _ = AdminProfile.objects.get_or_create(user=request.user)
        serializer = AdminProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AlterarSenhaView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AlterarSenhaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not request.user.check_password(serializer.validated_data['senha_atual']):
            return Response({'senha_atual': 'Senha atual incorreta.'}, status=400)

        request.user.set_password(serializer.validated_data['nova_senha'])
        request.user.save()
        update_session_auth_hash(request, request.user)
        return Response({'detail': 'Senha alterada com sucesso.'})


class AdminUsuariosView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        admins = User.objects.filter(is_staff=True).select_related('admin_profile')
        return Response(AdminUsuarioSerializer(admins, many=True).data)

    def post(self, request):
        serializer = ConvidarAdminSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if User.objects.filter(email=data['email']).exists():
            return Response({'email': 'Já existe um usuário com este e-mail.'}, status=400)

        temp_password = ''.join(
            secrets.choice(string.ascii_letters + string.digits) for _ in range(12)
        )
        user = User.objects.create_user(
            username=data['email'],
            email=data['email'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            password=temp_password,
            is_staff=True,
        )
        AdminProfile.objects.create(user=user, role=data['role'])
        # TODO: disparar e-mail com temp_password
        return Response({'detail': f'Convite enviado. Senha temporária: {temp_password}'}, status=201)


class AdminUsuarioDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, user_id):
        try:
            profile = AdminProfile.objects.get(user_id=user_id)
        except AdminProfile.DoesNotExist:
            return Response({'detail': 'Usuário não encontrado.'}, status=404)

        role = request.data.get('role')
        if role not in dict(AdminProfile.Role.choices):
            return Response({'detail': 'Role inválido.'}, status=400)

        profile.role = role
        profile.save()
        return Response({'detail': 'Role atualizado.'})

    def delete(self, request, user_id):
        if str(request.user.pk) == str(user_id):
            return Response({'detail': 'Você não pode remover seu próprio acesso.'}, status=400)

        try:
            user = User.objects.get(pk=user_id, is_staff=True)
        except User.DoesNotExist:
            return Response({'detail': 'Usuário não encontrado.'}, status=404)

        user.is_active = False
        user.save()
        return Response(status=204)


class ParametrosView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(ParametrosSistemaSerializer(ParametrosSistema.get()).data)

    def patch(self, request):
        params = ParametrosSistema.get()
        serializer = ParametrosSistemaSerializer(params, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)