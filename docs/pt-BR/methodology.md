# Metodologia e modelo de dados

## Proveniência e camadas

Manifestos versionados identificam URLs oficiais, SHA-512 publicados, tamanhos e conteúdo dos ZIPs. Originais locais são referências preservadas. O Parquet bruto mantém as colunas do CSV como texto e adiciona `source_package` e `source_sha512`. A visão `votes` converte quantidades com validação estrita e completa códigos eleitorais de município (5), zona (4) e seção (4) com zeros. O número da urna efetivada permanece texto.

Derivados e bancos são artefatos locais reconstruíveis, não definições de infraestrutura. DuckDB é usado somente para preparação e validação local; não define a arquitetura de hospedagem de produção.

## Granularidade e chaves

- `votes`: uma linha de votos da fonte; chave analítica composta por eleição/pleito, ano, turno, UF, município eleitoral, zona, seção, cargo, tipo de votável, número do votável e partido. Duplicações são preservadas e sinalizadas, nunca eliminadas silenciosamente.
- `section_office`: um registro por eleição/pleito, UF, município, zona, seção e cargo. Mínimos/máximos identificam divergências nos metadados repetidos. Não somar comparecimento ou aptos por linha de candidato nem entre cargos.
- `section_quality`: consistência dos metadados, aptos = comparecimento + abstenções e comparação diagnóstica da soma de votos com as oportunidades de voto esperadas. Para senador no primeiro turno de 2026, usa duas escolhas por eleitor; demais cargos, uma. É diagnóstico, não conclusão jurídica nem regra para anos históricos.
- `candidate_municipality` e `candidate_state`: somas dos votos dos BUs por território, preservando eleição, cargo, tipo e número. Tipo `1` seleciona candidatos nominais. Brancos, nulos e votos de legenda ficam separados.
- `candidates`: combinações distintas de nome/número/partido presentes no BU. Presidência tem abrangência nacional; cargos estaduais preservam UF. Variações de nomes/partidos são mantidas. Não é um cadastro completo de candidaturas.
- `territories`: municípios/localidades eleitorais distintos; país BR para registros nacionais e desconhecido para exterior até obter vínculo oficial.

Agregações de comparecimento usam apenas registros de seção/cargo com metadados repetidos consistentes. Conflitos permanecem visíveis nos relatórios; ausência não deve aparecer como zero ou total completo.

## Seções agregadas e urnas físicas

Uma seção agregada compartilha o BU da principal. Preservar essa relação; não distribuir votos da principal entre subordinadas nem gerar fatos adicionais. A versão atual preserva `aggregated_sections` como texto e cria `section_aliases` para buscar uma subordinada e localizar sua principal. Relacionar pela chave completa de eleição/pleito, território e cargo, usando o BU principal uma única vez; essa tabela nunca deve multiplicar votos. Conflitos são contados no relatório de validação. O identificador da urna física não é chave global de seção e não deve ser usado sozinho nas relações.

## Cobertura e verificações

Cobertura de pacotes: 28 territórios × 2 turnos em 2026. Contagens de seções indicam o que foi observado na fonte, sem provar presença de todas as seções esperadas. Verificações medem chaves duplicadas, votos negativos, divergências de metadados e balanços por seção/cargo. Falhas não são descartadas nem tratadas como verificadas. Votos tabulares de BU podem diferir da totalização oficial ajustada juridicamente; a conciliação deve considerar datas das fontes, anulações, destinações de votos, substituições e pleitos especiais.

Nome de localidade no exterior não determina país. Código municipal TSE não é código de geometria IBGE. Mapas precisam de vínculo revisado; pontos de locais de votação precisam de coordenadas de fonte identificada. Não inferir escolhas individuais de eleitores a partir de agregados ou logs.

## Marcadores da fonte

Duas linhas do segundo turno têm cargo e votável `-1`/`#NULO#`, com zero votos. São preservadas nos dados brutos, em `votes` e nos perfis por seção, e contadas separadamente. Agregações de candidatos e territórios excluem códigos não positivos de cargo/votável. Por isso a contagem de seções observadas e de seções com disputa difere; nenhuma representa cadastro independente de seções esperadas.
