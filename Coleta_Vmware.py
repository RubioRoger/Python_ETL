from datetime import datetime
st = datetime.now()
data_file = st.strftime("%Y-%m-%d_%H_00_00")
hora = st.strftime("%H:00:00")

#data_ref = '2025-07-22'

data_ref = st.strftime("%Y-%m-%d")

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
from models.app import App
from models.database import DataBase
from models.logger import Log
from models.configuracoes import Config



lg = Log()
cf = Config()
db = DataBase()
ap = App()
db_key = ap.key_db('cap')

import ssl
from pyVmomi import vim
from pyVim.connect import SmartConnect,Disconnect
import math
import numpy as np

#vcenter = 'platina'
class coletaVmware():

    def coleta(self):
        key_api = ap.key_vcenter(vcenter)
        ip = key_api['ip']
        us = key_api['user']
        pw = key_api['password']
        pr = key_api['port']
    
        context = ssl._create_unverified_context() 
        
        try:
            self.si = SmartConnect(host=ip, user=us, pwd=pw, port=pr, sslContext=context)
            self.content = self.si.RetrieveContent()
        except Exception as e:
            lg.logmessage(f"Erro ao conectar no vCenter: {e}")
            exit()
        lg.logmessage(f'Conexão realizada com sucesso com a API: {vcenter}')

    def extract_cluster(self):
    
        lg.logmessage(f'# Inicio do processo de coleta de armazenamento e recursos por cluster: {vcenter}')
    
        app_view = self.content.viewManager.CreateContainerView(self.content.rootFolder, [vim.ClusterComputeResource], True)
        app_lis = app_view.view
    
        data = []
    
        for cluster in app_lis:
            try:
                nome_cluster = cluster.name
                id_cluster = str(cluster).split(":")[-1].replace("'", "")
    
                total_capacity = None
                total_free     = None
                total_memory   = None
                total_cpu_disp = None
                total_cpu_use  = None
                total_mem_use  = None
    
                seen_datastores = set()
    
                for host in cluster.host:
                    # --- Datastores únicos ---
                    for ds in host.datastore:
                        ds_id = str(ds)
                        if ds_id in seen_datastores:
                            continue
                        try:
                            if ds.summary.capacity is not None:
                                total_capacity = (total_capacity or 0) + ds.summary.capacity
                            if ds.summary.freeSpace is not None:
                                total_free = (total_free or 0) + ds.summary.freeSpace
                            seen_datastores.add(ds_id)
                        except:
                            continue
    
                    # --- Memória ---
                    try:
                        if host.hardware.memorySize is not None:
                            total_memory = (total_memory or 0) + (host.hardware.memorySize // 1024 // 1024)  # MB
                        if host.summary.quickStats.overallMemoryUsage is not None:
                            total_mem_use = (total_mem_use or 0) + host.summary.quickStats.overallMemoryUsage
                    except:
                        pass
    
                    # --- CPU ---
                    try:
                        if host.hardware.cpuInfo.hz and host.hardware.cpuInfo.numCpuCores:
                            cpu_mhz = (host.hardware.cpuInfo.hz / 1_000_000) * host.hardware.cpuInfo.numCpuCores
                            total_cpu_disp = (total_cpu_disp or 0) + int(cpu_mhz)
    
                        if host.summary.quickStats.overallCpuUsage is not None:
                            total_cpu_use = (total_cpu_use or 0) + host.summary.quickStats.overallCpuUsage
                    except:
                        pass
    
                # --- Conversões de disco (só se houver valores) ---
                disk_total_gb = round(total_capacity / 1024 / 1024 / 1024, 3) if total_capacity is not None else None
                disk_free_gb  = round(total_free / 1024 / 1024 / 1024, 3) if total_free is not None else None
                disk_used_gb  = (round(disk_total_gb - disk_free_gb, 3) 
                                 if disk_total_gb is not None and disk_free_gb is not None else None)
    
                cluster_info = {
                    "vcenter"      : vcenter,
                    "data_coleta"  : data_ref,
                    "hora_coleta"  : hora,
                    "id_cluster"   : id_cluster,
                    "nome_cluster" : nome_cluster,
                    "disk_disp"    : disk_total_gb,
                    "disk_use"     : disk_used_gb,
                    "memoria_disp" : total_memory,
                    "memoria_use"  : total_mem_use,
                    "cpu_disp"     : total_cpu_disp,
                    "cpu_use"      : total_cpu_use
                }
    
                data.append(cluster_info)
    
            except Exception as e:
                lg.logmessage(f'[ERRO] ao coletar informações do cluster {vcenter}: {cluster.name} - {str(e)}')
    
        try:
            df = pd.DataFrame(data)
    
            lg.logmessage('## Salvando informações de armazenamento e recursos dos clusters em um arquivo XLSX')
    
            for col in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[col]):
                    df[col] = df[col].apply(lambda x: x.replace(tzinfo=None) if pd.notnull(x) and hasattr(x, 'tzinfo') else x)
    
            file_name = f'outputs\\{vcenter}_dados_clusters_{data_file}.xlsx'
            df.to_excel(file_name, index=False)
    
            lg.logmessage(f'[SUCESSO] Arquivo xlsx salvo com sucesso: {file_name}')
    
        except:
            df = pd.DataFrame()
    
        return df

    def insert_cluster(self):
        df = self.extract_cluster()
#=============================================================================== TABELA HORA
        df_1 = df[['data_coleta','hora_coleta']]
    
        if df is None or df.empty:
            lg.logmessage('[ALERT] : DataFrame em branco Processo cancelado')
        else:
            lg.logmessage('[SUCESSO] : DataFrame preenchido')

            db.executar(
                f''' 
                    IF OBJECT_ID('dbo.tb_{vcenter}_cluster_hora', 'U') IS NULL
                    BEGIN
                    CREATE TABLE tb_{vcenter}_cluster_hora (
                    vcenter	       varchar(10)
                    ,data_coleta   date
                    ,hora_coleta   time(0)
                    ,id_cluster	   varchar(100)
                    ,nome_cluster  varchar(100)
                    ,disk_disp	   float
                    ,disk_use	   float
                    ,memoria_disp  float
                    ,memoria_use   float
                    ,cpu_disp	   float
                    ,cpu_use	   float
                    )end
                ''',commit=True)
            
            db.organizar_df(f'tb_{vcenter}_cluster_hora',df)
        
            db.deletar_informacoes(f'tb_{vcenter}_cluster_hora',df_1)
            df = df.where(pd.notnull(df), None)
            df = df.replace({np.nan: None})
            db.inserir_df(f'tb_{vcenter}_cluster_hora',df)

    def insert_cluster_dia(self):
#=============================================================================== TABELA DIA            
            df_2 = db.consulta_dataframe(f"select * from tb_{vcenter}_cluster_hora where data_coleta = '{data_ref}'")
            df_2.insert(0, 'id_tab', df_2['data_coleta'].astype(str).str.replace('-', '', regex=False) + df_2['id_cluster'])
            df_2['id_tab'] = df_2['id_tab'].str.replace('-', '').str.replace('domainc', '')
        
            df_2 = df_2.groupby(['id_tab', 'vcenter', 'data_coleta', 'id_cluster', 'nome_cluster']).agg(
                horas_coletadas  = ('hora_coleta'  ,'nunique'),
                max_memoria_disp = ('memoria_disp' ,'max'),
                avg_memoria_disp = ('memoria_disp' ,'mean'),
                min_memoria_disp = ('memoria_disp' ,'min'),
                max_memoria_use  = ('memoria_use'  ,'max'),
                avg_memoria_use  = ('memoria_use'  ,'mean'),
                min_memoria_use  = ('memoria_use'  ,'min'),
                max_cpu_disp     = ('cpu_disp'     ,'max'),
                avg_cpu_disp     = ('cpu_disp'     ,'mean'),
                min_cpu_disp     = ('cpu_disp'     ,'min'),
                max_cpu_use      = ('cpu_use'      ,'max'),
                avg_cpu_use      = ('cpu_use'      ,'mean'),
                min_cpu_use      = ('cpu_use'      ,'min'),
                max_disk_disp    = ('disk_disp'    ,'max'),
                avg_disk_disp    = ('disk_disp'    ,'mean'),
                min_disk_disp    = ('disk_disp'    ,'min'),
                max_disk_use     = ('disk_use'     ,'max'),
                avg_disk_use     = ('disk_use'     ,'mean'),
                min_disk_use     = ('disk_use'     ,'min'),
            ).reset_index()
        
            df_2['per_memoria_max'] = cf.cfg_percent(df_2['max_memoria_use'], df_2['max_memoria_disp'])
            df_2['per_memoria_avg'] = cf.cfg_percent(df_2['avg_memoria_use'], df_2['avg_memoria_disp'])
            df_2['per_memoria_min'] = cf.cfg_percent(df_2['min_memoria_use'], df_2['min_memoria_disp'])
            df_2['per_cpu_max']     = cf.cfg_percent(df_2['max_cpu_use'],     df_2['max_cpu_disp'])
            df_2['per_cpu_avg']     = cf.cfg_percent(df_2['avg_cpu_use'],     df_2['avg_cpu_disp'])
            df_2['per_cpu_min']     = cf.cfg_percent(df_2['min_cpu_use'],     df_2['min_cpu_disp'])
            df_2['per_disk_max']    = cf.cfg_percent(df_2['max_disk_use'],    df_2['max_disk_disp'])
            df_2['per_disk_avg']    = cf.cfg_percent(df_2['avg_disk_use'],    df_2['avg_disk_disp'])
            df_2['per_disk_min']    = cf.cfg_percent(df_2['min_disk_use'],    df_2['min_disk_disp'])

            db.executar(
                f''' 
                IF OBJECT_ID('dbo.tb_{vcenter}_cluster_dia', 'U') IS NULL
                BEGIN
                CREATE TABLE tb_{vcenter}_cluster_dia(
                id_tab               varchar(50) primary key,
                vcenter              varchar(10) NULL,
                data_coleta          date NULL,
                id_cluster           varchar(100) NULL,
                nome_cluster         varchar(100) NULL,
                horas_coletadas      int NULL,
                max_memoria_disp     float NULL,
                avg_memoria_disp     float NULL,
                min_memoria_disp     float NULL,
                max_memoria_use      float NULL,
                avg_memoria_use      float NULL,
                min_memoria_use      float NULL,
                per_memoria_max      float NULL,
                per_memoria_avg      float NULL,
                per_memoria_min      float NULL,
                max_cpu_disp         float NULL,
                avg_cpu_disp         float NULL,
                min_cpu_disp         float NULL,
                max_cpu_use          float NULL,
                avg_cpu_use          float NULL,
                min_cpu_use          float NULL,
                per_cpu_max          float NULL,
                per_cpu_avg          float NULL,
                per_cpu_min          float NULL,
                max_disk_disp        float NULL,
                avg_disk_disp        float NULL,
                min_disk_disp        float NULL,
                max_disk_use         float NULL,
                avg_disk_use         float NULL,
                min_disk_use         float NULL,
                per_disk_max         float NULL,
                per_disk_avg         float NULL,
                per_disk_min         float NULL
                )end
                ''',commit=True)

            db.organizar_df(f'tb_{vcenter}_cluster_dia',df_2)
            db.deletar_id(f'tb_{vcenter}_cluster_dia',df_2)
            df_2 = df_2.where(pd.notnull(df_2), None)
            df_2 = df_2.replace({np.nan: None})
            db.inserir_df(f'tb_{vcenter}_cluster_dia',df_2)

    def extract_host(self):
    
        lg.logmessage(f'# Inicio do processo de coleta de armazenamento e recursos por host: {vcenter}')
        
        app_view = self.content.viewManager.CreateContainerView(
            self.content.rootFolder, [vim.HostSystem], True
        )
        app_lis = app_view.view
    
        data = []
    
        for host in app_lis:
            try:
                nome_host = host.name
                id_host = str(host)[15:][:-1]
                id_host = id_host.replace(':','')
    
                total_capacity = 0
                total_free = 0
    
                for ds in host.datastore:
                    try:
                        total_capacity += ds.summary.capacity
                        total_free += ds.summary.freeSpace
                    except:
                        continue  # datastore pode não estar acessível, ignora
    
                disk_total_gb = (
                    math.trunc((total_capacity / 1024 / 1024 / 1024) * 1000) / 1000.0
                    if total_capacity else None
                )
                disk_free_gb = (
                    math.trunc((total_free / 1024 / 1024 / 1024) * 1000) / 1000.0
                    if total_free else None
                )
                disk_used_gb = (
                    disk_total_gb - disk_free_gb
                    if disk_total_gb is not None and disk_free_gb is not None else None
                )
    
                host_info = {
                    "vcenter"      : vcenter,
                    "data_coleta"  : data_ref,
                    "hora_coleta"  : hora,
                    "id_host"      : id_host,
                    "nome_host"    : nome_host,
                    "disk_disp"    : disk_total_gb,
                    "disk_use"     : disk_used_gb,
                    "memoria_disp" : host.hardware.memorySize // 1024 // 1024 if host.hardware.memorySize else None,  # MB
                    "memoria_use"  : host.summary.quickStats.overallMemoryUsage,
                    "cpu_disp"     : (
                        host.hardware.cpuInfo.hz * host.hardware.cpuInfo.numCpuCores // 1000000
                        if host.hardware.cpuInfo else None
                    ),
                    "cpu_use"      : host.summary.quickStats.overallCpuUsage
                }
    
                data.append(host_info)
            except Exception as e:
                lg.logmessage(f'## erro ao coletar informações do host {vcenter}: {host.name} | {e}')
    
        try:
            df = pd.DataFrame(data)
    
            # Mantém None (sem conversão para 0 ou "N/D")
            df = df.where(pd.notnull(df), None)
    
            # Apenas remove sufixo de hostname se existir
            if "nome_host" in df.columns:
                df["nome_host"] = df["nome_host"].astype(str).str.replace('.cptm.info', '', regex=False)
    
            lg.logmessage('## Salvando informações de armazenamento e recursos dos hosts em um arquivo XLSX')
    
            for col in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[col]):
                    df[col] = df[col].apply(
                        lambda x: x.replace(tzinfo=None) if pd.notnull(x) and hasattr(x, 'tzinfo') else x
                    )
    
            file_name = f'outputs\\{vcenter}_dados_hosts_{data_file}.xlsx'
            df.to_excel(file_name, index=False)
    
            lg.logmessage(f'[SUCESSO] : Arquivo xlsx salvo com sucesso: {file_name}')
        except Exception as e:
            lg.logmessage(f'## erro ao salvar dados de host {vcenter}: {e}')
            df = pd.DataFrame()
        
        df = df.replace({np.nan: None})
        
        return df

    def insert_host(self):
        df = self.extract_host()
#=============================================================================== TABELA HORA
        df_1 = df[['data_coleta','hora_coleta']]
    
        if df is None or df.empty:
            lg.logmessage('[ALERT] : DataFrame em branco Processo cancelado')
        else:
            lg.logmessage('[SUCESSO] : DataFrame preenchido')
    
            db.executar(
                f''' 
                    IF OBJECT_ID('dbo.tb_{vcenter}_host_hora', 'U') IS NULL
                    BEGIN
                    CREATE TABLE tb_{vcenter}_host_hora (
                    vcenter	       varchar(10)
                    ,data_coleta   date
                    ,hora_coleta   time(0)
                    ,id_host       varchar(100)
                    ,nome_host     varchar(100)
                    ,disk_disp	   float
                    ,disk_use	   float
                    ,memoria_disp  float
                    ,memoria_use   float
                    ,cpu_disp	   float
                    ,cpu_use	   float
                    )end
                ''',commit=True)
            
            db.organizar_df(f'tb_{vcenter}_host_hora',df)
        
            db.deletar_informacoes(f'tb_{vcenter}_host_hora',df_1)
            df = df.where(pd.notnull(df), None)
            df = df.replace({np.nan: None})
            db.inserir_df(f'tb_{vcenter}_host_hora',df)

    def insert_host_dia(self):
#=============================================================================== TABELA DIA
            df_2 = db.consulta_dataframe(f"select * from tb_{vcenter}_host_hora where data_coleta = '{data_ref}'")
            df_2.insert(0, 'id_tab', df_2['data_coleta'].astype(str).str.replace('-', '', regex=False) + df_2['id_host'])
            df_2['id_tab'] = df_2['id_tab'].str.replace('-', '').str.replace('host', '')
        
            df_2 = df_2.groupby(['id_tab', 'vcenter', 'data_coleta', 'id_host', 'nome_host']).agg(
                horas_coletadas  = ('hora_coleta'  ,'nunique'),
                max_memoria_disp = ('memoria_disp' ,'max'),
                avg_memoria_disp = ('memoria_disp' ,'mean'),
                min_memoria_disp = ('memoria_disp' ,'min'),
                max_memoria_use  = ('memoria_use'  ,'max'),
                avg_memoria_use  = ('memoria_use'  ,'mean'),
                min_memoria_use  = ('memoria_use'  ,'min'),
                max_cpu_disp     = ('cpu_disp'     ,'max'),
                avg_cpu_disp     = ('cpu_disp'     ,'mean'),
                min_cpu_disp     = ('cpu_disp'     ,'min'),
                max_cpu_use      = ('cpu_use'      ,'max'),
                avg_cpu_use      = ('cpu_use'      ,'mean'),
                min_cpu_use      = ('cpu_use'      ,'min'),
                max_disk_disp    = ('disk_disp'    ,'max'),
                avg_disk_disp    = ('disk_disp'    ,'mean'),
                min_disk_disp    = ('disk_disp'    ,'min'),
                max_disk_use     = ('disk_use'     ,'max'),
                avg_disk_use     = ('disk_use'     ,'mean'),
                min_disk_use     = ('disk_use'     ,'min'),
            ).reset_index()
        
            df_2['per_memoria_max'] = cf.cfg_percent(df_2['max_memoria_use'], df_2['max_memoria_disp'])
            df_2['per_memoria_avg'] = cf.cfg_percent(df_2['avg_memoria_use'], df_2['avg_memoria_disp'])
            df_2['per_memoria_min'] = cf.cfg_percent(df_2['min_memoria_use'], df_2['min_memoria_disp'])
            df_2['per_cpu_max']     = cf.cfg_percent(df_2['max_cpu_use'],     df_2['max_cpu_disp'])
            df_2['per_cpu_avg']     = cf.cfg_percent(df_2['avg_cpu_use'],     df_2['avg_cpu_disp'])
            df_2['per_cpu_min']     = cf.cfg_percent(df_2['min_cpu_use'],     df_2['min_cpu_disp'])
            df_2['per_disk_max']    = cf.cfg_percent(df_2['max_disk_use'],    df_2['max_disk_disp'])
            df_2['per_disk_avg']    = cf.cfg_percent(df_2['avg_disk_use'],    df_2['avg_disk_disp'])
            df_2['per_disk_min']    = cf.cfg_percent(df_2['min_disk_use'],    df_2['min_disk_disp'])

            db.executar(
                f''' 
                IF OBJECT_ID('dbo.tb_{vcenter}_host_dia', 'U') IS NULL
                BEGIN
                CREATE TABLE tb_{vcenter}_host_dia(
                id_tab               varchar(50) primary key,
                vcenter              varchar(10) NULL,
                data_coleta          date NULL,
                id_host              varchar(100) NULL,
                nome_host            varchar(100) NULL,
                horas_coletadas      int NULL,
                max_memoria_disp     float NULL,
                avg_memoria_disp     float NULL,
                min_memoria_disp     float NULL,
                max_memoria_use      float NULL,
                avg_memoria_use      float NULL,
                min_memoria_use      float NULL,
                per_memoria_max      float NULL,
                per_memoria_avg      float NULL,
                per_memoria_min      float NULL,
                max_cpu_disp         float NULL,
                avg_cpu_disp         float NULL,
                min_cpu_disp         float NULL,
                max_cpu_use          float NULL,
                avg_cpu_use          float NULL,
                min_cpu_use          float NULL,
                per_cpu_max          float NULL,
                per_cpu_avg          float NULL,
                per_cpu_min          float NULL,
                max_disk_disp        float NULL,
                avg_disk_disp        float NULL,
                min_disk_disp        float NULL,
                max_disk_use         float NULL,
                avg_disk_use         float NULL,
                min_disk_use         float NULL,
                per_disk_max         float NULL,
                per_disk_avg         float NULL,
                per_disk_min         float NULL
                )end
                ''',commit=True)

            db.organizar_df(f'tb_{vcenter}_host_dia',df_2)
        
            db.deletar_id(f'tb_{vcenter}_host_dia',df_2)
            df_2 = df_2.where(pd.notnull(df_2), None)
            df_2 = df_2.replace({np.nan: None})
            db.inserir_df(f'tb_{vcenter}_host_dia',df_2)

    def extract_datastore(self):
    
        Log.logmessage(f'# Inicio do processo de coleta das informacoes dos Datastores: {vcenter}')
        
        app_view = self.content.viewManager.CreateContainerView(
            self.content.rootFolder, [vim.Datastore], True
        )
        app_lis = app_view.view
    
        data = []
    
        for ds in app_lis:
            try:
                ds_info = {
                    "vcenter"        : vcenter,
                    "data_coleta"    : data_ref,
                    "hora_coleta"    : hora,
                    "id_datastore"   : str(ds)[15:][:-1],
                    "nome_datastore" : ds.name,
                    "disk_disp"      : (
                        math.trunc((ds.summary.capacity / 1024 / 1024 / 1024) * 1000) / 1000.0
                        if ds.summary.capacity else None
                    ),
                    "disk_use"       : (
                        math.trunc(((ds.summary.capacity - ds.summary.freeSpace) / 1024 / 1024 / 1024) * 1000) / 1000.0
                        if ds.summary.capacity and ds.summary.freeSpace else None
                    )
                }
                data.append(ds_info)
            except Exception as e:
                Log.logmessage(f'## erro ao coletar informações do datastore {vcenter}: {ds.name} | {e}')
        
        df = pd.DataFrame(data)
    
        # Mantém None (não substitui por 0 ou string)
        df = df.where(pd.notnull(df), None)
    
        Log.logmessage('## Salvando informações dos datastores em um arquivo XLSX')
        
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].apply(
                    lambda x: x.replace(tzinfo=None) if pd.notnull(x) and hasattr(x, 'tzinfo') else x
                )
    
        file_name = f'outputs\\{vcenter}_dados_datastores_{data_file}.xlsx'
        df.to_excel(file_name, index=False)
    
        Log.logmessage(f'[SUCESSO] : Arquivo xlsx salvo com sucesso: {file_name}')

        df = df.replace({np.nan: None})
    
        return df

    def insert_datastore(self):
        df = self.extract_datastore()
#=============================================================================== TABELA HORA
        df_1 = df[['data_coleta','hora_coleta']]
    
        if df is None or df.empty:
            lg.logmessage('[ALERT] : DataFrame em branco Processo cancelado')
        else:
            lg.logmessage('[SUCESSO] : DataFrame preenchido')

            db.executar(
                f''' 
                    IF OBJECT_ID('dbo.tb_{vcenter}_datastore_hora', 'U') IS NULL
                    BEGIN
                    CREATE TABLE tb_{vcenter}_datastore_hora (
                    vcenter           varchar(10)
                    ,data_coleta      date
                    ,hora_coleta      time(0)
                    ,id_datastore     varchar(100)
                    ,nome_datastore   varchar(100)
                    ,disk_disp	      float
                    ,disk_use	      float
                    )end
                ''',commit=True)
            
            db.organizar_df(f'tb_{vcenter}_datastore_hora',df)
        
            db.deletar_informacoes(f'tb_{vcenter}_datastore_hora',df_1)
            df = df.where(pd.notnull(df), None)
            df = df.replace({np.nan: None})
            db.inserir_df(f'tb_{vcenter}_datastore_hora',df)

    def insert_datastore_dia(self):
#=============================================================================== TABELA HORA
            df_2 = db.consulta_dataframe(f"select * from tb_{vcenter}_datastore_hora where data_coleta = '{data_ref}'")
            df_2.insert(0, 'id_tab', df_2['data_coleta'].astype(str).str.replace('-', '', regex=False) + df_2['id_datastore'])
            df_2['id_tab'] = df_2['id_tab'].str.replace('-', '').str.replace('domainc', '')
            
            df_2 = df_2.groupby(['id_tab', 'vcenter', 'data_coleta', 'id_datastore', 'nome_datastore']).agg(
            horas_coletadas  = ('hora_coleta'  ,'nunique'),
            max_disk_disp    = ('disk_disp'    ,'max'),
            avg_disk_disp    = ('disk_disp'    ,'mean'),
            min_disk_disp    = ('disk_disp'    ,'min'),
            max_disk_use     = ('disk_use'     ,'max'),
            avg_disk_use     = ('disk_use'     ,'mean'),
            min_disk_use     = ('disk_use'     ,'min'),
            ).reset_index()

            df_2['per_disk_max']    = cf.cfg_percent(df_2['max_disk_use'],    df_2['max_disk_disp'])
            df_2['per_disk_avg']    = cf.cfg_percent(df_2['avg_disk_use'],    df_2['avg_disk_disp'])
            df_2['per_disk_min']    = cf.cfg_percent(df_2['min_disk_use'],    df_2['min_disk_disp'])

            db.executar(
                f''' 
                IF OBJECT_ID('dbo.tb_{vcenter}_datastore_dia', 'U') IS NULL
                BEGIN
                CREATE TABLE tb_{vcenter}_datastore_dia(
                id_tab varchar(50) primary key,
                vcenter varchar(10) NULL,
                data_coleta date NULL,
                id_datastore varchar(100) NULL,
                nome_datastore varchar(100) NULL,
                horas_coletadas      int NULL,
                max_disk_disp float NULL,
                avg_disk_disp float NULL,
                min_disk_disp float NULL,
                max_disk_use float NULL,
                avg_disk_use float NULL,
                min_disk_use float NULL,
                per_disk_max float NULL,
                per_disk_avg float NULL,
                per_disk_min float NULL
                )end
                ''',commit=True)

            db.organizar_df(f'tb_{vcenter}_datastore_dia',df_2)
        
            db.deletar_id(f'tb_{vcenter}_datastore_dia',df_2)
            df_2 = df_2.where(pd.notnull(df_2), None)
            df_2 = df_2.replace({np.nan: None})
            db.inserir_df(f'tb_{vcenter}_datastore_dia',df_2)

    def extract_virtual_machine(self):
        lg.logmessage(f'# Inicio do processo de coleta das informacoes da API: {vcenter} virtual machine')
        
        app_view = self.content.viewManager.CreateContainerView(
            self.content.rootFolder, [vim.VirtualMachine], True
        )
        app_lis = app_view.view
    
        data = []
    
        for vm in app_lis:
            try:
                vm_info = {
                    "vcenter"        : vcenter,
                    "data_coleta"    : data_ref,
                    "hora_coleta"    : hora,
                    "host"           : str(vm.summary.runtime.host)[16:][:-1],
                    "nome_host"      : vm.summary.guest.hostName,
                    "datastore"      : ", ".join([ds.name for ds in vm.datastore]),
                    "id_datastore"   : str(vm.datastore[0])[15:][:-1],
                    "ip"             : vm.guest.ipAddress,
                    "id"             : str(vm).split(":")[-1][:-1],
                    "servidor"       : vm.name,
                    "status"         : vm.runtime.powerState,
                    "memoria_disp"   : vm.summary.config.memorySizeMB,
                    "memoria_use"    : vm.summary.quickStats.guestMemoryUsage,
                    "cpu_disp"       : vm.runtime.maxCpuUsage,
                    "cpu_use"        : vm.summary.quickStats.overallCpuUsage
                }
                
                # Coleta de disco por partição
                if not getattr(vm.guest, "disk", None):
                    data.append(vm_info)
                else:
                    for disk in vm.guest.disk:
                        vm_info_copy              = vm_info.copy()
                        vm_info_copy["disk"]      = disk.diskPath if disk.diskPath else None
                        vm_info_copy["disk_disp"] = (
                            math.trunc((float(disk.capacity) / 1024 / 1024 / 1024) * 1000) / 1000.0
                            if disk.capacity else None
                        )
                        vm_info_copy["disk_use"]  = (
                            math.trunc(((float(disk.capacity) - float(disk.freeSpace)) / 1024 / 1024 / 1024) * 1000) / 1000.0
                            if disk.capacity and disk.freeSpace else None
                        )
                        data.append(vm_info_copy)
    
            except Exception as e:
                Log.logmessage(f'## erro ao coletar informações da vm {vcenter}: {vm.name} | {e}')
    
        df = pd.DataFrame(data)
    
        # Não converte mais nada para 0 ou 'N/D'
        # Apenas mantém None (ou NaN do pandas, que no Excel vira célula vazia)
        df = df.where(pd.notnull(df), None)
    
        Log.logmessage('## Salvando informações em um arquivo XLSX')
    
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].apply(
                    lambda x: x.replace(tzinfo=None) if pd.notnull(x) and hasattr(x, 'tzinfo') else x
                )
    
        file_name = f'outputs\\{vcenter}_dados_vms_{data_file}.xlsx'
        df.to_excel(file_name, index=False)
        lg.logmessage(f'### Arquivo xlsx salvo com sucesso: {file_name}')

        df = df.replace({np.nan: None})
        
        return df

    def insert_virtual_machine(self):
        df = self.extract_virtual_machine()
#=============================================================================== TABELA HORA
        df_1 = df[['data_coleta','hora_coleta']]
    
        if df is None or df.empty:
            lg.logmessage('[ALERT] : DataFrame em branco Processo cancelado')
        else:
            lg.logmessage('[SUCESSO] : DataFrame preenchido')

            db.executar(
                f''' 
                    IF OBJECT_ID('dbo.tb_{vcenter}_vm_hora', 'U') IS NULL
                    BEGIN
                    CREATE TABLE tb_{vcenter}_vm_hora(
                    vcenter              varchar(10)         NOT NULL,
                    data_coleta          date                NULL,
                    hora_coleta          time(0)             NULL,
                    host                 varchar(500)        NULL,
                    nome_host            varchar(500)        NULL,
                    datastore            varchar(1000)       NULL,
                    id_datastore         varchar(500)        NULL,
                    ip                   varchar(500)        NULL,
                    id                   varchar(500)        NULL,
                    servidor             varchar(500)        NULL,
                    status               varchar(100)        NULL,
                    memoria_disp         float               NULL,
                    memoria_use          float               NULL,
                    cpu_disp             float               NULL,
                    cpu_use              float               NULL,
                    disk_disp            float               NULL,
                    disk_use             float               NULL,
                    disk                 varchar(500)        NULL
                    )end
                ''',commit=True)
            
            db.organizar_df(f'tb_{vcenter}_vm_hora',df)
        
            db.deletar_informacoes(f'tb_{vcenter}_vm_hora',df_1)
        
            db.inserir_df(f'tb_{vcenter}_vm_hora',df)
#=============================================================================== TABELA DIA
            df_2 = db.consulta_dataframe(f"select * from tb_{vcenter}_vm_hora where status = 'poweredOn' and data_coleta = '{data_ref}'")
            df_2['ip'] = df_2['ip'].fillna('SEM_IP')
            df_2 = df_2.groupby(['vcenter', 'data_coleta', 'hora_coleta', 'ip', 'id', 'servidor']).agg(
                memoria_disp = ('memoria_disp', 'max'),
                memoria_use  = ('memoria_use',  'max'),
                cpu_disp     = ('cpu_disp',     'max'),
                cpu_use      = ('cpu_use',      'max'),
                disk_disp    = ('disk_disp',    'sum'),  # somando partições
                disk_use     = ('disk_use',     'sum')
            ).reset_index()
        
            # Segundo agrupamento: agregações finais por VM
            df_2 = df_2.groupby(['vcenter', 'data_coleta','ip','id', 'servidor']).agg(
                horas_coletadas  = ('hora_coleta',  'nunique'),
                max_memoria_disp = ('memoria_disp', 'max'),
                avg_memoria_disp = ('memoria_disp', 'mean'),
                min_memoria_disp = ('memoria_disp', 'min'),
                max_memoria_use  = ('memoria_use',  'max'),
                avg_memoria_use  = ('memoria_use',  'mean'),
                min_memoria_use  = ('memoria_use',  'min'),
                max_cpu_disp     = ('cpu_disp',     'max'),
                avg_cpu_disp     = ('cpu_disp',     'mean'),
                min_cpu_disp     = ('cpu_disp',     'min'),
                max_cpu_use      = ('cpu_use',      'max'),
                avg_cpu_use      = ('cpu_use',      'mean'),
                min_cpu_use      = ('cpu_use',      'min'),
                max_disk_disp    = ('disk_disp',    'max'),
                avg_disk_disp    = ('disk_disp',    'mean'),
                min_disk_disp    = ('disk_disp',    'min'),
                max_disk_use     = ('disk_use',     'max'),
                avg_disk_use     = ('disk_use',     'mean'),
                min_disk_use     = ('disk_use',     'min')
            ).reset_index()
        
            # Percentuais
            df_2['per_memoria_max'] = cf.cfg_percent(df_2['max_memoria_use'], df_2['max_memoria_disp'])
            df_2['per_memoria_avg'] = cf.cfg_percent(df_2['avg_memoria_use'], df_2['avg_memoria_disp'])
            df_2['per_memoria_min'] = cf.cfg_percent(df_2['min_memoria_use'], df_2['min_memoria_disp'])
            df_2['per_cpu_max']     = cf.cfg_percent(df_2['max_cpu_use'],     df_2['max_cpu_disp'])
            df_2['per_cpu_avg']     = cf.cfg_percent(df_2['avg_cpu_use'],     df_2['avg_cpu_disp'])
            df_2['per_cpu_min']     = cf.cfg_percent(df_2['min_cpu_use'],     df_2['min_cpu_disp'])
            df_2['per_disk_max']    = cf.cfg_percent(df_2['max_disk_use'],    df_2['max_disk_disp'])
            df_2['per_disk_avg']    = cf.cfg_percent(df_2['avg_disk_use'],    df_2['avg_disk_disp'])
            df_2['per_disk_min']    = cf.cfg_percent(df_2['min_disk_use'],    df_2['min_disk_disp'])
    
            db.executar(
                f''' 
                IF OBJECT_ID('dbo.tb_{vcenter}_vm_dia', 'U') IS NULL
                BEGIN
                CREATE TABLE tb_{vcenter}_vm_dia(
                vcenter varchar(10) NOT NULL,
                data_coleta date NULL,
                ip varchar(500) NULL,
                id varchar(500) NULL,
                servidor varchar(500) NULL,
                horas_coletadas int NULL,
                max_memoria_disp float NULL,
                avg_memoria_disp float NULL,
                min_memoria_disp float NULL,
                max_memoria_use float NULL,
                avg_memoria_use float NULL,
                min_memoria_use float NULL,
                per_memoria_max float NULL,
                per_memoria_avg float NULL,
                per_memoria_min float NULL,
                max_cpu_disp float NULL,
                avg_cpu_disp float NULL,
                min_cpu_disp float NULL,
                max_cpu_use float NULL,
                avg_cpu_use float NULL,
                min_cpu_use float NULL,
                per_cpu_max float NULL,
                per_cpu_avg float NULL,
                per_cpu_min float NULL,
                max_disk_disp float NULL,
                avg_disk_disp float NULL,
                min_disk_disp float NULL,
                max_disk_use float NULL,
                avg_disk_use float NULL,
                min_disk_use float NULL,
                per_disk_max float NULL,
                per_disk_avg float NULL,
                per_disk_min float NULL
                ) end
                ''',commit=True)
            
            db.organizar_df(f'tb_{vcenter}_vm_dia',df_2)
        
            db.executar(f"delete from tb_{vcenter}_vm_dia where data_coleta ='{data_ref}' ",commit=True)
            df_2 = df_2.where(pd.notnull(df_2), None)
            df_2 = df_2.replace({np.nan: None})
            db.inserir_df(f'tb_{vcenter}_vm_dia',df_2)

    def insert_disk(self):
        df_2 = db.consulta_dataframe(f"select * from tb_{vcenter}_vm_hora where status = 'poweredOn' and data_coleta = '{data_ref}' ")

        db.executar(f'''
                IF OBJECT_ID('dbo.tb_{vcenter}_disk_dia', 'U') IS NULL
                BEGIN
                CREATE TABLE dbo.tb_{vcenter}_disk_dia(
                vcenter varchar(10) NOT NULL,
                data_coleta date NULL,
                ip varchar(500) NULL,
                id varchar(500) NULL,
                servidor varchar(500) NULL,
                disk varchar(500) NULL,
                max_disk_disp float NULL,
                avg_disk_disp float NULL,
                min_disk_disp float NULL,
                max_disk_use float NULL,
                avg_disk_use float NULL,
                min_disk_use float NULL,
                per_disk_max float NULL,
                per_disk_avg float NULL,
                per_disk_min float NULL
                )end 
                ''',commit=True)
        
        df_2 = df_2.groupby(['vcenter', 'data_coleta', 'disk', 'ip', 'id', 'servidor']).agg(
            max_disk_disp    = ('disk_disp',    'max'),
            avg_disk_disp    = ('disk_disp',    'mean'),
            min_disk_disp    = ('disk_disp',    'min'),
            max_disk_use     = ('disk_use',     'max'),
            avg_disk_use     = ('disk_use',     'mean'),
            min_disk_use     = ('disk_use',     'min')
        ).reset_index()
        df_2['per_disk_max']    = cf.cfg_percent(df_2['max_disk_use'],    df_2['max_disk_disp'])
        df_2['per_disk_avg']    = cf.cfg_percent(df_2['avg_disk_use'],    df_2['avg_disk_disp'])
        df_2['per_disk_min']    = cf.cfg_percent(df_2['min_disk_use'],    df_2['min_disk_disp'])

        db.organizar_df(f'tb_{vcenter}_disk_dia',df_2)
    
        db.executar(f"delete from tb_{vcenter}_disk_dia where data_coleta = '{data_ref}' ")

        df_2 = df_2.where(pd.notnull(df_2), None)
        df_2 = df_2.replace({np.nan: None})

        db.inserir_df(f'tb_{vcenter}_disk_dia',df_2)

    def __init__(self):
        try:
            self.coleta()
            self.insert_cluster()
            self.insert_cluster_dia()
            self.insert_host()
            self.insert_host_dia()
            self.insert_datastore()
            self.insert_datastore_dia()
            self.insert_virtual_machine()
            self.insert_disk()
            #self.view()
            Disconnect(self.si)
        except: lg.logmessage('[ERRO] Processo nao executado')

def executar():
    db.conectar(db_key)
    lista = ap.vmware_list().split(",")
    for i in lista:
        global vcenter
        vcenter = i
        coletaVmware()
    db.desconectar()

if __name__ == '__main__':
    executar()

