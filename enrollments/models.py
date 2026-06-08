from django.db import models
from django.contrib.auth.models import User


class PeriodoMatricula(models.Model):
    nome = models.CharField(max_length=100)
    programa = models.CharField(max_length=10, choices=[('PGEDA', 'PGEDA'), ('PPEB', 'PPEB')])
    data_abertura = models.DateField()
    data_fechamento = models.DateField()
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.nome


class CandidatoAprovado(models.Model):
    STATUS_CHOICES = [
        ('PENDING',    'Pendente'),
        ('ANDAMENTO',  'Em andamento'),
        ('AGUARDANDO', 'Aguardando aprovação'),
        ('APROVADO',   'Aprovado'),
        ('REJEITADO',  'Rejeitado'),
    ]

    # ── Vínculo ──────────────────────────────────────────────────
    periodo     = models.ForeignKey(PeriodoMatricula, on_delete=models.CASCADE)
    user        = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='candidato_aprovado')
    is_first_access = models.BooleanField(default=True)
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    criado_em   = models.DateTimeField(auto_now_add=True)

    # ── Campos do CSV (preenchidos na importação) ─────────────────
    nome        = models.CharField(max_length=255)
    cpf         = models.CharField(max_length=14)
    inscricao   = models.CharField(max_length=20)
    email       = models.EmailField(blank=True, null=True)

    # ── Campos do formulário (preenchidos pelo candidato) ─────────
    social_name     = models.CharField(max_length=255, null=True, blank=True)
    date_of_birth   = models.DateField(null=True, blank=True)
    rg              = models.CharField(max_length=20, null=True, blank=True)
    issuing_body    = models.CharField(max_length=50, null=True, blank=True)
    dispatch_date   = models.DateField(null=True, blank=True)
    voter_id        = models.CharField(max_length=20, null=True, blank=True)
    voter_zone      = models.CharField(max_length=10, null=True, blank=True)
    voter_section   = models.CharField(max_length=10, null=True, blank=True)
    military_id     = models.CharField(max_length=50, null=True, blank=True)
    military_series = models.CharField(max_length=10, null=True, blank=True)
    military_category    = models.CharField(max_length=50, null=True, blank=True)
    military_dispatch_date = models.DateField(null=True, blank=True)
    mother_name     = models.CharField(max_length=255, null=True, blank=True)
    father_name     = models.CharField(max_length=255, null=True, blank=True)
    gender          = models.CharField(max_length=20, null=True, blank=True)
    marital_status  = models.CharField(max_length=50, null=True, blank=True)
    race_color      = models.CharField(max_length=20, null=True, blank=True)
    birth_country   = models.CharField(max_length=100, null=True, blank=True)
    birth_state     = models.CharField(max_length=2, null=True, blank=True)
    birth_city      = models.CharField(max_length=100, null=True, blank=True)
    nationality     = models.CharField(max_length=100, null=True, blank=True)
    phone           = models.CharField(max_length=20, null=True, blank=True)
    zip_code        = models.CharField(max_length=10, null=True, blank=True)
    street          = models.CharField(max_length=255, null=True, blank=True)
    number          = models.CharField(max_length=10, null=True, blank=True)
    complement      = models.CharField(max_length=100, null=True, blank=True)
    neighbourhood   = models.CharField(max_length=100, null=True, blank=True)
    city            = models.CharField(max_length=100, null=True, blank=True)
    state           = models.CharField(max_length=2, null=True, blank=True)
    emergency_contact_1 = models.CharField(max_length=255, null=True, blank=True)
    emergency_phone_1   = models.CharField(max_length=20, null=True, blank=True)
    emergency_contact_2 = models.CharField(max_length=255, null=True, blank=True)
    emergency_phone_2   = models.CharField(max_length=20, null=True, blank=True)
    institution     = models.CharField(max_length=255, null=True, blank=True)
    course          = models.CharField(max_length=255, null=True, blank=True)
    graduation_year = models.CharField(max_length=4, null=True, blank=True)
    lattes_url      = models.URLField(null=True, blank=True)
    research_area   = models.CharField(max_length=255, null=True, blank=True)
    bank_name       = models.CharField(max_length=100, null=True, blank=True)
    compe_code      = models.CharField(max_length=10, null=True, blank=True)
    agency          = models.CharField(max_length=20, null=True, blank=True)
    account_number  = models.CharField(max_length=20, null=True, blank=True)
    bank_account_type = models.CharField(max_length=10, null=True, blank=True)
    program_level   = models.CharField(max_length=10, null=True, blank=True)
    formulario_enviado = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.inscricao} - {self.nome}"


class DocumentoCandidato(models.Model):
    candidato   = models.ForeignKey(CandidatoAprovado, on_delete=models.CASCADE, related_name='documentos')
    tipo        = models.CharField(max_length=50)
    arquivo     = models.FileField(upload_to='documentos/%Y/%m/')
    enviado_em  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.candidato.nome} - {self.tipo}"