from azure.identity         import ClientSecretCredential
from azure.mgmt.consumption import ConsumptionManagementClient
from models.app                import App
from models.configuracoes      import Config
from models.database           import DataBase
from models.logger             import Log
                                            
import pandas as pd
import numpy  as np
import requests
import time
import hashlib
from datetime import datetime, timedelta

                                            
app = App()
cfg = Config()
dbo = DataBase()
log = Log()
dbkey = app.key_db('fin')
                                            
class finops_azure():

    # =========================
    # 1 - LISTAR SUBSCRIPTIONS
    # =========================

    def listar_subscriptions(self):
        log.logmessage("[AZURE] Listando subscriptions...")
        
        credential = ClientSecretCredential(
            tenant_id     = app.api_azure()['tenant_id'],
            client_id     = app.api_azure()['client_id'],
            client_secret = app.api_azure()['secret']
        )
        
        token = credential.get_token("https://management.azure.com/.default").token
        
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        url = "https://management.azure.com/subscriptions?api-version=2019-11-01"
        
        subs = []
        
        while url:
            response = requests.get(url, headers=headers)
            
            if response.status_code != 200:
                log.logmessage("[ERRO SUBSCRIPTIONS]", response.text)
                return []
            
            data = response.json()
            
            #print(data)  # mantém seu debug
            
            for item in data.get("value", []):
                sub_id = item.get("subscriptionId")
                if sub_id:
                    subs.append(sub_id)
            
            # trata paginação
            url = data.get("nextLink")
        
        log.logmessage(f"[AZURE] {len(subs)} subscriptions encontradas")

        #subs = ['6014647f-0453-4dc1-87d7-73ffb84c1987','8f54d30a-ea8f-4332-a184-58fd4a4481c8']
        
        return subs
        
    # =========================
    # 2 - PROCESSAR E GERAR DF
    # =========================
    def processar_dados(self, start_date, end_date):
        log.logmessage("[PROCESSAMENTO INICIADO]")
    
        dados_total = []
    
        credential = ClientSecretCredential(
            tenant_id     = app.api_azure()['tenant_id'],
            client_id     = app.api_azure()['client_id'],
            client_secret = app.api_azure()['secret']
        )
            
        subscriptions = self.listar_subscriptions()

        #subscriptions = ['6014647f-0453-4dc1-87d7-73ffb84c1987']

    
        for subscription_id in subscriptions:
            log.logmessage(f"[PROCESSANDO] Sub: {subscription_id}")
            
            try:
                client = ConsumptionManagementClient(credential, subscription_id)
                scope = f"/subscriptions/{subscription_id}"
                
                filter_str = f"properties/usageStart ge '{start_date}' and properties/usageEnd lt '{end_date}'"
                    
                for item in client.usage_details.list(scope=scope, filter=filter_str):
                    d = item.as_dict()
                    d["subscription_id"] = subscription_id
                    
                    dados_total.append(d)
                    
                log.logmessage(f"[SUCESSO] Sub {subscription_id}")
                
            except Exception as e:
                log.logmessage(f"[ERRO] Sub {subscription_id}: {e}")
    
        log.logmessage("[GERANDO DATAFRAME]")
    
        df = pd.json_normalize(dados_total)

        df.to_excel('completo.xlsx',index=False) ########################################################################## salvando arquivo
    
        # remover colunas que começam com TAG
        # df = df.loc[:, ~df.columns.str.startswith('TAG')]
    
        # limpar nomes das colunas TAG (remove espaço e _)
        df.columns = [col.replace(" ", "").replace("_", "") for col in df.columns]
    
        # padronizar nomes
        df.columns = [cfg.cfg_config_header(col) for col in df.columns]
    
        # remover duplicadas
        df = df.loc[:, ~df.columns.duplicated()]
        #df.drop(columns=['ID'], inplace=True, errors='ignore')
    
        # identificar colunas TAG
        colunas_tag = [col for col in df.columns if col.startswith('TAG')]
        
        # normalização de nomes (mapear variações)
        mapeamento_tags = {
            'TAGSAMBIENTE': 'AMBIENTE',
            'TAGSAMBEINTE': 'AMBIENTE',
            'TAGSAMBINTE': 'AMBIENTE',
            'TAGSAMBIETE': 'AMBIENTE',
            'TAGSENVIRONMENT': 'AMBIENTE',
            'TAGSXAMBIENTE': 'AMBIENTE',

            'TAGSPROJETO': 'PROJETO',
            'TAGSPROJECT': 'PROJETO',
            'TAGSXPROJETO': 'PROJETO',
            'TAGSNOMEDOPROJETO': 'PROJETO',
            'TAGSPOJETO': 'PROJETO',
            'TAGSSUBPROJETO':'SUBPROJETO',

            'TAGSCRIADOR':'CRIADOR',
            'TAGSCREATEDBY':'CRIADOR',

            'TAGSSERVICO':'SERVICO',

            'TAGSCLIENTE': 'CLIENTE',
            'TAGSNOMECLIENTE': 'CLIENTE',
            'TAGSXCLIENTE': 'CLIENTE',

            'TAGSDEPARTAMENTO': 'DEPARTAMENTO',

            'TAGSRESPONSAVEL': 'RESPONSAVEL',
            'TAGSSOLICITADOPOR': 'RESPONSAVEL',
            'TAGSAUTORIZADOPOR': 'RESPONSAVEL',
            'TAGSCRIADOPOR': 'RESPONSAVEL',
            'TAGSCREATOR': 'RESPONSAVEL',

            'TAGSGMU': 'GMUD',
            'TAGSGMUD': 'GMUD',

            'TAGSAPLICACAO': 'APLICACAO',
            'TAGSDESCRIPTION':'DESCRICAO',
            'TAGSVALOR':'VALOR'
        }

        # criar colunas finais (sem erro se não existirem)
        colunas_finais = set(mapeamento_tags.values())
        for col in colunas_finais:
            if col not in df.columns:
                df[col] = None

        # controle de uso do dicionário
        tags_encontradas = set()
        
        # preencher valores das TAGs normalizadas
        for col in colunas_tag:
            tag_normalizada = mapeamento_tags.get(col, None)
            
            if tag_normalizada:
                df[tag_normalizada] = df[tag_normalizada].fillna(df[col])
                tags_encontradas.add(col)
            else:
                log.logmessage(f"[TAG IGNORADA] {col} não está no mapeamento")

        # logar tags do dicionário que não apareceram no dataframe
        for tag in mapeamento_tags.keys():
            if tag not in colunas_tag:
                log.logmessage(f"[TAG NÃO ENCONTRADA] {tag}")

        # remover colunas TAG originais
        df = df.drop(columns=colunas_tag)
        
        log.logmessage(f"[FINALIZADO] {len(df)} registros")
        
        return df
        
    def __init__(self):
        self.listar_subscriptions()
        data_hoje = datetime.now()
        data_ontem = data_hoje - timedelta(days=1)
        
        # últimos 10 dias contando com ontem
        for i in range(1):
            data_processar = data_ontem - timedelta(days=i)
    
            data_str = data_processar.strftime('%Y-%m-%d')
            data_str_fim = (data_processar + timedelta(days=0)).strftime('%Y-%m-%d')
        
            log.logmessage(f"[REPROCESSANDO DIA] {data_str} ATÉ {data_str_fim}")
        
            df_sem_tag = self.processar_dados(data_str, data_str_fim)
        
            if df_sem_tag.empty:
                log.logmessage(f"[SEM DADOS] {data_str}")
                continue

            df_sem_tag.to_excel('testinho.xlsx',index=False)
#            dbo.conecatar(dbkey)        
#           
#            df2_sem_tag = df_sem_tag[['DATE']].drop_duplicates()
#    
#            #df_sem_tag = dbo.sincronizar_colunas(tabela='azure_billing_cost',df= df_sem_tag)
#            dbo.organizar_df                    (tabela='azure_billing_cost',df=df_sem_tag)
#            dbo.validar_dados                   (tabela='azure_billing_cost',df=df_sem_tag)
#    
#            df_sem_tag = df_sem_tag.replace({np.nan: None})
#    
#            df_sem_tag = df_sem_tag.where(pd.notnull(df_sem_tag), None)
#    
#            dbo.deletar_informacoes(tabela='azure_billing_cost',df=df2_sem_tag)
#    
#            dbo.inserir_df(tabela='azure_billing_cost',df=df_sem_tag)
#        
#            dbo.desconectar()

if __name__ == '__main__':
    finops_azure()