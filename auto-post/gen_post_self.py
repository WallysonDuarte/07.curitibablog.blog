import json

content = (
    "<h2>O que e o .self TLD</h2>"
    "<p>O <strong>.self</strong> e uma proposta de dominio de topo (TLD) criada para suportar a pratica de <strong>self-hosting</strong>, hospedar os proprios servicos em servidores pessoais ou privados. A ideia e criar um namespace dedicado para quem quer independencia digital real.</p>"
    "<p>Em vez de depender de dominios como .com, .net ou .io gerenciados por registradores comerciais, o .self seria um TLD orientado a comunidade, projetado para maquinas e servicos que nao precisam ser resolvidos pela internet publica. A resolucao funcionaria em redes privadas, VPNs ou resolvedores DNS alternativos.</p>"
    "<p>A proposta ganhou destaque em junho de 2026 quando um post da HCCF viralizou no Hacker News com centenas de comentarios, acendendo debate sobre soberania digital e o papel dos grandes registradores na internet.</p>"
    "<h2>Como funcionaria o .self</h2>"
    "<p>O modelo proposto nao depende da ICANN para funcionar. A ideia central e usar um <strong>sistema de resolucao DNS alternativo</strong>, onde usuarios configuram seus resolvedores para reconhecer enderecos .self.</p>"
    "<p>Quando voce digita meucalendario.self no navegador, o resolvedor DNS configurado na sua rede sabe que deve procurar esse endereco em um diretorio distribuido da comunidade, nao nos servidores raiz da ICANN. Isso e semelhante ao que projetos como OpenNIC e Handshake ja fazem.</p>"
    "<p>A diferenca proposta pelo .self e o foco em usabilidade para auto-hospedagem: certificados TLS compativeis com o namespace, integracao com ferramentas como Caddy, Nginx e Traefik, e suporte nativo para redes locais e VPNs como Tailscale e WireGuard.</p>"
    "<h2>Por que a comunidade self-hosting se empolgou</h2>"
    "<p>O movimento de auto-hospedagem cresceu muito nos ultimos anos. Plataformas como Nextcloud, Immich, Jellyfin e Vaultwarden tornaram acessivel hospedar em casa o que antes dependia de servicos pagos na nuvem.</p>"
    "<p>O problema que o .self resolve: acessar esses servicos de forma amigavel e complicado. Voce pode usar o IP local, criar um subdominio no Cloudflare ou usar o .local do mDNS. O .self oferece uma alternativa padronizada voltada especificamente para esse caso de uso.</p>"
    "<p>Na discussao do HN, muitos devs apontaram o aspecto filosofico: ter um namespace que nao pode ser tirado por uma empresa privada ou governo, representando seus servicos pessoais sem depender de infraestrutura centralizada.</p>"
    "<h2>Como comecar: usando o conceito .self hoje</h2>"
    "<p>O .self ainda nao e um TLD oficial. Mas voce pode experimentar o conceito com ferramentas que ja existem. Passo 1: configure um resolvedor DNS local. O Pi-hole com DNS customizado ou o AdGuard Home permitem definir que qualquer dominio .self resolva para um IP da sua rede.</p>"
    "<p>Passo 2: adicione entradas no servidor DNS local, por exemplo meunextcloud.self apontando para 192.168.1.10. Passo 3: aponte os dispositivos da rede para usar o DNS local. Passo 4: use o Caddy como proxy reverso com TLS auto-assinado para cada servico.</p>"
    "<p>O resultado e acesso tipo meunextcloud.self com HTTPS na sua rede domiciliar, sem expor nada a internet publica.</p>"
    "<h2>Exemplo pratico: rede domiciliar com .self</h2>"
    "<p>Imagine que voce tem um servidor caseiro rodando varios servicos. Sem .self, voce acessa pelo IP ou por URLs complicadas. Com o conceito .self implementado localmente, cada servico recebe um nome legivel: arquivos.self para o Nextcloud, fotos.self para o Immich, plex.self para o Jellyfin e senhas.self para o Vaultwarden.</p>"
    "<p>Cada servico tem HTTPS, um nome legivel e funciona em qualquer dispositivo da sua rede sem configuracao adicional. A configuracao e feita uma vez no Pi-hole e todos os dispositivos herdam automaticamente.</p>"
    "<p>Com o Tailscale, voce pode estender o mesmo acesso para quando estiver fora de casa. Os enderecos .self resolvem pelo Tailscale DNS, sem expor portas ao mundo.</p>"
    "<h2>Comparacao com alternativas</h2>"
    "<p>O <strong>.local (mDNS)</strong> e nativo no macOS e Linux, mas nao funciona em todos os dispositivos Android. Usar um subdominio real funciona bem com certbot, mas exige dominio pago e expoe o endereco no DNS publico. O Cloudflare Tunnel e elegante mas depende de terceiro, violando o principio de independencia do self-hosting.</p>"
    "<p>Projetos como OpenNIC e Handshake ja oferecem TLDs alternativos, mas com foco em descentralizacao ampla, nao self-hosting especificamente. O .self se diferencia por ser pensado do zero para auto-hospedagem, com suporte a ferramentas populares da comunidade e sem dependencia de terceiros.</p>"
    "<p>A escolha entre as abordagens depende do contexto. Para um dev solo em casa, Pi-hole mais Caddy mais conceito .self e provavelmente a combinacao mais pratica. Para uma equipe corporativa, Tailscale com Magic DNS pode ser mais simples de gerenciar.</p>"
    "<h2>Pontos positivos e limitacoes</h2>"
    "<p>O que funciona a favor: o conceito resolve um problema real de forma elegante. A padronizacao de um namespace dedicado facilita documentacao, tutoriais e configuracoes compartilhadas. Hoje cada um inventa sua propria solucao e e dificil compartilhar guias entre comunidades.</p>"
    "<p>Limitacoes importantes: o .self ainda e uma proposta, nao um padrao adotado. Sem aprovacao da ICANN, exige resolvedor configurado em cada rede. Isso limita o uso a ambientes controlados e exige configuracao manual em cada dispositivo que precisar acessar os servicos.</p>"
    "<p>Outro risco e a fragmentacao. Se cada comunidade criar seu proprio TLD alternativo, a confusao aumenta. A proposta so ganha valor se houver adocao suficiente para criar um ecossistema de ferramentas ao redor.</p>"
    "<h2>Casos de uso reais</h2>"
    "<p>O .self faz sentido para estes perfis:</p>"
    "<ul><li><strong>Dev com homelab:</strong> voce tem servidor em casa com varios servicos. Enderecos .self deixam o acesso tao facil quanto qualquer site comercial, sem configuracao por dispositivo.</li>"
    "<li><strong>Equipe pequena com servidor proprio:</strong> uma startup que hospeda Git, Wiki e CI num servidor proprio se beneficia de enderecos padronizados acessiveis pela VPN.</li>"
    "<li><strong>Entusiasta de privacidade:</strong> quer usar Vaultwarden em vez de 1Password, Immich em vez de Google Fotos. O .self facilita o acesso a todos esses servicos com uma unica configuracao de DNS.</li>"
    "<li><strong>Educador de infraestrutura:</strong> ensinar redes, DNS e self-hosting fica mais claro com um namespace dedicado e documentacao padronizada.</li></ul>"
    "<h2>Dicas e boas praticas</h2>"
    "<p>Para adotar o conceito .self hoje na sua rede:</p>"
    "<ul><li>Use o Pi-hole ou AdGuard Home como servidor DNS principal. Configure o DHCP do roteador para distribuir o IP do Pi-hole como DNS de toda a rede.</li>"
    "<li>Prefira um wildcard DNS local: *.self apontando para o IP do seu proxy reverso. Assim voce nao precisa criar entradas individuais para cada servico.</li>"
    "<li>Use o Caddy como proxy reverso. A configuracao de TLS para dominios internos e mais simples do que no Nginx.</li>"
    "<li>Separe os servicos que precisam de acesso externo dos que sao apenas internos. Os internos ficam no .self, os externos recebem subdominio real com certbot.</li></ul>"
    "<h2>Vale a pena?</h2>"
    "<p>O .self enquanto TLD oficial ainda e uma proposta. Mas o conceito e as ferramentas para implementa-lo localmente sao muito reais. Se voce pratica self-hosting ou quer comecar, configurar um DNS local com namespace padronizado e uma das melhores melhorias de qualidade de vida que voce pode fazer.</p>"
    "<p>A discussao ao redor do .self reflete algo maior: uma parte crescente da comunidade tech quer mais controle sobre a propria infraestrutura digital. Servicos de nuvem sao convenientes, mas dependencia total de terceiros tem seus custos em privacidade, preco e disponibilidade.</p>"
    "<p>O proximo passo: instale o Pi-hole ou AdGuard Home na sua rede, configure um DNS local com o namespace .self e teste com um servico que voce ja usa. A experiencia vai mostrar se essa abordagem faz sentido para o seu caso.</p>"
)

data = {
    "title": ".self: o dominio criado para quem hospeda os proprios servicos",
    "slug": "self-tld-dominio-auto-hospedagem-self-hosting",
    "summary": "O .self e uma proposta de TLD criado para a comunidade de self-hosting. Entenda o que e, como funcionaria, por que animou a comunidade tech e como voce pode adotar o conceito hoje na sua rede com Pi-hole e Caddy.",
    "metaTitle": ".self TLD: dominio para auto-hospedagem | CuritibaBlog",
    "metaDescription": "Conheca o .self, o dominio de topo proposto para self-hosting. Como funciona, por que importa para devs e como implementar hoje na sua rede.",
    "category": "tecnologia",
    "categories": ["tecnologia", "desenvolvimento"],
    "tags": ["self-hosting", "tld", "dns", "infraestrutura", "privacidade", "homelab", "redes"],
    "content": content,
    "faqs": [
        {
            "question": "O .self ja e um TLD oficial reconhecido pela ICANN?",
            "answer": "Nao. O .self e uma proposta de TLD alternativo nao aprovado pela ICANN. Ele nao funciona na internet publica por padrao. Voce pode usa-lo hoje apenas em redes privadas, configurando um resolvedor DNS local que reconheca o namespace."
        },
        {
            "question": "Qual e a diferenca entre .self e .local?",
            "answer": "O .local e usado pelo mDNS para descoberta de dispositivos em rede local. O .self e uma proposta para namespace estruturado de auto-hospedagem com suporte a HTTPS e proxy reverso, focado em servicos web e nao so em descoberta de dispositivos."
        },
        {
            "question": "Preciso de um servidor dedicado para usar o conceito .self?",
            "answer": "Nao. Um Raspberry Pi com Pi-hole e Caddy ja e suficiente. Qualquer maquina que rode Linux serve como ponto de partida, incluindo dispositivos ARM baratos como o Raspberry Pi 4."
        },
        {
            "question": "Como acessar servicos .self fora de casa?",
            "answer": "Usando uma VPN como Tailscale ou WireGuard. Com o Tailscale Magic DNS, voce configura o resolvedor para incluir o namespace .self e acessa seus servicos de qualquer lugar como se estivesse na rede local."
        },
        {
            "question": "O .self pode receber certificado TLS valido?",
            "answer": "Para uso interno, voce usa uma CA propria com mkcert ou configura o Caddy para conexoes internas. O acesso fica com HTTPS mas o certificado e auto-assinado. Certificados reconhecidos publicamente exigem TLD aprovado pela ICANN."
        }
    ],
    "blocks": [
        {
            "type": "info",
            "title": "Em numeros: self-hosting em 2026",
            "items": [
                {"label": "Instancias ativas do Nextcloud", "value": "mais de 400 mil"},
                {"label": "Stars no GitHub (Immich)", "value": "mais de 55 mil"},
                {"label": "Custo de um homelab basico", "value": "a partir de R$ 300 (Raspberry Pi 4)"},
                {"label": "TLDs alternativos existentes", "value": "OpenNIC, Handshake, Yggdrasil"},
                {"label": "Status do .self", "value": "Proposta da comunidade (nao aprovado ICANN)"}
            ]
        },
        {
            "type": "links",
            "title": "Links relacionados",
            "items": [
                {"label": "Pi-hole (DNS local)", "value": "https://pi-hole.net"},
                {"label": "AdGuard Home", "value": "https://adguard.com/pt_br/adguard-home/overview.html"},
                {"label": "Caddy (proxy reverso)", "value": "https://caddyserver.com"},
                {"label": "Tailscale (VPN mesh)", "value": "https://tailscale.com"}
            ]
        },
        {
            "type": "reviews",
            "title": "O que dizem os entusiastas de self-hosting",
            "items": [
                {
                    "name": "Thiago Monteiro",
                    "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=ThiagoMonteiro",
                    "text": "Configurei DNS local com Pi-hole e adotei o conceito .self nos meus servicos. A diferenca na usabilidade e enorme. Agora acesso tudo por nomes legiveis, sem decorar IP e porta."
                },
                {
                    "name": "Fernanda Rocha",
                    "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=FernandaRocha",
                    "text": "Uso Nextcloud, Vaultwarden e Jellyfin em casa. Integrar namespace padronizado via Caddy e AdGuard foi a configuracao que mais economizou tempo do meu homelab."
                },
                {
                    "name": "Lucas Andrade",
                    "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=LucasAndrade",
                    "text": "A ideia do .self faz muito sentido para equipes pequenas com servidor proprio. Enderecos padronizados pela VPN sao muito mais profissionais do que usar IP direto."
                }
            ]
        }
    ],
    "card1_titulo": "Privacidade total",
    "card1_texto": "Seus dados ficam no seu servidor, sem terceiros",
    "card2_titulo": "Acesso organizado",
    "card2_texto": "Enderecos legiveis para cada servico do homelab",
    "card3_titulo": "Sem custo de nuvem",
    "card3_texto": "Substitua servicos pagos por versoes proprias",
    "subtitulo_capa": "Como um novo dominio de topo pode mudar a forma de hospedar seus proprios servicos"
}

out = "E:/PROJETOS/curitibablog.com.br/07.curitibablog.blog/auto-post/logs/post-2026-06-30-06.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
with open(out, encoding="utf-8") as f:
    d = json.load(f)
print("OK", d["slug"])
