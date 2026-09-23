from django.core.exceptions import ObjectDoesNotExist
from rest_framework.permissions import BasePermission, SAFE_METHODS

from configuracoes.models import AdminProfile


def is_admin(user):
    return bool(user and user.is_authenticated and user.is_active and user.is_staff)


def is_super_admin(user):
    return is_admin(user) and (
        user.is_superuser
        or AdminProfile.objects.filter(user_id=user.pk, role=AdminProfile.Role.SUPER_ADMIN).exists()
    )


def is_candidate(user):
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if user.is_staff or user.is_superuser:
        return False
    try:
        return user.candidato_aprovado is not None
    except ObjectDoesNotExist:
        return False


class IsAdmin(BasePermission):
    message = 'Acesso restrito a administradores.'

    def has_permission(self, request, view):
        return is_admin(request.user)


class IsSuperAdmin(BasePermission):
    message = 'Somente super admin pode gerenciar administradores.'

    def has_permission(self, request, view):
        return is_super_admin(request.user)


class IsCandidate(BasePermission):
    message = 'Acesso restrito ao candidato titular.'

    def has_permission(self, request, view):
        return is_candidate(request.user)


class IsCandidateOrAdminReadOnly(BasePermission):
    def has_permission(self, request, view):
        return is_candidate(request.user) or (
            request.method in SAFE_METHODS and is_admin(request.user)
        )

    def has_object_permission(self, request, view, obj):
        if is_admin(request.user):
            return request.method in SAFE_METHODS
        candidate = getattr(obj, 'candidato', obj)
        return is_candidate(request.user) and candidate.user_id == request.user.pk
