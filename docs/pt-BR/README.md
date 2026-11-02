# Guia do projeto

## Objetivo

Disponibilizar coleta e análise reproduzíveis de dados eleitorais para reutilização pública e, depois, um site interativo com busca de candidatos, navegação territorial, mapas e gráficos. Os 425 pacotes tabulares de BU encontrados no catálogo do TSE, em ciclos de 2012 a 2026 e eleições suplementares, e 170 pacotes de resultados por seção de 2000 a 2010 foram coletados. As tabelas canônicas locais contêm 637.673.681 linhas de votos e 16.849.380 totais por seção/urna. Consulte o [guia histórico](historical-data.md), as [evidências dos BUs](../../reports/history/conversion-records.json), o [relatório de downloads antigos](../../reports/history/legacy-results-downloads.json) e a [auditoria de disponibilidade dos campos](../../reports/history/canonical-coverage.json). Interface em português do Brasil; identificadores e ferramentas em inglês.

## Reprodução

Siga o início rápido na raiz. `download.py --year 2026 --round 1` baixa um turno; sem `--round`, baixa ambos. Downloads usam `.part` para retomada; arquivos finais são conferidos contra o SHA-512 versionado. Divergência interrompe o processamento e preserva o arquivo para investigação. Não excluir o original para esconder uma falha.

`prepare.py --year 2026` converte um pacote por vez de CSV Latin-1 para UTF-8 e, depois, Parquet que preserva as colunas originais como texto. O hash do original é conferido antes da conversão. A leitura estrita rejeita registros malformados em vez de descartá-los silenciosamente. A cópia temporária UTF-8 é removida ao final de cada pacote. O banco local referencia os Parquets; mantenha a pasta de derivados no lugar ou execute novamente após movê-la. A retomada reutiliza saídas com a versão atual do processamento e a mesma identidade da fonte; não recalcula hashes dos derivados anteriores.

O parâmetro opcional `--raw-dir /caminho/para/bu` reutiliza uma coleção existente em pasta única, sem mover ou duplicar os ZIPs. Não publicar caminhos absolutos locais.

## Consultas

O banco `derived/2026/elections.duckdb` pode ser aberto pelo Python/DuckDB em modo somente leitura. A visão `votes` permite filtrar eleição, cargo, candidato, UF, município, zona e seção. Use consultas parametrizadas nas aplicações.

A tabela `candidates` serve para busca pelo nome presente no BU; `candidate_municipality` e `candidate_state` aceleram gráficos agregados. Todo percentual deve declarar seu denominador: todos os votos, votos nominais ou outra medida explícita. A soma nacional de cargos estaduais não representa uma disputa nacional única.

## Situação e desenvolvimento

Consulte `reports/2026/` e `reports/history/` para evidências geradas e a [metodologia](methodology.md) para interpretar os resultados. As tabelas canônicas de todos os ciclos ficam localmente e não entram no Git devido ao tamanho. Os resultados de 2000–2010 são totalizados por seção e não contêm número de urna; os BUs começam em 2012. Ainda falta conferir com cadastro independente de seções e totais oficiais, e não há dashboard hospedado ou base nacional publicada. Fluxo: issue → branch → commit → PR → revisão e testes → promoção aprovada. Teste local não autoriza implantação. Este repositório público não deve conter configuração de implantação ou infraestrutura.

## Próximas etapas

1. Validar linhas, unicidade das chaves e balanços por seção/cargo em 2026.
2. Conferir contra cadastro independente de seções esperadas e resultados agregados oficiais, preservando datas das fontes e diferenças de destinação jurídica dos votos.
3. Obter cadastro de candidatos e vínculos geográficos oficiais; adicionar países, malhas e coordenadas disponíveis dos locais de votação.
4. Construir o portal responsivo com fundo cinza e detalhes em vermelho, laranja e amarelo. Ainda não existe site público operacional.
5. Revisar adaptadores entre eleições e vínculos geográficos/de candidatos antes de criar análises históricas combinadas.
6. Avaliar distribuição separada das bases derivadas grandes; hospedagem dos dados ainda não definida.
