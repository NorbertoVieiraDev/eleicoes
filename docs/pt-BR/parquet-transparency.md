# Como os arquivos oficiais são convertidos para Parquet

O projeto muda a **representação de armazenamento** para viabilizar análises. Qualquer pessoa deve poder conferir isso pelas fontes, pelo código publicado e pelas regras explícitas, sem depender de uma declaração de confiança do projeto. Os ZIPs originais do TSE permanecem intactos.

## Sequência rastreável do processamento atual de 2026

1. Obter URL oficial do ZIP e SHA-512 em `data/2026/round-1/manifest.json` ou `round-2/manifest.json`. São retratos das fontes, não resultados atualizados automaticamente.
2. Baixar o ZIP por HTTPS. Calcular SHA-512 e comparar com o valor publicado. Interromper se houver divergência. Hash correto do ZIP, sozinho, não prova correção do Parquet derivado.
3. Abrir o ZIP e exigir exatamente um CSV. Ler o texto em **Latin-1** e escrever cópia temporária em **UTF-8**. Muda a codificação dos bytes, preservando os caracteres pretendidos, inclusive acentos. A leitura do ZIP também confere os CRCs durante a extração.
4. Interpretar o CSV com **DuckDB 1.4.3**, separador `;`, cabeçalho, `all_varchar=true`, `strict_mode=true` e `nullstr=''`. Todas as colunas originais entram como texto. Campos vazios são representados como `NULL` conforme essa configuração; marcadores literais como `#NULO#` e `-1` são mantidos. A conversão de vazio para NULL é uma transformação e está explicitada aqui.
5. Selecionar todas as colunas originais e acrescentar duas colunas de proveniência: `source_package` (nome do ZIP) e `source_sha512` (hash do ZIP conferido). Não selecionar candidatos, somar votos, eliminar duplicações ou completar códigos com zeros nessa exportação bruta.
6. Gravar `<pacote-original>.parquet` com compactação **Zstandard (ZSTD)**, reversível. A exportação bruta não filtra registros intencionalmente. Ela representa uma tabela interpretada, não uma cópia byte a byte do CSV: separadores, aspas, codificação e disposição física pertencem ao formato original.
7. Registrar contagem de linhas, hash da fonte, versão do processamento, tamanho e duração no JSON local do pacote. Remover somente a cópia temporária UTF-8. Preservar os ZIPs originais.

Implementação: [`scripts/prepare.py`](../../scripts/prepare.py). Dependências: [`requirements.txt`](../../requirements.txt). Manifestos registram URLs, hashes e a correção do link de RR. ZIP, CSV e Parquet têm hashes diferentes porque seus bytes são diferentes. Os bytes e a ordem física do Parquet também podem variar entre versões de bibliotecas. A comparação entre formatos deve conferir registros lógicos e a quantidade de repetições, não igualdade de hashes de arquivos distintos.

## Exportação bruta e produtos calculados

| Produto | Transformações |
| --- | --- |
| `<pacote>.parquet` | Interpretação/codificação do CSV e compactação; duas colunas de proveniência; colunas originais como texto |
| Visão `votes` | Nomes analíticos em inglês, conversão estrita de medidas numéricas e zeros à esquerda em município/zona/seção |
| `*.sections.parquet` / `section_office` | Agrupa por eleição, território, seção e cargo; soma votos e calcula verificações |
| Agregados de candidatos | Somam votos registrados por município/UF; excluem explicitamente códigos marcadores não positivos de cargo/votável |
| `section_aliases` | Relaciona agregadas ao BU principal para consulta; não distribui nem cria votos adicionais |

Duas linhas marcadoras do segundo turno de 2026, com zero votos e códigos `-1`/`#NULO#`, continuam na exportação bruta e em `votes`. A exclusão dos agregados de candidatos está documentada; não é remoção oculta da fonte. O diagnóstico de senador considera duas escolhas no primeiro turno de 2026. Produtos calculados não devem ser apresentados como arquivos oficiais inalterados.

## Reprodução e conferência independente

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/download.py --year 2026
python scripts/prepare.py --year 2026
python -m unittest discover -s tests -v
```

Para um exemplo pequeno, depois do download use `--only bweb_2t_ZZ_261020260742.zip` na preparação. Isso gera o Parquet/perfil desse pacote e não constitui carga nacional completa. Inspecione o CSV original e as colunas de mesmo nome no Parquet, desconsiderando apenas as duas colunas adicionadas. Uma auditoria completa de equivalência deve comparar nomes de colunas, contagens e o **multiconjunto de todos os valores interpretados das colunas originais**, preservando repetições e a regra declarada de NULL. Igualdade de totais de votos, sozinha, não prova igualdade linha a linha. Não presumir ordem física idêntica.

O relatório atual registra 56 pacotes, 69.947.081 linhas interpretadas, aproximadamente 32,42 GB de CSV e 2,57 GB de Parquet bruto. O ganho de espaço vem da organização por coluna e de valores repetidos, não de uma etapa declarada de redução de linhas. Esses tamanhos não incluem perfis por seção ou outros agregados. Três testes sintéticos cobrem preservação de identificadores/votos e granularidade do comparecimento, rejeição por hash divergente e votos numéricos inválidos.

## Alcance das verificações

O relatório existente confere hashes dos pacotes, validade das chaves/quantidades, duplicações de chave de voto, metadados e balanços de comparecimento/votos. **Não declara comparação independente completa dos multiconjuntos CSV versus Parquet.** A retomada confia nos metadados de conversões anteriores e não recalcula hashes dos derivados existentes. Para reproduzir independentemente, use diretório de saída/cópia de trabalho novo e as fontes originais. Parquets são derivados do projeto, não arquivos assinados ou certificados pelo TSE. A conversão não comprova presença de todas as seções esperadas, assinatura digital da urna ou reprodução dos ajustes jurídicos da totalização.
