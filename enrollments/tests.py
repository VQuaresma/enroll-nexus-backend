from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

class EnrollmentTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/api/enrollments/submit/" # Verifique se sua rota é essa

    def test_submit_enrollment_error_check(self):
        # Dados incompletos propositalmente para ver o erro
        data = {
  "full_name": "Vitor Quaresma Da Silva",
  "cpf": "06703385246",
  "date_of_birth": "2000-01-01",
  "degree": "MSC",
  "rg": "1234567",
  "issuing_body": "SSP/PA",
  "dispatch_date": "2015-05-20",
  "mother_name": "Nome da Sua Mãe",
  "father_name": "Nome do Seu Pai",
  "gender": "MASCULINO",
  "marital_status": "Solteiro",
  "race_color": "PARDA",
  "voter_id": "123456780100",
  "voter_zone": "001",
  "voter_section": "0010",
  "military_id": "123456789",
  "military_series": "A",
    "military_category": "2ª",
    "military_dispatch_date": "2018-12-10",
  "nationality": "Brasileira",
  "birth_country": "Brasil",
  "birth_state": "PA",
  "birth_city": "Belém",
  "email": "vitor@exemplo.com",
  "phone": "91988887777",
  "emergency_contact_1": "Contato de Teste 1",
    "emergency_phone_1": "91999999999",
    "emergency_contact_2": "Contato de Teste 2",
    "emergency_phone_2": "91888888888",
  "zip_code": "66000000",
  "street": "Rua Exemplo",
  "number": "123",
  "neighbourhood": "Marco",
  "city": "Belém",
  "state": "PA",
  "institution": "UFPA",
  "course": "Sistemas de Informação",
  "graduation_year": 2026,
  "lattes_url": "http://lattes.cnpq.br/0000000000000000",
  "research_area": "Engenharia de Software",
  "bank_name": "Banco do Brasil",
  "compe_code": "001",
  "agency": "1234",
  "account_number": "56789-0",
  "bank_account_type": "CC"
}
        
        response = self.client.post(self.url, data, format='json')
        
        # Se der erro 400, o print abaixo vai te mostrar EXATAMENTE 
        # qual campo o Django está reclamando e por quê.
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            print("\n--- ERROS DO DJANGO ---")
            print(response.data) 
            print("-----------------------\n")
            
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


