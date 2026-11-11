# Backend Enroll Nexus no Render

Preparação local concluída; nenhum recurso remoto foi criado ou alterado.
O frontend permanece no provedor atual.

## Antes de publicar

1. Conectar a conta Render para identificar o serviço existente, o banco e o plano.
2. Confirmar a origem HTTPS do frontend para `FRONTEND_URL`.
3. Revisar e publicar no GitHub as alterações locais. Não houve commit ou push automático.
4. Se for um serviço novo, revisar custos antes de aplicar `render.yaml`: ele propõe backend Starter, PostgreSQL Basic e disco persistente de 1 GB. Não aplicar esse blueprint sobre um banco existente.

O repositório já rastreia `backup.json` e arquivos em `media/`. Eles não devem ser usados para povoar o ambiente publicado. Foram adicionados ao `.gitignore`, mas isso **não remove arquivos já rastreados nem seu histórico**. Revisar o conteúdo rastreado antes de um novo push; nenhum arquivo local foi apagado.

## Serviço existente

Preservar o `DATABASE_URL` e o disco existentes após confirmar que são os recursos corretos. Usar:

```text
Build Command: bash build-render.sh
Start Command: python manage.py migrate --noinput && gunicorn core.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120
Health Check Path: /health/
```

Variáveis do serviço:

| Variável | Valor |
| --- | --- |
| `DJANGO_SETTINGS_MODULE` | `core.render_settings` |
| `DEBUG` | `False` |
| `SECRET_KEY` | Segredo de produção gerado pelo Render, com pelo menos 50 caracteres. Não usar o `.env` local. |
| `DATABASE_URL` | Conexão PostgreSQL do ambiente, com TLS. |
| `FRONTEND_URL` | Origem HTTPS do frontend, sem caminho ou barra final. |
| `MEDIA_ROOT` | `/var/data/media`, com disco persistente montado em `/var/data`. |
| `ALLOWED_HOSTS` | Domínios próprios adicionais, separados por vírgula, se existirem. O hostname do Render é incorporado automaticamente. |

As migrações são aplicadas no início do serviço. O build somente instala dependências, executa verificações de produção e coleta arquivos estáticos. Não executa seeds, importação de backup ou criação de usuários.

## Produção e acesso

- O SQLite local e suas credenciais de teste não são importados. Não reutilizar a conta/senha de teste como acesso público.
- Criar um administrador de produção pelo comando interativo `python manage.py createsuperuser` no ambiente Render, com senha forte; em serviço existente, preservar as contas válidas.
- A configuração de produção rejeita chave fraca e banco SQLite; força HTTPS, cookies seguros e hosts/CORS explícitos.
- WhiteNoise serve somente os arquivos estáticos. Os documentos permanecem protegidos pelas views autenticadas existentes e são armazenados no disco persistente.
- No provedor do frontend, definir `VITE_API_URL` para a origem HTTPS real do backend, sem `/api/enrollments/`, e reconstruir o frontend.

## Validação já realizada

- `manage.py check --deploy --fail-level WARNING` com a configuração de produção e credenciais fictícias de validação: passou. Não foi estabelecida conexão com banco remoto.
- `collectstatic` em diretório temporário: passou.
- Configuração rejeitou segredo curto e URL SQLite, como esperado.
- Testes do backend foram executados em banco isolado, incluindo os testes de disponibilidade de `/health/`.

## Validação após o deploy

Confirmar `/health/`, CSS do Django Admin, login JWT, refresh, CORS da origem do frontend e acesso autenticado a matrículas/documentos. Conferir persistência de um documento de teste após reinício usando dados descartáveis autorizados. O funcionamento remoto permanece não testado até haver acesso à conta e deploy efetivo.

Referências: [Django no Render](https://render.com/docs/deploy-django), [discos persistentes](https://render.com/docs/disks), [blueprints](https://render.com/docs/blueprint-spec).
