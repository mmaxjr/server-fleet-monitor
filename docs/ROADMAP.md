# Roadmap

Proximos passos planejados para evoluir o Server Fleet Monitor sem mudar o
principio do MVP: leitura segura, sem executar acoes destrutivas nos servidores.

## Curto prazo

- Suporte a autenticacao por chave SSH e passphrase.
- Exportacao do snapshot atual em JSON e CSV.
- Alertas externos para eventos criticos, com Telegram ou Discord.

## Medio prazo

- Historico local opcional em SQLite.
- Painel de tendencias para CPU, memoria, disco e load average.
- Perfis de inventario para separar producao, homologacao e laboratorio.

## Seguranca

- Manter o inventario fora do Git e com permissao `0600`.
- Validar fingerprints dos hosts antes de adicionar ao `known_hosts`.
- Evitar comandos remotos que alterem estado dos servidores.
