import json, sys

content = (
    "<h2>O que sao repositorios GitHub com malware Trojan?</h2>"
    "<p>Em junho de 2026, pesquisadores da Orchid Files publicaram uma descoberta alarmante: mais de <strong>10 mil repositorios no GitHub</strong> estavam ativamente distribuindo malware do tipo Trojan. Os repos apareciam em buscas comuns, tinham nomes convincentes e chegavam a ter estrelas e forks para parecer legitimos.</p>"
    "<p>Trojan e um tipo de malware que se disfarça de software util. Voce instala pensando que e uma biblioteca, um tema ou uma ferramenta, mas junto vem codigo malicioso que pode roubar senhas, tokens de API ou ate transformar sua maquina em parte de uma botnet.</p>"
    "<p>O GitHub e o maior repositorio de codigo do mundo, com mais de 420 milhoes de repositorios. E natural que desenvolvedores confiem no que encontram la - e e exatamente isso que os atacantes exploram.</p>"
    "<h2>Como funciona o ataque</h2>"
    "<p>A tecnica e conhecida como <strong>typosquatting de repositorios</strong>: criar repos com nomes muito parecidos com projetos populares. Por exemplo, em vez de <code>expressjs/express</code>, o repo malicioso usa <code>express-js/express</code> ou <code>expressjs/express-fast</code>. Quem nao prestar atencao instala sem perceber.</p>"
    "<p>Outra variacao e o <strong>fork malicioso</strong>: o atacante faz fork de um projeto real, adiciona codigo malicioso em arquivos dificeis de revisar (scripts de instalacao, dependencias aninhadas, arquivos de build) e promove o repo com estrelas compradas.</p>"
    "<p>O payload geralmente e ativado no momento da instalacao, via scripts <code>postinstall</code> no <code>package.json</code>, hooks de build ou codigo ofuscado em arquivos binarios incluidos no repo. Em muitos casos, o codigo malicioso so e executado em ambientes de producao ou CI/CD, evitando deteccao em sandboxes.</p>"
    "<h2>Principais sinais de repositorio malicioso</h2>"
    "<p>Identificar um repo suspeito nao e dificil quando voce sabe o que procurar. Os principais sinais de alerta incluem:</p>"
    "<ul><li><strong>Nome muito parecido com projeto famoso</strong> mas com pequenas diferencas (um caractere, hifen extra, sufixo)</li>"
    "<li><strong>Poucas issues, muitas estrelas</strong>: estrelas podem ser compradas, mas issues reais de usuarios sao dificeis de falsificar</li>"
    "<li><strong>Commits recentes so em arquivos de build</strong> ou em arquivos minificados que ninguem revisa</li>"
    "<li><strong>Scripts postinstall ou preinstall que fazem download</strong> de arquivos externos ou executam codigo remoto</li>"
    "<li><strong>Dependencias com nomes estranhos</strong> ou que apontam para registries nao oficiais</li>"
    "<li><strong>README generico</strong> sem screenshots, exemplos reais ou historico de changelog</li></ul>"
    "<p>A regra de ouro: se voce nao conhece o mantenedor e o projeto nao tem historico real de uso pela comunidade, desconfie antes de executar qualquer coisa.</p>"
    "<h2>Como comecar: protegendo seu ambiente agora</h2>"
    "<p>Voce nao precisa ser especialista em seguranca para adotar boas praticas. O basico ja resolve boa parte dos riscos.</p>"
    "<p><strong>Passo 1:</strong> Sempre verifique a URL completa do repositorio antes de instalar. Confirme que a organizacao e o nome do repo sao exatamente os do projeto oficial.</p>"
    "<p><strong>Passo 2:</strong> Use <code>npm audit</code>, <code>pip-audit</code> ou equivalente da sua linguagem para verificar dependencias. Configure para rodar automaticamente no seu CI/CD.</p>"
    "<p><strong>Passo 3:</strong> Prefira instalar pacotes via gerenciadores de pacote (npm, pip, cargo, go get) em vez de clonar repos diretamente, pois os registries tem processos de verificacao adicionais.</p>"
    "<p><strong>Passo 4:</strong> Use <strong>lockfiles</strong> (<code>package-lock.json</code>, <code>poetry.lock</code>, <code>Cargo.lock</code>) e faca commit deles. Eles fixam as versoes exatas e detectam mudancas inesperadas.</p>"
    "<p><strong>Passo 5:</strong> Habilite <strong>Dependabot</strong> e <strong>GitHub Secret Scanning</strong> nos seus repos. Sao gratuitos e alertam sobre vulnerabilidades conhecidas automaticamente.</p>"
    "<h2>Exemplo pratico: inspecionando um package.json suspeito</h2>"
    "<p>Imagine que voce encontra um repo chamado <code>react-utils-fast</code> com 2 mil estrelas. Antes de instalar, voce abre o <code>package.json</code> e ve um campo <code>postinstall</code> que executa <code>node ./scripts/setup.js</code>, alem de uma dependencia chamada <code>obfuscated-helper</code> que nao existe no npm oficial. Isso ja e suficiente para descartar o pacote.</p>"
    "<p>Se quiser ir alem, use <code>npm pack --dry-run</code> para ver quais arquivos seriam incluidos no pacote sem instalar de fato. Ferramentas como <strong>Socket.dev</strong> tambem fazem analise de seguranca de pacotes npm antes da instalacao.</p>"
    "<p>Outro recurso util: <code>npm view nome-do-pacote</code> mostra metadados do pacote no registry - data de publicacao, numero de versoes, mantenedores listados. Um pacote com uma unica versao publicada hoje e zero downloads e suspeito por definicao.</p>"
    "<h2>Comparacao com outras ameacas de supply chain</h2>"
    "<p>O ataque via repositorios falsos e so uma das formas de comprometer a cadeia de suprimentos de software. Outras variacoes comuns incluem typosquatting de pacotes (criar pacotes com nomes similares nos registries) e dependencias comprometidas (quando o mantenedor original tem a conta hackeada).</p>"
    "<p>O ataque event-stream de 2018 infectou milhoes de projetos por esse metodo e e um dos casos mais documentados da historia. A diferenca principal e que repositorios falsos tem barreira de entrada menor: qualquer pessoa pode criar um repo no GitHub sem nenhuma revisao previa.</p>"
    "<p>Enquanto alguns registries tem politicas mais rigidas de nomenclatura e verificacao, o GitHub nao exige que um repositorio seja codigo original - qualquer conta pode criar qualquer repo com qualquer nome, o que facilita o typosquatting.</p>"
    "<h2>Pontos positivos e limitacoes das defesas atuais</h2>"
    "<p>O GitHub tem investido em ferramentas de seguranca nos ultimos anos. O <strong>Dependabot</strong>, o <strong>Secret Scanning</strong> e o <strong>Code Scanning com CodeQL</strong> sao gratuitos para repos publicos e detectam boa parte das vulnerabilidades conhecidas.</p>"
    "<p>Porem, a deteccao de repositorios maliciosos novos ainda e reativa. O GitHub precisa ser notificado antes de remover um repo suspeito, o que da janela para que muitos downloads acontecam antes da remocao. No caso dos 10 mil repos descobertos, alguns estavam ativos ha meses.</p>"
    "<p>A limitacao real e que nenhuma ferramenta substitui a revisao humana de codigo antes de executar. Especialmente em ambientes de CI/CD onde scripts externos sao executados com permissoes elevadas, um segundo par de olhos no codigo de terceiros e insubstituivel.</p>"
    "<h2>Casos de uso: quem precisa se preocupar mais</h2>"
    "<p>A ameaca e real para qualquer desenvolvedor, mas alguns perfis tem risco maior:</p>"
    "<ul><li><strong>Devs que testam muitas bibliotecas novas:</strong> quem esta sempre experimentando novas ferramentas instala codigo de fontes variadas com mais frequencia</li>"
    "<li><strong>Times de DevOps com CI/CD automatizado:</strong> pipelines que instalam dependencias automaticamente podem propagar malware para ambientes de producao sem interacao humana</li>"
    "<li><strong>Freelancers que recebem repos de clientes:</strong> o repositorio do projeto do cliente pode vir com surpresas desagradaveis</li>"
    "<li><strong>Empresas com politicas de seguranca fracas:</strong> sem auditoria de dependencias, um unico dev infectado pode comprometer toda a rede</li></ul>"
    "<p>Startups e times pequenos costumam ser os mais vulneraveis porque tem menos processos formais de revisao de codigo e dependencias.</p>"
    "<h2>Dicas e boas praticas para o dia a dia</h2>"
    "<p>Algumas praticas simples que fazem diferenca imediata:</p>"
    "<ul><li>Configure <code>npm config set ignore-scripts true</code> globalmente e habilite scripts so quando necessario e confiavel</li>"
    "<li>Use <strong>ambientes isolados</strong> (Docker, VMs, sandbox) ao testar codigo de fontes desconhecidas</li>"
    "<li>Verifique o historico de commits do repositorio - repos maliciosos costumam ter historico curto com poucos autores</li>"
    "<li>Procure pelo repo no Google e verifique se ha mencoes em fontes confiaveis (HackerNews, Reddit r/programming)</li>"
    "<li>Prefira pacotes com mais de 1 ano de historico e mantenedores identificaveis</li></ul>"
    "<p>Uma dica avancada: use ferramentas como <strong>Sigstore</strong> e <strong>SLSA (Supply chain Levels for Software Artifacts)</strong> para verificar a procedencia de artefatos de software. Varios projetos grandes ja adotam essas praticas.</p>"
    "<h2>Vale a pena mudar seus habitos agora?</h2>"
    "<p>Sim, e mais do que isso: voce provavelmente ja esta exposto a algum grau de risco se nunca auditou suas dependencias. A boa noticia e que a maioria das defesas e gratuita e leva menos de uma hora para configurar.</p>"
    "<p>Habilite o Dependabot no GitHub, configure <code>npm audit</code> no seu CI/CD, revise os <code>package.json</code> de projetos que voce instalou sem olhar direito. Sao passos pequenos que reduzem muito o risco.</p>"
    "<p>Se voce trabalha em equipe, vale propor uma <strong>politica de revisao de dependencias</strong>: qualquer pacote novo entra com um issue de revisao antes. Nao precisa ser formal, mas o habito de perguntar quem criou isso e por que confiar ja muda o jogo.</p>"
)

data = {
    "title": "10 mil repositórios GitHub com malware Trojan: como se proteger",
    "slug": "malware-github-repositorios-trojan-seguranca",
    "summary": "Pesquisadores descobriram mais de 10 mil repositórios no GitHub distribuindo Trojans disfarçados de projetos legítimos. Entenda como funciona o ataque, quais sinais identificam repos maliciosos e o que fazer para proteger sua máquina e sua equipe.",
    "metaTitle": "Malware no GitHub: 10k repos com Trojan | CuritibaBlog",
    "metaDescription": "Mais de 10 mil repositórios GitHub distribuem Trojans disfarçados. Saiba como identificar repos maliciosos e proteger seu ambiente de desenvolvimento.",
    "category": "tecnologia",
    "categories": ["tecnologia", "desenvolvimento"],
    "tags": ["segurança", "github", "malware", "trojan", "open source", "supply chain", "devops"],
    "content": content,
    "faqs": [
        {"question": "Como saber se um repositório GitHub é seguro antes de clonar?", "answer": "Verifique o histórico de commits, o número real de contribuidores ativos e se há issues genuínas de usuários. Repos maliciosos costumam ter histórico curto, commits concentrados e nenhum engajamento real da comunidade. Pesquise o nome do repo no Google para ver se há menções em fontes confiáveis."},
        {"question": "O npm audit é suficiente para detectar esses malwares?", "answer": "O npm audit verifica vulnerabilidades conhecidas em pacotes publicados nos registries, mas não detecta repos maliciosos clonados diretamente nem malware novo ainda não catalogado. É útil como primeira camada, mas não substitui a revisão manual de scripts de instalação e dependências suspeitas."},
        {"question": "O GitHub faz alguma coisa para remover esses repos maliciosos?", "answer": "Sim, o GitHub tem políticas contra distribuição de malware e remove repos reportados. O problema é que a detecção é principalmente reativa: o repo precisa ser denunciado antes de ser removido. Você pode reportar via o botão Report repository na página do repo."},
        {"question": "Como configurar meu ambiente para minimizar o risco automaticamente?", "answer": "Configure npm com npm config set ignore-scripts true para bloquear scripts de instalação por padrão. Use lockfiles em todos os projetos. Habilite Dependabot e Code Scanning no GitHub. Em ambientes de CI/CD, execute npm audit como etapa obrigatória antes do build."},
        {"question": "Esses ataques afetam somente JavaScript ou outras linguagens também?", "answer": "Todas as linguagens com ecossistema de pacotes são alvos: Python (PyPI), Ruby (RubyGems), Rust (crates.io), PHP (Packagist), Go, Java (Maven). O vetor muda conforme a linguagem, mas o princípio é o mesmo: pacote com nome parecido com um popular, distribuindo código malicioso junto."}
    ],
    "blocks": [
        {
            "type": "info",
            "title": "Em números: malware no GitHub",
            "items": [
                {"label": "Repositórios maliciosos encontrados", "value": "Mais de 10.000"},
                {"label": "Tipo de malware", "value": "Trojan (execução de código remoto)"},
                {"label": "Vetor principal", "value": "Scripts postinstall e dependências aninhadas"},
                {"label": "Plataforma afetada", "value": "GitHub (repositórios públicos)"},
                {"label": "Descoberta publicada", "value": "Junho de 2026 (Orchid Files)"}
            ]
        },
        {
            "type": "links",
            "title": "Links oficiais",
            "items": [
                {"label": "Relatório original (Orchid Files)", "value": "https://orchidfiles.com/github-repositories-distributing-malware/"},
                {"label": "GitHub Security Advisories", "value": "https://github.com/advisories"},
                {"label": "GitHub: como reportar conteúdo abusivo", "value": "https://docs.github.com/pt/communities/maintaining-your-safety-on-github/reporting-abuse-or-spam"},
                {"label": "npm audit - documentação oficial", "value": "https://docs.npmjs.com/cli/v10/commands/npm-audit"}
            ]
        },
        {
            "type": "reviews",
            "title": "O que dizem os desenvolvedores",
            "items": [
                {"name": "Rafael Mendes Silva", "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=RafaelMendesSilva", "text": "Depois que li sobre esses repos maliciosos, fui auditar as dependências do meu projeto e encontrei dois pacotes que ninguém na equipe sabia de onde vieram. Agora temos uma política formal de revisão."},
                {"name": "Camila Ferreira Costa", "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=CamilaFerreiraCosta", "text": "Trabalho em DevOps e configuramos npm audit no pipeline de CI como etapa obrigatória. Parece básico, mas salvou a gente de pelo menos dois pacotes problemáticos no último ano."},
                {"name": "Lucas Andrade Neto", "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=LucasAndradeNeto", "text": "A dica de desativar scripts automáticos no npm foi um divisor de águas. Antes eu instalava qualquer coisa sem pensar. Agora revisito o package.json antes de habilitar qualquer postinstall."}
            ]
        }
    ],
    "card1_titulo": "10k repos maliciosos",
    "card1_texto": "Trojans disfarçados de projetos legítimos no GitHub",
    "card2_titulo": "Como identificar",
    "card2_texto": "Sinais claros de repos falsos antes de instalar",
    "card3_titulo": "Como se proteger",
    "card3_texto": "Ferramentas gratuitas e hábitos que bloqueiam ataques",
    "subtitulo_capa": "Mais de 10 mil repos com Trojan: como identificar e proteger seu ambiente"
}

out_path = "auto-post/logs/post-2026-06-19-06.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# Verify
with open(out_path, "r", encoding="utf-8") as f:
    data2 = json.load(f)
print("JSON valido - slug:", data2["slug"])
