from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
import re
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
    program_level = serializers.ChoiceField(choices=['MESTRADO', 'DOUTORADO'], required=False)
    bank_account_type = serializers.ChoiceField(choices=['CC', 'CP', 'CS'], required=False)

    def validate_cpf(self, value):
        digits = re.sub(r'\D', '', value)
        if len(digits) != 11 or len(set(digits)) == 1:
            raise serializers.ValidationError('CPF inválido.')
        for size in (9, 10):
            check = (sum(int(digits[i]) * (size + 1 - i) for i in range(size)) * 10) % 11
            if int(digits[size]) != (0 if check == 10 else check):
                raise serializers.ValidationError('CPF inválido.')
        return digits

    def validate_date_of_birth(self, value):
        if value:
            today = timezone.localdate()
            age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
            if age < 17:
                raise serializers.ValidationError('É necessário ter no mínimo 17 anos.')
        return value

    def validate_graduation_year(self, value):
        if value and (not value.isdigit() or not 1950 <= int(value) <= timezone.localdate().year):
            raise serializers.ValidationError('Ano de conclusão inválido.')
        return value

    def validate_compe_code(self, value):
        if value and not re.fullmatch(r'\d{3}', value):
            raise serializers.ValidationError('Informe três dígitos.')
        return value

    protected_fields = {
        'id', 'user', 'user_id', 'periodo', 'periodo_id', 'inscricao', 'status',
        'formulario_enviado', 'is_first_access', 'criado_em', 'created_at',
        'role', 'is_staff', 'is_superuser',
    }
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
        read_only_fields = (
            'user', 'periodo', 'inscricao', 'status', 'formulario_enviado',
            'is_first_access', 'criado_em',
        )
        extra_kwargs = {
            # Campos do CSV — não obrigatórios no PATCH do formulário
            'nome':      {'required': False},
            'cpf':       {'required': False},
            'inscricao': {'required': False},
            'periodo':   {'required': False},
            'status':    {'required': False},
        }

    def to_internal_value(self, data):
        forbidden = self.protected_fields.intersection(data)
        if forbidden:
            raise serializers.ValidationError({
                field: 'Este campo é controlado pelo servidor.' for field in sorted(forbidden)
            })
        data = data.copy()
        for field in ('date_of_birth', 'dispatch_date', 'military_dispatch_date'):
            if data.get(field) == '':
                data[field] = None
        return super().to_internal_value(data)

    def get_programa(self, obj):
        return obj.periodo.programa if obj.periodo else None


# ── Login ─────────────────────────────────────────────────────────────────────
class LoginCandidatoSerializer(serializers.Serializer):
    inscricao = serializers.CharField()
    senha = serializers.CharField(trim_whitespace=False)

    @transaction.atomic
    def validate(self, attrs):
        inscricao = str(attrs.get('inscricao', '')).strip()
        senha = attrs['senha']

        candidato = CandidatoAprovado.objects.select_for_update().filter(inscricao=inscricao).first()
        if not candidato:
            raise serializers.ValidationError("Dados inválidos.")

        user = candidato.user
        if user is None:
            # Never adopt an existing account just because its username matches an import.
            if User.objects.filter(username=inscricao).exists() or senha != candidato.cpf:
                raise serializers.ValidationError("Dados inválidos.")
            user = User.objects.create_user(username=inscricao, password=senha)
            candidato.user = user
            candidato.save(update_fields=['user'])

        if not user.is_active or user.is_staff or user.is_superuser or not user.check_password(senha):
            raise serializers.ValidationError("Dados inválidos.")

        refresh = RefreshToken.for_user(user)

        return {
            'access':         str(refresh.access_token),
            'refresh':        str(refresh),
            'nome':           candidato.nome,
            'programa':       candidato.periodo.programa,
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

    def validate(self, attrs):
        inicio = attrs.get('data_abertura', getattr(self.instance, 'data_abertura', None))
        fim = attrs.get('data_fechamento', getattr(self.instance, 'data_fechamento', None))
        if inicio and fim and fim < inicio:
            raise serializers.ValidationError({'data_fim': 'O fechamento deve ser posterior ou igual ? abertura.'})
        return attrs

    def get_total_candidatos(self, obj):
        return obj.candidatoaprovado_set.count()

    def get_ativo(self, obj):
        from django.utils import timezone
        hoje = timezone.localdate()
        return obj.ativo and obj.data_abertura <= hoje <= obj.data_fechamento

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
