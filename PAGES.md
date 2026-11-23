# MAIZO Store — hospedagem gratuita, sem servidor próprio

O servidor `server.py` fica disponível apenas para testes locais.
O ambiente principal é um **repositório GitHub público e um CDN compartilhado
gratuito (jsDelivr)**.

Após cada atualização de `main`, GitHub Actions:
1. baixa arquivos .ELF oficiais do GitHub Releases sob HTTPS;
2. exige tamanho e SHA-256 fixados em `server.py`;
3. salva `site/v1/apps/<id>.elf` e `site/v1/catalog`;
4. faz commit dos assets no próprio repositório.

Acesso ao catálogo (não precisa ativar Pages):
https://cdn.jsdelivr.net/gh/maizon/MaizoOPLstore@main/site/v1/catalog

Interface pública:
https://cdn.jsdelivr.net/gh/maizon/MaizoOPLstore@main/site/index.html

Arquivos de aplicativos:
https://cdn.jsdelivr.net/gh/maizon/MaizoOPLstore@main/site/v1/apps/fceumm.elf

**Atenção:** jsDelivr é HTTPS; o PS2 precisa de cliente TLS no OPL.
O catálogo retornado não é uma fonte de confiança: cada ELF DEVE ser
validado pelo SHA-256 fixo dentro do MAIZO SUPREME. URLs `@main` podem
ser armazenadas em cache pelo CDN, portanto novos assets podem demorar
a propagar. Se um upstream atualizar seu `latest`, o build rejeitará
o novo binário até que o catálogo seja revisado.
