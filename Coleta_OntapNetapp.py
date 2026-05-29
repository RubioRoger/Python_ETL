# pyinstaller --onefile --noconsole ontap.py
import warnings
warnings.filterwarnings("ignore")

# BIBLIOTECAS UTILIZADAS
import requests
from   datetime             import datetime
from   requests.auth        import HTTPBasicAuth
import numpy                as np
import pandas               as pd

# COLETANDO FUNCIONALIDADES DO MODULO MODELS
from   models.tabelas       import Ontap      # TABELAS DO BANCO DE DADOS
from   models.configuracoes import Config     # CONFIGURACOES DAS INFORMACOES
from   models.app           import App        # COLETA STRINGS DO ARQUIVO APP.CONFIG
from   models.database      import DataBase   # REALIZA OPERACOES NO BANCO DE DADOS
from   models.logger        import Log        # CONFIGURACOES DO ARQUIVO DE LOG
from   models.sharepoint    import SharePoint # ENVIA ARQUIVOS PARA O SHAREPOINT

tab          = Ontap()
lg           = Log()
cfg          = Config()
db           = DataBase()
ap           = App()
db_key       = ap.key_db('cap')

# VARIAVEIS DO AMBIENTE
st           = datetime.now()
data_file    = st.strftime("%Y-%m-%d_%H_00_00")
hora         = st.strftime("%H:00:00")
data_ref     = st.strftime("%Y-%m-%d")
vcenter      = 'storage_ontap'

# CLASSE DE EXTRACAO E INSERCAO DE INFORMACOES
class coletaNetapp():

# EXTRACAO DAS METRICAS DOS VOLUMES
    def extrair_volumes(self):

        url_base = f"https://{self.ip}/api/storage/volumes"
        lg.logmessage(f'Conectando {vcenter}')
    
        try:
            lg.logmessage(f"Conectando ao {vcenter} em {self.ip}...")
    
            # Primeira requisição: lista de volumes com UUID e nome
            response = requests.get(url_base, auth=HTTPBasicAuth(self.us, self.ps), verify=False, timeout=10)
    
            if response.status_code != 200:
                lg.logmessage(response.status_code)
                raise Exception(f"Erro na requisição: {response.status_code} - {response.text}")
    
            data = response.json()
            vol_data = []
    
            for vol in data.get('records', []):
                uuid = vol.get('uuid')
                name = vol.get('name')
    
                if not uuid:
                    continue
    
                # Segunda requisição: detalhes do volume pelo UUID
                url_detalhe = f"{url_base}/{uuid}"
                resp_detalhe = requests.get(url_detalhe, auth=HTTPBasicAuth(self.us, self.ps), verify=False, timeout=10)
    
                if resp_detalhe.status_code != 200:
                    lg.logmessage(f"Erro ao buscar detalhes do volume {name} ({uuid}): {resp_detalhe.status_code}")
                    continue
    
                detalhe = resp_detalhe.json()
                space = detalhe.get('space', {})
    
                size = space.get('size')
                available = space.get('available')
                used = space.get('used')
    
                vol_info = {
                    'data_coleta'    : data_ref,
                    'hora_coleta'    : hora,
                    'volume'         : name,
                    'storage_use'       : used / (1024**4) if size else None,
                    'storage_disp'      : (used+available) / (1024**4) if available else None,
                    'percent_used'        : used/(used+available)
                }
    
                vol_data.append(vol_info)
    
            # Monta DataFrame final
            df = pd.DataFrame(vol_data)
            df['id_tab'] = df['data_coleta'].astype(str) + df['hora_coleta'].astype(str) + df['volume'].astype(str)
            df['id_tab'] = df['id_tab'].str.replace('-', '').str.replace(':', '')
    
            file_name = f'outputs\\ontap_volumes_{data_file}.xlsx'
            df.to_excel(file_name, index=False)
            sha          = SharePoint()
            try:
                sha.exportar_csv_com_data(df,f"ontap_volumes",data_file,"Documents/etl_capacity/diorama/ontap")
            except: Log.logmessage(F'[ERRO] : NÃO FOI POSSIVEL SALVAR O ARQUIVO Documents/etl_capacity/diorama/ontap/ontap_volumes_{data_file}')
            
            lg.logmessage("Coleta concluída com sucesso.")
    
        except Exception as e:
            lg.logmessage(f"Erro ao conectar ou buscar volumes: {e}")
            df = pd.DataFrame()
    
        finally:
            lg.logmessage("Processo concluído.")
    
        return df

# EXTRACAO DAS METRICAS DOS CLUSTERS
    def extrair_cluster(self):
    
        url = f"https://{self.ip}/api/storage/cluster"
        lg.logmessage(f'Conectando {vcenter} (cluster)')
    
        try:
            lg.logmessage(f"Conectando ao {vcenter} em {self.ip}...")
    
            response = requests.get(url, auth=HTTPBasicAuth(self.us, self.ps), verify=False, timeout=10)
    
            if response.status_code != 200:
                lg.logmessage(response.status_code)
                raise Exception(f"Erro na requisição: {response.status_code} - {response.text}")
    
            dados = response.json()
            block = dados.get("block_storage", {})
    
            espaco_total = block.get("size")
            espaco_disponivel = block.get("available")
            espaco_utilizado = block.get("used")
    
            percentual_uso = round((espaco_utilizado / espaco_total) * 100, 1) if espaco_utilizado and espaco_total else None
    
            agg_info = {
                'data_coleta'           : data_ref,
                'hora_coleta'           : hora,
                'cluster'               : '10.148.9.170',
                'storage_use'              : espaco_utilizado / (1024**4) if espaco_utilizado else None,
                'storage_disp'             : (espaco_disponivel+espaco_utilizado) / (1024**4) if espaco_total else None,
                'percent_used'          : percentual_uso
            }
    
            df = pd.DataFrame([agg_info])
            df['id_tab'] = df['data_coleta'].astype(str) + df['hora_coleta'].astype(str) + df['cluster'].astype(str)
            df['id_tab'] = df['id_tab'].str.replace('-', '').str.replace(':', '').str.replace('.', '')
    
            file_name = f'outputs\\ontap_cluster_{data_file}.xlsx'
            df.to_excel(file_name, index=False)
            sha          = SharePoint()
            try:
                #cf.cfg_proxy()
                sha.exportar_csv_com_data(df,f"ontap_cluster",data_file,"Documents/etl_capacity/diorama/ontap")

            except: Log.logmessage(f'[ERRO] : NÃO FOI POSSIVEL SALVAR O ARQUIVO Documents/etl_capacity/diorama/ontap/ontap_cluster{data_file}')
            
            lg.logmessage("Coleta (cluster) concluída com sucesso.")
    
        except Exception as e:
            lg.logmessage(f"Erro ao conectar ou buscar cluster: {e}")
            df = pd.DataFrame()
    
        finally:
            lg.logmessage("Processo (cluster) concluído.")
    
        return df

# EXTRACAO DAS METRICAS DOS AGGREGATES
    def extrair_aggregate(self):
    
        url_base = f"https://{self.ip}/api/storage/aggregates"
        lg.logmessage(f'Conectando {vcenter} (aggregates)')
    
        try:
            lg.logmessage(f"Conectando ao {vcenter} em {self.ip}...")
    
            response = requests.get(url_base, auth=HTTPBasicAuth(self.us, self.ps), verify=False, timeout=10)
    
            if response.status_code != 200:
                lg.logmessage(response.status_code)
                raise Exception(f"Erro na requisição: {response.status_code} - {response.text}")
    
            dados = response.json()
            registros = dados.get("records", [])
    
            lista_info = []
    
            for registro in registros:
                uuid = registro.get("uuid")
                nome_aggr = registro.get("name")
    
                url_aggr = f"{url_base}/{uuid}"

                resp_aggr = requests.get(url_aggr, auth=HTTPBasicAuth(self.us, self.ps), verify=False, timeout=10)
    
                if resp_aggr.status_code != 200:
                    lg.logmessage(f"Erro ao acessar {url_aggr}: {resp_aggr.status_code}")
                    continue
    
                dados_aggr = resp_aggr.json()
                block = dados_aggr.get("space", {}).get("block_storage", {})
    
                size = block.get("size")
                available = block.get("available")
                used = block.get("used")
                used_percent = block.get("used_percent")
    
                info = {
                    'data_coleta'   : data_ref,
                    'hora_coleta'   : hora,
                    'aggregate'     : nome_aggr,
                    'storage_disp'  : (used+available) / (1024**4) if size else None,
                    'storage_use'   : used / (1024**4) if used else None,
                    'percent_used'  : used_percent,
                }
    
                lista_info.append(info)
    
            df = pd.DataFrame(lista_info)
            df['id_tab'] = df['data_coleta'].astype(str) + df['hora_coleta'].astype(str) + df['aggregate'].astype(str)
            df['id_tab'] = df['id_tab'].str.replace('-', '').str.replace(':', '')
    
            file_name = f'outputs\\ontap_aggregates_{data_file}.xlsx'
            df.to_excel(file_name, index=False)
            sha          = SharePoint()
            try:
                sha.exportar_csv_com_data(df,f"ontap_aggregates",data_file,"Documents/etl_capacity/diorama/ontap")
            except: Log.logmessage(F'[ERRO] : NÃO FOI POSSIVEL SALVAR O ARQUIVO Documents/etl_capacity/diorama/ontap/ontap_aggregates_{data_file}')

            lg.logmessage("Coleta (aggregates) concluída com sucesso.")
    
        except Exception as e:
            lg.logmessage(f"Erro ao conectar ou buscar aggregates: {e}")
            df = pd.DataFrame()
    
        finally:
            lg.logmessage("Processo (aggregates) concluído.")
    
        return df

# EXTRACAO DAS METRICAS DOS SMV
    def extrair_svm(self):

        url_base = f"https://{self.ip}/api/storage/volumes"
        lg.logmessage(f'Conectando {vcenter}')
    
        try:
            lg.logmessage(f"Conectando ao {vcenter} em {self.ip}...")
    
            # Primeira requisição: lista de volumes
            response = requests.get(url_base, auth=HTTPBasicAuth(self.us, self.ps), verify=False, timeout=10)
    
            if response.status_code != 200:
                lg.logmessage(response.status_code)
                raise Exception(f"Erro na requisição: {response.status_code} - {response.text}")
    
            data = response.json()
    
            total_size = 0
            total_available = 0
            total_used = 0
            uuid_ref = None
    
            for vol in data.get('records', []):
                uuid = vol.get('uuid')
                if not uuid:
                    continue
    
                # Segunda requisição: detalhes do volume
                url_detalhe = f"{url_base}/{uuid}"
                resp_detalhe = requests.get(url_detalhe, auth=HTTPBasicAuth(self.us, self.ps), verify=False, timeout=10)
    
                if resp_detalhe.status_code != 200:
                    lg.logmessage(f"Erro ao buscar detalhes do volume ({uuid}): {resp_detalhe.status_code}")
                    continue
    
                detalhe = resp_detalhe.json()
    
                # Filtra apenas volumes do svm "cptm_nas"
                svm_name = detalhe.get('svm', {}).get('name')
                if svm_name != "cptm_nas":
                    continue
    
                space = detalhe.get('space', {})
                total_size += space.get('size', 0)
                total_available += space.get('available', 0)
                total_used += space.get('used', 0)
    
                if uuid_ref is None:
                    uuid_ref = uuid  # apenas para registrar no DataFrame final
    
            # Monta DataFrame final (uma linha)
            df = pd.DataFrame([{
                'data_coleta'  : data_ref,
                'hora_coleta'  : hora,
                'svm'         : "cptm_nas",
                'storage_disp'      : (total_available+total_used) / (1024**4) if total_size else None,
                #'available_tb' : total_available / (1024**4) if total_available else None,
                'storage_use'      : total_used / (1024**4) if total_used else None,
                'percent_used' : (total_used/(total_available+total_used))*100
            }])
    
            df['id_tab'] = df['data_coleta'].astype(str) + df['hora_coleta'].astype(str)
            df['id_tab'] = df['id_tab'].str.replace('-', '').str.replace(':', '')
    
            file_name = f'outputs\\ontap_svm_{data_file}.xlsx'
            df.to_excel(file_name, index=False)
            sha          = SharePoint()
            try:
                sha.exportar_csv_com_data(df, f"ontap_svm", data_file, "Documents/etl_capacity/diorama/ontap")
            except Exception as e:
                import traceback
                erro = traceback.format_exc()
                Log.logmessage(f'[ERRO] Falha ao salvar o arquivo: ontap_svm_{data_file}.csv\nDetalhes: {erro}')


            lg.logmessage("Coleta concluída com sucesso.")
    
        except Exception as e:
            lg.logmessage(f"Erro ao conectar ou buscar volumes: {e}")
            df = pd.DataFrame()
    
        finally:
            lg.logmessage("Processo concluído.")
    
        return df

# INSTACIA AS FUNCOES QUE SERAO EXECUTADAS DURANTE O PROCESSO
    def __init__(self):
        try:
            # REMOVER PROXY, SEM ESSE TRATAMENTO NÃO É POSSIVEL REALIZAR AS COLETAS

            #VARIAVEIS DE CONEXÃO COM A API
            key_api = ap.key_ontap()
            self.ip = key_api['ip']
            self.us = key_api['user']
            self.ps = key_api['password']
            cfg.retry_com_proxy(self.extrair_svm)
            cfg.retry_com_proxy(self.extrair_cluster)
            cfg.retry_com_proxy(self.extrair_aggregate)
            cfg.retry_com_proxy(self.extrair_volumes)

        except:
            lg.logmessage('[ERRO] : Processo nao executado')

if __name__ == '__main__':
    coletaNetapp()
