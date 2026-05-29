import warnings
warnings.filterwarnings("ignore")

import requests
from   requests.auth import HTTPBasicAuth
import pandas as pd
from   datetime import datetime

from models.app    import App
from models.logger import Log
from models.sharepoint import SharePoint
from models.configuracoes import Config

log = Log()
cfg = Config()
st = datetime.now()
data_file = st.strftime("%Y-%m-%d_%H_00_00")
data_ref = st.strftime("%Y-%m-%d")

log.logmessage('Procurando credenciais OEM dentro do arquivo APP Config')
app = App()
credentials = app.key_oem()
ip   =  credentials['ip']
port =  credentials['port']
usu  =  credentials['user']
psw  =  credentials['password']

class coletaOEM:

    def __init__(self):
        try:
            log.logmessage('[INICIO] : Realizando processo de coleta OEM')
            log.logmessage('[PARAMETROS] : Carregando informações dos targets para realizar as coletas da metricas (nome e id)')
            cfg.retry_com_proxy(self.coleta_target)
        except: log.logmessage('[ERRO] : Não foi possivel realizar as coletas das informações de nome e id dos targets')

        try:
            log.logmessage('Coletando informa de filesystem')
            cfg.retry_com_proxy(self.coleta_filesystem)
            log.logmessage('Coleta realizada com sucesso')
        except: log.logmessage('[ERRO] : Não foi possivel realiza a coleta')

        try:
            log.logmessage('Coletando informa de Memória e CPU host')
            cfg.retry_com_proxy(self.coleta_host)
            log.logmessage('Coleta realizada com sucesso')
        except: log.logmessage('[ERRO] : Não foi possivel realiza a coleta')

        try:
            log.logmessage('Coletando informa de CPU database')
            cfg.retry_com_proxy(self.coleta_instancia)
            log.logmessage('Coleta realizada com sucesso')
        except: log.logmessage('[ERRO] : Não foi possivel realiza a coleta')

        try:
            log.logmessage('Coletando informa de para')
            cfg.retry_com_proxy(self.coleta_de_para)
            log.logmessage('Coleta realizada com sucesso')
        except: log.logmessage('[ERRO] : Não foi possivel realiza a coleta')

    def coleta_target(self):
        try:
            log.logmessage('[CONEXAO]  Realizando conexão com OEM')
            url_props = f"https://{ip}:{port}/em/api/targets"
            
            response = requests.get(url_props, auth=HTTPBasicAuth(usu, psw), verify=False)
            
            if response.status_code == 200:
                data = response.json()
    
                target_info = []
            
                for item in data.get('items', []):
                    target_info.append({
                        'name': item.get('name'),
                        'typeName': item.get('typeName'),
                        'id': item.get('id'),
                        'displayName': item.get('displayName'),
                        'owner': item.get('owner'),
                    })
        except: log.logmessage('[CONEXAO] : Não foi possivel realizar conexão com OEM')

        try:
            log.logmessage('[PREPARACAO] : Transformando json em dataframe')
            df = pd.DataFrame(target_info)
        except: log.logmessage('[PREPARACAO] : Não foi possivel tranformacao json em dataframe')
        
        log.logmessage('[HOST] :  Separando apenas as informações pertinentes a host')

        try:
            log.logmessage('[HOST] :  Separando apenas as informações pertinentes a host')
            df_host = df
            df_host = df[df['typeName'] == 'host']
        except: log.logmessage('[HOST] : Não foi possivel coletas as informações dos host')

        try:
            log.logmessage('[HOST] :  criando lista com os nomes dos host')
            self.lista_host = df_host['name'].tolist()
        except: log.logmessage('[HOST] : Não foi possivel coletas os nomes dos host')

        try:
            log.logmessage('[HOST] :  criando lista com os id dos host')
            self.lista_id_host = df_host['id'].tolist()
        except: log.logmessage('[HOST] : Não foi possivel coletas os nomes dos host')

        try:
            log.logmessage('[DATABASE] :  Separando apenas as informações pertinentes a oracle_database')
            df_oracle_database = df
            self.df_oracle_database = df_oracle_database[df_oracle_database['typeName'] == 'oracle_database']
        except: log.logmessage('[DATABASE] : Não foi possivel coletas as informações dos oracle_database')

        try:
            log.logmessage('[DATABASE] :  criando lista com os id dos oracle_database')
            self.df_oracle_database = self.df_oracle_database['id'].tolist()
        except: log.logmessage('[DATABASE] : Não foi possivel coletas os nomes dos oracle_database')

    def coleta_filesystem(self):
        coletor = []  # Lista para armazenar todos os DataFrames
        try:
            log.logmessage('[INICIO] :  Coletando métricas de Filesystem dos hosts via conexão HTTP')
            for n in self.lista_id_host:
                url_props = f"https://{ip}:{port}/em/api/targets/{n}/metricGroups/Filesystems/latestData"

                
                response = requests.get(url_props, auth=HTTPBasicAuth(usu, psw), verify=False)
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get('items', [])
                    
                    df = pd.DataFrame(items)
                    
                    df['host'] = data.get('targetName')
                    df['tipo'] = data.get('targetTypeName')
                    df['id'] = data.get('targetId')
                    df['data_coleta'] = data.get('timeCollected')
                    
                    coletor.append(df)
                else:
                    log.logmessage(f"[ERRO] : Falha na requisição HTTP para o host {n} - Status {response.status_code}")
        except:
            log.logmessage('[ERRO] : Não foi possível coletar as informações de Filesystem.')
    
        try:
            log.logmessage('[FINAL] : Preparando dados de Filesystem para armazenamento')
            if coletor:
                try:
                    df_final = pd.concat(coletor, ignore_index=True)
                except:
                    log.logmessage('[ERRO] : DataFrame vazio, não foi possível unificar as informações de Filesystem.')
    
                try:
                    df_final = df_final.rename(columns={
                        'size': 'disk_disp',
                        'pctAvailable': 'per_disk',
                        'available': 'disk_use',
                        'fileSystem': 'disk',
                    })
                    df_final['data_coleta'] = pd.to_datetime(df_final['data_coleta'], utc=True)
                    df_final['hora_coleta'] = df_final['data_coleta'].dt.strftime('%H:00:00')
                    df_final['data_coleta'] = df_final['data_coleta'].dt.date  
                    sha = SharePoint()

                    sha.exportar_csv_com_data(df_final, f"coleta_oem_filesystem_", data_file, "Documents/etl_capacity/diorama/oem")
                    log.logmessage(f"[ARQUIVO] : SALVO COM SUCESSO Documents/etl_capacity/diorama/oem/coleta_oem_filesystem_{data_file}")
                except:
                    log.logmessage(f"[ARQUIVO] : NÃO FOI POSSÍVEL SALVAR Documents/etl_capacity/diorama/oem/coleta_oem_filesystem_{data_file}")
            else:
                log.logmessage('[INFO] : Nenhum dado de Filesystem foi coletado.')
        except:
            log.logmessage('[ERRO] : Falha ao tentar salvar o arquivo de Filesystem.')

    def coleta_host(self):
        coletor = []  # Lista para armazenar todos os DataFrames
        try:
            log.logmessage('[INICIO] :  Coletando id dos hosts para realizar a conexão http')
            for n in self.lista_id_host:
                url_props = f"https://{ip}:{port}/em/api/targets/{n}/metricGroups/Load/latestData"
                
                response = requests.get(url_props, auth=HTTPBasicAuth(usu, psw), verify=False)
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get('items', [])
                    
                    df = pd.DataFrame(items)

                    df['host'] = data.get('targetName')
                    df['tipo'] = data.get('targetTypeName')
                    df['id'] = data.get('targetId')
                    df['data_coleta'] = data.get('timeCollected')
                    
                    coletor.append(df)
                else:
                    print(f"Erro na requisição para o host {n}: {response.status_code}")
        except: log.logmessage(f'[ERRO] : Não foi possivel coletar as informações.')
        # 1️⃣ Converter para datetime (garantindo que seja datetime)

        try:
            log.logmessage('[FINAL] : Prepa rando dados para armazenamento')
            if coletor: 
                try:
                    df_final = pd.concat(coletor, ignore_index=True)
                    df_final['data_coleta'] = pd.to_datetime(df_final['data_coleta'], utc=True)
                    df_final['hora_coleta'] = df_final['data_coleta'].dt.strftime('%H:00:00')
                    df_final['data_coleta'] = df_final['data_coleta'].dt.date 
                except: log.logmessage('[ERRO] : Dataframe vazio, não foi possivel unificar informações')

                try:
                    df_final = df_final[['data_coleta','host','id','tipo','cpuUtil','memUsedPct','hora_coleta']]
                    df_final = df_final.rename(columns={
                        'cpuUtil': 'per_cpu',
                        'memUsedPct': 'per_memoria',
                    })
                    sha = SharePoint()
                    sha.exportar_csv_com_data(df_final,f"coleta_oem_host_",data_file,"Documents/etl_capacity/diorama/oem")
                    log.logmessage(F'[ARQUIVO] : SALVO COM SUCESSO Documents/etl_capacity/diorama/oem/coleta_oem_host{data_file}')
                
                except:
                    log.logmessage(F'[ARQUIVO] : NÃO FOI POSSIVEL SALVAR Documents/etl_capacity/diorama/oem/coleta_oem_host{data_file}')
            else:
                print("Nenhum dado foi coletado.")
        except: log.logmessage('[ERRO] : Não foi possivel salvar o arquivo')

    def coleta_instancia(self):
        coletor = [] 
        try:
            log.logmessage('[INICIO] : Coletando dados de instâncias')
            for n in self.df_oracle_database:
                url_props = f"https://{ip}:{port}/em/api/targets/{n}/metricGroups/instance_efficiency/latestData"
                
                response = requests.get(url_props, auth=HTTPBasicAuth(usu, psw), verify=False)
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get('items', [])
                    
                    df = pd.DataFrame(items)
                    
                    df['nome_database'] = data.get('targetName')
                    df['grupo_de_metricas'] = data.get('metricGroupName')
                    df['data_coleta'] = data.get('timeCollected')
    
                    if 'cpu_time_pct' in df.columns:
                        df = df[['nome_database', 'grupo_de_metricas', 'data_coleta', 'cpu_time_pct']]
                    else:
                        df = df[['nome_database', 'grupo_de_metricas', 'data_coleta'] + [c for c in df.columns if c not in ['nome_database', 'grupo_de_metricas', 'data_coleta']]]
    
                    coletor.append(df)
                else:
                    print(f"Erro na requisição para o target {n}: {response.status_code}")
        except Exception as e:
            log.logmessage(f'[ERRO] : Falha ao coletar dados das instâncias. Detalhe: {e}')
        try:
            log.logmessage('[FINAL] : Preparando dados para armazenamento')
            if coletor:
                try:
                    df = pd.concat(coletor, ignore_index=True)
                except Exception as e:
                    log.logmessage(f'[ERRO] : Falha ao unificar DataFrames: {e}')
                    return
    
                try:
                    df_final = df.rename(columns={
                        'cpu_time_pct': 'cpu_use',
                    })
                    df_final['data_coleta'] = pd.to_datetime(df_final['data_coleta'], utc=True)
                    df_final['hora_coleta'] = df_final['data_coleta'].dt.strftime('%H:00:00')
                    df_final['data_coleta'] = df_final['data_coleta'].dt.date 

                    sha = SharePoint()
                    sha.exportar_csv_com_data(df_final, f"coleta_database_", data_file, "Documents/etl_capacity/diorama/oem")
                    log.logmessage(f"[ARQUIVO] : SALVO COM SUCESSO Documents/etl_capacity/diorama/oem/coleta_database{data_file}")
                except:
                    log.logmessage(f"[ARQUIVO] : NÃO FOI POSSÍVEL SALVAR Documents/etl_capacity/diorama/oem/coleta_database{data_file}")
            else:
                log.logmessage('[INFO] : Nenhum dado de coleta_database foi coletado.')
        except:
            log.logmessage('[ERRO] : Falha ao tentar salvar o arquivo de Filesystem.')

    def coleta_de_para(self):

        coletor = [] 
        try:
            log.logmessage('[INICIO] : Coletando dados de instâncias')
            for n in self.df_oracle_database:
                url_props = f"https://{ip}:{port}/em/api/targets/{n}/properties"
                
                response = requests.get(url_props, auth=HTTPBasicAuth(usu, psw), verify=False)
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get('items', [])
                    
                    df = pd.DataFrame(items)
    
                    # ---------------------------
                    # FILTRA E PIVOTA: InstanceName e MachineName
                    # ---------------------------
                    df_filt = df[df['id'].isin(['InstanceName', 'MachineName'])]
    
                    if not df_filt.empty:
                        df_pivot = df_filt.pivot_table(
                            index=None,
                            columns='id',
                            values='value',
                            aggfunc='first'
                        ).reset_index(drop=True)
                    else:
                        df_pivot = pd.DataFrame()
                    
                    df_pivot['id_target'] = n                                 # ← AQUI
                    df_pivot['MachineName'] = df_pivot['MachineName'].str.replace('-vip', '', regex=False)
                    
                    coletor.append(df_pivot)
    
                else:
                    print(f"Erro na requisição para o target {n}: {response.status_code}")
        except Exception as e:
            log.logmessage(f'[ERRO] : Falha ao coletar dados das instâncias. Detalhe: {e}')
    
        try:
            log.logmessage('[FINAL] : Preparando dados para armazenamento')
            if coletor:
                try:
                    df = pd.concat(coletor, ignore_index=True)
                except Exception as e:
                    log.logmessage(f'[ERRO] : Falha ao unificar DataFrames: {e}')
                    return
                
                sha = SharePoint()
                sha.exportar_csv_com_data(df, f"coleta_de_para_", data_file, "Documents/etl_capacity/diorama/oem")
                log.logmessage(f"[ARQUIVO] : SALVO COM SUCESSO Documents/etl_capacity/diorama/oem/coleta_de_para_{data_file}")
    
            else:
                log.logmessage('[INFO] : Nenhum dado de coleta_de_para_ foi coletado.')
        except:
            log.logmessage('[ERRO] : Falha ao tentar salvar o arquivo de Filesystem.')

if __name__ == '__main__':
    coletaOEM()