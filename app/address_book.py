# -*- coding: utf-8 -*-
"""Agenda de endereços (presets) para agilizar preenchimento.

- DELIVERY_PRESETS: preenche os campos de entrega (destinatário/telefone/endereço/cidade/estado/CEP).
- SENDER_PRESETS: exibido como "remetente sugerido" (não é salvo no banco por padrão).

Para adicionar/editar locais: edite este arquivo.
"""

DELIVERY_PRESETS = {
  "Camaçari": {
"destinatario": "Rafael Barros",
"telefone": "",
"endereco": "RUA BENZENO, S/N - PÓLO PETROQUÍMICO DE CAMAÇARI",
"cidade": "Camaçari",
"estado": "BA",
"cep": "42816-120",
"observacoes": "TAG – TRANSPORTADORA ASSOCIADA DE GÁS / ENGIE\nCentro de gasto: 01020504202"
  },
  "Jaboatão": {
"destinatario": "DENILSON SOUZA",
"telefone": "",
"endereco": "ROD BR 232, KM 15,4\nMANASSU",
"cidade": "Jaboatão dos Guararapes",
"estado": "PE",
"cep": "54130-340",
"observacoes": "ENGIE Soluções de Operação e Manutenção."
  },
  "Manaus": {
"destinatario": "",
"telefone": "",
"endereco": "Rua Rio Quixito, S/N – Distrito Industrial I",
"cidade": "Manaus",
"estado": "AM",
"cep": "69075-831",
"observacoes": "ENGIE Soluções de Operação e Manutenção"
  },
  "Mossoró": {
"destinatario": "José Henrique",
"telefone": "",
"endereco": "AV. INDUSTRIAL DEHUEL VIEIRA DINIZ, BR 304\nSanta Júlia\nCAIXA POSTAL 562",
"cidade": "Mossoró",
"estado": "RN",
"cep": "59623-300",
"observacoes": "ENGIE Soluções de Operação e Manutenção"
  },
  "Pilar": {
"destinatario": "CAMILA ELLER MONTEIRO",
"telefone": "",
"endereco": "FAZENDA VILA NOVA, S/N - ZONA RURAL\nCaixa postal: 21 - Agência Correios Pilar-AL\nCódigo da Agência: 04300530\nCEP: 57150-970",
"cidade": "Pilar",
"estado": "AL",
"cep": "57150-000",
"observacoes": "ENGIE Soluções de Operação e Manutenção"
  },
  "Vitória": {
"destinatario": "Alex Sandro",
"telefone": "",
"endereco": "Av. Duzentos, s/n, Quadra 03, Lote 01\nTerminal Industrial e Multimodal da Serra (TIMS)",
"cidade": "Serra",
"estado": "ES",
"cep": "29161-418",
"observacoes": "ENGIE Soluções de Operação e Manutenção"
  },
  "Itabuna": {
"destinatario": "",
"telefone": "",
"endereco": "RODOVIA BA 415 – KM 38 – DISTRITO INDUSTRIAL S/N  - FERRADAS\nPRÓXIMO A BAHIA GÁS",
"cidade": "Itabuna",
"estado": "BA",
"cep": "45602-625",
"observacoes": "ENGIE Soluções de Operação e Manutenção"
  },
  "Catu": {
"destinatario": "TATIANA CORREIA",
"telefone": "",
"endereco": "RODOVIA BA 507, S/N – FAZENDA HAROLDINA, ÁREA INDUSTRIAL DE SANTIAGO\nCAIXA POSTAL 59 - POJUCA - BA",
"cidade": "Pojuca",
"estado": "BA",
"cep": "48120-000",
"observacoes": "CG: 01020504102"
  },
  "Juaruna": {
"destinatario": "",
"telefone": "",
"endereco": "Estação de Compressão de Juaruna, SN, Lado esquerdo do Rio Urucu Km 140",
"cidade": "Coari",
"estado": "AM",
"cep": "69460-000",
"observacoes": ""
  },
  "Coari": {
"destinatario": "",
"telefone": "",
"endereco": "KM 152, do Gasoduto Urucu, S/N – Zona Rural",
"cidade": "Coari",
"estado": "AM",
"cep": "69460-000",
"observacoes": "ENGIE Soluções de Operação e Manutenção"
  },
  "Aracruz": {
"destinatario": "",
"telefone": "",
"endereco": "Rua Quintino Loureiro, 465 - Centro\nCAIXA POSTAL: 03",
"cidade": "Aracruz",
"estado": "ES",
"cep": "29190-970",
"observacoes": "ENGIE SOLUÇÕES DE OPERAÇÃO E MANUTENÇÃO"
  },
  "Piúma": {
"destinatario": "",
"telefone": "",
"endereco": "ESTRADA VELHA DE PIÚMA, KM 205, FAZENDA NOSSA SENHORA DAS GRAÇAS\nCAIXA POSTAL 98",
"cidade": "Piúma",
"estado": "ES",
"cep": "29285-000",
"observacoes": "ENGIE SOLUÇÕES DE OPERAÇÃO E MANUTENÇÃO"
  },
  "Prado": {
"destinatario": "",
"telefone": "",
"endereco": "FAZENDA ZELITO II, Rodovia BA 469, KM 9\nALCOBAÇA – BA, KM 682 DO GASODUTO GASCAC\nCaixa Postal: 48",
"cidade": "Alcobaça",
"estado": "BA",
"cep": "45910-000",
"observacoes": "ENGIE SOLUÇÕES DE OPERAÇÃO E MANUTENÇÃO"
  },
  "Maracanaú": {
"destinatario": "JULIANA DE GOES TEIXEIRA",
"telefone": "",
"endereco": "AVENIDA QUARTO ANEL VIARIO, S/N - DISTRITO INDUSTRIAL\nReferência: Antiga base da Transpetro",
"cidade": "Maracanaú",
"estado": "CE",
"cep": "61925-215",
"observacoes": "ENGIE SOLUÇÕES DE OPERAÇÃO E MANUTENÇÃO"
  },
  "Atalaia": {
"destinatario": "Ivone de Andrade",
"telefone": "",
"endereco": "AVENIDA MELICIO MACHADO, 1545 - TECARMO - ARUANA",
"cidade": "Aracaju",
"estado": "SE",
"cep": "49037-445",
"observacoes": ""
  },
  "João Pessoa": {
"destinatario": "EVA NASCIMENTO",
"telefone": "",
"endereco": "AVENIDA ESTEVAO GERSON CARNEIRO DA CUNHA, 145\nÁGUA FRIA\nFeC LOCAÇÃO EMPRESARIAL",
"cidade": "João Pessoa",
"estado": "PB",
"cep": "58073-020",
"observacoes": ""
  },
  "Macaíba": {
"destinatario": "ANGELA CAROLINA LOPES DA SILVA",
"telefone": "",
"endereco": "ROD RN-160, SITIO PERI PERI - ZONA RURAL\nCAIXA POSTAL: 90",
"cidade": "Macaíba",
"estado": "RN",
"cep": "59280-970",
"observacoes": ""
  },
  "Florianópolis": {
"destinatario": "LUIZ PAMPLONA",
"telefone": "",
"endereco": "Rua Paschoal Apostolo Pística, 5064 – MEZ – Agronômica",
"cidade": "Florianópolis",
"estado": "SC",
"cep": "88025-255",
"observacoes": "ENGIE SOLUCOES DE ILUMINACAO PUBLICA LTDA"
  },
  "São Paulo": {
"destinatario": "Hugo ARAUJO",
"telefone": "",
"endereco": "Av. Engenheiro Luís Carlos Berrini, 716 - 2º andar\nMonções",
"cidade": "São Paulo",
"estado": "SP",
"cep": "04571-926",
"observacoes": "ENGIE BRASIL SOLUCOES INTEGRADAS PART LTDA"
  },
  "Uberlândia": {
"destinatario": "Marcia Anacleto",
"telefone": "",
"endereco": "Rua Pedro Quirino - Marta Helena, 925",
"cidade": "Uberlândia",
"estado": "MG",
"cep": "38402-293",
"observacoes": "ENGIE BRASIL SOLUÇOES PARTICIPAÇÕES LTDA"
  },
  "Porto Alegre": {
"destinatario": "Gabriel Camargo Alves",
"telefone": "",
"endereco": "R. Dom Pedro II, Higienópolis, 978",
"cidade": "Porto Alegre",
"estado": "RS",
"cep": "90550-141",
"observacoes": "ENGIE CONSULTORIA E GESTAO DE ENERGIA LTDA"
  },
  "Cuiabá": {
"destinatario": "",
"telefone": "",
"endereco": "Av. Jose Monteiro de Figueiredo, 500 - Duque de Caxias",
"cidade": "Cuiabá",
"estado": "MT",
"cep": "78043-300",
"observacoes": "ENGIE BRASIL SOLUÇOES INTEGRADAS PART"
  },
  "Brasília": {
"destinatario": "JESSICA FRANCO BARROS",
"telefone": "",
"endereco": "Rod. Pres. Juscelino Kubitschek, s/n\nLago Sul",
"cidade": "Brasília",
"estado": "DF",
"cep": "71608-900",
"observacoes": "ENGIE BRASIL SERVICOS AEROPORTUARIOS LTDA"
  },
  "ROP": {
"destinatario": "",
"telefone": "",
"endereco": "Rua José Augusto Rodrigues, 175\nJacarepaguá",
"cidade": "Rio de Janeiro",
"estado": "RJ",
"cep": "22775-047",
"observacoes": "Engie Brasil Soluções Integradas LTDA"
  },
  "PPP Curitiba PR": {
"destinatario": "",
"telefone": "",
"endereco": "R. William Booth, 2349 - Boqueirão",
"cidade": "Curitiba",
"estado": "PR",
"cep": "81730-080",
"observacoes": "ENGIE BRASIL SOLUÇOES PARTICIPAÇÕES LTDA"
  },
  "Rio Grande do Sul RS": {
"destinatario": "EDSON BRAZ - TI25040478R01",
"telefone": "",
"endereco": "Rua Bento Gonçalves - SALA 02\n1294 - Lajeado - RS",
"cidade": "Lajeado",
"estado": "RS",
"cep": "95900-026",
"observacoes": "ENGIE BRASIL SOLUÇÕES INTEGRADAS"
  },
  "PPP Petrolina": {
"destinatario": "Gabriela Silva",
"telefone": "",
"endereco": "Avenida Filadélfia, 190\nPortal da Cidade",
"cidade": "Petrolina",
"estado": "PE",
"cep": "56313-305",
"observacoes": "ENGIE PPP Petrolina PE"
  },
  "Fortaleza - 1": {
"destinatario": "",
"telefone": "",
"endereco": "Avenida Senador Carlos Jereissati, 3000 - Setor Locadoras\nBairro: Serrinha\nPonto de referência: Em frente o antigo prédio da locadora Unidas.",
"cidade": "Fortaleza",
"estado": "CE",
"cep": "60741-900",
"observacoes": "ENGIE BRASIL SERVIÇOS AEROPORTUARIOS LTDA"
  },
  "Fortaleza - 2": {
"destinatario": "",
"telefone": "",
"endereco": "Av. Senador Carlos Jereissati, 3.000 - PPD SALA 651 - Serrinha.",
"cidade": "Fortaleza",
"estado": "CE",
"cep": "60860-125",
"observacoes": "ENGIE BRASIL SERVIÇOS AEROPORTUARIOS LTDA"
  }
}

SENDER_PRESETS = {
  "ENGIE SOM (RJ)": {
"nome": "ENGIE Soluções de Operação e Manutenção.",
"endereco": "AV PRESIDENTE WILSON, 231 – 21° Andar\nCENTRO – RIO DE JANEIRO – RJ",
"cidade": "Rio de Janeiro",
"estado": "RJ",
"cep": "20030-905"
  },
  "ENGIE BRASIL (RJ)": {
"nome": "ENGIE BRASIL SOLUÇÕES PARTICIPAÇÕES LTDA",
"endereco": "AV PRESIDENTE WILSON, 231 – 21° Andar\nCENTRO – RIO DE JANEIRO – RJ",
"cidade": "Rio de Janeiro",
"estado": "RJ",
"cep": "20030-905"
  }
}