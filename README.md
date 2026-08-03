# Automação de login iDRAC (6, 7, 8 e 9)

Script em Playwright que faz login automático em servidores Dell via iDRAC
(gerações 6, 7, 8 e 9), navega pelas seções (Dashboard, Storage e, quando
disponível, LCD) e salva screenshots de cada uma.

## Configuração

1. Copie o arquivo de exemplo e preencha com os dados reais dos seus servidores
   (esse arquivo final **não deve ser commitado** — já está no `.gitignore`):

   ```bash
   cp servidores.example.json servidores.json
   ```

2. Edite `servidores.json` com host, usuário, senha e geração (`idrac6`,
   `idrac7`, `idrac8` ou `idrac9`) de cada servidor.

3. (Opcional) Defina caminhos customizados via variáveis de ambiente:

   ```bash
   export IDRAC_CONFIG_PATH="/caminho/para/servidores.json"
   export IDRAC_OUTPUT_DIR="/caminho/para/salvar/prints"
   ```

   Se não definidas, o script usa `servidores.json` e `output/prints`
   relativos à pasta do projeto.

## Uso

```bash
pip install playwright
playwright install chromium
python idracamexer.py
```

## Estrutura

- `idracamexer.py` — script principal
- `servidores.example.json` — modelo de configuração (sem dados reais)
- `servidores.json` — sua configuração real (local, não versionada)

