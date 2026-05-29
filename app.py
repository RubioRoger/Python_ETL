"""
==============================================================================
Módulo: app.py
Descrição:
    Este módulo centraliza a leitura e recuperação de valores do arquivo
    App.config em XML, utilizado para armazenar chaves, conexões e credenciais.

    Funcionalidades principais:
    - Leitura de credenciais do SharePoint
    - Leitura de conexões com bancos de dados
    - Leitura de dados para integração com vCenter, AWS e ONTAP
    - Acesso a listas e parâmetros diversos configurados externamente

------------------------------------------------------------------------------
Exemplo de uso:

    from models.app import App

    app = App()

    # Buscar credenciais do SharePoint
    creds = app.api_key_sharepoint()

    # Recuperar string de conexão do banco de produção
    conn = app.db_key("prod")

    # Obter usuário e senha para SharePoint (via apelido)
    user, pwd = app.slm_email("slm")

    # Buscar informações de conexão com AWS
    aws = app.api_key_aws("aws_account_01")

------------------------------------------------------------------------------
Dependências:
    - xml.etree.ElementTree (módulo nativo do Python)

==============================================================================
"""

import xml.etree.ElementTree as ET

class App:
    def __init__(self):
        """
        Inicializa o App carregando o arquivo App.config.
        Tenta dois caminhos possíveis (ambiente DEV ou PROD).

        """
        caminho_prod = r"D:\Metricas\Scripts\SQLServer\Release\App.config"
        caminho2_dev = r"C:\Metricas\Scripts\SQLServer\Release\App.config"

        try:
            self.root = ET.parse(caminho_prod).getroot()
        except (FileNotFoundError, ET.ParseError):
            self.root = ET.parse(caminho2_dev).getroot()

    def key_sharepoint(self):
        """
        Retorna as credenciais para conexão com o SharePoint:
        - client_id
        - client_secret
        - site_url
        - site_url_fin (opcional)
        """
        keys_obrigatorias  = ["client_id_sharepoint", "client_secret_sharepoint", "site_url_sharepoint"]
        keys_opcionais     = ["site_url_sharepoint_fin"]
        result = {}
    
        for key in keys_obrigatorias:
            node = self.root.find(f".//add[@key='{key}']")
            if node is None:
                raise ValueError(f"Chave '{key}' não encontrada no App.config")
            result[key] = node.get("value")
    
        for key in keys_opcionais:
            node = self.root.find(f".//add[@key='{key}']")
            result[key] = node.get("value") if node is not None else None
    
        return result

    def key_oem(self):
        """
        Retorna as credenciais para conexão com o OEM:
        - ip
        - user
        - password
        - port
        """
        keys = ["oem"]
        result = {}
    
        for key in keys:
            node = self.root.find(f".//add[@key='{key}']")
            
            if node is None:
                raise ValueError(f"Chave '{key}' não encontrada no App.config")
            
            # Extrair as informações desejadas
            result['ip'] = node.get("ip")
            result['user'] = node.get("user")  # Adicionando o 'user'
            result['password'] = node.get("password")  # Adicionando o 'password'
            result['port'] = node.get("port")  # Adicionando o 'port'
    
        return result

    def key_oci(self):
        """
        Retorna lista de credenciais OCI, uma por tenancy configurada em lista_oci.
        Cada item: region, fingerprint, private_key_content, name, user_ocid, tenancy_ocid.
        """
        result_list = []
    
        # Bloco base: region, fingerprint e chave privada
        node_base = self.root.find(".//add[@key='oci']")
        if node_base is None:
            raise ValueError("Chave 'oci' não encontrada no App.config")
    
        region      = node_base.get("region")
        fingerprint = node_base.get("fingerprint")
    
        # ⚠️ Garante quebras de linha reais — XML pode remover os \n da chave RSA
        raw_key = node_base.get("private_key_content", "")
        private_key_content = raw_key.strip().replace("\\n", "\n")
    
        # Lista de tenancies (ex: "oci_prodespexadr,oci_prodespoci")
        node_lista = self.root.find(".//add[@key='lista_oci']")
        if node_lista is None:
            raise ValueError("Chave 'lista_oci' não encontrada no App.config")
    
        chaves = [c.strip() for c in node_lista.get("lista", "").split(",") if c.strip()]
        if not chaves:
            raise ValueError("Atributo 'lista' vazio em lista_oci")
    
        for chave in chaves:
            node_oci = self.root.find(f".//add[@key='{chave}']")
            if node_oci is None:
                raise ValueError(f"Perfil OCI '{chave}' não encontrado no App.config")
    
            result_list.append({
                "region":              region,
                "fingerprint":         fingerprint,
                "private_key_content": private_key_content,
                "name":                node_oci.get("name"),
                "user_ocid":           node_oci.get("user_ocid"),
                "tenancy_ocid":        node_oci.get("tenancy_ocid"),
            })
    
        return result_list

    def vmware_list(self):
        """
        Retorna a lista de hosts vCenter configurados no App.config.
        """
        node = self.root.find(f".//add[@key='lista_vcenter']")
        if node is None:
            raise ValueError("Chave 'lista_vcenter' não encontrada no App.config")
        return node.get('lista')

    def aws_list(self):
        """
        Retorna a lista de contas AWS configuradas no App.config.
        """
        node = self.root.find(f".//add[@key='lista_aws']")
        if node is None:
            raise ValueError("Chave 'lista_aws' não encontrada no App.config")
        return node.get('lista')

    def key_db(self, nick=None):
        """
        Retorna a string de conexão com o banco de dados conforme apelido:
        - 'dev'  → conexão de desenvolvimento
        - 'prod' → conexão de produção
        - 'cap'  → conexão de capacidade (produção específica)

        Parâmetros:
            nick (str): Apelido da conexão (dev, prod, cap, fin)

        Retorna:
            str: String de conexão do banco de dados
        """
        mapa = {
            "dev": "DBconnectionString_Dev",
            "prod": "DBconnectionString_Prod",
            "cap": "DBconnectionString_Prod_Cap",
            "fin": "DBconnectionString_Prod_finops"
        }

        if nick not in mapa:
            raise ValueError(f"Apelido de banco '{nick}' inválido. Use: dev, prod, cap ou fin.")

        key = mapa[nick]
        node = self.root.find(f".//add[@key='{key}']")
        if node is None:
            raise ValueError(f"Chave '{key}' não encontrada no App.config")
        return node.get('value')

    def key_vcenter(self, chave):
        """
        Retorna informações de conexão com o vCenter.

        Parâmetros:
            chave (str): Nome da chave no App.config

        Retorna:
            dict: Informações como URL, usuário, senha, IP e porta
        """
        node = self.root.find(f".//add[@key='{chave}']")
        if node is None:
            raise ValueError(f"Chave '{chave}' não encontrada no App.config")

        return {
            "url": node.get('url_session'),
            "user": node.get('user'),
            "password": node.get('psw'),
            "port": node.get('host_port'),
            "ip": node.get('host_ip')
        }

    def key_ontap(self):
        """
        Retorna as credenciais para acesso ao ONTAP (armazenamento NetApp).

        Retorna:
            dict: ip, usuário, senha
        """
        node = self.root.find(".//add[@key='ontap']")
        if node is None:
            raise ValueError("Chave 'ontap' não encontrada no App.config")
        return {
            "ip": node.get('ip'),
            "user": node.get('user'),
            "password": node.get('password'),
        }

    def key_aws(self, chave):
        """
        Retorna credenciais de uma conta AWS.

        Parâmetros:
            chave (str): Nome da chave no App.config

        Retorna:
            dict: AWS key_id e access_key
        """
        node = self.root.find(f".//add[@key='{chave}']")
        if node is None:
            raise ValueError("Chave 'aws' não encontrada no App.config")
        return {
            "key_id": node.get('key_id'),
            "access_key": node.get('access_key'),
        }


    def api_ibm_dipol(self, chave = 'ibm_dipol'):
        """
        Retorna credenciais de uma conta IBM.

        Parâmetros:
            chave (str): Nome da chave no App.config

        Retorna:
            dict: IBM api_key e api_id
        """
        node = self.root.find(f".//add[@key='{chave}']")
        if node is None:
            raise ValueError("Chave 'IBM' não encontrada no APLICACAO.config")
        return {
            "api_key": node.get('api_key'),
            "api_id": node.get('api_id'),
        }
    
    def api_ibm_sggd(self, chave = 'ibm_sggd'):
        """
        Retorna credenciais de uma conta IBM.

        Parâmetros:
            chave (str): Nome da chave no App.config

        Retorna:
            dict: IBM api_key e api_id
        """
        node = self.root.find(f".//add[@key='{chave}']")
        if node is None:
            raise ValueError("Chave 'IBM' não encontrada no APLICACAO.config")
        return {
            "api_key": node.get('api_key'),
            "api_id": node.get('api_id'),
        }
    
    def api_azure(self, chave = 'az_billing'):
        """
        Retorna credenciais de uma conta Azure.

        Parâmetros:
            chave (str): Nome da chave no App.config

        Retorna:
            dict: azure api_key e api_id
        """
        node = self.root.find(f".//add[@key='{chave}']")
        if node is None:
            raise ValueError("Chave 'Azure' não encontrada no APLICACAO.config")
        return {
            "user": node.get('user'),
            "client_id": node.get('client_id'),
            "tenant_id": node.get('tenant_id'),
            "secret": node.get('secret'),
        }