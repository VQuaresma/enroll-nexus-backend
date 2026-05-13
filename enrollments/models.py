from django.db import models

class Enrollment(models.Model):
    # --- DADOS PESSOAIS (Existentes + Novos do Doc) ---
    full_name = models.CharField(max_length=255, verbose_name="Nome Completo")
    cpf = models.CharField(max_length=14, unique=True)
    date_of_birth = models.DateField()
    rg = models.CharField(max_length=20)
    issuing_body = models.CharField(max_length=50, verbose_name="Órgão Expedidor")
    dispatch_date = models.DateField(verbose_name="Data de Expedição RG", null=True, blank=True)
    
    # Novos campos de Documentação
    voter_id = models.CharField(max_length=20, verbose_name="Título de Eleitor")
    voter_zone = models.CharField(max_length=10, verbose_name="Zona")
    voter_section = models.CharField(max_length=10, verbose_name="Seção")
    military_id = models.CharField(max_length=50, blank=True, null=True, verbose_name="Certificado Militar")
    military_date = models.DateField(blank=True, null=True, verbose_name="Data Exp. Militar")
    military_series = models.CharField(max_length=10, null=True, blank=True)
    military_category = models.CharField(max_length=50, null=True, blank=True)
    military_dispatch_date = models.DateField(null=True, blank=True)
    
    # Filiação e Perfil
    mother_name = models.CharField(max_length=255, verbose_name="Nome da Mãe")
    father_name = models.CharField(max_length=255, verbose_name="Nome do Pai")
    gender = models.CharField(max_length=20, verbose_name="Sexo") # MASCULINO / FEMININO
    marital_status = models.CharField(max_length=50, verbose_name="Estado Civil")
    race_color = models.CharField(max_length=20, verbose_name="Raça/Cor")
    
    # Naturalidade (Exigência UFPA)
    birth_country = models.CharField(max_length=100, default="Brasil", verbose_name="País")
    birth_state = models.CharField(max_length=2, verbose_name="UF de Nascimento")
    birth_city = models.CharField(max_length=100, verbose_name="Município de Nascimento")
    nationality = models.CharField(max_length=100, verbose_name="Nacionalidade")

    # --- ENDEREÇO E CONTATO ---
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, verbose_name="Celular") # Mantive apenas o Celular
    zip_code = models.CharField(max_length=10)
    street = models.CharField(max_length=255)
    number = models.CharField(max_length=10)
    complement = models.CharField(max_length=100, blank=True, null=True)
    neighbourhood = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)

    # --- PESSOAS DE CONTATO (Emergência no Doc) ---
    emergency_contact_1 = models.CharField(max_length=255, verbose_name="Contato Próximo 1")
    emergency_phone_1 = models.CharField(max_length=20, verbose_name="Celular Contato 1")
    emergency_contact_2 = models.CharField(max_length=255, verbose_name="Contato Próximo 2")
    emergency_phone_2 = models.CharField(max_length=20, verbose_name="Celular Contato 2")

    # --- FORMAÇÃO E BANCÁRIO (Já simplificados por você) ---
    institution = models.CharField(max_length=255, verbose_name="Instituição")
    course = models.CharField(max_length=255, verbose_name="Curso")
    graduation_year = models.CharField(max_length=4, verbose_name="Ano de Conclusão")
    bank_name = models.CharField(max_length=100)
    agency = models.CharField(max_length=20)
    account_number = models.CharField(max_length=20)

    # Controle
    registration_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, default='PENDING')

    def __str__(self):
        return self.full_name