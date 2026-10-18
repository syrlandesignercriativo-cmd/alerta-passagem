# ✈️ Alerta de Passagens — saindo de Recife

O sistema roda sozinho na nuvem do GitHub, 24 horas por dia, sem precisar do
seu computador ligado. Ele faz duas coisas:

### 🔥 1. Sua viagem: Recife ⇄ Fortaleza (29/01 a 31/01/2027) — atenção máxima
- Verifica **3 vezes por dia** (~07h, 13h e 20h, horário de Fortaleza).
- Notificação **urgente** (toca alto) quando ida + volta somar **até R$ 600**,
  e de novo sempre que baixar mais. **R$ 500 ou menos** = 🔥 PREÇO ÓTIMO.
- Botões **Comprar ida** e **Comprar volta** na própria notificação.

### ✈️ 2. Ofertas para todo o Brasil saindo de Recife
- Verifica **1 vez por dia** (~07h): qualquer cidade do Brasil, ida e volta
  **até R$ 600**, nos próximos 6 meses. Um dia procura viagens de fim de
  semana, no outro de uma semana.
- Notificação normal, em resumo, **só com ofertas novas** (não repete).

### 📱 3. Página com tudo
Uma página (site) com Fortaleza em destaque no topo e a lista de ofertas do
Brasil embaixo, com botões para comprar. Atualiza junto com cada verificação.

Tudo gratuito: GitHub (nuvem + página), SerpApi plano grátis (250 buscas/mês;
o sistema usa ~217) e o app ntfy.

---

## Passo 1 — App de notificação no celular (2 min)

1. Instale o app **ntfy** (Play Store ou App Store). Não precisa criar conta.
2. Toque em **+** → "Subscribe to topic".
3. Invente um nome **difícil de adivinhar**, ex.: `passagem-` seguido de letras e números aleatórios.
4. Guarde esse nome — é o seu `NTFY_TOPICO`.

## Passo 2 — Chave gratuita da SerpApi (3 min)

1. Crie conta em https://serpapi.com (plano Free).
2. Copie sua **API Key** no painel — é a sua `SERPAPI_KEY`.

## Passo 3 — Colocar para rodar no GitHub (5 min)

1. Crie conta em https://github.com e um repositório **público** novo chamado
   `alerta-passagem` (precisa ser público para a página grátis funcionar; suas
   chaves ficam escondidas nos "Secrets", ninguém vê).
2. Envie todos estes arquivos (botão "Add file → Upload files"), mantendo a
   pasta `.github/workflows/`.
3. **Settings → Secrets and variables → Actions → New repository secret**:
   - `SERPAPI_KEY` = sua chave da SerpApi
   - `NTFY_TOPICO` = o nome do tópico do Passo 1
4. **Settings → Pages**: em "Branch" escolha `main` e a pasta `/docs` → Save.
   O endereço da sua página aparece ali, algo como
   `https://SEU-USUARIO.github.io/alerta-passagem/`.
5. **Settings → Secrets and variables → Actions → aba Variables**: crie
   `URL_PAGINA` com esse endereço (vira o botão "Ver todas" da notificação).
6. Aba **Actions** → "Monitor de passagens" → **Run workflow** para rodar agora.
   Depois disso ele roda sozinho.

### Ajustes opcionais (aba Variables)

| Variável       | Padrão       | O que é                                     |
|----------------|--------------|---------------------------------------------|
| `PRECO_MAXIMO` | `600`        | Ida + volta máximo para avisar, R$           |
| `PRECO_OTIMO`  | `500`        | Abaixo disso vem como "preço ótimo"          |
| `ORIGEM`       | `REC`        | Aeroporto de saída                           |
| `DESTINO`      | `FOR`        | Destino da sua viagem                        |
| `DATA_IDA`     | `2027-01-29` | Data da ida (AAAA-MM-DD)                     |
| `DATA_VOLTA`   | `2027-01-31` | Data da volta                                |

## Sobre os links

Os botões abrem o **Google Flights** (google.com) já na busca certa. Lá você
escolhe o voo e segue para o site da companhia (Azul, Gol, LATAM) para pagar.
Confira sempre o endereço do site antes de digitar o cartão.

## Quer verificar com mais frequência?

O limite de 3x/dia vem do plano grátis da SerpApi. O plano Starter (US$ 25/mês,
1.000 buscas) permite verificar Fortaleza a cada ~2 horas — é só adicionar mais
horários no arquivo `.github/workflows/monitor.yml`.

## Depois da viagem

Desative: Actions → "Monitor de passagens" → "..." → Disable workflow.
