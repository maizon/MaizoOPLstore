# MAIZO Store — hospedagem 100% gratuita no GitHub Pages

Esta loja funciona **sem servidor Python 24 horas, sem Railway, sem VPS,
sem Raspberry Pi, sem domínio pago e sem computador ligado**.

A cada commit no main, a Action `Publish free MAIZO Store` obtém os ELF
direto do GitHub Releases por HTTPS, exige hash SHA-256 e tamanho exatos,
gera catálogo estático `v1/catalog`, e implanta arquivos `v1/apps/*.elf`
no **GitHub Pages gratuito**. O publicador falha se um asset mudar no
GitHub sem atualização explícita do catálogo e do hash.

Endereço esperado após publicação:
https://maizon.github.io/MaizoOPLstore/

**Importante:** GitHub Pages utiliza HTTPS (TLS). O OPL original possui
apenas cliente HTTP; é necessário atualizar o cliente PS2 com TLS para
usar a loja *diretamente no console*. O frontend na web funciona sem
esse requisito. Esta implementação gratuita substitui o serviço Python
`server.py`, que fica apenas como opção para teste local.

Para atualizar um ELF, revise licenças e o asset oficial, atualize
`server.py` e **o hash embutido no cliente PS2** simultaneamente.
Nunca deixe o PS2 aceitar hashes recebidos do catálogo pela própria
conexão de rede.
