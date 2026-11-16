# FIAP Generator

Aplicação Flask para geração e acompanhamento de fichas individuais de avaliação periódica (FIAP).

## Requisitos

- Python 3.11 ou superior
- PostgreSQL 14 ou superior para uso persistente

## Configuração local (Windows / PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edite `.env` e defina uma chave aleatória para `SECRET_KEY`:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Cole o resultado no arquivo `.env` e ajuste as variáveis `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` e `DB_PASSWORD` para sua instância PostgreSQL. Os valores do `.env.example` são apenas para desenvolvimento local; troque a senha antes de qualquer implantação. A aplicação conecta ao PostgreSQL usando o driver Psycopg 3.

## Banco e primeiro acesso

Com o banco escolhido acessível, aplique as migrações e crie a conta inicial:

```powershell
python -m flask --app app.py db upgrade
python -m flask --app app.py create-teacher
python app.py
```

O comando `create-teacher` solicita nome, e-mail e senha sem expor a senha no terminal. Não existe cadastro público de contas nesta etapa.

Acesse `http://127.0.0.1:5000`. Para habilitar cookies seguros em produção, configure `SESSION_COOKIE_SECURE=true` e publique o sistema somente atrás de HTTPS.

## Testes

```powershell
pytest
```

## Funcionalidades implementadas

- Autenticação de docentes e painel inicial.
- Cadastro, edição e exclusão protegida de cursos, unidades curriculares e turmas.
- Unidades curriculares e turmas vinculadas a cursos, com carga horária validada e limite de faltas calculado em 25%.
- Cadastro individual de alunos e importação de arquivos CSV/XLSX com validação e pré-visualização.
- Cadastro de FIAP com pré-visualização e confirmação antes de salvar.
- Exportação da ficha salva em PDF A4 no formato do modelo SENAI-SP.

As notas da média da classe e do aluno são inteiras, de 0 a 100. A carga horária e o limite máximo de faltas da ficha vêm da unidade curricular selecionada; o limite corresponde a 25% da carga horária. A turma e o docente são associados a partir do aluno e da sessão autenticada.

As pré-visualizações de importação e de FIAP são temporárias e expiram após 30 minutos. Para remover registros expirados automaticamente, agende diariamente o comando:

```powershell
python -m flask --app app.py cleanup-expired-previews
```
