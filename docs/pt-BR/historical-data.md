# Descoberta histórica de BUs e conversão bruta para Parquet

## Alcance de “todas as eleições disponíveis”

A busca oficial por `boletim`, em 01/11/2026, retornou 11 conjuntos com **425 recursos ZIP de BU tabular**: eleições regulares de 2012, 2014, 2016, 2018, 2020, 2022, 2024 e 2026, além de pacotes suplementares nos ciclos de catálogo 2020, 2022 e 2024. É um retrato do catálogo, não afirmação de que todas as eleições já realizadas têm BUs disponíveis. Candidaturas, contas, eleitorado, arquivos binários de urna, logs e RDVs não fazem parte desta conversão de BUs.

Os anos regulares têm respectivamente 46, 56, 46, 56, 54, 56, 52 e 56 recursos, mais três ZIPs externos de suplementares. Cobertura municipal difere da geral; não criar disputas de segundo turno inexistentes. As 425 URLs responderam HTTP 200 na verificação inicial por HEAD, com aproximadamente 13,78 GB compactados informados. Resposta HEAD não comprova conclusão de download ou conversão; consultar o relatório final.

## Coleta concluída (01/11/2026)

Os **425 de 425** pacotes ZIP externos encontrados no catálogo foram baixados e convertidos com sucesso. Eles produziram **466 arquivos Parquet locais**, **420.378.316 linhas** e **5.655.459.985 bytes** de Parquet (cerca de 5,66 GB decimais). O registro por pacote, com URL da fonte, SHA-512 do original, situação do hash publicado, membro de origem, SHA-512 da saída, linhas e campos de validação, está em [`reports/history/conversion-records.json`](../../reports/history/conversion-records.json). Uma auditoria separada recalculou o SHA-512 de cada ZIP baixado e de cada Parquet gerado; tamanhos e hashes conferiram. Contagens de linhas, nomes/ordem das colunas e impressões digitais DuckDB de todos os membros também conferiram.

| Ciclo de catálogo | Pacotes ZIP | Membros Parquet | Linhas | Bytes Parquet |
|---:|---:|---:|---:|---:|
| 2012 | 46 | 46 | 34.430.589 | 206.369.956 |
| 2014 | 56 | 56 | 56.748.147 | 258.592.988 |
| 2016 | 46 | 46 | 36.685.609 | 168.634.421 |
| 2018 | 56 | 56 | 73.552.486 | 349.764.055 |
| 2020 | 55 | 83 | 37.911.271 | 247.162.413 |
| 2022 | 57 | 57 | 72.978.729 | 460.030.267 |
| 2024 | 53 | 66 | 38.124.404 | 1.395.039.627 |
| 2026 | 56 | 56 | 69.947.081 | 2.569.866.258 |
| **Total** | **425** | **466** | **420.378.316** | **5.655.459.985** |

O catálogo listava hashes externos para 422 pacotes, e todos conferiram. Três ZIPs externos suplementares não tinham hash listado no catálogo; quando os arquivos internos tinham checksums no ZIP pai, eles foram verificados separadamente. Os CSVs de 2018 e 2020 continham **46.580 aspas sem escape** em campos de texto entre aspas (29.778 e 16.802, respectivamente). A etapa de compatibilidade documentada preserva essas aspas literais e registra a quantidade ajustada por membro; não ignora linhas malformadas. Os ZIPs e Parquets permanecem locais e fora do GitHub por causa do tamanho. O relatório e os scripts reproduzíveis são públicos; as impressões digitais lógicas são diagnósticos de consistência, não uma implementação independente nem uma prova sem colisões.

## Reprodução

```sh
python scripts/discover_bu.py
python scripts/probe_inventory.py
python scripts/collect_history.py --include-2026 --workers 2
python -m unittest discover -s tests -v
```

Instalar antes as dependências fixadas. A descoberta atualiza o inventário; revisar mudanças antes de baixar. `--year 2012` limita a um ano/ciclo. Por padrão, o coletor histórico ignora 2026, já coberto pela preparação analítica anterior; `--include-2026` também gera exportações brutas históricas para 2026. As duas famílias de saídas são separadas e não devem ser unidas como se fossem votos diferentes.

Índices: `data/<ano-catalogo>/round-<n>/source-index.json`; suplementares: `data/<ano-catalogo>/supplementary/source-index.json`. Downloads ficam em `raw/`, ignorado pelo Git. Saídas em `derived/history/<ano-catalogo>/<particao>/`, também ignoradas. Evidências públicas em `reports/history/`. Hashes SHA-512 dos Parquets locais identificam uma execução; não são assinaturas do TSE.

## Adaptadores e preservação

Cabeçalhos CSV são preservados literalmente, inclusive grafias/espaços históricos como `SG_ UF`. Em TXT sem cabeçalho, o primeiro campo com formato de data de geração identifica uma linha de dados; as colunas recebem nomes posicionais `field_001`, `field_002` etc. A primeira linha não é consumida como cabeçalho. Esses nomes não presumem significado ainda não revisado. Outros padrões interrompem a conversão para análise. Converter dados brutos não significa oferecer esquema histórico unificado para o dashboard.

O coletor decodifica Latin-1 para UTF-8 temporário e interpreta campos entre aspas separados por ponto e vírgula, com esquema explícito somente de texto, leitura estrita e `force_not_null` em todas as colunas originais. Algumas linhas de BU de 2018 e 2020 contêm aspas sem escape dentro de nomes de candidatos. Nesses dois ciclos eleitorais, o coletor normaliza todos os arquivos, corrige apenas as aspas que não podem ser terminadores de campo, preserva essas aspas no nome interpretado e registra a quantidade de correções por membro em `csv_unescaped_quote_repairs`; arquivos sem esses casos recebem zero. A leitura estrita continua habilitada depois dessa compatibilidade e registros malformados não são descartados. **Vazios continuam vazios**; `#NULO#`, `-1`, zeros à esquerda e duplicações permanecem como valores da fonte. Duas colunas de proveniência identificam o ZIP externo e seu SHA-512 local. Usa ZSTD. A regra de vazios difere da preparação analítica original de 2026, que documenta vazio→NULL; consulte o [guia de transparência](parquet-transparency.md).

ZIPs internos de suplementares são visitados recursivamente sem extrair caminhos arbitrários do arquivo para o computador. Se o ZIP pai contém `.sha512` ou `.sha1` de um ZIP interno, o hash é conferido antes da conversão. O pacote externo pode não ter hash listado no catálogo; isso é explicitado, sem declarar verificação publicada bem-sucedida. Todo ZIP externo recebe SHA-512 local. SHA-1 histórico é usado como verificação de integridade fornecida pela fonte, sem apresentá-lo como prova criptográfica moderna de autenticidade. Existem limites de profundidade e memória.

Ano/ciclo do catálogo e data efetiva da eleição são campos diferentes. Um pacote de ciclo 2024 pode incluir eventos em 2025 ou 2026; `ANO_ELEICAO`, `DT_PLEITO` e `NR_TURNO` originais permanecem intactos. Suplementares podem conter vários eventos/turnos. Pastas representam partições do catálogo e não substituem códigos ou datas dos pleitos.

## Validação e relatórios

Para cada membro, são comparados contagem de registros, nomes/ordem das colunas e dois resumos independentes da ordem física, calculados sobre todos os valores originais: soma e XOR dos hashes de linha DuckDB. Duplicações contribuem com sua multiplicidade. São diagnósticos do mesmo mecanismo de leitura/consulta, **não uma implementação independente ou prova matemática sem colisões**. Auditoria exata pode comparar multiconjuntos completos com `EXCEPT ALL` nos dois sentidos. Hashes de arquivos identificam bytes; resumos comparam registros interpretados conforme a regra declarada.

Hashes de fonte/saída, linhas, membro original, esquema, tamanhos e resultado permanecem no JSON local de cada pacote e no relatório público. CSV vazio pode gerar Parquet válido sem linhas; não comprova existência de disputa. Originais são preservados. Formatos desconhecidos, hashes divergentes e tabelas malformadas são reportados como falhas, sem descartar linhas silenciosamente. Retomadas confiam nos metadados concluídos; não recalculam todos os hashes dos derivados existentes. Sucesso de download/conversão não comprova cobertura de todas as seções nem totalização jurídica oficial.
