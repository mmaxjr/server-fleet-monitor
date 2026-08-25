# Server Fleet Monitor

<img width="1094" height="592" alt="image" src="https://github.com/user-attachments/assets/443f4074-d78c-41ea-aad4-0e76e352a7cf" />


Dashboard de terminal para acompanhar vários servidores Debian por SSH. A coleta usa `psutil` remotamente quando disponível e troca automaticamente para `/proc`, `df`, `systemctl` e `ss` quando o pacote não está instalado.

O MVP é somente leitura: ele não instala pacotes, reinicia serviços nem modifica os servidores.

## Recursos

- CPU, memória, swap, load average, uptime e discos.
- Interfaces e processos principais quando `psutil` estiver disponível.
- Serviços systemd com falha e portas em escuta pelo fallback.
- Estados separados para timeout, autenticação, host key e erro de coleta.
- Coleta concorrente sem congelar o dashboard.
- Filtro, atualização manual com `r` e detalhes por servidor.
- Última leitura válida preservada após falhas temporárias.

## Requisitos

- Host central Linux com Python 3.11 ou superior.
- Acesso SSH aos servidores Debian.
- `python3` nos servidores remotos.
- `psutil` remoto é opcional; no Debian pode ser instalado com `apt install python3-psutil`.

## Instalação no Debian central

```bash
sudo apt update
sudo apt install python3 python3-venv
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

## Inventário

Copie o exemplo e limite sua leitura ao proprietário:

```bash
cp inventory.example.yaml inventory.yaml
chmod 600 inventory.yaml
```

Edite `inventory.yaml`:

```yaml
settings:
  refresh_interval: 10
  ssh_timeout: 5
  max_concurrency: 10
  warning_threshold: 80
  critical_threshold: 90

servers:
  - name: web-01
    host: 192.168.1.20
    port: 22
    username: monitor
    password: "sua-senha"
```

As senhas não são exibidas no painel nem incluídas intencionalmente nos erros. Ainda assim, o inventário contém texto sensível e deve usar permissão `0600`.

## Cadastrar as chaves dos hosts

Por segurança, o programa rejeita hosts ausentes do `known_hosts`. Conecte uma vez manualmente e confirme a fingerprint:

```bash
ssh monitor@192.168.1.20
```

Em automações, `ssh-keyscan` pode coletar a chave, mas a fingerprint precisa ser conferida por um canal confiável antes de adicioná-la:

```bash
ssh-keyscan -H 192.168.1.20
```

## Execução

```bash
fleet-monitor --inventory inventory.yaml
```

Também é possível executar:

```bash
python3 -m fleet_monitor --inventory inventory.yaml
```

Atalhos:

- `r`: atualizar agora.
- `/`: focar o filtro.
- `Enter`: abrir os detalhes da linha.
- `q`: sair.

## Exportar um snapshot

Para coletar uma vez e exportar o resultado sem abrir o dashboard:

```bash
fleet-monitor --inventory inventory.yaml --export json
fleet-monitor --inventory inventory.yaml --export csv --export-path /tmp/snapshot.csv
```

Sem `--export-path`, o arquivo é gravado como `snapshot.json` ou `snapshot.csv` no diretório atual.

## Testes

```bash
pip install -e '.[test]'
pytest -v
python3 -m compileall fleet_monitor
```

Os testes usam executores falsos e não precisam de servidores SSH reais.

## Roadmap

O planejamento publico esta em [docs/ROADMAP.md](docs/ROADMAP.md). As primeiras
evolucoes previstas sao autenticacao por chave SSH, exportacao JSON/CSV e alertas
externos para estados criticos.

## Limitações do MVP

- O fallback depende de `python3`, `/proc` e ferramentas usuais do Debian.
- Senhas ficam no inventário; uma evolução recomendada é suporte a chaves SSH e cofre de segredos.
- Não há banco de dados, gráficos históricos ou alertas externos.
