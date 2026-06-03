from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from .models import Enrollment, CandidatoAprovado, PeriodoMatricula


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
    
class PeriodoMatriculaSerializer(serializers.ModelSerializer):
    total_candidatos = serializers.SerializerMethodField()
    ativo = serializers.SerializerMethodField()
    candidatos = serializers.SerializerMethodField()

    # Aliases para o frontend
    titulo = serializers.CharField(source='nome')
    data_inicio = serializers.DateField(source='data_abertura')
    data_fim = serializers.DateField(source='data_fechamento')

    class Meta:
        model = PeriodoMatricula
        fields = [
            'id', 'titulo', 'data_inicio', 'data_fim',
            'programa', 'total_candidatos', 'ativo', 'candidatos'
        ]

    def get_total_candidatos(self, obj):
        return obj.candidatoaprovado_set.count()

    def get_ativo(self, obj):
        from datetime import date
        hoje = date.today()
        return obj.data_abertura <= hoje <= obj.data_fechamento

    def get_candidatos(self, obj):
        from .models import Enrollment

        # Busca todos os CPFs que já enviaram o formulário de uma vez só (eficiente)
        cpfs_com_enrollment = set(
            Enrollment.objects.filter(
                cpf__in=obj.candidatoaprovado_set.values_list('cpf', flat=True)
            ).values_list('cpf', flat=True)
        )

        resultado = []
        for c in obj.candidatoaprovado_set.all():
            # Status administrativo já definido (aprovado/rejeitado pelo admin)
            status_salvo = (c.status or '').upper()
            if status_salvo in ('APROVADO', 'APPROVED'):
                status_display = 'aprovado'
            elif status_salvo in ('REJEITADO', 'REJECTED'):
                status_display = 'rejeitado'
            # Enviou o formulário completo
            elif c.cpf in cpfs_com_enrollment:
                status_display = 'aguardando'  # "aguardando" = aguardando aprovação do admin
            # Fez login mas não enviou o forms
            elif not c.is_first_access:
                status_display = 'em andamento'
            # Nunca logou
            else:
                status_display = 'pendente'

            resultado.append({
                'id': c.id,
                'nome': c.nome,
                'cpf': c.cpf,
                'inscricao': c.inscricao,
                'email': c.email,
                'status': status_display,
            })

        return resultado