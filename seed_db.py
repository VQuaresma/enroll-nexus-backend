import os
import django
import random

# AJUSTE: Nome da pasta do seu projeto onde está o settings.py
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings') 
django.setup()

from enrollments.models import Enrollment 

def seed_data(n=10):
    niveis = ['MESTRADO', 'DOUTORADO']
    programas = ['PGEDA', 'PPEB'] # <-- Nossos dois programas
    
    nomes = [
        "Vitor Quaresma", "Maria Silva", "João Santos", "Ana Oliveira", 
        "Carlos Souza", "Beatriz Lima", "Fernando Costa", "Juliana Rocha",
        "Ricardo Almeida", "Patrícia Gomes"
    ]

    print(f"⏳ Gerando {n} inscrições para o NEB...")

    for i in range(n):
        nome_random = random.choice(nomes) + f" {random.randint(10, 99)}"
        programa_sorteado = random.choice(programas)
        Enrollment.objects.create(

            # Identificação do Programa
            program=programa_sorteado, # <-- Salva no banco de dados
            # Dados Pessoais
            full_name=nome_random,
            social_name="",
            program_level=random.choice(niveis),
            cpf=f"{random.randint(100,999)}.{random.randint(100,999)}.{random.randint(100,999)}-{random.randint(10,99)}",
            date_of_birth="1998-05-20",
            rg=f"{random.randint(1000000, 9999999)}",
            issuing_body="SEGUP",
            dispatch_date="2015-10-10",
            
            # Documentação
            voter_id="1234567890",
            voter_zone="01",
            voter_section="150",
            mother_name="Nome da Mãe de Teste",
            father_name="Nome do Pai de Teste",
            gender="MASCULINO" if i % 2 == 0 else "FEMININO",
            marital_status="SOLTEIRO(A)",
            race_color="PARDA",
            
            # Naturalidade
            birth_country="Brasil",
            birth_state="PA",
            birth_city="Belém",
            nationality="Brasileira",

            # Endereço e Contato
            email=f"teste_{random.randint(1000, 9999)}@ufpa.br",
            phone="91988887777",
            zip_code="66000-000",
            street="Rua de Teste",
            number=str(i),
            neighbourhood="Guamá",
            city="Belém",
            state="PA",

            # Emergência
            emergency_contact_1="Contato 1",
            emergency_phone_1="91911112222",
            emergency_contact_2="Contato 2",
            emergency_phone_2="91933334444",

            # Formação e Bancário
            institution="UFPA",
            course="Sistemas de Informação",
            graduation_year="2023",
            bank_name="Banco do Brasil",
            agency="0001",
            account_number=f"12345-{i}"
        )

    print(f"✅ Sucesso! {n} inscrições adicionadas.")

if __name__ == '__main__':
    seed_data()