"""
Monitor de passagens baratas -> notificação no celular (app ntfy) + página web.

1) PRIORIDADE: Recife -> Fortaleza nas datas da viagem (ida e volta pesquisadas
   separadamente). Notificação URGENTE quando o total ficar até PRECO_MAXIMO.
2) OFERTAS BRASIL: qualquer destino no Brasil saindo de Recife, ida e volta até
   PRECO_MAXIMO, nos próximos meses (Google "Explorar"). Notificação normal,
   em resumo, só com ofertas novas.
3) Gera a página docs/index.html com tudo (publicada no GitHub Pages).

Configuração por variáveis de ambiente (veja README.md).
"""

import html
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

# ---------------- Configuração ----------------
ORIGEM = os.getenv("ORIGEM", "REC")
DESTINO = os.getenv("DESTINO", "FOR")
DATA_IDA = os.getenv("DATA_IDA", "2027-01-29")
DATA_VOLTA = os.getenv("DATA_VOLTA", "2027-01-31")
PRECO_MAXIMO = float(os.getenv("PRECO_MAXIMO", "600"))  # ida + volta, R$
PRECO_OTIMO = float(os.getenv("PRECO_OTIMO", "500"))
QUEDA_MINIMA_PCT = float(os.getenv("QUEDA_MINIMA_PCT", "3"))
ADULTOS = os.getenv("ADULTOS", "1")
BRASIL_KGMID = "/m/015fr"  # código do Google para "Brasil"

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
NTFY_TOPICO = os.getenv("NTFY_TOPICO")
NTFY_SERVIDOR = os.getenv("NTFY_SERVIDOR", "https://ntfy.sh")
URL_PAGINA = os.getenv("URL_PAGINA", "")  # link da sua página, para o botão da notificação

PASTA = Path(__file__).parent
ARQUIVO_HISTORICO = PASTA / "historico_precos.json"
ARQUIVO_PAGINA = PASTA / "docs" / "index.html"
FUSO_BR = timezone(timedelta(hours=-3))
SERPAPI = "https://serpapi.com/search.json"


def brl(v: float) -> str:
    return f"R$ {v:,.0f}".replace(",", ".")


def dia(data: str) -> str:
    return datetime.fromisoformat(data).strftime("%d/%m") if data else "?"


def chamar_serpapi(params: dict) -> dict:
    params = {**params, "currency": "BRL", "hl": "pt-br", "gl": "br",
              "adults": ADULTOS, "api_key": SERPAPI_KEY}
    r = requests.get(SERPAPI, params=params, timeout=90)
    r.raise_for_status()
    dados = r.json()
    if "error" in dados:
        raise RuntimeError(dados["error"])
    return dados


# ---------------- 1) Recife -> Fortaleza nas datas ----------------
def buscar_trecho(origem: str, destino: str, data: str) -> dict | None:
    dados = chamar_serpapi({"engine": "google_flights", "departure_id": origem,
                            "arrival_id": destino, "outbound_date": data, "type": "2"})
    voos = [v for v in dados.get("best_flights", []) + dados.get("other_flights", []) if v.get("price")]
    if not voos:
        return None
    v = min(voos, key=lambda x: x["price"])
    seg = v.get("flights", [])
    return {
        "preco": v["price"],
        "companhia": ", ".join(sorted({s.get("airline", "?") for s in seg})),
        "saida": seg[0]["departure_airport"].get("time", "")[-5:] if seg else "",
        "chegada": seg[-1]["arrival_airport"].get("time", "")[-5:] if seg else "",
        "paradas": max(len(seg) - 1, 0),
        "link": dados.get("search_metadata", {}).get("google_flights_url", ""),
    }


# ---------------- 2) Ofertas para todo o Brasil ----------------
def buscar_ofertas_brasil() -> list[dict]:
    ofertas = []
    # 1 = viagem de fim de semana, 2 = uma semana. Alterna por dia para caber
    # no plano grátis da SerpApi (1 busca/dia em vez de 2).
    duracao_do_dia = "1" if datetime.now(FUSO_BR).toordinal() % 2 == 0 else "2"
    for duracao in (duracao_do_dia,):
        dados = chamar_serpapi({
            "engine": "google_travel_explore", "departure_id": ORIGEM,
            "arrival_area_id": BRASIL_KGMID, "type": "1", "month": "0",
            "travel_duration": duracao, "max_price": str(int(PRECO_MAXIMO)),
        })
        for d in dados.get("destinations", []):
            preco = d.get("flight_price")
            if not preco or preco > PRECO_MAXIMO:
                continue
            ofertas.append({
                "cidade": d.get("name", "?"),
                "codigo": (d.get("destination_airport") or {}).get("code", ""),
                "preco": preco,
                "ida": d.get("start_date", ""),
                "volta": d.get("end_date", ""),
                "companhia": d.get("airline", ""),
                "paradas": d.get("number_of_stops"),
                "link": d.get("link") or "https://www.google.com/travel/explore",
            })
    # mantém só a oferta mais barata de cada cidade
    melhores = {}
    for o in ofertas:
        if o["cidade"] not in melhores or o["preco"] < melhores[o["cidade"]]["preco"]:
            melhores[o["cidade"]] = o
    return sorted(melhores.values(), key=lambda o: o["preco"])


# ---------------- Notificação no celular (ntfy) ----------------
def notificar(titulo, texto, links=(), prioridade=3, tags=("airplane",)) -> None:
    if not NTFY_TOPICO:
        print(f"[aviso] NTFY_TOPICO não configurado. Notificação seria:\n{titulo}\n{texto}\n")
        return
    payload = {"topic": NTFY_TOPICO, "title": titulo, "message": texto,
               "tags": list(tags), "priority": prioridade}
    links = [(n, u) for n, u in links if u]
    if links:
        payload["click"] = links[0][1]
        payload["actions"] = [{"action": "view", "label": n, "url": u} for n, u in links[:3]]
    requests.post(NTFY_SERVIDOR, json=payload, timeout=30).raise_for_status()


# ---------------- Histórico ----------------
def carregar_historico() -> dict:
    if ARQUIVO_HISTORICO.exists():
        txt = ARQUIVO_HISTORICO.read_text(encoding="utf-8").strip()
        return json.loads(txt) if txt else {}
    return {}


def salvar_historico(h: dict) -> None:
    ARQUIVO_HISTORICO.write_text(json.dumps(h, indent=2, ensure_ascii=False), encoding="utf-8")


def linha_voo(nome: str, data: str, v: dict) -> str:
    escalas = "direto" if v["paradas"] == 0 else f"{v['paradas']} parada(s)"
    return f"{nome} {dia(data)}: {brl(v['preco'])} · {v['companhia']} · {v['saida']}→{v['chegada']} · {escalas}"


# ---------------- Rotinas ----------------
def checar_viagem(h: dict, agora: str) -> None:
    ida = buscar_trecho(ORIGEM, DESTINO, DATA_IDA)
    volta = buscar_trecho(DESTINO, ORIGEM, DATA_VOLTA)
    if not ida or not volta:
        print("Recife-Fortaleza: nenhum voo encontrado em um dos trechos.")
        return
    total = ida["preco"] + volta["preco"]
    v = h.setdefault("viagem", {})
    v.setdefault("leituras", []).append({"quando": agora, "ida": ida["preco"],
                                         "volta": volta["preco"], "total": total})
    v["leituras"] = v["leituras"][-300:]
    v["menor_total"] = min(total, v.get("menor_total") or total)
    v["atual"] = {"quando": agora, "total": total, "ida": ida, "volta": volta}
    print(f"[VIAGEM] ida {brl(ida['preco'])} + volta {brl(volta['preco'])} = {brl(total)}")

    ultimo = v.get("ultimo_alerta")
    if total <= PRECO_MAXIMO and (ultimo is None or total <= ultimo * (1 - QUEDA_MINIMA_PCT / 100)):
        v["ultimo_alerta"] = total
        if total <= PRECO_OTIMO:
            titulo = f"🔥 SUA VIAGEM: PREÇO ÓTIMO {brl(total)}"
        elif ultimo:
            titulo = f"🔥 SUA VIAGEM baixou: {brl(total)}"
        else:
            titulo = f"🔥 SUA VIAGEM no orçamento: {brl(total)}"
        texto = "\n".join([
            f"Recife ⇄ Fortaleza · {dia(DATA_IDA)} a {dia(DATA_VOLTA)}",
            linha_voo("Ida", DATA_IDA, ida),
            linha_voo("Volta", DATA_VOLTA, volta),
            "Toque nos botões para comprar cada trecho. Promoção some rápido!",
        ])
        notificar(titulo, texto, [("Comprar ida", ida["link"]), ("Comprar volta", volta["link"])],
                  prioridade=5, tags=("rotating_light",))


def checar_brasil(h: dict, agora: str) -> None:
    ofertas = buscar_ofertas_brasil()
    b = h.setdefault("brasil", {})
    ja_avisadas = b.get("avisadas", {})  # "cidade|ida|volta" -> preço avisado
    novas = []
    for o in ofertas:
        chave = f"{o['cidade']}|{o['ida']}|{o['volta']}"
        antes = ja_avisadas.get(chave)
        if antes is None or o["preco"] <= antes * (1 - QUEDA_MINIMA_PCT / 100):
            novas.append(o)
            ja_avisadas[chave] = o["preco"]
    b["avisadas"] = dict(list(ja_avisadas.items())[-500:])
    b["atual"] = {"quando": agora, "ofertas": ofertas}
    print(f"[BRASIL] {len(ofertas)} ofertas até {brl(PRECO_MAXIMO)}, {len(novas)} novas")

    if novas:
        linhas = [f"{o['cidade']}: {brl(o['preco'])} ({dia(o['ida'])}–{dia(o['volta'])})" for o in novas[:8]]
        if len(novas) > 8:
            linhas.append(f"+ {len(novas) - 8} outras na página")
        notificar(f"✈️ {len(novas)} oferta(s) saindo de Recife até {brl(PRECO_MAXIMO)}",
                  "\n".join(linhas),
                  [("Ver todas", URL_PAGINA), (f"Abrir {novas[0]['cidade']}", novas[0]["link"])],
                  prioridade=3, tags=("airplane",))


# ---------------- 3) Página ----------------
def gerar_pagina(h: dict, agora: str) -> None:
    e = html.escape
    v = h.get("viagem", {}).get("atual")
    if v:
        tot = v["total"]
        selo = ("🔥 Preço ótimo" if tot <= PRECO_OTIMO else
                "✅ Dentro do orçamento" if tot <= PRECO_MAXIMO else "⏳ Ainda acima do orçamento")
        cls = "ok" if tot <= PRECO_MAXIMO else "acima"
        menor = h["viagem"].get("menor_total")

        def trecho(nome, data, t):
            esc = "direto" if t["paradas"] == 0 else f"{t['paradas']} parada(s)"
            return (f'<div class="trecho"><div><b>{nome} · {dia(data)}</b><br>'
                    f'<span>{e(t["companhia"])} · {t["saida"]}→{t["chegada"]} · {esc}</span></div>'
                    f'<div class="dir"><b>{brl(t["preco"])}</b><a class="btn" href="{e(t["link"])}" '
                    f'target="_blank" rel="noopener">Comprar</a></div></div>')

        bloco_viagem = (f'<section class="viagem {cls}"><p class="tag">SUA VIAGEM</p>'
                        f'<h2>Recife ⇄ Fortaleza · {dia(DATA_IDA)} a {dia(DATA_VOLTA)}</h2>'
                        f'<p class="total">{brl(tot)} <small>ida + volta</small></p>'
                        f'<p class="selo">{selo} · seu limite: {brl(PRECO_MAXIMO)}'
                        f'{f" · menor já visto: {brl(menor)}" if menor else ""}</p>'
                        f'{trecho("Ida", DATA_IDA, v["ida"])}{trecho("Volta", DATA_VOLTA, v["volta"])}'
                        f'<p class="mini">Verificado em {v["quando"]}</p></section>')
    else:
        bloco_viagem = '<section class="viagem"><p>Aguardando a primeira verificação…</p></section>'

    b = h.get("brasil", {}).get("atual")
    if b and b["ofertas"]:
        itens = "".join(
            f'<a class="oferta" href="{e(o["link"])}" target="_blank" rel="noopener">'
            f'<div><b>{e(o["cidade"])}</b> <span>{e(o["codigo"])}</span><br>'
            f'<span>{dia(o["ida"])} – {dia(o["volta"])}'
            f'{" · " + e(o["companhia"]) if o["companhia"] else ""}</span></div>'
            f'<b class="preco">{brl(o["preco"])}</b></a>' for o in b["ofertas"])
        bloco_brasil = (f'<h3>Ofertas saindo de Recife até {brl(PRECO_MAXIMO)} (ida + volta)</h3>'
                        f'<p class="mini">Próximos 6 meses · verificado em {b["quando"]}</p>{itens}')
    else:
        bloco_brasil = f'<h3>Ofertas saindo de Recife até {brl(PRECO_MAXIMO)}</h3><p>Nenhuma oferta nesse preço agora.</p>'

    pagina = f"""<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Alerta de Passagens</title>
<style>
:root{{--bg:#f5f6f8;--card:#fff;--txt:#14171c;--sub:#5d6573;--ok:#0a7a45;--warn:#b25d00;--acc:#0b57d0;--brd:#e3e6eb}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0f1115;--card:#1a1d23;--txt:#eef0f3;--sub:#9aa3b2;--ok:#3ccf8a;--warn:#ffae4a;--acc:#7cacf8;--brd:#2a2f38}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--txt);font:16px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}}
main{{max-width:680px;margin:0 auto;padding:20px 16px 40px}}h1{{font-size:20px;margin:0 0 16px}}
.viagem{{background:var(--card);border:2px solid var(--brd);border-radius:16px;padding:18px;margin-bottom:28px}}
.viagem.ok{{border-color:var(--ok)}}.tag{{margin:0;font-size:12px;font-weight:700;letter-spacing:.08em;color:var(--acc)}}
h2{{font-size:18px;margin:4px 0 8px}}.total{{font-size:34px;font-weight:800;margin:0}}.total small{{font-size:14px;font-weight:400;color:var(--sub)}}
.selo{{margin:4px 0 14px;color:var(--sub)}}.ok .selo{{color:var(--ok);font-weight:600}}.acima .selo{{color:var(--warn)}}
.trecho,.oferta{{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:12px 0;border-top:1px solid var(--brd)}}
.trecho span,.oferta span,.mini{{color:var(--sub);font-size:14px}}.dir{{text-align:right;white-space:nowrap}}
.btn{{display:inline-block;margin-left:10px;background:var(--acc);color:#fff;padding:7px 14px;border-radius:999px;text-decoration:none;font-weight:600;font-size:14px}}
.oferta{{background:var(--card);border:1px solid var(--brd);border-radius:12px;padding:12px 14px;margin:8px 0;color:inherit;text-decoration:none}}
.preco{{font-size:18px;white-space:nowrap}}h3{{font-size:17px;margin:0 0 2px}}
</style></head><body><main><h1>✈️ Alerta de Passagens</h1>{bloco_viagem}{bloco_brasil}
<p class="mini">Atualizado em {agora} (horário de Fortaleza). Preços do Google Flights; confirme o valor final no site da companhia antes de pagar.</p>
</main></body></html>"""
    ARQUIVO_PAGINA.parent.mkdir(exist_ok=True)
    ARQUIVO_PAGINA.write_text(pagina, encoding="utf-8")


# ---------------- Principal ----------------
def main() -> int:
    if "--teste" in sys.argv:
        notificar("Teste do alerta de passagens ✅", "Se você está vendo isso, está funcionando!",
                  [("Abrir Google Flights", "https://www.google.com/travel/flights")])
        return 0
    if not SERPAPI_KEY:
        print("Defina a variável SERPAPI_KEY.")
        return 1

    agora_dt = datetime.now(FUSO_BR)
    agora = agora_dt.strftime("%d/%m %H:%M")
    h = carregar_historico()

    try:
        checar_viagem(h, agora)
    except Exception as ex:
        print(f"[erro viagem] {ex}")

    # Ofertas do Brasil: 1x por dia (rodada da manhã) ou quando pedir --brasil
    if "--brasil" in sys.argv or agora_dt.hour < 10:
        try:
            checar_brasil(h, agora)
        except Exception as ex:
            print(f"[erro brasil] {ex}")

    salvar_historico(h)
    gerar_pagina(h, agora)
    return 0


if __name__ == "__main__":
    sys.exit(main())
