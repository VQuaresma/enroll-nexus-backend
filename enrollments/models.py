from django.db import models
from django.contrib.auth.models import User


class Enrollment(models.Model):
    LEVEL_CHOICES = [
        ('MESTRADO', 'Mestrado'),
        ('DOUTORADO', 'Doutorado'),
    ]
    PROGRAM_CHOICES = [
        ('PGEDA', 'PGEDA'),
        ('PPEB', 'PPEB'),
    ]
    full_name = models.CharField(max_length=255)
    social_name = models.CharField(max_length=255, null=True, blank=True)
    program_level = models.CharField(max_length=10, choices=LEVEL_CHOICES)
    program = models.CharField(max_length=10, null=True, blank=True)
    cpf = models.CharField(max_length=14, unique=True)
    date_of_birth = models.DateField()
    rg = models.CharField(max_length=20)
    issuing_body = models.CharField(max_length=50)
    dispatch_date = models.DateField(null=True, blank=True)
    voter_id = models.CharField(max_length=20)
    voter_zone = models.CharField(max_length=10)
    voter_section = models.CharField(max_length=10)
    military_id = models.CharField(max_length=50, blank=True, null=True)
    military_date = models.DateField(blank=True, null=True)
    military_series = models.CharField(max_length=10, null=True, blank=True)
    military_category = models.CharField(max_length=50, null=True, blank=True)
    military_dispatch_date = models.DateField(null=True, blank=True)
    mother_name = models.CharField(max_length=255)
    father_name = models.CharField(max_length=255)
    gender = models.CharField(max_length=20)
    marital_status = models.CharField(max_length=50)
    race_color = models.CharField(max_length=20)
    birth_country = models.CharField(max_length=100, default="Brasil")
    birth_state = models.CharField(max_length=2)
    birth_city = models.CharField(max_length=100)
    nationality = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    zip_code = models.CharField(max_length=10)
    street = models.CharField(max_length=255)
    number = models.CharField(max_length=10)
    complement = models.CharField(max_length=100, blank=True, null=True)
    neighbourhood = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    emergency_contact_1 = models.CharField(max_length=255)
    emergency_phone_1 = models.CharField(max_length=20)
    emergency_contact_2 = models.CharField(max_length=255)
    emergency_phone_2 = models.CharField(max_length=20)
    institution = models.CharField(max_length=255)
    course = models.CharField(max_length=255)
    graduation_year = models.CharField(max_length=4)
    bank_name = models.CharField(max_length=100)
    agency = models.CharField(max_length=20)
    account_number = models.CharField(max_length=20)
    registration_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, default='PENDING')

    def __str__(self):
        return self.full_name


class Candidato(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil_candidato')
    programa = models.CharField(max_length=10, choices=[('PGEDA', 'PGEDA'), ('PPEB', 'PPEB')], default='PGEDA')
    matricula = models.CharField(max_length=20, unique=True)
    cpf = models.CharField(max_length=14, unique=True)
    is_first_access = models.BooleanField(default=True)
    status = models.CharField(
        max_length=30,
        choices=[
            ('APROVADO', 'Aprovado no Processo'),
            ('PRE_MATRICULA', 'Pré-Matrícula Iniciada'),
            ('CONCLUIDA', 'Matrícula Concluída')
        ],
        default='APROVADO'
    )

    def __str__(self):
        return f"{self.matricula} - {self.user.first_name}"


class PeriodoMatricula(models.Model):
    nome = models.CharField(max_length=100)
    programa = models.CharField(max_length=10, choices=[('PGEDA', 'PGEDA'), ('PPEB', 'PPEB')])
    data_abertura = models.DateField()
    data_fechamento = models.DateField()
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.nome


class CandidatoAprovado(models.Model):
    periodo = models.ForeignKey(PeriodoMatricula, on_delete=models.CASCADE)
    nome = models.CharField(max_length=255)
    cpf = models.CharField(max_length=14)
    inscricao = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    status = models.CharField(default='PENDING', max_length=20)
    user = models.OneToOneField(          # ← campo que estava faltando
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='candidato_aprovado'
    )
    is_first_access = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.inscricao} - {self.nome}"