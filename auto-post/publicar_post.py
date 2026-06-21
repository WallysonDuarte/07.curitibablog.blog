"""
publicar_post.py — Recebe JSON do post, gera capa, faz upload, insere MongoDB, rebuilda blogs.
Uso: python publicar_post.py <caminho_para_json>

O JSON deve ter todos os campos do post (title, slug, content, faqs, blocks, etc.)
Gerado pelo agente Claude Code a partir do prompt_post.md.
"""
import os, sys, json, uuid, re, datetime, unicodedata
from pathlib import Path

import requests
import boto3
from botocore.client import Config
import pymongo

THIS_DIR = Path(__file__).parent
LOGS_DIR = THIS_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

MONGO_USER   = "curitibasoftware"
MONGO_PASS   = "Curitiba@2025+++"
MONGO_DB     = "curitibasoftware"
MONGO_COL    = "blogposts"

IDRIVE_URL    = "https://s3.us-east-1.idrivee2.com"
IDRIVE_KEY    = "W5HR4oX6jKc53WENnNUe"
IDRIVE_SECRET = "vRDJCcHHBk7vYLbQ05iEvvnWVD4zw3afMXsOQX0X"
IDRIVE_BUCKET = "curitibasoftware-blog"
PUBLIC_BASE   = "https://api.curitibasoftware.com.br/api/blog/image"

VPS_HOST = "31.97.252.45"
VPS_PORT = 2222
VPS_USER = "ubuntu"
SSH_KEY  = str(Path.home() / ".ssh" / "id_server_nopass")

BLOGS = ["curitibablog", "blogdudu", "devlevelup", "dozeroaojunior", "levelupdev"]

# IndexNow — chave de verificacao (arquivo <chave>.txt em cada blog)
INDEXNOW_KEY = "6363e67916a04a8586c27e7c3aea3a8a"
BLOG_DOMAIN = {
    "curitibablog":   "curitibablog.com.br",
    "blogdudu":       "blogdudu.com.br",
    "devlevelup":     "devlevelup.com.br",
    "dozeroaojunior": "dozeroaojunior.com.br",
    "levelupdev":     "levelupdev.com.br",
}

# Paths locais (source Astro) e remotos (deploy no VPS)
BLOG_LOCAL = {
    "curitibablog":   "E:/PROJETOS/curitibablog.com.br/07.curitibablog.blog",
    "blogdudu":       "E:/PROJETOS/blogdudu.com.br/07.blogdudu.blog",
    "devlevelup":     "E:/PROJETOS/devlevelup.com.br/07.devlevelup.blog",
    "dozeroaojunior": "E:/PROJETOS/dozeroaojunior.com.br/07.dozeroaojunior.blog",
    "levelupdev":     "E:/PROJETOS/levelupdev.com.br/07.levelupdev.blog",
}
BLOG_REMOTE = {
    "curitibablog":   "/opt/curitibablog",
    "blogdudu":       "/opt/blogdudu",
    "devlevelup":     "/opt/devlevelup",
    "dozeroaojunior": "/opt/dozeroaojunior",
    "levelupdev":     "/opt/levelupdev",
}

CHARS_PROIBIDOS = ["—", "–", "“", "”", "‘", "’", "…"]

# Correcoes de acentuacao PT-BR — aplicadas antes de publicar
# Formato: (regex_sem_acento, forma_correta)
_ACENTO_FIXES = [
    # Palavras comuns sem acento
    (r'\bvoce\b', 'você'), (r'\bvoces\b', 'vocês'),
    (r'\btambem\b', 'também'),
    (r'\bentao\b', 'então'),
    (r'\bnao\b', 'não'),
    (r'\bja\b', 'já'),
    (r'\bapos\b', 'após'),
    (r'\bate\b', 'até'),
    (r'\bso\b', 'só'),
    (r'\bporem\b', 'porém'),
    (r'\balguem\b', 'alguém'),
    (r'\bninguem\b', 'ninguém'),
    # Terminações -ção/-ções
    (r'\bacao\b', 'ação'), (r'\bacoes\b', 'ações'),
    (r'\bintegracao\b', 'integração'), (r'\bintegracoes\b', 'integrações'),
    (r'\bautomacao\b', 'automação'), (r'\bautomacoes\b', 'automações'),
    (r'\bexecucao\b', 'execução'), (r'\bexecucoes\b', 'execuções'),
    (r'\bconfiguracao\b', 'configuração'), (r'\bconfiguracoes\b', 'configurações'),
    (r'\bcriacao\b', 'criação'), (r'\bcriacoes\b', 'criações'),
    (r'\bcomunicacao\b', 'comunicação'), (r'\bcomunicacoes\b', 'comunicações'),
    (r'\bconexao\b', 'conexão'), (r'\bconexoes\b', 'conexões'),
    (r'\bfuncao\b', 'função'), (r'\bfuncoes\b', 'funções'),
    (r'\boperacao\b', 'operação'), (r'\boperacoes\b', 'operações'),
    (r'\binformacao\b', 'informação'), (r'\binformacoes\b', 'informações'),
    (r'\bvalidacao\b', 'validação'), (r'\bvalidacoes\b', 'validações'),
    (r'\bimplementacao\b', 'implementação'), (r'\bimplementacoes\b', 'implementações'),
    (r'\bdocumentacao\b', 'documentação'),
    (r'\bapresentacao\b', 'apresentação'), (r'\bapresentacoes\b', 'apresentações'),
    (r'\binstancio\b', 'instância'), (r'\binstancias\b', 'instâncias'), (r'\binstancia\b', 'instância'),
    (r'\brelacao\b', 'relação'), (r'\brelacoes\b', 'relações'),
    (r'\bsolucao\b', 'solução'), (r'\bsolucoes\b', 'soluções'),
    (r'\bgestao\b', 'gestão'), (r'\bgestoes\b', 'gestões'),
    (r'\binsercao\b', 'inserção'), (r'\binserções\b', 'inserções'),
    (r'\bexcecao\b', 'exceção'), (r'\bexcecoes\b', 'exceções'),
    (r'\bdistribuicao\b', 'distribuição'), (r'\bdistribuicoes\b', 'distribuições'),
    (r'\bintroducao\b', 'introdução'),
    (r'\bevolucao\b', 'evolução'),
    (r'\bmigracao\b', 'migração'), (r'\bmigracoes\b', 'migrações'),
    (r'\bavaliacao\b', 'avaliação'), (r'\bavaliacoes\b', 'avaliações'),
    (r'\bextensao\b', 'extensão'), (r'\bextensoes\b', 'extensões'),
    (r'\bversao\b', 'versão'), (r'\bversoes\b', 'versões'),
    (r'\bpermissao\b', 'permissão'), (r'\bpermissoes\b', 'permissões'),
    (r'\bdefinicao\b', 'definição'), (r'\bdefinicoes\b', 'definições'),
    (r'\batencao\b', 'atenção'),
    (r'\borganizacao\b', 'organização'), (r'\borganizacoes\b', 'organizações'),
    (r'\bnotificacao\b', 'notificação'), (r'\bnotificacoes\b', 'notificações'),
    (r'\brepresentacao\b', 'representação'),
    (r'\breplicacao\b', 'replicação'),
    (r'\btransacao\b', 'transação'), (r'\btransacoes\b', 'transações'),
    (r'\bsegurança\b', 'segurança'), (r'\bautorizacao\b', 'autorização'),
    (r'\bautenticacao\b', 'autenticação'),
    (r'\bserializacao\b', 'serialização'),
    (r'\bcompilacao\b', 'compilação'),
    (r'\bverificacao\b', 'verificação'), (r'\bverificacoes\b', 'verificações'),
    (r'\bprocessamento\b', 'processamento'),  # sem acento mesmo
    (r'\blancamento\b', 'lançamento'), (r'\blancamentos\b', 'lançamentos'),
    (r'\blancou\b', 'lançou'), (r'\blanca\b', 'lança'), (r'\blancam\b', 'lançam'),
    (r'\bmanutencao\b', 'manutenção'), (r'\bmanutencoes\b', 'manutenções'),
    (r'\bcompensacao\b', 'compensação'), (r'\bcompensacoes\b', 'compensações'),
    (r'\borquestracao\b', 'orquestração'),
    (r'\binspecao\b', 'inspeção'), (r'\binspecoes\b', 'inspeções'),
    (r'\bcorrecao\b', 'correção'), (r'\bcorrecoes\b', 'correções'),
    (r'\bprotecao\b', 'proteção'), (r'\bprotecoes\b', 'proteções'),
    (r'\brestricao\b', 'restrição'), (r'\brestricoes\b', 'restrições'),
    (r'\bexibicao\b', 'exibição'), (r'\bexibicoes\b', 'exibições'),
    (r'\bgravacao\b', 'gravação'), (r'\bgravacoes\b', 'gravações'),
    (r'\bimportacao\b', 'importação'), (r'\bexportacao\b', 'exportação'),
    (r'\bextracao\b', 'extração'), (r'\bextracoes\b', 'extrações'),
    (r'\bconversao\b', 'conversão'), (r'\bconversoes\b', 'conversões'),
    (r'\bpublicacao\b', 'publicação'), (r'\bpublicacoes\b', 'publicações'),
    (r'\bnavegacao\b', 'navegação'),
    (r'\binstrucao\b', 'instrução'), (r'\binstrucoes\b', 'instruções'),
    (r'\bproducao\b', 'produção'), (r'\bproducoes\b', 'produções'),
    (r'\brepresentar\b', 'representar'),  # ok sem acento
    (r'\breducao\b', 'redução'), (r'\breducoes\b', 'reduções'),
    (r'\bcalculacao\b', 'cálculo'),
    (r'\balteracao\b', 'alteração'), (r'\balteracoes\b', 'alterações'),
    (r'\bpaginacao\b', 'paginação'),
    (r'\baplicacao\b', 'aplicação'), (r'\baplicacoes\b', 'aplicações'),
    (r'\bcontribuicao\b', 'contribuição'), (r'\bcontribuicoes\b', 'contribuições'),
    (r'\bpolicidade\b', 'publicidade'),
    (r'\bgravitacao\b', 'gravitação'),
    (r'\blocalizacao\b', 'localização'),
    (r'\botimizacao\b', 'otimização'),
    (r'\btensao\b', 'tensão'),
    (r'\bterminacao\b', 'terminação'),
    (r'\bdistincao\b', 'distinção'),
    (r'\bcomposicao\b', 'composição'),
    (r'\bposicao\b', 'posição'), (r'\bposicoes\b', 'posições'),
    (r'\batribuicao\b', 'atribuição'),
    # Terminações -ão (outros)
    (r'\bpadrao\b', 'padrão'), (r'\bpadroes\b', 'padrões'),
    (r'\borgao\b', 'órgão'), (r'\borgaos\b', 'órgãos'),
    # -ência/-ências
    (r'\bexperiencia\b', 'experiência'), (r'\bexperiencias\b', 'experiências'),
    (r'\bciencia\b', 'ciência'), (r'\bciencias\b', 'ciências'),
    (r'\bfrequencia\b', 'frequência'), (r'\bfrequencias\b', 'frequências'),
    (r'\baudiencia\b', 'audiência'), (r'\baudiencias\b', 'audiências'),
    (r'\bgerencia\b', 'gerência'), (r'\bgerencias\b', 'gerências'),
    (r'\bsequencia\b', 'sequência'), (r'\bsequencias\b', 'sequências'),
    (r'\bepidencia\b', 'evidência'),
    (r'\bevidencia\b', 'evidência'), (r'\bevidencias\b', 'evidências'),
    (r'\bcoerencia\b', 'coerência'),
    (r'\bcoincidencia\b', 'coincidência'),
    (r'\bdependencia\b', 'dependência'), (r'\bdependencias\b', 'dependências'),
    (r'\bindependencia\b', 'independência'),
    (r'\binteligencia\b', 'inteligência'),
    (r'\bexcelencia\b', 'excelência'),
    (r'\bpresenca\b', 'presença'), (r'\bpresencas\b', 'presenças'),
    (r'\bpotencia\b', 'potência'), (r'\bpotencias\b', 'potências'),
    (r'\breferencia\b', 'referência'), (r'\breferencias\b', 'referências'),
    (r'\bdiferenca\b', 'diferença'), (r'\bdiferencas\b', 'diferenças'),
    (r'\bconveniencia\b', 'conveniência'),
    (r'\bpatencia\b', 'patência'), (r'\bpotencialmente\b', 'potencialmente'),
    # Adjetivos proparoxítonos (-ico/-ica)
    (r'\bunico\b', 'único'), (r'\bunicos\b', 'únicos'), (r'\bunica\b', 'única'), (r'\bunicas\b', 'únicas'),
    (r'\bpublico\b', 'público'), (r'\bpublicos\b', 'públicos'), (r'\bpublica\b', 'pública'), (r'\bpublicas\b', 'públicas'),
    (r'\bcodigo\b', 'código'), (r'\bcodigos\b', 'códigos'),
    (r'\bautomatico\b', 'automático'), (r'\bautomatica\b', 'automática'), (r'\bautomaticos\b', 'automáticos'), (r'\bautomaticas\b', 'automáticas'),
    (r'\btecnico\b', 'técnico'), (r'\btecnica\b', 'técnica'), (r'\btecnicos\b', 'técnicos'), (r'\btecnicas\b', 'técnicas'),
    (r'\bpratico\b', 'prático'), (r'\bpratica\b', 'prática'), (r'\bpraticos\b', 'práticos'), (r'\bpraticas\b', 'práticas'),
    (r'\bespecifico\b', 'específico'), (r'\bespecifica\b', 'específica'), (r'\bespecificos\b', 'específicos'), (r'\bespecificas\b', 'específicas'),
    (r'\bcritico\b', 'crítico'), (r'\bcritica\b', 'crítica'), (r'\bcriticos\b', 'críticos'), (r'\bcriticas\b', 'críticas'),
    (r'\bdinamico\b', 'dinâmico'), (r'\bdinamica\b', 'dinâmica'), (r'\bdinamicos\b', 'dinâmicos'), (r'\bdinamicas\b', 'dinâmicas'),
    (r'\bestatico\b', 'estático'), (r'\bestatica\b', 'estática'), (r'\bestaticos\b', 'estáticos'), (r'\bestaticas\b', 'estáticas'),
    (r'\bbasico\b', 'básico'), (r'\bbasica\b', 'básica'), (r'\bbasicos\b', 'básicos'), (r'\bbasicas\b', 'básicas'),
    (r'\bclassico\b', 'clássico'), (r'\bclassica\b', 'clássica'), (r'\bclassicos\b', 'clássicos'), (r'\bclassicas\b', 'clássicas'),
    (r'\bhistorico\b', 'histórico'), (r'\bhistorica\b', 'histórica'), (r'\bhistoricos\b', 'históricos'), (r'\bhistoricas\b', 'históricas'),
    (r'\beconomico\b', 'econômico'), (r'\beconomica\b', 'econômica'), (r'\beconomicos\b', 'econômicos'), (r'\beconomicas\b', 'econômicas'),
    (r'\bcientifico\b', 'científico'), (r'\bcientifica\b', 'científica'), (r'\bcientificos\b', 'científicos'),
    (r'\bmatematico\b', 'matemático'), (r'\bmatematica\b', 'matemática'), (r'\bmatematicos\b', 'matemáticos'),
    (r'\bestetico\b', 'estético'), (r'\bestetica\b', 'estética'),
    (r'\bsimbolico\b', 'simbólico'), (r'\bsimbolica\b', 'simbólica'),
    (r'\borganico\b', 'orgânico'), (r'\borganica\b', 'orgânica'),
    (r'\bferramenta\b', 'ferramenta'),  # ok sem acento
    (r'\baltruistico\b', 'altruístico'),
    (r'\bideologico\b', 'ideológico'), (r'\bideologica\b', 'ideológica'),
    (r'\banalogico\b', 'analógico'), (r'\banalogica\b', 'analógica'),
    (r'\bfisico\b', 'físico'), (r'\bfisica\b', 'física'), (r'\bfisicos\b', 'físicos'), (r'\bfisicas\b', 'físicas'),
    (r'\bquimico\b', 'químico'), (r'\bquimica\b', 'química'),
    (r'\bgenerico\b', 'genérico'), (r'\bgenerica\b', 'genérica'),
    (r'\bproprio\b', 'próprio'), (r'\bpropria\b', 'própria'), (r'\bproprios\b', 'próprios'), (r'\bproprias\b', 'próprias'),
    (r'\bconcluido\b', 'concluído'), (r'\bconcluida\b', 'concluída'), (r'\bconcluidos\b', 'concluídos'), (r'\bconcluidas\b', 'concluídas'),
    (r'\bincluido\b', 'incluído'), (r'\bincluida\b', 'incluída'), (r'\bincluidos\b', 'incluídos'), (r'\bincluidas\b', 'incluídas'),
    # Substantivos proparoxítonos
    (r'\bminimo\b', 'mínimo'), (r'\bminima\b', 'mínima'), (r'\bminimos\b', 'mínimos'), (r'\bminimas\b', 'mínimas'),
    (r'\bmaximo\b', 'máximo'), (r'\bmaxima\b', 'máxima'), (r'\bmaaximos\b', 'máximos'), (r'\bmaaximas\b', 'máximas'),
    (r'\bproximo\b', 'próximo'), (r'\bprojima\b', 'próxima'), (r'\bprojimos\b', 'próximos'), (r'\bprojimas\b', 'próximas'),
    (r'\bproxima\b', 'próxima'), (r'\bprojimos\b', 'próximos'), (r'\bproximas\b', 'próximas'),
    (r'\bultimo\b', 'último'), (r'\bultima\b', 'última'), (r'\bultimos\b', 'últimos'), (r'\bultimas\b', 'últimas'),
    (r'\bnivel\b', 'nível'), (r'\bniveis\b', 'níveis'),
    (r'\bnumero\b', 'número'), (r'\bnumeros\b', 'números'),
    (r'\bmodulo\b', 'módulo'), (r'\bmodulos\b', 'módulos'),
    (r'\bindice\b', 'índice'), (r'\bindices\b', 'índices'),
    (r'\bpagina\b', 'página'), (r'\bpaginas\b', 'páginas'),
    (r'\bmaquina\b', 'máquina'), (r'\bmaquinas\b', 'máquinas'),
    (r'\bdecada\b', 'década'), (r'\bdecadas\b', 'décadas'),
    (r'\banalise\b', 'análise'), (r'\banalises\b', 'análises'),
    (r'\bdiagnostico\b', 'diagnóstico'), (r'\bdiagnosticos\b', 'diagnósticos'),
    (r'\bsintaxe\b', 'sintaxe'),  # ok sem acento
    (r'\bcaracter\b', 'caráter'), (r'\bcaracteres\b', 'caracteres'),
    (r'\batomo\b', 'átomo'), (r'\batomos\b', 'átomos'),
    # Adjetivos -ável/-ível
    (r'\bdisponivel\b', 'disponível'), (r'\bdisponiveis\b', 'disponíveis'),
    (r'\bpossivel\b', 'possível'), (r'\bpossiveis\b', 'possíveis'),
    (r'\bdificil\b', 'difícil'), (r'\bdificeis\b', 'difíceis'),
    (r'\bfacil\b', 'fácil'), (r'\bfaceis\b', 'fáceis'),
    (r'\buteis\b', 'úteis'), (r'\butil\b', 'útil'),
    (r'\bresponsavel\b', 'responsável'), (r'\bresponsaveis\b', 'responsáveis'),
    (r'\bconfiavel\b', 'confiável'), (r'\bconfiaveis\b', 'confiáveis'),
    (r'duravel', 'durável'), (r'duraveis', 'duráveis'),
    (r'\bflexivel\b', 'flexível'), (r'\bflexiveis\b', 'flexíveis'),
    (r'\bescalavel\b', 'escalável'), (r'\bescalaveis\b', 'escaláveis'),
    (r'\bsustentavel\b', 'sustentável'), (r'\bsustentaveis\b', 'sustentáveis'),
    (r'\badaptavel\b', 'adaptável'), (r'\badaptaveis\b', 'adaptáveis'),
    (r'\bimportante\b', 'importante'),  # ok sem acento
    (r'\bvulneravel\b', 'vulnerável'), (r'\bvulneraveis\b', 'vulneráveis'),
    (r'\baplicavel\b', 'aplicável'), (r'\baplicaveis\b', 'aplicáveis'),
    (r'\bnotavel\b', 'notável'), (r'\bnotaveis\b', 'notáveis'),
    (r'\bcomparavel\b', 'comparável'), (r'\bcompáráveis\b', 'comparáveis'),
    # Inglês / Português nomes de tech
    (r'\bingles\b', 'inglês'),
    (r'\bportugues\b', 'português'), (r'\bportuguesai\b', 'português'),
    (r'\bfrances\b', 'francês'),
    # Substantivos comuns
    (r'\bservico\b', 'serviço'), (r'\bservicos\b', 'serviços'),
    (r'\bnegocios\b', 'negócios'), (r'\bnegocio\b', 'negócio'),
    (r'\bestagio\b', 'estágio'), (r'\bestágios\b', 'estágios'), (r'\bestâgios\b', 'estágios'),
    (r'\binterface\b', 'interface'),  # ok sem acento
    (r'\bcomodo\b', 'cômodo'), (r'\bcomodidade\b', 'comodidade'),
    # Verbos com acento — "e"→"é" e "esta"→"está" REMOVIDOS: ambiguidade conjuncao/verbo
    # nao corrigir "e" (conjuncao "e" vs verbo "e") nem "esta" (pronome vs verbo "esta")
    # Outras palavras
    (r'\bvideo\b', 'vídeo'), (r'\bvideos\b', 'vídeos'),
    (r'\baudio\b', 'áudio'), (r'\baudios\b', 'áudios'),
    (r'\bperiodo\b', 'período'), (r'\bperiodos\b', 'períodos'),
    (r'\bproposito\b', 'propósito'), (r'\bpropositos\b', 'propósitos'),
    (r'\bexito\b', 'êxito'), (r'\bexitos\b', 'êxitos'),
    (r'\bancora\b', 'âncora'), (r'\bancoras\b', 'âncoras'),
    (r'\bsuperficie\b', 'superfície'), (r'\bsuperficies\b', 'superfícies'),
    (r'\borigem\b', 'origem'),  # ok sem acento
    (r'\boriginar\b', 'originar'),  # ok
    (r'\bhabilidade\b', 'habilidade'),  # ok
    (r'\bhabito\b', 'hábito'), (r'\bhabitos\b', 'hábitos'),
    (r'\bprazo\b', 'prazo'),  # ok sem acento
    (r'\bfacilidade\b', 'facilidade'),  # ok sem acento
    (r'\binterrupao\b', 'interrupção'),  # typo
    (r'\binterrupcao\b', 'interrupção'), (r'\binterrupcoes\b', 'interrupções'),
    (r'\bconcorrencia\b', 'concorrência'),
    (r'\btransparencia\b', 'transparência'),
    (r'\bcoincidencias\b', 'coincidências'),
    (r'\bpratica\b', 'prática'), (r'\bpraticas\b', 'práticas'),  # duplicado mas ok
    (r'\bregistro\b', 'registro'),  # ok
    (r'\bresumo\b', 'resumo'),  # ok
    (r'\bcapitulo\b', 'capítulo'), (r'\bcapitulos\b', 'capítulos'),
    (r'\bgraficos\b', 'gráficos'), (r'\bgrafico\b', 'gráfico'),
    (r'\btopico\b', 'tópico'), (r'\btopicos\b', 'tópicos'),
    (r'\bcelula\b', 'célula'), (r'\bcelulas\b', 'células'),
    (r'\bprologo\b', 'prólogo'),
    (r'\bepilogo\b', 'epílogo'),
    (r'\bgenero\b', 'gênero'), (r'\bgeneros\b', 'gêneros'),
    (r'\brecurso\b', 'recurso'),  # ok
    (r'\bparametro\b', 'parâmetro'), (r'\bparametros\b', 'parâmetros'),
    (r'\brepositorio\b', 'repositório'), (r'\brepositorios\b', 'repositórios'),
    (r'\bdestaque\b', 'destaque'),  # ok
    (r'\bresultado\b', 'resultado'),  # ok
    (r'\bpadrao\b', 'padrão'),  # duplicado mas ok
    (r'\bmecanismo\b', 'mecanismo'),  # ok
    (r'\bgrafos\b', 'grafos'),  # ok
    (r'\bpessoa\b', 'pessoa'),  # ok
    (r'\bdecisao\b', 'decisão'), (r'\bdecisoes\b', 'decisões'),
    (r'\bprestacao\b', 'prestação'),
    (r'\bexecucao\b', 'execução'),  # dup ok
    (r'\btransferencia\b', 'transferência'), (r'\btransferencias\b', 'transferências'),
    (r'\bsolucao\b', 'solução'),  # dup ok
    (r'\bperfomance\b', 'performance'),  # typo fix
    (r'\bperformace\b', 'performance'),  # typo fix
    (r'\btrafico\b', 'tráfego'),
    (r'\blegado\b', 'legado'),  # ok sem acento
    (r'\bacesso\b', 'acesso'),  # ok
    (r'\bgarantia\b', 'garantia'),  # ok
    (r'\bdiretorio\b', 'diretório'), (r'\bdiretorios\b', 'diretórios'),
    (r'\bsalario\b', 'salário'), (r'\bsalarios\b', 'salários'),
    (r'\bescritorio\b', 'escritório'), (r'\bescritorios\b', 'escritórios'),
    (r'\bcenario\b', 'cenário'), (r'\bcenarios\b', 'cenários'),
    (r'\bterritorio\b', 'território'), (r'\bterritórios\b', 'territórios'),
    (r'\bpatrimonio\b', 'patrimônio'), (r'\bpatrimonios\b', 'patrimônios'),
    (r'\bentidades\b', 'entidades'),  # ok
    (r'\bhierarquia\b', 'hierarquia'),  # ok
    (r'\borgao\b', 'órgão'), (r'\borgaos\b', 'órgãos'),
    (r'\borgaos\b', 'órgãos'),
    (r'\bcongelado\b', 'congelado'),  # ok
    (r'\bexplicacao\b', 'explicação'), (r'\bexplicacoes\b', 'explicações'),
    (r'\bpossibilidade\b', 'possibilidade'),  # ok
    (r'\bcapacidade\b', 'capacidade'),  # ok
    (r'\brecorrencia\b', 'recorrência'), (r'\brecorrencias\b', 'recorrências'),
    (r'\bpermanencia\b', 'permanência'),
    (r'\boriginarios\b', 'originários'), (r'\boriginario\b', 'originário'),
    (r'\bescopos\b', 'escopos'),  # ok
    (r'\bescopo\b', 'escopo'),  # ok
    (r'\bqualidade\b', 'qualidade'),  # ok
    (r'\bsimulacao\b', 'simulação'), (r'\bsimulacoes\b', 'simulações'),
    (r'\bstatus\b', 'status'),  # ok (palavra inglesa)
    (r'\blatencia\b', 'latência'), (r'\blatencias\b', 'latências'),
    (r'\bresiliencia\b', 'resiliência'),
    (r'\bobservabilidade\b', 'observabilidade'),  # ok
    (r'\bpersistencia\b', 'persistência'),
    (r'\bdurabilidade\b', 'durabilidade'),  # ok
    (r'\batomicidade\b', 'atomicidade'),  # ok
    (r'\bcongelamento\b', 'congelamento'),  # ok
    (r'\bassincrono\b', 'assíncrono'), (r'\bassincrona\b', 'assíncrona'), (r'\bassincronos\b', 'assíncronos'),
    (r'\bsincrono\b', 'síncrono'), (r'\bsincrona\b', 'síncrona'), (r'\bsincronos\b', 'síncronos'),
    (r'\bidempotente\b', 'idempotente'),  # ok
    (r'\bsistematico\b', 'sistemático'), (r'\bsistematica\b', 'sistemática'),
    (r'\bautossuficiente\b', 'autossuficiente'),  # ok
    (r'\bautomatizar\b', 'automatizar'),  # ok
    (r'\borderem\b', 'ordem'),  # ok - "ordem" sem acento
    (r'\bordernar\b', 'ordenar'),  # ok
    (r'\breproduzivel\b', 'reproduzível'), (r'\breproduzíveis\b', 'reproduzíveis'),
    (r'\bkubernetes\b', 'Kubernetes'),  # nome proprio capitalizado
    (r'\bdocker\b', 'Docker'),  # nome proprio
    (r'\blinux\b', 'Linux'),
    (r'\bwindows\b', 'Windows'),
    (r'\bpython\b', 'Python'),
    (r'\bgithub\b', 'GitHub'),
    (r'\byoutube\b', 'YouTube'),
    (r'\bjavascript\b', 'JavaScript'),
    (r'\btypescript\b', 'TypeScript'),
    (r'\bpostgresql\b', 'PostgreSQL'),
    (r'\bmongodb\b', 'MongoDB'),
    (r'\bwordpress\b', 'WordPress'),
    (r'\binstagram\b', 'Instagram'),
    (r'\bwhatsapp\b', 'WhatsApp'),
    (r'\blinkedin\b', 'LinkedIn'),
    (r'\bfacebook\b', 'Facebook'),
    # Padroes frequentemente gerados por IA sem acento (adicionados v3 19/06/2026)
    (r'\bsao\b', 'são'),
    (r'\bseguranca\b', 'segurança'),
    (r'\busuario\b', 'usuário'), (r'\busuarios\b', 'usuários'),
    (r'\bbinario\b', 'binário'), (r'\bbinarios\b', 'binários'),
    (r'\bdeteccao\b', 'detecção'), (r'\bdeteccoes\b', 'detecções'),
    (r'\blegitimo\b', 'legítimo'), (r'\blegitima\b', 'legítima'), (r'\blegitimos\b', 'legítimos'), (r'\blegitimas\b', 'legítimas'),
    (r'\bobrigatorio\b', 'obrigatório'), (r'\bobrigatoria\b', 'obrigatória'), (r'\bobrigatorios\b', 'obrigatórios'), (r'\bobrigatorias\b', 'obrigatórias'),
    (r'\bcriterio\b', 'critério'), (r'\bcriterios\b', 'critérios'),
    (r'\barbitrario\b', 'arbitrário'), (r'\barbitraria\b', 'arbitrária'),
    (r'\btemporario\b', 'temporário'), (r'\btemporaria\b', 'temporária'),
    (r'\bnecessario\b', 'necessário'), (r'\bnecessaria\b', 'necessária'),
    (r'\binedito\b', 'inédito'), (r'\binedita\b', 'inédita'),
    (r'\bhibrido\b', 'híbrido'), (r'\bhibrida\b', 'híbrida'),
    (r'\bvigilancia\b', 'vigilância'),
    (r'\blicenca\b', 'licença'), (r'\blicencas\b', 'licenças'),
    (r'\bheranca\b', 'herança'),
    (r'\bcomecar\b', 'começar'), (r'\bcomecou\b', 'começou'), (r'\bcomecam\b', 'começam'), (r'\bcomecando\b', 'começando'),
    (r'\bcomeca\b', 'começa'), (r'\bcomecara\b', 'começará'),
    (r'\blancar\b', 'lançar'), (r'\blancando\b', 'lançando'),
    (r'\balcancar\b', 'alcançar'), (r'\balcancou\b', 'alcançou'), (r'\balcanca\b', 'alcança'),
    (r'\bavancar\b', 'avançar'), (r'\bavancou\b', 'avançou'), (r'\bavanca\b', 'avança'), (r'\bavancam\b', 'avançam'),
    (r'\bforcar\b', 'forçar'), (r'\bforcou\b', 'forçou'), (r'\bforca\b', 'força'), (r'\bforcam\b', 'forçam'),
    (r'\binfeccao\b', 'infecção'), (r'\binfeccoes\b', 'infecções'),
    (r'\bexcecao\b', 'exceção'), (r'\bexcecoes\b', 'exceções'),
    (r'\bpresenca\b', 'presença'),
    (r'\bevidencia\b', 'evidência'), (r'\bevidencias\b', 'evidências'),
    (r'\blaboratorio\b', 'laboratório'), (r'\blaboratorios\b', 'laboratórios'),
    (r'\bacessorio\b', 'acessório'), (r'\bacessorios\b', 'acessórios'),
    (r'\bpremio\b', 'prêmio'), (r'\bpremios\b', 'prêmios'),
    (r'\btrafego\b', 'tráfego'),
    (r'\balem\b', 'além'),
    (r'\btambem\b', 'também'),
    (r'\bentao\b', 'então'),
    (r'\bnao\b', 'não'),
    (r'\bvoce\b', 'você'), (r'\bvoces\b', 'vocês'),
]

def _acento_repl(correct):
    """Retorna função de substituição que preserva caixa."""
    def _fn(m):
        word = m.group(0)
        if word.isupper():
            return correct.upper()
        if word[0].isupper():
            return correct[0].upper() + correct[1:]
        return correct
    return _fn

def corrigir_acentos(text: str) -> tuple[str, int]:
    """Corrige acentuacao PT-BR no texto. Retorna (texto_corrigido, num_correcoes)."""
    correcoes = 0
    for padrao, correto in _ACENTO_FIXES:
        novo, n = re.subn(padrao, _acento_repl(correto), text, flags=re.IGNORECASE)
        if n:
            correcoes += n
            text = novo
    return text, correcoes

def _corrigir_campos_post(post: dict) -> int:
    """Aplica correcao de acentos em todos os campos texto do post. Retorna total de correcoes."""
    total = 0
    campos_diretos = ["title", "summary", "metaTitle", "metaDescription", "content",
                      "card1_titulo", "card1_texto", "card2_titulo", "card2_texto",
                      "card3_titulo", "card3_texto", "subtitulo_capa"]
    for campo in campos_diretos:
        if campo in post and isinstance(post[campo], str):
            post[campo], n = corrigir_acentos(post[campo])
            total += n
    for faq in post.get("faqs", []):
        for k in ("question", "answer"):
            if k in faq:
                faq[k], n = corrigir_acentos(faq[k])
                total += n
    for block in post.get("blocks", []):
        if "title" in block:
            block["title"], n = corrigir_acentos(block["title"])
            total += n
        for item in block.get("items", []):
            for k in ("label", "value", "text", "name"):
                if k in item and isinstance(item[k], str):
                    item[k], n = corrigir_acentos(item[k])
                    total += n
    return total


def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


# ── Spell checker PT-BR via pyspellchecker ────────────────────────────────────
# Palavras técnicas, siglas e nomes próprios que não constam no dicionário PT-BR
_SPELL_ALLOWLIST = {
    # Nomes de tecnologias / marcas
    "api","apis","saas","paas","iaas","sdk","cli","gui","ui","ux","url","urls",
    "http","https","html","css","xml","json","yaml","sql","nosql","graphql",
    "rest","grpc","oauth","jwt","cors","csp","csrf","xss",
    "docker","kubernetes","nginx","linux","ubuntu","debian","macos","windows",
    "python","javascript","typescript","nodejs","react","angular","vue","astro",
    "mongodb","postgresql","mysql","redis","kafka","rabbitmq","elasticsearch",
    "github","gitlab","bitbucket","npm","pip","brew","apt","yarn","pnpm",
    "aws","gcp","azure","cloudflare","vercel","netlify","heroku","railway",
    "claude","chatgpt","gemini","ollama","langchain","openai","anthropic",
    "dotnet","csharp","java","golang","rust","swift","kotlin","php","ruby",
    "vscode","jetbrains","neovim","vim","git","ci","cd","devops","mlops",
    "llm","llms","rag","nlp","ia","ml","ai","gpu","cpu","ram","ssd","tpu",
    "regex","stdin","stdout","stderr","bash","powershell","zsh","ssh","ftp",
    "webhook","websocket","microservices","monorepo","monolith","backend","frontend",
    "deploy","deployment","container","containers","cluster","clusters","pod","pods",
    "token","tokens","payload","cache","hash","hashmap","array","string","boolean",
    "async","await","callback","promise","stream","pipeline","middleware","proxy",
    "webhook","endpoint","endpoints","crud","orm","dto","dao","pojo","mvp",
    "waha","idrive","cnpj","cpf","mei","clt","pj","lgpd","gdpr",
    "curitiba","parana","brasil","sao","paulo","rio","janeiro",  # nomes proprios
    "blog","blogs","post","posts","feed","rss","seo","cta","roi","kpi",
    # Abreviaturas comuns no texto técnico
    "ex","etc","vs","obs","ps","nb","id","ids","ok","apps","app",
    # Termos em inglês usados sem tradução
    "framework","frameworks","plugin","plugins","runtime","build","builds",
    "commit","commits","branch","merge","pull","push","fork","forks","repo","repos",
    "issue","issues","release","releases","tag","tags","debug","debugger",
    "benchmark","benchmarks","snippet","snippets","boilerplate","scaffold",
    "feature","features","bug","bugs","hotfix","refactor","lint","linter",
    "log","logs","dashboard","dashboards","template","templates","layout",
    "sidebar","navbar","footer","header","banner","modal","popup","tooltip",
    "dark","light","mode","toggle","switch","checkbox","dropdown","slider",
    "upload","download","streaming","hosted","hosting","server","servers",
    "client","clients","request","requests","response","responses","payload",
    "router","routers","route","routes","middleware","handler","handlers",
    "schema","schemas","migration","migrations","seed","seeds","fixture",
    "mock","mocks","stub","stubs","spy","test","tests","coverage","suite",
    "bot","bots","scraper","crawler","parser","worker","workers","cron","job","jobs",
    "feedback","update","updates","setup","settings","config","configs","flag","flags",
    "backup","backups","restore","rollback","snapshot","snapshots","revert",
    "status","health","metrics","trace","traces","span","spans","alert","alerts",
    "grafana","prometheus","datadog","sentry","newrelic","splunk",
    # Palavras portuguesas que o dicionário pode não reconhecer
    "chatbot","chatbots","startup","startups","roadmap","roadmaps","sprint","sprints",
    "ticket","tickets","backlog","standup","scrum","kanban","agile",
}

def _strip_html(text: str) -> str:
    return re.sub(r'<[^>]+>', ' ', text)

def _normalizar(word: str) -> str:
    """Remove acentos para comparar (NFD decomposition)."""
    return ''.join(c for c in unicodedata.normalize('NFD', word) if unicodedata.category(c) != 'Mn')

def _e_apenas_acento(original: str, corrigido: str) -> bool:
    """Verifica se a diferença entre original e corrigido é apenas acentuação."""
    return _normalizar(original.lower()) == _normalizar(corrigido.lower())

_spell_checker = None
def _get_spell_checker():
    global _spell_checker
    if _spell_checker is None:
        try:
            from spellchecker import SpellChecker
            _spell_checker = SpellChecker(language='pt', distance=1)
        except ImportError:
            _spell_checker = False  # não disponível
    return _spell_checker

def spell_check_post(post: dict) -> tuple[int, list[str]]:
    """
    Detecta palavras sem acento usando dicionário PT-BR (pyspellchecker).
    Corrige automaticamente apenas quando há exatamente 1 candidato e a
    diferença é SOMENTE de acentuação (sem mudança de letras).
    Retorna (num_correcoes, lista_de_avisos_para_revisao_manual).
    """
    checker = _get_spell_checker()
    if not checker:
        return 0, []

    # Campos de texto a verificar (campos de string simples)
    campos_texto = ["title", "summary", "metaTitle", "metaDescription", "content"]

    # 1. Coletar todo o texto para descobrir vocabulário a verificar
    texto_completo = " ".join(
        _strip_html(post.get(c, "") or "") for c in campos_texto
    )
    # Tokenizar: apenas palavras com 4+ letras, sem números, em minúsculas
    palavras_raw = re.findall(r'\b[a-záéíóúàãõêôûüçñ]{4,}\b', texto_completo, re.IGNORECASE)
    palavras_lower = {w.lower() for w in palavras_raw}

    # 2. Filtrar allowlist e palavras já com acento (reconhecidas)
    candidatas = palavras_lower - _SPELL_ALLOWLIST
    desconhecidas = checker.unknown(candidatas)

    # 3. Para cada palavra desconhecida, calcular correção segura
    correcoes_map: dict[str, str] = {}  # original_lower -> corrigido
    avisos: list[str] = []

    for palavra in desconhecidas:
        if palavra in _SPELL_ALLOWLIST:
            continue
        candidates = checker.candidates(palavra) or set()
        candidates_list = list(candidates)

        if len(candidates_list) == 1:
            corrigido = candidates_list[0]
            if _e_apenas_acento(palavra, corrigido) and corrigido != palavra:
                correcoes_map[palavra] = corrigido
        elif len(candidates_list) > 1:
            # Filtrar candidatos que são apenas versão acentuada
            acentuados = [c for c in candidates_list if _e_apenas_acento(palavra, c) and c != palavra]
            if len(acentuados) == 1:
                correcoes_map[palavra] = acentuados[0]
            elif len(candidates_list) <= 4:
                avisos.append(f"'{palavra}' -> candidatos: {candidates_list}")

    if not correcoes_map:
        return 0, avisos

    # 4. Aplicar correções nos campos (preservando case)
    def _make_replacer(corrigido: str):
        def _fn(m):
            w = m.group(0)
            if w.isupper(): return corrigido.upper()
            if w[0].isupper(): return corrigido[0].upper() + corrigido[1:]
            return corrigido
        return _fn

    total = 0
    for campo in campos_texto:
        v = post.get(campo, "") or ""
        if not v:
            continue
        for errado, correto in correcoes_map.items():
            novo, n = re.subn(r'\b' + re.escape(errado) + r'\b', _make_replacer(correto), v, flags=re.IGNORECASE)
            if n:
                v = novo
                total += n
        post[campo] = v

    # Campos de FAQs e blocks
    for faq in post.get("faqs", []):
        for k in ("question", "answer"):
            v = faq.get(k, "") or ""
            for errado, correto in correcoes_map.items():
                novo, n = re.subn(r'\b' + re.escape(errado) + r'\b', _make_replacer(correto), v, flags=re.IGNORECASE)
                if n: v = novo; total += n
            faq[k] = v

    for block in post.get("blocks", []):
        for k in ("title",):
            v = block.get(k, "") or ""
            for errado, correto in correcoes_map.items():
                novo, n = re.subn(r'\b' + re.escape(errado) + r'\b', _make_replacer(correto), v, flags=re.IGNORECASE)
                if n: v = novo; total += n
            block[k] = v
        for item in block.get("items", []):
            for k in ("label", "value", "text"):
                v = item.get(k, "") or ""
                for errado, correto in correcoes_map.items():
                    novo, n = re.subn(r'\b' + re.escape(errado) + r'\b', _make_replacer(correto), v, flags=re.IGNORECASE)
                    if n: v = novo; total += n
                item[k] = v

    return total, avisos


def slugify(text: str) -> str:
    text = text.lower()
    for pat, rep in [("[àáâãä]","a"),("[èéêë]","e"),("[ìíîï]","i"),("[òóôõö]","o"),("[ùúûü]","u"),("[ç]","c"),("[ñ]","n")]:
        text = re.sub(pat, rep, text)
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text.strip())
    return re.sub(r"-+", "-", text)[:80]


def check_post(post: dict):
    fields = [post.get(k, "") for k in ["title","summary","metaTitle","metaDescription","content"]]
    for faq in post.get("faqs", []):
        fields += [faq.get("question",""), faq.get("answer","")]
    for block in post.get("blocks", []):
        fields.append(block.get("title",""))
        for item in block.get("items", []):
            fields += [item.get("label",""), item.get("value",""), item.get("text","")]
    for f in fields:
        for c in CHARS_PROIBIDOS:
            if c in f:
                raise ValueError(f"Char proibido U+{ord(c):04X} em: {f[:80]!r}")


def upload_capa(local_path: str) -> tuple:
    file_key = f"covers/{uuid.uuid4()}-cover.jpg"
    s3 = boto3.client(
        "s3",
        endpoint_url=IDRIVE_URL,
        aws_access_key_id=IDRIVE_KEY,
        aws_secret_access_key=IDRIVE_SECRET,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        region_name="us-east-1",
    )
    try:
        s3.head_bucket(Bucket=IDRIVE_BUCKET)
    except Exception:
        s3.create_bucket(Bucket=IDRIVE_BUCKET)
    s3.upload_file(local_path, IDRIVE_BUCKET, file_key, ExtraArgs={"ContentType": "image/jpeg"})
    public_url = f"{PUBLIC_BASE}/{file_key}"
    log(f"Upload OK: {file_key}")
    return file_key, public_url


def inserir_post(post: dict) -> str:
    """Insere via SSH tunnel: encaminha porta local 27018 para 127.0.0.1:27017 no VPS."""
    import paramiko, threading, socket

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(VPS_HOST, port=VPS_PORT, username=VPS_USER, key_filename=SSH_KEY, timeout=30)

    transport = ssh.get_transport()
    local_port = 27018

    # Cria o tunnel em background
    def _forward(local_sock):
        try:
            chan = transport.open_channel("direct-tcpip", ("127.0.0.1", 27017), ("127.0.0.1", local_port))
            while True:
                r, _, _ = __import__("select").select([local_sock, chan], [], [], 1)
                if local_sock in r:
                    data = local_sock.recv(1024)
                    if not data:
                        break
                    chan.send(data)
                if chan in r:
                    data = chan.recv(1024)
                    if not data:
                        break
                    local_sock.send(data)
        except Exception:
            pass
        finally:
            local_sock.close()

    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", local_port))
    server.listen(1)
    server.settimeout(5)

    def _accept_loop():
        try:
            while True:
                try:
                    conn, _ = server.accept()
                    t = threading.Thread(target=_forward, args=(conn,), daemon=True)
                    t.start()
                except socket.timeout:
                    if not transport.is_active():
                        break
        except Exception:
            pass

    t = threading.Thread(target=_accept_loop, daemon=True)
    t.start()

    import time; time.sleep(0.5)  # aguarda tunnel abrir

    from urllib.parse import quote
    uri = f"mongodb://{MONGO_USER}:{quote(MONGO_PASS)}@127.0.0.1:{local_port}/admin?authSource=admin&authMechanism=SCRAM-SHA-1"
    client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=15000)
    db = client[MONGO_DB]
    col = db[MONGO_COL]

    slug = post["slug"]
    existing = col.find_one({"slug": slug}, {"_id": 1, "coverImageKey": 1})
    if existing:
        # Post already exists — update cover image if a new one was generated
        new_key = post.get("coverImageKey")
        new_url = post.get("coverImageUrl")
        if new_key and new_key != existing.get("coverImageKey"):
            col.update_one(
                {"slug": slug},
                {"$set": {"coverImageKey": new_key, "coverImageUrl": new_url}},
            )
            inserted_id = str(existing["_id"])
            client.close()
            server.close()
            log(f"Post ja existia — coverImageKey atualizado: {new_key}")
            return inserted_id
        else:
            raise ValueError(f"Post ja publicado com slug '{slug}' — nao criar duplicado")

    result = col.insert_one(post)
    inserted_id = str(result.inserted_id)
    client.close()
    server.close()
    ssh.close()
    return inserted_id


def rebuild_blogs() -> dict:
    """Build local (npm run build) + deploy via SCP para cada blog."""
    import paramiko, subprocess, tarfile, tempfile

    results = {}
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(VPS_HOST, port=VPS_PORT, username=VPS_USER, key_filename=SSH_KEY, timeout=30)
    sftp = ssh.open_sftp()

    for blog in BLOGS:
        local_dir = BLOG_LOCAL[blog]
        remote_dir = BLOG_REMOTE[blog]
        log(f"Build {blog}...")
        try:
            # 1. npm run build local (npm.cmd no Windows)
            npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
            result = subprocess.run(
                [npm_cmd, "run", "build"],
                cwd=local_dir,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                raise RuntimeError(f"npm build falhou: {result.stderr[-300:]}")
            log(f"  {blog}: build OK")

            # 2. Tar do dist/
            dist_dir = f"{local_dir}/dist"
            tar_path = f"{local_dir}/{blog}-build.tar.gz"
            with tarfile.open(tar_path, "w:gz") as tar:
                tar.add(dist_dir, arcname=".")
            log(f"  {blog}: tar criado")

            # 3. SCP para VPS
            remote_tar = f"/tmp/{blog}-autopost.tar.gz"
            sftp.put(tar_path, remote_tar)
            log(f"  {blog}: SCP OK")

            # 4. Extrair no VPS
            cmd = f"sudo find {remote_dir} -mindepth 1 -delete 2>/dev/null; sudo tar -xzf {remote_tar} -C {remote_dir}; sudo chown -R www-data:www-data {remote_dir}; rm {remote_tar}"
            _, stdout, stderr = ssh.exec_command(cmd, timeout=120)
            stdout.read()
            log(f"  {blog}: deploy OK")
            results[blog] = {"ok": True}

        except Exception as e:
            log(f"  {blog}: ERRO - {e}")
            results[blog] = {"ok": False, "erro": str(e)}

    sftp.close()
    ssh.close()
    return results


def notificar_indexnow(slug: str) -> dict:
    """Notifica IndexNow (Bing/Yandex) com as URLs do novo post em todos os blogs."""
    import threading

    resultados = {}
    lock = threading.Lock()

    def _notificar_blog(blog: str):
        domain = BLOG_DOMAIN[blog]
        url_post = f"https://{domain}/{slug}"
        payload = {
            "host": domain,
            "key": INDEXNOW_KEY,
            "keyLocation": f"https://{domain}/{INDEXNOW_KEY}.txt",
            "urlList": [url_post],
        }
        try:
            r = requests.post(
                "https://api.indexnow.org/indexnow",
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
            status = r.status_code
            ok = status in (200, 202)
            with lock:
                resultados[blog] = {"ok": ok, "status": status}
            log(f"  IndexNow {blog}: HTTP {status} {'OK' if ok else 'FALHOU'}")
        except Exception as e:
            with lock:
                resultados[blog] = {"ok": False, "erro": str(e)}
            log(f"  IndexNow {blog}: ERRO - {e}")

    threads = [threading.Thread(target=_notificar_blog, args=(b,)) for b in BLOGS]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    sucessos = sum(1 for v in resultados.values() if v.get("ok"))
    log(f"IndexNow: {sucessos}/{len(BLOGS)} blogs notificados")
    return resultados


# ---------------------------------------------------------------------------
# Redes Sociais — Facebook Graph API + Instagram Business API
# Credenciais em: E:/PROJETOS/00.documentos/secrets/curitibablog.com.br/social.json
# {
#   "fb_page_id": "103132212436476",
#   "fb_page_token": "<PAGE_ACCESS_TOKEN_LONGA_DURACAO>",
#   "ig_user_id": "17841453558088350"
# }
_SOCIAL_SECRETS_PATH = Path("E:/PROJETOS/00.documentos/secrets/curitibablog.com.br/social.json")

WHATSAPP_GROUP_ID   = "120363409507724098@g.us"
WHATSAPP_GROUP_LINK = "https://chat.whatsapp.com/FXw6emOLBtIHOusvzzz1pS"
WAHA_URL            = "http://127.0.0.1:3000"
WAHA_API_KEY        = "CuritibaShopping2025SecretKey"
WAHA_SESSION        = "default"


def _load_social_config() -> dict | None:
    try:
        if _SOCIAL_SECRETS_PATH.exists():
            return json.loads(_SOCIAL_SECRETS_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def _truncar(texto: str, max_chars: int) -> str:
    if len(texto) <= max_chars:
        return texto
    return texto[:max_chars - 3].rstrip() + "..."


def postar_whatsapp_grupo(titulo: str, summary: str, slug: str) -> dict:
    """Envia mensagem sobre novo post no grupo WhatsApp via WAHA (SSH tunnel para VPS:3000)."""
    import paramiko, threading, socket, time

    post_url = f"https://curitibablog.com.br/{slug}"
    mensagem = (
        f"📰 *{titulo}*\n\n"
        f"{_truncar(summary, 200)}\n\n"
        f"🔗 Leia agora: {post_url}\n\n"
        f"💬 Gostou? Compartilhe com quem pode se interessar!\n"
        f"👥 Entre no grupo para receber novidades:\n{WHATSAPP_GROUP_LINK}"
    )

    # SSH tunnel: encaminha 127.0.0.1:3001 (local) -> 127.0.0.1:3000 (VPS)
    local_waha_port = 3001
    ssh = None
    server_sock = None
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(VPS_HOST, port=VPS_PORT, username=VPS_USER, key_filename=SSH_KEY, timeout=30)
        transport = ssh.get_transport()

        def _forward(local_conn):
            try:
                chan = transport.open_channel("direct-tcpip", ("127.0.0.1", 3000), ("127.0.0.1", local_waha_port))
                while True:
                    r, _, _ = __import__("select").select([local_conn, chan], [], [], 1)
                    if local_conn in r:
                        data = local_conn.recv(4096)
                        if not data:
                            break
                        chan.send(data)
                    if chan in r:
                        data = chan.recv(4096)
                        if not data:
                            break
                        local_conn.send(data)
            except Exception:
                pass
            finally:
                local_conn.close()

        server_sock = socket.socket()
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(("127.0.0.1", local_waha_port))
        server_sock.listen(5)
        server_sock.settimeout(5)

        def _accept_loop():
            try:
                while True:
                    try:
                        conn, _ = server_sock.accept()
                        t = threading.Thread(target=_forward, args=(conn,), daemon=True)
                        t.start()
                    except socket.timeout:
                        if not transport.is_active():
                            break
            except Exception:
                pass

        threading.Thread(target=_accept_loop, daemon=True).start()
        time.sleep(0.5)

        waha_url_tunnel = f"http://127.0.0.1:{local_waha_port}"
        r = requests.post(
            f"{waha_url_tunnel}/api/sendText",
            headers={"X-Api-Key": WAHA_API_KEY, "Content-Type": "application/json"},
            json={"session": WAHA_SESSION, "chatId": WHATSAPP_GROUP_ID, "text": mensagem},
            timeout=20,
        )
        if r.ok:
            log(f"WhatsApp grupo: mensagem enviada")
            return {"ok": True}
        else:
            log(f"WhatsApp grupo: ERRO HTTP {r.status_code} — {r.text[:200]}")
            return {"ok": False, "erro": r.text[:200]}
    except Exception as e:
        log(f"WhatsApp grupo: EXCECAO — {e}")
        return {"ok": False, "erro": str(e)}
    finally:
        if server_sock:
            try:
                server_sock.close()
            except Exception:
                pass
        if ssh:
            try:
                ssh.close()
            except Exception:
                pass


def postar_redes_sociais(titulo: str, summary: str, slug: str, cover_url: str | None) -> dict:
    """
    Passo 11 do pipeline: publica no Facebook Page e no Instagram Business.
    Requer social.json com fb_page_id, fb_page_token, ig_user_id.
    Falha silenciosa: erros sao logados mas NAO bloqueiam a publicacao.
    """
    config = _load_social_config()
    if not config:
        log("AVISO: social.json nao encontrado — pulando autopost em redes sociais")
        return {"facebook": "sem_config", "instagram": "sem_config"}

    fb_page_id    = config.get("fb_page_id", "")
    fb_page_token = config.get("fb_page_token", "")
    ig_user_id    = config.get("ig_user_id", "")
    post_url      = f"https://curitibablog.com.br/{slug}"
    resultados    = {}

    legenda = (
        f"{titulo}\n\n"
        f"{_truncar(summary, 200)}\n\n"
        f"🔗 Leia o artigo completo: {post_url}\n\n"
        f"💬 Quer ficar informado? Entre no nosso grupo do WhatsApp:\n{WHATSAPP_GROUP_LINK}\n\n"
        "#tecnologia #ia #desenvolvedores #programacao #curitibablog"
    )

    # Facebook Page
    if fb_page_id and fb_page_token:
        try:
            graph_url = f"https://graph.facebook.com/v25.0/{fb_page_id}/feed"
            payload_fb = {
                "message": legenda,
                "link": post_url,
                "access_token": fb_page_token,
            }
            r = requests.post(graph_url, data=payload_fb, timeout=20)
            if r.ok:
                post_id = r.json().get("id", "")
                log(f"Facebook: post publicado ({post_id})")
                resultados["facebook"] = {"ok": True, "id": post_id}
            else:
                log(f"Facebook: ERRO HTTP {r.status_code} — {r.text[:200]}")
                resultados["facebook"] = {"ok": False, "erro": r.text[:200]}
        except Exception as e:
            log(f"Facebook: EXCECAO — {e}")
            resultados["facebook"] = {"ok": False, "erro": str(e)}
    else:
        log("Facebook: fb_page_id ou fb_page_token nao configurados — pulando")
        resultados["facebook"] = "sem_config"

    # Instagram Business
    if ig_user_id and fb_page_token and cover_url:
        try:
            media_url = f"https://graph.facebook.com/v25.0/{ig_user_id}/media"
            payload_media = {
                "image_url": cover_url,
                "caption": legenda,
                "access_token": fb_page_token,
            }
            r1 = requests.post(media_url, data=payload_media, timeout=20)
            if not r1.ok:
                raise RuntimeError(f"Criar container falhou: HTTP {r1.status_code} {r1.text[:200]}")
            container_id = r1.json().get("id", "")

            publish_url = f"https://graph.facebook.com/v25.0/{ig_user_id}/media_publish"
            r2 = requests.post(publish_url, data={"creation_id": container_id, "access_token": fb_page_token}, timeout=20)
            if r2.ok:
                ig_post_id = r2.json().get("id", "")
                log(f"Instagram: post publicado ({ig_post_id})")
                resultados["instagram"] = {"ok": True, "id": ig_post_id}
            else:
                raise RuntimeError(f"Publicar container falhou: HTTP {r2.status_code} {r2.text[:200]}")
        except Exception as e:
            log(f"Instagram: EXCECAO — {e}")
            resultados["instagram"] = {"ok": False, "erro": str(e)}
    elif not cover_url:
        log("Instagram: sem cover_url disponivel — pulando (Instagram requer imagem)")
        resultados["instagram"] = "sem_imagem"
    else:
        log("Instagram: ig_user_id nao configurado — pulando")
        resultados["instagram"] = "sem_config"

    return resultados


def postar_x_twitter(titulo: str, summary: str, slug: str) -> dict:
    """
    Passo 13 do pipeline: publica tweet no X via API v2 OAuth 1.0a.
    Requer social.json com x_consumer_key, x_consumer_secret,
    x_access_token, x_access_token_secret.
    Falha silenciosa — erros sao logados mas NAO bloqueiam a publicacao.
    """
    config = _load_social_config()
    if not config:
        log("X: social.json nao encontrado — pulando")
        return {"ok": False, "erro": "sem_config"}

    consumer_key    = config.get("x_consumer_key", "")
    consumer_secret = config.get("x_consumer_secret", "")
    access_token    = config.get("x_access_token", "")
    access_secret   = config.get("x_access_token_secret", "")

    if not all([consumer_key, consumer_secret, access_token, access_secret]):
        log("X: credenciais incompletas em social.json — pulando")
        return {"ok": False, "erro": "credenciais_incompletas"}

    post_url = f"https://curitibablog.com.br/{slug}"
    hashtags = "#tecnologia #IA #programacao #webdev"
    tweet_base = f"{titulo}\n\n{post_url}\n\n{hashtags}"
    if len(tweet_base) > 280:
        max_titulo = 280 - len(f"\n\n{post_url}\n\n{hashtags}") - 3
        tweet_text = f"{titulo[:max_titulo]}...\n\n{post_url}\n\n{hashtags}"
    else:
        tweet_text = tweet_base

    try:
        from requests_oauthlib import OAuth1
        auth = OAuth1(consumer_key, consumer_secret, access_token, access_secret)
        r = requests.post(
            "https://api.twitter.com/2/tweets",
            auth=auth,
            json={"text": tweet_text},
            timeout=20,
        )
        if r.ok:
            tweet_id = r.json().get("data", {}).get("id", "")
            log(f"X: tweet publicado ({tweet_id})")
            return {"ok": True, "id": tweet_id}
        else:
            log(f"X: ERRO HTTP {r.status_code} — {r.text[:200]}")
            return {"ok": False, "erro": r.text[:200]}
    except Exception as e:
        log(f"X: EXCECAO — {e}")
        return {"ok": False, "erro": str(e)}


def postar_reddit(titulo: str, summary: str, slug: str) -> dict:
    """
    Passo 14 do pipeline: submete link post no Reddit via API OAuth2 (script app).
    Requer social.json com reddit_client_id, reddit_client_secret,
    reddit_username, reddit_password, reddit_subreddit.
    Falha silenciosa — erros sao logados mas NAO bloqueiam a publicacao.
    """
    config = _load_social_config()
    if not config:
        log("Reddit: social.json nao encontrado — pulando")
        return {"ok": False, "erro": "sem_config"}

    client_id     = config.get("reddit_client_id", "")
    client_secret = config.get("reddit_client_secret", "")
    username      = config.get("reddit_username", "")
    password      = config.get("reddit_password", "")
    subreddit     = config.get("reddit_subreddit", "")

    if not all([client_id, client_secret, username, password, subreddit]):
        log("Reddit: credenciais incompletas em social.json — pulando")
        return {"ok": False, "erro": "credenciais_incompletas"}

    post_url = f"https://curitibablog.com.br/{slug}"

    try:
        # OAuth2 token via password grant (script app)
        token_r = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=(client_id, client_secret),
            data={"grant_type": "password", "username": username, "password": password},
            headers={"User-Agent": "curitibablog-autopost/1.0"},
            timeout=15,
        )
        if not token_r.ok:
            log(f"Reddit: falha ao obter token — {token_r.status_code} {token_r.text[:200]}")
            return {"ok": False, "erro": f"token_{token_r.status_code}"}

        access_token = token_r.json().get("access_token", "")
        if not access_token:
            log(f"Reddit: token vazio — {token_r.text[:200]}")
            return {"ok": False, "erro": "token_vazio"}

        # Submeter link post
        submit_r = requests.post(
            "https://oauth.reddit.com/api/submit",
            headers={
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "curitibablog-autopost/1.0",
            },
            data={
                "kind": "link",
                "sr": subreddit,
                "title": titulo[:300],
                "url": post_url,
                "resubmit": True,
                "nsfw": False,
                "spoiler": False,
            },
            timeout=20,
        )
        if not submit_r.ok:
            log(f"Reddit: ERRO submit {submit_r.status_code} — {submit_r.text[:200]}")
            return {"ok": False, "erro": submit_r.text[:200]}

        data = submit_r.json()
        # Reddit retorna erros dentro do JSON com status 200
        errors = data.get("json", {}).get("errors", [])
        if errors:
            log(f"Reddit: ERRO na resposta — {errors}")
            return {"ok": False, "erro": str(errors)}

        post_id = data.get("json", {}).get("data", {}).get("id", "")
        permalink = data.get("json", {}).get("data", {}).get("url", "")
        log(f"Reddit: post publicado ({post_id}) — {permalink}")
        return {"ok": True, "id": post_id, "url": permalink}

    except Exception as e:
        log(f"Reddit: EXCECAO — {e}")
        return {"ok": False, "erro": str(e)}


def main(json_path: str):
    hoje = datetime.date.today().isoformat()
    log_path = LOGS_DIR / f"{hoje}.json"
    run_log = {"data": hoje, "etapas": {}}

    try:
        # 1. Ler JSON do post gerado pelo agente
        log(f"Lendo post de: {json_path}")
        with open(json_path, encoding="utf-8") as f:
            post_data = json.load(f)

        slug = slugify(post_data.get("slug", post_data.get("title", "")))
        post_data["slug"] = slug

        # 2. Validar chars proibidos
        check_post(post_data)
        log("checkPost OK")

        # 2b. Corrigir acentuacao PT-BR automaticamente (ANTES de usar titulo/subtitulo)
        n_correcoes = _corrigir_campos_post(post_data)
        # 2c. Spell checker PT-BR (pyspellchecker) — captura padroes nao cobertos pela lista manual
        n_spell, avisos_spell = spell_check_post(post_data)
        n_correcoes += n_spell
        if n_correcoes:
            log(f"AVISO: {n_correcoes} correcao(es) de acentuacao aplicada(s) — revise o JSON gerado")
            if n_spell:
                log(f"  spell checker aplicou {n_spell} correcao(es) adicionais")
        else:
            log("Acentuacao PT-BR OK")
        for aviso in avisos_spell:
            log(f"  SPELL REVISAO MANUAL: {aviso}")

        # Extrair titulo/subtitulo APOS correcao de acentos
        titulo    = post_data["title"]
        subtitulo = post_data.get("subtitulo_capa", "")
        log(f"Post: {titulo} | slug: {slug}")

        # 3. Garantir category valida
        cats_validas = {"ferramentas-de-ia", "desenvolvimento", "tecnologia", "negocios"}
        if post_data.get("category") not in cats_validas:
            post_data["category"] = "tecnologia"
        if not post_data.get("categories"):
            post_data["categories"] = [post_data["category"], "tecnologia"]

        # 4. Gerar capa via Google Flow (Playwright)
        # Se Flow falhar: publicar sem imagem (sem fallback Pillow — texto sem acento e invalido em producao)
        sys.path.insert(0, str(THIS_DIR))
        capa_path = str(LOGS_DIR / f"{hoje}-cover.jpg")
        cover_key = None
        cover_url = None
        try:
            from gerar_capa_flow import gerar_capa_flow
            gerar_capa_flow(titulo=titulo, output_path=capa_path)
            log(f"Capa gerada via Flow: {capa_path}")
            run_log["etapas"]["capa"] = capa_path

            # 5. Upload IDrive E2 (so se capa foi gerada)
            cover_key, cover_url = upload_capa(capa_path)
            run_log["etapas"]["upload"] = {"key": cover_key, "url": cover_url}
        except Exception as e_flow:
            log(f"AVISO: Flow falhou ({e_flow}) — post sera publicado sem imagem de capa")
            run_log["etapas"]["capa"] = f"FALHOU: {e_flow}"

        # 6. Montar doc MongoDB
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        doc = {
            "isActive": True,
            "title": titulo,
            "slug": slug,
            "summary": post_data.get("summary", ""),
            "metaTitle": post_data.get("metaTitle", titulo[:60]),
            "metaDescription": post_data.get("metaDescription", ""),
            "content": post_data.get("content", ""),
            "faqs": post_data.get("faqs", []),
            "blocks": post_data.get("blocks", []),
            "tags": post_data.get("tags", []),
            "category": post_data.get("category", "tecnologia"),
            "categories": post_data.get("categories", ["tecnologia"]),
            "authorId": "system",
            "authorName": "CuritibaBlog",
            "isPublished": True,
            "publishedAt": now_utc,
            "isFeatured": False,
            "sequence": 0,
            "views": 0,
            "sites": BLOGS,
        }
        if cover_key:
            doc["coverImageKey"] = cover_key
        if cover_url:
            doc["coverImageUrl"] = cover_url
        _corrigir_campos_post(doc)
        spell_check_post(doc)
        check_post(doc)

        # 7. Inserir MongoDB
        inserted_id = inserir_post(doc)
        log(f"Post inserido: {inserted_id}")
        run_log["etapas"]["mongo"] = {"id": inserted_id, "slug": slug}

        # 8. Rebuild blogs
        rebuild_results = rebuild_blogs()
        run_log["etapas"]["rebuild"] = rebuild_results

        # 9. Verificar HTTP
        try:
            r = requests.get(f"https://curitibablog.com.br/{slug}", timeout=15)
            http_status = r.status_code
        except:
            http_status = 0
        log(f"HTTP curitibablog/{slug}: {http_status}")
        run_log["etapas"]["http_check"] = http_status

        # 10. Notificar IndexNow (Bing/Yandex) — paralelo por blog
        log("Notificando IndexNow...")
        indexnow_results = notificar_indexnow(slug)
        run_log["etapas"]["indexnow"] = indexnow_results

        # 11. Autopost Facebook e Instagram
        log("Postando em redes sociais...")
        social_results = postar_redes_sociais(
            titulo=doc["title"],
            summary=doc["summary"],
            slug=slug,
            cover_url=cover_url,
        )
        run_log["etapas"]["social"] = social_results

        # 12. Enviar no grupo WhatsApp Curitiba Blog
        log("Enviando no grupo WhatsApp...")
        wpp_result = postar_whatsapp_grupo(
            titulo=doc["title"],
            summary=doc["summary"],
            slug=slug,
        )
        run_log["etapas"]["whatsapp"] = wpp_result

        # 13. Postar no X (Twitter)
        log("Postando no X (Twitter)...")
        x_result = postar_x_twitter(
            titulo=doc["title"],
            summary=doc["summary"],
            slug=slug,
        )
        run_log["etapas"]["x_twitter"] = x_result

        # 14. Postar no Reddit
        log("Postando no Reddit...")
        reddit_result = postar_reddit(
            titulo=doc["title"],
            summary=doc["summary"],
            slug=slug,
        )
        run_log["etapas"]["reddit"] = reddit_result

        run_log["status"] = "CONCLUIDO"
        run_log["post_url"] = f"https://curitibablog.com.br/{slug}"
        log(f"CONCLUIDO: https://curitibablog.com.br/{slug}")

    except Exception as e:
        import traceback
        run_log["status"] = "ERRO"
        run_log["erro"] = str(e)
        run_log["traceback"] = traceback.format_exc()
        log(f"ERRO: {e}")
        sys.exit(1)
    finally:
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(run_log, f, ensure_ascii=False, indent=2, default=str)
        log(f"Log: {log_path}")

    return run_log.get("status") == "CONCLUIDO"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python publicar_post.py <caminho_para_json>")
        sys.exit(1)
    ok = main(sys.argv[1])
    sys.exit(0 if ok else 1)
