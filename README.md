# Medsoft

## Visão Geral

O Medsoft é uma plataforma web para gestão de clínicas e consultórios, desenvolvida em Python, com arquitetura baseada em Flask, suporte a PostgreSQL e estrutura preparada para operação multiempresa (tenant).

## Funcionalidades

- Agenda
- Cadastro de Pacientes
- Profissionais de Saúde
- Clínicas e Empresas
- Receituário
- Anamnese
- Usuários e Perfis
- Configurações
- APIs

## Estrutura

```text
backend/
templates/
static/
docs/
database/
tests/
```

## Documentação

- DOCUMENTACAO.md
- MANUAL_DESENVOLVEDOR.md

## Organizar o histórico localmente

O botão **Organizar texto** usa regras locais em Python para distribuir as frases
pelos tópicos do padrão incluído. Não utiliza serviços externos, não requer chave e
não envia dados clínicos pela internet. O resultado volta ao campo de edição e só é
gravado depois da revisão do profissional e do clique em **Salvar**.

A classificação reconhece termos comuns relacionados a histórico familiar,
medicamentos, alergias, antecedentes, cirurgias, hábitos, exame físico, diagnóstico
e conduta. Frases ambíguas são mantidas em História da Doença Atual, Queixa
Principal ou no primeiro tópico disponível, nessa ordem.
