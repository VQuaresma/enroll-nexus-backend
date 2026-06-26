from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import User


class AdminProfile(models.Model):
    class Role(models.TextChoices):
        SUPER_ADMIN = 'super_admin', 'Super Admin'
        AVALIADOR   = 'avaliador',   'Avaliador'

    user   = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_profile')
    role   = models.CharField(max_length=20, choices=Role.choices, default=Role.AVALIADOR)
    foto   = models.ImageField(upload_to='perfis/', null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class ParametrosSistema(models.Model):
    """Singleton — sempre pk=1"""
    max_candidatos_por_periodo  = models.IntegerField(default=100)
    aceitar_novas_inscricoes    = models.BooleanField(default=True)
    email_template_aprovado     = models.TextField(
        default="Parabéns! Sua pré-matrícula foi aprovada."
    )
    email_template_aguardando   = models.TextField(
        default="Sua inscrição está em análise. Aguarde o retorno."
    )
    tema                        = models.CharField(
        max_length=10,
        choices=[('light', 'Claro'), ('dark', 'Escuro')],
        default='light'
    )
    candidatos_por_pagina       = models.IntegerField(default=10)

    class Meta:
        verbose_name = "Parâmetros do Sistema"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj