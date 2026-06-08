from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from .models import CandidatoAprovado, PeriodoMatricula, DocumentoCandidato


# ── Documentos ────────────────────────────────────────────────────────────────
class DocumentoSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = DocumentoCandidato
        fields = ['id', 'tipo', 'url', 'enviado_em']

    def get_url(self, obj):
        request = self.context.get('request')
        if obj.arquivo and request:
            return request.build_absolute_uri(obj.arquivo.url)
        return obj.arquivo.url if obj.arquivo else None


# ── Candidato (modelo unificado) ──────────────────────────────────────────────
class CandidatoAprovadoSerializer(serializers.ModelSerializer):
    documentos = DocumentoSerializer(many=True, read_only=True)
    # Expõe o programa do período para o frontend
    programa = serializers.SerializerMethodField()
    # Alias para manter compatibilidade com o frontend (created_at)
    created_at = serializers.DateTimeField(source='criado_em', read_only=True)
    # Alias full_name → nome (o forms envia full_name)
    full_name = serializers.CharField(source='nome', required=False)

    class Meta:
        model = CandidatoAprovado
        fields = '__all__'
        extra_kwargs = {
            # Campos do CSV — não obrigatórios no PATCH do formulário
            'nome':      {'required': False},
            'cpf':       {'required': False},
            'inscricao': {'required': False},
            'periodo':   {'required': False},
            'status':    {'required': False},
        }

    def get_programa(self, obj):
        return obj.periodo.programa if obj.periodo else None


# ── Login ─────────────────────────────────────────────────────────────────────
class LoginCandidatoSerializer(serializers.Serializer):
    inscricao = serializers.CharField()
    senha = serializers.CharField()

    def validate(self, attrs):
        inscricao = str(attrs.get('inscricao', '')).strip()
        senha = str(attrs.get('senha', '')).strip()

        candidato = CandidatoAprovado.objects.filter(inscricao=inscricao).first()
        if not candidato:
            raise serializers.ValidationError("Dados inválidos.")

        user, criado = User.objects.get_or_create(
            username=inscricao,
            defaults={'password': make_password(candidato.cpf)}
        )

        if criado or candidato.user is None:
            candidato.user = user
            candidato.save()

        if not user.check_password(senha):
            raise serializers.ValidationError("Dados inválidos.")

        refresh = RefreshToken.for_user(user)

        return {
            'access':         str(refresh.access_token),
            'refresh':        str(refresh),
            'nome':           candidato.nome,
            'inscricao':      candidato.inscricao,
            'is_first_access': candidato.is_first_access,
            'formulario_enviado': candidato.formulario_enviado,
        }


# ── Período ───────────────────────────────────────────────────────────────────
class PeriodoMatriculaSerializer(serializers.ModelSerializer):
    total_candidatos = serializers.SerializerMethodField()
    ativo            = serializers.SerializerMethodField()
    candidatos       = serializers.SerializerMethodField()

    titulo     = serializers.CharField(source='nome')
    data_inicio = serializers.DateField(source='data_abertura')
    data_fim    = serializers.DateField(source='data_fechamento')

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
        resultado = []
        for c in obj.candidatoaprovado_set.all():
            status_salvo = (c.status or '').upper()
            if status_salvo == 'APROVADO':
                status_display = 'aprovado'
            elif status_salvo == 'REJEITADO':
                status_display = 'rejeitado'
            elif c.formulario_enviado:
                status_display = 'aguardando'
            elif not c.is_first_access:
                status_display = 'em andamento'
            else:
                status_display = 'pendente'

            resultado.append({
                'id':       c.id,
                'nome':     c.nome,
                'cpf':      c.cpf,
                'inscricao': c.inscricao,
                'email':    c.email,
                'status':   status_display,
            })
        return resultado