from playwright.sync_api import sync_playwright
from datetime import datetime
import os
import json

# Caminhos configuráveis via variável de ambiente, com um valor padrão
# relativo ao próprio projeto (evita expor usuário/pasta local no repositório).
CONFIG_PATH = os.environ.get("IDRAC_CONFIG_PATH", "servidores.json")
BASE_OUTPUT = os.environ.get("IDRAC_OUTPUT_DIR", "output/prints")

# Tempo extra (em segundos) que o script vai esperar APÓS o carregamento sumir
TEMPO_ESPERA_SECAO = 15

SELETORES = {
    "idrac8": {
        "user": "#user",
        "senha": "#password",
        "botao": "button:has-text('Submit')",
        "frame_menu": "treelist",
        "frame_conteudo": "da",
        "js_storage": "f_select('C32', '', '')",
        "js_lcd": None,
    },
    "idrac7": {
        "user": "#user",
        "senha": "#password",
        "botao": "#btnOK",
        "frame_menu": "treelist",
        "frame_conteudo": "da",
        "js_storage": "f_select('C32', '', '')",
        "js_lcd": None,
    },
    "idrac6": {
        "user": "#user",
        "senha": "#password",
        "botao": 'role=link[name="Submit"]',
        "frame_menu": "treelist",
        "frame_conteudo": "da",
        "js_storage": None,
        "js_lcd": "f_select('C10', '', '')",
    },
    "idrac9": {
        "user": "input[name='username']",
        "senha": "input[name='password']",
        "botao": "button:has-text('Log In')",

        # Itens de menu clicáveis (barra de navegação) - não usa frameset
        "menu_dashboard": "strong[translate='menu_dashboard']",
        "menu_storage": "strong[translate='menu_storage']",
        # "menu_lcd": "strong[translate='...']",  # ainda falta confirmar

        # Títulos que confirmam que a seção carregou de verdade
        "titulo_dashboard": "span[translate='menu_dashboard']",
        "titulo_storage": "span[translate='menu_storage']",
        # "titulo_lcd": "span[translate='...']",  # ainda falta confirmar
    },
}

# URL de login padrão (idrac6/7/8). O idrac9 usa uma URL diferente (interface REST GUI),
# então ele tem entrada própria neste dicionário.
LOGIN_URL_TEMPLATE = "https://{host}/login.html"
LOGIN_URL_TEMPLATES = {
    "idrac9": "https://{host}/restgui/index.html",
}


def obter_login_url(geracao, host):
    template = LOGIN_URL_TEMPLATES.get(geracao, LOGIN_URL_TEMPLATE)
    return template.format(host=host)

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    servidores = json.load(f)

# Formato de data e hora: dd_mm_aa_hh_mm
timestamp = datetime.now().strftime("%d_%m_%y_%H_%M")


def tirar_print(page, output_dir, nome_servidor, nome_secao, timestamp):
    """
    Gera o print no formato: dd_mm_aa_hh_mm_nome_do_servidor_secao.png
    Exemplo: 31_07_26_14_30_S0039_dashboard.png
    """
    nome_arquivo = f"{timestamp}_{nome_servidor}_{nome_secao}.png"
    path_final = os.path.join(output_dir, nome_arquivo)
    page.screenshot(path=path_final, full_page=True)


def aguardar_conteudo_carregar(page, frame_name, espera_extra_s=15, timeout_ms=45000):
    page.wait_for_timeout(2000)

    seletores_spinner = [
        "[class*='load' i]",
        "[id*='load' i]",
        "[class*='spinner' i]",
        "[class*='busy' i]",
        "[role='progressbar']",
        "img[src*='load' i]",
        "img[src*='spin' i]",
        "img[src*='progress' i]",
        "#loading_div",
        "#progress_div",
        "#wait_div",
        ".loading",
    ]

    tempo_decorrido = 0
    intervalo = 1000

    print(f"    -> Aguardando término do carregamento no frame '{frame_name}'...")
    while tempo_decorrido < timeout_ms:
        content_frame = page.frame(name=frame_name)
        if not content_frame:
            page.wait_for_timeout(intervalo)
            tempo_decorrido += intervalo
            continue

        algum_visivel = False
        for seletor in seletores_spinner:
            try:
                loc = content_frame.locator(seletor)
                if loc.count() > 0 and loc.first.is_visible():
                    algum_visivel = True
                    break
            except Exception:
                pass

        if not algum_visivel:
            break

        page.wait_for_timeout(intervalo)
        tempo_decorrido += intervalo

    print(f"    -> Estabilizando tela ({espera_extra_s}s de pausa)...")
    page.wait_for_timeout(espera_extra_s * 1000)


def processar_frameset(page, sel, output_dir, nome_servidor, timestamp, possui_storage, possui_lcd):
    print("    -> Localizando estrutura de framesets...")
    page.wait_for_selector(f"frame[name='{sel['frame_menu']}']", state="attached", timeout=40000)
    page.wait_for_selector(f"frame[name='{sel['frame_conteudo']}']", state="attached", timeout=40000)

    # --- Dashboard ---
    print("    -> Processando Dashboard...")
    aguardar_conteudo_carregar(page, sel["frame_conteudo"], espera_extra_s=TEMPO_ESPERA_SECAO)
    tirar_print(page, output_dir, nome_servidor, "dashboard", timestamp)
    print("    -> Print da Dashboard salvo!")

    frame_menu = page.frame(name=sel["frame_menu"])

    # --- Storage ---
    if possui_storage and sel.get("js_storage"):
        try:
            print("    -> Solicitando aba Storage...")
            frame_menu.evaluate(sel["js_storage"])
            aguardar_conteudo_carregar(page, sel["frame_conteudo"], espera_extra_s=TEMPO_ESPERA_SECAO)
            tirar_print(page, output_dir, nome_servidor, "storage", timestamp)
            print("    -> Print de Storage salvo!")
        except Exception as e:
            print(f"    -> Storage falhou: {e}")

    # --- LCD ---
    if possui_lcd and sel.get("js_lcd"):
        try:
            print("    -> Solicitando aba LCD...")
            frame_menu.evaluate(sel["js_lcd"])
            aguardar_conteudo_carregar(page, sel["frame_conteudo"], espera_extra_s=TEMPO_ESPERA_SECAO)
            tirar_print(page, output_dir, nome_servidor, "lcd", timestamp)
            print("    -> Print de LCD salvo!")
        except Exception as e:
            print(f"    -> LCD falhou: {e}")


def processar_idrac9(page, sel, output_dir, nome_servidor, timestamp, possui_storage, possui_lcd):
    """
    iDRAC9 não usa frameset (é uma SPA/REST GUI), então a navegação é feita
    clicando diretamente nos itens de menu e esperando o TÍTULO da seção
    (span) aparecer — isso garante que a página realmente trocou de tela.
    """
    # --- Dashboard ---
    print("    -> Processando Dashboard...")
    page.wait_for_selector(sel["titulo_dashboard"], timeout=15000)
    page.wait_for_timeout(5000)
    tirar_print(page, output_dir, nome_servidor, "dashboard", timestamp)
    print("    -> Print da Dashboard salvo!")

    # --- Storage ---
    if possui_storage and sel.get("menu_storage"):
        try:
            print("    -> Solicitando aba Storage...")
            elemento_menu_storage = page.locator(sel["menu_storage"]).locator("visible=true").first
            # force=True ignora overlays invisíveis que costumam bloquear cliques na iDRAC
            elemento_menu_storage.click(force=True)

            page.wait_for_selector(sel["titulo_storage"], state="visible", timeout=15000)

            # Aguarda o tráfego de rede acalmar, garantindo que as APIs de
            # storage terminaram de trazer os dados de discos/volumes
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass  # ignora se houver ping contínuo impedindo o networkidle

            page.wait_for_timeout(5000)
            tirar_print(page, output_dir, nome_servidor, "storage", timestamp)
            print("    -> Print de Storage salvo!")
        except Exception as e:
            print(f"    -> Storage falhou: {e}")

    # --- LCD ---
    if possui_lcd:
        if sel.get("menu_lcd") and sel.get("titulo_lcd"):
            try:
                print("    -> Solicitando aba LCD...")
                page.locator(sel["menu_lcd"]).locator("visible=true").first.click(force=True)
                page.wait_for_selector(sel["titulo_lcd"], state="visible", timeout=15000)
                page.wait_for_timeout(1500)
                tirar_print(page, output_dir, nome_servidor, "lcd", timestamp)
                print("    -> Print de LCD salvo!")
            except Exception as e:
                print(f"    -> LCD falhou: {e}")
        else:
            # Seletores de LCD do iDRAC9 ainda não confirmados (ver comentário em SELETORES)
            print("    -> LCD do iDRAC9 ainda não implementado (seletores pendentes), pulando.")


with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=[
            "--ignore-certificate-errors",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-background-timer-throttling",
            "--disable-blink-features=AutomationControlled",
        ],
    )

    for srv in servidores:
        nome_servidor = srv["nome"]  # Pega o nome vindo diretamente do .json
        host = srv["host"]
        geracao = srv.get("geracao", "idrac8")
        possui_storage = srv.get("possui_storage", True)
        possui_lcd = srv.get("possui_lcd", False)

        if geracao not in SELETORES:
            print(f"  -> Geração '{geracao}' não suportada para {nome_servidor}, pulando.")
            continue

        sel = SELETORES[geracao]
        output_dir = os.path.join(BASE_OUTPUT, nome_servidor)
        os.makedirs(output_dir, exist_ok=True)

        print(f"\nProcessando {nome_servidor} ({host}) [{geracao}]...")

        context = browser.new_context(
            ignore_https_errors=True, viewport={"width": 1600, "height": 1000}
        )

        try:
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            )
            page = context.new_page()

            login_url = obter_login_url(geracao, host)
            page.goto(login_url)

            page.locator(sel["user"]).wait_for(state="visible", timeout=40000)

            page.fill(sel["user"], srv["usuario"])
            page.wait_for_timeout(500)
            page.fill(sel["senha"], srv["senha"])
            page.wait_for_timeout(1000)

            print("    -> Submetendo login...")
            if geracao == "idrac7":
                page.evaluate("document.querySelector('#btnOK') ? document.querySelector('#btnOK').click() : null")
            elif geracao == "idrac8":
                # iDRAC8 (Express) às vezes não expõe um <button> real com o texto
                # "Submit" — pode ser <input type=submit>, role=button, ou um
                # elemento clicável genérico. Tentamos várias estratégias em
                # cascata antes de recorrer a um clique forçado via JS.
                submit_locators = [
                    sel["botao"],                 # "button:has-text('Submit')"
                    "input[type='submit']",
                    "role=button[name='Submit']",
                    "#btnOK",
                ]
                clicado = False
                for loc in submit_locators:
                    try:
                        elemento = page.locator(loc)
                        if elemento.count() > 0 and elemento.first.is_visible():
                            elemento.first.click(timeout=3000)
                            clicado = True
                            print(f"    -> Clique em Submit via seletor: {loc}")
                            break
                    except Exception:
                        continue

                if not clicado:
                    print("    -> Nenhum seletor padrão funcionou, tentando clique forçado via JS...")
                    resultado = page.evaluate(
                        """
                        () => {
                            const candidatos = [...document.querySelectorAll(
                                "button, input[type='submit'], input[type='button'], a"
                            )];
                            const btn = candidatos.find(el =>
                                (el.textContent || el.value || '').trim().toLowerCase().includes('submit')
                            );
                            if (btn) {
                                btn.click();
                                return true;
                            }
                            return false;
                        }
                        """
                    )
                    if not resultado:
                        raise Exception(
                            "Não foi possível localizar/clicar no botão Submit do iDRAC8."
                        )
                    print("    -> Clique em Submit via JS (fallback) executado.")
            else:
                page.click(sel["botao"])

            try:
                page.locator("text=Verifying credentials").wait_for(state="detached", timeout=30000)
            except Exception:
                pass

            try:
                page.wait_for_function("() => !window.location.href.includes('login.html')", timeout=30000)
            except Exception:
                pass

            if geracao == "idrac9":
                processar_idrac9(page, sel, output_dir, nome_servidor, timestamp, possui_storage, possui_lcd)
            else:
                processar_frameset(page, sel, output_dir, nome_servidor, timestamp, possui_storage, possui_lcd)
            print(f"  -> OK: {nome_servidor}")

        except Exception as e:
            debug_frames = os.path.join(output_dir, f"{timestamp}_{nome_servidor}_DEBUG_erro.png")
            page.screenshot(path=debug_frames, full_page=True)

            # Salva também o HTML da página no momento do erro, útil para
            # inspecionar qual seletor de botão/campo realmente existe no DOM.
            try:
                debug_html = os.path.join(output_dir, f"{timestamp}_{nome_servidor}_DEBUG_erro.html")
                with open(debug_html, "w", encoding="utf-8") as f_html:
                    f_html.write(page.content())
            except Exception:
                debug_html = None

            print(f"  -> Erro em {nome_servidor}: {e}. Print de debug salvo em: {debug_frames}")
            if debug_html:
                print(f"     HTML de debug salvo em: {debug_html}")

        finally:
            context.close()

    browser.close()

print("\nConcluído.")


#31/07/26 - iDRAC de geração 6 e 7 funcionando
#03/08/26 - iDRAC 8 funcionando, iDRAC 9 integrado neste mesmo script (função processar_idrac9)
#Pendências: 1) confirmar seletores de LCD do iDRAC9 (menu_lcd/titulo_lcd em SELETORES);
#            2) adicionar os servidores idrac9 no servidores2.json (basta "geracao": "idrac9");
#            3) checar se CONFIG_PATH ainda deve apontar pra pasta idrac678 ou se vale
#               unificar num só servidores.json agora que está tudo num script único.