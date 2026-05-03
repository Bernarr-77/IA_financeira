# Bia - Secretária Financeira Autônoma via WhatsApp 🤖💰

A **Bia** é uma assistente financeira inteligente baseada em Inteligência Artificial que funciona diretamente pelo seu WhatsApp. Em vez de usar planilhas complexas ou aplicativos cheios de menus, você simplesmente conversa com a Bia em linguagem natural, e ela cuida de tudo para você.

## ✨ O que a Bia faz?

A Bia possui 22 "superpoderes" projetados para facilitar o seu controle financeiro:

### 📝 Gestão de Transações
- **Registrar Gasto:** "Gastei 50 no Subway" ou "Comprei um notebook por 3000 em 5x". Ela entende o valor, a descrição, se foi parcelado e até sugere a categoria.
- **Registrar Receita:** "Recebi 2000 de salário".
- **Deletar/Editar Transações:** Corrige descrições, valores ou apaga lançamentos errados pelo ID.
- **Buscar Transações:** "Onde gastei com farmácia?" - ela vasculha o histórico para você.

### 📊 Consultas e Relatórios
- **Resumo do Mês & Saldo Livre:** Responde rapidamente "Quanto gastei esse mês?" e "Quanto ainda posso gastar?" com base no seu limite mensal configurado.
- **Consulta por Categoria & Ranking:** Mostra exatamente para onde seu dinheiro está indo ("Em que estou gastando mais?").
- **Comparação de Meses:** "Gastei mais esse mês ou no passado?".
- **Exportação de Resumo:** Gera um relatório de texto limpo para você copiar e compartilhar.

### 💳 Controle de Parcelas e Dívidas
- **Lembretes e Vencimentos:** Mostra o que vence "hoje" ou nos próximos 30 dias.
- **Controle de Pagamento:** Marca parcelas específicas como pagas ("Paguei a parcela do celular").
- **Nível de Comprometimento:** Calcula quanto da sua renda já está comprometida com dívidas futuras.

### 🧠 Inteligência e Perfil
- **Previsão de Gastos:** Estima como vai fechar o mês com base no seu ritmo atual.
- **Alertas e Sugestões:** Avisa se você está passando do limite em alguma categoria e dá dicas reais de economia.
- **Perfil Personalizável:** Você configura seu limite mensal e o dia de vencimento do cartão.

### 🤖 Autonomia Completa
- **Entende Áudios:** Você pode mandar comandos de voz, e ela transcreve e executa a ação.
- **Notificações Ativas (Celery Workers):** A Bia tem iniciativa. Ela não espera você perguntar, ela te avisa sozinha:
  - 🕖 **07h00:** Alerta de parcelas/contas que vencem hoje.
  - 🕘 **21h00:** Resumo diário do que você gastou no dia.
  - 🗓️ **Segunda 08h00:** Relatório semanal detalhado.
  - 📊 **Dia 1 às 08h00:** Fechamento completo do mês que acabou.

---

## 🛠️ Stack Tecnológico

- **Backend:** Python, FastAPI
- **Banco de Dados:** PostgreSQL, SQLAlchemy (ORM), Alembic (Migrations)
- **Inteligência Artificial:** Google GenAI SDK (Modelo: *Gemini 2.5 Pro*) + Structured Outputs (Pydantic/Instructor)
- **Mensageria e Integração:** Evolution API (WhatsApp Webhook)
- **Automação e Tarefas Assíncronas:** Celery, Celery Beat, Redis (Broker)

---

## 🚀 Como funciona a arquitetura?

1. Você manda uma mensagem no WhatsApp.
2. A **Evolution API** recebe e dispara um *Webhook* para a API do FastAPI.
3. A API resgata o seu histórico de conversas no banco de dados para ter contexto.
4. O histórico e a nova mensagem são enviados para o **LLM (Gemini)**.
5. O LLM decide, de forma autônoma (usando *Function Calling*), qual ferramenta (tool) deve acionar.
6. A ferramenta é executada (ex: salvar no banco, calcular saldo), e o LLM formula a resposta amigável.
7. A resposta é enviada de volta pelo WhatsApp.
8. Paralelamente, processos **Celery Beat** monitoram as datas e disparam resumos/alertas proativamente nos horários configurados.

O sistema também é **Multi-Instância**, ou seja, vários usuários (cada um com seu próprio celular conectado na Evolution API) podem interagir simultaneamente com a Bia.
